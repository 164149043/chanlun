# -*- coding: utf-8 -*-
"""状态机转换器 (State Machine Converter)

将 AI 输出的"多场景并列模式"转换为"状态机模式"

功能：
1. 选择概率最高的场景作为 active_strategy
2. 其他场景作为 standby_strategies
3. 根据 primary_scenario.direction 确定状态
4. 根据 confidence_constraint 确定风险等级

版本：v2.0
"""
from typing import Dict, Any, List, Optional


# 状态常量
STATE_STRATEGY_ACTIVE = "STRATEGY_ACTIVE"
STATE_WAIT_CONFIRMATION = "WAIT_CONFIRMATION"
STATE_OBSERVE_ONLY = "OBSERVE_ONLY"

# 策略状态常量
STATUS_WAIT = "WAIT"
STATUS_READY = "READY"
STATUS_ACTIVE = "ACTIVE"
STATUS_INVALIDATED = "INVALIDATED"

# 风险等级
RISK_NORMAL = "NORMAL"
RISK_CAUTION = "CAUTION"
RISK_HIGH_RISK = "HIGH_RISK"


def scenarios_to_state_machine(
    ai_output: Dict[str, Any],
    current_price: float,
    historical_winrate: Optional[float] = None,
    similar_case_winrate: Optional[float] = None
) -> Dict[str, Any]:
    """
    将多场景模式转换为状态机模式

    参数：
    - ai_output: AI 输出的 JSON（包含 scenarios 和 primary_scenario）
    - current_price: 当前价格
    - historical_winrate: 历史胜率（可选，用于确定风险等级）
    - similar_case_winrate: 相似案例胜率（可选）

    返回：
    - 状态机格式的字典
    """
    scenarios = ai_output.get("scenarios", [])
    primary = ai_output.get("primary_scenario", {})
    structure = ai_output.get("structure_judgement", {})
    signals = ai_output.get("signals", {})

    # 如果没有场景，返回观察状态
    if not scenarios:
        return {
            "current_state": STATE_OBSERVE_ONLY,
            "active_strategy": None,
            "invalidation": {},
            "standby_strategies": []
        }

    # 按概率排序，选择主策略
    sorted_scenarios = sorted(scenarios, key=lambda x: x.get("probability", 0), reverse=True)
    main_scenario = sorted_scenarios[0]

    # 确定当前状态（基于历史胜率和信号）
    current_state = _determine_state(
        primary,
        structure,
        signals,
        historical_winrate,
        similar_case_winrate
    )

    # 构建激活策略
    active_strategy = _build_active_strategy(main_scenario, current_price, current_state)

    # 构建备用策略
    standby_strategies = _build_standby_strategies(sorted_scenarios[1:])

    # 构建否决条件
    invalidation = _build_invalidation(main_scenario, structure, current_state)

    return {
        "current_state": current_state,
        "active_strategy": active_strategy,
        "invalidation": invalidation,
        "standby_strategies": standby_strategies
    }


def _determine_state(
    primary: Dict[str, Any],
    structure: Dict[str, Any],
    signals: Dict[str, Any],
    historical_winrate: Optional[float] = None,
    similar_case_winrate: Optional[float] = None
) -> str:
    """
    确定当前状态

    规则：
    1. 历史胜率 < 30% 或 相似案例胜率 = 0% → OBSERVE_ONLY
    2. 有买入信号但主方向是做空 → WAIT_CONFIRMATION
    3. 其他 → STRATEGY_ACTIVE
    """
    # 检查历史胜率
    if historical_winrate is not None and historical_winrate < 0.25:
        return STATE_OBSERVE_ONLY

    if similar_case_winrate is not None and similar_case_winrate == 0:
        return STATE_OBSERVE_ONLY

    # 检查方向与信号冲突
    buy_sell_points = signals.get("buy_sell_points", [])
    primary_direction = primary.get("direction", "")

    has_buy_signal = any("buy" in s.lower() for s in buy_sell_points)
    has_sell_signal = any("sell" in s.lower() for s in buy_sell_points)

    if primary_direction == "down" and has_buy_signal and not has_sell_signal:
        return STATE_WAIT_CONFIRMATION
    elif primary_direction == "up" and has_sell_signal and not has_buy_signal:
        return STATE_WAIT_CONFIRMATION

    # 检查价格位置
    price_position = structure.get("price_position", "")
    if price_position == "inside_zs":
        # 价格在中枢内部，需要等待确认
        return STATE_WAIT_CONFIRMATION

    return STATE_STRATEGY_ACTIVE


def _build_active_strategy(
    scenario: Dict[str, Any],
    current_price: float,
    current_state: str
) -> Dict[str, Any]:
    """
    构建激活策略

    从 scenario 中提取信息，构建 active_strategy 结构
    """
    direction = scenario.get("direction", "up")
    trigger = scenario.get("trigger", "")
    target_range = scenario.get("target_range", [])
    entry_range = scenario.get("entry_range", [])

    # 确定策略状态
    if current_state == STATE_OBSERVE_ONLY:
        status = STATUS_INVALIDATED
    elif current_state == STATE_WAIT_CONFIRMATION:
        status = STATUS_WAIT
    else:
        status = STATUS_READY

    # 构建入场门槛
    entry_gate = {
        "price_zone": _ensure_entry_zone(entry_range, current_price, direction),
        "structure_required": _extract_structure_conditions(trigger, direction)
    }

    # 计算执行参数
    execution = _build_execution_params(target_range, entry_range, current_price, direction)

    return {
        "direction": direction,
        "status": status,
        "entry_gate": entry_gate,
        "execution": execution
    }


def _ensure_entry_zone(
    entry_range: List[float],
    current_price: float,
    direction: str
) -> List[float]:
    """
    确保入场区间存在且合理

    如果 AI 没有提供 entry_range，根据当前价格和方向生成默认区间
    """
    if entry_range and len(entry_range) == 2:
        low, high = entry_range
        if low <= high:
            return [low, high]

    # 生成默认入场区间（当前价 ±1%）
    if direction == "up":
        return [current_price * 0.99, current_price * 1.005]
    elif direction == "down":
        return [current_price * 0.995, current_price * 1.01]
    else:  # range
        return [current_price * 0.99, current_price * 1.01]


def _extract_structure_conditions(trigger: str, direction: str) -> List[str]:
    """
    从 trigger 中提取结构触发条件

    如果 trigger 为空或太泛，根据方向生成默认条件
    """
    conditions = []

    if trigger:
        # 将 trigger 拆分为条件列表
        # 常见触发词：突破、回踩、不破、站回、跌破等
        if "突破" in trigger or "站回" in trigger:
            conditions.append(f"price_break_{direction == 'up' and 'resistance' or 'support'}")
        if "回踩" in trigger or "不破" in trigger:
            conditions.append("price_hold_support")

        # 默认添加原 trigger
        if len(conditions) == 0:
            conditions.append(trigger)
    else:
        # 根据 direction 生成默认条件
        if direction == "up":
            conditions = [
                "price_hold_dd",
                "15m_break_zd",
                "no_new_down_bi"
            ]
        elif direction == "down":
            conditions = [
                "price_reject_zg",
                "15m_fail_break_zd",
                "no_new_up_bi"
            ]
        else:
            conditions = [
                "price_range_bound",
                "low_volatility"
            ]

    return conditions


def _build_execution_params(
    target_range: List[float],
    entry_range: List[float],
    current_price: float,
    direction: str
) -> Dict[str, Any]:
    """
    构建执行参数（止损、目标、盈亏比）
    """
    if target_range and len(target_range) == 2:
        tgt_low, tgt_high = target_range
        if direction == "up":
            stop_loss = min(tgt_low, current_price * 0.98)
            target = tgt_high
        else:
            stop_loss = max(tgt_high, current_price * 1.02)
            target = tgt_low
    else:
        # 默认参数
        if direction == "up":
            stop_loss = current_price * 0.985
            target = current_price * 1.02
        else:
            stop_loss = current_price * 1.015
            target = current_price * 0.98

    # 计算盈亏比
    if direction == "up":
        rr = (target - current_price) / (current_price - stop_loss) if stop_loss < current_price else 1.0
    else:
        rr = (current_price - target) / (stop_loss - current_price) if stop_loss > current_price else 1.0

    return {
        "entry_type": "split",  # 分批入场
        "stop_loss": round(stop_loss, 2),
        "target": round(target, 2),
        "rr": round(rr, 2)
    }


def _build_standby_strategies(scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    构建备用策略列表

    将其他场景转换为 standby_strategies
    """
    standby = []

    for scenario in scenarios[:3]:  # 最多保留3个备用策略
        direction = scenario.get("direction", "")
        trigger = scenario.get("trigger", "")

        standby.append({
            "direction": direction,
            "activate_if": _build_activate_conditions(trigger, direction)
        })

    return standby


def _build_activate_conditions(trigger: str, direction: str) -> List[str]:
    """
    构建激活条件（用于备用策略）
    """
    conditions = []

    if trigger:
        conditions.append(trigger)
    else:
        if direction == "up":
            conditions = ["price_break_resistance", "volume_confirm"]
        elif direction == "down":
            conditions = ["price_break_support", "volume_confirm"]
        else:
            conditions = ["price_enter_range", "volatility_drop"]

    return conditions


def _build_invalidation(
    scenario: Dict[str, Any],
    structure: Dict[str, Any],
    current_state: str
) -> Dict[str, Any]:
    """
    构建否决条件

    定义什么情况下应该放弃当前策略
    """
    direction = scenario.get("direction", "")
    price_position = structure.get("price_position", "")
    trigger = scenario.get("trigger", "")

    invalidate_conditions = []
    next_state = STATE_OBSERVE_ONLY

    if direction == "up":
        # 做多策略的否决条件
        invalidate_conditions = [
            "15m_failed_break_zd",
            "1h_new_down_bi",
            "price_break_dd"
        ]
        next_state = STATE_OBSERVE_ONLY
    elif direction == "down":
        # 做空策略的否决条件
        invalidate_conditions = [
            "15m_reclaim_zg_with_strength",
            "1h_new_up_bi",
            "price_break_gg"
        ]
        next_state = STATE_OBSERVE_ONLY
    else:  # range
        # 震荡策略的否决条件
        invalidate_conditions = [
            "price_break_range_high",
            "price_break_range_low",
            "high_volatility_breakout"
        ]
        next_state = STATE_STRATEGY_ACTIVE

    return {
        "invalidate_active_if": invalidate_conditions,
        "next_state": next_state
    }


def format_state_machine_for_display(state_machine: Dict[str, Any]) -> str:
    """
    格式化状态机用于终端显示

    返回易于阅读的状态机摘要
    """
    if not state_machine:
        return "（无状态机数据）"

    current_state = state_machine.get("current_state", "")
    active = state_machine.get("active_strategy", {})
    invalidation = state_machine.get("invalidation", {})

    lines = []
    lines.append(f"\n【状态机】当前: {current_state}")

    if active:
        direction = active.get("direction", "")
        status = active.get("status", "")
        lines.append(f"  激活策略: {direction} | {status}")

        entry_gate = active.get("entry_gate", {})
        price_zone = entry_gate.get("price_zone", [])
        if price_zone:
            lines.append(f"  入场区间: {price_zone[0]:,.0f} - {price_zone[1]:,.0f}")

        structure_required = entry_gate.get("structure_required", [])
        if structure_required:
            lines.append(f"  结构触发:")
            for cond in structure_required:
                lines.append(f"    - {_translate_condition(cond)}")

        execution = active.get("execution", {})
        if execution:
            lines.append(f"  执行: 止损{execution.get('stop_loss', 0):,.0f} | "
                       f"目标{execution.get('target', 0):,.0f} | "
                       f"RR{execution.get('rr', 0):.1f}")

    invalidate_if = invalidation.get("invalidate_active_if", [])
    if invalidate_if:
        lines.append(f"  否决条件:")
        for cond in invalidate_if[:3]:  # 最多显示3个
            lines.append(f"    - {_translate_condition(cond)}")

    return "\n".join(lines)


def _translate_condition(cond: str) -> str:
    """
    将英文条件代码翻译为中文
    """
    condition_map = {
        'price_hold_dd': '价格守住 DD',
        'price_break_gg': '价格突破 GG',
        'price_break_zd': '价格突破 ZD',
        'price_reject_zg': '价格受阻 ZG',
        'price_reject_zd': '价格受阻 ZD',
        'price_hold_zg': '价格守住 ZG',
        'price_reclaim_zg': '价格站回 ZG',
        'price_break_dd': '价格跌破 DD',
        '15m_break_zd': '15分钟突破 ZD',
        '15m_failed_break_zd': '15分钟未能突破 ZD',
        '15m_fail_break_zd': '15分钟未能突破 ZD',
        '15m_reclaim_zg_with_strength': '15分钟强势站回 ZG',
        '1h_new_up_bi': '1小时新向上笔',
        '1h_new_down_bi': '1小时新向下笔',
        '1h_trend_flip_up': '1小时趋势翻多',
        '1h_trend_flip_down': '1小时趋势翻空',
        'no_new_down_bi': '无新向下笔',
        'no_new_up_bi': '无新向上笔',
        'volume_confirm': '成交量确认',
        'strong_volume': '大成交量',
        'volume_surge': '成交量激增',
        'volume_weak': '成交量萎缩',
        'price_break_resistance': '价格突破阻力位',
        'price_break_support': '价格跌破支撑位',
        'price_hold_support': '价格守住支撑位',
        'price_range_bound': '价格区间受限',
        'low_volatility': '低波动率',
        'price_enter_range': '价格进入区间',
        'volatility_drop': '波动率下降',
        'price_break_range_high': '价格突破区间上沿',
        'price_break_range_low': '价格突破区间下沿',
        'high_volatility_breakout': '高波动突破',
    }
    return condition_map.get(cond, cond)


# ============================================
# 主程序测试
# ============================================
if __name__ == "__main__":
    # 测试数据
    test_ai_output = {
        "primary_scenario": {
            "direction": "down",
            "probability": 0.5
        },
        "scenarios": [
            {
                "rank": 1,
                "probability": 0.5,
                "direction": "down",
                "trigger": "价格反弹至72000附近后滞涨",
                "target_range": [60000, 62000],
                "entry_range": [68000, 72000]
            },
            {
                "rank": 2,
                "probability": 0.4,
                "direction": "range",
                "trigger": "价格在60000获得支撑",
                "target_range": [60000, 72000],
                "entry_range": [60000, 72000]
            }
        ],
        "structure_judgement": {
            "price_position": "below_zs"
        },
        "signals": {
            "buy_sell_points": ["1sell"]
        }
    }

    # 转换
    state_machine = scenarios_to_state_machine(
        test_ai_output,
        current_price=66742,
        historical_winrate=0.38
    )

    # 显示
    import json
    print("=== 状态机转换结果 ===")
    print(json.dumps(state_machine, ensure_ascii=False, indent=2))

    print("\n=== 终端显示格式 ===")
    print(format_state_machine_for_display(state_machine))
