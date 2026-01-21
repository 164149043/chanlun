# -*- coding: utf-8 -*-
"""信号质量评分权重优化模块

功能：
1. 从历史数据提取各维度得分
2. 分析各维度与胜率/得分的相关性
3. 基于相关性计算最优权重
4. 生成权重配置文件

优化方法：
1. 单维度胜率差分析：高分段胜率 - 低分段胜率 = 预测力
2. 皮尔逊相关系数：维度得分与命中结果的相关性
3. 逻辑回归系数：多维度联合优化
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
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field

DB_PATH = Path(__file__).parent / "chanlun_ai.db"
WEIGHTS_PATH = Path(__file__).parent / "optimized_weights.json"

# 当前默认权重（经验值）
DEFAULT_WEIGHTS = {
    "signal_type": 20,
    "trend": 20,
    "position": 15,
    "strength": 15,
    "history": 20,
    "risk_reward": 10,
}

# 维度名称映射
DIM_NAMES = {
    "signal_type": "信号类型",
    "trend": "趋势一致性",
    "position": "价格位置",
    "strength": "力度背驰",
    "history": "历史胜率",
    "risk_reward": "盈亏比",
}


@dataclass
class DimensionStats:
    """维度统计数据"""
    name: str
    total_samples: int = 0
    high_score_samples: int = 0
    high_score_wins: int = 0
    low_score_samples: int = 0
    low_score_wins: int = 0
    correlation: float = 0.0
    predictive_power: float = 0.0
    suggested_weight: float = 0.0
    scores: List[float] = field(default_factory=list)
    outcomes: List[int] = field(default_factory=list)  # 1=命中, 0=未命中


class WeightOptimizer:
    """权重优化器"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.records: List[Dict] = []
        self.dimension_stats: Dict[str, DimensionStats] = {}
    
    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
    
    def _classify_signal(self, buy_sell_points: list, divergences: list) -> str:
        """分类信号类型"""
        if not buy_sell_points and not divergences:
            return "none"
        
        for signal in buy_sell_points:
            signal_lower = signal.lower()
            if "1buy" in signal_lower:
                return "1buy"
            elif "2buy" in signal_lower:
                return "2buy"
            elif "3buy" in signal_lower:
                return "3buy"
            elif "1sell" in signal_lower:
                return "1sell"
            elif "2sell" in signal_lower:
                return "2sell"
            elif "3sell" in signal_lower:
                return "3sell"
        
        for bc in divergences:
            bc_lower = bc.lower()
            if "bottom" in bc_lower or "底" in bc:
                return "bc_buy"
            elif "top" in bc_lower or "顶" in bc:
                return "bc_sell"
        
        return "mixed"
    
    def _score_signal_type(self, signal_type: str, direction: str) -> float:
        """计算信号类型得分（归一化到0-1）"""
        if direction == "up":
            if signal_type in ["1buy", "bc_buy"]:
                return 1.0
            elif signal_type == "2buy":
                return 0.9
            elif signal_type == "3buy":
                return 0.75
            elif signal_type in ["1sell", "2sell", "3sell", "bc_sell"]:
                return 0.25
            elif signal_type == "mixed":
                return 0.5
            else:
                return 0.4
        elif direction == "down":
            if signal_type in ["1sell", "bc_sell"]:
                return 1.0
            elif signal_type == "2sell":
                return 0.9
            elif signal_type == "3sell":
                return 0.75
            elif signal_type in ["1buy", "2buy", "3buy", "bc_buy"]:
                return 0.25
            elif signal_type == "mixed":
                return 0.5
            else:
                return 0.4
        else:
            return 0.5
    
    def _score_trend(self, trend: str, direction: str) -> float:
        """计算趋势一致性得分（归一化到0-1）"""
        if direction == "up":
            if trend == "up_trend":
                return 1.0
            elif trend == "consolidation":
                return 0.6
            elif trend == "down_trend":
                return 0.25
            else:
                return 0.5
        elif direction == "down":
            if trend == "down_trend":
                return 1.0
            elif trend == "consolidation":
                return 0.6
            elif trend == "up_trend":
                return 0.25
            else:
                return 0.5
        else:
            return 0.5
    
    def _score_position(self, position: str, direction: str) -> float:
        """计算价格位置得分（归一化到0-1）"""
        if direction == "up":
            if position == "below_zs":
                return 1.0
            elif position == "inside_zs":
                return 0.8
            elif position == "above_zs":
                return 0.53
            else:
                return 0.67
        elif direction == "down":
            if position == "above_zs":
                return 1.0
            elif position == "inside_zs":
                return 0.8
            elif position == "below_zs":
                return 0.53
            else:
                return 0.67
        else:
            return 0.67
    
    def _score_strength(self, strength: str, has_divergence: bool, direction: str) -> float:
        """计算力度背驰得分（归一化到0-1）"""
        base_score = 0.47
        
        if strength == "weakening":
            if direction in ["up", "down"]:
                base_score = 0.8
        elif strength == "strengthening":
            if direction in ["up", "down"]:
                base_score = 0.67
        
        if has_divergence:
            base_score = min(1.0, base_score + 0.2)
        
        return base_score
    
    def _score_risk_reward(self, target_pct: float, stop_pct: float) -> float:
        """计算盈亏比得分（归一化到0-1）"""
        if stop_pct <= 0:
            return 0.5
        
        rr_ratio = target_pct / stop_pct
        
        if rr_ratio >= 3:
            return 1.0
        elif rr_ratio >= 2:
            return 0.8
        elif rr_ratio >= 1.5:
            return 0.6
        elif rr_ratio >= 1:
            return 0.4
        else:
            return 0.2
    
    def load_historical_data(self, min_samples: int = 50) -> int:
        """加载历史数据
        
        返回：加载的有效记录数
        """
        conn = self._get_conn()
        
        rows = conn.execute("""
            SELECT ai_json, outcome_json, chanlun_json
            FROM analysis_snapshot
            WHERE evaluated = 1 AND outcome_json IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 2000
        """).fetchall()
        conn.close()
        
        self.records = []
        
        for ai_str, outcome_str, chanlun_str in rows:
            try:
                ai = json.loads(ai_str) if ai_str else {}
                outcome = json.loads(outcome_str)
                chanlun = json.loads(chanlun_str) if chanlun_str else {}
                
                # 提取基础数据
                source = chanlun if chanlun else ai
                signal_data = source.get("signal", {})
                summary = source.get("structure_summary", {})
                
                buy_sell_points = signal_data.get("buy_sell_points", [])
                divergences = signal_data.get("divergences", [])
                trend = summary.get("trend", "unknown")
                position = summary.get("price_position", "unknown")
                strength = summary.get("strength_comparison", "unknown")
                
                primary = ai.get("primary_scenario", {})
                direction = primary.get("direction", outcome.get("direction", "unknown"))
                target_pct = primary.get("target_pct", 2.0)
                stop_pct = primary.get("stop_pct", 1.5)
                
                hit_target = outcome.get("hit_target", False)
                score = outcome.get("score", 0)
                
                # 分类信号
                signal_type = self._classify_signal(buy_sell_points, divergences)
                has_divergence = bool(divergences)
                
                # 计算各维度归一化得分
                dim_scores = {
                    "signal_type": self._score_signal_type(signal_type, direction),
                    "trend": self._score_trend(trend, direction),
                    "position": self._score_position(position, direction),
                    "strength": self._score_strength(strength, has_divergence, direction),
                    "risk_reward": self._score_risk_reward(target_pct, stop_pct),
                }
                
                # 历史胜率维度需要特殊处理（暂用0.5）
                dim_scores["history"] = 0.5
                
                self.records.append({
                    "dim_scores": dim_scores,
                    "hit_target": hit_target,
                    "score": score,
                    "direction": direction,
                    "signal_type": signal_type,
                })
                
            except Exception:
                continue
        
        print(f"加载了 {len(self.records)} 条有效记录")
        return len(self.records)
    
    def analyze_dimensions(self) -> Dict[str, DimensionStats]:
        """分析各维度的预测力"""
        if not self.records:
            print("请先调用 load_historical_data()")
            return {}
        
        # 初始化统计
        for dim in DEFAULT_WEIGHTS.keys():
            self.dimension_stats[dim] = DimensionStats(name=dim)
        
        # 收集数据
        for rec in self.records:
            hit = 1 if rec["hit_target"] else 0
            
            for dim, score in rec["dim_scores"].items():
                stats = self.dimension_stats[dim]
                stats.total_samples += 1
                stats.scores.append(score)
                stats.outcomes.append(hit)
                
                # 分高低分段
                if score >= 0.7:  # 高分段
                    stats.high_score_samples += 1
                    if hit:
                        stats.high_score_wins += 1
                elif score <= 0.5:  # 低分段
                    stats.low_score_samples += 1
                    if hit:
                        stats.low_score_wins += 1
        
        # 计算各维度统计量
        for dim, stats in self.dimension_stats.items():
            # 1. 预测力（胜率差）
            high_wr = stats.high_score_wins / stats.high_score_samples if stats.high_score_samples > 5 else 0.5
            low_wr = stats.low_score_wins / stats.low_score_samples if stats.low_score_samples > 5 else 0.5
            stats.predictive_power = high_wr - low_wr
            
            # 2. 皮尔逊相关系数
            stats.correlation = self._calculate_correlation(stats.scores, stats.outcomes)
        
        return self.dimension_stats
    
    def _calculate_correlation(self, x: List[float], y: List[int]) -> float:
        """计算皮尔逊相关系数"""
        n = len(x)
        if n < 10:
            return 0.0
        
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        
        sum_sq_x = sum((xi - mean_x) ** 2 for xi in x)
        sum_sq_y = sum((yi - mean_y) ** 2 for yi in y)
        
        denominator = math.sqrt(sum_sq_x * sum_sq_y)
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def calculate_optimal_weights(self, method: str = "correlation") -> Dict[str, float]:
        """计算最优权重
        
        参数：
        - method: "correlation"（相关系数法）或 "predictive"（预测力法）
        
        返回：
        - 各维度最优权重（总和100）
        """
        if not self.dimension_stats:
            self.analyze_dimensions()
        
        raw_weights = {}
        
        for dim, stats in self.dimension_stats.items():
            if method == "correlation":
                # 使用相关系数的绝对值作为原始权重
                raw_weights[dim] = max(0.01, abs(stats.correlation))
            elif method == "predictive":
                # 使用预测力作为原始权重
                raw_weights[dim] = max(0.01, stats.predictive_power + 0.1)
            else:
                # 混合方法
                raw_weights[dim] = max(0.01, abs(stats.correlation) * 0.5 + stats.predictive_power * 0.5 + 0.05)
        
        # 归一化到总和100
        total = sum(raw_weights.values())
        if total == 0:
            return DEFAULT_WEIGHTS.copy()
        
        optimal_weights = {}
        for dim, raw in raw_weights.items():
            # 计算归一化权重
            weight = (raw / total) * 100
            # 设置最小权重5分，避免某维度权重过低
            optimal_weights[dim] = max(5, round(weight, 1))
        
        # 调整使总和为100
        current_total = sum(optimal_weights.values())
        if current_total != 100:
            diff = 100 - current_total
            # 将差值加到最大权重维度
            max_dim = max(optimal_weights, key=optimal_weights.get)
            optimal_weights[max_dim] += diff
        
        return optimal_weights
    
    def generate_report(self) -> str:
        """生成优化报告"""
        if not self.dimension_stats:
            self.analyze_dimensions()
        
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  信号质量评分 - 权重优化分析报告")
        lines.append("=" * 70)
        lines.append(f"\n  分析样本数: {len(self.records)} 条已评估记录")
        
        # 整体胜率
        total_wins = sum(1 for r in self.records if r["hit_target"])
        overall_wr = total_wins / len(self.records) if self.records else 0
        lines.append(f"  整体胜率: {overall_wr*100:.1f}%")
        
        # 各维度分析
        lines.append("\n" + "-" * 70)
        lines.append("  【各维度预测力分析】")
        lines.append("-" * 70)
        lines.append(f"  {'维度':<12} {'高分胜率':<12} {'低分胜率':<12} {'预测力':<10} {'相关系数':<10}")
        lines.append("  " + "-" * 58)
        
        for dim, stats in sorted(
            self.dimension_stats.items(),
            key=lambda x: abs(x[1].correlation),
            reverse=True
        ):
            high_wr = stats.high_score_wins / stats.high_score_samples if stats.high_score_samples > 0 else 0
            low_wr = stats.low_score_wins / stats.low_score_samples if stats.low_score_samples > 0 else 0
            
            dim_name = DIM_NAMES.get(dim, dim)
            lines.append(
                f"  {dim_name:<12} {high_wr*100:>6.1f}%      {low_wr*100:>6.1f}%      "
                f"{stats.predictive_power:>+6.1%}    {stats.correlation:>+6.3f}"
            )
        
        # 权重对比
        lines.append("\n" + "-" * 70)
        lines.append("  【权重优化建议】")
        lines.append("-" * 70)
        
        optimal_corr = self.calculate_optimal_weights(method="correlation")
        optimal_pred = self.calculate_optimal_weights(method="predictive")
        
        lines.append(f"  {'维度':<12} {'当前权重':<12} {'相关性优化':<12} {'预测力优化':<12}")
        lines.append("  " + "-" * 48)
        
        for dim in DEFAULT_WEIGHTS.keys():
            dim_name = DIM_NAMES.get(dim, dim)
            current = DEFAULT_WEIGHTS[dim]
            corr = optimal_corr.get(dim, current)
            pred = optimal_pred.get(dim, current)
            
            lines.append(f"  {dim_name:<12} {current:>6.0f}       {corr:>6.1f}       {pred:>6.1f}")
        
        # 建议
        lines.append("\n" + "-" * 70)
        lines.append("  【优化建议】")
        lines.append("-" * 70)
        
        # 找出预测力最强和最弱的维度
        sorted_dims = sorted(
            self.dimension_stats.items(),
            key=lambda x: abs(x[1].correlation),
            reverse=True
        )
        
        best_dim = sorted_dims[0]
        worst_dim = sorted_dims[-1]
        
        lines.append(f"  最强预测维度: {DIM_NAMES.get(best_dim[0], best_dim[0])} (相关系数: {best_dim[1].correlation:+.3f})")
        lines.append(f"  最弱预测维度: {DIM_NAMES.get(worst_dim[0], worst_dim[0])} (相关系数: {worst_dim[1].correlation:+.3f})")
        
        # 给出具体建议
        if abs(best_dim[1].correlation) > 0.1:
            lines.append(f"\n  建议: 提高「{DIM_NAMES.get(best_dim[0], best_dim[0])}」权重，该维度对胜率有显著预测作用")
        
        if abs(worst_dim[1].correlation) < 0.02:
            lines.append(f"  建议: 降低「{DIM_NAMES.get(worst_dim[0], worst_dim[0])}」权重，该维度对胜率预测作用有限")
        
        lines.append("\n" + "=" * 70)
        
        return "\n".join(lines)
    
    def save_optimized_weights(self, method: str = "correlation") -> str:
        """保存优化后的权重到配置文件
        
        返回：配置文件路径
        """
        optimal_weights = self.calculate_optimal_weights(method=method)
        
        config = {
            "version": "1.0",
            "method": method,
            "sample_count": len(self.records),
            "weights": optimal_weights,
            "default_weights": DEFAULT_WEIGHTS,
            "dimension_stats": {
                dim: {
                    "correlation": round(stats.correlation, 4),
                    "predictive_power": round(stats.predictive_power, 4),
                    "high_score_win_rate": round(
                        stats.high_score_wins / stats.high_score_samples if stats.high_score_samples > 0 else 0, 4
                    ),
                    "low_score_win_rate": round(
                        stats.low_score_wins / stats.low_score_samples if stats.low_score_samples > 0 else 0, 4
                    ),
                }
                for dim, stats in self.dimension_stats.items()
            }
        }
        
        with open(WEIGHTS_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 优化权重已保存到: {WEIGHTS_PATH}")
        return str(WEIGHTS_PATH)
    
    def load_optimized_weights() -> Dict[str, float]:
        """加载优化后的权重（静态方法，供其他模块调用）"""
        if not WEIGHTS_PATH.exists():
            return DEFAULT_WEIGHTS.copy()
        
        try:
            with open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("weights", DEFAULT_WEIGHTS)
        except Exception:
            return DEFAULT_WEIGHTS.copy()


def load_optimized_weights() -> Dict[str, float]:
    """加载优化后的权重（模块级函数）"""
    if not WEIGHTS_PATH.exists():
        return DEFAULT_WEIGHTS.copy()
    
    try:
        with open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("weights", DEFAULT_WEIGHTS)
    except Exception:
        return DEFAULT_WEIGHTS.copy()


# ============================================
# CLI 入口
# ============================================

def main():
    """主函数：执行权重优化分析"""
    import argparse
    
    parser = argparse.ArgumentParser(description="信号质量评分权重优化")
    parser.add_argument("--save", action="store_true", help="保存优化后的权重")
    parser.add_argument("--method", choices=["correlation", "predictive", "mixed"],
                       default="correlation", help="优化方法")
    args = parser.parse_args()
    
    print("\n🔬 开始权重优化分析...")
    print("=" * 70)
    
    optimizer = WeightOptimizer()
    
    # 1. 加载数据
    count = optimizer.load_historical_data()
    if count < 50:
        print(f"⚠️  样本数不足（{count}条），建议至少50条已评估记录")
        if count < 20:
            print("❌ 样本太少，无法进行可靠的权重优化")
            return
    
    # 2. 分析维度
    print("\n📊 分析各维度预测力...")
    optimizer.analyze_dimensions()
    
    # 3. 生成报告
    report = optimizer.generate_report()
    print(report)
    
    # 4. 保存权重（如果指定）
    if args.save:
        optimizer.save_optimized_weights(method=args.method)
        
        # 显示新旧权重对比
        print("\n📌 新旧权重对比:")
        print("-" * 50)
        optimal = optimizer.calculate_optimal_weights(method=args.method)
        for dim in DEFAULT_WEIGHTS.keys():
            dim_name = DIM_NAMES.get(dim, dim)
            old = DEFAULT_WEIGHTS[dim]
            new = optimal[dim]
            change = new - old
            arrow = "↑" if change > 0 else ("↓" if change < 0 else "→")
            print(f"  {dim_name:<12}: {old:>5.0f} → {new:>5.1f}  {arrow} {change:+.1f}")


if __name__ == "__main__":
    main()
