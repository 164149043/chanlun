# -*- coding: utf-8 -*-
"""回测验证模块

验证AI自我学习系统的有效性：
1. 模拟置信度约束的历史效果
2. 对比有/无历史上下文的表现
3. 生成A/B测试报告
4. 计算改进幅度
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
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
import statistics

import matplotlib.pyplot as plt
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

DB_PATH = Path(__file__).parent / "chanlun_ai.db"
OUTPUT_DIR = Path(__file__).parent / "output"


@dataclass
class BacktestResult:
    """回测结果"""
    name: str
    total: int = 0
    wins: int = 0
    losses: int = 0
    stopped: int = 0
    avg_score: float = 0.0
    avg_profit: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    
    @property
    def win_rate(self) -> float:
        return self.wins / self.total * 100 if self.total > 0 else 0
    
    @property
    def stop_rate(self) -> float:
        return self.stopped / self.total * 100 if self.total > 0 else 0


@dataclass
class ABTestReport:
    """A/B测试报告"""
    baseline: BacktestResult
    improved: BacktestResult
    improvement_pct: Dict[str, float] = field(default_factory=dict)
    statistical_significance: Dict[str, bool] = field(default_factory=dict)


class BacktestValidator:
    """回测验证器"""
    
    def __init__(self, db_path: Path = DB_PATH, output_dir: Path = OUTPUT_DIR):
        self.db_path = db_path
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
    
    def _fetch_records(self, days: int = None) -> List[Dict]:
        """获取评估记录"""
        conn = self._get_conn()
        
        query = """
            SELECT id, symbol, interval, timestamp, price, 
                   ai_json, outcome_json, chanlun_json
            FROM analysis_snapshot
            WHERE evaluated = 1 AND ai_json IS NOT NULL AND outcome_json IS NOT NULL
        """
        params = []
        
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            query += " AND timestamp >= ?"
            params.append(cutoff.isoformat())
        
        query += " ORDER BY timestamp ASC"
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        
        records = []
        for rid, symbol, interval, timestamp, price, ai_str, outcome_str, chanlun_str in rows:
            try:
                ai = json.loads(ai_str) if ai_str else {}
                outcome = json.loads(outcome_str)
                chanlun = json.loads(chanlun_str) if chanlun_str else {}
            except:
                continue
            
            records.append({
                "id": rid,
                "symbol": symbol,
                "interval": interval,
                "timestamp": timestamp,
                "price": float(price) if price else 0,
                "ai": ai,
                "outcome": outcome,
                "chanlun": chanlun
            })
        
        return records
    
    def _calculate_historical_winrate(self, records: List[Dict], current_index: int, 
                                       direction: str = None, lookback: int = 20) -> float:
        """计算历史胜率（截至当前记录之前）"""
        start_idx = max(0, current_index - lookback)
        historical = records[start_idx:current_index]
        
        if not historical:
            return 0.5  # 无历史数据，返回50%
        
        if direction:
            historical = [r for r in historical 
                         if r["outcome"].get("direction") == direction]
        
        if not historical:
            return 0.5
        
        wins = sum(1 for r in historical if r["outcome"].get("hit_target"))
        return wins / len(historical)
    
    def _simulate_confidence_constraint(self, record: Dict, historical_winrate: float) -> Dict:
        """模拟置信度约束效果"""
        ai = record["ai"]
        outcome = record["outcome"]
        primary = ai.get("primary_scenario", {})
        
        original_prob = primary.get("probability", 0.5)
        original_target = primary.get("target_pct", 3.0)
        original_stop = primary.get("stop_pct", 2.0)
        
        # 模拟约束规则
        adjusted_prob = original_prob
        adjusted_target = original_target
        adjusted_stop = original_stop
        
        # 规则1：历史胜率<20%，降低概率和目标
        if historical_winrate < 0.2:
            adjusted_prob = original_prob * 0.7
            adjusted_target = original_target * 0.8
        # 规则2：历史胜率<10%，大幅降低
        elif historical_winrate < 0.1:
            adjusted_prob = original_prob * 0.5
            adjusted_target = original_target * 0.6
        # 规则3：历史胜率>40%，可提高
        elif historical_winrate > 0.4:
            adjusted_prob = min(0.8, original_prob * 1.1)
        
        # 规则4：确保盈亏比≥1.5
        if adjusted_target / adjusted_stop < 1.5:
            adjusted_stop = adjusted_target / 1.5
        
        return {
            "original": {
                "probability": original_prob,
                "target_pct": original_target,
                "stop_pct": original_stop
            },
            "adjusted": {
                "probability": adjusted_prob,
                "target_pct": adjusted_target,
                "stop_pct": adjusted_stop
            },
            "historical_winrate": historical_winrate
        }
    
    def _evaluate_with_constraint(self, record: Dict, constraint: Dict) -> Dict:
        """使用约束后重新评估结果"""
        outcome = record["outcome"]
        adjusted = constraint["adjusted"]
        
        max_favorable = outcome.get("max_favorable_move", 0)
        max_adverse = outcome.get("max_adverse_move", 0)
        
        # 使用调整后的目标和止损判断
        adjusted_target = adjusted["target_pct"]
        adjusted_stop = adjusted["stop_pct"]
        
        hit_target = max_favorable >= adjusted_target
        hit_stop = max_adverse >= adjusted_stop
        
        # 重新计算得分
        if hit_target and not hit_stop:
            score = 1.0
            result = "success"
        elif hit_stop:
            score = 0.0
            result = "stopped"
        elif outcome.get("direction") in ["up", "down"]:
            final = outcome.get("final_move", 0)
            direction = outcome.get("direction")
            if (direction == "up" and final > 0) or (direction == "down" and final < 0):
                score = 0.5
                result = "partial"
            else:
                score = 0.0
                result = "failed"
        else:
            score = 0.0
            result = "no_direction"
        
        return {
            "hit_target": hit_target,
            "hit_stop": hit_stop,
            "score": score,
            "result": result
        }
    
    def run_baseline_backtest(self, records: List[Dict]) -> BacktestResult:
        """运行基准回测（原始预测）"""
        result = BacktestResult(name="基准策略")
        scores = []
        profits = []
        
        for rec in records:
            outcome = rec["outcome"]
            result.total += 1
            
            if outcome.get("hit_target"):
                result.wins += 1
            else:
                result.losses += 1
            
            if outcome.get("hit_stop"):
                result.stopped += 1
            
            scores.append(outcome.get("score", 0))
            profits.append(outcome.get("final_move", 0))
        
        if scores:
            result.avg_score = statistics.mean(scores)
        if profits:
            result.avg_profit = statistics.mean(profits)
            if len(profits) > 1:
                result.sharpe_ratio = statistics.mean(profits) / statistics.stdev(profits) if statistics.stdev(profits) > 0 else 0
        
        return result
    
    def run_constrained_backtest(self, records: List[Dict], lookback: int = 20) -> BacktestResult:
        """运行约束后的回测"""
        result = BacktestResult(name="约束策略")
        scores = []
        profits = []
        
        for i, rec in enumerate(records):
            outcome = rec["outcome"]
            direction = outcome.get("direction")
            
            # 计算历史胜率
            hist_winrate = self._calculate_historical_winrate(records, i, direction, lookback)
            
            # 模拟约束
            constraint = self._simulate_confidence_constraint(rec, hist_winrate)
            
            # 重新评估
            new_eval = self._evaluate_with_constraint(rec, constraint)
            
            result.total += 1
            
            if new_eval["hit_target"]:
                result.wins += 1
            else:
                result.losses += 1
            
            if new_eval["hit_stop"]:
                result.stopped += 1
            
            scores.append(new_eval["score"])
            profits.append(outcome.get("final_move", 0))
        
        if scores:
            result.avg_score = statistics.mean(scores)
        if profits:
            result.avg_profit = statistics.mean(profits)
            if len(profits) > 1:
                result.sharpe_ratio = statistics.mean(profits) / statistics.stdev(profits) if statistics.stdev(profits) > 0 else 0
        
        return result
    
    def run_filtered_backtest(self, records: List[Dict], 
                               min_winrate: float = 0.3,
                               min_prob: float = 0.5) -> BacktestResult:
        """运行过滤策略回测（只执行高置信度交易）"""
        result = BacktestResult(name="过滤策略")
        scores = []
        profits = []
        skipped = 0
        
        for i, rec in enumerate(records):
            outcome = rec["outcome"]
            direction = outcome.get("direction")
            primary = rec["ai"].get("primary_scenario", {})
            
            # 计算历史胜率
            hist_winrate = self._calculate_historical_winrate(records, i, direction, 20)
            
            # 过滤条件
            prob = primary.get("probability", 0.5)
            if hist_winrate < min_winrate or prob < min_prob:
                skipped += 1
                continue
            
            result.total += 1
            
            if outcome.get("hit_target"):
                result.wins += 1
            else:
                result.losses += 1
            
            if outcome.get("hit_stop"):
                result.stopped += 1
            
            scores.append(outcome.get("score", 0))
            profits.append(outcome.get("final_move", 0))
        
        if scores:
            result.avg_score = statistics.mean(scores)
        if profits:
            result.avg_profit = statistics.mean(profits)
        
        print(f"  过滤策略：跳过 {skipped} 条低置信度预测")
        
        return result
    
    def run_ab_test(self, days: int = 90) -> ABTestReport:
        """运行A/B测试"""
        records = self._fetch_records(days)
        
        if len(records) < 20:
            print(f"数据不足：只有 {len(records)} 条记录")
            return None
        
        print(f"\n{'='*60}")
        print(f"📊 回测验证 - A/B测试 (最近{days}天, N={len(records)})")
        print(f"{'='*60}")
        
        # 运行基准回测
        print("\n1️⃣  基准策略回测...")
        baseline = self.run_baseline_backtest(records)
        
        # 运行约束回测
        print("2️⃣  约束策略回测...")
        constrained = self.run_constrained_backtest(records)
        
        # 运行过滤回测
        print("3️⃣  过滤策略回测...")
        filtered = self.run_filtered_backtest(records)
        
        # 创建报告
        report = ABTestReport(baseline=baseline, improved=constrained)
        
        # 计算改进幅度
        if baseline.win_rate > 0:
            report.improvement_pct["win_rate"] = (constrained.win_rate - baseline.win_rate) / baseline.win_rate * 100
        if baseline.avg_score > 0:
            report.improvement_pct["avg_score"] = (constrained.avg_score - baseline.avg_score) / baseline.avg_score * 100
        if baseline.stop_rate > 0:
            report.improvement_pct["stop_rate"] = (baseline.stop_rate - constrained.stop_rate) / baseline.stop_rate * 100
        
        # 输出结果
        self._print_ab_report(baseline, constrained, filtered, report)
        
        return report
    
    def _print_ab_report(self, baseline: BacktestResult, constrained: BacktestResult, 
                         filtered: BacktestResult, report: ABTestReport):
        """打印A/B测试报告"""
        print(f"\n{'='*60}")
        print("📈 回测结果对比")
        print(f"{'='*60}")
        
        print(f"\n{'指标':<15} {'基准策略':>12} {'约束策略':>12} {'过滤策略':>12} {'改进幅度':>12}")
        print("-" * 65)
        
        # 胜率
        imp = report.improvement_pct.get("win_rate", 0)
        imp_str = f"{'+' if imp > 0 else ''}{imp:.1f}%" if imp != 0 else "-"
        print(f"{'胜率':<15} {baseline.win_rate:>11.1f}% {constrained.win_rate:>11.1f}% {filtered.win_rate:>11.1f}% {imp_str:>12}")
        
        # 止损率
        imp = report.improvement_pct.get("stop_rate", 0)
        imp_str = f"{'+' if imp > 0 else ''}{imp:.1f}%" if imp != 0 else "-"
        print(f"{'止损率':<15} {baseline.stop_rate:>11.1f}% {constrained.stop_rate:>11.1f}% {filtered.stop_rate:>11.1f}% {imp_str:>12}")
        
        # 平均得分
        imp = report.improvement_pct.get("avg_score", 0)
        imp_str = f"{'+' if imp > 0 else ''}{imp:.1f}%" if imp != 0 else "-"
        print(f"{'平均得分':<15} {baseline.avg_score:>12.3f} {constrained.avg_score:>12.3f} {filtered.avg_score:>12.3f} {imp_str:>12}")
        
        # 样本数
        print(f"{'样本数':<15} {baseline.total:>12} {constrained.total:>12} {filtered.total:>12} {'-':>12}")
        
        print(f"\n{'='*60}")
        print("📋 结论")
        print(f"{'='*60}")
        
        # 判断改进效果
        win_imp = report.improvement_pct.get("win_rate", 0)
        score_imp = report.improvement_pct.get("avg_score", 0)
        
        if win_imp > 5:
            print("✅ 置信度约束显著提升了胜率")
        elif win_imp > 0:
            print("✓ 置信度约束略微提升了胜率")
        elif win_imp < -5:
            print("⚠️  置信度约束降低了胜率，建议调整参数")
        else:
            print("→ 置信度约束对胜率影响不明显")
        
        if filtered.total > 0 and filtered.win_rate > baseline.win_rate + 10:
            print(f"✅ 过滤策略表现更优：胜率提升 {filtered.win_rate - baseline.win_rate:.1f}%")
            print(f"   建议：只执行高置信度预测 (跳过 {baseline.total - filtered.total} 条)")
    
    def plot_backtest_comparison(self, days: int = 90) -> str:
        """绘制回测对比图"""
        records = self._fetch_records(days)
        
        if len(records) < 20:
            print(f"数据不足：只有 {len(records)} 条记录")
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'回测验证对比 (最近{days}天, N={len(records)})', fontsize=14, fontweight='bold')
        
        # 计算滚动数据
        window = max(10, len(records) // 10)
        
        baseline_winrates = []
        constrained_winrates = []
        filtered_winrates = []
        
        for i in range(window, len(records)):
            window_records = records[i-window:i]
            
            # 基准
            baseline_wins = sum(1 for r in window_records if r["outcome"].get("hit_target"))
            baseline_winrates.append(baseline_wins / window * 100)
            
            # 约束
            constrained_wins = 0
            for j, rec in enumerate(window_records):
                direction = rec["outcome"].get("direction")
                hist_wr = self._calculate_historical_winrate(records, i-window+j, direction, 20)
                constraint = self._simulate_confidence_constraint(rec, hist_wr)
                new_eval = self._evaluate_with_constraint(rec, constraint)
                if new_eval["hit_target"]:
                    constrained_wins += 1
            constrained_winrates.append(constrained_wins / window * 100)
            
            # 过滤
            filtered_total = 0
            filtered_wins = 0
            for j, rec in enumerate(window_records):
                direction = rec["outcome"].get("direction")
                hist_wr = self._calculate_historical_winrate(records, i-window+j, direction, 20)
                prob = rec["ai"].get("primary_scenario", {}).get("probability", 0.5)
                if hist_wr >= 0.3 and prob >= 0.5:
                    filtered_total += 1
                    if rec["outcome"].get("hit_target"):
                        filtered_wins += 1
            if filtered_total > 0:
                filtered_winrates.append(filtered_wins / filtered_total * 100)
            else:
                filtered_winrates.append(filtered_winrates[-1] if filtered_winrates else 50)
        
        x = list(range(len(baseline_winrates)))
        
        # 1. 滚动胜率对比
        ax1 = axes[0, 0]
        ax1.plot(x, baseline_winrates, 'b-', label='基准策略', alpha=0.7)
        ax1.plot(x, constrained_winrates, 'g-', label='约束策略', alpha=0.7)
        ax1.plot(x, filtered_winrates, 'r-', label='过滤策略', alpha=0.7)
        ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
        ax1.set_xlabel('时间序列')
        ax1.set_ylabel('滚动胜率 (%)')
        ax1.set_title(f'滚动胜率对比 (窗口={window})')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 策略对比柱状图
        ax2 = axes[0, 1]
        strategies = ['基准策略', '约束策略', '过滤策略']
        final_winrates = [
            np.mean(baseline_winrates),
            np.mean(constrained_winrates),
            np.mean(filtered_winrates)
        ]
        colors = ['#3498db', '#27ae60', '#e74c3c']
        bars = ax2.bar(strategies, final_winrates, color=colors)
        ax2.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
        ax2.set_ylabel('平均胜率 (%)')
        ax2.set_title('策略平均胜率对比')
        ax2.set_ylim(0, 100)
        
        for bar, wr in zip(bars, final_winrates):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{wr:.1f}%', ha='center', fontsize=10)
        
        # 3. 累计收益曲线
        ax3 = axes[1, 0]
        baseline_cumsum = np.cumsum([r["outcome"].get("final_move", 0) for r in records])
        ax3.plot(baseline_cumsum, 'b-', label='基准策略', alpha=0.7)
        ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax3.set_xlabel('交易序号')
        ax3.set_ylabel('累计收益 (%)')
        ax3.set_title('累计收益曲线')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. 置信度约束效果
        ax4 = axes[1, 1]
        
        # 统计不同历史胜率区间的实际表现
        bins = [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 1.0)]
        bin_labels = ['<20%', '20-40%', '40-60%', '>60%']
        bin_winrates = []
        bin_counts = []
        
        for low, high in bins:
            bin_records = []
            for i, rec in enumerate(records):
                direction = rec["outcome"].get("direction")
                hist_wr = self._calculate_historical_winrate(records, i, direction, 20)
                if low <= hist_wr < high:
                    bin_records.append(rec)
            
            if bin_records:
                wins = sum(1 for r in bin_records if r["outcome"].get("hit_target"))
                bin_winrates.append(wins / len(bin_records) * 100)
                bin_counts.append(len(bin_records))
            else:
                bin_winrates.append(0)
                bin_counts.append(0)
        
        bars = ax4.bar(bin_labels, bin_winrates, color='#9b59b6')
        ax4.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
        ax4.set_xlabel('历史胜率区间')
        ax4.set_ylabel('实际胜率 (%)')
        ax4.set_title('历史胜率 vs 实际表现')
        ax4.set_ylim(0, 100)
        
        for bar, wr, cnt in zip(bars, bin_winrates, bin_counts):
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{wr:.0f}%\n(n={cnt})', ha='center', fontsize=9)
        
        plt.tight_layout()
        
        output_path = self.output_dir / f"backtest_comparison_{datetime.now().strftime('%Y%m%d')}.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 回测对比图已保存: {output_path}")
        return str(output_path)
    
    def run_full_validation(self, days: int = 90) -> Dict[str, Any]:
        """运行完整验证"""
        print(f"\n{'='*60}")
        print(f"🔬 AI自我学习系统 - 完整回测验证")
        print(f"{'='*60}")
        
        # 运行A/B测试
        report = self.run_ab_test(days)
        
        # 生成可视化
        print(f"\n📊 生成可视化图表...")
        chart_path = self.plot_backtest_comparison(days)
        
        return {
            "report": report,
            "chart_path": chart_path
        }


def run_backtest_validation(days: int = 90):
    """运行回测验证"""
    validator = BacktestValidator()
    return validator.run_full_validation(days)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="回测验证")
    parser.add_argument("--days", type=int, default=90, help="验证最近多少天")
    
    args = parser.parse_args()
    
    run_backtest_validation(args.days)
