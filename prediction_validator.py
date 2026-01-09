"""预测校验模块

用途：
- 对 AI 输出的预测进行二次校验
- 根据历史统计数据自动调整预测参数
- 生成警告信息
"""
from typing import Dict, Any, List, Tuple


def validate_prediction(
    ai_output: Dict[str, Any],
    stats_summary: Dict[str, Any],
    symbol: str,
    interval: str
) -> Tuple[Dict[str, Any], List[str]]:
    """校验并调整 AI 预测
    
    参数：
    - ai_output: AI 输出的预测 JSON
    - stats_summary: 统计数据摘要（来自 get_stats_summary）
    - symbol: 交易对
    - interval: 周期
    
    返回：
    - (调整后的 ai_output, 警告列表)
    """
    warnings = []
    
    # 如果没有历史数据，跳过校验
    if not stats_summary.get("has_data"):
        return ai_output, warnings
    
    # 提取 primary_scenario
    primary = ai_output.get("primary_scenario", {})
    if not primary:
        return ai_output, warnings
    
    direction = primary.get("direction", "unknown")
    target_pct = primary.get("target_pct", 0)
    stop_pct = primary.get("stop_pct", 0)
    confidence = primary.get("confidence", "medium")
    
    # 规则 1：看涨预测历史成功率低
    if direction == "up":
        up_stats = stats_summary.get("by_direction", {}).get("up", {})
        up_acc = up_stats.get("acc", 0)
        
        if up_acc < 10:
            warnings.append("⚠️ 看涨预测历史成功率低于 10%，建议谨慎")
            # 降低目标
            if target_pct > 2.0:
                old_target = target_pct
                primary["target_pct"] = target_pct * 0.7  # 降低 30%
                warnings.append(f"   → 自动调整：目标从 {old_target:.1f}% 降至 {primary['target_pct']:.1f}%")
            
            # 降低信心度
            if confidence in ["high", "very_high"]:
                primary["confidence"] = "medium"
                warnings.append("   → 自动调整：信心度降低至 medium")
        
        elif up_acc < 30:
            warnings.append("⚠️ 看涨预测历史成功率偏低，已进行适度调整")
            if target_pct > 3.0:
                old_target = target_pct
                primary["target_pct"] = target_pct * 0.85  # 降低 15%
                warnings.append(f"   → 自动调整：目标从 {old_target:.1f}% 降至 {primary['target_pct']:.1f}%")
    
    # 规则 2：看跌预测历史表现良好
    elif direction == "down":
        down_stats = stats_summary.get("by_direction", {}).get("down", {})
        down_acc = down_stats.get("acc", 0)
        
        if down_acc > 50:
            warnings.append("✅ 看跌预测历史表现良好，当前预测可信度较高")
    
    # 规则 3：交易对历史表现差
    symbol_stats = stats_summary.get("by_symbol", {}).get(symbol, {})
    symbol_acc = symbol_stats.get("acc", 0)
    
    if symbol_acc < 10 and symbol_acc > 0:
        warnings.append(f"⚠️ {symbol} 历史成功率低于 10%，建议采用保守策略")
        
        # 降低目标
        if target_pct > 2.0:
            old_target = target_pct
            primary["target_pct"] = max(1.5, target_pct * 0.75)  # 降低 25%，最低 1.5%
            warnings.append(f"   → 自动调整：目标从 {old_target:.1f}% 降至 {primary['target_pct']:.1f}%")
        
        # 扩大止损
        if stop_pct < target_pct * 0.5:
            old_stop = stop_pct
            primary["stop_pct"] = target_pct * 0.6  # 止损设为目标的 60%
            warnings.append(f"   → 自动调整：止损从 {old_stop:.1f}% 扩大至 {primary['stop_pct']:.1f}%")
    
    # 规则 4：整体得分过低
    avg_score = stats_summary.get("avg_score", 0)
    if avg_score < 0.25:
        warnings.append("⚠️ 系统整体得分偏低，建议采用更保守的参数")
        
        # 全面调整
        if target_pct > 2.5:
            old_target = target_pct
            primary["target_pct"] = 2.0
            warnings.append(f"   → 自动调整：目标统一调整为 {primary['target_pct']:.1f}%")
        
        if stop_pct < 1.5:
            primary["stop_pct"] = 1.5
            warnings.append(f"   → 自动调整：止损统一调整为 {primary['stop_pct']:.1f}%")
    
    # 规则 5：目标与止损比例不合理
    if stop_pct > 0 and target_pct / stop_pct < 1.2:
        warnings.append("⚠️ 风险收益比不合理（止损过大相对目标）")
        old_stop = stop_pct
        primary["stop_pct"] = target_pct * 0.5  # 调整为目标的 50%
        warnings.append(f"   → 自动调整：止损从 {old_stop:.1f}% 调整至 {primary['stop_pct']:.1f}%")
    
    # 规则 6：目标过高警告
    if interval == "1h" and target_pct > 4.0:
        warnings.append(f"⚠️ 1h 周期目标 {target_pct:.1f}% 过高，建议不超过 3-4%")
    elif interval == "4h" and target_pct > 8.0:
        warnings.append(f"⚠️ 4h 周期目标 {target_pct:.1f}% 过高，建议不超过 6-8%")
    
    # 更新回 ai_output
    ai_output["primary_scenario"] = primary
    
    return ai_output, warnings


def get_adjustment_summary(warnings: List[str]) -> str:
    """生成调整摘要文本
    
    参数：
    - warnings: 警告列表
    
    返回：
    - 格式化的摘要文本
    """
    if not warnings:
        return "✅ 预测参数合理，无需调整"
    
    output = ["📋 预测校验与调整："]
    output.extend([f"  {w}" for w in warnings])
    
    return "\n".join(output)


def should_skip_prediction(stats_summary: Dict[str, Any], symbol: str, direction: str) -> Tuple[bool, str]:
    """判断是否应该跳过当前预测（极端情况）
    
    参数：
    - stats_summary: 统计摘要
    - symbol: 交易对
    - direction: 预测方向
    
    返回：
    - (是否跳过, 原因说明)
    """
    # 如果没有历史数据，不跳过
    if not stats_summary.get("has_data"):
        return False, ""
    
    # 检查该方向的历史表现
    dir_stats = stats_summary.get("by_direction", {}).get(direction, {})
    dir_acc = dir_stats.get("acc", 0)
    
    # 如果某个方向的成功率持续为 0，且样本数 >= 30，建议跳过
    total = stats_summary.get("total", 0)
    if dir_acc == 0 and total >= 30:
        return True, f"该方向（{direction}）历史成功率为 0%（样本数 {total}），建议暂停预测"
    
    # 检查交易对表现
    symbol_stats = stats_summary.get("by_symbol", {}).get(symbol, {})
    symbol_acc = symbol_stats.get("acc", 0)
    
    if symbol_acc == 0 and total >= 20:
        return True, f"{symbol} 历史成功率为 0%（样本数 {total}），建议暂停该交易对预测"
    
    return False, ""


def apply_conservative_mode(ai_output: Dict[str, Any]) -> Dict[str, Any]:
    """应用保守模式（极端降低风险）
    
    参数：
    - ai_output: AI 输出
    
    返回：
    - 调整后的输出
    """
    primary = ai_output.get("primary_scenario", {})
    
    # 降低目标到最小值
    primary["target_pct"] = 1.5
    primary["stop_pct"] = 1.0
    primary["confidence"] = "low"
    
    # 添加保守模式标记
    primary["note"] = "⚠️ 保守模式：基于历史表现，系统自动采用最小风险参数"
    
    ai_output["primary_scenario"] = primary
    
    return ai_output
