#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据库查询与统计工具（增强版）

用途：
- 查看分析快照历史
- 查看结果回填记录
- 统计 AI 预测准确率
- 导出 CSV 文件（含结构上下文）

使用方法：
    python query_stats.py                    # 显示所有统计
    python query_stats.py --snapshots        # 只显示快照列表
    python query_stats.py --outcomes         # 只显示结果列表
    python query_stats.py --accuracy         # 只显示准确率统计
    python query_stats.py --export-csv results.csv  # 导出结果到 CSV
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
import argparse
import csv
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "chanlun_ai.db"


# ============================================
# 结构上下文提取（从 stats_enhanced.py 复用）
# ============================================

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
# 值翻译函数（英文 -> 中文）
# ============================================

def _translate_direction(direction: str) -> str:
    """翻译方向"""
    return {"up": "看涨", "down": "看跌", "unknown": "未知"}.get(direction, direction)


def _translate_outcome(outcome: str) -> str:
    """翻译结果类型"""
    return {
        "success": "成功命中",
        "partial": "部分正确",
        "stopped": "止损出局",
        "failed": "方向错误",
        "unknown": "未知",
        "no_direction": "无方向"
    }.get(outcome, outcome)


def _translate_trend(trend: str) -> str:
    """翻译趋势"""
    return {
        "up_trend": "上升趋势",
        "down_trend": "下降趋势",
        "consolidation": "震荡整理",
        "unknown": "未知"
    }.get(trend, trend)


def _translate_position(position: str) -> str:
    """翻译价格位置"""
    return {
        "above_zs": "中枢上方",
        "inside_zs": "中枢内部",
        "below_zs": "中枢下方",
        "unknown": "未知"
    }.get(position, position)


def _translate_strength(strength: str) -> str:
    """翻译力度对比"""
    return {
        "weakening": "力度衰竭",
        "strengthening": "力度增强",
        "similar": "力度相近",
        "unknown": "未知"
    }.get(strength, strength)


def _translate_signal(signal: str) -> str:
    """翻译信号类型"""
    return {
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
        "unknown": "未知"
    }.get(signal, signal)


def _translate_quality(grade: str) -> str:
    """翻译信号质量评级"""
    return {
        "A": "A-优质",
        "B": "B-良好",
        "C": "C-一般",
        "D": "D-低质",
        "unknown": "未评级"
    }.get(grade, grade if grade else "未评级")


def _translate_action(action: str) -> str:
    """翻译建议动作"""
    return {
        "trade": "建议交易",
        "wait": "建议观望",
        "skip": "建议跳过",
        "": "无建议"
    }.get(action, action if action else "无建议")


def extract_structure_context(chanlun_json: dict, ai_json: dict, outcome_json: dict) -> dict:
    """从记录中提取结构上下文
    
    参数：
    - chanlun_json: exporter 导出的完整缠论结构
    - ai_json: AI 的输出
    - outcome_json: 评估结果
    
    返回：
    - dict: 结构上下文
    """
    # 优先从 outcome 中获取（新版评估会保存）
    ctx = outcome_json.get("structure_context", {}) if outcome_json else {}
    
    if not ctx or ctx.get("trend") == "unknown":
        # 优先从 chanlun_json 提取
        source = chanlun_json if chanlun_json else ai_json
        
        if source:
            signal = source.get("signal", {})
            summary = source.get("structure_summary", {})
            
            buy_sell_points = signal.get("buy_sell_points", [])
            divergences = signal.get("divergences", [])
            
            ctx = {
                "trend": summary.get("trend", "unknown"),
                "price_position": summary.get("price_position", "unknown"),
                "strength_comparison": summary.get("strength_comparison", "unknown"),
                "signal_type": _classify_signal(buy_sell_points, divergences),
                "has_signal": bool(buy_sell_points or divergences),
            }
    
    return ctx


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
    """计算 AI 预测准确率统计（增强版，含结构上下文）"""
    conn = get_db_conn()
    c = conn.cursor()
    
    # 增加 chanlun_json 和 ai_json
    c.execute(
        """
        SELECT outcome_json, symbol, interval, chanlun_json, ai_json
        FROM analysis_snapshot
        WHERE evaluated = 1 AND outcome_json IS NOT NULL
        """
    )
    rows = c.fetchall()
    conn.close()
    
    total = 0
    hit_count = 0
    stop_count = 0
    by_direction_map = {}
    by_symbol_map = {}
    by_interval_map = {}
    by_outcome_map = {}
    by_trend_map = {}
    by_position_map = {}
    by_signal_map = {}
    by_quality_map = {}
    by_scoring_mode_map = {}  # 新增：按评分模式统计
    total_score = 0
    total_enhanced_score = 0
    
    for (outcome_json_str, symbol, interval, chanlun_json_str, ai_json_str) in rows:
        try:
            outcome = json.loads(outcome_json_str)
            chanlun_data = json.loads(chanlun_json_str) if chanlun_json_str else {}
            ai_data = json.loads(ai_json_str) if ai_json_str else {}
        except Exception:
            continue
        
        total += 1
        direction = outcome.get("direction", "unknown")
        hit_target = outcome.get("hit_target", False)
        hit_stop = outcome.get("hit_stop", False)
        outcome_type = outcome.get("outcome", "unknown")
        score = outcome.get("score", 0)
        enhanced_score = outcome.get("enhanced_score", score)
        
        total_score += score
        total_enhanced_score += enhanced_score
        
        if hit_target:
            hit_count += 1
        if hit_stop:
            stop_count += 1
        
        # 提取结构上下文
        ctx = extract_structure_context(chanlun_data, ai_data, outcome)
        trend = ctx.get("trend", "unknown")
        position = ctx.get("price_position", "unknown")
        signal_type = ctx.get("signal_type", "none")
        
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
        
        # 按趋势统计（新增）
        stats = by_trend_map.setdefault(trend, {"total": 0, "hit": 0, "score": 0})
        stats["total"] += 1
        stats["score"] += score
        if hit_target:
            stats["hit"] += 1
        
        # 按位置统计（新增）
        stats = by_position_map.setdefault(position, {"total": 0, "hit": 0, "score": 0})
        stats["total"] += 1
        stats["score"] += score
        if hit_target:
            stats["hit"] += 1
        
        # 按信号类型统计（新增）
        stats = by_signal_map.setdefault(signal_type, {"total": 0, "hit": 0, "score": 0})
        stats["total"] += 1
        stats["score"] += score
        if hit_target:
            stats["hit"] += 1
        
        # 按信号质量评级统计（新增）
        quality = ai_data.get("signal_quality", {})
        grade = quality.get("grade", "unknown")
        stats = by_quality_map.setdefault(grade, {"total": 0, "hit": 0, "score": 0})
        stats["total"] += 1
        stats["score"] += score
        if hit_target:
            stats["hit"] += 1

        # 按评分模式统计（新增）
        scoring_mode = outcome.get("scoring_mode", "target_based")
        best_score = outcome.get("best_score", score)
        stats = by_scoring_mode_map.setdefault(scoring_mode, {"total": 0, "valid": 0, "score": 0})
        stats["total"] += 1
        stats["score"] += best_score
        if best_score >= 0.5:  # 得分>=0.5视为有效
            stats["valid"] += 1
    
    def build_list(map_data):
        result = []
        for key, stats in map_data.items():
            avg_score = stats["score"] / stats["total"] if stats["total"] > 0 else 0
            hit = stats.get("hit", 0)
            result.append((key, stats["total"], hit, avg_score))
        return result

    def build_scoring_list(map_data):
        """构建评分模式统计列表（特殊处理，因为有valid字段）"""
        result = []
        for key, stats in map_data.items():
            total = stats["total"]
            valid = stats.get("valid", 0)
            avg_score = stats["score"] / total if total > 0 else 0
            result.append((key, total, valid, avg_score))
        return result
    
    by_direction = build_list(by_direction_map)
    by_symbol = build_list(by_symbol_map)
    by_interval = build_list(by_interval_map)
    by_trend = build_list(by_trend_map)
    by_position = build_list(by_position_map)
    by_signal = build_list(by_signal_map)
    by_quality = build_list(by_quality_map)
    by_outcome = list(by_outcome_map.items())
    by_scoring_mode = build_scoring_list(by_scoring_mode_map)  # 新增
    
    avg_score = total_score / total if total > 0 else 0
    avg_enhanced_score = total_enhanced_score / total if total > 0 else 0
    
    return {
        "total": total,
        "hit_count": hit_count,
        "stop_count": stop_count,
        "avg_score": avg_score,
        "avg_enhanced_score": avg_enhanced_score,
        "by_direction": by_direction,
        "by_symbol": by_symbol,
        "by_interval": by_interval,
        "by_outcome": by_outcome,
        # 新增
        "by_trend": by_trend,
        "by_position": by_position,
        "by_signal": by_signal,
        "by_quality": by_quality,
        "by_scoring_mode": by_scoring_mode,  # v2.2 新增
    }

def print_snapshots(limit: int = 10):
    """打印快照列表"""
    print("\n【最近分析快照】")
    print("=" * 90)
    print(f"{'ID':<6} {'交易对':<12} {'周期':<8} {'时间':<30} {'价格':<12} {'AI输出'}")
    print("-" * 90)
    
    rows = query_snapshots(limit)
    if not rows:
        print("（暂无数据）")
    else:
        for row in rows:
            snapshot_id, symbol, interval, timestamp, price, has_ai = row
            print(f"{snapshot_id:<6} {symbol:<12} {interval:<8} {timestamp:<30} {price:<12.2f} {has_ai}")
    
    print()


def print_outcomes(limit: int = 10):
    """打印结果列表（基于 analysis_snapshot.outcome_json）"""
    print("\n【最近评估结果】")
    print("=" * 110)
    print(f"{'ID':<6} {'交易对':<12} {'周期':<8} {'K线数':<8} {'起始价':<10} {'最高价':<10} {'最低价':<10} {'方向':<8} {'命中':<8}")
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
            direction_cn = {"up": "看涨", "down": "看跌", "unknown": "未知"}.get(direction, direction)
            evaluated_bars = outcome.get("evaluated_bars", 0)
            entry_price = outcome.get("entry_price", price)
            max_high = outcome.get("max_high", entry_price)
            min_low = outcome.get("min_low", entry_price)
            hit_target = outcome.get("hit_target", False)
            hit_str = "是" if hit_target else "否"
            print(f"{snapshot_id:<6} {symbol:<12} {interval:<8} {evaluated_bars:<8} {entry_price:<10.2f} {max_high:<10.2f} {min_low:<10.2f} {direction_cn:<8} {hit_str:<8}")
    
    print()


def print_accuracy():
    """打印准确率统计（增强版 - 中文）"""
    stats = calculate_accuracy()
    
    print("\n" + "=" * 70)
    print("  AI 预测准确率统计报表（增强版）")
    print("=" * 70)
    
    # 总体统计
    total = stats["total"]
    hit_count = stats["hit_count"]
    stop_count = stats.get("stop_count", 0)
    avg_score = stats["avg_score"]
    avg_enhanced = stats.get("avg_enhanced_score", avg_score)
    accuracy = (hit_count / total * 100) if total > 0 else 0
    stop_rate = (stop_count / total * 100) if total > 0 else 0
    
    print(f"\n【整体统计】")
    print(f"  总样本数:       {total}")
    print(f"  命中目标:       {hit_count} ({accuracy:.1f}%)")
    print(f"  触发止损:       {stop_count} ({stop_rate:.1f}%)")
    print(f"  平均得分:       {avg_score:.3f}")
    print(f"  增强得分:       {avg_enhanced:.3f}")
    
    # 按结果类型统计
    if stats["by_outcome"]:
        print("\n【按结果类型】")
        print("-" * 60)
        for outcome_type, count in sorted(stats["by_outcome"], key=lambda x: x[1], reverse=True):
            percentage = (count / total * 100) if total > 0 else 0
            outcome_name = {
                "success": "[OK] 成功命中",
                "partial": "[~~] 部分正确（方向对）",
                "stopped": "[XX] 止损出局",
                "failed": "[NO] 方向错误",
                "unknown": "[??] 未知",
                "no_direction": "[--] 无方向"
            }.get(outcome_type, outcome_type)
            print(f"  {outcome_name:<28} {count:>4} ({percentage:>5.1f}%)")
    
    # 按走势方向统计
    if stats["by_direction"]:
        print("\n【按预测方向】")
        print(f"  {'方向':<8} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分'}")
        print("  " + "-" * 50)
        for direction, total_dir, hit_dir, avg_score_dir in stats["by_direction"]:
            acc_dir = (hit_dir / total_dir * 100) if total_dir > 0 else 0
            direction_name = {"up": "看涨", "down": "看跌", "unknown": "未知"}.get(direction, direction)
            print(f"  {direction_name:<8} {total_dir:<10} {hit_dir:<8} {acc_dir:>6.1f}%   {avg_score_dir:.3f}")
    
    # 按交易对统计
    if stats["by_symbol"]:
        print("\n【按交易对】")
        print(f"  {'交易对':<12} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分'}")
        print("  " + "-" * 55)
        for symbol, total_sym, hit_sym, avg_score_sym in stats["by_symbol"]:
            acc_sym = (hit_sym / total_sym * 100) if total_sym > 0 else 0
            print(f"  {symbol:<12} {total_sym:<10} {hit_sym:<8} {acc_sym:>6.1f}%   {avg_score_sym:.3f}")
    
    # 按周期统计
    if stats["by_interval"]:
        print("\n【按时间周期】")
        print(f"  {'周期':<10} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分'}")
        print("  " + "-" * 50)
        for interval, total_int, hit_int, avg_score_int in stats["by_interval"]:
            acc_int = (hit_int / total_int * 100) if total_int > 0 else 0
            print(f"  {interval:<10} {total_int:<10} {hit_int:<8} {acc_int:>6.1f}%   {avg_score_int:.3f}")
    
    # 按趋势统计（新增）
    if stats.get("by_trend"):
        print("\n【按趋势类型】")
        print(f"  {'趋势':<12} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分'}")
        print("  " + "-" * 50)
        trend_order = {"up_trend": 0, "down_trend": 1, "consolidation": 2, "unknown": 3}
        sorted_trends = sorted(stats["by_trend"], key=lambda x: trend_order.get(x[0], 99))
        for trend, total_t, hit_t, avg_score_t in sorted_trends:
            acc_t = (hit_t / total_t * 100) if total_t > 0 else 0
            trend_name = {"up_trend": "上升趋势", "down_trend": "下降趋势", "consolidation": "震荡整理", "unknown": "未知"}.get(trend, trend)
            print(f"  {trend_name:<12} {total_t:<10} {hit_t:<8} {acc_t:>6.1f}%   {avg_score_t:.3f}")
    
    # 按位置统计（新增）
    if stats.get("by_position"):
        print("\n【按价格位置】")
        print(f"  {'位置':<12} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分'}")
        print("  " + "-" * 50)
        pos_order = {"above_zs": 0, "inside_zs": 1, "below_zs": 2, "unknown": 3}
        sorted_pos = sorted(stats["by_position"], key=lambda x: pos_order.get(x[0], 99))
        for pos, total_p, hit_p, avg_score_p in sorted_pos:
            acc_p = (hit_p / total_p * 100) if total_p > 0 else 0
            pos_name = {"above_zs": "中枢上方", "inside_zs": "中枢内部", "below_zs": "中枢下方", "unknown": "未知"}.get(pos, pos)
            print(f"  {pos_name:<12} {total_p:<10} {hit_p:<8} {acc_p:>6.1f}%   {avg_score_p:.3f}")
    
    # 按信号类型统计（新增）
    if stats.get("by_signal"):
        print("\n【按信号类型】")
        print(f"  {'信号':<12} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分'}")
        print("  " + "-" * 50)
        sorted_sig = sorted(stats["by_signal"], key=lambda x: x[1], reverse=True)
        for sig, total_s, hit_s, avg_score_s in sorted_sig:
            acc_s = (hit_s / total_s * 100) if total_s > 0 else 0
            sig_name = {
                "1buy": "一买", "2buy": "二买", "3buy": "三买",
                "1sell": "一卖", "2sell": "二卖", "3sell": "三卖",
                "bc_buy": "底背驰买", "bc_sell": "顶背驰卖",
                "mixed": "混合信号", "none": "无信号", "unknown": "未知"
            }.get(sig, sig)
            print(f"  {sig_name:<12} {total_s:<10} {hit_s:<8} {acc_s:>6.1f}%   {avg_score_s:.3f}")
    
    # 按信号质量评级统计（新增）
    if stats.get("by_quality"):
        has_quality_data = any(q[0] != "unknown" for q in stats["by_quality"])
        if has_quality_data:
            print("\n【按信号质量评级】")
            print(f"  {'评级':<10} {'样本数':<10} {'命中':<8} {'胜率':<10} {'平均分'}")
            print("  " + "-" * 50)
            quality_order = {"A": 0, "B": 1, "C": 2, "D": 3, "unknown": 4}
            sorted_quality = sorted(stats["by_quality"], key=lambda x: quality_order.get(x[0], 99))
            for grade, total_q, hit_q, avg_score_q in sorted_quality:
                acc_q = (hit_q / total_q * 100) if total_q > 0 else 0
                grade_name = {
                    "A": "A-优质", "B": "B-良好", "C": "C-一般", "D": "D-低质", "unknown": "未评级"
                }.get(grade, grade)
                print(f"  {grade_name:<10} {total_q:<10} {hit_q:<8} {acc_q:>6.1f}%   {avg_score_q:.3f}")

    # 按评分模式统计（v2.2 新增）
    if stats.get("by_scoring_mode"):
        print("\n【按评分模式】")
        print(f"  {'模式':<18} {'样本数':<10} {'有效':<8} {'有效率':<10} {'平均分'}")
        print("  " + "-" * 55)
        mode_names = {
            "target_based": "目标命中",
            "atr_normalized": "ATR归一化",
            "signal_expected": "信号期望",
            "volatility_adjusted": "波动率调整",
        }
        for mode, total, valid, avg_score in stats["by_scoring_mode"]:
            mode_name = mode_names.get(mode, mode)
            valid_rate = (valid / total * 100) if total > 0 else 0
            print(f"  {mode_name:<18} {total:<10} {valid:<8} {valid_rate:>6.1f}%   {avg_score:.3f}")

    print("\n" + "=" * 70)
    print("  [提示] 详细分析请运行: python stats_enhanced.py")
    print("=" * 70 + "\n")


def export_to_csv(filename: str):
    """导出评估结果到 CSV 文件（增强版，含结构上下文）
    
    参数：
    - filename: 输出文件名
    """
    conn = get_db_conn()
    c = conn.cursor()
    
    # 增加 chanlun_json 字段
    c.execute(
        """
        SELECT id, symbol, interval, timestamp, price, ai_json, outcome_json, chanlun_json
        FROM analysis_snapshot
        WHERE evaluated = 1 AND outcome_json IS NOT NULL
        ORDER BY timestamp ASC
        """
    )
    
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        print("[WARN] No data to export")
        return
    
    # 准备 CSV 数据
    csv_rows = []
    for row in rows:
        snapshot_id, symbol, interval, timestamp, price, ai_json_str, outcome_json_str, chanlun_json_str = row
        
        try:
            ai_data = json.loads(ai_json_str) if ai_json_str else {}
            outcome = json.loads(outcome_json_str)
            chanlun_data = json.loads(chanlun_json_str) if chanlun_json_str else {}
        except Exception:
            continue
        
        # 提取关键信息
        primary = ai_data.get("primary_scenario", {})
        
        # 提取结构上下文（新增）
        ctx = extract_structure_context(chanlun_data, ai_data, outcome)
        
        csv_row = {
            "ID": snapshot_id,
            "交易对": symbol,
            "周期": interval,
            "分析时间": timestamp,
            "入场价格": price,
            "方向": _translate_direction(outcome.get("direction", "unknown")),
            "目标(%)": outcome.get("target_pct", 0),
            "止损(%)": outcome.get("stop_pct", 0),
            "命中目标": "是" if outcome.get("hit_target") else "否",
            "触发止损": "是" if outcome.get("hit_stop") else "否",
            "结果类型": _translate_outcome(outcome.get("outcome", "unknown")),
            "得分": outcome.get("score", 0),
            "增强得分": outcome.get("enhanced_score", outcome.get("score", 0)),
            "最终价格": outcome.get("final_price", 0),
            "最终变动(%)": outcome.get("final_move", 0),
            "最大有利变动(%)": outcome.get("max_favorable_move", 0),
            "最大不利变动(%)": outcome.get("max_adverse_move", 0),
            "实际盈亏比": outcome.get("actual_rr", 0),
            "命中K线位置": outcome.get("hit_target_bar", ""),
            "评估K线数": outcome.get("evaluated_bars", 0),
            "最高价": outcome.get("max_high", 0),
            "最低价": outcome.get("min_low", 0),
            # 结构上下文字段（中文翻译）
            "趋势类型": _translate_trend(ctx.get("trend", "unknown")),
            "价格位置": _translate_position(ctx.get("price_position", "unknown")),
            "力度对比": _translate_strength(ctx.get("strength_comparison", "unknown")),
            "信号类型": _translate_signal(ctx.get("signal_type", "none")),
            "有无信号": "是" if ctx.get("has_signal") else "否",
            # AI 信息
            "AI概率": primary.get("probability", 0),
            "AI触发条件": primary.get("trigger", "")[:50] if primary.get("trigger") else "",
            "AI逻辑": primary.get("reasoning", primary.get("logic", ""))[:100] if primary.get("reasoning") or primary.get("logic") else "",
            # 信号质量（新增）
            "信号质量评级": _translate_quality(ai_data.get("signal_quality", {}).get("grade", "unknown")),
            "信号质量得分": ai_data.get("signal_quality", {}).get("total_score", ""),
            "建议动作": _translate_action(ai_data.get("signal_quality", {}).get("action", "")),
        }
        csv_rows.append(csv_row)
    
    # 写入 CSV
    if csv_rows:
        fieldnames = csv_rows[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        
        print(f"[OK] Exported {len(csv_rows)} records to: {filename}")
    else:
        print("[WARN] No valid data")


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
    
    print("[DONE] Query completed.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[WARN] User interrupted.\n")
    except Exception as e:
        print(f"\n\n[ERROR] {e}\n")
        import traceback
        traceback.print_exc()
