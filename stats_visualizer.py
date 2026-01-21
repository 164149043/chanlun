# -*- coding: utf-8 -*-
"""统计可视化模块

生成评估统计的可视化图表：
1. 胜率柱状图（按维度）
2. 得分分布直方图
3. 盈亏比散点图
4. 时间序列表现图
"""
import os
os.system('chcp 65001 >nul 2>&1')

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

DB_PATH = Path(__file__).parent / "chanlun_ai.db"
OUTPUT_DIR = Path(__file__).parent / "output"


def connect_db() -> sqlite3.Connection:
    """连接数据库"""
    return sqlite3.connect(DB_PATH)


def fetch_records_with_time(conn) -> List[Dict]:
    """获取带时间戳的评估记录"""
    rows = conn.execute(
        """
        SELECT id, symbol, interval, timestamp, price, ai_json, outcome_json
        FROM analysis_snapshot
        WHERE evaluated = 1 AND ai_json IS NOT NULL AND outcome_json IS NOT NULL
        ORDER BY timestamp ASC
        """
    ).fetchall()

    records = []
    for rid, symbol, interval, timestamp, price, ai_json_str, outcome_json_str in rows:
        try:
            ai = json.loads(ai_json_str)
            outcome = json.loads(outcome_json_str)
        except Exception:
            continue
        
        records.append({
            "id": rid,
            "symbol": symbol,
            "interval": interval,
            "timestamp": timestamp,
            "price": float(price),
            "ai": ai,
            "outcome": outcome,
        })
    return records


def plot_win_rate_by_dimension(records: List[Dict], output_path: str = None):
    """绘制多维度胜率对比图"""
    
    if not records:
        print("No data to plot")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Chanlun + AI Win Rate Analysis', fontsize=14, fontweight='bold')
    
    # 1. 按方向统计
    direction_stats = {}
    for rec in records:
        outcome = rec["outcome"]
        direction = outcome.get("direction", "unknown")
        if direction not in direction_stats:
            direction_stats[direction] = {"total": 0, "wins": 0}
        direction_stats[direction]["total"] += 1
        if outcome.get("hit_target"):
            direction_stats[direction]["wins"] += 1
    
    ax1 = axes[0, 0]
    dirs = list(direction_stats.keys())
    totals = [direction_stats[d]["total"] for d in dirs]
    win_rates = [direction_stats[d]["wins"] / direction_stats[d]["total"] * 100 
                 if direction_stats[d]["total"] > 0 else 0 for d in dirs]
    
    colors = ['#2ecc71' if d == 'up' else '#e74c3c' if d == 'down' else '#95a5a6' for d in dirs]
    bars1 = ax1.bar(dirs, win_rates, color=colors, edgecolor='black', linewidth=0.5)
    ax1.set_ylabel('Win Rate (%)')
    ax1.set_title('Win Rate by Direction')
    ax1.set_ylim(0, 100)
    ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
    
    # 添加数值标签
    for bar, total in zip(bars1, totals):
        height = bar.get_height()
        ax1.annotate(f'{height:.1f}%\n(n={total})',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)
    
    # 2. 按周期统计
    interval_stats = {}
    for rec in records:
        interval = rec["interval"]
        outcome = rec["outcome"]
        if interval not in interval_stats:
            interval_stats[interval] = {"total": 0, "wins": 0}
        interval_stats[interval]["total"] += 1
        if outcome.get("hit_target"):
            interval_stats[interval]["wins"] += 1
    
    ax2 = axes[0, 1]
    intervals = sorted(interval_stats.keys(), key=lambda x: {'15m': 0, '1h': 1, '4h': 2, '1d': 3}.get(x, 99))
    totals2 = [interval_stats[i]["total"] for i in intervals]
    win_rates2 = [interval_stats[i]["wins"] / interval_stats[i]["total"] * 100 
                  if interval_stats[i]["total"] > 0 else 0 for i in intervals]
    
    bars2 = ax2.bar(intervals, win_rates2, color='#3498db', edgecolor='black', linewidth=0.5)
    ax2.set_ylabel('Win Rate (%)')
    ax2.set_title('Win Rate by Interval')
    ax2.set_ylim(0, 100)
    ax2.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
    
    for bar, total in zip(bars2, totals2):
        height = bar.get_height()
        ax2.annotate(f'{height:.1f}%\n(n={total})',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)
    
    # 3. 按交易对统计
    symbol_stats = {}
    for rec in records:
        symbol = rec["symbol"]
        outcome = rec["outcome"]
        if symbol not in symbol_stats:
            symbol_stats[symbol] = {"total": 0, "wins": 0}
        symbol_stats[symbol]["total"] += 1
        if outcome.get("hit_target"):
            symbol_stats[symbol]["wins"] += 1
    
    ax3 = axes[1, 0]
    symbols = list(symbol_stats.keys())
    totals3 = [symbol_stats[s]["total"] for s in symbols]
    win_rates3 = [symbol_stats[s]["wins"] / symbol_stats[s]["total"] * 100 
                  if symbol_stats[s]["total"] > 0 else 0 for s in symbols]
    
    bars3 = ax3.bar(symbols, win_rates3, color='#9b59b6', edgecolor='black', linewidth=0.5)
    ax3.set_ylabel('Win Rate (%)')
    ax3.set_title('Win Rate by Symbol')
    ax3.set_ylim(0, 100)
    ax3.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
    ax3.tick_params(axis='x', rotation=45)
    
    for bar, total in zip(bars3, totals3):
        height = bar.get_height()
        ax3.annotate(f'{height:.1f}%\n(n={total})',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)
    
    # 4. 按结果类型统计
    outcome_stats = {}
    for rec in records:
        outcome_type = rec["outcome"].get("outcome", "unknown")
        if outcome_type not in outcome_stats:
            outcome_stats[outcome_type] = 0
        outcome_stats[outcome_type] += 1
    
    ax4 = axes[1, 1]
    outcomes = list(outcome_stats.keys())
    counts = [outcome_stats[o] for o in outcomes]
    
    colors4 = {
        'success': '#2ecc71',
        'partial': '#f1c40f',
        'stopped': '#e74c3c',
        'failed': '#c0392b',
        'unknown': '#95a5a6',
        'no_direction': '#7f8c8d'
    }
    pie_colors = [colors4.get(o, '#95a5a6') for o in outcomes]
    
    wedges, texts, autotexts = ax4.pie(counts, labels=outcomes, autopct='%1.1f%%',
                                        colors=pie_colors, startangle=90)
    ax4.set_title('Outcome Distribution')
    
    plt.tight_layout()
    
    # 保存图片
    if output_path is None:
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / "stats_win_rate.png"
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"【完成】胜率图表已保存: {output_path}")
    return str(output_path)


def plot_score_distribution(records: List[Dict], output_path: str = None):
    """绘制得分分布图"""
    
    if not records:
        print("No data to plot")
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle('Score Distribution Analysis', fontsize=14, fontweight='bold')
    
    # 1. 得分直方图
    scores = [rec["outcome"].get("score", 0) for rec in records]
    enhanced_scores = [rec["outcome"].get("enhanced_score", rec["outcome"].get("score", 0)) for rec in records]
    
    ax1 = axes[0]
    ax1.hist(scores, bins=20, color='#3498db', edgecolor='black', alpha=0.7, label='Basic Score')
    ax1.hist(enhanced_scores, bins=20, color='#e74c3c', edgecolor='black', alpha=0.5, label='Enhanced Score')
    ax1.set_xlabel('Score')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Score Distribution')
    ax1.legend()
    ax1.axvline(x=np.mean(scores), color='#3498db', linestyle='--', label=f'Mean: {np.mean(scores):.2f}')
    
    # 2. 最大有利变动 vs 最大不利变动
    ax2 = axes[1]
    favorable = [rec["outcome"].get("max_favorable_move", 0) for rec in records]
    adverse = [abs(rec["outcome"].get("max_adverse_move", 0)) for rec in records]
    
    # 根据结果着色
    colors = []
    for rec in records:
        if rec["outcome"].get("hit_target"):
            colors.append('#2ecc71')  # 绿色-成功
        elif rec["outcome"].get("hit_stop"):
            colors.append('#e74c3c')  # 红色-止损
        else:
            colors.append('#95a5a6')  # 灰色-其他
    
    ax2.scatter(adverse, favorable, c=colors, alpha=0.6, edgecolors='black', linewidth=0.5)
    ax2.set_xlabel('Max Adverse Move (%)')
    ax2.set_ylabel('Max Favorable Move (%)')
    ax2.set_title('Risk vs Reward')
    
    # 添加对角线（1:1 盈亏比）
    max_val = max(max(favorable), max(adverse)) if favorable and adverse else 10
    ax2.plot([0, max_val], [0, max_val], 'k--', alpha=0.3, label='1:1 R/R')
    ax2.plot([0, max_val], [0, max_val * 2], 'g--', alpha=0.3, label='2:1 R/R')
    ax2.legend()
    
    # 添加图例
    legend_elements = [
        mpatches.Patch(color='#2ecc71', label='Hit Target'),
        mpatches.Patch(color='#e74c3c', label='Hit Stop'),
        mpatches.Patch(color='#95a5a6', label='Other'),
    ]
    ax2.legend(handles=legend_elements, loc='upper left')
    
    plt.tight_layout()
    
    if output_path is None:
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / "stats_score_dist.png"
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"【完成】得分分布图已保存: {output_path}")
    return str(output_path)


def plot_performance_over_time(records: List[Dict], output_path: str = None):
    """绘制时间序列表现图"""
    
    if not records:
        print("No data to plot")
        return
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    fig.suptitle('Performance Over Time', fontsize=14, fontweight='bold')
    
    # 解析时间戳
    times = []
    scores = []
    cumulative_wins = []
    win_count = 0
    
    for i, rec in enumerate(records):
        try:
            ts = datetime.fromisoformat(rec["timestamp"].replace('Z', '+00:00'))
        except:
            ts = datetime.now()
        times.append(ts)
        scores.append(rec["outcome"].get("score", 0))
        if rec["outcome"].get("hit_target"):
            win_count += 1
        cumulative_wins.append(win_count)
    
    # 1. 累计胜率曲线
    ax1 = axes[0]
    cumulative_rate = [w / (i + 1) * 100 for i, w in enumerate(cumulative_wins)]
    ax1.plot(times, cumulative_rate, color='#3498db', linewidth=2, label='Cumulative Win Rate')
    ax1.fill_between(times, cumulative_rate, alpha=0.3)
    ax1.set_ylabel('Cumulative Win Rate (%)')
    ax1.set_title('Win Rate Over Time')
    ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. 滚动平均得分
    ax2 = axes[1]
    window = min(10, len(scores))  # 滚动窗口
    rolling_avg = []
    for i in range(len(scores)):
        start = max(0, i - window + 1)
        rolling_avg.append(np.mean(scores[start:i+1]))
    
    ax2.plot(times, rolling_avg, color='#e74c3c', linewidth=2, label=f'Rolling Avg Score (window={window})')
    ax2.scatter(times, scores, color='#95a5a6', alpha=0.5, s=20, label='Individual Score')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('Score')
    ax2.set_title('Score Over Time')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if output_path is None:
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / "stats_time_series.png"
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"【完成】时间序列图已保存: {output_path}")
    return str(output_path)


def generate_all_charts():
    """生成所有统计图表"""
    
    print("\n" + "=" * 60)
    print("  统计图表可视化")
    print("=" * 60 + "\n")
    
    conn = connect_db()
    try:
        records = fetch_records_with_time(conn)
        
        if not records:
            print("  【警告】数据库中暂无评估记录")
            print("  请先运行: python evaluate_outcome.py\n")
            return
        
        print(f"  已找到 {len(records)} 条评估记录\n")
        
        # 生成图表
        plot_win_rate_by_dimension(records)
        plot_score_distribution(records)
        plot_performance_over_time(records)
        
        print("\n" + "=" * 60)
        print("  【完成】所有图表已生成！")
        print(f"  输出目录: {OUTPUT_DIR}")
        print("=" * 60 + "\n")
        
    finally:
        conn.close()


def main():
    """主函数"""
    generate_all_charts()


if __name__ == "__main__":
    main()
