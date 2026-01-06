#!/usr/bin/env python3
"""数据库查询与统计工具

用途：
- 查看分析快照历史
- 查看结果回填记录
- 统计 AI 预测准确率

使用方法：
    python query_stats.py                    # 显示所有统计
    python query_stats.py --snapshots        # 只显示快照列表
    python query_stats.py --outcomes         # 只显示结果列表
    python query_stats.py --accuracy         # 只显示准确率统计
"""
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "chanlun_ai.db"


def get_db_conn():
    """获取数据库连接"""
    return sqlite3.connect(DB_PATH)


def query_snapshots(limit: int = 10):
    """查询最近的分析快照"""
    conn = get_db_conn()
    c = conn.cursor()
    
    c.execute("""
        SELECT id, symbol, interval, timestamp, price, 
               CASE WHEN ai_json IS NOT NULL THEN '是' ELSE '否' END as has_ai
        FROM analysis_snapshot
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    
    rows = c.fetchall()
    conn.close()
    
    return rows


def query_outcomes(limit: int = 10):
    """查询最近的结果回填记录"""
    conn = get_db_conn()
    c = conn.cursor()
    
    c.execute("""
        SELECT o.id, s.symbol, s.interval, o.check_after_minutes,
               s.price as start_price, o.future_price,
               o.result_direction, o.hit_scenario_rank,
               o.checked_at
        FROM analysis_outcome o
        JOIN analysis_snapshot s ON o.snapshot_id = s.id
        ORDER BY o.checked_at DESC
        LIMIT ?
    """, (limit,))
    
    rows = c.fetchall()
    conn.close()
    
    return rows


def calculate_accuracy():
    """计算 AI 预测准确率统计"""
    conn = get_db_conn()
    c = conn.cursor()
    
    # 总体准确率
    c.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN hit_scenario_rank IS NOT NULL THEN 1 ELSE 0 END) as hit_count
        FROM analysis_outcome
    """)
    total, hit_count = c.fetchone()
    
    # 按时间间隔统计
    c.execute("""
        SELECT 
            check_after_minutes,
            COUNT(*) as total,
            SUM(CASE WHEN hit_scenario_rank IS NOT NULL THEN 1 ELSE 0 END) as hit_count,
            ROUND(AVG(CASE WHEN hit_scenario_rank IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 2) as accuracy
        FROM analysis_outcome
        GROUP BY check_after_minutes
        ORDER BY check_after_minutes
    """)
    by_interval = c.fetchall()
    
    # 按命中的 rank 统计
    c.execute("""
        SELECT 
            hit_scenario_rank,
            COUNT(*) as count
        FROM analysis_outcome
        WHERE hit_scenario_rank IS NOT NULL
        GROUP BY hit_scenario_rank
        ORDER BY hit_scenario_rank
    """)
    by_rank = c.fetchall()
    
    # 按走势方向统计
    c.execute("""
        SELECT 
            result_direction,
            COUNT(*) as count,
            SUM(CASE WHEN hit_scenario_rank IS NOT NULL THEN 1 ELSE 0 END) as hit_count
        FROM analysis_outcome
        GROUP BY result_direction
    """)
    by_direction = c.fetchall()
    
    conn.close()
    
    return {
        "total": total or 0,
        "hit_count": hit_count or 0,
        "by_interval": by_interval,
        "by_rank": by_rank,
        "by_direction": by_direction,
    }


def print_snapshots(limit: int = 10):
    """打印快照列表"""
    print("\n📸 最近的分析快照")
    print("=" * 90)
    print(f"{'ID':<6} {'交易对':<12} {'周期':<8} {'时间':<20} {'价格':<12} {'AI输出'}")
    print("-" * 90)
    
    rows = query_snapshots(limit)
    if not rows:
        print("（暂无数据）")
    else:
        for row in rows:
            snapshot_id, symbol, interval, timestamp, price, has_ai = row
            print(f"{snapshot_id:<6} {symbol:<12} {interval:<8} {timestamp:<20} {price:<12.2f} {has_ai}")
    
    print()


def print_outcomes(limit: int = 10):
    """打印结果列表"""
    print("\n📊 最近的结果回填")
    print("=" * 110)
    print(f"{'ID':<6} {'交易对':<12} {'周期':<8} {'间隔':<8} {'起始价':<10} {'未来价':<10} {'方向':<8} {'命中':<8} {'检查时间'}")
    print("-" * 110)
    
    rows = query_outcomes(limit)
    if not rows:
        print("（暂无数据）")
    else:
        for row in rows:
            out_id, symbol, interval, check_min, start_price, future_price, direction, hit_rank, checked_at = row
            hit_str = f"Rank {hit_rank}" if hit_rank else "未命中"
            print(f"{out_id:<6} {symbol:<12} {interval:<8} {check_min:<8} {start_price:<10.2f} {future_price:<10.2f} {direction:<8} {hit_str:<8} {checked_at}")
    
    print()


def print_accuracy():
    """打印准确率统计"""
    stats = calculate_accuracy()
    
    print("\n📈 AI 预测准确率统计")
    print("=" * 60)
    
    # 总体统计
    total = stats["total"]
    hit_count = stats["hit_count"]
    accuracy = (hit_count / total * 100) if total > 0 else 0
    
    print(f"\n总评估次数: {total}")
    print(f"命中次数: {hit_count}")
    print(f"总体准确率: {accuracy:.2f}%")
    
    # 按时间间隔统计
    if stats["by_interval"]:
        print("\n按时间间隔统计:")
        print(f"{'间隔(分钟)':<15} {'评估次数':<12} {'命中次数':<12} {'准确率'}")
        print("-" * 60)
        for check_min, total, hit, acc in stats["by_interval"]:
            interval_name = f"{check_min} ({int(check_min/60)}h)"
            print(f"{interval_name:<15} {total:<12} {hit:<12} {acc:.2f}%")
    
    # 按命中 rank 统计
    if stats["by_rank"]:
        print("\n命中的 Scenario 分布:")
        print(f"{'Rank':<10} {'命中次数'}")
        print("-" * 30)
        for rank, count in stats["by_rank"]:
            print(f"Rank {rank:<5} {count}")
    
    # 按走势方向统计
    if stats["by_direction"]:
        print("\n按走势方向统计:")
        print(f"{'方向':<10} {'总次数':<12} {'命中次数':<12} {'准确率'}")
        print("-" * 60)
        for direction, total_dir, hit_dir in stats["by_direction"]:
            acc_dir = (hit_dir / total_dir * 100) if total_dir > 0 else 0
            print(f"{direction:<10} {total_dir:<12} {hit_dir:<12} {acc_dir:.2f}%")
    
    print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据库查询与统计工具")
    parser.add_argument("--snapshots", action="store_true", help="只显示快照列表")
    parser.add_argument("--outcomes", action="store_true", help="只显示结果列表")
    parser.add_argument("--accuracy", action="store_true", help="只显示准确率统计")
    parser.add_argument("--limit", type=int, default=10, help="查询记录数量（默认: 10）")
    
    args = parser.parse_args()
    
    # 如果没有指定任何选项，显示所有统计
    show_all = not (args.snapshots or args.outcomes or args.accuracy)
    
    if show_all or args.snapshots:
        print_snapshots(args.limit)
    
    if show_all or args.outcomes:
        print_outcomes(args.limit)
    
    if show_all or args.accuracy:
        print_accuracy()
    
    print("✅ 查询完成\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断\n")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}\n")
        import traceback
        traceback.print_exc()
