#!/usr/bin/env python3
"""数据库查询与统计工具

用途：
- 查看分析快照历史
- 查看结果回填记录
- 统计 AI 预测准确率
- 导出 CSV 文件

使用方法：
    python query_stats.py                    # 显示所有统计
    python query_stats.py --snapshots        # 只显示快照列表
    python query_stats.py --outcomes         # 只显示结果列表
    python query_stats.py --accuracy         # 只显示准确率统计
    python query_stats.py --export-csv results.csv  # 导出结果到 CSV
"""
import sqlite3
import argparse
import csv
import json
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
    """查询最近的结果回填记录（基于 analysis_snapshot.outcome_json）"""
    conn = get_db_conn()
    c = conn.cursor()
    
    c.execute(
        """
        SELECT id, symbol, interval, timestamp, price, outcome_json
        FROM analysis_snapshot
        WHERE evaluated = 1 AND outcome_json IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )
    
    rows = c.fetchall()
    conn.close()
    
    return rows

def calculate_accuracy():
    """计算 AI 预测准确率统计（基于 analysis_snapshot.outcome_json）"""
    conn = get_db_conn()
    c = conn.cursor()
    
    c.execute(
        """
        SELECT outcome_json, symbol, interval
        FROM analysis_snapshot
        WHERE evaluated = 1 AND outcome_json IS NOT NULL
        """
    )
    rows = c.fetchall()
    conn.close()
    
    import json
    
    total = 0
    hit_count = 0
    by_direction_map = {}
    by_symbol_map = {}
    by_interval_map = {}
    by_outcome_map = {}
    total_score = 0
    
    for (outcome_json_str, symbol, interval) in rows:
        try:
            outcome = json.loads(outcome_json_str)
        except Exception:
            continue
        
        total += 1
        direction = outcome.get("direction", "unknown")
        hit_target = outcome.get("hit_target", False)
        outcome_type = outcome.get("outcome", "unknown")
        score = outcome.get("score", 0)
        
        total_score += score
        
        if hit_target:
            hit_count += 1
        
        # 按方向统计
        stats = by_direction_map.setdefault(direction, {"total": 0, "hit": 0, "score": 0})
        stats["total"] += 1
        stats["score"] += score
        if hit_target:
            stats["hit"] += 1
        
        # 按交易对统计
        stats = by_symbol_map.setdefault(symbol, {"total": 0, "hit": 0, "score": 0})
        stats["total"] += 1
        stats["score"] += score
        if hit_target:
            stats["hit"] += 1
        
        # 按周期统计
        stats = by_interval_map.setdefault(interval, {"total": 0, "hit": 0, "score": 0})
        stats["total"] += 1
        stats["score"] += score
        if hit_target:
            stats["hit"] += 1
        
        # 按结果类型统计
        by_outcome_map[outcome_type] = by_outcome_map.get(outcome_type, 0) + 1
    
    by_direction = []
    for direction, stats in by_direction_map.items():
        avg_score = stats["score"] / stats["total"] if stats["total"] > 0 else 0
        by_direction.append((direction, stats["total"], stats["hit"], avg_score))
    
    by_symbol = []
    for symbol, stats in by_symbol_map.items():
        avg_score = stats["score"] / stats["total"] if stats["total"] > 0 else 0
        by_symbol.append((symbol, stats["total"], stats["hit"], avg_score))
    
    by_interval = []
    for interval, stats in by_interval_map.items():
        avg_score = stats["score"] / stats["total"] if stats["total"] > 0 else 0
        by_interval.append((interval, stats["total"], stats["hit"], avg_score))
    
    by_outcome = list(by_outcome_map.items())
    
    avg_score = total_score / total if total > 0 else 0
    
    return {
        "total": total,
        "hit_count": hit_count,
        "avg_score": avg_score,
        "by_direction": by_direction,
        "by_symbol": by_symbol,
        "by_interval": by_interval,
        "by_outcome": by_outcome,
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
    """打印结果列表（基于 analysis_snapshot.outcome_json）"""
    print("\n📊 最近的结果回填")
    print("=" * 110)
    print(f"{'ID':<6} {'交易对':<12} {'周期':<8} {'K线数':<8} {'起始价':<10} {'最高价':<10} {'最低价':<10} {'方向':<8} {'命中目标':<8}")
    print("-" * 110)
    
    rows = query_outcomes(limit)
    if not rows:
        print("（暂无数据）")
    else:
        import json
        for row in rows:
            snapshot_id, symbol, interval, timestamp, price, outcome_json_str = row
            try:
                outcome = json.loads(outcome_json_str)
            except Exception:
                outcome = {}
            direction = outcome.get("direction", "unknown")
            evaluated_bars = outcome.get("evaluated_bars", 0)
            entry_price = outcome.get("entry_price", price)
            max_high = outcome.get("max_high", entry_price)
            min_low = outcome.get("min_low", entry_price)
            hit_target = outcome.get("hit_target", False)
            hit_str = "是" if hit_target else "否"
            print(f"{snapshot_id:<6} {symbol:<12} {interval:<8} {evaluated_bars:<8} {entry_price:<10.2f} {max_high:<10.2f} {min_low:<10.2f} {direction:<8} {hit_str:<8}")
    
    print()


def print_accuracy():
    """打印准确率统计"""
    stats = calculate_accuracy()
    
    print("\n📈 AI 预测准确率统计")
    print("=" * 60)
    
    # 总体统计
    total = stats["total"]
    hit_count = stats["hit_count"]
    avg_score = stats["avg_score"]
    accuracy = (hit_count / total * 100) if total > 0 else 0
    
    print(f"\n总评估次数: {total}")
    print(f"命中目标次数: {hit_count}")
    print(f"命中率: {accuracy:.2f}%")
    print(f"平均得分: {avg_score:.2f} / 1.0")
    
    # 按结果类型统计
    if stats["by_outcome"]:
        print("\n按结果类型统计:")
        print("-" * 60)
        for outcome_type, count in sorted(stats["by_outcome"], key=lambda x: x[1], reverse=True):
            percentage = (count / total * 100) if total > 0 else 0
            outcome_name = {
                "success": "✓ 成功（命中目标）",
                "partial": "≈ 部分正确（方向对但未达目标）",
                "stopped": "⊗ 止损出局",
                "failed": "✗ 失败（方向错误）",
                "unknown": "? 未知",
                "no_direction": "- 无方向"
            }.get(outcome_type, outcome_type)
            print(f"  {outcome_name:<30} {count:>3} 次 ({percentage:>5.1f}%)")
    
    # 按走势方向统计
    if stats["by_direction"]:
        print("\n按走势方向统计:")
        print(f"{'方向':<10} {'评估次数':<12} {'命中次数':<12} {'平均得分':<12} {'命中率'}")
        print("-" * 70)
        for direction, total_dir, hit_dir, avg_score_dir in stats["by_direction"]:
            acc_dir = (hit_dir / total_dir * 100) if total_dir > 0 else 0
            direction_name = {"up": "看涨 ↑", "down": "看跌 ↓", "unknown": "未知"}.get(direction, direction)
            print(f"{direction_name:<10} {total_dir:<12} {hit_dir:<12} {avg_score_dir:<12.2f} {acc_dir:.2f}%")
    
    # 按交易对统计
    if stats["by_symbol"]:
        print("\n按交易对统计:")
        print(f"{'交易对':<15} {'评估次数':<12} {'命中次数':<12} {'平均得分':<12} {'命中率'}")
        print("-" * 75)
        for symbol, total_sym, hit_sym, avg_score_sym in stats["by_symbol"]:
            acc_sym = (hit_sym / total_sym * 100) if total_sym > 0 else 0
            print(f"{symbol:<15} {total_sym:<12} {hit_sym:<12} {avg_score_sym:<12.2f} {acc_sym:.2f}%")
    
    # 按周期统计
    if stats["by_interval"]:
        print("\n按周期统计:")
        print(f"{'周期':<10} {'评估次数':<12} {'命中次数':<12} {'平均得分':<12} {'命中率'}")
        print("-" * 70)
        for interval, total_int, hit_int, avg_score_int in stats["by_interval"]:
            acc_int = (hit_int / total_int * 100) if total_int > 0 else 0
            print(f"{interval:<10} {total_int:<12} {hit_int:<12} {avg_score_int:<12.2f} {acc_int:.2f}%")
    
    print()


def export_to_csv(filename: str):
    """导出评估结果到 CSV 文件
    
    参数：
    - filename: 输出文件名
    """
    conn = get_db_conn()
    c = conn.cursor()
    
    c.execute(
        """
        SELECT id, symbol, interval, timestamp, price, ai_json, outcome_json
        FROM analysis_snapshot
        WHERE evaluated = 1 AND outcome_json IS NOT NULL
        ORDER BY timestamp ASC
        """
    )
    
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        print("⚠️  没有可导出的数据")
        return
    
    # 准备 CSV 数据
    csv_rows = []
    for row in rows:
        snapshot_id, symbol, interval, timestamp, price, ai_json_str, outcome_json_str = row
        
        try:
            ai_data = json.loads(ai_json_str) if ai_json_str else {}
            outcome = json.loads(outcome_json_str)
        except Exception:
            continue
        
        # 提取关键信息
        primary = ai_data.get("primary_scenario", {})
        
        csv_row = {
            "ID": snapshot_id,
            "交易对": symbol,
            "周期": interval,
            "分析时间": timestamp,
            "入场价格": price,
            "方向": outcome.get("direction", "unknown"),
            "目标(%)": outcome.get("target_pct", 0),
            "止损(%)": outcome.get("stop_pct", 0),
            "命中目标": "是" if outcome.get("hit_target") else "否",
            "触发止损": "是" if outcome.get("hit_stop") else "否",
            "结果类型": outcome.get("outcome", "unknown"),
            "得分": outcome.get("score", 0),
            "最终价格": outcome.get("final_price", 0),
            "最终变动(%)": outcome.get("final_move", 0),
            "最大有利变动(%)": outcome.get("max_favorable_move", 0),
            "最大不利变动(%)": outcome.get("max_adverse_move", 0),
            "评估K线数": outcome.get("evaluated_bars", 0),
            "最高价": outcome.get("max_high", 0),
            "最低价": outcome.get("min_low", 0),
            "AI信心度": primary.get("confidence", ""),
            "AI逻辑": primary.get("logic", "")[:100] if primary.get("logic") else "",  # 截取前100字符
        }
        csv_rows.append(csv_row)
    
    # 写入 CSV
    if csv_rows:
        fieldnames = csv_rows[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        
        print(f"✅ 已导出 {len(csv_rows)} 条记录到: {filename}")
    else:
        print("⚠️  没有有效数据")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据库查询与统计工具")
    parser.add_argument("--snapshots", action="store_true", help="只显示快照列表")
    parser.add_argument("--outcomes", action="store_true", help="只显示结果列表")
    parser.add_argument("--accuracy", action="store_true", help="只显示准确率统计")
    parser.add_argument("--export-csv", type=str, help="导出结果到 CSV 文件")
    parser.add_argument("--limit", type=int, default=10, help="查询记录数量（默认: 10）")
    
    args = parser.parse_args()
    
    # CSV 导出
    if args.export_csv:
        export_to_csv(args.export_csv)
        return
    
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
