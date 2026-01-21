# -*- coding: utf-8 -*-
"""历史上下文模块

功能：
1. 检索与当前分析相似的历史案例
2. 分析历史案例的表现（胜率、得分）
3. 生成历史上下文摘要，注入到Prompt中

相似度匹配维度：
- 交易对（symbol）
- 周期（interval）
- 信号类型（1buy/1sell/...）
- 趋势类型（up_trend/down_trend/consolidation）
- 价格位置（above_zs/inside_zs/below_zs）
- 力度对比（weakening/strengthening/similar）
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
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass

DB_PATH = Path(__file__).parent / "chanlun_ai.db"


@dataclass
class SimilarCase:
    """相似案例"""
    snapshot_id: int
    symbol: str
    interval: str
    timestamp: str
    direction: str
    signal_type: str
    trend: str
    position: str
    hit_target: bool
    score: float
    target_pct: float
    stop_pct: float
    max_favorable: float
    max_adverse: float
    similarity_score: float  # 相似度得分


class HistoryContextBuilder:
    """历史上下文构建器"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._cache: Dict[str, Any] = {}
    
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
    
    def _extract_context(self, chanlun_json: dict, ai_json: dict) -> Dict[str, str]:
        """从JSON中提取结构上下文"""
        source = chanlun_json if chanlun_json else ai_json
        
        signal = source.get("signal", {})
        summary = source.get("structure_summary", {})
        
        buy_sell_points = signal.get("buy_sell_points", [])
        divergences = signal.get("divergences", [])
        
        return {
            "signal_type": self._classify_signal(buy_sell_points, divergences),
            "trend": summary.get("trend", "unknown"),
            "position": summary.get("price_position", "unknown"),
            "strength": summary.get("strength_comparison", "unknown"),
        }
    
    def _calculate_similarity(
        self,
        current: Dict[str, str],
        historical: Dict[str, str],
        symbol_match: bool,
        interval_match: bool,
    ) -> float:
        """计算相似度得分（0-100）"""
        score = 0
        
        # 交易对匹配（权重20）
        if symbol_match:
            score += 20
        
        # 周期匹配（权重15）
        if interval_match:
            score += 15
        
        # 信号类型匹配（权重25）
        if current["signal_type"] == historical["signal_type"]:
            score += 25
        elif current["signal_type"] != "unknown" and historical["signal_type"] != "unknown":
            # 同方向信号（buy类 vs buy类）
            curr_is_buy = "buy" in current["signal_type"]
            hist_is_buy = "buy" in historical["signal_type"]
            if curr_is_buy == hist_is_buy:
                score += 15
        
        # 趋势匹配（权重20）
        if current["trend"] == historical["trend"]:
            score += 20
        elif current["trend"] != "unknown" and historical["trend"] != "unknown":
            score += 5  # 都有明确趋势但不同
        
        # 价格位置匹配（权重15）
        if current["position"] == historical["position"]:
            score += 15
        elif current["position"] != "unknown" and historical["position"] != "unknown":
            score += 5
        
        # 力度匹配（权重5）
        if current["strength"] == historical["strength"]:
            score += 5
        
        return score
    
    def search_similar_cases(
        self,
        symbol: str,
        interval: str,
        current_context: Dict[str, str],
        direction: str = None,
        min_similarity: float = 40,
        limit: int = 20,
    ) -> List[SimilarCase]:
        """检索相似历史案例
        
        参数：
        - symbol: 当前交易对
        - interval: 当前周期
        - current_context: 当前结构上下文（signal_type, trend, position, strength）
        - direction: AI预测方向（可选）
        - min_similarity: 最小相似度阈值
        - limit: 返回数量限制
        
        返回：
        - List[SimilarCase]: 按相似度排序的历史案例
        """
        conn = self._get_conn()
        
        # 查询已评估的历史记录
        rows = conn.execute("""
            SELECT 
                id, symbol, interval, timestamp, 
                ai_json, outcome_json, chanlun_json
            FROM analysis_snapshot
            WHERE evaluated = 1 AND outcome_json IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 500
        """).fetchall()
        conn.close()
        
        similar_cases = []
        
        for row in rows:
            snapshot_id, hist_symbol, hist_interval, timestamp, ai_str, outcome_str, chanlun_str = row
            
            try:
                ai_json = json.loads(ai_str) if ai_str else {}
                outcome = json.loads(outcome_str)
                chanlun_json = json.loads(chanlun_str) if chanlun_str else {}
            except Exception:
                continue
            
            # 提取历史记录的上下文
            hist_context = self._extract_context(chanlun_json, ai_json)
            
            # 计算相似度
            similarity = self._calculate_similarity(
                current_context,
                hist_context,
                symbol_match=(symbol == hist_symbol),
                interval_match=(interval == hist_interval),
            )
            
            # 如果指定了方向，额外检查方向匹配
            hist_direction = outcome.get("direction", "unknown")
            if direction and direction == hist_direction:
                similarity += 10  # 方向匹配加分
            
            if similarity < min_similarity:
                continue
            
            # 构建相似案例
            primary = ai_json.get("primary_scenario", {})
            
            case = SimilarCase(
                snapshot_id=snapshot_id,
                symbol=hist_symbol,
                interval=hist_interval,
                timestamp=timestamp,
                direction=hist_direction,
                signal_type=hist_context["signal_type"],
                trend=hist_context["trend"],
                position=hist_context["position"],
                hit_target=outcome.get("hit_target", False),
                score=outcome.get("score", 0),
                target_pct=primary.get("target_pct", 0),
                stop_pct=primary.get("stop_pct", 0),
                max_favorable=outcome.get("max_favorable_move", 0),
                max_adverse=outcome.get("max_adverse_move", 0),
                similarity_score=similarity,
            )
            similar_cases.append(case)
        
        # 按相似度排序
        similar_cases.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return similar_cases[:limit]
    
    def analyze_similar_cases(self, cases: List[SimilarCase]) -> Dict[str, Any]:
        """分析相似案例的统计表现
        
        返回：
        - dict: 包含胜率、平均得分、建议等
        """
        if not cases:
            return {
                "total": 0,
                "has_data": False,
                "message": "无相似历史案例",
            }
        
        total = len(cases)
        wins = sum(1 for c in cases if c.hit_target)
        win_rate = wins / total if total > 0 else 0
        avg_score = sum(c.score for c in cases) / total if total > 0 else 0
        
        # 按方向分组
        by_direction = defaultdict(lambda: {"total": 0, "wins": 0, "score": 0})
        for c in cases:
            by_direction[c.direction]["total"] += 1
            by_direction[c.direction]["score"] += c.score
            if c.hit_target:
                by_direction[c.direction]["wins"] += 1
        
        direction_stats = {}
        for d, stats in by_direction.items():
            direction_stats[d] = {
                "total": stats["total"],
                "wins": stats["wins"],
                "win_rate": stats["wins"] / stats["total"] if stats["total"] > 0 else 0,
                "avg_score": stats["score"] / stats["total"] if stats["total"] > 0 else 0,
            }
        
        # 计算平均有利/不利变动
        avg_favorable = sum(c.max_favorable for c in cases) / total if total > 0 else 0
        avg_adverse = sum(c.max_adverse for c in cases) / total if total > 0 else 0
        
        # 生成建议
        if win_rate >= 0.5:
            suggestion = "历史相似案例表现良好，当前信号可信度较高"
            confidence = "high"
        elif win_rate >= 0.3:
            suggestion = "历史相似案例表现一般，建议谨慎操作"
            confidence = "medium"
        elif win_rate >= 0.15:
            suggestion = "历史相似案例胜率偏低，建议降低仓位或观望"
            confidence = "low"
        else:
            suggestion = "历史相似案例表现很差，强烈建议观望"
            confidence = "very_low"
        
        return {
            "total": total,
            "has_data": True,
            "wins": wins,
            "win_rate": round(win_rate, 3),
            "avg_score": round(avg_score, 3),
            "by_direction": direction_stats,
            "avg_favorable_move": round(avg_favorable, 2),
            "avg_adverse_move": round(avg_adverse, 2),
            "suggestion": suggestion,
            "confidence": confidence,
        }
    
    def build_prompt_context(
        self,
        symbol: str,
        interval: str,
        chanlun_json: Dict[str, Any],
        ai_direction: str = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """构建Prompt历史上下文
        
        参数：
        - symbol: 交易对
        - interval: 周期
        - chanlun_json: 当前缠论结构JSON
        - ai_direction: AI预测方向（可选）
        
        返回：
        - (prompt_text, stats_dict): Prompt文本和统计数据
        """
        # 提取当前上下文
        current_context = self._extract_context(chanlun_json, {})
        
        # 检索相似案例
        cases = self.search_similar_cases(
            symbol=symbol,
            interval=interval,
            current_context=current_context,
            direction=ai_direction,
            min_similarity=40,
            limit=20,
        )
        
        # 分析统计
        stats = self.analyze_similar_cases(cases)
        
        # 构建Prompt文本
        if not stats["has_data"]:
            prompt_text = """
【历史参考】
无足够相似的历史案例可供参考。
"""
        else:
            # 方向统计文本
            dir_lines = []
            for d, s in stats.get("by_direction", {}).items():
                dir_name = {"up": "看涨", "down": "看跌"}.get(d, d)
                dir_lines.append(
                    f"  - {dir_name}: {s['total']}条, 胜率{s['win_rate']*100:.1f}%, 平均得分{s['avg_score']:.2f}"
                )
            dir_text = "\n".join(dir_lines) if dir_lines else "  - 无"
            
            # 相似案例详情（取前5条）
            case_lines = []
            for c in cases[:5]:
                result = "命中" if c.hit_target else "未中"
                dir_name = {"up": "看涨", "down": "看跌"}.get(c.direction, c.direction)
                case_lines.append(
                    f"  - [{c.symbol} {c.interval}] {dir_name}, {result}, 得分{c.score:.2f}, 相似度{c.similarity_score:.0f}%"
                )
            cases_text = "\n".join(case_lines) if case_lines else "  - 无"
            
            prompt_text = f"""
【历史参考 - 相似案例分析】
当前结构特征: 信号={current_context['signal_type']}, 趋势={current_context['trend']}, 位置={current_context['position']}

相似案例统计（共{stats['total']}条）:
- 整体胜率: {stats['win_rate']*100:.1f}%
- 平均得分: {stats['avg_score']:.2f}/1.0
- 平均有利变动: {stats['avg_favorable_move']:.2f}%
- 平均不利变动: {stats['avg_adverse_move']:.2f}%

按方向统计:
{dir_text}

最相似案例:
{cases_text}

历史建议: {stats['suggestion']}
置信度: {stats['confidence']}

【重要提示】
基于历史相似案例的表现，请在分析中:
1. 参考历史胜率调整预测概率
2. 如果历史胜率<20%，应该更加保守
3. 如果历史胜率>40%，可以适当提高置信度
4. 参考历史平均变动幅度设置目标和止损
"""
        
        return prompt_text, stats


def get_history_context(
    symbol: str,
    interval: str,
    chanlun_json: Dict[str, Any],
    ai_direction: str = None,
) -> Tuple[str, Dict[str, Any]]:
    """获取历史上下文（便捷函数）
    
    返回：
    - (prompt_text, stats_dict)
    """
    builder = HistoryContextBuilder()
    return builder.build_prompt_context(symbol, interval, chanlun_json, ai_direction)


# ============================================
# 测试
# ============================================

def main():
    """测试历史上下文构建"""
    # 模拟当前分析的缠论结构
    test_chanlun = {
        "signal": {
            "buy_sell_points": ["1sell"],
            "divergences": ["bi"],
        },
        "structure_summary": {
            "trend": "consolidation",
            "price_position": "above_zs",
            "strength_comparison": "similar",
        }
    }
    
    print("测试历史上下文构建...")
    print("=" * 60)
    
    prompt_text, stats = get_history_context(
        symbol="BTC/USDT",
        interval="1h",
        chanlun_json=test_chanlun,
        ai_direction="down",
    )
    
    print(prompt_text)
    print("\n" + "=" * 60)
    print("统计数据:")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
