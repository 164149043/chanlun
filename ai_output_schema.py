"""AI 输出 JSON Schema 定义

定义 AI 分析输出的标准格式，确保输出结构化、可解析

版本历史：
- v1.0: 初始版本，多场景并列模式
- v2.0: 新增状态机模式（向后兼容）
"""
from typing import Dict, Any, List, Optional


# ============================================
# 状态机 Schema (v2.0 新增)
# ============================================

# 状态定义
STATE_VALUES = ["STRATEGY_ACTIVE", "WAIT_CONFIRMATION", "OBSERVE_ONLY"]

# 策略状态定义
STRATEGY_STATUS_VALUES = ["WAIT", "READY", "ACTIVE", "INVALIDATED"]

# 风险等级定义
RISK_MODE_VALUES = ["NORMAL", "CAUTION", "HIGH_RISK"]

STATE_MACHINE_SCHEMA = {
    "current_state": f"string (状态: {' / '.join(STATE_VALUES)})",
    "active_strategy": {
        "direction": "string (up / down)",
        "status": f"string (策略状态: {' / '.join(STRATEGY_STATUS_VALUES)})",
        "entry_gate": {
            "price_zone": ["number (入场区间低)", "number (入场区间高)"],
            "structure_required": ["string (结构触发条件列表)"]
        },
        "execution": {
            "entry_type": "string (入场方式: market / limit / split)",
            "stop_loss": "number (止损价格)",
            "target": "number (目标价格)",
            "rr": "number (盈亏比)"
        }
    },
    "invalidation": {
        "invalidate_active_if": ["string (否决条件列表)"],
        "next_state": "string (否决后切换到的状态)"
    },
    "standby_strategies": [
        {
            "direction": "string (up / down / range)",
            "activate_if": ["string (激活条件列表)"]
        }
    ]
}


# ============================================
# 标准 AI 输出 Schema (v1.0，保留兼容)
# ============================================

# AI 输出的标准 JSON Schema
AI_OUTPUT_SCHEMA = {
    # v2.0 新增：版本标识
    "version": "string (版本: 1.0 / 2.0)",
    "output_mode": "string (输出模式: scenarios / state_machine)",

    # 原有字段（保留）
    "meta": {
        "symbol": "string",
        "interval": "string",
        "price": "number",
        "timestamp": "string"
    },
    "analysis": "string",  # AI 的文字分析内容（可选）
    "structure_judgement": {
        "current_state": "string",
        "trend": "string",  # up_trend / down_trend / consolidation
        "latest_bi": {
            "direction": "string",
            "is_done": "boolean",
            "strength_vs_prev": "string"  # weakening / strengthening / similar
        },
        "latest_xd": {
            "direction": "string",
            "is_done": "boolean"
        },
        "zs": {
            "level": "number",
            "zg": "number",  # 中枢高点
            "zd": "number",  # 中枢低点
            "gg": "number",  # 最高点
            "dd": "number",  # 最低点
            "range": ["number", "number"],
            "relation": "string"
        },
        "price_position": "string"  # above_zs / below_zs / inside_zs
    },
    "signals": {
        "buy_sell_points": ["string"],
        "divergences": ["string"]
    },
    "primary_scenario": {
        "direction": "string",
        "target_pct": "number",
        "stop_pct": "number",
        "probability": "number",
        "trigger": "string",
        "reasoning": "string"
    },
    "scenarios": [
        {
            "rank": "number",
            "probability": "number",
            "direction": "string",
            "trigger": "string",
            "target_range": ["number", "number"],
            "entry_range": ["number", "number"],
            "logic": "string"
        }
    ],
    "risk_notes": ["string"],

    # v2.0 新增：状态机格式（可选）
    "state_machine": STATE_MACHINE_SCHEMA
}


def validate_ai_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """验证 AI 输出是否符合 Schema
    
    参数：
    - output: AI 返回的 JSON 对象
    
    返回：
    - 验证通过的 output
    
    抛出：
    - ValueError: 如果不符合 Schema
    """
    
    # 1. 检查必需的顶层字段
    required_keys = ["meta", "structure_judgement", "primary_scenario", "scenarios"]
    for key in required_keys:
        if key not in output:
            raise ValueError(f"AI 输出缺少必需字段: {key}")
    
    # 2. 检查 meta 字段
    meta = output.get("meta", {})
    meta_required = ["symbol", "interval", "price", "timestamp"]
    for key in meta_required:
        if key not in meta:
            raise ValueError(f"meta 缺少字段: {key}")
    
    # 3. 检查 structure_judgement 字段
    sj = output.get("structure_judgement", {})
    if "current_state" not in sj:
        raise ValueError("structure_judgement 缺少 current_state")
    
    # 4. 检查 scenarios（必须是数组）
    scenarios = output.get("scenarios", [])
    if not isinstance(scenarios, list):
        raise ValueError("scenarios 必须是数组")
    
    if len(scenarios) == 0:
        raise ValueError("scenarios 不能为空")
    
    # 5. 验证并标准化概率格式
    # 检测概率格式：如果总和 > 2，说明 AI 返回的是百分比形式（如 40, 35, 25）
    # 需要转换为小数形式（0.4, 0.35, 0.25）
    total_prob = sum(s.get("probability", 0) for s in scenarios)

    # 标准化概率格式为 0-1 之间的小数
    if total_prob > 2:  # AI 返回的是百分比形式
        for scenario in scenarios:
            prob = scenario.get("probability", 0)
            scenario["probability"] = prob / 100
        total_prob = total_prob / 100

    if total_prob > 1.05:  # 允许 5% 的误差
        raise ValueError(f"scenarios 概率总和异常: {total_prob:.2f}")

    # 同样处理 primary_scenario 的概率
    primary = output.get("primary_scenario", {})
    if primary.get("probability"):
        prob = primary["probability"]
        if prob > 1:  # 大于1说明是百分比形式
            primary["probability"] = prob / 100

    # 6. 检查每个 scenario 的必需字段
    scenario_required = ["rank", "probability", "direction", "trigger", "logic"]
    for i, scenario in enumerate(scenarios):
        for key in scenario_required:
            if key not in scenario:
                raise ValueError(f"scenarios[{i}] 缺少字段: {key}")

    return output


def get_schema_template() -> str:
    """获取 JSON Schema 的文本模板（用于 Prompt）"""
    
    return """{
  "meta": {
    "symbol": "string",
    "interval": "string",
    "price": "number",
    "timestamp": "string"
  },
  "analysis": "string (必须填写：3-5段话的完整分析，包含当前结构、走势分析、关键价位ZG/ZD/GG/DD、做多/做空/震荡策略与具体点位）",
  "structure_judgement": {
    "current_state": "string (简述当前结构状态)",
    "trend": "string (up_trend / down_trend / consolidation)",
    "latest_bi": {
      "direction": "string (up / down)",
      "is_done": "boolean",
      "strength_vs_prev": "string (weakening / strengthening / similar，与同向前笔力度对比)"
    },
    "latest_xd": {
      "direction": "string (up / down)",
      "is_done": "boolean"
    },
    "zs": {
      "level": "number (中枢级别)",
      "zg": "number (中枢高点)",
      "zd": "number (中枢低点)",
      "gg": "number (中枢最高点)",
      "dd": "number (中枢最低点)",
      "range": ["number (low)", "number (high)"],
      "relation": "string (中枢关系：extend / new / ...)"
    },
    "price_position": "string (above_zs / below_zs / inside_zs)"
  },
  "signals": {
    "buy_sell_points": ["string (如 1buy, 2buy, 3buy, 1sell, 2sell, 3sell)"],
    "divergences": ["string (背驰类型)"]
  },
  "primary_scenario": {
    "direction": "up" | "down",
    "target_pct": "number (目标涨跌幅%，正数，如 3.0 表示 3%)",
    "stop_pct": "number (止损幅度%，正数，如 1.5 表示 1.5%)",
    "probability": "number (0~1)",
    "trigger": "string (触发条件，使用缠论术语如'突破ZG'、'回踩不破ZD')",
    "reasoning": "string (基于缠论结构的逻辑推导)"
  },
  "scenarios": [
    {
      "rank": "number",
      "probability": "number (0~1)",
      "direction": "string (up / down / range)",
      "trigger": "string (触发条件)",
      "target_range": ["number (低)", "number (高)"],
      "entry_range": ["number (入场低)", "number (入场高)"],
      "logic": "string (缠论逻辑)"
    }
  ],
  "risk_notes": ["string (风险提示)"]
}"""


def get_state_machine_schema_template() -> str:
    """获取状态机模式的 JSON Schema 文本模板（用于 Prompt）

    这是 v2.0 新增的状态机输出格式，强制单一激活策略。
    """
    return """{
  "meta": {
    "symbol": "string",
    "interval": "string",
    "price": "number",
    "timestamp": "string"
  },
  "version": "2.0",
  "output_mode": "state_machine",

  "state_machine": {
    "current_state": "STRATEGY_ACTIVE | WAIT_CONFIRMATION | OBSERVE_ONLY",

    "active_strategy": {
      "direction": "up | down",
      "status": "WAIT | READY | ACTIVE | INVALIDATED",

      "entry_gate": {
        "price_zone": ["number (入场区间低)", "number (入场区间高)"],
        "structure_required": [
          "string (结构触发条件，如: price_hold_dd)",
          "string (如: 15m_break_zd)",
          "string (如: no_new_down_bi)"
        ]
      },

      "execution": {
        "entry_type": "market | limit | split",
        "stop_loss": "number (止损价格)",
        "target": "number (目标价格)",
        "rr": "number (盈亏比，如 1.5)"
      }
    },

    "invalidation": {
      "invalidate_active_if": [
        "string (否决条件1，如: 15m_reclaim_zs_with_strength)",
        "string (否决条件2，如: 1h_trend_flip_up)"
      ],
      "next_state": "OBSERVE_ONLY | RANGE_STRATEGY"
    },

    "standby_strategies": [
      {
        "direction": "down | up | range",
        "activate_if": [
          "string (激活条件)",
          "string (如: dd_break)"
        ]
      }
    ]
  },

  # 以下字段保留用于向后兼容和显示
  "structure_judgement": {
    "trend": "string (up_trend / down_trend / consolidation)",
    "price_position": "string (above_zs / below_zs / inside_zs)",
    "zs": {
      "zg": "number (中枢高点)",
      "zd": "number (中枢低点)",
      "gg": "number (最高点)",
      "dd": "number (最低点)"
    }
  },

  "risk_notes": ["string (风险提示)"]
}"""
