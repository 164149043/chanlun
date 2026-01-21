# -*- coding: utf-8 -*-
"""信号质量评分模块

根据多个维度对交易信号进行质量评分（0-100分）：
1. 买卖点类型（可配置权重）
2. 趋势一致性（可配置权重）
3. 价格位置（可配置权重）
4. 力度背驰（可配置权重）
5. 历史胜率（可配置权重）
6. 盈亏比（可配置权重）

评分等级：
- 80-100: 优质信号（建议交易）
- 60-79:  良好信号（可以交易）
- 40-59:  一般信号（谨慎交易）
- 0-39:   低质信号（建议观望）

权重优化：
- 使用 weight_optimizer.py 可自动基于历史数据优化权重
- 优化后的权重保存在 optimized_weights.json
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
        pass

import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from collections import defaultdict

DB_PATH = Path(__file__).parent / "chanlun_ai.db"
WEIGHTS_PATH = Path(__file__).parent / "optimized_weights.json"

# 默认权重（经验值）
DEFAULT_WEIGHTS = {
    "signal_type": 20,
    "trend": 20,
    "position": 15,
    "strength": 15,
    "history": 20,
    "risk_reward": 10,
}


def _load_weights() -> Dict[str, float]:
    """加载权重配置（优先使用优化后的权重）"""
    if WEIGHTS_PATH.exists():
        try:
            with open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            weights = config.get("weights", {})
            if weights:
                return weights
        except Exception:
            pass
    return DEFAULT_WEIGHTS.copy()


# 全局权重配置
WEIGHTS = _load_weights()


# ============================================
# 历史统计缓存
# ============================================

_HISTORY_STATS_CACHE: Dict[str, Dict] = {}


def _load_history_stats() -> Dict[str, Dict]:
    """加载历史统计数据（用于计算历史胜率）"""
    global _HISTORY_STATS_CACHE
    
    if _HISTORY_STATS_CACHE:
        return _HISTORY_STATS_CACHE
    
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            """
            SELECT ai_json, outcome_json, chanlun_json
            FROM analysis_snapshot
            WHERE evaluated = 1 AND outcome_json IS NOT NULL
            """
        ).fetchall()
        conn.close()
        
        # 按信号类型统计
        signal_stats = defaultdict(lambda: {"total": 0, "wins": 0})
        # 按趋势统计
        trend_stats = defaultdict(lambda: {"total": 0, "wins": 0})
        # 按位置统计
        position_stats = defaultdict(lambda: {"total": 0, "wins": 0})
        # 按方向统计
        direction_stats = defaultdict(lambda: {"total": 0, "wins": 0})
        # 按组合统计（信号+方向）
        combo_stats = defaultdict(lambda: {"total": 0, "wins": 0})
        
        for ai_str, outcome_str, chanlun_str in rows:
            try:
                ai = json.loads(ai_str) if ai_str else {}
                outcome = json.loads(outcome_str)
                chanlun = json.loads(chanlun_str) if chanlun_str else {}
                
                hit_target = outcome.get("hit_target", False)
                
                # 获取信号类型
                source = chanlun if chanlun else ai
                signal = source.get("signal", {})
                summary = source.get("structure_summary", {})
                
                buy_sell_points = signal.get("buy_sell_points", [])
                divergences = signal.get("divergences", [])
                trend = summary.get("trend", "unknown")
                position = summary.get("price_position", "unknown")
                
                # 主场景方向
                primary = ai.get("primary_scenario", {})
                direction = primary.get("direction", outcome.get("direction", "unknown"))
                
                # 分类信号
                signal_type = _classify_signal(buy_sell_points, divergences)
                
                # 更新统计
                signal_stats[signal_type]["total"] += 1
                if hit_target:
                    signal_stats[signal_type]["wins"] += 1
                
                trend_stats[trend]["total"] += 1
                if hit_target:
                    trend_stats[trend]["wins"] += 1
                
                position_stats[position]["total"] += 1
                if hit_target:
                    position_stats[position]["wins"] += 1
                
                direction_stats[direction]["total"] += 1
                if hit_target:
                    direction_stats[direction]["wins"] += 1
                
                # 组合统计
                combo_key = f"{signal_type}_{direction}"
                combo_stats[combo_key]["total"] += 1
                if hit_target:
                    combo_stats[combo_key]["wins"] += 1
                    
            except Exception:
                continue
        
        _HISTORY_STATS_CACHE = {
            "signal": dict(signal_stats),
            "trend": dict(trend_stats),
            "position": dict(position_stats),
            "direction": dict(direction_stats),
            "combo": dict(combo_stats),
        }
        
    except Exception:
        _HISTORY_STATS_CACHE = {}
    
    return _HISTORY_STATS_CACHE


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


def _get_win_rate(stats_dict: dict, key: str) -> float:
    """获取历史胜率"""
    if not stats_dict or key not in stats_dict:
        return 0.5  # 无数据时返回中性值
    
    s = stats_dict[key]
    total = s.get("total", 0)
    wins = s.get("wins", 0)
    
    if total < 5:  # 样本太少
        return 0.5
    
    return wins / total


# ============================================
# 评分函数
# ============================================

def score_signal_type(signal_type: str, direction: str, max_score: float = None) -> Tuple[float, str]:
    """评分：买卖点类型
    
    评分逻辑：
    - 方向一致的买卖点得分高
    - 1买/1卖 > 2买/2卖 > 3买/3卖
    - 背驰信号次之
    - 无信号或方向冲突得分低
    """
    if max_score is None:
        max_score = WEIGHTS.get("signal_type", 20)
    
    # 计算得分比例
    if direction == "up":
        if signal_type in ["1buy", "bc_buy"]:
            ratio, reason = 1.0, "一买/底背驰 + 看涨，强买入信号"
        elif signal_type == "2buy":
            ratio, reason = 0.9, "二买 + 看涨，较强买入信号"
        elif signal_type == "3buy":
            ratio, reason = 0.75, "三买 + 看涨，回调买入信号"
        elif signal_type in ["1sell", "2sell", "3sell", "bc_sell"]:
            ratio, reason = 0.25, "卖出信号 + 看涨，方向冲突"
        elif signal_type == "mixed":
            ratio, reason = 0.5, "混合信号 + 看涨"
        else:
            ratio, reason = 0.4, "无明确信号 + 看涨"
    elif direction == "down":
        if signal_type in ["1sell", "bc_sell"]:
            ratio, reason = 1.0, "一卖/顶背驰 + 看跌，强卖出信号"
        elif signal_type == "2sell":
            ratio, reason = 0.9, "二卖 + 看跌，较强卖出信号"
        elif signal_type == "3sell":
            ratio, reason = 0.75, "三卖 + 看跌，反弹卖出信号"
        elif signal_type in ["1buy", "2buy", "3buy", "bc_buy"]:
            ratio, reason = 0.25, "买入信号 + 看跌，方向冲突"
        elif signal_type == "mixed":
            ratio, reason = 0.5, "混合信号 + 看跌"
        else:
            ratio, reason = 0.4, "无明确信号 + 看跌"
    else:
        ratio, reason = 0.5, "震荡方向，信号参考价值有限"
    
    return round(ratio * max_score, 1), reason


def score_trend_consistency(trend: str, direction: str, max_score: float = None) -> Tuple[float, str]:
    """评分：趋势一致性
    
    评分逻辑：
    - 顺势交易得分高
    - 逆势交易得分低
    - 震荡中性
    """
    if max_score is None:
        max_score = WEIGHTS.get("trend", 20)
    
    if direction == "up":
        if trend == "up_trend":
            ratio, reason = 1.0, "上升趋势 + 看涨，顺势做多"
        elif trend == "consolidation":
            ratio, reason = 0.6, "震荡 + 看涨，需等待突破确认"
        elif trend == "down_trend":
            ratio, reason = 0.25, "下降趋势 + 看涨，逆势操作风险高"
        else:
            ratio, reason = 0.5, "趋势未知"
    elif direction == "down":
        if trend == "down_trend":
            ratio, reason = 1.0, "下降趋势 + 看跌，顺势做空"
        elif trend == "consolidation":
            ratio, reason = 0.6, "震荡 + 看跌，需等待破位确认"
        elif trend == "up_trend":
            ratio, reason = 0.25, "上升趋势 + 看跌，逆势操作风险高"
        else:
            ratio, reason = 0.5, "趋势未知"
    else:
        if trend == "consolidation":
            ratio, reason = 0.75, "震荡行情，高抛低吸策略"
        else:
            ratio, reason = 0.5, "方向不明确"
    
    return round(ratio * max_score, 1), reason


def score_price_position(position: str, direction: str, max_score: float = None) -> Tuple[float, str]:
    """评分：价格位置
    
    评分逻辑：
    - 中枢下方做多 / 中枢上方做空 得分高（有空间）
    - 中枢内部得分中等
    - 中枢上方做多 / 中枢下方做空 得分低（空间有限）
    """
    if max_score is None:
        max_score = WEIGHTS.get("position", 15)
    
    if direction == "up":
        if position == "below_zs":
            ratio, reason = 1.0, "价格在中枢下方，做多空间充足"
        elif position == "inside_zs":
            ratio, reason = 0.8, "价格在中枢内部，等待方向选择"
        elif position == "above_zs":
            ratio, reason = 0.53, "价格在中枢上方，追涨风险"
        else:
            ratio, reason = 0.67, "位置未知"
    elif direction == "down":
        if position == "above_zs":
            ratio, reason = 1.0, "价格在中枢上方，做空空间充足"
        elif position == "inside_zs":
            ratio, reason = 0.8, "价格在中枢内部，等待方向选择"
        elif position == "below_zs":
            ratio, reason = 0.53, "价格在中枢下方，追跌风险"
        else:
            ratio, reason = 0.67, "位置未知"
    else:
        if position == "inside_zs":
            ratio, reason = 1.0, "价格在中枢内部，震荡策略有效"
        else:
            ratio, reason = 0.67, "价格远离中枢"
    
    return round(ratio * max_score, 1), reason


def score_strength_divergence(strength: str, has_divergence: bool, direction: str, max_score: float = None) -> Tuple[float, str]:
    """评分：力度背驰
    
    评分逻辑：
    - 力度衰竭 + 反向操作 得分高
    - 有背驰信号加分
    - 力度增强但逆势操作扣分
    """
    if max_score is None:
        max_score = WEIGHTS.get("strength", 15)
    
    base_ratio = 0.47
    reason_parts = []
    
    # 力度评估
    if strength == "weakening":
        if direction in ["up", "down"]:
            base_ratio = 0.8
            reason_parts.append("力度衰竭")
    elif strength == "strengthening":
        if direction in ["up", "down"]:
            base_ratio = 0.67
            reason_parts.append("力度增强")
    elif strength == "similar":
        reason_parts.append("力度相近")
    else:
        reason_parts.append("力度未知")
    
    # 背驰加分
    if has_divergence:
        base_ratio = min(1.0, base_ratio + 0.2)
        reason_parts.append("存在背驰信号")
    
    return round(base_ratio * max_score, 1), "，".join(reason_parts) if reason_parts else "力度正常"


def score_history_winrate(signal_type: str, direction: str, max_score: float = None) -> Tuple[float, str]:
    """评分：历史胜率
    
    评分逻辑：
    - 基于历史数据的同类信号胜率
    - 组合胜率（信号+方向）权重更高
    """
    if max_score is None:
        max_score = WEIGHTS.get("history", 20)
    
    stats = _load_history_stats()
    
    if not stats:
        return round(0.5 * max_score, 1), "历史数据不足"
    
    # 获取组合胜率
    combo_key = f"{signal_type}_{direction}"
    combo_stats = stats.get("combo", {})
    combo_wr = _get_win_rate(combo_stats, combo_key)
    
    # 获取信号胜率
    signal_stats = stats.get("signal", {})
    signal_wr = _get_win_rate(signal_stats, signal_type)
    
    # 加权平均（组合权重60%，信号权重40%）
    avg_wr = combo_wr * 0.6 + signal_wr * 0.4
    
    # 映射到分数（胜率作为比例）
    score = avg_wr * max_score
    
    # 获取样本数
    combo_total = combo_stats.get(combo_key, {}).get("total", 0)
    
    if combo_total < 5:
        reason = f"样本不足({combo_total}条)，历史胜率参考有限"
    elif avg_wr >= 0.5:
        reason = f"历史胜率{avg_wr*100:.1f}%（{combo_total}条样本），表现良好"
    elif avg_wr >= 0.3:
        reason = f"历史胜率{avg_wr*100:.1f}%（{combo_total}条样本），表现一般"
    else:
        reason = f"历史胜率{avg_wr*100:.1f}%（{combo_total}条样本），表现较差"
    
    return round(score, 1), reason


def score_volatility(target_pct: float, stop_pct: float, max_score: float = None) -> Tuple[float, str]:
    """评分：盈亏比合理性
    
    评分逻辑：
    - 盈亏比（目标/止损）>= 2 得高分
    - 盈亏比 1-2 中等
    - 盈亏比 < 1 低分
    """
    if max_score is None:
        max_score = WEIGHTS.get("risk_reward", 10)
    
    if stop_pct <= 0:
        return round(0.5 * max_score, 1), "止损参数异常"
    
    rr_ratio = target_pct / stop_pct
    
    if rr_ratio >= 3:
        ratio, reason = 1.0, f"盈亏比 {rr_ratio:.1f}:1，风险收益极佳"
    elif rr_ratio >= 2:
        ratio, reason = 0.8, f"盈亏比 {rr_ratio:.1f}:1，风险收益良好"
    elif rr_ratio >= 1.5:
        ratio, reason = 0.6, f"盈亏比 {rr_ratio:.1f}:1，风险收益一般"
    elif rr_ratio >= 1:
        ratio, reason = 0.4, f"盈亏比 {rr_ratio:.1f}:1，风险收益较差"
    else:
        ratio, reason = 0.2, f"盈亏比 {rr_ratio:.1f}:1，风险大于收益"
    
    return round(ratio * max_score, 1), reason


# ============================================
# 综合评分
# ============================================

def calculate_signal_quality(
    chanlun_json: Dict[str, Any],
    ai_json: Dict[str, Any],
) -> Dict[str, Any]:
    """计算信号质量综合评分
    
    参数：
    - chanlun_json: 缠论结构 JSON（来自 exporter）
    - ai_json: AI 输出 JSON
    
    返回：
    - dict: 包含总分、各维度得分、评级、建议
    """
    # 提取数据
    source = chanlun_json if chanlun_json else ai_json
    
    signal = source.get("signal", {})
    summary = source.get("structure_summary", {})
    
    buy_sell_points = signal.get("buy_sell_points", [])
    divergences = signal.get("divergences", [])
    trend = summary.get("trend", "unknown")
    position = summary.get("price_position", "unknown")
    strength = summary.get("strength_comparison", "unknown")
    
    # 从 AI 输出获取
    primary = ai_json.get("primary_scenario", {})
    direction = primary.get("direction", "unknown")
    target_pct = primary.get("target_pct", 2.0)
    stop_pct = primary.get("stop_pct", 1.5)
    
    # 分类信号
    signal_type = _classify_signal(buy_sell_points, divergences)
    has_divergence = bool(divergences)
    
    # 加载当前权重配置
    weights = WEIGHTS
    
    # 计算各维度得分
    scores = {}
    reasons = {}
    max_scores = {}
    
    # 1. 信号类型
    max_scores["signal_type"] = weights.get("signal_type", 20)
    s1, r1 = score_signal_type(signal_type, direction, max_scores["signal_type"])
    scores["signal_type"] = s1
    reasons["signal_type"] = r1
    
    # 2. 趋势一致性
    max_scores["trend"] = weights.get("trend", 20)
    s2, r2 = score_trend_consistency(trend, direction, max_scores["trend"])
    scores["trend"] = s2
    reasons["trend"] = r2
    
    # 3. 价格位置
    max_scores["position"] = weights.get("position", 15)
    s3, r3 = score_price_position(position, direction, max_scores["position"])
    scores["position"] = s3
    reasons["position"] = r3
    
    # 4. 力度背驰
    max_scores["strength"] = weights.get("strength", 15)
    s4, r4 = score_strength_divergence(strength, has_divergence, direction, max_scores["strength"])
    scores["strength"] = s4
    reasons["strength"] = r4
    
    # 5. 历史胜率
    max_scores["history"] = weights.get("history", 20)
    s5, r5 = score_history_winrate(signal_type, direction, max_scores["history"])
    scores["history"] = s5
    reasons["history"] = r5
    
    # 6. 盈亏比
    max_scores["risk_reward"] = weights.get("risk_reward", 10)
    s6, r6 = score_volatility(target_pct, stop_pct, max_scores["risk_reward"])
    scores["risk_reward"] = s6
    reasons["risk_reward"] = r6
    
    # 计算总分
    total_score = sum(scores.values())
    
    # 评级
    if total_score >= 80:
        grade = "A"
        grade_name = "优质信号"
        action = "trade"
        action_name = "建议交易"
    elif total_score >= 60:
        grade = "B"
        grade_name = "良好信号"
        action = "trade"
        action_name = "可以交易"
    elif total_score >= 40:
        grade = "C"
        grade_name = "一般信号"
        action = "wait"
        action_name = "谨慎观望"
    else:
        grade = "D"
        grade_name = "低质信号"
        action = "skip"
        action_name = "建议放弃"
    
    # 生成建议
    advice_parts = []
    
    # 找出得分最高和最低的维度
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_dim = sorted_scores[0]
    worst_dim = sorted_scores[-1]
    
    dim_names = {
        "signal_type": "信号类型",
        "trend": "趋势一致性",
        "position": "价格位置",
        "strength": "力度背驰",
        "history": "历史胜率",
        "risk_reward": "盈亏比",
    }
    
    advice_parts.append(f"优势: {dim_names[best_dim[0]]}({best_dim[1]}分)")
    if worst_dim[1] < 10:
        advice_parts.append(f"风险: {dim_names[worst_dim[0]]}({worst_dim[1]}分)")
    
    return {
        "total_score": round(total_score, 1),
        "grade": grade,
        "grade_name": grade_name,
        "action": action,
        "action_name": action_name,
        "scores": scores,
        "max_scores": max_scores,
        "reasons": reasons,
        "advice": "；".join(advice_parts),
        "signal_type": signal_type,
        "direction": direction,
        "weights_optimized": WEIGHTS_PATH.exists(),
    }


def format_quality_report(quality: Dict[str, Any]) -> str:
    """格式化质量评分报告（用于终端输出）"""
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  信号质量评分")
    lines.append("=" * 60)
    
    # 总分和评级
    total = quality["total_score"]
    grade = quality["grade"]
    grade_name = quality["grade_name"]
    action_name = quality["action_name"]
    
    lines.append(f"\n  总分: {total}/100  评级: {grade} ({grade_name})")
    lines.append(f"  建议: {action_name}")
    
    # 各维度得分
    lines.append("\n  【各维度得分】")
    lines.append("-" * 60)
    
    # 使用动态权重
    weights = WEIGHTS
    dim_names = {
        "signal_type": "信号类型",
        "trend": "趋势一致性",
        "position": "价格位置",
        "strength": "力度背驰",
        "history": "历史胜率",
        "risk_reward": "盈亏比",
    }
    
    scores = quality["scores"]
    reasons = quality["reasons"]
    
    for key, name in dim_names.items():
        max_score = weights.get(key, 10)
        score = scores.get(key, 0)
        reason = reasons.get(key, "")
        bar_len = int(score / max_score * 10) if max_score > 0 else 0
        bar = "#" * bar_len + "-" * (10 - bar_len)
        lines.append(f"  {name:<10} [{bar}] {score:>5.1f}/{max_score:.0f}")
        if reason:
            lines.append(f"              {reason}")
    
    # 综合建议
    lines.append("\n  【综合分析】")
    lines.append("-" * 60)
    lines.append(f"  {quality['advice']}")
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)


# ============================================
# 主函数（测试用）
# ============================================

def main():
    """测试信号质量评分"""
    # 模拟数据
    chanlun_json = {
        "signal": {
            "buy_sell_points": ["1sell"],
            "divergences": ["bi"],
        },
        "structure_summary": {
            "trend": "consolidation",
            "price_position": "above_zs",
            "strength_comparison": "similar",
        }
    }
    
    ai_json = {
        "primary_scenario": {
            "direction": "down",
            "target_pct": 2.5,
            "stop_pct": 1.5,
            "probability": 0.4,
        }
    }
    
    quality = calculate_signal_quality(chanlun_json, ai_json)
    report = format_quality_report(quality)
    print(report)
    
    print("\n完整质量数据:")
    print(json.dumps(quality, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
