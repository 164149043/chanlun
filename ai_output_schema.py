"""AI 输出 JSON Schema 定义

定义 AI 分析输出的标准格式，确保输出结构化、可解析
"""
from typing import Dict, Any, List


# AI 输出的标准 JSON Schema
AI_OUTPUT_SCHEMA = {
    "meta": {
        "symbol": "string",
        "interval": "string",
        "price": "number",
        "timestamp": "string"
    },
    "structure_judgement": {
        "current_state": "string",
        "latest_bi": {
            "direction": "string",
            "is_done": "boolean"
        },
        "latest_xd": {
            "direction": "string",
            "is_done": "boolean"
        },
        "zs": {
            "level": "number",
            "range": ["number", "number"],
            "relation": "string"
        }
    },
    "signals": {
        "buy_sell_points": ["string"],
        "divergences": ["string"]
    },
    "scenarios": [
        {
            "rank": "number",
            "probability": "number",
            "direction": "string",
            "trigger": "string",
            "target_range": ["number", "number"],
            "logic": "string"
        }
    ],
    "risk_notes": ["string"]
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
    required_keys = ["meta", "structure_judgement", "scenarios"]
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
    
    # 5. 验证概率总和
    total_prob = sum(s.get("probability", 0) for s in scenarios)
    if total_prob > 1.05:  # 允许 5% 的误差
        raise ValueError(f"scenarios 概率总和异常: {total_prob:.2f}")
    
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
  "structure_judgement": {
    "current_state": "string",
    "latest_bi": {
      "direction": "string",
      "is_done": "boolean"
    },
    "latest_xd": {
      "direction": "string",
      "is_done": "boolean"
    },
    "zs": {
      "level": "number",
      "range": ["number", "number"],
      "relation": "string"
    }
  },
  "signals": {
    "buy_sell_points": ["string"],
    "divergences": ["string"]
  },
  "scenarios": [
    {
      "rank": "number",
      "probability": "number",
      "direction": "string",
      "trigger": "string",
      "target_range": ["number", "number"],
      "logic": "string"
    }
  ],
  "risk_notes": ["string"]
}"""
