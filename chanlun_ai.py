#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""缠论 AI 分析命令行工具

用法:
    python chanlun_ai.py BTCUSDT 1h              # 基础分析
    python chanlun_ai.py ETHUSDT 4h --save       # 分析并保存报告
    python chanlun_ai.py BTCUSDT 1h --limit 500  # 指定K线数量
    python chanlun_ai.py BTCUSDT 1h --simple     # 快速分析（简化Prompt）
    python chanlun_ai.py BTCUSDT 1h --table      # 表格格式输入（输出Markdown）
    python chanlun_ai.py BTCUSDT 1h --structured # 强制JSON输出
    python chanlun_ai.py BTCUSDT 1h --stats      # 分析后显示统计信息

示例:
    python chanlun_ai.py BTCUSDT 1h
    python chanlun_ai.py ETHUSDT 4h --save
    python chanlun_ai.py BTCUSDT 1h --table
    python chanlun_ai.py BTCUSDT 1h --stats      # 分析并显示准确率统计
"""
import os
import sys

# Windows 终端编码修复
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass  # Python < 3.7

import argparse
import json
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

# 导入数据库管理器（修复连接泄漏问题）
try:
    from db_manager import get_db_conn, get_db_path, safe_json_loads, safe_json_dumps
    DB_MANAGER_AVAILABLE = True
except ImportError:
    DB_MANAGER_AVAILABLE = False

# 导入统计模块
try:
    from query_stats import calculate_accuracy, print_accuracy
    from stats_formatter import format_stats_for_prompt, get_stats_summary
    from prediction_validator import validate_prediction, get_adjustment_summary, should_skip_prediction
    STATS_AVAILABLE = True
except ImportError:
    STATS_AVAILABLE = False

# 导入历史上下文模块（P0新增）
try:
    from history_context import get_history_context
    HISTORY_CONTEXT_AVAILABLE = True
except ImportError:
    HISTORY_CONTEXT_AVAILABLE = False

# 导入逻辑验证模块（P2新增）
try:
    from logic_validator import validate_ai_output as validate_logic, format_validation_report
    LOGIC_VALIDATOR_AVAILABLE = True
except ImportError:
    LOGIC_VALIDATOR_AVAILABLE = False

# 导入学习反馈模块（Step1新增）
try:
    from learning_feedback import get_learning_feedback, LearningReport
    LEARNING_FEEDBACK_AVAILABLE = True
except ImportError:
    LEARNING_FEEDBACK_AVAILABLE = False

# 导入置信度约束模块（Step3新增）
try:
    from confidence_constraint import apply_confidence_constraints, format_constraint_result
    CONFIDENCE_CONSTRAINT_AVAILABLE = True
except ImportError:
    CONFIDENCE_CONSTRAINT_AVAILABLE = False


# ============================================
# 数据库功能（SQLite）
# ============================================

# 获取数据库路径
if DB_MANAGER_AVAILABLE:
    DB_PATH = get_db_path()
else:
    DB_PATH = Path(__file__).parent / "chanlun_ai.db"


def get_db_conn():
    """获取数据库连接（兼容性包装）"""
    if DB_MANAGER_AVAILABLE:
        from db_manager import get_db_conn_no_context
        return get_db_conn_no_context()
    return sqlite3.connect(DB_PATH)


def init_db():
    """初始化数据库表结构（首次运行时自动创建）"""
    if DB_MANAGER_AVAILABLE:
        from db_manager import init_db as db_init
        db_init()
        return

    # 兼容性代码（当db_manager不可用时）
    conn = get_db_conn()
    try:
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
            created_at TEXT NOT NULL,
            evaluated INTEGER DEFAULT 0,
            outcome_json TEXT
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
    finally:
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
    - snapshot_id: 插入的记录 ID，失败时返回 None
    """
    conn = None
    try:
        conn = get_db_conn()
        c = conn.cursor()
        # 使用 UTC 时间（与 Binance API 保持一致）
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat()

        # 安全的JSON序列化
        chanlun_json_str = safe_json_dumps(chanlun_json) if DB_MANAGER_AVAILABLE else json.dumps(chanlun_json, ensure_ascii=False)
        ai_json_str = safe_json_dumps(ai_json) if (ai_json and DB_MANAGER_AVAILABLE) else (json.dumps(ai_json, ensure_ascii=False) if ai_json else None)

        c.execute("""
            INSERT INTO analysis_snapshot
            (symbol, interval, timestamp, price, chanlun_json, ai_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol,
            interval,
            now,
            float(price),
            chanlun_json_str,
            ai_json_str,
            now,
        ))

        snapshot_id = c.lastrowid
        conn.commit()
        return snapshot_id

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return None
    except Exception as e:
        print(f"保存快照失败: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


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
    conn = None
    try:
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
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    except Exception as e:
        print(f"保存结果失败: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


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
    
    parser.add_argument(
        "--stats",
        action="store_true",
        help="分析完成后显示统计信息"
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
    
    # ========================================
    # 4.5. 获取历史统计数据（新增）
    # ========================================
    # 在外层定义变量，确保作用域可见
    stats_context = ""
    stats_summary = None
    use_structured = args.structured  # 提前定义 use_structured
    
    if STATS_AVAILABLE:
        try:
            print("\n" + "=" * 60)
            print("📈 步骤 4.5/6: 获取历史统计数据...")
            print("=" * 60)
            
            stats = calculate_accuracy()
            if stats and stats.get("total", 0) > 0:
                stats_context = format_stats_for_prompt(stats, display_symbol, interval)
                stats_summary = get_stats_summary(stats)
                print(f"   ✓ 已加载 {stats['total']} 条历史记录")
                print(f"   ✓ 整体命中率: {stats_summary['accuracy']:.1f}%")
                print(f"   ✓ 平均得分: {stats_summary['avg_score']:.2f} / 1.0")
            else:
                print("   ⚠️  暂无历史数据")
        except Exception as e:
            print(f"   ⚠️  统计数据加载失败: {e}")
    
    # ========================================
    # 4.6. 获取历史上下文（所有模式通用）
    # ========================================
    history_context_text = ""
    learning_feedback_text = ""
    learning_report = None
    
    # 只在非 simple 模式下获取历史上下文（simple 模式追求速度）
    if not args.simple:
        # P0：获取相似案例历史上下文
        if HISTORY_CONTEXT_AVAILABLE:
            try:
                history_context_text, history_stats = get_history_context(
                    symbol=display_symbol,
                    interval=interval,
                    chanlun_json=ai_json,
                )
                if history_stats.get("has_data"):
                    print(f"   🔍 找到 {history_stats['total']} 条相似案例")
                    print(f"   📈 相似案例胜率: {history_stats['win_rate']*100:.1f}%")
                    print(f"   💡 建议: {history_stats['suggestion']}")
            except Exception as hc_err:
                print(f"   ⚠️  历史上下文加载失败: {hc_err}")
        
        # Step1：获取AI学习反馈（自我认知）
        if LEARNING_FEEDBACK_AVAILABLE:
            try:
                learning_feedback_text, learning_report = get_learning_feedback(
                    days=30,
                    symbol=display_symbol,
                    interval=interval,
                )
                if learning_report and learning_report.total_predictions > 0:
                    print(f"   🧠 AI自我认知: 历史胜率{learning_report.overall_win_rate*100:.1f}%")
                    if learning_report.error_patterns:
                        print(f"   ⚠️  发现 {len(learning_report.error_patterns)} 个错误模式")
            except Exception as lf_err:
                print(f"   ⚠️  学习反馈加载失败: {lf_err}")
    
    try:
        # 构造 Prompt
        if args.structured and args.table:
            # 表格格式 + 结构化 JSON 输出
            prompt = build_structured_table_prompt(ai_json)
            print("   📊 使用表格格式 Prompt + 强制 JSON 输出...")
            use_structured = True
        elif args.structured:
            # 使用已获取的历史上下文构造结构化 Prompt
            prompt = build_structured_prompt(
                ai_json,
                stats_context=stats_context,
                history_context=history_context_text,
                learning_feedback=learning_feedback_text,
            )
            print("   🔒 使用结构化 Prompt（强制 JSON 输出")
            if stats_context:
                print("   📊 已注入历史统计数据")
            if history_context_text:
                print("   📚 已注入相似案例分析")
            if learning_feedback_text:
                print("   🧠 已注入AI自我认知")
            print("   ...")
            use_structured = True
        elif args.table:
            # 表格格式 + Markdown 输出（注入历史上下文）
            prompt = build_table_format_prompt(
                ai_json,
                stats_context=stats_context,
                history_context=history_context_text,
                learning_feedback=learning_feedback_text,
            )
            print("   📊 使用表格格式 Prompt（输出 Markdown）...")
            if history_context_text:
                print("   📚 已注入相似案例分析")
            if learning_feedback_text:
                print("   🧠 已注入AI自我认知")
            use_structured = False
        elif args.simple:
            prompt = build_simple_prompt(ai_json)
            print("   ⚡ 使用简化 Prompt（跳过历史上下文以提高速度）...")
            use_structured = False
        else:
            # 标准模式（注入历史上下文）
            prompt = build_prompt(
                ai_json,
                stats_context=stats_context,
                history_context=history_context_text,
                learning_feedback=learning_feedback_text,
            )
            print("   📝 使用标准 Prompt...")
            if history_context_text:
                print("   📚 已注入相似案例分析")
            if learning_feedback_text:
                print("   🧠 已注入AI自我认知")
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

                # 解析 JSON（添加异常处理）
                try:
                    structured_output = json.loads(clean_result)
                except json.JSONDecodeError as e:
                    print(f"   ✗ JSON 解析失败: {e}")
                    print(f"   原始内容: {clean_result[:200]}...")
                    structured_output = None
                    
                # 验证 Schema
                validated_output = validate_ai_output(structured_output)
                    
                print("   ✓ JSON 验证通过")
                
                # ========================================
                # 4.6. 系统校验与调整（新增）
                # ========================================
                print(f"   🔍 校验条件: STATS_AVAILABLE={STATS_AVAILABLE}, stats_summary={'Yes' if stats_summary else 'None'}")
                
                if STATS_AVAILABLE and stats_summary:
                    print("   🔍 执行预测校验...")
                    try:
                        validated_output, warnings = validate_prediction(
                            validated_output,
                            stats_summary,
                            display_symbol,
                            interval
                        )
                        
                        if warnings:
                            print("\n" + get_adjustment_summary(warnings))
                        else:
                            print("   ✓ 预测参数合理，无需调整")
                    except Exception as val_err:
                        print(f"   ⚠️  校验失败: {val_err}")
                        import traceback
                        traceback.print_exc()
                else:
                    if not STATS_AVAILABLE:
                        print("   ⚠️  统计模块不可用，跳过校验")
                    elif not stats_summary:
                        print("   ⚠️  统计数据为空，跳过校验")
                
                # ⭐ P2：AI分析逻辑验证
                if LOGIC_VALIDATOR_AVAILABLE:
                    try:
                        logic_result = validate_logic(
                            validated_output,
                            chanlun_json=ai_json,
                            current_price=latest_price,
                            auto_fix=True,
                        )

                        if logic_result.has_critical_errors:
                            print(f"   ⚠️  发现 {len(logic_result.errors)} 个严重逻辑错误")
                            for err in logic_result.errors:
                                print(f"      [{err.code}] {err.message}")
                            # 使用修复后的输出
                            if logic_result.fixed_output:
                                validated_output = logic_result.fixed_output
                                print("   🔧 已应用自动修复")
                        elif logic_result.warnings:
                            print(f"   ⚠️  发现 {len(logic_result.warnings)} 个逻辑警告")
                        else:
                            print("   ✓ 逻辑验证通过")

                        # 显示入场区间优化信息
                        from logic_validator import format_entry_range_fixes
                        entry_fix_msg = format_entry_range_fixes(logic_result, latest_price)
                        if entry_fix_msg:
                            print(entry_fix_msg)

                        # 将逻辑验证结果添加到输出
                        validated_output["logic_validation"] = {
                            "is_valid": logic_result.is_valid,
                            "errors": len(logic_result.errors),
                            "warnings": len(logic_result.warnings),
                        }
                    except Exception as lv_err:
                        print(f"   ⚠️  逻辑验证失败: {lv_err}")
                
                # ⭐ Step3：置信度约束（基于学习反馈自动调整参数）
                if CONFIDENCE_CONSTRAINT_AVAILABLE and learning_report:
                    try:
                        # 提取当前信号类型
                        current_signal = None
                        signal_data = ai_json.get("signal", {})
                        buy_sell_points = signal_data.get("buy_sell_points", [])
                        if buy_sell_points:
                            for s in buy_sell_points:
                                sl = s.lower()
                                if "1buy" in sl: current_signal = "1buy"; break
                                elif "2buy" in sl: current_signal = "2buy"; break
                                elif "1sell" in sl: current_signal = "1sell"; break
                                elif "2sell" in sl: current_signal = "2sell"; break
                        
                        validated_output, constraint_result = apply_confidence_constraints(
                            validated_output,
                            learning_report=learning_report,
                            current_signal=current_signal,
                        )
                        
                        if constraint_result.adjusted:
                            print(f"   🎯 置信度约束已应用 (风险等级: {constraint_result.risk_level.upper()})")
                            for adj in constraint_result.adjustments[:2]:  # 显示前2条调整
                                print(f"      - {adj}")
                        else:
                            print("   ✓ 参数已在合理范围")
                        
                        # 添加约束结果到输出
                        validated_output["confidence_constraint"] = {
                            "adjusted": constraint_result.adjusted,
                            "risk_level": constraint_result.risk_level,
                            "probability_change": f"{constraint_result.original_probability:.0%} → {constraint_result.new_probability:.0%}",
                        }
                    except Exception as cc_err:
                        print(f"   ⚠️  置信度约束失败: {cc_err}")
                
                # ⭐ 计算信号质量评分（保存到数据库前）
                try:
                    from signal_quality import calculate_signal_quality
                    quality = calculate_signal_quality(ai_json, validated_output)
                    # 将质量评分添加到 validated_output 中（用于数据库存储）
                    validated_output["signal_quality"] = {
                        "total_score": quality["total_score"],
                        "grade": quality["grade"],
                        "action": quality["action"],
                    }
                except Exception as qe:
                    print(f"   ⚠️  信号质量评分计算失败: {qe}")

                # ⭐ v2.0 新增：状态机转换（自动生成状态机格式）
                try:
                    from state_machine_converter import scenarios_to_state_machine, format_state_machine_for_display

                    # 获取历史胜率（用于确定风险等级）
                    hist_winrate = stats_summary.get("accuracy", 0) if stats_summary else None

                    # 转换为状态机格式
                    state_machine = scenarios_to_state_machine(
                        validated_output,
                        latest_price,
                        historical_winrate=hist_winrate
                    )
                    validated_output["state_machine"] = state_machine
                    validated_output["output_mode"] = "state_machine"
                    validated_output["version"] = "2.0"

                    print(f"   🔄 已生成状态机格式: {state_machine.get('current_state', 'UNKNOWN')}")
                except Exception as sm_err:
                    print(f"   ⚠️  状态机转换失败: {sm_err}")

                # ⭐ v2.1 新增：规则引擎（结构优先原则）
                try:
                    from rule_engine import apply_rule_engine

                    # 应用规则引擎约束 AI 概率分配
                    success, rule_result = apply_rule_engine(
                        ai_json=ai_json,
                        ai_output=validated_output,
                        latest_price=latest_price,
                        enable_ai_adjustment=True  # 允许 AI 在 ±10% 范围内微调
                    )

                    if success and rule_result:
                        # 更新 scenarios 中的概率
                        scenarios = validated_output.get("scenarios", [])
                        if scenarios:
                            # 按方向更新概率
                            for scenario in scenarios:
                                direction = scenario.get("direction", "")
                                if direction == "up":
                                    scenario["probability"] = rule_result.ai_adjusted_probabilities["up"]
                                elif direction == "down":
                                    scenario["probability"] = rule_result.ai_adjusted_probabilities["down"]
                                elif direction == "range":
                                    scenario["probability"] = rule_result.ai_adjusted_probabilities["range"]

                            # 更新 primary_scenario 方向和概率
                            primary = validated_output.get("primary_scenario", {})
                            primary["direction"] = rule_result.primary_direction
                            primary["probability"] = max(rule_result.ai_adjusted_probabilities.values())

                        # 保存规则引擎结果
                        validated_output["rule_engine_result"] = {
                            "base_probabilities": rule_result.base_probabilities,
                            "ai_adjusted_probabilities": rule_result.ai_adjusted_probabilities,
                            "primary_direction": rule_result.primary_direction,
                            "confidence_level": rule_result.confidence_level,
                            "applied_rules": rule_result.applied_rules,
                            "warnings": rule_result.warnings
                        }

                        # 输出规则引擎处理信息
                        print(f"   📐 规则引擎已应用 {len(rule_result.applied_rules)} 条规则")
                        print(f"      基准概率: up={rule_result.base_probabilities['up']:.0%} "
                              f"down={rule_result.base_probabilities['down']:.0%} "
                              f"range={rule_result.base_probabilities['range']:.0%}")
                        print(f"      调整后概率: up={rule_result.ai_adjusted_probabilities['up']:.0%} "
                              f"down={rule_result.ai_adjusted_probabilities['down']:.0%} "
                              f"range={rule_result.ai_adjusted_probabilities['range']:.0%}")
                        print(f"      主推方向: {rule_result.primary_direction}")
                        print(f"      置信度: {rule_result.confidence_level}")
                        if rule_result.warnings:
                            for w in rule_result.warnings:
                                print(f"      ⚠️  {w}")

                except ImportError:
                    # 规则引擎模块不可用，跳过
                    pass
                except Exception as re_err:
                    print(f"   ⚠️  规则引擎处理失败: {re_err}")

                # ⭐ 保存分析快照到数据库（AI 输出验证通过后）
                try:
                    snapshot_id = save_snapshot(
                        symbol=display_symbol,
                        interval=interval,
                        price=latest_price,
                        chanlun_json=ai_json,  # 完整的缠论结构 JSON
                        ai_json=validated_output,  # AI 输出的结构化 JSON（含信号质量）
                    )
                    print(f"   💾 已保存分析快照（ID: {snapshot_id}）")
                except Exception as db_err:
                    print(f"   ⚠️  数据库保存失败: {db_err}")
                
                print("\n" + "=" * 60)
                print("【AI 结构化分析结果】")
                print("=" * 60)

                # 获取数据
                meta = validated_output.get("meta", {})
                current_price = float(meta.get("price", latest_price))
                primary = validated_output.get("primary_scenario", {})
                scenarios = validated_output.get("scenarios", [])

                # 结构判断（从 structure_judgment 提取）
                structure = validated_output.get("structure_judgement", {})
                trend_desc = structure.get("trend", "未知")
                price_pos = structure.get("price_position", "未知")

                # 显示结构判断
                print(f"\n📊 结构判断：{trend_desc}，价格位置：{price_pos}")

                # 显示策略详情（分行显示，更清晰）
                print("\n【策略分析】")

                up_scenarios = [s for s in scenarios if s.get("direction") == "up"]
                down_scenarios = [s for s in scenarios if s.get("direction") == "down"]
                range_scenarios = [s for s in scenarios if s.get("direction") == "range"]

                up_prob = sum(s.get("probability", 0) for s in up_scenarios)
                down_prob = sum(s.get("probability", 0) for s in down_scenarios)
                range_prob = sum(s.get("probability", 0) for s in range_scenarios)

                # 做多策略
                if up_prob > 0:
                    if up_scenarios:
                        s = up_scenarios[0]
                        tr = s.get("target_range")
                        er = s.get("entry_range")  # 入场点位区间
                        if tr and len(tr) == 2:
                            # target_range 只是目标区间，止损需要另外计算
                            # 做多：目标是上界，止损是下界
                            tgt_low, tgt_high = tr[0], tr[1]  # 0=下界, 1=上界
                            # 止损在下界或当前价下方2%
                            stp = min(tr[0], current_price * 0.98)  # 取下界或当前价*0.98
                            # 入场点位区间
                            if er and len(er) == 2:
                                entry_low, entry_high = er[0], er[1]
                                print(f"  📈 做多({up_prob*100:.0f}%): 入场{entry_low:,.0f}-{entry_high:,.0f} 目标{tgt_high:,.0f} 止损{stp:,.0f}")
                            else:
                                # 没有入场区间时，默认在当前价格附近
                                print(f"  📈 做多({up_prob*100:.0f}%): 入场{current_price:,.0f}附近 目标{tgt_high:,.0f} 止损{stp:,.0f}")
                        else:
                            tgt_pct = s.get("target_pct", 2)
                            stp_pct = s.get("stop_pct", 1)
                            tgt = current_price * (1 + tgt_pct / 100)
                            stp = current_price * (1 - stp_pct / 100)
                            trigger = s.get("trigger", "")[:30]
                            print(f"  📈 做多({up_prob*100:.0f}%): 入场{current_price:,.0f}附近 目标{tgt:,.0f}({tgt_pct:.1f}%) 止损{stp:,.0f}")

                # 做空策略
                if down_prob > 0:
                    if down_scenarios:
                        s = down_scenarios[0]
                        tr = s.get("target_range")
                        er = s.get("entry_range")  # 入场点位区间
                        if tr and len(tr) == 2:
                            # 做空：目标是下界，止损是上界
                            tgt_low, tgt_high = tr[0], tr[1]  # 0=下界, 1=上界
                            # 止损在上界或当前价上方2%
                            stp = max(tr[0], current_price * 1.02)  # 取上界或当前价*1.02
                            # 入场点位区间
                            if er and len(er) == 2:
                                entry_low, entry_high = er[0], er[1]
                                print(f"  📉 做空({down_prob*100:.0f}%): 入场{entry_low:,.0f}-{entry_high:,.0f} 目标{tgt_low:,.0f} 止损{stp:,.0f}")
                            else:
                                # 没有入场区间时，默认在当前价格附近
                                print(f"  📉 做空({down_prob*100:.0f}%): 入场{current_price:,.0f}附近 目标{tgt_low:,.0f} 止损{stp:,.0f}")
                        else:
                            tgt_pct = s.get("target_pct", 2)
                            stp_pct = s.get("stop_pct", 1)
                            tgt = current_price * (1 - tgt_pct / 100)
                            stp = current_price * (1 + stp_pct / 100)
                            trigger = s.get("trigger", "")[:30]
                            print(f"  📉 做空({down_prob*100:.0f}%): 入场{current_price:,.0f}附近 目标{tgt:,.0f}({tgt_pct:.1f}%) 止损{stp:,.0f}")

                # 震荡策略
                if range_prob > 0:
                    if range_scenarios:
                        s = range_scenarios[0]
                        tr = s.get("target_range")
                        er = s.get("entry_range")  # 入场点位区间
                        if tr and len(tr) == 2:
                            # 震荡策略的 target_range 就是震荡区间
                            # entry_range 是建议的入场区间
                            if er and len(er) == 2:
                                print(f"  ↔️ 震荡({range_prob*100:.0f}%): 入场{er[0]:,.0f}-{er[1]:,.0f} 区间{tr[0]:,.0f}-{tr[1]:,.0f} 高抛低吸")
                            else:
                                print(f"  ↔️ 震荡({range_prob*100:.0f}%): 区间{tr[0]:,.0f} - {tr[1]:,.0f} 高抛低吸")
                        else:
                            tgt = s.get("target_pct", 2)
                            low = current_price * (1 - tgt / 100)
                            high = current_price * (1 + tgt / 100)
                            print(f"  ↔️ 震荡({range_prob*100:.0f}%): 区间{low:,.0f} - {high:,.0f}")

                # 关键价位
                zs = structure.get("zs", {})
                if zs:
                    print(f"\n📍 关键位: ZG={zs.get('zg',0):.0f} ZD={zs.get('zd',0):.0f} GG={zs.get('gg',0):.0f} DD={zs.get('dd',0):.0f}")

                # 主要预测（精简一行）
                direction = primary.get("direction", "up")
                direction_emoji = "📈" if direction == "up" else "📉"
                target_pct = primary.get("target_pct", 0)
                stop_pct = primary.get("stop_pct", 0)
                probability = primary.get("probability", 0)

                if direction == "up":
                    target_price = current_price * (1 + target_pct / 100)
                    stop_price = current_price * (1 - stop_pct / 100)
                else:
                    target_price = current_price * (1 - target_pct / 100)
                    stop_price = current_price * (1 + stop_pct / 100)

                print(f"🎯 主推：{direction_emoji} 目标{target_price:,.0f} 止损{stop_price:,.0f} 概率{probability*100:.0f}%")

                # 2.5 v2.0 新增：状态机显示
                if "state_machine" in validated_output:
                    try:
                        from state_machine_converter import format_state_machine_for_display
                        state_machine = validated_output["state_machine"]
                        print(format_state_machine_for_display(state_machine))
                    except Exception as sm_display_err:
                        print(f"   ⚠️  状态机显示失败: {sm_display_err}")

                # 2.5 信号质量评分（显示报告）
                if "signal_quality" in validated_output:
                    try:
                        from signal_quality import calculate_signal_quality, format_quality_report
                        # 重新计算完整质量数据以获取详细报告
                        quality = calculate_signal_quality(ai_json, validated_output)
                        quality_report = format_quality_report(quality)
                        print(quality_report)
                    except Exception as qe:
                        # 如果详细报告失败，仍然显示简化版
                        sq = validated_output["signal_quality"]
                        print(f"\n  信号质量评分: {sq['total_score']:.1f}/100 (评级: {sq['grade']})")

                # 3. 显示完整 JSON 已移除（避免与 format_cli_output 重复输出）
                # 如需查看完整JSON，可查看数据库或添加 --verbose 参数
                    
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
            
            print(f"   \u2713 报告已保存: {output_file}")
        except Exception as e:
            print(f"   \u2717 保存失败: {e}")
        
    # ========================================
    # 8. 显示统计信息（可选）
    # ========================================
    if args.stats:
        if not STATS_AVAILABLE:
            print("\n\u26a0\ufe0f  统计模块不可用，请确保 query_stats.py 存在")
        else:
            print("\n" + "=" * 60)
            print("📊 步骤 6/6: 显示统计信息...")
            print("=" * 60)
            try:
                print_accuracy()
                print("📊 如需查看详细统计，请运行：")
                print("   python query_stats.py")
                print("   python query_stats.py --export-csv results.csv")
            except Exception as e:
                print(f"   \u2717 统计显示失败: {e}")
        
    print("\n\u2705 分析完成！\n")


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
