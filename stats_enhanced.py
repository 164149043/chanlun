# -*- coding: utf-8 -*-
"""增强版统计报表模块

新增统计维度：
1. 按买卖点类型（1buy/2buy/3buy/1sell/2sell/3sell）
2. 按趋势类型（up_trend/down_trend/consolidation）
3. 按力度对比（weakening/strengthening/similar）
4. 按价格位置（above_zs/below_zs/inside_zs）
5. 按有无信号（has_signal）
6. 交叉组合统计（信号类型 × 趋势 × 位置）
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

import sqlite3
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Any

DB_PATH = Path(__file__).parent / "chanlun_ai.db"


def connect_db() -> sqlite3.Connection:
    """连接数据库"""
    return sqlite3.connect(DB_PATH)


def fetch_evaluated_records(conn) -> List[Dict[str, Any]]:
    """获取所有已评估的记录"""
    rows = conn.execute(
        """
        SELECT id, symbol, interval, price, ai_json, outcome_json, chanlun_json
        FROM analysis_snapshot
        WHERE evaluated = 1 AND ai_json IS NOT NULL AND outcome_json IS NOT NULL
        """
    ).fetchall()

    records = []
    for rid, symbol, interval, price, ai_json_str, outcome_json_str, chanlun_json_str in rows:
        try:
            ai = json.loads(ai_json_str)
            outcome = json.loads(outcome_json_str)
            chanlun = json.loads(chanlun_json_str) if chanlun_json_str else None
        except Exception:
            continue
        
        records.append({
            "id": rid,
            "symbol": symbol,
            "interval": interval,
            "price": float(price),
            "ai": ai,
            "outcome": outcome,
            "chanlun": chanlun,  # 新增：完整缠论结构
        })
    return records


def get_structure_context(record: Dict) -> Dict:
    """从记录中提取结构上下文"""
    outcome = record["outcome"]
    ai = record["ai"]
    chanlun = record.get("chanlun", {})  # 完整缠论结构
    
    # 优先从 outcome 中获取（新版评估会保存）
    ctx = outcome.get("structure_context", {})
    
    if not ctx or ctx.get("trend") == "unknown":
        # 优先从 chanlun_json（exporter 导出的完整结构）提取
        source = chanlun if chanlun else ai
        
        signal = source.get("signal", {})
        summary = source.get("structure_summary", {})
        
        ctx = {
            "buy_sell_points": signal.get("buy_sell_points", []),
            "divergences": signal.get("divergences", []),
            "trend": summary.get("trend", "unknown"),
            "price_position": summary.get("price_position", "unknown"),
            "strength_comparison": summary.get("strength_comparison", "unknown"),
            "signal_type": "unknown",
            "has_signal": False,
        }
        
        # 判断有无信号
        ctx["has_signal"] = bool(ctx["buy_sell_points"] or ctx["divergences"])
        
        # 分类信号类型
        ctx["signal_type"] = _classify_signal(ctx["buy_sell_points"], ctx["divergences"])
    
    return ctx


def _classify_signal(buy_sell_points: list, divergences: list) -> str:
    """分类信号类型"""
    if not buy_sell_points and not divergences:
        return "none"
    
    for signal in buy_sell_points:
        signal_lower = signal.lower()
        if "1buy" in signal_lower:
            return "1buy"
        elif "2buy" in signal_lower:
            return "2buy"
        elif "3buy" in signal_lower:
            return "3buy"
        elif "1sell" in signal_lower:
            return "1sell"
        elif "2sell" in signal_lower:
            return "2sell"
        elif "3sell" in signal_lower:
            return "3sell"
    
    for bc in divergences:
        bc_lower = bc.lower()
        if "bottom" in bc_lower or "底" in bc:
            return "bc_buy"
        elif "top" in bc_lower or "顶" in bc:
            return "bc_sell"
    
    return "mixed"


# ============================================
# 统计函数
# ============================================

def stat_by_signal_type(records: List[Dict]) -> List[Tuple]:
    """按信号类型统计"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0, "enhanced_score": 0})
    
    for rec in records:
        ctx = get_structure_context(rec)
        outcome = rec["outcome"]
        signal_type = ctx.get("signal_type", "unknown")
        
        s = stats[signal_type]
        s["total"] += 1
        if outcome.get("hit_target"):
            s["wins"] += 1
        s["score"] += outcome.get("score", 0)
        s["enhanced_score"] += outcome.get("enhanced_score", outcome.get("score", 0))
    
    result = []
    for sig_type, s in stats.items():
        total = s["total"]
        wins = s["wins"]
        win_rate = round(wins / total, 3) if total > 0 else 0
        avg_score = round(s["score"] / total, 3) if total > 0 else 0
        avg_enhanced = round(s["enhanced_score"] / total, 3) if total > 0 else 0
        result.append((sig_type, total, wins, win_rate, avg_score, avg_enhanced))
    
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def stat_by_trend(records: List[Dict]) -> List[Tuple]:
    """按趋势类型统计"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0})
    
    for rec in records:
        ctx = get_structure_context(rec)
        outcome = rec["outcome"]
        trend = ctx.get("trend", "unknown")
        
        s = stats[trend]
        s["total"] += 1
        if outcome.get("hit_target"):
            s["wins"] += 1
        s["score"] += outcome.get("score", 0)
    
    result = []
    for trend, s in stats.items():
        total = s["total"]
        wins = s["wins"]
        win_rate = round(wins / total, 3) if total > 0 else 0
        avg_score = round(s["score"] / total, 3) if total > 0 else 0
        result.append((trend, total, wins, win_rate, avg_score))
    
    order = {"up_trend": 0, "down_trend": 1, "consolidation": 2, "unknown": 3}
    result.sort(key=lambda x: order.get(x[0], 99))
    return result


def stat_by_position(records: List[Dict]) -> List[Tuple]:
    """按价格位置统计"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0})
    
    for rec in records:
        ctx = get_structure_context(rec)
        outcome = rec["outcome"]
        position = ctx.get("price_position", "unknown")
        
        s = stats[position]
        s["total"] += 1
        if outcome.get("hit_target"):
            s["wins"] += 1
        s["score"] += outcome.get("score", 0)
    
    result = []
    for pos, s in stats.items():
        total = s["total"]
        wins = s["wins"]
        win_rate = round(wins / total, 3) if total > 0 else 0
        avg_score = round(s["score"] / total, 3) if total > 0 else 0
        result.append((pos, total, wins, win_rate, avg_score))
    
    order = {"above_zs": 0, "inside_zs": 1, "below_zs": 2, "unknown": 3}
    result.sort(key=lambda x: order.get(x[0], 99))
    return result


def stat_by_strength(records: List[Dict]) -> List[Tuple]:
    """按力度对比统计"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0})
    
    for rec in records:
        ctx = get_structure_context(rec)
        outcome = rec["outcome"]
        strength = ctx.get("strength_comparison", "unknown")
        
        s = stats[strength]
        s["total"] += 1
        if outcome.get("hit_target"):
            s["wins"] += 1
        s["score"] += outcome.get("score", 0)
    
    result = []
    for strength, s in stats.items():
        total = s["total"]
        wins = s["wins"]
        win_rate = round(wins / total, 3) if total > 0 else 0
        avg_score = round(s["score"] / total, 3) if total > 0 else 0
        result.append((strength, total, wins, win_rate, avg_score))
    
    order = {"weakening": 0, "strengthening": 1, "similar": 2, "unknown": 3}
    result.sort(key=lambda x: order.get(x[0], 99))
    return result


def stat_by_has_signal(records: List[Dict]) -> List[Tuple]:
    """按有无信号统计"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0})
    
    for rec in records:
        ctx = get_structure_context(rec)
        outcome = rec["outcome"]
        has_signal = ctx.get("has_signal", False)
        key = "has_signal" if has_signal else "no_signal"
        
        s = stats[key]
        s["total"] += 1
        if outcome.get("hit_target"):
            s["wins"] += 1
        s["score"] += outcome.get("score", 0)
    
    result = []
    for key, s in stats.items():
        total = s["total"]
        wins = s["wins"]
        win_rate = round(wins / total, 3) if total > 0 else 0
        avg_score = round(s["score"] / total, 3) if total > 0 else 0
        result.append((key, total, wins, win_rate, avg_score))
    
    return result


def stat_combo_signal_direction(records: List[Dict]) -> List[Tuple]:
    """信号类型 × AI方向 组合统计"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0})
    
    for rec in records:
        ctx = get_structure_context(rec)
        outcome = rec["outcome"]
        ai = rec["ai"]
        
        signal_type = ctx.get("signal_type", "unknown")
        primary = ai.get("primary_scenario", {})
        direction = primary.get("direction", outcome.get("direction", "unknown"))
        
        key = (signal_type, direction)
        s = stats[key]
        s["total"] += 1
        if outcome.get("hit_target"):
            s["wins"] += 1
        s["score"] += outcome.get("score", 0)
    
    result = []
    for (sig, dir), s in stats.items():
        total = s["total"]
        wins = s["wins"]
        win_rate = round(wins / total, 3) if total > 0 else 0
        avg_score = round(s["score"] / total, 3) if total > 0 else 0
        result.append((sig, dir, total, wins, win_rate, avg_score))
    
    result.sort(key=lambda x: x[2], reverse=True)
    return result


def stat_by_signal_quality(records: List[Dict]) -> List[Tuple]:
    """按信号质量评级统计"""
    stats = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0})
    
    for rec in records:
        ai = rec["ai"]
        outcome = rec["outcome"]
        
        # 获取信号质量评级
        quality = ai.get("signal_quality", {})
        grade = quality.get("grade", "unknown")
        
        s = stats[grade]
        s["total"] += 1
        if outcome.get("hit_target"):
            s["wins"] += 1
        s["score"] += outcome.get("score", 0)
    
    result = []
    for grade, s in stats.items():
        total = s["total"]
        wins = s["wins"]
        win_rate = round(wins / total, 3) if total > 0 else 0
        avg_score = round(s["score"] / total, 3) if total > 0 else 0
        result.append((grade, total, wins, win_rate, avg_score))
    
    # 按评级排序
    order = {"A": 0, "B": 1, "C": 2, "D": 3, "unknown": 4}
    result.sort(key=lambda x: order.get(x[0], 99))
    return result


def stat_performance_metrics(records: List[Dict]) -> Dict:
    """计算整体性能指标"""
    if not records:
        return {}
    
    total = len(records)
    wins = sum(1 for r in records if r["outcome"].get("hit_target"))
    stops = sum(1 for r in records if r["outcome"].get("hit_stop"))
    
    total_score = sum(r["outcome"].get("score", 0) for r in records)
    total_enhanced = sum(r["outcome"].get("enhanced_score", r["outcome"].get("score", 0)) for r in records)
    
    # 收集盈亏比
    rr_list = [r["outcome"].get("actual_rr", 0) for r in records if r["outcome"].get("actual_rr", 0) > 0]
    avg_rr = round(sum(rr_list) / len(rr_list), 2) if rr_list else 0
    
    # 收集命中时间
    hit_bars = [r["outcome"].get("hit_target_bar", 0) for r in records if r["outcome"].get("hit_target_bar")]
    avg_hit_bar = round(sum(hit_bars) / len(hit_bars), 1) if hit_bars else 0
    
    return {
        "total": total,
        "wins": wins,
        "stops": stops,
        "win_rate": round(wins / total, 3) if total > 0 else 0,
        "stop_rate": round(stops / total, 3) if total > 0 else 0,
        "avg_score": round(total_score / total, 3) if total > 0 else 0,
        "avg_enhanced_score": round(total_enhanced / total, 3) if total > 0 else 0,
        "avg_actual_rr": avg_rr,
        "avg_hit_bars": avg_hit_bar,
    }


# ============================================
# 报表输出
# ============================================

def print_enhanced_report(records: List[Dict]):
    """打印增强版统计报表（中文）"""
    
    print("\n" + "=" * 70)
    print("  缠论 + AI 增强版统计报表")
    print("=" * 70)
    
    if not records:
        print("\n  （暂无数据，请先运行分析和评估）")
        return
    
    # 1. 整体性能指标
    metrics = stat_performance_metrics(records)
    print("\n【1】整体性能")
    print("-" * 70)
    print(f"  总样本数:       {metrics['total']}")
    print(f"  命中次数:       {metrics['wins']} ({metrics['win_rate']*100:.1f}%)")
    print(f"  止损次数:       {metrics['stops']} ({metrics['stop_rate']*100:.1f}%)")
    print(f"  平均得分:       {metrics['avg_score']:.3f}")
    print(f"  增强得分:       {metrics['avg_enhanced_score']:.3f}")
    print(f"  平均盈亏比:     {metrics['avg_actual_rr']:.2f}")
    print(f"  平均命中时间:   {metrics['avg_hit_bars']:.1f} 根K线")
    
    # 2. 按信号类型统计
    signal_stats = stat_by_signal_type(records)
    if signal_stats:
        print("\n【2】按信号类型")
        print("-" * 70)
        print(f"  {'信号':<12} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分':<10}")
        print("  " + "-" * 55)
        for sig, total, wins, win_rate, avg_score, _ in signal_stats:
            sig_name = _get_signal_name_cn(sig)
            print(f"  {sig_name:<12} {total:<10} {wins:<8} {win_rate*100:>6.1f}%   {avg_score:<10.3f}")
    
    # 3. 按趋势统计
    trend_stats = stat_by_trend(records)
    if trend_stats:
        print("\n【3】按趋势类型")
        print("-" * 70)
        print(f"  {'趋势':<12} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分':<10}")
        print("  " + "-" * 55)
        for trend, total, wins, win_rate, avg_score in trend_stats:
            trend_name = _get_trend_name_cn(trend)
            print(f"  {trend_name:<12} {total:<10} {wins:<8} {win_rate*100:>6.1f}%   {avg_score:<10.3f}")
    
    # 4. 按价格位置统计
    pos_stats = stat_by_position(records)
    if pos_stats:
        print("\n【4】按价格位置")
        print("-" * 70)
        print(f"  {'位置':<12} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分':<10}")
        print("  " + "-" * 55)
        for pos, total, wins, win_rate, avg_score in pos_stats:
            pos_name = _get_position_name_cn(pos)
            print(f"  {pos_name:<12} {total:<10} {wins:<8} {win_rate*100:>6.1f}%   {avg_score:<10.3f}")
    
    # 5. 按力度对比统计
    strength_stats = stat_by_strength(records)
    if strength_stats:
        print("\n【5】按力度对比")
        print("-" * 70)
        print(f"  {'力度':<12} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分':<10}")
        print("  " + "-" * 55)
        for strength, total, wins, win_rate, avg_score in strength_stats:
            strength_name = _get_strength_name_cn(strength)
            print(f"  {strength_name:<12} {total:<10} {wins:<8} {win_rate*100:>6.1f}%   {avg_score:<10.3f}")
    
    # 6. 按有无信号统计
    signal_exist_stats = stat_by_has_signal(records)
    if signal_exist_stats:
        print("\n【6】按有无信号")
        print("-" * 70)
        for key, total, wins, win_rate, avg_score in signal_exist_stats:
            label = "有信号" if key == "has_signal" else "无信号"
            print(f"  {label:<12} 样本: {total:<6} 胜率: {win_rate*100:>5.1f}%  平均分: {avg_score:.3f}")
    
    # 7. 组合统计（信号 × 方向）
    combo_stats = stat_combo_signal_direction(records)
    if combo_stats:
        print("\n【7】组合统计：信号 × 方向（前10）")
        print("-" * 70)
        print(f"  {'信号':<10} {'方向':<6} {'样本':<8} {'命中':<6} {'胜率':<10}")
        print("  " + "-" * 50)
        for sig, dir, total, wins, win_rate, _ in combo_stats[:10]:
            if total >= 3:  # 至少3个样本
                sig_name = _get_signal_name_cn(sig)[:10]
                dir_name = {"up": "看涨", "down": "看跌", "unknown": "未知"}.get(dir, dir)
                print(f"  {sig_name:<10} {dir_name:<6} {total:<8} {wins:<6} {win_rate*100:>6.1f}%")
    
    # 8. 按信号质量评级统计
    quality_stats = stat_by_signal_quality(records)
    has_quality_data = any(g != "unknown" for g, _, _, _, _ in quality_stats)
    if quality_stats and has_quality_data:
        print("\n【8】按信号质量评级")
        print("-" * 70)
        print(f"  {'评级':<10} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分':<10}")
        print("  " + "-" * 55)
        grade_names = {
            "A": "A-优质",
            "B": "B-良好",
            "C": "C-一般",
            "D": "D-低质",
            "unknown": "未评级",
        }
        for grade, total, wins, win_rate, avg_score in quality_stats:
            grade_name = grade_names.get(grade, grade)
            print(f"  {grade_name:<10} {total:<10} {wins:<8} {win_rate*100:>6.1f}%   {avg_score:<10.3f}")
    
    print("\n" + "=" * 70)
    print("  【提示】胜率 > 50% 且样本数 >= 10 的组合具有统计意义")
    print("  【提示】信号质量评级 A/B 的胜率应高于 C/D")
    print("=" * 70 + "\n")


def _get_signal_name(sig: str) -> str:
    """获取信号显示名称（英文）"""
    names = {
        "1buy": "1Buy",
        "2buy": "2Buy",
        "3buy": "3Buy",
        "1sell": "1Sell",
        "2sell": "2Sell",
        "3sell": "3Sell",
        "bc_buy": "BC_Buy",
        "bc_sell": "BC_Sell",
        "mixed": "Mixed",
        "none": "None",
        "unknown": "Unknown",
    }
    return names.get(sig, sig)


def _get_signal_name_cn(sig: str) -> str:
    """获取信号显示名称（中文）"""
    names = {
        "1buy": "一买",
        "2buy": "二买",
        "3buy": "三买",
        "1sell": "一卖",
        "2sell": "二卖",
        "3sell": "三卖",
        "bc_buy": "底背驰买",
        "bc_sell": "顶背驰卖",
        "mixed": "混合信号",
        "none": "无信号",
        "unknown": "未知",
    }
    return names.get(sig, sig)


def _get_trend_name(trend: str) -> str:
    """获取趋势显示名称（英文）"""
    names = {
        "up_trend": "UpTrend",
        "down_trend": "DownTrend",
        "consolidation": "Consolidation",
        "unknown": "Unknown",
    }
    return names.get(trend, trend)


def _get_trend_name_cn(trend: str) -> str:
    """获取趋势显示名称（中文）"""
    names = {
        "up_trend": "上升趋势",
        "down_trend": "下降趋势",
        "consolidation": "震荡整理",
        "unknown": "未知",
    }
    return names.get(trend, trend)


def _get_position_name(pos: str) -> str:
    """获取位置显示名称（英文）"""
    names = {
        "above_zs": "Above ZS",
        "inside_zs": "Inside ZS",
        "below_zs": "Below ZS",
        "unknown": "Unknown",
    }
    return names.get(pos, pos)


def _get_position_name_cn(pos: str) -> str:
    """获取位置显示名称（中文）"""
    names = {
        "above_zs": "中枢上方",
        "inside_zs": "中枢内部",
        "below_zs": "中枢下方",
        "unknown": "未知",
    }
    return names.get(pos, pos)


def _get_strength_name(strength: str) -> str:
    """获取力度显示名称（英文）"""
    names = {
        "weakening": "Weakening",
        "strengthening": "Strengthening",
        "similar": "Similar",
        "unknown": "Unknown",
    }
    return names.get(strength, strength)


def _get_strength_name_cn(strength: str) -> str:
    """获取力度显示名称（中文）"""
    names = {
        "weakening": "力度衰竭",
        "strengthening": "力度增强",
        "similar": "力度相近",
        "unknown": "未知",
    }
    return names.get(strength, strength)


# ============================================
# 主函数
# ============================================

def main():
    """主函数"""
    conn = connect_db()
    try:
        records = fetch_evaluated_records(conn)
        print_enhanced_report(records)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
