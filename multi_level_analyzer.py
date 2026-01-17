# -*- coding: utf-8 -*-
"""多级别联立分析模块

实现缠论的多级别联立分析：
- 大级别（4H）：确定大方向和主要中枢
- 中级别（1H）：找买卖点
- 小级别（15M）：精确入场时机

使用方法：
    python multi_level_analyzer.py BTCUSDT
    python multi_level_analyzer.py BTCUSDT --save
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from binance import get_klines
from chanlun_adapter import convert_to_chanlun_bars
from chanlun_icl import ICL
from chanlun_ai_exporter import ChanlunAIExporter

# Windows 终端编码修复
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')


# 默认的多级别配置
DEFAULT_LEVELS = {
    "large": {"interval": "4h", "limit": 500, "name": "大级别"},
    "medium": {"interval": "1h", "limit": 500, "name": "中级别"},
    "small": {"interval": "15m", "limit": 500, "name": "小级别"},
}


class MultiLevelAnalyzer:
    """多级别联立分析器"""
    
    def __init__(self, symbol: str, levels: Dict[str, Dict] = None):
        """初始化多级别分析器
        
        参数：
        - symbol: 交易对，如 "BTCUSDT"
        - levels: 级别配置，默认使用 4H/1H/15M
        """
        self.symbol = symbol.upper().replace("/", "")
        self.display_symbol = f"{self.symbol[:3]}/{self.symbol[3:]}" if len(self.symbol) > 3 else self.symbol
        self.levels = levels or DEFAULT_LEVELS
        
        # 存储各级别的分析结果
        self._results: Dict[str, Dict[str, Any]] = {}
        self._latest_price: float = 0.0
    
    def analyze(self) -> Dict[str, Any]:
        """执行多级别分析
        
        返回：
        - 包含所有级别分析结果的综合 JSON
        """
        print(f"\n{'='*60}")
        print(f"[MULTI] Multi-Level Analysis: {self.display_symbol}")
        print(f"{'='*60}")
        
        exporter = ChanlunAIExporter()
        
        for level_key, level_config in self.levels.items():
            interval = level_config["interval"]
            limit = level_config["limit"]
            name = level_config["name"]
            
            print(f"\n[UP] 分析 {name} ({interval})...")
            
            try:
                # 1. 获取K线数据
                klines = get_klines(self.symbol, interval, limit=limit)
                print(f"   [v] 获取到 {len(klines)} 根K线")
                
                # 2. 转换格式
                bars = convert_to_chanlun_bars(klines)
                df = pd.DataFrame(bars)
                df = df.rename(columns={
                    "date": "date", "o": "open", "h": "high",
                    "l": "low", "c": "close", "a": "volume",
                })
                
                # 3. 缠论计算
                frequency_map = {
                    "1m": "1m", "5m": "5m", "15m": "15m",
                    "1h": "60m", "4h": "240m", "1d": "1440m"
                }
                frequency = frequency_map.get(interval, interval)
                
                icl = ICL(code=self.display_symbol, frequency=frequency, config={})
                icl = icl.process_klines(df)
                
                # 4. 导出结构
                ai_json = exporter.export(
                    icl=icl,
                    symbol=self.display_symbol,
                    interval=interval,
                    klines=klines,
                )
                
                # 5. 提取关键信息
                summary = self._extract_level_summary(icl, klines, level_key)
                
                self._results[level_key] = {
                    "interval": interval,
                    "name": name,
                    "ai_json": ai_json,
                    "summary": summary,
                    "icl": icl,
                    "klines": klines,
                }
                
                # 更新最新价格（使用小级别的最新价格）
                if level_key == "small":
                    self._latest_price = klines[-1]["close"]
                
                print(f"   [v] {name}分析完成")
                self._print_level_summary(summary, name)
                
            except Exception as e:
                print(f"   [x] {name}分析失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 6. 综合分析
        combined = self._combine_analysis()
        
        return combined
    
    def _extract_level_summary(self, icl: Any, klines: List[Dict], level_key: str) -> Dict[str, Any]:
        """提取单个级别的关键摘要"""
        
        bis = icl.get_bis() if hasattr(icl, 'get_bis') else []
        xds = icl.get_xds() if hasattr(icl, 'get_xds') else []
        bi_zss = icl.get_bi_zss() if hasattr(icl, 'get_bi_zss') else []
        
        latest_price = klines[-1]["close"] if klines else 0
        
        # 最新笔
        latest_bi = bis[-1] if bis else None
        latest_bi_info = None
        if latest_bi:
            latest_bi_info = {
                "type": latest_bi.type,
                "start_price": latest_bi.start_price,
                "end_price": latest_bi.end_price,
                "mmds": [m.name for m in (latest_bi.mmds or [])],
                "has_bc": any(getattr(bc, 'bc', False) for bc in (latest_bi.bcs or [])),
            }
        
        # 最新线段
        latest_xd = xds[-1] if xds else None
        latest_xd_info = None
        if latest_xd:
            latest_xd_info = {
                "type": latest_xd.type,
                "start_price": latest_xd.start_price,
                "end_price": latest_xd.end_price,
            }
        
        # 最新中枢
        latest_zs = bi_zss[-1] if bi_zss else None
        latest_zs_info = None
        price_vs_zs = "unknown"
        if latest_zs:
            latest_zs_info = {
                "zg": latest_zs.zg,
                "zd": latest_zs.zd,
                "gg": getattr(latest_zs, 'gg', latest_zs.zg),
                "dd": getattr(latest_zs, 'dd', latest_zs.zd),
            }
            # 判断价格相对中枢位置
            if latest_price > latest_zs.zg:
                price_vs_zs = "above"  # 在中枢上方
            elif latest_price < latest_zs.zd:
                price_vs_zs = "below"  # 在中枢下方
            else:
                price_vs_zs = "inside"  # 在中枢内部
        
        # 收集所有买卖点和背驰
        all_mmds = []
        all_bcs = []
        for bi in bis[-5:]:  # 最近5笔
            all_mmds.extend([m.name for m in (bi.mmds or [])])
            if any(getattr(bc, 'bc', False) for bc in (bi.bcs or [])):
                all_bcs.append(f"bi_{bi.type}")
        
        # 判断趋势
        trend = self._determine_trend(bis, xds, bi_zss)
        
        return {
            "latest_price": latest_price,
            "bi_count": len(bis),
            "xd_count": len(xds),
            "zs_count": len(bi_zss),
            "latest_bi": latest_bi_info,
            "latest_xd": latest_xd_info,
            "latest_zs": latest_zs_info,
            "price_vs_zs": price_vs_zs,
            "recent_mmds": list(set(all_mmds)),
            "recent_bcs": list(set(all_bcs)),
            "trend": trend,
        }
    
    def _determine_trend(self, bis: List, xds: List, zss: List) -> str:
        """判断当前趋势
        
        返回: "up_trend" | "down_trend" | "consolidation"
        """
        if not bis or len(bis) < 3:
            return "unknown"
        
        # 方法1: 基于最近3笔的高低点
        recent_bis = bis[-5:]
        highs = [bi.high for bi in recent_bis]
        lows = [bi.low for bi in recent_bis]
        
        # 检查高点和低点是否递增/递减
        highs_rising = all(highs[i] <= highs[i+1] for i in range(len(highs)-1))
        lows_rising = all(lows[i] <= lows[i+1] for i in range(len(lows)-1))
        highs_falling = all(highs[i] >= highs[i+1] for i in range(len(highs)-1))
        lows_falling = all(lows[i] >= lows[i+1] for i in range(len(lows)-1))
        
        if highs_rising and lows_rising:
            return "up_trend"
        elif highs_falling and lows_falling:
            return "down_trend"
        
        # 方法2: 基于中枢
        if zss and len(zss) >= 2:
            zs1, zs2 = zss[-2], zss[-1]
            if zs2.zd > zs1.zg:
                return "up_trend"  # 中枢上移
            elif zs2.zg < zs1.zd:
                return "down_trend"  # 中枢下移
        
        return "consolidation"
    
    def _print_level_summary(self, summary: Dict, name: str) -> None:
        """打印单个级别的摘要"""
        
        trend_map = {
            "up_trend": "[UP] Up Trend",
            "down_trend": "[DN] Down Trend",
            "consolidation": "[RNG] Consolidation",
            "unknown": "[?] Unknown",
        }
        
        pos_map = {
            "above": "中枢上方",
            "below": "中枢下方",
            "inside": "中枢内部",
            "unknown": "无中枢",
        }
        
        print(f"   └─ 趋势: {trend_map.get(summary['trend'], '?')}")
        print(f"   └─ 位置: {pos_map.get(summary['price_vs_zs'], '?')}")
        
        if summary.get('recent_mmds'):
            print(f"   └─ 信号: {', '.join(summary['recent_mmds'])}")
        
        if summary.get('latest_zs'):
            zs = summary['latest_zs']
            print(f"   └─ 中枢: {zs['zd']:.0f} - {zs['zg']:.0f}")
    
    def _combine_analysis(self) -> Dict[str, Any]:
        """综合多级别分析结果"""
        
        print(f"\n{'='*60}")
        print("[LNK] 综合多级别分析")
        print(f"{'='*60}")
        
        # 提取各级别摘要
        large = self._results.get("large", {}).get("summary", {})
        medium = self._results.get("medium", {}).get("summary", {})
        small = self._results.get("small", {}).get("summary", {})
        
        # 综合判断
        combined_judgment = self._make_combined_judgment(large, medium, small)
        
        # 构造综合 JSON
        combined = {
            "meta": {
                "symbol": self.display_symbol,
                "analysis_type": "multi_level",
                "levels": list(self.levels.keys()),
                "timestamp": datetime.now().isoformat(),
                "latest_price": self._latest_price,
            },
            "levels": {},
            "combined_judgment": combined_judgment,
        }
        
        # 添加各级别数据
        for level_key, result in self._results.items():
            combined["levels"][level_key] = {
                "interval": result["interval"],
                "name": result["name"],
                "summary": result["summary"],
                "ai_json": result["ai_json"],
            }
        
        # 打印综合判断
        self._print_combined_judgment(combined_judgment)
        
        return combined
    
    def _make_combined_judgment(
        self,
        large: Dict,
        medium: Dict,
        small: Dict,
    ) -> Dict[str, Any]:
        """综合多级别做出判断"""
        
        # 趋势一致性检查
        trends = [
            large.get("trend", "unknown"),
            medium.get("trend", "unknown"),
            small.get("trend", "unknown"),
        ]
        
        # 计算趋势得分
        up_score = trends.count("up_trend")
        down_score = trends.count("down_trend")
        
        # 主趋势判断
        if up_score >= 2:
            main_trend = "up"
            trend_strength = "strong" if up_score == 3 else "moderate"
        elif down_score >= 2:
            main_trend = "down"
            trend_strength = "strong" if down_score == 3 else "moderate"
        else:
            main_trend = "range"
            trend_strength = "weak"
        
        # 信号汇总
        all_signals = []
        all_signals.extend(large.get("recent_mmds", []))
        all_signals.extend(medium.get("recent_mmds", []))
        all_signals.extend(small.get("recent_mmds", []))
        
        # 买卖点优先级
        buy_signals = [s for s in all_signals if "buy" in s.lower()]
        sell_signals = [s for s in all_signals if "sell" in s.lower()]
        
        # 位置判断
        positions = [
            large.get("price_vs_zs", "unknown"),
            medium.get("price_vs_zs", "unknown"),
            small.get("price_vs_zs", "unknown"),
        ]
        
        # 综合建议
        suggestion = self._generate_suggestion(
            main_trend, trend_strength, buy_signals, sell_signals, positions, medium
        )
        
        return {
            "main_trend": main_trend,
            "trend_strength": trend_strength,
            "trend_alignment": {
                "large": large.get("trend", "unknown"),
                "medium": medium.get("trend", "unknown"),
                "small": small.get("trend", "unknown"),
            },
            "position_alignment": {
                "large": large.get("price_vs_zs", "unknown"),
                "medium": medium.get("price_vs_zs", "unknown"),
                "small": small.get("price_vs_zs", "unknown"),
            },
            "signals": {
                "buy_signals": list(set(buy_signals)),
                "sell_signals": list(set(sell_signals)),
            },
            "key_levels": {
                "large_zs": large.get("latest_zs"),
                "medium_zs": medium.get("latest_zs"),
                "small_zs": small.get("latest_zs"),
            },
            "suggestion": suggestion,
        }
    
    def _generate_suggestion(
        self,
        main_trend: str,
        trend_strength: str,
        buy_signals: List[str],
        sell_signals: List[str],
        positions: List[str],
        medium: Dict,
    ) -> Dict[str, Any]:
        """生成综合交易建议"""
        
        suggestion = {
            "direction": "wait",
            "confidence": "low",
            "action": "观望",
            "reason": "",
            "entry_condition": "",
            "stop_loss_hint": "",
            "target_hint": "",
        }
        
        # 强势上涨 + 有买点信号
        if main_trend == "up" and trend_strength == "strong":
            if buy_signals:
                suggestion.update({
                    "direction": "long",
                    "confidence": "high",
                    "action": "积极做多",
                    "reason": f"三级别趋势一致向上，出现买点信号: {', '.join(buy_signals)}",
                    "entry_condition": "小级别回调不破中枢下沿时入场",
                    "stop_loss_hint": "止损设在小级别中枢下沿下方",
                    "target_hint": "目标看大级别前高或中枢上沿",
                })
            else:
                suggestion.update({
                    "direction": "long",
                    "confidence": "medium",
                    "action": "等待回调做多",
                    "reason": "三级别趋势一致向上，但暂无买点信号",
                    "entry_condition": "等待小级别出现买点信号",
                })
        
        # 强势下跌 + 有卖点信号
        elif main_trend == "down" and trend_strength == "strong":
            if sell_signals:
                suggestion.update({
                    "direction": "short",
                    "confidence": "high",
                    "action": "积极做空",
                    "reason": f"三级别趋势一致向下，出现卖点信号: {', '.join(sell_signals)}",
                    "entry_condition": "小级别反弹不破中枢上沿时入场",
                    "stop_loss_hint": "止损设在小级别中枢上沿上方",
                    "target_hint": "目标看大级别前低或中枢下沿",
                })
            else:
                suggestion.update({
                    "direction": "short",
                    "confidence": "medium",
                    "action": "等待反弹做空",
                    "reason": "三级别趋势一致向下，但暂无卖点信号",
                    "entry_condition": "等待小级别出现卖点信号",
                })
        
        # 中等强度趋势
        elif trend_strength == "moderate":
            if main_trend == "up" and buy_signals:
                suggestion.update({
                    "direction": "long",
                    "confidence": "medium",
                    "action": "谨慎做多",
                    "reason": f"多数级别向上，有买点: {', '.join(buy_signals)}",
                    "entry_condition": "确认小级别企稳后入场",
                })
            elif main_trend == "down" and sell_signals:
                suggestion.update({
                    "direction": "short",
                    "confidence": "medium",
                    "action": "谨慎做空",
                    "reason": f"多数级别向下，有卖点: {', '.join(sell_signals)}",
                    "entry_condition": "确认小级别走弱后入场",
                })
            else:
                suggestion.update({
                    "direction": "wait",
                    "confidence": "low",
                    "action": "观望",
                    "reason": "趋势不够明确，等待更清晰的信号",
                })
        
        # 震荡
        else:
            # 检查中级别中枢
            medium_zs = medium.get("latest_zs")
            if medium_zs:
                suggestion.update({
                    "direction": "range",
                    "confidence": "medium",
                    "action": "高抛低吸",
                    "reason": "多级别趋势不一致，处于震荡格局",
                    "entry_condition": f"中级别中枢区间: {medium_zs['zd']:.0f} - {medium_zs['zg']:.0f}",
                    "stop_loss_hint": "突破中枢边界止损",
                    "target_hint": "中枢另一边界止盈",
                })
            else:
                suggestion.update({
                    "direction": "wait",
                    "confidence": "low",
                    "action": "观望",
                    "reason": "走势不明确，建议等待",
                })
        
        return suggestion
    
    def _print_combined_judgment(self, judgment: Dict) -> None:
        """打印综合判断结果"""
        
        trend_map = {
            "up": "[UP] 上涨",
            "down": "[DN] 下跌",
            "range": "[RNG] 震荡",
        }
        
        strength_map = {
            "strong": "💪 强",
            "moderate": "[MID] 中",
            "weak": "[WK] 弱",
        }
        
        confidence_map = {
            "high": "[G] 高",
            "medium": "[Y] 中",
            "low": "[R] 低",
        }
        
        suggestion = judgment.get("suggestion", {})
        
        print(f"\n[TGT] 主趋势: {trend_map.get(judgment['main_trend'], '?')} ({strength_map.get(judgment['trend_strength'], '?')})")
        print(f"\n[CHT] 各级别趋势:")
        for level, trend in judgment.get("trend_alignment", {}).items():
            trend_str = {"up_trend": "[UP]", "down_trend": "[DN]", "consolidation": "[RNG]", "unknown": "[?]"}.get(trend, "[?]")
            print(f"   {level}: {trend_str}")
        
        print(f"\n[TIP] 综合建议:")
        print(f"   方向: {suggestion.get('action', '?')}")
        print(f"   信心: {confidence_map.get(suggestion.get('confidence'), '?')}")
        print(f"   原因: {suggestion.get('reason', '')}")
        
        if suggestion.get("entry_condition"):
            print(f"   入场: {suggestion['entry_condition']}")
        if suggestion.get("stop_loss_hint"):
            print(f"   止损: {suggestion['stop_loss_hint']}")
        if suggestion.get("target_hint"):
            print(f"   目标: {suggestion['target_hint']}")
        
        # 买卖点信号
        signals = judgment.get("signals", {})
        if signals.get("buy_signals"):
            print(f"\n   [BUY] 买点: {', '.join(signals['buy_signals'])}")
        if signals.get("sell_signals"):
            print(f"   [SELL] 卖点: {', '.join(signals['sell_signals'])}")
    
    def get_multi_level_prompt_data(self) -> Dict[str, Any]:
        """获取用于 AI Prompt 的多级别数据"""
        
        if not self._results:
            return {}
        
        return {
            "symbol": self.display_symbol,
            "latest_price": self._latest_price,
            "levels": {
                level_key: {
                    "interval": result["interval"],
                    "name": result["name"],
                    "summary": result["summary"],
                    "ai_json": result["ai_json"],
                }
                for level_key, result in self._results.items()
            },
        }


def main():
    """命令行入口"""
    
    parser = argparse.ArgumentParser(
        description="缠论多级别联立分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python multi_level_analyzer.py BTCUSDT
  python multi_level_analyzer.py ETHUSDT --save
        """
    )
    
    parser.add_argument("symbol", type=str, help="交易对，如: BTCUSDT")
    parser.add_argument("--save", action="store_true", help="保存分析结果到文件")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON")
    
    args = parser.parse_args()
    
    try:
        analyzer = MultiLevelAnalyzer(symbol=args.symbol)
        result = analyzer.analyze()
        
        if args.json:
            print("\n" + "=" * 60)
            print("📄 完整 JSON 数据:")
            print("=" * 60)
            # 移除 icl 对象（不可序列化）
            for level in result.get("levels", {}).values():
                if "icl" in level:
                    del level["icl"]
                if "klines" in level:
                    del level["klines"]
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        
        if args.save:
            output_dir = Path(__file__).parent / "output"
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"multi_level_{args.symbol}_{timestamp}.json"
            
            # 移除不可序列化的对象
            save_result = result.copy()
            for level in save_result.get("levels", {}).values():
                if "icl" in level:
                    del level["icl"]
                if "klines" in level:
                    del level["klines"]
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(save_result, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"\n[SAV] 结果已保存: {output_file}")
        
        print("\n[OK] 多级别分析完成！\n")
        
    except KeyboardInterrupt:
        print("\n\n[WARN]️ 用户中断\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n[ERR] 错误: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
