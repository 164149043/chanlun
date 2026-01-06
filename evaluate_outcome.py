#!/usr/bin/env python3
"""结果回填脚本 - 评估 AI 预测准确率

用途：
- 查找 N 分钟前生成的分析快照（尚未回填结果的）
- 从 Binance 拉取未来 N 分钟的 K 线数据
- 计算实际价格区间（最高/最低/收盘价）
- 判断是否命中 AI 预测的 scenario
- 将结果写入 analysis_outcome 表

使用方法：
    python evaluate_outcome.py           # 默认评估 60 分钟后的结果
    python evaluate_outcome.py 240       # 评估 4 小时后的结果
    python evaluate_outcome.py 1440      # 评估 1 天后的结果
"""
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from binance import get_klines

# 数据库路径
DB_PATH = Path(__file__).parent / "chanlun_ai.db"


def get_db_conn():
    """获取数据库连接"""
    return sqlite3.connect(DB_PATH)


def find_pending_snapshots(check_after_minutes: int):
    """查找待评估的分析快照
    
    参数：
    - check_after_minutes: 检查时间间隔（60/240/1440 分钟）
    
    返回：
    - List[tuple]: 待评估的快照记录
      每条记录包含：(id, symbol, interval, timestamp, price, ai_json)
    """
    conn = get_db_conn()
    c = conn.cursor()

    # 计算截止时间（当前时间 - N 分钟）
    cutoff = (datetime.now() - timedelta(minutes=check_after_minutes)).isoformat()

    # 查找符合条件的快照：
    # 1. 创建时间早于 N 分钟前
    # 2. 有 ai_json（即使用了结构化输出）
    # 3. 还没有对应 N 分钟的 outcome 记录
    c.execute("""
        SELECT s.id, s.symbol, s.interval, s.timestamp, s.price, s.ai_json
        FROM analysis_snapshot s
        WHERE s.timestamp <= ?
          AND s.ai_json IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM analysis_outcome o
              WHERE o.snapshot_id = s.id
                AND o.check_after_minutes = ?
          )
        ORDER BY s.timestamp ASC
    """, (cutoff, check_after_minutes))

    rows = c.fetchall()
    conn.close()
    return rows


def calculate_price_stats(klines):
    """计算 K 线数据的价格统计
    
    参数：
    - klines: Binance K 线数据列表
    
    返回：
    - dict: {
        "future_price": 最后一根收盘价,
        "max_price": 期间最高价,
        "min_price": 期间最低价
      }
    """
    if not klines:
        return None
    
    max_price = max(k["high"] for k in klines)
    min_price = min(k["low"] for k in klines)
    future_price = klines[-1]["close"]
    
    return {
        "future_price": future_price,
        "max_price": max_price,
        "min_price": min_price,
    }


def judge_direction(start_price: float, end_price: float, threshold: float = 0.01):
    """判断价格走势方向
    
    参数：
    - start_price: 起始价格
    - end_price: 结束价格
    - threshold: 震荡判断阈值（默认 1%）
    
    返回：
    - str: "up" / "down" / "range"
    """
    change_ratio = (end_price - start_price) / start_price
    
    if change_ratio > threshold:
        return "up"
    elif change_ratio < -threshold:
        return "down"
    else:
        return "range"


def judge_hit(ai_json_str: str, max_price: float, min_price: float):
    """判断未来价格是否命中 AI 预测的某个 scenario
    
    参数：
    - ai_json_str: AI 输出的 JSON 字符串
    - max_price: 未来时间段内的最高价
    - min_price: 未来时间段内的最低价
    
    返回：
    - int or None: 命中的 scenario rank，无命中返回 None
    """
    try:
        ai_json = json.loads(ai_json_str)
    except (json.JSONDecodeError, TypeError):
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
    """保存结果回填记录到数据库"""
    conn = get_db_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()

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


def evaluate_outcomes(check_after_minutes: int):
    """评估待回填的分析快照
    
    参数：
    - check_after_minutes: 检查时间间隔（60/240/1440 分钟）
    """
    print(f"🔍 查找 {check_after_minutes} 分钟前的待评估快照...")
    
    snapshots = find_pending_snapshots(check_after_minutes)
    
    if not snapshots:
        print("✅ 没有待评估的快照")
        return
    
    print(f"📊 找到 {len(snapshots)} 条待评估记录\n")
    
    success_count = 0
    failed_count = 0
    
    for snapshot in snapshots:
        snapshot_id, symbol, interval, timestamp, price, ai_json_str = snapshot
        
        print(f"评估快照 #{snapshot_id}: {symbol} @ {interval}")
        print(f"  分析时间: {timestamp}")
        print(f"  当时价格: {price:.2f}")
        
        # 解析时间戳（确保带时区信息）
        try:
            analysis_time = datetime.fromisoformat(timestamp)
            # 如果没有时区信息，添加 UTC 时区
            if analysis_time.tzinfo is None:
                from datetime import timezone
                analysis_time = analysis_time.replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"  ✗ 时间戳格式错误，跳过")
            failed_count += 1
            continue
        
        # 计算未来时间范围
        future_time = analysis_time + timedelta(minutes=check_after_minutes)
        
        # 标准化交易对格式（BTC/USDT → BTCUSDT）
        binance_symbol = symbol.replace("/", "")
        
        # 从 Binance 拉取未来 K 线数据
        try:
            # 拉取足够的数据（预留余量）
            # 例如：60 分钟 + 1h 周期，至少需要 2 根 K 线
            limit = max(10, int(check_after_minutes / 60) + 5)
            
            klines = get_klines(binance_symbol, interval, limit=limit)
            
            # 调试：打印时间信息
            if klines:
                print(f"  调试：分析时间 = {analysis_time}")
                print(f"  调试：最新 K 线时间 = {klines[-1]['open_time']}")
                print(f"  调试：拉取了 {len(klines)} 根 K 线")
            
            # 筛选出分析时间之后的 K 线
            future_klines = [
                k for k in klines
                if k["open_time"] >= analysis_time
            ]
            
            if not future_klines:
                print(f"  ⚠️  未找到未来 K 线数据")
                print(f"  原因：所有 K 线的时间都早于分析时间")
                continue
            
        except Exception as e:
            print(f"  ✗ 拉取 K 线失败: {e}")
            failed_count += 1
            continue
        
        # 计算价格统计
        stats = calculate_price_stats(future_klines)
        if not stats:
            print(f"  ✗ 价格统计计算失败")
            failed_count += 1
            continue
        
        future_price = stats["future_price"]
        max_price = stats["max_price"]
        min_price = stats["min_price"]
        
        # 判断走势方向
        result_direction = judge_direction(price, future_price)
        
        # 判断是否命中 AI 预测
        hit_rank = judge_hit(ai_json_str, max_price, min_price)
        
        print(f"  未来价格: {future_price:.2f}")
        print(f"  价格区间: [{min_price:.2f}, {max_price:.2f}]")
        print(f"  走势方向: {result_direction}")
        print(f"  命中 Scenario: {hit_rank if hit_rank else '未命中'}")
        
        # 保存结果
        try:
            save_outcome(
                snapshot_id=snapshot_id,
                check_after_minutes=check_after_minutes,
                future_price=future_price,
                max_price=max_price,
                min_price=min_price,
                result_direction=result_direction,
                hit_scenario_rank=hit_rank,
                note=f"基于 {len(future_klines)} 根 K 线评估",
            )
            print(f"  ✓ 结果已保存\n")
            success_count += 1
        except Exception as e:
            print(f"  ✗ 保存失败: {e}\n")
            failed_count += 1
    
    print("=" * 60)
    print(f"✅ 评估完成: 成功 {success_count} 条，失败 {failed_count} 条")


def main():
    """主函数"""
    
    # 从命令行参数读取检查时间间隔，默认 60 分钟
    if len(sys.argv) > 1:
        try:
            check_after_minutes = int(sys.argv[1])
        except ValueError:
            print("❌ 参数错误：请提供数字（60/240/1440）")
            print("\n使用方法:")
            print("  python evaluate_outcome.py 60     # 1 小时后")
            print("  python evaluate_outcome.py 240    # 4 小时后")
            print("  python evaluate_outcome.py 1440   # 1 天后")
            sys.exit(1)
    else:
        check_after_minutes = 60  # 默认 1 小时
    
    print("=" * 60)
    print(f"📈 缠论 AI 预测结果回填工具")
    print(f"⏰ 评估时间间隔: {check_after_minutes} 分钟 ({check_after_minutes/60:.1f} 小时)")
    print("=" * 60)
    print()
    
    try:
        evaluate_outcomes(check_after_minutes)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
