"""缠论 AI JSON 导出器

本模块的职责：
- 从 ICL 结构中提取关键信息
- 构造符合 AI 分析要求的标准化 JSON
- 提供简洁的摘要信息用于终端输出
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd


class ChanlunAIExporter:
    """缠论结构 → AI JSON 导出器"""
    
    def export(
        self,
        icl: Any,
        symbol: str,
        interval: str,
        klines: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """导出完整的 AI 分析 JSON
        
        参数：
        - icl: ICL 缠论计算结果对象
        - symbol: 交易对，如 "BTC/USDT"
        - interval: 周期，如 "1h"
        - klines: 原始 K 线数据列表
        
        返回：
        - 符合 AI 输入规范的 JSON 字典
        """
        
        latest_kline = klines[-1] if klines else {}
        latest_price = latest_kline.get("close", 0.0)
        
        # 1. meta - 元信息
        meta = self._build_meta(
            symbol=symbol,
            interval=interval,
            timestamp=datetime.now(),
            kline_count=len(klines),
            icl=icl,
        )
        
        # 2. market - 市场状态
        market = self._build_market(latest_price=latest_price)
        
        # 3. bi - 笔（取最后 15 条）
        bi = self._build_bi(icl=icl, max_count=15)
        
        # 4. segment - 线段（取最后 5 条）
        segment = self._build_segment(icl=icl, max_count=5)
        
        # 5. center - 中枢
        center = self._build_center(icl=icl)
        
        # 6. signal - 买卖点/背驰汇总
        signal = self._build_signal(icl=icl)
        
        # 7. context - AI 提示上下文
        context = {
            "analysis_goal": "predict_next_move",
            "market_type": "crypto",
            "allowed_strategy": ["trend_follow", "range_trade"],
        }
        
        # 8. structure_summary - 结构摘要（新增）
        structure_summary = self._build_structure_summary(icl=icl, latest_price=latest_price)
        
        return {
            "meta": meta,
            "market": market,
            "bi": bi,
            "segment": segment,
            "center": center,
            "signal": signal,
            "context": context,
            "structure_summary": structure_summary,
        }
    
    def export_summary(self, icl: Any, latest_price: float) -> Dict[str, Any]:
        """导出简洁摘要（用于终端输出）
        
        返回：
        - summary: 包含关键信息的摘要字典
        """
        
        bis = icl.get_bis() if hasattr(icl, 'get_bis') else []
        xds = icl.get_xds() if hasattr(icl, 'get_xds') else []
        
        # 最新一笔状态
        latest_bi = None
        if bis:
            latest_bi = bis[-1]
        
        # 中枢信息
        centers = []
        if hasattr(icl, 'get_bi_zss'):
            bi_zss = icl.get_bi_zss(None) or []
            for zs in bi_zss:
                centers.append({
                    "type": "bi",
                    "high": getattr(zs, 'high', 0),
                    "low": getattr(zs, 'low', 0),
                    "level": getattr(zs, 'level', 1),
                    "relation": getattr(zs, 'relation', 'unknown'),
                })
        
        # 信号汇总
        signals = self._extract_signals(icl)
        
        return {
            "latest_price": latest_price,
            "latest_bi": {
                "direction": getattr(latest_bi, 'type', 'unknown') if latest_bi else None,
                "is_done": True if latest_bi else None,
            } if latest_bi else None,
            "centers": centers,
            "signals": signals,
            "bi_count": len(bis),
            "segment_count": len(xds),
        }
    
    def _build_meta(
        self,
        symbol: str,
        interval: str,
        timestamp: datetime,
        kline_count: int,
        icl: Any,
    ) -> Dict[str, Any]:
        """构造 meta 块"""
        
        bis = icl.get_bis() if hasattr(icl, 'get_bis') else []
        xds = icl.get_xds() if hasattr(icl, 'get_xds') else []
        
        center_count = 0
        if hasattr(icl, 'get_bi_zss'):
            center_count += len(icl.get_bi_zss(None) or [])
        if hasattr(icl, 'get_xd_zss'):
            center_count += len(icl.get_xd_zss(None) or [])
        
        return {
            "symbol": symbol,
            "interval": interval,
            "timestamp": timestamp.isoformat(),
            "engine": "chanlun-local",
            "engine_version": "simple-icl-v1",
            "data_size": {
                "kline": kline_count,
                "bi": len(bis),
                "segment": len(xds),
                "center": center_count,
            },
        }
    
    def _build_market(self, latest_price: float) -> Dict[str, Any]:
        """构造 market 块"""
        return {
            "latest_price": latest_price,
            "trend_hint": "range",
            "volatility_hint": "medium",
        }
    
    def _build_bi(self, icl: Any, max_count: int = 15) -> List[Dict[str, Any]]:
        """构造 bi 块（最近的笔）"""
        
        if not hasattr(icl, 'get_bis'):
            return []
        
        bis = icl.get_bis() or []
        recent_bis = bis[-max_count:] if len(bis) > max_count else bis
        
        result = []
        for bi in recent_bis:
            bi_dict = {
                "index": getattr(bi, 'index', 0),
                "direction": getattr(bi, 'type', 'unknown'),
                "is_done": True,
            }
            
            # 时间和价格
            if hasattr(bi, 'start_time'):
                start_time = getattr(bi, 'start_time')
                bi_dict["start_time"] = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
            if hasattr(bi, 'end_time'):
                end_time = getattr(bi, 'end_time')
                bi_dict["end_time"] = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
            if hasattr(bi, 'start_price'):
                bi_dict["start_price"] = float(getattr(bi, 'start_price'))
            if hasattr(bi, 'end_price'):
                bi_dict["end_price"] = float(getattr(bi, 'end_price'))
            
            # 买卖点
            mmds = getattr(bi, 'mmds', []) or []
            if mmds:
                bi_dict["buy_sell_point"] = getattr(mmds[-1], 'name', None)
            else:
                bi_dict["buy_sell_point"] = None
            
            # 背驰
            bcs = getattr(bi, 'bcs', []) or []
            divergence_types = [getattr(bc, 'type', '') for bc in bcs if getattr(bc, 'bc', False)]
            bi_dict["divergence"] = divergence_types[0] if divergence_types else None
            
            # 力度值（新增）
            if hasattr(bi, 'strength'):
                bi_dict["strength"] = round(float(getattr(bi, 'strength', 0)), 2)
            if hasattr(bi, 'macd_strength'):
                bi_dict["macd_strength"] = round(float(getattr(bi, 'macd_strength', 0)), 2)
            if hasattr(bi, 'price_strength'):
                bi_dict["price_strength"] = round(float(getattr(bi, 'price_strength', 0)), 2)
            
            result.append(bi_dict)
        
        return result
    
    def _build_segment(self, icl: Any, max_count: int = 5) -> List[Dict[str, Any]]:
        """构造 segment 块（线段）"""
        
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
            
            # 时间和价格
            if hasattr(xd, 'start_time'):
                start_time = getattr(xd, 'start_time')
                xd_dict["start_time"] = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
            if hasattr(xd, 'end_time'):
                end_time = getattr(xd, 'end_time')
                xd_dict["end_time"] = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
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
    
    def _build_center(self, icl: Any) -> List[Dict[str, Any]]:
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
                
                if hasattr(zs, 'start_time'):
                    start_time = getattr(zs, 'start_time')
                    zs_dict["start_time"] = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
                if hasattr(zs, 'end_time'):
                    end_time = getattr(zs, 'end_time')
                    zs_dict["end_time"] = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
                
                # 中枢核心价格区间（新增 ZG/ZD/GG/DD）
                if hasattr(zs, 'zg'):
                    zs_dict["zg"] = float(getattr(zs, 'zg'))  # 中枢高点
                if hasattr(zs, 'zd'):
                    zs_dict["zd"] = float(getattr(zs, 'zd'))  # 中枢低点
                if hasattr(zs, 'gg'):
                    zs_dict["gg"] = float(getattr(zs, 'gg'))  # 中枢最高点
                if hasattr(zs, 'dd'):
                    zs_dict["dd"] = float(getattr(zs, 'dd'))  # 中枢最低点
                
                # 兼容旧字段
                if hasattr(zs, 'high'):
                    zs_dict["high"] = float(getattr(zs, 'high'))
                if hasattr(zs, 'low'):
                    zs_dict["low"] = float(getattr(zs, 'low'))
                if hasattr(zs, 'level'):
                    zs_dict["level"] = int(getattr(zs, 'level'))
                if hasattr(zs, 'relation'):
                    zs_dict["relation"] = str(getattr(zs, 'relation'))
                if hasattr(zs, 'bi_count'):
                    zs_dict["bi_count"] = int(getattr(zs, 'bi_count'))  # 中枢内笔的数量
                
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
                
                if hasattr(zs, 'start_time'):
                    start_time = getattr(zs, 'start_time')
                    zs_dict["start_time"] = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
                if hasattr(zs, 'end_time'):
                    end_time = getattr(zs, 'end_time')
                    zs_dict["end_time"] = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
                
                # 中枢核心价格区间
                if hasattr(zs, 'zg'):
                    zs_dict["zg"] = float(getattr(zs, 'zg'))
                if hasattr(zs, 'zd'):
                    zs_dict["zd"] = float(getattr(zs, 'zd'))
                if hasattr(zs, 'gg'):
                    zs_dict["gg"] = float(getattr(zs, 'gg'))
                if hasattr(zs, 'dd'):
                    zs_dict["dd"] = float(getattr(zs, 'dd'))
                
                if hasattr(zs, 'high'):
                    zs_dict["high"] = float(getattr(zs, 'high'))
                if hasattr(zs, 'low'):
                    zs_dict["low"] = float(getattr(zs, 'low'))
                if hasattr(zs, 'level'):
                    zs_dict["level"] = int(getattr(zs, 'level'))
                if hasattr(zs, 'relation'):
                    zs_dict["relation"] = str(getattr(zs, 'relation'))
                
                result.append(zs_dict)
        
        return result
    
    def _build_signal(self, icl: Any) -> Dict[str, Any]:
        """构造 signal 块（买卖点/背驰汇总）"""
        
        signals = self._extract_signals(icl)
        
        return {
            "buy_sell_points": signals["buy_sell_points"],
            "divergences": signals["divergences"],
            "last_signal_time": None,
        }
    
    def _extract_signals(self, icl: Any) -> Dict[str, List[str]]:
        """提取信号汇总"""
        
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
        
        return {
            "buy_sell_points": sorted(set(buy_sell_points)),
            "divergences": sorted(set(divergences)),
        }
    
    def _build_structure_summary(self, icl: Any, latest_price: float) -> Dict[str, Any]:
        """构造结构摘要（新增）
        
        提供给 AI 的高级结构解读，包括：
        - 趋势判断
        - 价格相对中枢位置
        - 最新笔/线段状态
        - 力度对比
        """
        
        bis = icl.get_bis() if hasattr(icl, 'get_bis') else []
        xds = icl.get_xds() if hasattr(icl, 'get_xds') else []
        bi_zss = icl.get_bi_zss() if hasattr(icl, 'get_bi_zss') else []
        
        summary = {
            "trend": "unknown",
            "price_position": "unknown",
            "latest_bi_direction": "unknown",
            "latest_bi_strength": 0,
            "prev_bi_strength": 0,
            "strength_comparison": "unknown",
            "key_levels": {},
        }
        
        # 1. 趋势判断（基于最近笔的高低点）
        if len(bis) >= 5:
            recent_bis = bis[-5:]
            highs = [bi.high for bi in recent_bis]
            lows = [bi.low for bi in recent_bis]
            
            highs_rising = all(highs[i] <= highs[i+1] for i in range(len(highs)-1))
            lows_rising = all(lows[i] <= lows[i+1] for i in range(len(lows)-1))
            highs_falling = all(highs[i] >= highs[i+1] for i in range(len(highs)-1))
            lows_falling = all(lows[i] >= lows[i+1] for i in range(len(lows)-1))
            
            if highs_rising and lows_rising:
                summary["trend"] = "up_trend"
            elif highs_falling and lows_falling:
                summary["trend"] = "down_trend"
            else:
                summary["trend"] = "consolidation"
        
        # 2. 价格相对中枢位置
        if bi_zss:
            latest_zs = bi_zss[-1]
            zg = getattr(latest_zs, 'zg', 0)
            zd = getattr(latest_zs, 'zd', 0)
            
            if latest_price > zg:
                summary["price_position"] = "above_zs"
            elif latest_price < zd:
                summary["price_position"] = "below_zs"
            else:
                summary["price_position"] = "inside_zs"
            
            # 关键价位
            summary["key_levels"] = {
                "zg": zg,
                "zd": zd,
                "gg": getattr(latest_zs, 'gg', zg),
                "dd": getattr(latest_zs, 'dd', zd),
            }
        
        # 3. 最新笔状态和力度
        if bis:
            latest_bi = bis[-1]
            summary["latest_bi_direction"] = getattr(latest_bi, 'type', 'unknown')
            summary["latest_bi_strength"] = round(getattr(latest_bi, 'strength', 0), 2)
            
            if len(bis) >= 3:
                # 比较同向前笔力度
                prev_same_dir_bi = None
                for bi in reversed(bis[:-1]):
                    if bi.type == latest_bi.type:
                        prev_same_dir_bi = bi
                        break
                
                if prev_same_dir_bi:
                    summary["prev_bi_strength"] = round(getattr(prev_same_dir_bi, 'strength', 0), 2)
                    
                    if summary["latest_bi_strength"] > 0 and summary["prev_bi_strength"] > 0:
                        ratio = summary["latest_bi_strength"] / summary["prev_bi_strength"]
                        if ratio < 0.8:
                            summary["strength_comparison"] = "weakening"  # 力度减弱
                        elif ratio > 1.2:
                            summary["strength_comparison"] = "strengthening"  # 力度增强
                        else:
                            summary["strength_comparison"] = "similar"  # 力度相当
        
        # 4. 趋势描述（中文）
        trend_desc = {
            "up_trend": "上升趋势（高点和低点依次抬高）",
            "down_trend": "下降趋势（高点和低点依次降低）",
            "consolidation": "震荡盘整（无明显趋势）",
            "unknown": "未知",
        }
        summary["trend_description"] = trend_desc.get(summary["trend"], "未知")
        
        position_desc = {
            "above_zs": "价格在中枢上方（多头占优）",
            "below_zs": "价格在中枢下方（空头占优）",
            "inside_zs": "价格在中枢内部（多空博弈）",
            "unknown": "无中枢参考",
        }
        summary["position_description"] = position_desc.get(summary["price_position"], "未知")
        
        return summary
