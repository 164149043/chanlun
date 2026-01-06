import sqlite3
import json
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent / "chanlun_ai.db"


def connect_db() -> sqlite3.Connection:
    """连接 SQLite 数据库（只读逻辑，不修改数据）"""
    return sqlite3.connect(DB_PATH)


def fetch_evaluated_records(conn):
    """获取已评估的快照记录

    返回每条记录的结构：
    {
      "id": int,
      "symbol": str,
      "interval": str,
      "price": float,
      "ai": dict,         # ai_json 解析后
      "outcome": dict     # outcome_json 解析后
    }
    """
    rows = conn.execute(
        """
        SELECT id, symbol, interval, price, ai_json, outcome_json
        FROM analysis_snapshot
        WHERE evaluated = 1 AND ai_json IS NOT NULL AND outcome_json IS NOT NULL
        """
    ).fetchall()

    records = []
    for rid, symbol, interval, price, ai_json_str, outcome_json_str in rows:
        try:
            ai = json.loads(ai_json_str)
            outcome = json.loads(outcome_json_str)
        except Exception:
            # 跳过无法解析的记录
            continue
        records.append(
            {
                "id": rid,
                "symbol": symbol,
                "interval": interval,
                "price": float(price),
                "ai": ai,
                "outcome": outcome,
            }
        )
    return records


def compute_in_zs(record) -> str:
    """根据 AI 输出判断当前价格是否在中枢区间内

    返回值："in" / "out" / "unknown"
    """
    ai = record["ai"]
    price = record["price"]

    try:
        zs = ai.get("structure_judgement", {}).get("zs", {})
        zs_range = zs.get("range") or []
        if not (isinstance(zs_range, list) and len(zs_range) == 2):
            return "unknown"
        low, high = float(zs_range[0]), float(zs_range[1])
        if low <= price <= high:
            return "in"
        else:
            return "out"
    except Exception:
        return "unknown"


def stat_ai_overall(records):
    """按 primary_scenario.direction 统计 AI 总体表现"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0, "stops": 0})

    for rec in records:
        ai = rec["ai"]
        outcome = rec["outcome"]
        primary = ai.get("primary_scenario") or {}
        direction = primary.get("direction", "unknown")

        hit_target = bool(outcome.get("hit_target"))
        hit_stop = bool(outcome.get("hit_stop"))

        s = stats[direction]
        s["total"] += 1
        if hit_target:
            s["wins"] += 1
        if hit_stop:
            s["stops"] += 1

    # 生成列表并计算胜率
    result = []
    for direction, s in stats.items():
        total = s["total"]
        wins = s["wins"]
        stops = s["stops"]
        win_rate = round(wins / total, 3) if total > 0 else 0.0
        result.append((direction, total, wins, stops, win_rate))

    # 按样本数降序排序
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def stat_by_structure(records):
    """按是否在中枢内统计表现（不区分 AI 方向）"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0})

    for rec in records:
        outcome = rec["outcome"]
        in_zs = compute_in_zs(rec)
        hit_target = bool(outcome.get("hit_target"))

        s = stats[in_zs]
        s["total"] += 1
        if hit_target:
            s["wins"] += 1

    result = []
    for in_zs, s in stats.items():
        total = s["total"]
        wins = s["wins"]
        win_rate = round(wins / total, 3) if total > 0 else 0.0
        result.append((in_zs, total, wins, win_rate))

    # 固定顺序：in / out / unknown
    order = {"in": 0, "out": 1, "unknown": 2}
    result.sort(key=lambda x: order.get(x[0], 99))
    return result


def stat_combo_ai_structure(records):
    """结构 × AI 组合统计（方向 × 是否在中枢内）"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0})

    for rec in records:
        ai = rec["ai"]
        outcome = rec["outcome"]
        primary = ai.get("primary_scenario") or {}
        direction = primary.get("direction", "unknown")
        in_zs = compute_in_zs(rec)
        hit_target = bool(outcome.get("hit_target"))

        key = (direction, in_zs)
        s = stats[key]
        s["total"] += 1
        if hit_target:
            s["wins"] += 1

    result = []
    for (direction, in_zs), s in stats.items():
        total = s["total"]
        wins = s["wins"]
        win_rate = round(wins / total, 3) if total > 0 else 0.0
        result.append((direction, in_zs, total, wins, win_rate))

    # 按方向、结构排序
    def sort_key(row):
        direction, in_zs, *_ = row
        dir_order = {"up": 0, "down": 1, "range": 2, "unknown": 3}.get(direction, 9)
        zs_order = {"in": 0, "out": 1, "unknown": 2}.get(in_zs, 9)
        return (dir_order, zs_order)

    result.sort(key=sort_key)
    return result


def print_report(ai_overall, zs_stats, combo_stats):
    print("\n" + "=" * 60)
    print("📊 缠论 × AI 统计报告（研究用）")
    print("=" * 60)

    # 一、AI 总体判断表现
    print("\n【一】AI 总体判断表现（按 primary_scenario.direction）")
    if not ai_overall:
        print("  （暂无数据，请先运行分析和回填脚本）")
    else:
        for d, total, wins, stops, win_rate in ai_overall:
            print(
                f"  - 方向: {d:>6} | 样本: {total:<4} | 命中: {wins:<4} | "
                f"止损: {stops:<4} | 胜率: {win_rate:.3f}"
            )

    # 二、是否在中枢内
    print("\n【二】是否在中枢内（不看 AI，只看结构位置）")
    if not zs_stats:
        print("  （暂无数据）")
    else:
        for in_zs, total, wins, win_rate in zs_stats:
            if in_zs == "in":
                label = "中枢内"
            elif in_zs == "out":
                label = "中枢外"
            else:
                label = "未知 "
            print(
                f"  - {label} | 样本: {total:<4} | 命中: {wins:<4} | 胜率: {win_rate:.3f}"
            )

    # 三、结构 × AI 组合
    print("\n【三】结构 × AI 组合（方向 × 是否在中枢内）")
    if not combo_stats:
        print("  （暂无数据）")
    else:
        for direction, in_zs, total, wins, win_rate in combo_stats:
            if in_zs == "in":
                zs_label = "中枢内"
            elif in_zs == "out":
                zs_label = "中枢外"
            else:
                zs_label = "未知 "
            print(
                f"  - AI:{direction:>6} + {zs_label} | 样本:{total:<4} | 胜率:{win_rate:.3f}"
            )

    print("\n" + "=" * 60)
    print("📌 提示：")
    print("  • 胜率 < 0.45 的组合，可以考虑忽略")
    print("  • 样本数 < 20 的结论暂不采信，只作参考")
    print("  • 建议按交易对、周期分别统计，可扩展为分组过滤")
    print("=" * 60)


def main():
    conn = connect_db()
    try:
        records = fetch_evaluated_records(conn)
        ai_overall = stat_ai_overall(records)
        zs_stats = stat_by_structure(records)
        combo_stats = stat_combo_ai_structure(records)
        print_report(ai_overall, zs_stats, combo_stats)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
