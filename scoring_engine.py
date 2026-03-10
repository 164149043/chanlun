#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""多维度评分引擎

提供多种评分模式，公平对待不同类型的信号和波动率环境

评分模式：
1. target_based - 原始目标命中评分
2. atr_normalized - ATR归一化评分（核心）
3. signal_expected - 基于信号类型期望评分
4. volatility_adjusted - 基于波动率调整评分
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
import math


class ScoringMode(Enum):
    """评分模式"""
    TARGET_BASED = "target"      # 原始：目标命中评分
    ATR_NORMALIZED = "atr"       # ATR归一化评分
    SIGNAL_EXPECTED = "signal"   # 信号类型期望评分
    VOLATILITY_ADJUSTED = "vol"  # 波动率调整评分


# 信号类型期望配置（预期盈亏比和预期波动）
SIGNAL_EXPECTATIONS: Dict[str, Dict[str, Any]] = {
    # 趋势延续型：期望大波动
    "3buy": {"expected_rr": 2.5, "expected_move_pct": 3.0, "description": "三类买点"},
    "3sell": {"expected_rr": 2.5, "expected_move_pct": 3.0, "description": "三类卖点"},

    # 回调不破型：中等波动
    "2buy": {"expected_rr": 2.0, "expected_move_pct": 2.0, "description": "二类买点"},
    "2sell": {"expected_rr": 2.0, "expected_move_pct": 2.0, "description": "二类卖点"},

    # 转折确认型：小波动也可
    "1buy": {"expected_rr": 1.5, "expected_move_pct": 1.5, "description": "一类买点"},
    "1sell": {"expected_rr": 1.5, "expected_move_pct": 1.5, "description": "一类卖点"},

    # 衰竭反转型：最小期望
    "bc_buy": {"expected_rr": 1.0, "expected_move_pct": 1.0, "description": "底背驰"},
    "bc_sell": {"expected_rr": 1.0, "expected_move_pct": 1.0, "description": "顶背驰"},

    # 默认
    "none": {"expected_rr": 1.5, "expected_move_pct": 1.5, "description": "无信号"},
    "unknown": {"expected_rr": 1.5, "expected_move_pct": 1.5, "description": "未知"},
    "mixed": {"expected_rr": 1.5, "expected_move_pct": 1.5, "description": "混合信号"},
}


@dataclass
class ScoringResult:
    """单个评分结果"""
    mode: str
    score: float
    details: Dict = field(default_factory=dict)


class ScoringEngine:
    """多维度评分引擎

    核心功能：ATR归一化评分
    - 公平对待不同波动率的周期
    - 公平对待不同类型的信号
    """

    def __init__(self):
        self.modes = [
            ScoringMode.TARGET_BASED,
            ScoringMode.ATR_NORMALIZED,
            ScoringMode.SIGNAL_EXPECTED,
            ScoringMode.VOLATILITY_ADJUSTED,
        ]

    def calculate_atr_normalized_score(
        self,
        outcome: Dict[str, Any],
        signal_type: str,
        atr: float,
        entry_price: float
    ) -> ScoringResult:
        """ATR归一化评分（核心功能）

        原理：
        1. 计算实际盈利的ATR倍数：normalized_profit = actual_profit_pips / ATR
        2. 根据信号类型获取期望ATR倍数
        3. 评分 = min(1.0, normalized_profit / expected_profit)

        这样可以公平对待不同波动率的周期：
        - 高波动周期（如4h）：即使盈利多，但ATR也大，归一化后可能不高
        - 低波动周期（如15m）：即使盈利少，但ATR也小，归一化后可能很高

        参数：
            outcome: 评估结果字典
            signal_type: 信号类型（1buy/2buy/3buy/bc_buy等）
            atr: ATR值（价格单位）
            entry_price: 入场价格

        返回：
            ScoringResult: 评分结果
        """
        if atr <= 0:
            return ScoringResult(
                mode="atr_normalized",
                score=0.0,
                details={"error": "invalid_atr", "atr": atr}
            )

        # 获取实际最大有利变动（%）
        actual_move_pct = outcome.get("max_favorable_move", 0)

        # 转换为价格单位的盈利
        actual_profit_price = entry_price * actual_move_pct / 100

        # 计算ATR倍数
        atr_multiple = actual_profit_price / atr

        # 根据信号类型获取期望
        expected = SIGNAL_EXPECTATIONS.get(signal_type, SIGNAL_EXPECTATIONS["none"])
        expected_move_pct = expected["expected_move_pct"]

        # 期望盈利（价格单位）
        expected_profit_price = entry_price * expected_move_pct / 100

        # 期望ATR倍数
        expected_atr_multiple = expected_profit_price / atr

        # 计算评分
        if expected_atr_multiple > 0:
            score = min(1.0, atr_multiple / expected_atr_multiple)
        else:
            score = 0.0

        # 如果命中目标，额外加分
        if outcome.get("hit_target"):
            score = max(score, 0.7)  # 命中目标至少0.7分

        # 如果触发止损，扣分
        if outcome.get("hit_stop"):
            score = min(score, 0.3)  # 止损最多0.3分

        return ScoringResult(
            mode="atr_normalized",
            score=round(score, 3),
            details={
                "atr": round(atr, 2),
                "actual_move_pct": round(actual_move_pct, 2),
                "atr_multiple": round(atr_multiple, 2),
                "expected_move_pct": expected_move_pct,
                "expected_atr_multiple": round(expected_atr_multiple, 2),
                "signal_type": signal_type,
            }
        )

    def calculate_signal_expected_score(
        self,
        outcome: Dict[str, Any],
        signal_type: str
    ) -> ScoringResult:
        """基于信号类型期望评分

        不同信号类型有不同的合理期望：
        - 3buy/3sell: 期望大波动 (3%)
        - 2buy/2sell: 期望中等波动 (2%)
        - 1buy/1sell: 期望小波动也可 (1.5%)
        - bc_buy/bc_sell: 期望最小波动 (1%)

        参数：
            outcome: 评估结果字典
            signal_type: 信号类型

        返回：
            ScoringResult: 评分结果
        """
        actual_move_pct = outcome.get("max_favorable_move", 0)

        # 获取期望
        expected = SIGNAL_EXPECTATIONS.get(signal_type, SIGNAL_EXPECTATIONS["none"])
        expected_move_pct = expected["expected_move_pct"]

        # 计算评分
        if expected_move_pct > 0:
            score = min(1.0, actual_move_pct / expected_move_pct)
        else:
            score = 0.0

        # 命中目标加成
        if outcome.get("hit_target"):
            score = max(score, 0.7)

        # 止损扣分
        if outcome.get("hit_stop"):
            score = min(score, 0.3)

        return ScoringResult(
            mode="signal_expected",
            score=round(score, 3),
            details={
                "actual_move_pct": round(actual_move_pct, 2),
                "expected_move_pct": expected_move_pct,
                "signal_type": signal_type,
                "signal_description": expected["description"],
            }
        )

    def calculate_volatility_adjusted_score(
        self,
        outcome: Dict[str, Any],
        volatility_percentile: float = 0.5
    ) -> ScoringResult:
        """基于波动率调整评分

        volatility_percentile: 该周期在历史波动率中的分位数（0-1）
        - 0.5表示中等波动率
        - >0.7表示高波动率环境
        - <0.3表示低波动率环境

        高波动环境：降低期望（因为大波动更容易）
        低波动环境：提高期望（因为小波动不容易）

        参数：
            outcome: 评估结果字典
            volatility_percentile: 波动率分位数（0-1）

        返回：
            ScoringResult: 评分结果
        """
        actual_move_pct = outcome.get("max_favorable_move", 0)

        # 根据波动率分位数调整期望
        if volatility_percentile > 0.7:
            # 高波动：期望3%
            expected_pct = 3.0
        elif volatility_percentile < 0.3:
            # 低波动：期望1%
            expected_pct = 1.0
        else:
            # 中等波动：期望2%
            expected_pct = 2.0

        if expected_pct > 0:
            score = min(1.0, actual_move_pct / expected_pct)
        else:
            score = 0.0

        if outcome.get("hit_target"):
            score = max(score, 0.7)

        if outcome.get("hit_stop"):
            score = min(score, 0.3)

        return ScoringResult(
            mode="volatility_adjusted",
            score=round(score, 3),
            details={
                "actual_move_pct": round(actual_move_pct, 2),
                "expected_pct": expected_pct,
                "volatility_percentile": volatility_percentile,
            }
        )

    def calculate_target_based_score(
        self,
        outcome: Dict[str, Any]
    ) -> ScoringResult:
        """原始目标命中评分（向后兼容）

        参数：
            outcome: 评估结果字典

        返回：
            ScoringResult: 评分结果
        """
        score = outcome.get("score", 0.0)

        return ScoringResult(
            mode="target_based",
            score=score,
            details={
                "hit_target": outcome.get("hit_target", False),
                "hit_stop": outcome.get("hit_stop", False),
                "outcome": outcome.get("outcome", ""),
            }
        )

    def calculate_all_scores(
        self,
        outcome: Dict[str, Any],
        signal_type: str = "none",
        atr: Optional[float] = None,
        entry_price: Optional[float] = None,
        volatility_percentile: float = 0.5
    ) -> Dict[str, ScoringResult]:
        """计算所有评分模式

        参数：
            outcome: 评估结果字典
            signal_type: 信号类型
            atr: ATR值（可选）
            entry_price: 入场价格（可选，ATR评分需要）
            volatility_percentile: 波动率分位数（默认0.5）

        返回：
            Dict[str, ScoringResult]: 所有评分模式的结果
        """
        results: Dict[str, ScoringResult] = {}

        # 1. 原始目标命中评分
        results["target_based"] = self.calculate_target_based_score(outcome)

        # 2. ATR归一化评分（需要ATR和入场价）
        if atr is not None and entry_price is not None and atr > 0:
            results["atr_normalized"] = self.calculate_atr_normalized_score(
                outcome, signal_type, atr, entry_price
            )

        # 3. 信号类型期望评分
        results["signal_expected"] = self.calculate_signal_expected_score(
            outcome, signal_type
        )

        # 4. 波动率调整评分
        results["volatility_adjusted"] = self.calculate_volatility_adjusted_score(
            outcome, volatility_percentile
        )

        return results

    def get_best_score(self, scores: Dict[str, ScoringResult]) -> ScoringResult:
        """获取最佳评分（按优先级）

        优先级：atr_normalized > signal_expected > volatility_adjusted > target_based

        参数：
            scores: 所有评分结果

        返回：
            ScoringResult: 最佳评分
        """
        priority = ["atr_normalized", "signal_expected", "volatility_adjusted", "target_based"]

        for mode in priority:
            if mode in scores:
                return scores[mode]

        # 如果都没有，返回第一个
        return next(iter(scores.values())) if scores else ScoringResult("unknown", 0.0)

    def format_score_comparison(
        self,
        scores: Dict[str, ScoringResult],
        signal_type: str = "none"
    ) -> str:
        """格式化评分对比输出

        参数：
            scores: 所有评分结果
            signal_type: 信号类型

        返回:
            str: 格式化的评分对比文本
        """
        lines = ["📊 多维度评分:"]

        mode_names = {
            "target_based": "目标命中",
            "atr_normalized": "ATR归一化",
            "signal_expected": "信号期望",
            "volatility_adjusted": "波动率调整",
        }

        for mode, result in scores.items():
            mode_name = mode_names.get(mode, mode)
            details = result.details

            # 构建详情字符串
            detail_parts = []
            if "atr_multiple" in details:
                detail_parts.append(f"{details['atr_multiple']}倍ATR，期望{details['expected_atr_multiple']}倍")
            if "expected_move_pct" in details and "actual_move_pct" in details and mode != "atr_normalized":
                detail_parts.append(f"{details['actual_move_pct']}%盈利，期望{details['expected_move_pct']}%")

            detail_str = ", ".join(detail_parts) if detail_parts else ""

            lines.append(
                f"  {mode_name:>12}: {result.score:.3f}  ({detail_str})" if detail_str
                else f"  {mode_name:>12}: {result.score:.3f}"
            )

        return "\n".join(lines)


def calculate_atr(
    klines: List[Dict[str, Any]],
    period: int = 14
) -> float:
    """计算 ATR（Average True Range）

    ATR 是衡量市场波动率的指标，计算方式为：
    TR = max(H-L, |H-PC|, |L-PC|)
    ATR = SMA(TR, period)

    参数：
        klines: K线列表，需要包含 high, low, close
        period: ATR周期，默认14

    返回：
        ATR值（价格单位，非百分比）
    """
    if len(klines) < period + 1:
        return 0.0

    true_ranges: List[float] = []
    for i in range(1, len(klines)):
        high = klines[i].get("high", 0)
        low = klines[i].get("low", 0)
        prev_close = klines[i - 1].get("close", 0)

        if high <= 0 or low <= 0 or prev_close <= 0:
            continue

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return 0.0

    return sum(true_ranges[-period:]) / period


# ============================================
# 命令行测试
# ============================================

if __name__ == "__main__":
    import json
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

    print("=" * 60)
    print("多维度评分引擎测试")
    print("=" * 60)

    # 测试数据
    klines = [
        {"high": 67000, "low": 66500, "close": 66800},
        {"high": 67200, "low": 66600, "close": 67100},
        {"high": 67500, "low": 66800, "close": 67400},
        {"high": 67400, "low": 66900, "close": 67000},
        {"high": 67800, "low": 67000, "close": 67600},
        {"high": 68000, "low": 67200, "close": 67900},
        {"high": 68200, "low": 67500, "close": 68000},
        {"high": 68100, "low": 67400, "close": 67700},
        {"high": 68300, "low": 67600, "close": 68200},
        {"high": 68500, "low": 67800, "close": 68400},
        {"high": 68400, "low": 67700, "close": 68100},
        {"high": 68600, "low": 67900, "close": 68500},
        {"high": 68800, "low": 68100, "close": 68700},
        {"high": 68700, "low": 68000, "close": 68400},
        {"high": 68900, "low": 68200, "close": 68800},
    ]

    # 计算ATR
    atr = calculate_atr(klines)
    print(f"\nATR (14周期): {atr:.2f}")

    # 测试评分引擎
    engine = ScoringEngine()

    # 测试场景1：1buy信号，小波动盈利
    print("\n【测试场景1：1buy信号，1.5%盈利】")
    outcome1 = {
        "max_favorable_move": 1.5,
        "hit_target": True,
        "hit_stop": False,
        "score": 1.0,
    }
    scores1 = engine.calculate_all_scores(
        outcome=outcome1,
        signal_type="1buy",
        atr=atr,
        entry_price=67000,
    )
    print(engine.format_score_comparison(scores1, "1buy"))

    best1 = engine.get_best_score(scores1)
    print(f"最佳评分: {best1.score:.3f} ({best1.mode})")

    # 测试场景2：3buy信号，大波动盈利
    print("\n【测试场景2：3buy信号，3%盈利】")
    outcome2 = {
        "max_favorable_move": 3.0,
        "hit_target": True,
        "hit_stop": False,
        "score": 1.0,
    }
    scores2 = engine.calculate_all_scores(
        outcome=outcome2,
        signal_type="3buy",
        atr=atr,
        entry_price=67000,
    )
    print(engine.format_score_comparison(scores2, "3buy"))

    best2 = engine.get_best_score(scores2)
    print(f"最佳评分: {best2.score:.3f} ({best2.mode})")

    # 测试场景3：背驰信号，小波动盈利
    print("\n【测试场景3：bc_buy信号，1%盈利】")
    outcome3 = {
        "max_favorable_move": 1.0,
        "hit_target": False,
        "hit_stop": False,
        "score": 0.0,
    }
    scores3 = engine.calculate_all_scores(
        outcome=outcome3,
        signal_type="bc_buy",
        atr=atr,
        entry_price=67000,
    )
    print(engine.format_score_comparison(scores3, "bc_buy"))

    best3 = engine.get_best_score(scores3)
    print(f"最佳评分: {best3.score:.3f} ({best3.mode})")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
