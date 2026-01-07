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

# ============================================
# 配置
# ============================================

DB_PATH = Path(__file__).parent / "chanlun_ai.db"
FUTURE_BARS = 10  # 观察未来 10 根 K 线


# ============================================
# 数据库操作
# ============================================

def fetch_pending_records(conn) -> List[tuple]:
    """获取待评估的记录（evaluated = 0 且有 ai_json）
    
    返回：
    - List[tuple]: (id, symbol, interval, timestamp, ai_json_str)
    """
    sql = """
    SELECT id, symbol, interval, timestamp, ai_json
    FROM analysis_snapshot
    WHERE evaluated = 0 AND ai_json IS NOT NULL
    """
    return conn.execute(sql).fetchall()


def mark_as_evaluated(conn, record_id: int, outcome_json: dict):
    """标记记录为已评估
    
    参数：
    - record_id: 快照 ID
    - outcome_json: 评估结果 JSON
    """
    conn.execute(
        """
        UPDATE analysis_snapshot
        SET outcome_json = ?, evaluated = 1
        WHERE id = ?
        """,
        (json.dumps(outcome_json, ensure_ascii=False), record_id)
    )
    conn.commit()


# ============================================
# 核心评估逻辑
# ============================================

def evaluate_outcome(ai_json: dict, future_klines: List[Dict[str, Any]], entry_price: float) -> dict:
    """核心评估逻辑
    
    参数：
    - ai_json: AI 输出的结构化 JSON
    - future_klines: 未来 K 线列表（至少 10 根）
    - entry_price: 入场价格（分析时的价格）
    
    返回：
    - dict: 评估结果
      {
        "direction": "up" | "down",
        "hit_target": bool,
        "hit_stop": bool,
        "max_favorable_move": float,  # 最大有利变动（%）
        "max_adverse_move": float,    # 最大不利变动（%）
        "evaluated_bars": int         # 实际评估的 K 线数量
      }
    """
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
    
    # 2. 计算未来价格区间
    if not future_klines:
        return {
            "error": "No future klines available",
            "evaluated_bars": 0
        }
    
    # 使用 close 价格
    future_closes = [k["close"] for k in future_klines]
    future_highs = [k["high"] for k in future_klines]
    future_lows = [k["low"] for k in future_klines]
    
    max_high = max(future_highs)
    min_low = min(future_lows)
    
    # 3. 计算最大变动幅度
    max_up_move = (max_high - entry_price) / entry_price * 100
    max_down_move = (min_low - entry_price) / entry_price * 100
    
    # 4. 判断是否命中目标和止损
    if direction == "up":
        hit_target = max_up_move >= target_pct
        hit_stop = max_down_move <= -stop_pct
        max_favorable_move = round(max_up_move, 2)
        max_adverse_move = round(max_down_move, 2)
    elif direction == "down":
        hit_target = max_down_move <= -target_pct
        hit_stop = max_up_move >= stop_pct
        max_favorable_move = round(-max_down_move, 2)
        max_adverse_move = round(max_up_move, 2)
    else:
        hit_target = False
        hit_stop = False
        max_favorable_move = round(max(abs(max_up_move), abs(max_down_move)), 2)
        max_adverse_move = round(min(abs(max_up_move), abs(max_down_move)), 2)
    
    return {
        "direction": direction,
        "target_pct": target_pct,
        "stop_pct": stop_pct,
        "hit_target": hit_target,
        "hit_stop": hit_stop,
        "max_favorable_move": max_favorable_move,
        "max_adverse_move": max_adverse_move,
        "evaluated_bars": len(future_klines),
        "entry_price": entry_price,
        "max_high": max_high,
        "min_low": min_low,
    }


# ============================================
# 主流程
# ============================================

def main():
    """主流程"""
    
    print("=" * 60)
    print("📈 缠论 AI 预测结果回填工具（新版）")
    print("=" * 60)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    records = fetch_pending_records(conn)
    
    print(f"🔍 待回填记录数: {len(records)}\n")
    
    if not records:
        print("✅ 没有待评估的快照")
        conn.close()
        return
    
    success_count = 0
    failed_count = 0
    
    for rec in records:
        record_id, symbol, interval, timestamp_str, ai_json_str = rec
        
        print(f"评估快照 #{record_id}: {symbol} @ {interval}")
        print(f"  分析时间: {timestamp_str}")
        
        try:
            # 1. 解析 AI JSON
            ai_json = json.loads(ai_json_str)
            
            # 2. 解析时间戳（ISO 格式）
            analysis_time = datetime.fromisoformat(timestamp_str)
            if analysis_time.tzinfo is None:
                analysis_time = analysis_time.replace(tzinfo=timezone.utc)
            
            # 3. 转换为毫秒时间戳
            start_time_ms = int(analysis_time.timestamp() * 1000)
            
            # 4. 标准化交易对格式（BTC/USDT → BTCUSDT）
            binance_symbol = symbol.replace("/", "")
            
            # 5. 拉取未来 K 线（从分析时间开始）
            print(f"  ⏳ 拉取未来 {FUTURE_BARS} 根 K 线...")
            
            klines = get_klines(
                symbol=binance_symbol,
                interval=interval,
                limit=FUTURE_BARS,
                start_time=start_time_ms
            )
            
            if len(klines) < FUTURE_BARS:
                print(f"  ⚠️  K 线数量不足（{len(klines)}/{FUTURE_BARS}），跳过")
                failed_count += 1
                continue
            
            # 6. 获取入场价格（分析时的价格）
            # 从数据库读取
            cursor = conn.execute(
                "SELECT price FROM analysis_snapshot WHERE id = ?",
                (record_id,)
            )
            entry_price = cursor.fetchone()[0]
            
            # 7. 评估结果
            outcome = evaluate_outcome(ai_json, klines, entry_price)
            
            if "error" in outcome:
                print(f"  ✗ 评估失败: {outcome['error']}")
                failed_count += 1
                continue
            
            # 8. 保存结果
            mark_as_evaluated(conn, record_id, outcome)
            
            print(f"  方向: {outcome['direction']}")
            print(f"  目标: {outcome['target_pct']}% | 止损: {outcome['stop_pct']}%")
            print(f"  命中目标: {'✓' if outcome['hit_target'] else '✗'}")
            print(f"  触发止损: {'✓' if outcome['hit_stop'] else '✗'}")
            print(f"  最大有利变动: {outcome['max_favorable_move']}%")
            print(f"  最大不利变动: {outcome['max_adverse_move']}%")
            print(f"  ✓ outcome 已回填\n")
            
            success_count += 1
            
        except Exception as e:
            print(f"  ✗ 处理失败: {e}\n")
            failed_count += 1
            import traceback
            traceback.print_exc()
            continue
    
    conn.close()
    
    print("=" * 60)
    print(f"✅ 评估完成: 成功 {success_count} 条，失败 {failed_count} 条")


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
