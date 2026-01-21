# -*- coding: utf-8 -*-
"""AI学习报告可视化模块

生成直观的AI表现图表：
1. 按方向/信号类型/周期的胜率对比
2. 目标偏差分析图
3. 学习曲线（滚动胜率趋势）
4. 错误模式分布
5. 置信度约束效果对比
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
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

DB_PATH = Path(__file__).parent / "chanlun_ai.db"
OUTPUT_DIR = Path(__file__).parent / "output"


class LearningVisualizer:
    """学习报告可视化器"""
    
    def __init__(self, db_path: Path = DB_PATH, output_dir: Path = OUTPUT_DIR):
        self.db_path = db_path
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
    
    def _fetch_records(self, days: int = 90) -> List[Dict]:
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
    
    def _classify_signal(self, ai: dict, chanlun: dict) -> str:
        """分类信号类型"""
        source = chanlun if chanlun else ai
        signal = source.get("signal", {})
        buy_sell_points = signal.get("buy_sell_points", [])
        divergences = signal.get("divergences", [])
        
        if not buy_sell_points and not divergences:
            return "无信号"
        
        for s in buy_sell_points:
            sl = s.lower()
            if "1buy" in sl: return "一买"
            elif "2buy" in sl: return "二买"
            elif "3buy" in sl: return "三买"
            elif "1sell" in sl: return "一卖"
            elif "2sell" in sl: return "二卖"
            elif "3sell" in sl: return "三卖"
        
        if divergences:
            for d in divergences:
                dl = d.lower()
                if "bottom" in dl or "底" in d: return "底背驰"
                elif "top" in dl or "顶" in d: return "顶背驰"
        
        return "混合信号"
    
    def plot_performance_dashboard(self, days: int = 90) -> str:
        """生成完整的表现仪表盘"""
        records = self._fetch_records(days)
        
        if len(records) < 5:
            print(f"数据不足：只有 {len(records)} 条记录")
            return None
        
        fig = plt.figure(figsize=(16, 12))
        fig.suptitle(f'AI学习表现仪表盘 (最近{days}天, N={len(records)})', 
                     fontsize=14, fontweight='bold')
        
        # 创建子图网格
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # 1. 按方向胜率 (左上)
        ax1 = fig.add_subplot(gs[0, 0])
        self._plot_direction_winrate(records, ax1)
        
        # 2. 按信号类型胜率 (中上)
        ax2 = fig.add_subplot(gs[0, 1])
        self._plot_signal_winrate(records, ax2)
        
        # 3. 按周期胜率 (右上)
        ax3 = fig.add_subplot(gs[0, 2])
        self._plot_interval_winrate(records, ax3)
        
        # 4. 目标偏差分析 (左中)
        ax4 = fig.add_subplot(gs[1, 0])
        self._plot_target_deviation(records, ax4)
        
        # 5. 得分分布 (中中)
        ax5 = fig.add_subplot(gs[1, 1])
        self._plot_score_distribution(records, ax5)
        
        # 6. 盈亏比分布 (右中)
        ax6 = fig.add_subplot(gs[1, 2])
        self._plot_risk_reward(records, ax6)
        
        # 7. 学习曲线 (底部横跨)
        ax7 = fig.add_subplot(gs[2, :])
        self._plot_learning_curve(records, ax7)
        
        plt.tight_layout()
        
        output_path = self.output_dir / f"learning_dashboard_{datetime.now().strftime('%Y%m%d')}.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 仪表盘已保存: {output_path}")
        return str(output_path)
    
    def _plot_direction_winrate(self, records: List[Dict], ax):
        """绘制按方向的胜率"""
        direction_map = {"up": "看涨", "down": "看跌", "sideways": "震荡"}
        stats = defaultdict(lambda: {"total": 0, "wins": 0})
        
        for rec in records:
            outcome = rec["outcome"]
            direction = outcome.get("direction", "unknown")
            display_dir = direction_map.get(direction, direction)
            stats[display_dir]["total"] += 1
            if outcome.get("hit_target"):
                stats[display_dir]["wins"] += 1
        
        dirs = list(stats.keys())
        totals = [stats[d]["total"] for d in dirs]
        win_rates = [stats[d]["wins"] / stats[d]["total"] * 100 
                     if stats[d]["total"] > 0 else 0 for d in dirs]
        
        colors = ['#27ae60' if d == '看涨' else '#e74c3c' if d == '看跌' else '#95a5a6' 
                  for d in dirs]
        
        bars = ax.bar(dirs, win_rates, color=colors, edgecolor='black', linewidth=0.5)
        ax.set_ylabel('胜率 (%)')
        ax.set_title('按预测方向')
        ax.set_ylim(0, 100)
        ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='50%基准')
        
        # 标注数值
        for bar, total, wr in zip(bars, totals, win_rates):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                   f'{wr:.1f}%\n(n={total})', ha='center', va='bottom', fontsize=9)
    
    def _plot_signal_winrate(self, records: List[Dict], ax):
        """绘制按信号类型的胜率"""
        stats = defaultdict(lambda: {"total": 0, "wins": 0})
        
        for rec in records:
            signal = self._classify_signal(rec["ai"], rec["chanlun"])
            stats[signal]["total"] += 1
            if rec["outcome"].get("hit_target"):
                stats[signal]["wins"] += 1
        
        # 排序：按样本数量
        sorted_signals = sorted(stats.keys(), key=lambda x: stats[x]["total"], reverse=True)
        
        if len(sorted_signals) > 8:
            sorted_signals = sorted_signals[:8]
        
        signals = sorted_signals
        totals = [stats[s]["total"] for s in signals]
        win_rates = [stats[s]["wins"] / stats[s]["total"] * 100 
                     if stats[s]["total"] > 0 else 0 for s in signals]
        
        # 颜色：买入信号绿色，卖出信号红色
        colors = []
        for s in signals:
            if '买' in s or 'buy' in s.lower():
                colors.append('#27ae60')
            elif '卖' in s or 'sell' in s.lower():
                colors.append('#e74c3c')
            else:
                colors.append('#3498db')
        
        bars = ax.barh(signals, win_rates, color=colors, edgecolor='black', linewidth=0.5)
        ax.set_xlabel('胜率 (%)')
        ax.set_title('按信号类型')
        ax.set_xlim(0, 100)
        ax.axvline(x=50, color='gray', linestyle='--', alpha=0.5)
        
        # 标注数值
        for bar, total, wr in zip(bars, totals, win_rates):
            ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                   f'{wr:.0f}% (n={total})', va='center', fontsize=8)
    
    def _plot_interval_winrate(self, records: List[Dict], ax):
        """绘制按周期的胜率"""
        stats = defaultdict(lambda: {"total": 0, "wins": 0})
        
        for rec in records:
            interval = rec["interval"]
            stats[interval]["total"] += 1
            if rec["outcome"].get("hit_target"):
                stats[interval]["wins"] += 1
        
        # 按周期排序
        interval_order = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        sorted_intervals = sorted(stats.keys(), 
                                  key=lambda x: interval_order.index(x) if x in interval_order else 99)
        
        intervals = sorted_intervals
        totals = [stats[i]["total"] for i in intervals]
        win_rates = [stats[i]["wins"] / stats[i]["total"] * 100 
                     if stats[i]["total"] > 0 else 0 for i in intervals]
        
        bars = ax.bar(intervals, win_rates, color='#3498db', edgecolor='black', linewidth=0.5)
        ax.set_ylabel('胜率 (%)')
        ax.set_title('按时间周期')
        ax.set_ylim(0, 100)
        ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
        
        # 标注数值
        for bar, total, wr in zip(bars, totals, win_rates):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                   f'{wr:.0f}%\n(n={total})', ha='center', va='bottom', fontsize=8)
    
    def _plot_target_deviation(self, records: List[Dict], ax):
        """绘制目标偏差分析"""
        targets = []
        actuals = []
        colors = []
        
        for rec in records:
            primary = rec["ai"].get("primary_scenario", {})
            target_pct = primary.get("target_pct", 0)
            max_favorable = rec["outcome"].get("max_favorable_move", 0)
            
            if target_pct > 0 and target_pct < 50:  # 过滤异常值
                targets.append(target_pct)
                actuals.append(max_favorable)
                colors.append('#27ae60' if rec["outcome"].get("hit_target") else '#e74c3c')
        
        if not targets:
            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
            return
        
        ax.scatter(targets, actuals, c=colors, alpha=0.6, s=30)
        
        # 绘制理想线（目标=实际）
        max_val = max(max(targets), max(actuals)) * 1.1
        ax.plot([0, max_val], [0, max_val], 'k--', alpha=0.5, label='目标=实际')
        
        # 标注区域
        ax.fill_between([0, max_val], [0, max_val], [0, 0], alpha=0.1, color='red', label='目标过高')
        ax.fill_between([0, max_val], [0, max_val], [max_val, max_val], alpha=0.1, color='green', label='目标保守')
        
        ax.set_xlabel('预测目标 (%)')
        ax.set_ylabel('实际最大变动 (%)')
        ax.set_title('目标偏差分析')
        ax.legend(loc='upper left', fontsize=8)
        
        # 计算平均偏差
        avg_deviation = np.mean([t - a for t, a in zip(targets, actuals)])
        ax.text(0.95, 0.05, f'平均偏差: {avg_deviation:.2f}%', 
               transform=ax.transAxes, ha='right', fontsize=9,
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    def _plot_score_distribution(self, records: List[Dict], ax):
        """绘制得分分布"""
        scores = [rec["outcome"].get("score", 0) for rec in records]
        
        if not scores:
            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
            return
        
        bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        counts, _, patches = ax.hist(scores, bins=bins, edgecolor='black', linewidth=0.5)
        
        # 颜色渐变
        for i, patch in enumerate(patches):
            if i < 3:
                patch.set_facecolor('#e74c3c')
            elif i < 5:
                patch.set_facecolor('#f39c12')
            elif i < 7:
                patch.set_facecolor('#3498db')
            else:
                patch.set_facecolor('#27ae60')
        
        ax.set_xlabel('得分')
        ax.set_ylabel('数量')
        ax.set_title('得分分布')
        
        avg_score = np.mean(scores)
        ax.axvline(x=avg_score, color='red', linestyle='-', linewidth=2, label=f'平均={avg_score:.2f}')
        ax.legend(loc='upper right', fontsize=9)
    
    def _plot_risk_reward(self, records: List[Dict], ax):
        """绘制盈亏比分布"""
        risk_rewards = []
        hit_targets = []
        
        for rec in records:
            outcome = rec["outcome"]
            favorable = outcome.get("max_favorable_move", 0)
            adverse = outcome.get("max_adverse_move", 0)
            
            if adverse > 0:
                rr = favorable / adverse
                if rr < 10:  # 过滤异常
                    risk_rewards.append(rr)
                    hit_targets.append(outcome.get("hit_target", False))
        
        if not risk_rewards:
            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
            return
        
        colors = ['#27ae60' if h else '#e74c3c' for h in hit_targets]
        
        ax.scatter(range(len(risk_rewards)), risk_rewards, c=colors, alpha=0.6, s=20)
        ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5, label='盈亏比=1')
        ax.axhline(y=1.5, color='green', linestyle='--', alpha=0.5, label='盈亏比=1.5')
        
        avg_rr = np.mean(risk_rewards)
        ax.axhline(y=avg_rr, color='blue', linestyle='-', linewidth=2, label=f'平均={avg_rr:.2f}')
        
        ax.set_xlabel('预测序号')
        ax.set_ylabel('盈亏比')
        ax.set_title('实际盈亏比分布')
        ax.legend(loc='upper right', fontsize=8)
        ax.set_ylim(0, min(max(risk_rewards) * 1.1, 5))
    
    def _plot_learning_curve(self, records: List[Dict], ax):
        """绘制学习曲线"""
        if len(records) < 10:
            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
            return
        
        # 计算滚动胜率
        window_size = max(10, len(records) // 10)
        
        timestamps = []
        rolling_winrates = []
        rolling_scores = []
        
        for i in range(window_size, len(records)):
            window = records[i-window_size:i]
            wins = sum(1 for r in window if r["outcome"].get("hit_target"))
            scores = [r["outcome"].get("score", 0) for r in window]
            
            timestamps.append(i)
            rolling_winrates.append(wins / window_size * 100)
            rolling_scores.append(np.mean(scores) * 100)
        
        ax.plot(timestamps, rolling_winrates, 'b-', linewidth=2, label=f'滚动胜率 (窗口={window_size})')
        ax.plot(timestamps, rolling_scores, 'g-', linewidth=2, alpha=0.7, label='滚动得分×100')
        
        # 基准线
        ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='50%基准')
        
        # 趋势线
        if len(timestamps) > 2:
            z = np.polyfit(timestamps, rolling_winrates, 1)
            p = np.poly1d(z)
            ax.plot(timestamps, p(timestamps), 'r--', linewidth=1, alpha=0.7, 
                   label=f'趋势 ({z[0]:.3f}/样本)')
        
        ax.set_xlabel('预测序号')
        ax.set_ylabel('胜率/得分 (%)')
        ax.set_title('学习曲线 (滚动指标趋势)')
        ax.legend(loc='upper left', fontsize=9)
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)
        
        # 显示总体统计
        total_wins = sum(1 for r in records if r["outcome"].get("hit_target"))
        total_winrate = total_wins / len(records) * 100
        ax.text(0.98, 0.95, f'总体胜率: {total_winrate:.1f}% (N={len(records)})', 
               transform=ax.transAxes, ha='right', va='top', fontsize=10,
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    def plot_error_patterns(self, days: int = 90) -> str:
        """绘制错误模式分析图"""
        records = self._fetch_records(days)
        
        if len(records) < 10:
            print(f"数据不足：只有 {len(records)} 条记录")
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'AI错误模式分析 (最近{days}天)', fontsize=14, fontweight='bold')
        
        # 1. 失败案例分析
        ax1 = axes[0, 0]
        self._plot_failure_analysis(records, ax1)
        
        # 2. 方向错误分析
        ax2 = axes[0, 1]
        self._plot_direction_errors(records, ax2)
        
        # 3. 时间分布
        ax3 = axes[1, 0]
        self._plot_time_distribution(records, ax3)
        
        # 4. 错误类型分布
        ax4 = axes[1, 1]
        self._plot_error_types(records, ax4)
        
        plt.tight_layout()
        
        output_path = self.output_dir / f"error_patterns_{datetime.now().strftime('%Y%m%d')}.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 错误模式图已保存: {output_path}")
        return str(output_path)
    
    def _plot_failure_analysis(self, records: List[Dict], ax):
        """绘制失败案例分析"""
        failures = [r for r in records if not r["outcome"].get("hit_target")]
        
        # 按失败原因分类
        reasons = defaultdict(int)
        for r in failures:
            outcome = r["outcome"]
            if outcome.get("hit_stop"):
                reasons["触发止损"] += 1
            elif outcome.get("direction") == "unknown":
                reasons["方向不明"] += 1
            else:
                direction = outcome.get("direction")
                final = outcome.get("final_move", 0)
                if (direction == "up" and final < 0) or (direction == "down" and final > 0):
                    reasons["方向错误"] += 1
                else:
                    reasons["未达目标"] += 1
        
        if not reasons:
            ax.text(0.5, 0.5, '无失败案例', ha='center', va='center', transform=ax.transAxes)
            return
        
        labels = list(reasons.keys())
        sizes = list(reasons.values())
        colors = ['#e74c3c', '#f39c12', '#9b59b6', '#95a5a6']
        
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                          colors=colors[:len(labels)],
                                          explode=[0.05] * len(labels))
        ax.set_title(f'失败原因分布 (N={len(failures)})')
    
    def _plot_direction_errors(self, records: List[Dict], ax):
        """绘制方向预测错误分析"""
        direction_map = {"up": "看涨", "down": "看跌"}
        
        # 统计方向预测正确性
        direction_stats = defaultdict(lambda: {"correct": 0, "wrong": 0})
        
        for r in records:
            outcome = r["outcome"]
            direction = outcome.get("direction")
            if direction not in ["up", "down"]:
                continue
            
            final_move = outcome.get("final_move", 0)
            is_correct = (direction == "up" and final_move > 0) or (direction == "down" and final_move < 0)
            
            display_dir = direction_map.get(direction, direction)
            if is_correct:
                direction_stats[display_dir]["correct"] += 1
            else:
                direction_stats[display_dir]["wrong"] += 1
        
        if not direction_stats:
            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
            return
        
        dirs = list(direction_stats.keys())
        correct = [direction_stats[d]["correct"] for d in dirs]
        wrong = [direction_stats[d]["wrong"] for d in dirs]
        
        x = np.arange(len(dirs))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, correct, width, label='正确', color='#27ae60')
        bars2 = ax.bar(x + width/2, wrong, width, label='错误', color='#e74c3c')
        
        ax.set_ylabel('数量')
        ax.set_title('方向预测正确性')
        ax.set_xticks(x)
        ax.set_xticklabels(dirs)
        ax.legend()
        
        # 标注正确率
        for i, d in enumerate(dirs):
            total = correct[i] + wrong[i]
            if total > 0:
                rate = correct[i] / total * 100
                ax.text(i, max(correct[i], wrong[i]) + 1, f'{rate:.0f}%', ha='center', fontsize=10)
    
    def _plot_time_distribution(self, records: List[Dict], ax):
        """绘制时间分布"""
        success_hours = []
        failure_hours = []
        
        for r in records:
            try:
                ts = datetime.fromisoformat(r["timestamp"].replace('Z', '+00:00'))
                hour = ts.hour
                if r["outcome"].get("hit_target"):
                    success_hours.append(hour)
                else:
                    failure_hours.append(hour)
            except:
                continue
        
        if not success_hours and not failure_hours:
            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
            return
        
        hours = list(range(24))
        success_counts = [success_hours.count(h) for h in hours]
        failure_counts = [failure_hours.count(h) for h in hours]
        
        ax.bar(hours, success_counts, label='成功', color='#27ae60', alpha=0.7)
        ax.bar(hours, failure_counts, bottom=success_counts, label='失败', color='#e74c3c', alpha=0.7)
        
        ax.set_xlabel('小时 (UTC)')
        ax.set_ylabel('数量')
        ax.set_title('预测时间分布')
        ax.legend()
        ax.set_xticks(range(0, 24, 2))
    
    def _plot_error_types(self, records: List[Dict], ax):
        """绘制错误类型统计"""
        error_types = defaultdict(int)
        
        for r in records:
            outcome = r["outcome"]
            if outcome.get("hit_target"):
                continue
            
            primary = r["ai"].get("primary_scenario", {})
            target_pct = primary.get("target_pct", 0)
            stop_pct = primary.get("stop_pct", 0)
            max_favorable = outcome.get("max_favorable_move", 0)
            
            # 分类错误类型
            if outcome.get("hit_stop"):
                error_types["止损触发"] += 1
            elif target_pct > 0 and max_favorable > target_pct * 0.5:
                error_types["接近目标"] += 1
            elif target_pct > max_favorable * 2:
                error_types["目标过高"] += 1
            else:
                error_types["其他"] += 1
        
        if not error_types:
            ax.text(0.5, 0.5, '无错误案例', ha='center', va='center', transform=ax.transAxes)
            return
        
        labels = list(error_types.keys())
        values = list(error_types.values())
        colors = ['#e74c3c', '#f39c12', '#9b59b6', '#95a5a6']
        
        bars = ax.barh(labels, values, color=colors[:len(labels)])
        ax.set_xlabel('数量')
        ax.set_title('错误类型分布')
        
        # 标注数值
        for bar, v in zip(bars, values):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                   f'{v}', va='center', fontsize=10)


def generate_learning_report(days: int = 90) -> Tuple[str, str]:
    """生成完整学习报告可视化"""
    visualizer = LearningVisualizer()
    
    print(f"\n{'='*60}")
    print(f"📊 生成AI学习报告可视化 (最近{days}天)")
    print(f"{'='*60}")
    
    dashboard_path = visualizer.plot_performance_dashboard(days)
    error_path = visualizer.plot_error_patterns(days)
    
    return dashboard_path, error_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AI学习报告可视化")
    parser.add_argument("--days", type=int, default=90, help="分析最近多少天")
    
    args = parser.parse_args()
    
    generate_learning_report(args.days)
