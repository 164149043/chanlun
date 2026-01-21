# -*- coding: utf-8 -*-
"""置信度约束模块

功能：
1. 根据AI历史表现自动调整预测参数
2. 对低胜率场景强制降低置信度
3. 约束目标幅度不超过历史实际变动
4. 生成调整说明

基于学习反馈报告强制约束AI输出，让AI"说多谨慎"
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

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

# 尝试导入学习反馈模块
try:
    from learning_feedback import LearningReport, LearningFeedbackAnalyzer
    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False
    LearningReport = None


@dataclass
class ConstraintResult:
    """约束结果"""
    adjusted: bool  # 是否进行了调整
    adjustments: List[str]  # 调整说明列表
    original_probability: float
    new_probability: float
    original_target: float
    new_target: float
    original_stop: float
    new_stop: float
    risk_level: str  # high/medium/low
    recommendation: str


class ConfidenceConstraint:
    """置信度约束器"""
    
    def __init__(self, learning_report: 'LearningReport' = None):
        self.report = learning_report
    
    def apply_constraints(
        self,
        ai_output: Dict[str, Any],
        current_signal: str = None,
    ) -> Tuple[Dict[str, Any], ConstraintResult]:
        """应用置信度约束
        
        参数：
        - ai_output: AI输出的JSON
        - current_signal: 当前信号类型
        
        返回：
        - (调整后的ai_output, ConstraintResult)
        """
        primary = ai_output.get("primary_scenario", {})
        if not primary:
            return ai_output, ConstraintResult(
                adjusted=False,
                adjustments=[],
                original_probability=0,
                new_probability=0,
                original_target=0,
                new_target=0,
                original_stop=0,
                new_stop=0,
                risk_level="unknown",
                recommendation="无primary_scenario"
            )
        
        # 提取原始值
        direction = primary.get("direction", "unknown")
        orig_prob = primary.get("probability", 0.5)
        orig_target = primary.get("target_pct", 2.0)
        orig_stop = primary.get("stop_pct", 1.0)
        
        new_prob = orig_prob
        new_target = orig_target
        new_stop = orig_stop
        
        adjustments = []
        risk_level = "low"
        
        if self.report and self.report.total_predictions >= 20:
            # 规则1：基于方向胜率约束
            dir_stats = self.report.by_direction.get(direction)
            if dir_stats and dir_stats.has_enough_samples:
                if dir_stats.win_rate < 0.1:
                    # 胜率<10%：大幅降低
                    risk_level = "high"
                    factor = 0.5
                    new_prob = min(0.3, orig_prob * factor)
                    new_target = min(1.5, orig_target * 0.6)
                    adjustments.append(f"该方向历史胜率仅{dir_stats.win_rate*100:.0f}%，大幅降低置信度")
                    
                elif dir_stats.win_rate < 0.2:
                    # 胜率<20%：适度降低
                    risk_level = "medium"
                    factor = 0.7
                    new_prob = min(0.4, orig_prob * factor)
                    new_target = min(2.0, orig_target * 0.75)
                    adjustments.append(f"该方向历史胜率{dir_stats.win_rate*100:.0f}%偏低，降低置信度")
                
                # 约束目标幅度不超过历史实际变动的1.5倍
                if dir_stats.avg_actual_move > 0:
                    max_target = dir_stats.avg_actual_move * 1.5
                    if new_target > max_target:
                        old_target = new_target
                        new_target = round(max_target, 1)
                        adjustments.append(f"目标从{old_target:.1f}%降至{new_target:.1f}%（历史实际变动{dir_stats.avg_actual_move:.1f}%的1.5倍）")
            
            # 规则2：基于信号类型约束
            if current_signal:
                sig_stats = self.report.by_signal_type.get(current_signal)
                if sig_stats and sig_stats.has_enough_samples:
                    if sig_stats.win_rate < 0.1:
                        risk_level = "high"
                        new_prob = min(new_prob, 0.25)
                        adjustments.append(f"信号类型({current_signal})历史胜率仅{sig_stats.win_rate*100:.0f}%")
            
            # 规则3：整体胜率约束
            if self.report.overall_win_rate < 0.15:
                if risk_level != "high":
                    risk_level = "medium"
                new_prob = min(new_prob, 0.4)
                new_target = min(new_target, 2.0)
                if new_prob < orig_prob or new_target < orig_target:
                    adjustments.append("系统整体胜率较低，采用保守策略")
        
        # 规则4：通用约束 - 盈亏比检查
        if new_stop > 0 and new_target / new_stop < 1.5:
            # 盈亏比不足1.5，调整止损
            new_stop = round(new_target / 1.5, 2)
            adjustments.append(f"调整止损至{new_stop:.1f}%以确保盈亏比≥1.5")
        
        # 规则5：概率合理性
        new_prob = max(0.1, min(0.8, new_prob))  # 限制在10%-80%
        new_target = max(0.5, new_target)  # 最小目标0.5%
        new_stop = max(0.3, new_stop)  # 最小止损0.3%
        
        # 应用调整
        adjusted = (new_prob != orig_prob or new_target != orig_target or new_stop != orig_stop)
        
        if adjusted:
            ai_output["primary_scenario"]["probability"] = round(new_prob, 2)
            ai_output["primary_scenario"]["target_pct"] = round(new_target, 1)
            ai_output["primary_scenario"]["stop_pct"] = round(new_stop, 2)
            
            # 同步调整scenarios中的第一个
            scenarios = ai_output.get("scenarios", [])
            if scenarios:
                scenarios[0]["probability"] = round(new_prob, 2)
        
        # 生成建议
        if risk_level == "high":
            recommendation = "高风险场景，建议观望或极小仓位试探"
        elif risk_level == "medium":
            recommendation = "中等风险，建议轻仓操作并严格止损"
        else:
            recommendation = "风险可控，可按正常仓位操作"
        
        result = ConstraintResult(
            adjusted=adjusted,
            adjustments=adjustments,
            original_probability=orig_prob,
            new_probability=new_prob,
            original_target=orig_target,
            new_target=new_target,
            original_stop=orig_stop,
            new_stop=new_stop,
            risk_level=risk_level,
            recommendation=recommendation,
        )
        
        return ai_output, result


def apply_confidence_constraints(
    ai_output: Dict[str, Any],
    learning_report: 'LearningReport' = None,
    current_signal: str = None,
) -> Tuple[Dict[str, Any], ConstraintResult]:
    """应用置信度约束（便捷函数）"""
    constraint = ConfidenceConstraint(learning_report)
    return constraint.apply_constraints(ai_output, current_signal)


def format_constraint_result(result: ConstraintResult) -> str:
    """格式化约束结果"""
    if not result.adjusted:
        return "✅ 参数合理，无需约束调整"
    
    lines = []
    lines.append("")
    lines.append("=" * 50)
    lines.append("  置信度约束调整")
    lines.append("=" * 50)
    
    risk_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(result.risk_level, "⚪")
    lines.append(f"\n  风险等级: {risk_icon} {result.risk_level.upper()}")
    
    lines.append(f"\n  【参数调整】")
    if result.original_probability != result.new_probability:
        lines.append(f"  概率: {result.original_probability*100:.0f}% → {result.new_probability*100:.0f}%")
    if result.original_target != result.new_target:
        lines.append(f"  目标: {result.original_target:.1f}% → {result.new_target:.1f}%")
    if result.original_stop != result.new_stop:
        lines.append(f"  止损: {result.original_stop:.1f}% → {result.new_stop:.2f}%")
    
    lines.append(f"\n  【调整原因】")
    for adj in result.adjustments:
        lines.append(f"  - {adj}")
    
    lines.append(f"\n  【建议】{result.recommendation}")
    lines.append("=" * 50)
    
    return "\n".join(lines)


# ============================================
# 测试
# ============================================

def main():
    """测试置信度约束"""
    # 模拟AI输出
    test_output = {
        "primary_scenario": {
            "direction": "up",
            "target_pct": 3.5,
            "stop_pct": 1.5,
            "probability": 0.6,
        },
        "scenarios": [
            {"rank": 1, "probability": 0.6, "direction": "up"},
        ]
    }
    
    print("测试置信度约束...")
    print("=" * 50)
    print("原始参数:")
    print(f"  方向: up")
    print(f"  概率: 60%")
    print(f"  目标: 3.5%")
    print(f"  止损: 1.5%")
    
    if LEARNING_AVAILABLE:
        # 加载学习报告
        analyzer = LearningFeedbackAnalyzer()
        report = analyzer.analyze(days=30)
        
        # 应用约束
        adjusted_output, result = apply_confidence_constraints(
            test_output,
            learning_report=report,
            current_signal="1buy",
        )
        
        print(format_constraint_result(result))
        
        print("\n调整后参数:")
        primary = adjusted_output["primary_scenario"]
        print(f"  概率: {primary['probability']*100:.0f}%")
        print(f"  目标: {primary['target_pct']:.1f}%")
        print(f"  止损: {primary['stop_pct']:.2f}%")
    else:
        print("⚠️ 学习反馈模块不可用")


if __name__ == "__main__":
    main()
