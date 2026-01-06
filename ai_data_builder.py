"""AI 数据构建模块（ai_data_builder）

本模块的职责：
- 从缠论引擎的 ICL 结果中提取关键信息
- 构造符合 AI 分析要求的标准化 JSON 结构
- 不做任何技术分析或策略判断，只做数据映射

设计原则：
- 输入：ICL 对象 + 市场上下文（最新价格、交易对等）
- 输出：7 大块标准 JSON（meta / market / bi / segment / center / signal / context）
- 保持数据完整性，不裁剪关键字段
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def build_ai_input_json(
    *,
    icl: Any,
    symbol: str,
    interval: str,
    latest_price: float,
    timestamp: Optional[datetime] = None,
    kline_count: int = 0,
    trend_hint: str = "range",
    volatility_hint: str = "medium",
    analysis_goal: str = "predict_next_move",
) -> Dict[str, Any]:
    """构造 AI 输入 JSON

    参数：
    - icl: 缠论引擎返回的 ICL 对象
    - symbol: 交易对，如 "BTC/USDT"
    - interval: 周期，如 "60m"
    - latest_price: 当前最新价格
    - timestamp: 分析时间戳（可选，默认为当前时间）
    - kline_count: K 线数量
    - trend_hint: 趋势提示（range/up/down）
    - volatility_hint: 波动性提示（low/medium/high）
    - analysis_goal: 分析目标

    返回：
    - 标准化的 AI 输入 JSON 字典
    """

    if timestamp is None:
        timestamp = datetime.now()

    # 1. meta —— 分析元信息
    meta = _build_meta(
        symbol=symbol,
        interval=interval,
        timestamp=timestamp,
        kline_count=kline_count,
        icl=icl,
    )

    # 2. market —— 当前市场状态
    market = _build_market(
        latest_price=latest_price,
        trend_hint=trend_hint,
        volatility_hint=volatility_hint,
    )

    # 3. bi —— 最近的笔（取最后 9-15 条）
    bi = _build_bi(icl=icl, max_count=15)

    # 4. segment —— 线段（取最后 3-5 条）
    segment = _build_segment(icl=icl, max_count=5)

    # 5. center —— 中枢
    center = _build_center(icl=icl)

    # 6. signal —— 买卖点/背驰汇总
    signal = _build_signal(icl=icl)

    # 7. context —— AI 提示上下文
    context = _build_context(analysis_goal=analysis_goal)

    return {
        "meta": meta,
        "market": market,
        "bi": bi,
        "segment": segment,
        "center": center,
        "signal": signal,
        "context": context,
    }


def _build_meta(
    symbol: str,
    interval: str,
    timestamp: datetime,
    kline_count: int,
    icl: Any,
) -> Dict[str, Any]:
    """构造 meta 块"""

    bis = icl.get_bis() if hasattr(icl, 'get_bis') else []
    xds = icl.get_xds() if hasattr(icl, 'get_xds') else []

    # 统计中枢数量（笔中枢 + 线段中枢）
    center_count = 0
    if hasattr(icl, 'get_bi_zss'):
        center_count += len(icl.get_bi_zss(None) or [])
    if hasattr(icl, 'get_xd_zss'):
        center_count += len(icl.get_xd_zss(None) or [])

    return {
        "symbol": symbol,
        "interval": interval,
        "timestamp": timestamp.isoformat(),
        "engine": "chanlun-local",  # 使用我们自己的简化引擎
        "engine_version": "simple-icl-v1",
        "data_size": {
            "kline": kline_count,
            "bi": len(bis),
            "segment": len(xds),
            "center": center_count,
        },
    }


def _build_market(
    latest_price: float,
    trend_hint: str,
    volatility_hint: str,
) -> Dict[str, Any]:
    """构造 market 块"""

    return {
        "latest_price": latest_price,
        "trend_hint": trend_hint,
        "volatility_hint": volatility_hint,
    }


def _build_bi(icl: Any, max_count: int = 15) -> List[Dict[str, Any]]:
    """构造 bi 块（最近的笔）

    只取最后 max_count 条，避免 AI 输入过长
    """

    if not hasattr(icl, 'get_bis'):
        return []

    bis = icl.get_bis() or []

    # 只取最后 max_count 条
    recent_bis = bis[-max_count:] if len(bis) > max_count else bis

    result = []
    for bi in recent_bis:
        # 提取笔的关键字段
        bi_dict = {
            "index": getattr(bi, 'index', 0),
            "direction": getattr(bi, 'type', 'unknown'),
            "is_done": True,  # 简化实现中默认都是完成的
        }
        
        # 时间字段
        if hasattr(bi, 'start_time'):
            start_time = getattr(bi, 'start_time')
            bi_dict["start_time"] = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
        
        if hasattr(bi, 'end_time'):
            end_time = getattr(bi, 'end_time')
            bi_dict["end_time"] = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
        
        # 价格字段
        if hasattr(bi, 'start_price'):
            bi_dict["start_price"] = float(getattr(bi, 'start_price'))
        
        if hasattr(bi, 'end_price'):
            bi_dict["end_price"] = float(getattr(bi, 'end_price'))

        # 如果有买卖点
        mmds = getattr(bi, 'mmds', []) or []
        if mmds:
            # 取最后一个买卖点的名称
            bi_dict["buy_sell_point"] = getattr(mmds[-1], 'name', None)
        else:
            bi_dict["buy_sell_point"] = None

        # 如果有背驰
        bcs = getattr(bi, 'bcs', []) or []
        divergence_types = [getattr(bc, 'type', '') for bc in bcs if getattr(bc, 'bc', False)]
        bi_dict["divergence"] = divergence_types[0] if divergence_types else None

        result.append(bi_dict)

    return result


def _build_segment(icl: Any, max_count: int = 5) -> List[Dict[str, Any]]:
    """构造 segment 块（线段）

    只取最后 max_count 条
    """

    if not hasattr(icl, 'get_xds'):
        return []

    xds = icl.get_xds() or []
    recent_xds = xds[-max_count:] if len(xds) > max_count else xds

    result = []
    for xd in recent_xds:
        xd_dict = {
            "index": getattr(xd, 'index', 0),
            "direction": getattr(xd, 'type', 'unknown'),
            "is_done": True,
        }
        
        # 时间字段
        if hasattr(xd, 'start_time'):
            start_time = getattr(xd, 'start_time')
            xd_dict["start_time"] = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
        
        if hasattr(xd, 'end_time'):
            end_time = getattr(xd, 'end_time')
            xd_dict["end_time"] = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
        
        # 价格字段
        if hasattr(xd, 'start_price'):
            xd_dict["start_price"] = float(getattr(xd, 'start_price'))
        
        if hasattr(xd, 'end_price'):
            xd_dict["end_price"] = float(getattr(xd, 'end_price'))

        # 背驰
        bcs = getattr(xd, 'bcs', []) or []
        divergence_types = [getattr(bc, 'type', '') for bc in bcs if getattr(bc, 'bc', False)]
        xd_dict["divergence"] = divergence_types[0] if divergence_types else None

        result.append(xd_dict)

    return result


def _build_center(icl: Any) -> List[Dict[str, Any]]:
    """构造 center 块（中枢）"""

    result = []

    # 笔中枢
    if hasattr(icl, 'get_bi_zss'):
        bi_zss = icl.get_bi_zss(None) or []
        for zs in bi_zss:
            zs_dict = {
                "index": getattr(zs, 'index', 0),
                "type": "bi",
                "zs_type": getattr(zs, 'zs_type', 'standard'),
            }
            
            # 时间字段
            if hasattr(zs, 'start_time'):
                start_time = getattr(zs, 'start_time')
                zs_dict["start_time"] = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
            
            if hasattr(zs, 'end_time'):
                end_time = getattr(zs, 'end_time')
                zs_dict["end_time"] = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
            
            # 高低点字段
            if hasattr(zs, 'high'):
                zs_dict["high"] = float(getattr(zs, 'high'))
            
            if hasattr(zs, 'low'):
                zs_dict["low"] = float(getattr(zs, 'low'))
            
            # 等级和关系
            if hasattr(zs, 'level'):
                zs_dict["level"] = int(getattr(zs, 'level'))
            
            if hasattr(zs, 'relation'):
                zs_dict["relation"] = str(getattr(zs, 'relation'))
            
            result.append(zs_dict)

    # 线段中枢
    if hasattr(icl, 'get_xd_zss'):
        xd_zss = icl.get_xd_zss(None) or []
        for zs in xd_zss:
            zs_dict = {
                "index": getattr(zs, 'index', 0),
                "type": "segment",
                "zs_type": getattr(zs, 'zs_type', 'standard'),
            }
            
            # 时间字段
            if hasattr(zs, 'start_time'):
                start_time = getattr(zs, 'start_time')
                zs_dict["start_time"] = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
            
            if hasattr(zs, 'end_time'):
                end_time = getattr(zs, 'end_time')
                zs_dict["end_time"] = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
            
            # 高低点字段
            if hasattr(zs, 'high'):
                zs_dict["high"] = float(getattr(zs, 'high'))
            
            if hasattr(zs, 'low'):
                zs_dict["low"] = float(getattr(zs, 'low'))
            
            # 等级和关系
            if hasattr(zs, 'level'):
                zs_dict["level"] = int(getattr(zs, 'level'))
            
            if hasattr(zs, 'relation'):
                zs_dict["relation"] = str(getattr(zs, 'relation'))
            
            result.append(zs_dict)

    return result


def _build_signal(icl: Any) -> Dict[str, Any]:
    """构造 signal 块（买卖点/背驰汇总）"""

    buy_sell_points = []
    divergences = []

    # 从笔中收集
    if hasattr(icl, 'get_bis'):
        bis = icl.get_bis() or []
        for bi in bis:
            mmds = getattr(bi, 'mmds', []) or []
            for mmd in mmds:
                name = getattr(mmd, 'name', None)
                if name:
                    buy_sell_points.append(name)

            bcs = getattr(bi, 'bcs', []) or []
            for bc in bcs:
                if getattr(bc, 'bc', False):
                    bc_type = getattr(bc, 'type', '')
                    if bc_type:
                        divergences.append(bc_type)

    # 从线段中收集
    if hasattr(icl, 'get_xds'):
        xds = icl.get_xds() or []
        for xd in xds:
            mmds = getattr(xd, 'mmds', []) or []
            for mmd in mmds:
                name = getattr(mmd, 'name', None)
                if name:
                    buy_sell_points.append(name)

            bcs = getattr(xd, 'bcs', []) or []
            for bc in bcs:
                if getattr(bc, 'bc', False):
                    bc_type = getattr(bc, 'type', '')
                    if bc_type:
                        divergences.append(bc_type)

    # 去重
    buy_sell_points = sorted(set(buy_sell_points))
    divergences = sorted(set(divergences))

    return {
        "buy_sell_points": buy_sell_points,
        "divergences": divergences,
        "last_signal_time": None,  # 简化实现中暂不提取时间
    }


def _build_context(analysis_goal: str) -> Dict[str, Any]:
    """构造 context 块"""

    return {
        "analysis_goal": analysis_goal,
        "market_type": "crypto",
        "allowed_strategy": ["trend_follow", "range_trade"],
    }
