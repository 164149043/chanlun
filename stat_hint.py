"""A2.5 统计提示模块
====================

提供结构对应的历史统计提示，不干预系统决策。

- 只读：只从 SQLite `analysis_snapshot` 读取数据，不写入
- 维度：按 (symbol, interval, 是否在中枢内/外) 统计
- 输出：固定结构，包含 sample / win_rate / level / hint
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any

DB_PATH = Path(__file__).parent / "chanlun_ai.db"

# 最小样本数，小于此数量视为样本不足
MIN_SAMPLE = 20


def _compute_in_zs(ai: Dict[str, Any], price: float) -> str:
    """根据 AI 输出判断当前价格是否在中枢区间内

    返回值：
    - "in"      当前价落在中枢区间内
    - "out"     当前价在中枢区间外
    - "unknown" 无法判断（缺少中枢数据）
    """
    try:
        zs = ai.get("structure_judgement", {}).get("zs", {})
        zs_range = zs.get("range") or []
        if not (isinstance(zs_range, list) and len(zs_range) == 2):
            return "unknown"
        low, high = float(zs_range[0]), float(zs_range[1])
        if low <= price <= high:
            return "in"
        else:
            return "out"
    except Exception:
        return "unknown"


def get_stat_hint(symbol: str, interval: str, in_zs: bool) -> Dict[str, Any]:
    """返回当前结构的统计提示（A2.5）

    参数：
    - symbol:   交易对，例如 "BTC/USDT"
    - interval: 周期，例如 "1h"、"4h"
    - in_zs:    当前结构是否在中枢内（调用方计算的布尔值）

    返回：
    ```python
    {
        "sample": int,              # 有效样本数
        "win_rate": float | None,   # 胜率（样本不足时为 None）
        "level": "high" | "mid" | "low" | "unknown",
        "hint": str,                # 中文提示文案
    }
    ```
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        # 只取当前 symbol + interval 下，已评估且有 outcome 的记录
        rows = conn.execute(
            """
            SELECT price, ai_json, outcome_json
            FROM analysis_snapshot
            WHERE evaluated = 1
              AND symbol = ?
              AND interval = ?
              AND ai_json IS NOT NULL
              AND outcome_json IS NOT NULL
            """,
            (symbol, interval),
        ).fetchall()
    finally:
        conn.close()

    target_label = "in" if in_zs else "out"

    total = 0
    wins = 0

    for price, ai_json_str, outcome_json_str in rows:
        try:
            ai = json.loads(ai_json_str)
            outcome = json.loads(outcome_json_str)
        except Exception:
            continue

        label = _compute_in_zs(ai, float(price))
        if label != target_label:
            continue

        total += 1
        if bool(outcome.get("hit_target")):
            wins += 1

    # 样本不足：直接返回 unknown
    if total < MIN_SAMPLE:
        return {
            "sample": total,
            "win_rate": None,
            "level": "unknown",
            "hint": "样本数量不足，暂无可靠统计结论",
        }

    win_rate = round(wins / total, 3) if total > 0 else 0.0

    # A2.5 分级规则
    if win_rate >= 0.60:
        level = "high"
        hint = "历史统计显示，该结构具备明显统计优势"
    elif win_rate >= 0.50:
        level = "mid"
        hint = "历史统计显示，该结构表现中性，可谨慎参考"
    else:
        level = "low"
        hint = "历史统计显示，该结构胜率偏低，谨慎参考"

    return {
        "sample": total,
        "win_rate": win_rate,
        "level": level,
        "hint": hint,
    }


if __name__ == "__main__":
    # 简单自测：不会抛异常即可
    example = get_stat_hint("BTC/USDT", "1h", in_zs=True)
    print(example)
