"""evaluate_outcome.py - AI 预测结果回填脚本

职责：
1. 找出还没有 outcome 的 AI 记录（evaluated = 0）
2. 读取当时的 symbol / interval / timestamp
3. 拉取"未来 K 线"（从分析时间开始的 N 根 K 线）
4. 用统一规则评估结果
5. 写回 outcome_json
6. 标记为 evaluated = 1

评估规则：
- 观察未来 N = 50 根 K 线
- 使用 close 价
- 从 AI 给出的 primary_scenario 里取：
  - direction（up/down）
  - target_pct（目标涨跌幅）
  - stop_pct（止损幅度）
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from binance import get_klines

# 导入数据库管理器（修复连接泄漏问题）
try:
    from db_manager import get_db_conn, safe_json_loads, safe_json_dumps
    DB_MANAGER_AVAILABLE = True
except ImportError:
    DB_MANAGER_AVAILABLE = False

# ============================================
# 配置
# ============================================

DB_PATH = Path(__file__).parent / "chanlun_ai.db"

# 根据周期设置不同的评估窗口（K线根数）
FUTURE_BARS_CONFIG = {
    "15m": 96,  # 24小时
    "1h": 48,   # 48小时（2天）
    "4h": 24,   # 96小时（4天）
    "1d": 10,   # 10天
}

# 评估窗口说明：
# - 15m 周期：96根 = 24小时，适合短线测试
# - 1h 周期：48根 = 48小时，适合快速测试
# - 4h 周期：24根 = 96小时，适合中线测试
# - 1d 周期：10根 = 10天，适合中长期测试
# 注意：正式使用建议增加到 48-50 根以获得更准确的评估


# ============================================
# 数据库操作
# ============================================

def get_db_conn():
    """获取数据库连接（兼容性包装）"""
    if DB_MANAGER_AVAILABLE:
        from db_manager import get_db_conn_no_context
        return get_db_conn_no_context()
    return sqlite3.connect(str(DB_PATH))


def fetch_pending_records(conn) -> List[tuple]:
    """获取待评估的记录（evaluated = 0 且有 ai_json）

    返回：
    - List[tuple]: (id, symbol, interval, timestamp, ai_json_str, chanlun_json_str)
    """
    try:
        sql = """
        SELECT id, symbol, interval, timestamp, ai_json, chanlun_json
        FROM analysis_snapshot
        WHERE evaluated = 0 AND ai_json IS NOT NULL
        """
        return conn.execute(sql).fetchall()
    except sqlite3.Error as e:
        print(f"数据库查询错误: {e}")
        return []


def mark_as_evaluated(conn, record_id: int, outcome_json: dict):
    """标记记录为已评估

    参数：
    - record_id: 快照 ID
    - outcome_json: 评估结果 JSON
    """
    try:
        # 安全的JSON序列化
        if DB_MANAGER_AVAILABLE:
            outcome_json_str = safe_json_dumps(outcome_json)
        else:
            outcome_json_str = json.dumps(outcome_json, ensure_ascii=False)

        conn.execute(
            """
            UPDATE analysis_snapshot
            SET outcome_json = ?, evaluated = 1
            WHERE id = ?
            """,
            (outcome_json_str, record_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"数据库更新错误: {e}")
        try:
            conn.rollback()
        except:
            pass


# ============================================
# 核心评估逻辑
# ============================================

def extract_structure_context(ai_json: dict, chanlun_json: dict = None) -> dict:
    """从缠论结构 JSON 中提取上下文（用于细分统计）
    
    参数：
    - ai_json: AI 输出的结构化 JSON
    - chanlun_json: exporter 导出的完整缠论结构 JSON（优先使用）
    
    返回：
    - dict: 结构上下文信息
    """
    context = {
        "buy_sell_points": [],
        "divergences": [],
        "trend": "unknown",
        "price_position": "unknown",
        "strength_comparison": "unknown",
        "zg": 0,
        "zd": 0,
        "has_signal": False,
    }
    
    # 优先从 chanlun_json（exporter 导出的完整结构）提取
    source = chanlun_json if chanlun_json else ai_json
    
    # 从 signal 字段提取买卖点和背驰
    signal = source.get("signal", {})
    context["buy_sell_points"] = signal.get("buy_sell_points", [])
    context["divergences"] = signal.get("divergences", [])
    context["has_signal"] = bool(context["buy_sell_points"] or context["divergences"])
    
    # 从 structure_summary 提取趋势和位置（新版导出）
    summary = source.get("structure_summary", {})
    if summary:
        context["trend"] = summary.get("trend", "unknown")
        context["price_position"] = summary.get("price_position", "unknown")
        context["strength_comparison"] = summary.get("strength_comparison", "unknown")
        key_levels = summary.get("key_levels", {})
        context["zg"] = key_levels.get("zg", 0)
        context["zd"] = key_levels.get("zd", 0)
    
    # 兼容旧版：从 structure_judgement 提取（AI 输出或旧版 chanlun_json）
    if not summary:
        sj = ai_json.get("structure_judgement", {}) if ai_json else {}
        if sj:
            zs = sj.get("zs", {})
            zs_range = zs.get("range") or []
            if isinstance(zs_range, list) and len(zs_range) == 2:
                context["zd"] = context["zd"] or float(zs_range[0])
                context["zg"] = context["zg"] or float(zs_range[1])
    
    # 分类买卖点类型
    context["signal_type"] = _classify_signal(context["buy_sell_points"], context["divergences"])
    
    return context


def _classify_signal(buy_sell_points: list, divergences: list) -> str:
    """分类信号类型
    
    返回：
    - "1buy" / "2buy" / "3buy" / "1sell" / "2sell" / "3sell" / 
    - "bc_buy" / "bc_sell" / "mixed" / "none"
    """
    if not buy_sell_points and not divergences:
        return "none"
    
    # 优先级：明确的买卖点 > 背驰信号
    for signal in buy_sell_points:
        signal_lower = signal.lower()
        if "1buy" in signal_lower or "一买" in signal:
            return "1buy"
        elif "2buy" in signal_lower or "二买" in signal:
            return "2buy"
        elif "3buy" in signal_lower or "三买" in signal:
            return "3buy"
        elif "1sell" in signal_lower or "一卖" in signal:
            return "1sell"
        elif "2sell" in signal_lower or "二卖" in signal:
            return "2sell"
        elif "3sell" in signal_lower or "三卖" in signal:
            return "3sell"
    
    # 背驰信号
    for bc in divergences:
        bc_lower = bc.lower()
        if "bi" in bc_lower or "笔" in bc:
            if "bottom" in bc_lower or "底" in bc:
                return "bc_buy"
            elif "top" in bc_lower or "顶" in bc:
                return "bc_sell"
    
    if buy_sell_points or divergences:
        return "mixed"
    
    return "none"


# 滑点容忍度（0.1%）
SLIPPAGE_PCT = 0.1


def evaluate_outcome(ai_json: dict, future_klines: List[Dict[str, Any]], entry_price: float, chanlun_json: dict = None) -> dict:
    """核心评估逻辑（增强版）

    参数：
    - ai_json: AI 输出的结构化 JSON
    - future_klines: 未来 K 线列表（至少 10 根）
    - entry_price: 入场价格（分析时的价格）
    - chanlun_json: exporter 导出的完整缠论结构 JSON（可选，用于提取结构上下文）

    返回：
    - dict: 评估结果（包含结构上下文）
      {
        "direction": "up" | "down",
        "hit_target": bool,
        "hit_stop": bool,
        "max_favorable_move": float,  # 最大有利变动（%）
        "max_adverse_move": float,    # 最大不利变动（%）
        "evaluated_bars": int,        # 实际评估的 K 线数量
        "structure_context": {...}    # 缠论结构上下文
      }
    """
    # ========================================
    # 边界情况检查（新增安全检查）
    # ========================================
    # 1. 数据量检查
    if not future_klines or len(future_klines) < 5:
        return {
            "error": "insufficient_klines",
            "evaluated_bars": len(future_klines) if future_klines else 0,
            "message": "K线数据不足（至少需要5根）"
        }

    # 2. 价格异常值检测（波动超过10倍视为异常）
    closes = [k["close"] for k in future_klines]
    if max(closes) > 0 and min(closes) > 0:
        volatility_ratio = max(closes) / min(closes)
        if volatility_ratio > 10:
            return {
                "error": "abnormal_price_movement",
                "evaluated_bars": len(future_klines),
                "volatility_ratio": volatility_ratio,
                "message": f"价格波动异常（{volatility_ratio:.1f}倍）"
            }

    # 3. 入场价格有效性检查
    if entry_price <= 0:
        return {
            "error": "invalid_entry_price",
            "evaluated_bars": len(future_klines),
            "entry_price": entry_price
        }

    # ========================================
    # 原有评估逻辑
    # ========================================
    # 1. 提取 primary_scenario
    primary_scenario = ai_json.get("primary_scenario")
    if not primary_scenario:
        # 如果没有 primary_scenario，尝试从 scenarios 数组中取 rank=1
        scenarios = ai_json.get("scenarios", [])
        if scenarios:
            primary_scenario = next((s for s in scenarios if s.get("rank") == 1), None)

    if not primary_scenario:
        return {
            "error": "No primary_scenario found in AI output",
            "evaluated_bars": len(future_klines)
        }

    direction = primary_scenario.get("direction", "unknown")
    target_pct = primary_scenario.get("target_pct", 0)
    stop_pct = primary_scenario.get("stop_pct", 0)

    # 使用 close 价格
    future_closes = [k["close"] for k in future_klines]
    future_highs = [k["high"] for k in future_klines]
    future_lows = [k["low"] for k in future_klines]

    max_high = max(future_highs)
    min_low = min(future_lows)

    # 3. 计算最大变动幅度
    max_up_move = (max_high - entry_price) / entry_price * 100
    max_down_move = (min_low - entry_price) / entry_price * 100

    # 4. 判断是否命中目标和止损（添加滑点容忍度）
    # 滑点容忍度：考虑0.1%的交易成本
    if direction == "up":
        # 多头：需要达到目标扣除滑点后的价格
        effective_target = max(target_pct * (1 - SLIPPAGE_PCT / 100), 0)
        effective_stop = stop_pct * (1 + SLIPPAGE_PCT / 100)
        hit_target = max_up_move >= effective_target
        hit_stop = max_down_move <= -effective_stop
        max_favorable_move = round(max_up_move, 2)
        max_adverse_move = round(max_down_move, 2)
    elif direction == "down":
        # 空头：需要达到目标扣除滑点后的价格
        effective_target = max(target_pct * (1 - SLIPPAGE_PCT / 100), 0)
        effective_stop = stop_pct * (1 + SLIPPAGE_PCT / 100)
        hit_target = max_down_move <= -effective_target
        hit_stop = max_up_move >= effective_stop
        max_favorable_move = round(-max_down_move, 2)
        max_adverse_move = round(max_up_move, 2)
    else:
        hit_target = False
        hit_stop = False
        max_favorable_move = round(max(abs(max_up_move), abs(max_down_move)), 2)
        max_adverse_move = round(min(abs(max_up_move), abs(max_down_move)), 2)
    
    # 5. 计算综合得分和结果分类
    final_close = future_closes[-1]
    final_move = (final_close - entry_price) / entry_price * 100
    
    if direction in ["up", "down"]:
        if hit_target and not hit_stop:
            score = 1.0
            outcome = "success"
        elif hit_stop:
            score = 0.0
            outcome = "stopped"
        elif not hit_target and not hit_stop:
            # 根据最终走势评分
            if (direction == "up" and final_move > 0) or (direction == "down" and final_move < 0):
                score = 0.5
                outcome = "partial"  # 方向对但未达目标
            else:
                score = 0.0
                outcome = "failed"  # 方向错误
        else:
            score = 0.0
            outcome = "unknown"
    else:
        score = 0.0
        outcome = "no_direction"
    
    # 提取结构上下文（优先从 chanlun_json 提取）
    structure_context = extract_structure_context(ai_json, chanlun_json)
    
    # 计算命中时间（第几根 K 线命中目标/止损）
    hit_target_bar = None
    hit_stop_bar = None
    
    for i, k in enumerate(future_klines):
        if direction == "up":
            k_up_move = (k["high"] - entry_price) / entry_price * 100
            k_down_move = (k["low"] - entry_price) / entry_price * 100
            if hit_target_bar is None and k_up_move >= target_pct:
                hit_target_bar = i + 1
            if hit_stop_bar is None and k_down_move <= -stop_pct:
                hit_stop_bar = i + 1
        elif direction == "down":
            k_up_move = (k["high"] - entry_price) / entry_price * 100
            k_down_move = (k["low"] - entry_price) / entry_price * 100
            if hit_target_bar is None and k_down_move <= -target_pct:
                hit_target_bar = i + 1
            if hit_stop_bar is None and k_up_move >= stop_pct:
                hit_stop_bar = i + 1
    
    # 计算盈亏比（实际）
    actual_rr = 0
    if max_adverse_move != 0:
        actual_rr = round(abs(max_favorable_move / max_adverse_move), 2)

    # 计算预期盈亏比
    expected_rr = round(target_pct / stop_pct, 2) if stop_pct > 0 else 0

    # 改进评分算法（传入风险调整参数）
    enhanced_score = _calculate_enhanced_score(
        hit_target=hit_target,
        hit_stop=hit_stop,
        direction=direction,
        final_move=final_move,
        max_favorable_move=max_favorable_move,
        target_pct=target_pct,
        hit_target_bar=hit_target_bar,
        total_bars=len(future_klines),
        expected_rr=expected_rr,
        actual_rr=actual_rr
    )

    # 构建基础结果
    result = {
        "direction": direction,
        "target_pct": target_pct,
        "stop_pct": stop_pct,
        "hit_target": hit_target,
        "hit_stop": hit_stop,
        "max_favorable_move": max_favorable_move,
        "max_adverse_move": max_adverse_move,
        "final_move": round(final_move, 2),
        "evaluated_bars": len(future_klines),
        "entry_price": entry_price,
        "final_price": round(final_close, 4),
        "max_high": max_high,
        "min_low": min_low,
        "score": score,
        "enhanced_score": enhanced_score,
        "outcome": outcome,
        # 新增字段
        "hit_target_bar": hit_target_bar,
        "hit_stop_bar": hit_stop_bar,
        "actual_rr": actual_rr,
        "expected_rr": expected_rr,
        "structure_context": structure_context,
        # v2.1 新增：标准字段别名（兼容性）
        "max_adverse_excursion": max_adverse_move,  # 别名：最大不利变动（MAE）
        "max_favorable_excursion": max_favorable_move,  # 别名：最大有利变动（MFE）
        "stop_price": entry_price * (1 - stop_pct/100) if direction == "up" else entry_price * (1 + stop_pct/100),  # 计算的止损价
        "target_price": entry_price * (1 + target_pct/100) if direction == "up" else entry_price * (1 - target_pct/100),  # 计算的目标价
    }

    # ========================================
    # 多维度评分（v2.2 新增）
    # ========================================
    try:
        from scoring_engine import ScoringEngine, calculate_atr

        # 计算ATR
        atr = calculate_atr(future_klines) if future_klines else None

        # 提取信号类型
        signal_type = structure_context.get("signal_type", "none")

        # 多维度评分
        scoring_engine = ScoringEngine()
        all_scores = scoring_engine.calculate_all_scores(
            outcome=result,
            signal_type=signal_type,
            atr=atr,
            entry_price=entry_price,
        )

        # 获取最佳评分
        best_score = scoring_engine.get_best_score(all_scores)

        # 扩展结果
        result.update({
            "scoring_mode": best_score.mode,
            "best_score": best_score.score,
            "all_scores": {k: v.score for k, v in all_scores.items()},
            "scoring_details": {k: v.details for k, v in all_scores.items()},
            "signal_type": signal_type,
            "atr_at_entry": round(atr, 2) if atr else None,
        })

    except ImportError:
        # 向后兼容：如果scoring_engine不可用，使用原有评分
        result["scoring_mode"] = "target_based"
        result["best_score"] = result.get("score", 0.0)
        result["all_scores"] = {"target_based": result.get("score", 0.0)}
        result["scoring_details"] = {}
        result["signal_type"] = structure_context.get("signal_type", "none")
        result["atr_at_entry"] = None

    return result


def _calculate_enhanced_score(
    hit_target: bool,
    hit_stop: bool,
    direction: str,
    final_move: float,
    max_favorable_move: float,
    target_pct: float,
    hit_target_bar: int,
    total_bars: int,
    expected_rr: float = 0,
    actual_rr: float = 0,
) -> float:
    """计算增强评分（改进版：考虑风险调整收益）

    评分维度：
    1. 命中目标 (0.35)
    2. 方向正确 (0.2)
    3. 最大有利变动占目标比例 (0.2)
    4. 命中速度 (0.15)
    5. 风险调整 (0.1) - 超额完成目标时加分

    返回：0.0 ~ 1.0
    """
    score = 0.0

    # 1. 命中目标（权重 0.35）
    if hit_target and not hit_stop:
        score += 0.35
    elif hit_target and hit_stop:
        # 先命中目标再止损，给一半分
        score += 0.2

    # 2. 方向正确（权重 0.2）
    if direction == "up" and final_move > 0:
        score += 0.2
    elif direction == "down" and final_move < 0:
        score += 0.2
    elif direction in ["up", "down"]:
        # 方向错误
        score += 0.0

    # 3. 最大有利变动占目标比例（权重 0.2）
    if target_pct > 0:
        ratio = min(max_favorable_move / target_pct, 1.0)
        score += 0.2 * ratio

    # 4. 命中速度（权重 0.15）
    if hit_target_bar is not None and total_bars > 0:
        # 越快命中得分越高
        speed_score = 1.0 - (hit_target_bar / total_bars)
        score += 0.15 * speed_score

    # 5. 风险调整（权重 0.1）- 超额完成目标时加分
    if expected_rr > 0 and actual_rr > 0:
        if actual_rr > expected_rr * 1.2:
            # 超额完成20%以上
            score += 0.1
        elif actual_rr > expected_rr:
            # 超额完成
            score += 0.05
        elif actual_rr < expected_rr * 0.8:
            # 严重低于预期
            score -= 0.05

    return round(min(score, 1.0), 3)


# ============================================
# 主流程
# ============================================

def main():
    """主流程"""

    print("=" * 60)
    print("📈 缠论 AI 预测结果回填工具（新版）")
    print("=" * 60)
    print()

    conn = None
    try:
        conn = get_db_conn()
        records = fetch_pending_records(conn)

        print(f"🔍 待回填记录数: {len(records)}\n")

        if not records:
            print("✅ 没有待评估的快照")
            return

        success_count = 0
        failed_count = 0

        for rec in records:
            record_id, symbol, interval, timestamp_str, ai_json_str, chanlun_json_str = rec

            print(f"评估快照 #{record_id}: {symbol} @ {interval}")
            print(f"  分析时间: {timestamp_str}")

            try:
                # 1. 解析 AI JSON 和 缠论结构 JSON（添加异常处理）
                try:
                    if DB_MANAGER_AVAILABLE:
                        ai_json = safe_json_loads(ai_json_str, {})
                        chanlun_json = safe_json_loads(chanlun_json_str) if chanlun_json_str else None
                    else:
                        ai_json = json.loads(ai_json_str) if ai_json_str else {}
                        chanlun_json = json.loads(chanlun_json_str) if chanlun_json_str else None
                except json.JSONDecodeError as e:
                    print(f"  ✗ JSON解析失败: {e}")
                    failed_outcome = {
                        "error": "json_parse_error",
                        "error_message": f"JSON解析失败: {e}",
                        "score": 0.0,
                        "outcome": "failed"
                    }
                    mark_as_evaluated(conn, record_id, failed_outcome)
                    failed_count += 1
                    continue

                # 2. 解析时间戳（ISO 格式）
                try:
                    analysis_time = datetime.fromisoformat(timestamp_str)
                    if analysis_time.tzinfo is None:
                        analysis_time = analysis_time.replace(tzinfo=timezone.utc)
                except ValueError as e:
                    print(f"  ✗ 时间解析失败: {e}")
                    failed_count += 1
                    continue

                # 3. 转换为毫秒时间戳
                start_time_ms = int(analysis_time.timestamp() * 1000)

                # 4. 标准化交易对格式（BTC/USDT → BTCUSDT）
                binance_symbol = symbol.replace("/", "")

                # 5. 根据周期获取需要的 K 线数量
                future_bars = FUTURE_BARS_CONFIG.get(interval, 50)

                # 6. 拉取未来 K 线（从分析时间开始）
                print(f"  ⏳ 拉取未来 {future_bars} 根 K 线...")

                klines = get_klines(
                    symbol=binance_symbol,
                    interval=interval,
                    limit=future_bars,
                    start_time=start_time_ms
                )

                if len(klines) < future_bars:
                    print(f"  ⚠️  K 线数量不足（{len(klines)}/{future_bars}），记录评估失败")
                    # 记录评估失败原因（修复：不再跳过，而是记录失败原因）
                    failed_outcome = {
                        "error": "insufficient_data",
                        "error_message": f"K线数量不足（{len(klines)}/{future_bars}）",
                        "evaluated_bars": len(klines),
                        "required_bars": future_bars,
                        "score": 0.0,
                        "outcome": "failed"
                    }
                    mark_as_evaluated(conn, record_id, failed_outcome)
                    failed_count += 1
                    continue

                # 7. 获取入场价格（分析时的价格）
                # 从数据库读取
                cursor = conn.execute(
                    "SELECT price FROM analysis_snapshot WHERE id = ?",
                    (record_id,)
                )
                result = cursor.fetchone()
                if not result:
                    print(f"  ✗ 无法找到快照价格")
                    failed_count += 1
                    continue
                entry_price = result[0]

                # 8. 评估结果（传入 chanlun_json 以提取结构上下文）
                outcome = evaluate_outcome(ai_json, klines, entry_price, chanlun_json)

                if "error" in outcome:
                    print(f"  ✗ 评估失败: {outcome['error']}")
                    # 即使失败也记录
                    mark_as_evaluated(conn, record_id, outcome)
                    failed_count += 1
                    continue

                # 9. 保存结果
                mark_as_evaluated(conn, record_id, outcome)

                print(f"  方向: {outcome['direction']}")
                print(f"  目标: {outcome['target_pct']}% | 止损: {outcome['stop_pct']}%")
                print(f"  命中目标: {'✓' if outcome['hit_target'] else '✗'}")
                print(f"  触发止损: {'✓' if outcome['hit_stop'] else '✗'}")
                print(f"  结果: {outcome['outcome']} (得分: {outcome['score']:.1f})")
                print(f"  最终变动: {outcome['final_move']}%")
                print(f"  最大有利: {outcome['max_favorable_move']}%")
                print(f"  最大不利: {outcome['max_adverse_move']}%")

                # 多维度评分输出（v2.2）
                if "scoring_mode" in outcome:
                    signal_type = outcome.get("signal_type", "unknown")
                    atr = outcome.get("atr_at_entry")
                    print(f"  信号类型: {signal_type}")
                    if atr:
                        print(f"  ATR: {atr}")

                    # 评分对比
                    all_scores = outcome.get("all_scores", {})
                    if all_scores:
                        mode_names = {
                            "target_based": "目标命中",
                            "atr_normalized": "ATR归一化",
                            "signal_expected": "信号期望",
                            "volatility_adjusted": "波动率调整",
                        }
                        print(f"  📊 多维度评分:")
                        for mode, score in all_scores.items():
                            mode_name = mode_names.get(mode, mode)
                            print(f"    {mode_name:>12}: {score:.3f}")

                    best_mode = outcome.get("scoring_mode", "unknown")
                    best_score = outcome.get("best_score", outcome.get("score", 0))
                    mode_name_cn = {
                        "target_based": "目标命中",
                        "atr_normalized": "ATR归一化",
                        "signal_expected": "信号期望",
                        "volatility_adjusted": "波动率调整",
                    }.get(best_mode, best_mode)
                    print(f"  最佳评分: {best_score:.3f} ({mode_name_cn})")

                print(f"  ✓ outcome 已回填\n")

                success_count += 1

            except Exception as e:
                print(f"  ✗ 处理失败: {e}\n")
                failed_count += 1
                import traceback
                traceback.print_exc()
                continue

        print("=" * 60)
        print(f"✅ 评估完成: 成功 {success_count} 条，失败 {failed_count} 条")

    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
    except Exception as e:
        print(f"❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
