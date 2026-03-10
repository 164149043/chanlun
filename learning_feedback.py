# -*- coding: utf-8 -*-
"""AI学习反馈报告模块

功能：
1. 统计AI的整体历史表现（不只是相似案例）
2. 发现AI的系统性错误模式
3. 生成"自我认知"摘要注入Prompt
4. 提供置信度约束建议

核心指标：
- 按方向统计胜率（看涨/看跌/震荡）
- 按信号类型统计胜率
- 目标幅度偏差分析
- 典型错误模式识别
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
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent / "chanlun_ai.db"

# 导入数据库管理器（修复连接泄漏问题）
try:
    from db_manager import get_db_conn, safe_json_loads
    DB_MANAGER_AVAILABLE = True
except ImportError:
    DB_MANAGER_AVAILABLE = False


def get_min_sample_size(total_samples: int) -> int:
    """动态计算最小样本量阈值

    根据总样本数动态确定统计是否有意义。
    样本越多，需要的最小样本量也越大。

    参数:
        total_samples: 总样本数

    返回:
        int: 最小样本量阈值
    """
    if total_samples < 50:
        return 5
    elif total_samples < 200:
        return 10
    elif total_samples < 500:
        return 15
    else:
        return 20


@dataclass
class PerformanceStats:
    """表现统计"""
    total: int = 0
    wins: int = 0
    losses: int = 0
    avg_score: float = 0.0
    avg_target_pct: float = 0.0
    avg_actual_move: float = 0.0
    target_deviation: float = 0.0  # 目标偏差（目标-实际）
    total_predictions: int = 0  # 总预测数（用于动态计算最小样本量）

    @property
    def win_rate(self) -> float:
        return self.wins / self.total if self.total > 0 else 0

    @property
    def has_enough_samples(self) -> bool:
        """动态判断是否有足够样本"""
        min_size = get_min_sample_size(self.total_predictions)
        return self.total >= min_size


@dataclass
class ErrorPattern:
    """错误模式"""
    pattern_type: str
    description: str
    frequency: int
    severity: str  # high/medium/low
    suggestion: str


@dataclass 
class LearningReport:
    """学习反馈报告"""
    # 基础统计
    total_predictions: int = 0
    overall_win_rate: float = 0.0
    overall_avg_score: float = 0.0
    
    # 按方向统计
    by_direction: Dict[str, PerformanceStats] = field(default_factory=dict)
    
    # 按信号类型统计
    by_signal_type: Dict[str, PerformanceStats] = field(default_factory=dict)
    
    # 按周期统计
    by_interval: Dict[str, PerformanceStats] = field(default_factory=dict)
    
    # 错误模式
    error_patterns: List[ErrorPattern] = field(default_factory=list)
    
    # 建议
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # 置信度约束建议
    confidence_adjustments: Dict[str, float] = field(default_factory=dict)


class LearningFeedbackAnalyzer:
    """学习反馈分析器"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if DB_MANAGER_AVAILABLE:
            from db_manager import get_db_conn_no_context
            return get_db_conn_no_context()
        return sqlite3.connect(str(self.db_path))
    
    def _classify_signal(self, ai_json: dict, chanlun_json: dict) -> str:
        """分类信号类型"""
        source = chanlun_json if chanlun_json else ai_json
        signal = source.get("signal", {})
        buy_sell_points = signal.get("buy_sell_points", [])
        divergences = signal.get("divergences", [])
        
        if not buy_sell_points and not divergences:
            return "none"
        
        for s in buy_sell_points:
            sl = s.lower()
            if "1buy" in sl: return "1buy"
            elif "2buy" in sl: return "2buy"
            elif "3buy" in sl: return "3buy"
            elif "1sell" in sl: return "1sell"
            elif "2sell" in sl: return "2sell"
            elif "3sell" in sl: return "3sell"
        
        if divergences:
            for d in divergences:
                dl = d.lower()
                if "bottom" in dl or "底" in d: return "bc_buy"
                elif "top" in dl or "顶" in d: return "bc_sell"
        
        return "mixed"
    
    def analyze(self, days: int = 30, symbol: str = None, interval: str = None) -> LearningReport:
        """分析AI历史表现
        
        参数：
        - days: 分析最近多少天的数据
        - symbol: 过滤特定交易对
        - interval: 过滤特定周期
        
        返回：
        - LearningReport
        """
        conn = self._get_conn()
        
        # 构建查询
        query = """
            SELECT ai_json, outcome_json, chanlun_json, symbol, interval, timestamp
            FROM analysis_snapshot
            WHERE evaluated = 1 AND outcome_json IS NOT NULL
        """
        params = []
        
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            query += " AND timestamp >= ?"
            params.append(cutoff.isoformat())
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if interval:
            query += " AND interval = ?"
            params.append(interval)
        
        query += " ORDER BY timestamp DESC LIMIT 1000"
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        
        # 初始化报告
        report = LearningReport()
        
        # 收集数据
        direction_data = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0, "targets": [], "actuals": []})
        signal_data = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0})
        interval_data = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0})
        
        all_scores = []
        all_wins = 0
        target_deviations = []
        
        for ai_str, outcome_str, chanlun_str, sym, intv, ts in rows:
            try:
                ai = json.loads(ai_str) if ai_str else {}
                outcome = json.loads(outcome_str)
                chanlun = json.loads(chanlun_str) if chanlun_str else {}
            except:
                continue
            
            # 提取数据
            primary = ai.get("primary_scenario", {})
            direction = primary.get("direction", outcome.get("direction", "unknown"))
            target_pct = primary.get("target_pct", 0)
            hit_target = outcome.get("hit_target", False)
            score = outcome.get("score", 0)
            max_favorable = outcome.get("max_favorable_move", 0)
            
            signal_type = self._classify_signal(ai, chanlun)
            
            # 累计统计
            report.total_predictions += 1
            all_scores.append(score)
            if hit_target:
                all_wins += 1
            
            # 按方向
            direction_data[direction]["total"] += 1
            direction_data[direction]["score"] += score
            direction_data[direction]["targets"].append(target_pct)
            direction_data[direction]["actuals"].append(max_favorable)
            if hit_target:
                direction_data[direction]["wins"] += 1
            
            # 按信号类型
            signal_data[signal_type]["total"] += 1
            signal_data[signal_type]["score"] += score
            if hit_target:
                signal_data[signal_type]["wins"] += 1
            
            # 按周期
            interval_data[intv]["total"] += 1
            interval_data[intv]["score"] += score
            if hit_target:
                interval_data[intv]["wins"] += 1
            
            # 目标偏差
            if target_pct > 0:
                deviation = target_pct - max_favorable
                target_deviations.append(deviation)
        
        # 计算整体指标
        if report.total_predictions > 0:
            report.overall_win_rate = all_wins / report.total_predictions
            report.overall_avg_score = sum(all_scores) / len(all_scores)
        
        # 按方向统计
        for direction, data in direction_data.items():
            stats = PerformanceStats(
                total=data["total"],
                wins=data["wins"],
                losses=data["total"] - data["wins"],
                avg_score=data["score"] / data["total"] if data["total"] > 0 else 0,
                avg_target_pct=sum(data["targets"]) / len(data["targets"]) if data["targets"] else 0,
                avg_actual_move=sum(data["actuals"]) / len(data["actuals"]) if data["actuals"] else 0,
            )
            stats.target_deviation = stats.avg_target_pct - stats.avg_actual_move
            report.by_direction[direction] = stats
        
        # 按信号类型统计
        for signal_type, data in signal_data.items():
            stats = PerformanceStats(
                total=data["total"],
                wins=data["wins"],
                avg_score=data["score"] / data["total"] if data["total"] > 0 else 0,
            )
            report.by_signal_type[signal_type] = stats
        
        # 按周期统计
        for intv, data in interval_data.items():
            stats = PerformanceStats(
                total=data["total"],
                wins=data["wins"],
                avg_score=data["score"] / data["total"] if data["total"] > 0 else 0,
            )
            report.by_interval[intv] = stats
        
        # 识别错误模式
        self._identify_error_patterns(report, target_deviations)
        
        # 生成建议
        self._generate_recommendations(report)
        
        # 计算置信度约束
        self._calculate_confidence_adjustments(report)
        
        return report
    
    def _identify_error_patterns(self, report: LearningReport, target_deviations: List[float]):
        """识别错误模式"""
        patterns = []
        
        # 模式1：目标设置过高
        if target_deviations:
            avg_deviation = sum(target_deviations) / len(target_deviations)
            if avg_deviation > 1.0:
                patterns.append(ErrorPattern(
                    pattern_type="target_too_high",
                    description=f"目标幅度平均偏高 {avg_deviation:.1f}%",
                    frequency=len([d for d in target_deviations if d > 1.0]),
                    severity="high",
                    suggestion="降低目标幅度设置，建议不超过历史实际变动的1.5倍"
                ))
        
        # 模式2：看涨预测准确率低
        up_stats = report.by_direction.get("up")
        if up_stats and up_stats.total >= 10 and up_stats.win_rate < 0.15:
            patterns.append(ErrorPattern(
                pattern_type="up_prediction_weak",
                description=f"看涨预测胜率仅 {up_stats.win_rate*100:.1f}%",
                frequency=up_stats.total,
                severity="high",
                suggestion="对看涨预测应更加谨慎，降低概率或建议观望"
            ))
        
        # 模式3：无信号时乱猜
        none_stats = report.by_signal_type.get("none")
        if none_stats and none_stats.total >= 10 and none_stats.win_rate < 0.15:
            patterns.append(ErrorPattern(
                pattern_type="no_signal_guessing",
                description=f"无明确信号时预测胜率仅 {none_stats.win_rate*100:.1f}%",
                frequency=none_stats.total,
                severity="high",
                suggestion="无明确买卖点信号时，应建议观望而非强行预测"
            ))
        
        # 模式4：某周期表现差
        for intv, stats in report.by_interval.items():
            if stats.total >= 10 and stats.win_rate < 0.1:
                patterns.append(ErrorPattern(
                    pattern_type=f"weak_interval_{intv}",
                    description=f"{intv}周期预测胜率仅 {stats.win_rate*100:.1f}%",
                    frequency=stats.total,
                    severity="medium",
                    suggestion=f"在{intv}周期应采用更保守的策略"
                ))
        
        report.error_patterns = patterns
    
    def _generate_recommendations(self, report: LearningReport):
        """生成建议"""
        # 找出强项
        for direction, stats in report.by_direction.items():
            if stats.has_enough_samples and stats.win_rate >= 0.3:
                dir_name = {"up": "看涨", "down": "看跌", "range": "震荡"}.get(direction, direction)
                report.strengths.append(f"{dir_name}预测胜率{stats.win_rate*100:.0f}%，表现较好")
        
        for signal, stats in report.by_signal_type.items():
            if stats.has_enough_samples and stats.win_rate >= 0.35:
                report.strengths.append(f"{signal}信号预测胜率{stats.win_rate*100:.0f}%")
        
        # 找出弱项
        for direction, stats in report.by_direction.items():
            if stats.has_enough_samples and stats.win_rate < 0.15:
                dir_name = {"up": "看涨", "down": "看跌", "range": "震荡"}.get(direction, direction)
                report.weaknesses.append(f"{dir_name}预测胜率仅{stats.win_rate*100:.0f}%")
        
        for signal, stats in report.by_signal_type.items():
            if stats.has_enough_samples and stats.win_rate < 0.1:
                report.weaknesses.append(f"{signal}信号预测胜率仅{stats.win_rate*100:.0f}%")
        
        # 生成建议
        if report.overall_win_rate < 0.2:
            report.recommendations.append("整体胜率偏低，建议采用更保守的预测策略")
        
        for pattern in report.error_patterns:
            if pattern.severity == "high":
                report.recommendations.append(pattern.suggestion)
    
    def _calculate_confidence_adjustments(self, report: LearningReport):
        """计算置信度调整系数"""
        adjustments = {}
        
        # 基于方向的调整
        for direction, stats in report.by_direction.items():
            if stats.has_enough_samples:
                if stats.win_rate < 0.15:
                    adjustments[f"direction_{direction}"] = 0.5  # 大幅降低
                elif stats.win_rate < 0.25:
                    adjustments[f"direction_{direction}"] = 0.7  # 适度降低
                elif stats.win_rate >= 0.4:
                    adjustments[f"direction_{direction}"] = 1.1  # 略微提高
        
        # 基于信号的调整
        for signal, stats in report.by_signal_type.items():
            if stats.has_enough_samples:
                if stats.win_rate < 0.1:
                    adjustments[f"signal_{signal}"] = 0.5
                elif stats.win_rate >= 0.35:
                    adjustments[f"signal_{signal}"] = 1.15
        
        report.confidence_adjustments = adjustments
    
    def build_self_awareness_prompt(self, report: LearningReport, current_direction: str = None, current_signal: str = None) -> str:
        """构建自我认知Prompt
        
        参数：
        - report: 学习报告
        - current_direction: 当前预测方向（可选，用于特定警告）
        - current_signal: 当前信号类型（可选）
        
        返回：
        - 注入Prompt的自我认知文本
        """
        lines = []
        lines.append("\n【AI自我认知 - 基于历史表现】")
        lines.append("-" * 50)
        
        # 整体表现
        lines.append(f"你最近的整体表现：")
        lines.append(f"  - 总预测: {report.total_predictions}次")
        lines.append(f"  - 整体胜率: {report.overall_win_rate*100:.1f}%")
        lines.append(f"  - 平均得分: {report.overall_avg_score:.2f}/1.0")
        
        # 按方向表现
        lines.append(f"\n你的方向预测表现：")
        for direction, stats in report.by_direction.items():
            if stats.total >= 5:
                dir_name = {"up": "看涨", "down": "看跌", "range": "震荡"}.get(direction, direction)
                status = "✓" if stats.win_rate >= 0.25 else "✗"
                lines.append(f"  {status} {dir_name}: 胜率{stats.win_rate*100:.0f}% ({stats.total}次)")
                
                # 目标偏差警告
                if stats.target_deviation > 1.0:
                    lines.append(f"      ⚠️ 你的{dir_name}目标平均偏高{stats.target_deviation:.1f}%")
        
        # 错误模式警告
        if report.error_patterns:
            lines.append(f"\n⚠️ 你的常见错误模式：")
            for pattern in report.error_patterns[:3]:  # 最多显示3个
                lines.append(f"  - {pattern.description}")
        
        # 当前场景特定警告
        if current_direction:
            dir_stats = report.by_direction.get(current_direction)
            if dir_stats and dir_stats.has_enough_samples:
                dir_name = {"up": "看涨", "down": "看跌", "range": "震荡"}.get(current_direction, current_direction)
                if dir_stats.win_rate < 0.15:
                    lines.append(f"\n🚨 重要警告：你当前想预测{dir_name}，但你的{dir_name}历史胜率仅{dir_stats.win_rate*100:.0f}%！")
                    lines.append(f"   建议：降低概率或改为观望")
        
        if current_signal:
            sig_stats = report.by_signal_type.get(current_signal)
            if sig_stats and sig_stats.has_enough_samples and sig_stats.win_rate < 0.15:
                lines.append(f"\n🚨 警告：当前信号类型({current_signal})你的历史胜率仅{sig_stats.win_rate*100:.0f}%")
        
        # 行为要求
        lines.append(f"\n【基于以上历史表现，本次分析要求】")
        
        if report.overall_win_rate < 0.2:
            lines.append("1. 你的整体胜率很低，必须采用保守策略")
            lines.append("2. 概率不要超过40%，目标幅度不要超过1.5%")
        else:
            lines.append("1. 参考你的历史表现调整预测置信度")
        
        # 目标约束
        avg_actual = 0
        for stats in report.by_direction.values():
            if stats.avg_actual_move > 0:
                avg_actual = max(avg_actual, stats.avg_actual_move)
        
        if avg_actual > 0:
            lines.append(f"3. 历史实际平均变动约{avg_actual:.1f}%，目标幅度不应超过{avg_actual*1.5:.1f}%")
        
        for rec in report.recommendations[:2]:
            lines.append(f"4. {rec}")
        
        lines.append("-" * 50)
        
        return "\n".join(lines)


def get_learning_feedback(
    days: int = 30,
    symbol: str = None,
    interval: str = None,
    current_direction: str = None,
    current_signal: str = None,
) -> Tuple[str, LearningReport]:
    """获取学习反馈（便捷函数）
    
    返回：
    - (prompt_text, report)
    """
    analyzer = LearningFeedbackAnalyzer()
    report = analyzer.analyze(days=days, symbol=symbol, interval=interval)
    prompt_text = analyzer.build_self_awareness_prompt(report, current_direction, current_signal)
    return prompt_text, report


def format_learning_report(report: LearningReport) -> str:
    """格式化学习报告（用于终端显示）"""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  AI 学习反馈报告")
    lines.append("=" * 70)
    
    # 整体表现
    lines.append(f"\n  【整体表现】")
    lines.append(f"  总预测次数: {report.total_predictions}")
    lines.append(f"  整体胜率: {report.overall_win_rate*100:.1f}%")
    lines.append(f"  平均得分: {report.overall_avg_score:.2f}/1.0")
    
    # 按方向
    lines.append(f"\n  【按方向统计】")
    lines.append(f"  {'方向':<10} {'样本':<8} {'胜率':<10} {'平均分':<10} {'目标偏差'}")
    lines.append("  " + "-" * 55)
    for direction, stats in sorted(report.by_direction.items(), key=lambda x: x[1].win_rate, reverse=True):
        dir_name = {"up": "看涨", "down": "看跌", "range": "震荡"}.get(direction, direction)
        dev_str = f"+{stats.target_deviation:.1f}%" if stats.target_deviation > 0 else f"{stats.target_deviation:.1f}%"
        lines.append(f"  {dir_name:<10} {stats.total:<8} {stats.win_rate*100:>6.1f}%   {stats.avg_score:>6.2f}     {dev_str}")
    
    # 按信号类型
    lines.append(f"\n  【按信号类型统计】")
    lines.append(f"  {'信号':<12} {'样本':<8} {'胜率':<10} {'平均分'}")
    lines.append("  " + "-" * 45)
    for signal, stats in sorted(report.by_signal_type.items(), key=lambda x: x[1].win_rate, reverse=True):
        lines.append(f"  {signal:<12} {stats.total:<8} {stats.win_rate*100:>6.1f}%   {stats.avg_score:>6.2f}")
    
    # 错误模式
    if report.error_patterns:
        lines.append(f"\n  【发现的错误模式】")
        for i, pattern in enumerate(report.error_patterns, 1):
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(pattern.severity, "⚪")
            lines.append(f"  {i}. {severity_icon} {pattern.description}")
            lines.append(f"       建议: {pattern.suggestion}")
    
    # 强项/弱项
    if report.strengths:
        lines.append(f"\n  【强项】")
        for s in report.strengths:
            lines.append(f"  ✓ {s}")
    
    if report.weaknesses:
        lines.append(f"\n  【弱项】")
        for w in report.weaknesses:
            lines.append(f"  ✗ {w}")
    
    # 建议
    if report.recommendations:
        lines.append(f"\n  【改进建议】")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"  {i}. {rec}")
    
    lines.append("\n" + "=" * 70)
    
    return "\n".join(lines)


# ============================================
# CLI 入口
# ============================================

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI学习反馈报告")
    parser.add_argument("--days", type=int, default=30, help="分析最近多少天")
    parser.add_argument("--symbol", type=str, help="过滤交易对")
    parser.add_argument("--interval", type=str, help="过滤周期")
    args = parser.parse_args()
    
    print("\n📊 生成AI学习反馈报告...")
    
    analyzer = LearningFeedbackAnalyzer()
    report = analyzer.analyze(days=args.days, symbol=args.symbol, interval=args.interval)
    
    # 打印报告
    print(format_learning_report(report))
    
    # 打印Prompt示例
    print("\n" + "=" * 70)
    print("  【注入Prompt的自我认知文本示例】")
    print("=" * 70)
    prompt_text = analyzer.build_self_awareness_prompt(report, current_direction="up")
    print(prompt_text)


if __name__ == "__main__":
    main()
