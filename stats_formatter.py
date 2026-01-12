"""统计数据格式化模块

用途：
- 将 query_stats.py 的统计数据格式化为适合 AI 理解的文本
- 提供简洁、关键的历史表现信息
"""
from typing import Dict, Any, Optional


def format_stats_for_prompt(stats: Dict[str, Any], symbol: str, interval: str) -> str:
    """将统计数据格式化为 Prompt 片段
    
    参数：
    - stats: calculate_accuracy() 返回的统计字典
    - symbol: 当前分析的交易对（如 BTC/USDT）
    - interval: 当前分析的周期（如 1h）
    
    返回：
    - 格式化的统计文本
    """
    if not stats or stats.get("total", 0) == 0:
        return """
【系统历史表现】
暂无历史评估数据，这是系统首次运行。
"""
    
    total = stats["total"]
    hit_count = stats["hit_count"]
    avg_score = stats.get("avg_score", 0)
    accuracy = (hit_count / total * 100) if total > 0 else 0
    
    # 构建基础统计
    output = f"""
【系统历史表现】
总评估次数：{total} 次
整体命中率：{accuracy:.1f}% (命中 {hit_count}/{total})
平均得分：{avg_score:.2f} / 1.0

"""
    
    # 按方向统计
    direction_stats = _format_direction_stats(stats.get("by_direction", []))
    if direction_stats:
        output += direction_stats + "\n"
    
    # 当前交易对的表现
    symbol_stats = _format_symbol_stats(stats.get("by_symbol", []), symbol)
    if symbol_stats:
        output += symbol_stats + "\n"
    
    # 当前周期的表现
    interval_stats = _format_interval_stats(stats.get("by_interval", []), interval)
    if interval_stats:
        output += interval_stats + "\n"
    
    # 结果类型分布
    outcome_stats = _format_outcome_stats(stats.get("by_outcome", []), total)
    if outcome_stats:
        output += outcome_stats + "\n"
    
    # AI 调整建议
    suggestions = _generate_suggestions(stats, symbol, interval)
    if suggestions:
        output += suggestions
    
    return output


def _format_direction_stats(by_direction: list) -> str:
    """格式化方向统计"""
    if not by_direction:
        return ""
    
    output = "按方向统计：\n"
    for direction, total_dir, hit_dir, avg_score_dir in by_direction:
        acc_dir = (hit_dir / total_dir * 100) if total_dir > 0 else 0
        direction_name = {"up": "看涨", "down": "看跌", "unknown": "未知"}.get(direction, direction)
        
        # 添加表现评级
        if acc_dir >= 50:
            rating = "✅ 表现良好"
        elif acc_dir >= 30:
            rating = "⚠️ 表现一般"
        else:
            rating = "❌ 表现不佳"
        
        output += f"  {direction_name}：{acc_dir:.1f}% ({hit_dir}/{total_dir}) | 得分 {avg_score_dir:.2f} | {rating}\n"
    
    return output


def _format_symbol_stats(by_symbol: list, current_symbol: str) -> str:
    """格式化交易对统计（重点关注当前交易对）"""
    if not by_symbol:
        return ""
    
    # 查找当前交易对的数据
    current_stats = None
    for symbol, total_sym, hit_sym, avg_score_sym in by_symbol:
        if symbol == current_symbol:
            current_stats = (symbol, total_sym, hit_sym, avg_score_sym)
            break
    
    if not current_stats:
        return f"当前交易对 {current_symbol}：暂无历史数据\n"
    
    symbol, total_sym, hit_sym, avg_score_sym = current_stats
    acc_sym = (hit_sym / total_sym * 100) if total_sym > 0 else 0
    
    # 表现评级
    if acc_sym >= 50:
        rating = "✅ 表现良好"
    elif acc_sym >= 30:
        rating = "⚠️ 表现一般"
    else:
        rating = "❌ 表现不佳"
    
    return f"当前交易对 {symbol}：{acc_sym:.1f}% ({hit_sym}/{total_sym}) | 得分 {avg_score_sym:.2f} | {rating}\n"


def _format_interval_stats(by_interval: list, current_interval: str) -> str:
    """格式化周期统计（重点关注当前周期）"""
    if not by_interval:
        return ""
    
    # 查找当前周期的数据
    current_stats = None
    for interval, total_int, hit_int, avg_score_int in by_interval:
        if interval == current_interval:
            current_stats = (interval, total_int, hit_int, avg_score_int)
            break
    
    if not current_stats:
        return f"当前周期 {current_interval}：暂无历史数据\n"
    
    interval, total_int, hit_int, avg_score_int = current_stats
    acc_int = (hit_int / total_int * 100) if total_int > 0 else 0
    
    # 表现评级
    if acc_int >= 50:
        rating = "✅ 表现良好"
    elif acc_int >= 30:
        rating = "⚠️ 表现一般"
    else:
        rating = "❌ 表现不佳"
    
    return f"当前周期 {interval}：{acc_int:.1f}% ({hit_int}/{total_int}) | 得分 {avg_score_int:.2f} | {rating}\n"


def _format_outcome_stats(by_outcome: list, total: int) -> str:
    """格式化结果类型分布"""
    if not by_outcome:
        return ""
    
    output = "结果类型分布：\n"
    outcome_names = {
        "success": "✓ 成功（命中目标）",
        "partial": "≈ 部分正确（方向对但未达目标）",
        "stopped": "⊗ 止损出局",
        "failed": "✗ 失败（方向错误）",
        "unknown": "? 未知",
        "no_direction": "- 无方向"
    }
    
    for outcome_type, count in sorted(by_outcome, key=lambda x: x[1], reverse=True):
        percentage = (count / total * 100) if total > 0 else 0
        name = outcome_names.get(outcome_type, outcome_type)
        output += f"  {name}: {count} 次 ({percentage:.1f}%)\n"
    
    return output


def _generate_suggestions(stats: Dict[str, Any], symbol: str, interval: str) -> str:
    """根据统计数据生成 AI 调整建议"""
    suggestions = ["【AI 调整建议】"]
    
    # 分析方向表现
    by_direction = {d[0]: (d[2], d[1], d[3]) for d in stats.get("by_direction", [])}
    
    if "up" in by_direction:
        up_hit, up_total, up_score = by_direction["up"]
        up_acc = (up_hit / up_total * 100) if up_total > 0 else 0
        if up_acc < 20:
            suggestions.append("1. 看涨预测历史表现不佳，建议：")
            suggestions.append("   - 降低看涨目标预期（减少 20-30%）")
            suggestions.append("   - 提高看涨的触发门槛")
            suggestions.append("   - 增加止损保护幅度")
    
    if "down" in by_direction:
        down_hit, down_total, down_score = by_direction["down"]
        down_acc = (down_hit / down_total * 100) if down_total > 0 else 0
        if down_acc > 50:
            suggestions.append("2. 看跌预测历史表现良好，可适当提高信心度")
    
    # 分析交易对表现
    by_symbol_dict = {s[0]: (s[2], s[1], s[3]) for s in stats.get("by_symbol", [])}
    if symbol in by_symbol_dict:
        sym_hit, sym_total, sym_score = by_symbol_dict[symbol]
        sym_acc = (sym_hit / sym_total * 100) if sym_total > 0 else 0
        if sym_acc < 20:
            suggestions.append(f"3. {symbol} 历史准确率较低，建议采用更保守的策略")
    
    # 分析整体得分
    avg_score = stats.get("avg_score", 0)
    if avg_score < 0.3:
        suggestions.append("4. 整体得分偏低，建议：")
        suggestions.append("   - 优先关注高概率、小幅度的机会")
        suggestions.append("   - 严格设置止损，避免大幅亏损")
    
    if len(suggestions) == 1:
        return ""  # 没有具体建议
    
    return "\n".join(suggestions) + "\n"


def get_stats_summary(stats: Dict[str, Any]) -> Dict[str, Any]:
    """获取统计数据的简化摘要（用于系统校验）
    
    参数：
    - stats: calculate_accuracy() 返回的统计字典
    
    返回：
    - 简化的统计摘要字典
    """
    if not stats or stats.get("total", 0) == 0:
        return {
            "has_data": False,
            "total": 0,
            "accuracy": 0,
            "avg_score": 0
        }
    
    total = stats["total"]
    hit_count = stats["hit_count"]
    avg_score = stats.get("avg_score", 0)
    accuracy = (hit_count / total * 100) if total > 0 else 0
    
    # 提取方向、交易对、周期的表现
    by_direction = {d[0]: {"acc": (d[2]/d[1]*100) if d[1] > 0 else 0, "score": d[3]} 
                    for d in stats.get("by_direction", [])}
    by_symbol = {s[0]: {"acc": (s[2]/s[1]*100) if s[1] > 0 else 0, "score": s[3]} 
                 for s in stats.get("by_symbol", [])}
    by_interval = {i[0]: {"acc": (i[2]/i[1]*100) if i[1] > 0 else 0, "score": i[3]} 
                   for i in stats.get("by_interval", [])}
    
    return {
        "has_data": True,
        "total": total,
        "accuracy": accuracy,
        "avg_score": avg_score,
        "by_direction": by_direction,
        "by_symbol": by_symbol,
        "by_interval": by_interval
    }
