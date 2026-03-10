# -*- coding: utf-8 -*-
"""缠论结构优先规则引擎 (Rule Engine)

根据缠论"结构优先"原则，约束 AI 的概率分配，
确保概率分配符合缠论理论而非单纯的技术分析。

核心原则：
1. 结构优先 > 力度优先
2. 规则引擎给出基准概率，AI 可在 ±10% 范围内微调
3. 透明记录规则应用过程

版本：v1.0
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ===== 枚举定义 =====

class ZSRelation(Enum):
    """中枢关系类型"""
    EXTEND = "extend"
    UP_TREND = "up_trend"
    DOWN_TREND = "down_trend"
    NEW = "new"


class PricePosition(Enum):
    """价格位置"""
    ABOVE_ZS = "above_zs"
    BELOW_ZS = "below_zs"
    INSIDE_ZS = "inside_zs"


class BiDirection(Enum):
    """笔方向"""
    UP = "up"
    DOWN = "down"


class BiStrength(Enum):
    """笔力度"""
    WEAKENING = "weakening"
    STRENGTHENING = "strengthening"
    SIMILAR = "similar"


class DirectionBias(Enum):
    """方向倾向"""
    UP = "up"
    DOWN = "down"
    RANGE = "range"


# ===== 数据结构 =====

@dataclass
class StructureInput:
    """规则引擎输入数据结构"""
    zs_relation: ZSRelation
    price_position: PricePosition
    bi_direction: str  # "up" or "down"
    bi_strength: str  # "strengthening", "weakening", "similar"
    buy_sell_points: List[str]
    divergences: List[str]
    current_price: float
    key_levels: Dict[str, float]  # zg, zd, gg, dd

    @classmethod
    def from_chanlun_json(cls, ai_json: Dict[str, Any], latest_price: float) -> 'StructureInput':
        """从 chanlun_ai 的 AI JSON 构造输入"""
        # 解析中枢关系
        zs_relation = ZSRelation.NEW
        center_list = ai_json.get("center", [])
        if center_list:
            relation = center_list[-1].get("relation", "new")
            if relation == "extend":
                zs_relation = ZSRelation.EXTEND
            elif relation == "up":
                zs_relation = ZSRelation.UP_TREND
            elif relation == "down":
                zs_relation = ZSRelation.DOWN_TREND
            elif relation == "up_trend":
                zs_relation = ZSRelation.UP_TREND
            elif relation == "down_trend":
                zs_relation = ZSRelation.DOWN_TREND

        # 解析价格位置
        structure_summary = ai_json.get("structure_summary", {})
        price_pos_str = structure_summary.get("price_position", "inside_zs")
        price_position = PricePosition.INSIDE_ZS
        if "above" in price_pos_str:
            price_position = PricePosition.ABOVE_ZS
        elif "below" in price_pos_str:
            price_position = PricePosition.BELOW_ZS
        elif "inside" in price_pos_str:
            price_position = PricePosition.INSIDE_ZS

        # 解析笔信息
        bi_direction = structure_summary.get("latest_bi_direction", "up")
        bi_strength = structure_summary.get("strength_comparison", "similar")

        # 解析信号
        signal = ai_json.get("signal", {})
        buy_sell_points = signal.get("buy_sell_points", [])
        divergences = signal.get("divergences", [])

        # 解析关键位
        key_levels = {
            "zg": structure_summary.get("zg", 0),
            "zd": structure_summary.get("zd", 0),
            "gg": structure_summary.get("gg", 0),
            "dd": structure_summary.get("dd", 0),
        }

        return cls(
            zs_relation=zs_relation,
            price_position=price_position,
            bi_direction=bi_direction,
            bi_strength=bi_strength,
            buy_sell_points=buy_sell_points,
            divergences=divergences,
            current_price=latest_price,
            key_levels=key_levels
        )


@dataclass
class RuleEngineResult:
    """规则引擎输出结果"""
    base_probabilities: Dict[str, float]  # {up, down, range}
    ai_adjusted_probabilities: Dict[str, float]  # AI 微调后
    primary_direction: str
    confidence_level: str  # HIGH/MEDIUM/LOW
    applied_rules: List[str]
    warnings: List[str]
    reasoning: str


# ===== 核心规则引擎类 =====

class RuleEngine:
    """缠论结构优先规则引擎"""

    # AI 微调范围：±10%
    ADJUSTMENT_RANGE = 0.10

    # 概率归一化最小值
    MIN_PROB = 0.05

    def __init__(self, enable_ai_adjustment: bool = True, verbose: bool = True):
        """
        参数:
            enable_ai_adjustment: 是否允许 AI 在规则基准上微调
            verbose: 是否输出详细日志
        """
        self.enable_ai_adjustment = enable_ai_adjustment
        self.verbose = verbose
        self.rules_applied = []

    def calculate_base_probabilities(
        self,
        structure: StructureInput
    ) -> Dict[str, float]:
        """
        根据缠论结构计算基准概率分布（核心规则）

        这是"结构优先"原则的核心实现
        """
        self.rules_applied = []

        # 初始化中性概率
        probs = {"up": 0.33, "down": 0.33, "range": 0.34}

        # ===== 规则1: 中枢关系优先级（最高优先级）=====
        if structure.zs_relation == ZSRelation.EXTEND:
            # extend 状态 → 优先判定为震荡
            probs = {"up": 0.25, "down": 0.25, "range": 0.50}
            self._add_rule("EXTEND_PRIORITIZE_RANGE")

        elif structure.zs_relation == ZSRelation.UP_TREND:
            # up_trend 状态 → 优先判定为上涨
            probs = {"up": 0.50, "down": 0.20, "range": 0.30}
            self._add_rule("UP_TREND_PRIORITIZE_BULL")

        elif structure.zs_relation == ZSRelation.DOWN_TREND:
            # down_trend 状态 → 优先判定为下跌
            probs = {"up": 0.20, "down": 0.50, "range": 0.30}
            self._add_rule("DOWN_TREND_PRIORITIZE_BEAR")

        elif structure.zs_relation == ZSRelation.NEW:
            # new 状态 → 谨慎判断，分布更均衡
            probs = {"up": 0.35, "down": 0.35, "range": 0.30}
            self._add_rule("NEW_STATE_CAUTIOUS")

        # ===== 规则2: 价格位置调整 =====
        probs = self._apply_price_position_rule(probs, structure)

        # ===== 规则3: 最新笔方向和力度调整 =====
        probs = self._apply_bi_strength_rule(probs, structure)

        # ===== 规则4: 买卖点信号调整 =====
        probs = self._apply_signal_rule(probs, structure)

        # ===== 规则5: 背驰信号调整 =====
        probs = self._apply_divergence_rule(probs, structure)

        # 归一化
        return self._normalize(probs)

    def apply_ai_adjustment(
        self,
        base_probs: Dict[str, float],
        ai_probs: Dict[str, float]
    ) -> Dict[str, float]:
        """
        应用 AI 微调（在规则基准上 ±10% 范围内）

        参数:
            base_probs: 规则引擎计算的基准概率
            ai_probs: AI 原始输出的概率

        返回:
            调整后的概率（确保在 base ± 10% 范围内）
        """
        if not self.enable_ai_adjustment:
            return base_probs.copy()

        adjusted = {
            "up": self._adjust_single_probability(base_probs["up"], ai_probs.get("up", 0.33)),
            "down": self._adjust_single_probability(base_probs["down"], ai_probs.get("down", 0.33)),
            "range": self._adjust_single_probability(base_probs["range"], ai_probs.get("range", 0.34))
        }

        return self._normalize(adjusted)

    def process(
        self,
        structure: StructureInput,
        ai_output: Dict[str, Any]
    ) -> RuleEngineResult:
        """
        完整处理流程

        参数:
            structure: 缠论结构输入
            ai_output: AI 原始输出

        返回:
            RuleEngineResult
        """
        self.rules_applied = []

        # 1. 计算规则引擎基准概率
        base_probs = self.calculate_base_probabilities(structure)

        # 2. 提取 AI 输出的概率
        ai_probs = self._extract_ai_probabilities(ai_output)

        # 3. 应用 AI 微调
        adjusted_probs = self.apply_ai_adjustment(base_probs, ai_probs)

        # 4. 确定主推方向
        primary_direction = self._determine_primary_direction(adjusted_probs)

        # 5. 计算置信度
        confidence_level = self._calculate_confidence(
            base_probs, adjusted_probs, structure
        )

        # 6. 生成推理说明
        reasoning = self._generate_reasoning(
            structure, base_probs, adjusted_probs, primary_direction
        )

        # 7. 收集警告
        warnings = self._collect_warnings(
            structure, base_probs, ai_probs, adjusted_probs
        )

        return RuleEngineResult(
            base_probabilities=base_probs,
            ai_adjusted_probabilities=adjusted_probs,
            primary_direction=primary_direction,
            confidence_level=confidence_level,
            applied_rules=self.rules_applied.copy(),
            reasoning=reasoning,
            warnings=warnings
        )

    # ===== 私有方法：规则应用 =====

    def _apply_price_position_rule(
        self,
        probs: Dict[str, float],
        structure: StructureInput
    ) -> Dict[str, float]:
        """应用价格位置规则"""
        pos = structure.price_position

        if pos == PricePosition.ABOVE_ZS:
            # 价格在中枢上方 → 偏多头，但需警惕回落
            probs["up"] = min(0.65, probs["up"] + 0.10)
            probs["range"] = max(0.15, probs["range"] - 0.05)
            self._add_rule("PRICE_POS_ABOVE_ZS")

        elif pos == PricePosition.BELOW_ZS:
            # 价格在中枢下方 → 偏空头，但需警惕反弹
            probs["down"] = min(0.65, probs["down"] + 0.10)
            probs["range"] = max(0.15, probs["range"] - 0.05)
            self._add_rule("PRICE_POS_BELOW_ZS")

        elif pos == PricePosition.INSIDE_ZS:
            # 价格在中枢内部 → 震荡概率增加
            probs["range"] = min(0.60, probs["range"] + 0.15)
            probs["up"] = max(0.15, probs["up"] - 0.05)
            probs["down"] = max(0.15, probs["down"] - 0.05)
            self._add_rule("PRICE_POS_INSIDE_ZS")

        return probs

    def _apply_bi_strength_rule(
        self,
        probs: Dict[str, float],
        structure: StructureInput
    ) -> Dict[str, float]:
        """应用笔力度规则"""
        strength = structure.bi_strength.lower()
        direction = structure.bi_direction.lower()

        if strength == "weakening" or "weaken" in strength:
            # 力度减弱 → 反转概率增加
            if direction == "up":
                # 上升力度减弱 → 做空概率增加
                probs["down"] = min(0.50, probs["down"] + 0.10)
                probs["up"] = max(0.15, probs["up"] - 0.05)
            else:
                # 下降力度减弱 → 做多概率增加
                probs["up"] = min(0.50, probs["up"] + 0.10)
                probs["down"] = max(0.15, probs["down"] - 0.05)
            self._add_rule("BI_STRENGTH_WEAKENING")

        elif strength == "strengthening" or "strengthen" in strength:
            # 力度增强 → 趋势延续
            if direction == "up":
                probs["up"] = min(0.60, probs["up"] + 0.10)
            else:
                probs["down"] = min(0.60, probs["down"] + 0.10)
            probs["range"] = max(0.15, probs["range"] - 0.05)
            self._add_rule("BI_STRENGTH_STRENGTHENING")

        return probs

    def _apply_signal_rule(
        self,
        probs: Dict[str, float],
        structure: StructureInput
    ) -> Dict[str, float]:
        """应用买卖点信号规则"""
        for signal in structure.buy_sell_points:
            sig_lower = signal.lower()

            if "1buy" in sig_lower or ("bc" in sig_lower and "buy" in sig_lower):
                probs["up"] = min(0.70, probs["up"] + 0.10)
                self._add_rule("SIGNAL_1BUY")
            elif "2buy" in sig_lower:
                probs["up"] = min(0.65, probs["up"] + 0.08)
                self._add_rule("SIGNAL_2BUY")
            elif "3buy" in sig_lower:
                probs["up"] = min(0.55, probs["up"] + 0.05)
                self._add_rule("SIGNAL_3BUY")
            elif "1sell" in sig_lower or ("bc" in sig_lower and "sell" in sig_lower):
                probs["down"] = min(0.70, probs["down"] + 0.10)
                self._add_rule("SIGNAL_1SELL")
            elif "2sell" in sig_lower:
                probs["down"] = min(0.65, probs["down"] + 0.08)
                self._add_rule("SIGNAL_2SELL")
            elif "3sell" in sig_lower:
                probs["down"] = min(0.55, probs["down"] + 0.05)
                self._add_rule("SIGNAL_3SELL")

        return probs

    def _apply_divergence_rule(
        self,
        probs: Dict[str, float],
        structure: StructureInput
    ) -> Dict[str, float]:
        """应用背驰规则"""
        for div in structure.divergences:
            div_lower = div.lower()

            if "bottom" in div_lower or "底" in div_lower:
                # 底背驰 → 做多
                probs["up"] = min(0.60, probs["up"] + 0.08)
                self._add_rule("DIVERGENCE_BOTTOM")
            elif "top" in div_lower or "顶" in div_lower:
                # 顶背驰 → 做空
                probs["down"] = min(0.60, probs["down"] + 0.08)
                self._add_rule("DIVERGENCE_TOP")

        return probs

    # ===== 私有方法：辅助函数 =====

    def _normalize(self, probs: Dict[str, float]) -> Dict[str, float]:
        """归一化概率，确保总和为1"""
        total = probs["up"] + probs["down"] + probs["range"]
        if total == 0:
            return {"up": 0.33, "down": 0.33, "range": 0.34}

        return {
            "up": round(probs["up"] / total, 2),
            "down": round(probs["down"] / total, 2),
            "range": round(probs["range"] / total, 2)
        }

    def _adjust_single_probability(self, base: float, ai: float) -> float:
        """
        调整单个概率（在 base ± 10% 范围内）

        参数:
            base: 规则引擎基准概率
            ai: AI 建议概率

        返回:
            调整后的概率
        """
        diff = ai - base
        max_diff = self.ADJUSTMENT_RANGE

        # 限制调整范围
        if abs(diff) <= max_diff:
            return ai
        elif diff > 0:
            return base + max_diff
        else:
            return base - max_diff

    def _extract_ai_probabilities(self, ai_output: Dict[str, Any]) -> Dict[str, float]:
        """从 AI 输出中提取概率分布"""
        scenarios = ai_output.get("scenarios", [])
        if not scenarios:
            return {"up": 0.33, "down": 0.33, "range": 0.34}

        probs = {"up": 0.0, "down": 0.0, "range": 0.0}

        for scenario in scenarios:
            direction = scenario.get("direction", scenario.get("type", ""))
            prob = scenario.get("probability", 0)

            if direction in ["up", "long"]:
                probs["up"] += prob
            elif direction in ["down", "short"]:
                probs["down"] += prob
            elif direction == "range":
                probs["range"] += prob

        # 如果没有找到有效概率，返回默认值
        if probs["up"] == 0 and probs["down"] == 0 and probs["range"] == 0:
            return {"up": 0.33, "down": 0.33, "range": 0.34}

        return self._normalize(probs)

    def _determine_primary_direction(self, probs: Dict[str, float]) -> str:
        """确定主推方向"""
        max_prob = max(probs.values())
        for direction, prob in probs.items():
            if prob == max_prob:
                return direction
        return "range"

    def _calculate_confidence(
        self,
        base: Dict[str, float],
        adjusted: Dict[str, float],
        structure: StructureInput
    ) -> str:
        """
        计算置信度等级

        置信度规则:
        - HIGH: 规则明确（如强趋势 + 买卖点），AI 与规则一致
        - MEDIUM: 规则中等，AI 与规则有小幅偏离
        - LOW: 规则模糊（如 new 状态），AI 与规则大幅偏离
        """
        # 1. 计算 AI 与规则的一致性
        avg_diff = (
            abs(adjusted["up"] - base["up"]) +
            abs(adjusted["down"] - base["down"]) +
            abs(adjusted["range"] - base["range"])
        ) / 3

        # 2. 计算主推概率的集中度
        max_prob = max(adjusted.values())

        # 3. 判断结构清晰度
        structure_clarity = 0
        if structure.zs_relation in [ZSRelation.UP_TREND, ZSRelation.DOWN_TREND]:
            structure_clarity += 0.3
        if structure.buy_sell_points:
            structure_clarity += 0.3
        if structure.divergences:
            structure_clarity += 0.2

        # 4. 综合判断
        if avg_diff < 0.05 and max_prob > 0.50 and structure_clarity > 0.5:
            return "HIGH"
        elif avg_diff < 0.10 and max_prob > 0.40:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_reasoning(
        self,
        structure: StructureInput,
        base: Dict[str, float],
        adjusted: Dict[str, float],
        primary_direction: str
    ) -> str:
        """生成推理说明"""
        lines = [
            f"结构分析：{structure.zs_relation.value} + {structure.price_position.value}",
            f"基准概率：up={base['up']:.0%} down={base['down']:.0%} range={base['range']:.0%}",
            f"调整后：up={adjusted['up']:.0%} down={adjusted['down']:.0%} range={adjusted['range']:.0%}",
            f"主推方向：{primary_direction}"
        ]
        return " | ".join(lines)

    def _collect_warnings(
        self,
        structure: StructureInput,
        base: Dict[str, float],
        ai: Dict[str, float],
        adjusted: Dict[str, float]
    ) -> List[str]:
        """收集警告信息"""
        warnings = []

        # 警告1: AI 与规则引擎严重偏离
        if abs(adjusted["up"] - base["up"]) > 0.08:
            warnings.append(
                f"AI与规则在做多概率上偏离较大 "
                f"(规则{base['up']:.0%} vs AI{adjusted['up']:.0%})"
            )

        # 警告2: new 状态谨慎判断
        if structure.zs_relation == ZSRelation.NEW:
            warnings.append("中枢处于new状态，建议谨慎判断")

        # 警告3: 方向信号冲突
        if structure.buy_sell_points:
            has_buy = any("buy" in s.lower() for s in structure.buy_sell_points)
            has_sell = any("sell" in s.lower() for s in structure.buy_sell_points)
            if has_buy and has_sell:
                warnings.append("同时存在买卖点信号，建议等待明确方向")

        # 警告4: 力度背驰与方向不一致
        if (structure.bi_strength == "weakening" and
                structure.zs_relation in [ZSRelation.UP_TREND, ZSRelation.DOWN_TREND]):
            warnings.append("趋势方向与笔力度背驰，注意反转可能")

        return warnings

    def _add_rule(self, rule_name: str):
        """记录应用的规则"""
        if rule_name not in self.rules_applied:
            self.rules_applied.append(rule_name)


# ===== 便捷函数 =====

def apply_rule_engine(
    ai_json: Dict[str, Any],
    ai_output: Dict[str, Any],
    latest_price: float,
    enable_ai_adjustment: bool = True
) -> Tuple[bool, RuleEngineResult]:
    """
    应用规则引擎到 AI 输出

    参数:
        ai_json: 缠论结构 JSON
        ai_output: AI 原始输出
        latest_price: 当前价格
        enable_ai_adjustment: 是否允许 AI 微调

    返回:
        (success, rule_result) - 是否成功，规则引擎结果
    """
    try:
        # 构造规则引擎输入
        structure = StructureInput.from_chanlun_json(ai_json, latest_price)

        # 创建规则引擎并处理
        engine = RuleEngine(enable_ai_adjustment=enable_ai_adjustment)
        result = engine.process(structure, ai_output)

        return True, result
    except Exception as e:
        return False, None


# ===== 主程序测试 =====

if __name__ == "__main__":
    # 测试数据
    test_ai_json = {
        "structure_summary": {
            "trend": "consolidation",
            "price_position": "below_zs",
            "latest_bi_direction": "down",
            "strength_comparison": "strengthening",
            "zg": 68476.22,
            "zd": 67690.0
        },
        "signal": {
            "buy_sell_points": ["1buy", "3sell"],
            "divergences": ["bi"]
        },
        "center": [
            {"relation": "down_trend"},
            {"relation": "down_trend"},
            {"relation": "extend"}
        ]
    }

    test_ai_output = {
        "scenarios": [
            {"direction": "down", "probability": 0.40},
            {"direction": "range", "probability": 0.35},
            {"direction": "up", "probability": 0.25}
        ]
    }

    # 执行规则引擎
    success, result = apply_rule_engine(
        test_ai_json,
        test_ai_output,
        latest_price=66852.04,
        enable_ai_adjustment=True
    )

    if success:
        print("=== 规则引擎处理结果 ===")
        print(f"基准概率: up={result.base_probabilities['up']:.0%} "
              f"down={result.base_probabilities['down']:.0%} "
              f"range={result.base_probabilities['range']:.0%}")
        print(f"调整后概率: up={result.ai_adjusted_probabilities['up']:.0%} "
              f"down={result.ai_adjusted_probabilities['down']:.0%} "
              f"range={result.ai_adjusted_probabilities['range']:.0%}")
        print(f"主推方向: {result.primary_direction}")
        print(f"置信度: {result.confidence_level}")
        print(f"应用规则: {', '.join(result.applied_rules)}")
        print(f"推理: {result.reasoning}")
        if result.warnings:
            print("警告:")
            for w in result.warnings:
                print(f"  - {w}")
    else:
        print("规则引擎处理失败")
