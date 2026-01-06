#!/usr/bin/env python3
"""缠论 AI 分析命令行工具

用法:
    python chanlun_ai.py BTCUSDT 1h              # 基础分析
    python chanlun_ai.py ETHUSDT 4h --save       # 分析并保存报告
    python chanlun_ai.py BTCUSDT 1h --limit 500  # 指定K线数量
    python chanlun_ai.py BTCUSDT 1h --simple     # 快速分析（简化Prompt）
    python chanlun_ai.py BTCUSDT 1h --table      # 表格格式输入（输出Markdown）
    python chanlun_ai.py BTCUSDT 1h --structured # 强制JSON输出

示例:
    python chanlun_ai.py BTCUSDT 1h
    python chanlun_ai.py ETHUSDT 4h --save
    python chanlun_ai.py BTCUSDT 1h --table
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import sqlite3
from dotenv import load_dotenv

import pandas as pd
import yaml

# 项目模块导入
from binance import get_klines
from chanlun_adapter import convert_to_chanlun_bars
from chanlun_icl import ICL
from chanlun_ai_exporter import ChanlunAIExporter
from prompt_builder import build_prompt, build_simple_prompt, build_structured_prompt, build_table_format_prompt, build_structured_table_prompt
from output_formatter import format_cli_output
from ai.llm import call_ai
from ai_output_schema import validate_ai_output


# ============================================
# 数据库功能（SQLite）
# ============================================

DB_PATH = Path(__file__).parent / "chanlun_ai.db"


def get_db_conn():
    """获取数据库连接"""
    return sqlite3.connect(DB_PATH)


def init_db():
    """初始化数据库表结构（首次运行时自动创建）"""
    conn = get_db_conn()
    c = conn.cursor()

    # 表 1: analysis_snapshot（分析快照）
    c.execute("""
    CREATE TABLE IF NOT EXISTS analysis_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        interval TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        price REAL NOT NULL,
        chanlun_json TEXT NOT NULL,
        ai_json TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # 表 2: analysis_outcome（未来结果回填）
    c.execute("""
    CREATE TABLE IF NOT EXISTS analysis_outcome (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        check_after_minutes INTEGER NOT NULL,
        future_price REAL NOT NULL,
        max_price REAL NOT NULL,
        min_price REAL NOT NULL,
        result_direction TEXT NOT NULL,
        hit_scenario_rank INTEGER,
        note TEXT,
        checked_at TEXT NOT NULL,
        FOREIGN KEY(snapshot_id) REFERENCES analysis_snapshot(id)
    )
    """)

    conn.commit()
    conn.close()


def save_snapshot(symbol: str, interval: str, price: float, chanlun_json: dict, ai_json: dict = None):
    """保存一次分析快照到数据库
    
    参数：
    - symbol: 交易对（如 BTC/USDT）
    - interval: 周期（如 1h）
    - price: 当前价格
    - chanlun_json: 完整的缠论结构 JSON（exporter 导出的）
    - ai_json: AI 输出的 JSON（如果有结构化输出）
    
    返回：
    - snapshot_id: 插入的记录 ID
    """
    conn = get_db_conn()
    c = conn.cursor()
    # 使用 UTC 时间（与 Binance API 保持一致）
    from datetime import timezone
    now = datetime.now(timezone.utc).isoformat()

    c.execute("""
        INSERT INTO analysis_snapshot
        (symbol, interval, timestamp, price, chanlun_json, ai_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol,
        interval,
        now,
        float(price),
        json.dumps(chanlun_json, ensure_ascii=False),
        json.dumps(ai_json, ensure_ascii=False) if ai_json else None,
        now,
    ))

    snapshot_id = c.lastrowid
    conn.commit()
    conn.close()

    return snapshot_id


def judge_hit(ai_json: dict, max_price: float, min_price: float):
    """判断未来价格是否命中 AI 预测的某个 scenario
    
    参数：
    - ai_json: AI 输出的结构化 JSON
    - max_price: 未来时间段内的最高价
    - min_price: 未来时间段内的最低价
    
    返回：
    - hit_scenario_rank: 命中的 scenario 的 rank（1, 2, 3...），无命中返回 None
    """
    if not ai_json:
        return None

    scenarios = ai_json.get("scenarios", [])
    for s in scenarios:
        target_range = s.get("target_range")
        rank = s.get("rank")

        if not target_range or len(target_range) != 2:
            continue

        low, high = target_range
        # 只要未来价格区间和目标区间有重叠，就认为命中
        if min_price <= high and max_price >= low:
            return rank

    return None


def save_outcome(
    snapshot_id: int,
    check_after_minutes: int,
    future_price: float,
    max_price: float,
    min_price: float,
    result_direction: str,
    hit_scenario_rank: int = None,
    note: str = "",
):
    """保存一次结果回填记录
    
    参数：
    - snapshot_id: 对应的快照 ID
    - check_after_minutes: 检查时间（60/240/1440 分钟后）
    - future_price: 未来价格（N 分钟后的收盘价）
    - max_price: N 分钟内最高价
    - min_price: N 分钟内最低价
    - result_direction: 实际方向（up/down/range）
    - hit_scenario_rank: 命中的 scenario rank
    - note: 备注信息
    """
    conn = get_db_conn()
    c = conn.cursor()
    # 使用 UTC 时间（与 Binance API 保持一致）
    from datetime import timezone
    now = datetime.now(timezone.utc).isoformat()

    c.execute("""
        INSERT INTO analysis_outcome
        (snapshot_id, check_after_minutes, future_price, max_price, min_price,
         result_direction, hit_scenario_rank, note, checked_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(snapshot_id),
        int(check_after_minutes),
        float(future_price),
        float(max_price),
        float(min_price),
        result_direction,
        hit_scenario_rank,
        note,
        now,
    ))

    conn.commit()
    conn.close()


# ============================================
# CLI 工具核心逻辑
# ============================================


def parse_args():
    """解析命令行参数"""
    
    parser = argparse.ArgumentParser(
        description="缠论 AI 分析工具 - 基于 Binance 行情和 DeepSeek AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python chanlun_ai.py BTCUSDT 1h              基础分析
  python chanlun_ai.py ETHUSDT 4h --save       保存完整报告
  python chanlun_ai.py BTCUSDT 1h --limit 500  使用500根K线
  python chanlun_ai.py BTCUSDT 1h --simple     快速分析
  python chanlun_ai.py BTCUSDT 1h --table      表格格式（输出Markdown）
  python chanlun_ai.py BTCUSDT 1h --structured 强制JSON输出
  python chanlun_ai.py BTCUSDT 1h --no-ai      仅显示结构（不调用AI）
        """
    )
    
    parser.add_argument(
        "symbol",
        type=str,
        help="交易对，如: BTCUSDT, ETHUSDT"
    )
    
    parser.add_argument(
        "interval",
        type=str,
        help="周期，如: 1m, 5m, 15m, 1h, 4h, 1d"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="K线数量 (默认: 500)"
    )
    
    parser.add_argument(
        "--save",
        action="store_true",
        help="保存完整分析报告到 output/ 目录"
    )
    
    parser.add_argument(
        "--simple",
        action="store_true",
        help="使用简化Prompt，输出更简洁"
    )
    
    parser.add_argument(
        "--structured",
        action="store_true",
        help="强制 AI 输出结构化 JSON（推荐）"
    )
    
    parser.add_argument(
        "--table",
        action="store_true",
        help="使用表格格式 Prompt，输出 Markdown 分析报告"
    )
    
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="仅显示缠论结构，不调用AI分析"
    )
    
    return parser.parse_args()


def load_api_key():
    """加载 API Key（优先从 .env，其次 config.yaml，最后环境变量）
    
    返回: (api_key, provider, model, temperature, max_tokens)
    """
    
    # 加载 .env 文件（优先级最高）
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    # 1. 从 .env 文件读取
    provider = os.getenv("AI_PROVIDER", "siliconflow")
    model = os.getenv("AI_MODEL", "Pro/deepseek-ai/DeepSeek-V3.2")
    temperature = float(os.getenv("AI_TEMPERATURE", "0.3"))
    max_tokens = int(os.getenv("AI_MAX_TOKENS", "4096"))
    
    # 根据 provider 读取对应的 API Key
    api_key = None
    if provider == "siliconflow":
        api_key = os.getenv("SILICONFLOW_API_KEY")
    elif provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
    elif provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
    
    # 2. 如果 .env 中没有，尝试从 config.yaml 读取
    if not api_key:
        config_file = Path(__file__).parent / "config.yaml"
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                api_key = config.get("ai", {}).get("api", {}).get("api_key")
                if api_key and api_key != "YOUR_API_KEY":
                    return api_key, provider, model, temperature, max_tokens
        except Exception:
            pass
    
    # 3. 最后尝试环境变量（兼容旧配置）
    if not api_key:
        api_key = os.environ.get("SILICONFLOW_API_KEY")
    
    return api_key, provider, model, temperature, max_tokens


def main():
    """主函数"""
    
    # 初始化数据库（首次运行时自动创建表）
    init_db()
    
    args = parse_args()
    
    # 标准化交易对格式
    symbol = args.symbol.upper().replace("/", "")
    display_symbol = f"{symbol[:3]}/{symbol[3:]}" if len(symbol) > 3 else symbol
    interval = args.interval.lower()
    
    print(f"\n🚀 开始分析 {display_symbol} @ {interval} ({args.limit} 根K线)")
    print("=" * 60)
    
    # ========================================
    # 1. 获取行情数据
    # ========================================
    print("\n📊 步骤 1/5: 获取 Binance K 线数据...")
    try:
        klines = get_klines(symbol, interval, limit=args.limit)
        print(f"   ✓ 获取到 {len(klines)} 根 K 线")
    except Exception as e:
        print(f"   ✗ 获取失败: {e}")
        sys.exit(1)
    
    # ========================================
    # 2. 缠论计算
    # ========================================
    print("\n🧮 步骤 2/5: 缠论结构计算...")
    try:
        bars = convert_to_chanlun_bars(klines)
        
        df = pd.DataFrame(bars)
        df = df.rename(columns={
            "date": "date",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "a": "volume",
        })
        
        # 转换周期格式（Binance → 缠论引擎）
        frequency_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "60m", "4h": "240m", "1d": "1440m"
        }
        frequency = frequency_map.get(interval, interval)
        
        icl = ICL(code=display_symbol, frequency=frequency, config=None)
        icl = icl.process_klines(df)
        
        print(f"   ✓ 缠论计算完成")
    except Exception as e:
        print(f"   ✗ 计算失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # ========================================
    # 3. 导出 AI JSON
    # ========================================
    print("\n📦 步骤 3/5: 构造 AI 输入数据...")
    try:
        exporter = ChanlunAIExporter()
        
        # 导出完整 JSON
        ai_json = exporter.export(
            icl=icl,
            symbol=display_symbol,
            interval=interval,
            klines=klines,
        )
        
        # 导出摘要
        latest_price = klines[-1]["close"]
        summary = exporter.export_summary(icl=icl, latest_price=latest_price)
        
        print(f"   ✓ 数据构造完成")
    except Exception as e:
        print(f"   ✗ 构造失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # ========================================
    # 4. 显示结构摘要
    # ========================================
    print("\n" + format_cli_output(
        symbol=display_symbol,
        interval=interval,
        summary=summary,
    ))
    
    # 如果用户指定 --no-ai，则到此结束
    if args.no_ai:
        print("✓ 结构分析完成（已跳过 AI 分析）\n")
        sys.exit(0)
    
    # ========================================
    # 5. AI 分析
    # ========================================
    print("\n🤖 步骤 4/5: 调用 AI 进行分析...")
    
    # 加载 API Key 和配置
    api_key, provider, model, temperature, max_tokens = load_api_key()
    if not api_key:
        print("✗ 未找到 API Key")
        print("\n请配置 API Key：")
        print("推荐方式 1: 在 .env 文件中设置（优先级最高）")
        print("  SILICONFLOW_API_KEY=your_key_here")
        print("\n方式 2: 在 config.yaml 中设置 ai.api.api_key")
        print("方式 3: 设置环境变量 SILICONFLOW_API_KEY")
        sys.exit(1)
        
    print(f"\n⚙️  配置信息：")
    print(f"   Provider: {provider}")
    print(f"   Model: {model}")
    print(f"   Temperature: {temperature}")
    print(f"   Max Tokens: {max_tokens}")
    
    try:
        # 构造 Prompt
        if args.structured and args.table:
            # 表格格式 + 结构化 JSON 输出
            prompt = build_structured_table_prompt(ai_json)
            print("   📊 使用表格格式 Prompt + 强制 JSON 输出...")
            use_structured = True
        elif args.structured:
            prompt = build_structured_prompt(ai_json)
            print("   🔒 使用结构化 Prompt（强制 JSON 输出）...")
            use_structured = True
        elif args.table:
            # 表格格式 + Markdown 输出
            prompt = build_table_format_prompt(ai_json)
            print("   📊 使用表格格式 Prompt（输出 Markdown）...")
            use_structured = False
        elif args.simple:
            prompt = build_simple_prompt(ai_json)
            print("   ⚡ 使用简化 Prompt...")
            use_structured = False
        else:
            prompt = build_prompt(ai_json)
            print("   📝 使用标准 Prompt...")
            use_structured = False
            
        # 调用 AI
        print("   ⏳ 等待 AI 响应（可能需要20-60 秒）...")
            
        analysis_result = call_ai(
            prompt=prompt,
            model=model,
            api_key=api_key,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )
            
        print("   ✓ AI 分析完成")
            
        # 如果使用结构化输出，需要验证和解析 JSON
        if use_structured:
            print("   🔍 验证 JSON 输出...")
            try:
                # 移除可能的 markdown 代码块标记
                clean_result = analysis_result.strip()
                if clean_result.startswith("```json"):
                    clean_result = clean_result[7:]
                if clean_result.startswith("```"):
                    clean_result = clean_result[3:]
                if clean_result.endswith("```"):
                    clean_result = clean_result[:-3]
                clean_result = clean_result.strip()
                    
                # 解析 JSON
                structured_output = json.loads(clean_result)
                    
                # 验证 Schema
                validated_output = validate_ai_output(structured_output)
                    
                print("   ✓ JSON 验证通过")
                
                # ⭐ 保存分析快照到数据库（AI 输出验证通过后）
                try:
                    snapshot_id = save_snapshot(
                        symbol=display_symbol,
                        interval=interval,
                        price=latest_price,
                        chanlun_json=ai_json,  # 完整的缠论结构 JSON
                        ai_json=validated_output,  # AI 输出的结构化 JSON
                    )
                    print(f"   💾 已保存分析快照（ID: {snapshot_id}）")
                except Exception as db_err:
                    print(f"   ⚠️  数据库保存失败: {db_err}")
                
                print("\n" + "=" * 60)
                print("【AI 结构化分析结果】")
                print("=" * 60)
                print(json.dumps(validated_output, ensure_ascii=False, indent=2))
                print("=" * 60)
                    
            except json.JSONDecodeError as e:
                print(f"   ✗ JSON 解析失败: {e}")
                print("\n原始输出：")
                print(analysis_result)
                analysis_result = None
            except ValueError as e:
                print(f"   ✗ JSON 验证失败: {e}")
                print("\n原始输出：")
                print(analysis_result)
                analysis_result = None
            
    except Exception as e:
        print(f"   ✗ AI 调用失败: {e}")
        analysis_result = None
        use_structured = False
    
    # ========================================
    # 6. 输出结果
    # ========================================
    if analysis_result:
        # 显示 AI 分析
        print(format_cli_output(
            symbol=display_symbol,
            interval=interval,
            summary=summary,
            analysis=analysis_result,
        ))
    
    # ========================================
    # 7. 保存报告（可选）
    # ========================================
    if args.save and analysis_result:
        print("\n💾 步骤 5/5: 保存分析报告...")
        
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"analysis_{symbol}_{interval}_{timestamp_str}.md"
        
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# {display_symbol} {interval} 缠论 AI 分析报告\n\n")
                f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**最新价格**: {latest_price:,.2f}\n\n")
                f.write(f"**数据周期**: {interval}\n\n")
                f.write(f"**K线数量**: {len(klines)} 根\n\n")
                f.write(f"**分析模型**: DeepSeek-V3.2 (硅基流动)\n\n")
                f.write("---\n\n")
                f.write(analysis_result)
            
            print(f"   ✓ 报告已保存: {output_file}")
        except Exception as e:
            print(f"   ✗ 保存失败: {e}")
    
    print("\n✅ 分析完成！\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 未预期的错误: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
