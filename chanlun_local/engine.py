"""缠论引擎封装（engine）- 改进版

本模块的职责：
- 接收已经准备好的、完整的 K 线数据序列（不裁剪、不修改）
- 进行缠论结构计算（笔、线段、中枢等）
- 返回 ICL 对象，供上层按需读取笔、线段、中枢、买卖点、背驰等结构

改进内容（v2.0）：
1. K线包含关系处理 - 合并K线后再识别分型
2. 分型识别完善 - 严格的顶底分型判断
3. 笔算法改进 - 正确处理分型连接和笔的延伸
4. 线段算法重写 - 基于特征序列分型
5. 中枢计算优化 - 完善中枢关系判断
6. 背驰和买卖点完善 - 多维度力度计算
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import logging

import pandas as pd
import numpy as np

# 设置日志
logger = logging.getLogger(__name__)


# ============================================================
# 缠论结构对象定义
# ============================================================

class MergedKline:
    """合并后的K线对象（处理包含关系后）"""
    def __init__(
        self,
        index: int,
        date: Any,
        high: float,
        low: float,
        open_price: float,
        close: float,
        raw_indices: List[int] = None,
    ):
        self.index = index  # 合并后的索引
        self.date = date
        self.high = high
        self.low = low
        self.open = open_price
        self.close = close
        self.raw_indices = raw_indices or [index]  # 原始K线索引列表
    
    def __repr__(self):
        return f"<MergedKline idx={self.index} H={self.high:.2f} L={self.low:.2f}>"


class SimpleFX:
    """分型对象（顶分型/底分型）"""
    def __init__(
        self,
        fx_type: str,
        index: int,
        kline: MergedKline,
        price: float,
        time: Any,
        raw_index: int = None,
    ):
        self.type = fx_type  # "ding" 或 "di"
        self.index = index   # 在合并K线列表中的索引
        self.k = kline       # 中间那根K线
        self.val = price     # 分型价格（顶分型取high，底分型取low）
        self.time = time
        self.raw_index = raw_index or index  # 原始K线索引
    
    def __repr__(self):
        return f"<SimpleFX type={self.type} idx={self.index} price={self.val:.2f}>"


class SimpleKline:
    """简化的 K 线对象（用于兼容 mapper.py）"""
    def __init__(self, date: Any, high: float, low: float, close: float):
        self.date = date
        self.high = high
        self.low = low
        self.close = close


class SimpleBi:
    """笔对象（改进版）"""
    def __init__(
        self,
        index: int,
        direction: str,
        start_fx: SimpleFX,
        end_fx: SimpleFX,
        start_index: int,
        end_index: int,
        is_done: bool = True,
    ):
        self.index = index
        self.type = direction  # 'up' or 'down'
        self._is_done = is_done
        
        # 分型信息
        self.start_fx = start_fx
        self.end_fx = end_fx
        
        # K 线索引范围（用于力度计算）
        self.start_index = start_index
        self.end_index = end_index
        
        # 时间与价格信息
        self.start_time = start_fx.time
        self.end_time = end_fx.time
        self.start_price = float(start_fx.val)
        self.end_price = float(end_fx.val)
        
        # 兼容 mapper.py 的分型结构
        start_kline = SimpleKline(self.start_time, self.start_price, self.start_price, self.start_price)
        end_kline = SimpleKline(self.end_time, self.end_price, self.end_price, self.end_price)
        self.start = SimpleFX("di" if direction == "up" else "ding", start_fx.index, start_fx.k, self.start_price, self.start_time)
        self.end = SimpleFX("ding" if direction == "up" else "di", end_fx.index, end_fx.k, self.end_price, self.end_time)
        
        # 高低点
        if direction == "up":
            self.high = self.end_price
            self.low = self.start_price
        else:
            self.high = self.start_price
            self.low = self.end_price
        
        # 力度（多维度），默认 0
        self.strength: float = 0.0
        self.macd_strength: float = 0.0
        self.price_strength: float = 0.0
        self.slope_strength: float = 0.0
        
        # 买卖点和背驰列表
        self.mmds: List[Any] = []
        self.bcs: List[Any] = []
    
    def is_done(self) -> bool:
        """判断笔是否完成"""
        return self._is_done
    
    def __repr__(self):
        return (
            f"<SimpleBi index={self.index} type={self.type} "
            f"start={self.start_price:.2f} end={self.end_price:.2f} done={self._is_done}>"
        )


class SimpleXD:
    """线段对象（改进版）"""
    def __init__(
        self,
        index: int,
        direction: str,
        start_bi: SimpleBi,
        end_bi: SimpleBi,
        bi_list: List[SimpleBi],
        is_done: bool = True,
    ):
        self.index = index
        self.type = direction
        self._is_done = is_done
        
        # 线段覆盖的笔
        self.bi_list = bi_list
        self.start_bi_index = start_bi.index
        self.end_bi_index = end_bi.index
        
        # 时间与价格信息
        self.start_time = start_bi.start_time
        self.end_time = end_bi.end_time
        self.start_price = start_bi.start_price
        self.end_price = end_bi.end_price
        
        # 兼容 mapper.py 的分型结构
        start_kline = SimpleKline(self.start_time, self.start_price, self.start_price, self.start_price)
        end_kline = SimpleKline(self.end_time, self.end_price, self.end_price, self.end_price)
        self.start = SimpleFX("di" if direction == "up" else "ding", 0, None, self.start_price, self.start_time)
        self.end = SimpleFX("ding" if direction == "up" else "di", 0, None, self.end_price, self.end_time)
        
        # 高低点和分型
        if direction == "up":
            self.high = self.end_price
            self.low = self.start_price
            self.ding_fx = self.end
            self.di_fx = self.start
        else:
            self.high = self.start_price
            self.low = self.end_price
            self.ding_fx = self.start
            self.di_fx = self.end
        
        # 力度
        self.strength: float = 0.0
        
        # 买卖点和背驰列表
        self.mmds: List[Any] = []
        self.bcs: List[Any] = []
    
    def is_done(self) -> bool:
        return self._is_done
    
    def __repr__(self) -> str:
        return (
            f"<SimpleXD index={self.index} type={self.type} "
            f"start={self.start_price:.2f} end={self.end_price:.2f} bis={len(self.bi_list)}>"
        )


class SimpleZS:
    """中枢对象（改进版）"""
    def __init__(
        self,
        index: int,
        zs_type: str,
        direction: str,
        start_time: Any,
        end_time: Any,
        zg: float,
        zd: float,
        gg: float,
        dd: float,
        level: int = 1,
        relation: str = "new",
        bi_count: int = 0,
    ):
        self.index = index
        self.zs_type = zs_type  # "bi" 笔中枢 / "xd" 线段中枢
        self.direction = direction  # "up" / "down" / "zd"（震荡）
        
        # 时间信息
        self.start_time = start_time
        self.end_time = end_time
        
        # 中枢的四个关键价格
        self.zg = zg  # 中枢高点（ZG）
        self.zd = zd  # 中枢低点（ZD）
        self.gg = gg  # 高高点（GG）
        self.dd = dd  # 低低点（DD）
        
        # 兼容旧版字段
        self.high = zg
        self.low = zd
        self.type = direction
        
        # 中枢状态
        self.level = level
        self.relation = relation  # "new" / "extend" / "up_trend" / "down_trend"
        self.bi_count = bi_count
        self.done = True
        self.real = True
    
    def __repr__(self) -> str:
        return (
            f"<SimpleZS index={self.index} type={self.zs_type} "
            f"direction={self.direction} ZG={self.zg:.2f} ZD={self.zd:.2f} "
            f"GG={self.gg:.2f} DD={self.dd:.2f}>"
        )


class SimpleBC:
    """背驰对象"""
    def __init__(
        self,
        bc_type: str,
        is_bc: bool = True,
        zs: Optional[SimpleZS] = None,
        compare_item: Any = None,
    ):
        self.type = bc_type  # "bi" / "xd" / "zsd" / "pz" / "qs"
        self.bc = is_bc
        self.zs = zs
        self.compare_item = compare_item  # 对比的笔/线段
    
    def __repr__(self) -> str:
        return f"<SimpleBC type={self.type} is_bc={self.bc}>"


class SimpleMMD:
    """买卖点对象"""
    def __init__(
        self,
        name: str,
        zs: Optional[SimpleZS] = None,
        msg: Optional[str] = None
    ):
        self.name = name  # "1buy"/"2buy"/"3buy"/"1sell"/"2sell"/"3sell"
        self.zs = zs
        self.msg = msg
    
    def __repr__(self) -> str:
        return f"<SimpleMMD name={self.name} msg={self.msg}>"


# ============================================================
# 缠论引擎核心类（改进版）
# ============================================================

class SimpleICL:
    """缠论引擎核心类（改进版 v2.0）
    
    改进内容：
    1. K线包含关系处理
    2. 严格的分型识别
    3. 正确的笔划分
    4. 基于特征序列的线段划分
    5. 完善的中枢计算
    6. 多维度背驰判断
    """
    
    def __init__(self, code: str, frequency: str, config: Dict[str, Any]):
        self.code = code
        self.frequency = frequency
        self.config = config or {}
        
        # 算法参数
        self.bi_min_kline = self.config.get('bi_min_kline', 4)  # 笔的最小K线数量（合并后）
        self.xd_min_bi = self.config.get('xd_min_bi', 3)  # 线段的最小笔数量
        self.zs_min_bi = self.config.get('zs_min_bi', 3)  # 中枢的最小笔数量
        
        # 中间结果
        self._merged_klines: List[MergedKline] = []
        self._fx_list: List[SimpleFX] = []
        
        # 缠论结构结果
        self._bis: List[SimpleBi] = []
        self._xds: List[SimpleXD] = []
        self._bi_zss: List[SimpleZS] = []
        self._xd_zss: List[SimpleZS] = []
        self._zsd_zss: List[SimpleZS] = []
        
        # 原始数据
        self._raw_df: pd.DataFrame = None
    
    def process_klines(self, df: pd.DataFrame) -> "SimpleICL":
        """对 K 线进行缠论结构计算
        
        计算流程：
        1. K线包含关系处理（合并K线）
        2. 在合并K线上识别分型
        3. 根据分型生成笔
        4. 根据笔生成线段（特征序列法）
        5. 计算中枢
        6. 计算买卖点和背驰
        """
        if len(df) == 0:
            return self
        
        # 保存原始数据
        self._raw_df = df.copy()
        
        # 确保 df 有必要的字段
        required_cols = ['date', 'open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"缺少必须字段: {col}")
        
        # 1. K线包含关系处理
        self._merged_klines = self._merge_klines(df)
        logger.debug(f"合并K线: {len(df)} -> {len(self._merged_klines)}")
        
        # 2. 识别分型
        self._fx_list = self._calculate_fx(self._merged_klines)
        logger.debug(f"识别分型: {len(self._fx_list)} 个")
        
        # 3. 生成笔
        self._bis = self._calculate_bi(self._fx_list, self._merged_klines)
        logger.debug(f"生成笔: {len(self._bis)} 笔")
        
        # 4. 计算笔的力度
        self._calculate_bi_strength(df)
        
        # 5. 生成线段
        self._xds = self._calculate_xd(self._bis)
        logger.debug(f"生成线段: {len(self._xds)} 段")
        
        # 6. 计算线段力度
        self._calculate_xd_strength()
        
        # 7. 计算中枢
        self._bi_zss = self._calculate_zs(self._bis, "bi")
        self._xd_zss = self._calculate_zs_from_xd(self._xds, "xd")
        logger.debug(f"笔中枢: {len(self._bi_zss)}, 线段中枢: {len(self._xd_zss)}")
        
        # 8. 计算买卖点和背驰
        self._calculate_mmds_and_bcs()
        
        return self
    
    # ========================================
    # 1. K线包含关系处理
    # ========================================
    
    def _merge_klines(self, df: pd.DataFrame) -> List[MergedKline]:
        """处理K线包含关系
        
        包含关系定义：
        - 当前K线的高低点完全在前一K线的高低点范围内，或反之
        - 即：(H1 >= H2 and L1 <= L2) 或 (H2 >= H1 and L2 <= L1)
        
        合并规则：
        - 向上趋势：取两根K线的 max(high), max(low)
        - 向下趋势：取两根K线的 min(high), min(low)
        
        趋势判断：
        - 比较合并后的最新K线与前一K线的高点
        """
        if len(df) < 2:
            return [MergedKline(
                index=0,
                date=df.iloc[0]['date'],
                high=float(df.iloc[0]['high']),
                low=float(df.iloc[0]['low']),
                open_price=float(df.iloc[0]['open']),
                close=float(df.iloc[0]['close']),
                raw_indices=[0],
            )] if len(df) == 1 else []
        
        merged: List[MergedKline] = []
        
        # 第一根K线直接加入
        first = df.iloc[0]
        merged.append(MergedKline(
            index=0,
            date=first['date'],
            high=float(first['high']),
            low=float(first['low']),
            open_price=float(first['open']),
            close=float(first['close']),
            raw_indices=[0],
        ))
        
        for i in range(1, len(df)):
            row = df.iloc[i]
            curr_high = float(row['high'])
            curr_low = float(row['low'])
            
            prev = merged[-1]
            prev_high = prev.high
            prev_low = prev.low
            
            # 检查是否存在包含关系
            has_contain = (
                (curr_high <= prev_high and curr_low >= prev_low) or  # 当前被前一个包含
                (curr_high >= prev_high and curr_low <= prev_low)     # 当前包含前一个
            )
            
            if has_contain:
                # 确定趋势方向
                if len(merged) >= 2:
                    direction = "up" if merged[-1].high > merged[-2].high else "down"
                else:
                    # 只有一根K线时，看当前K线的趋势
                    direction = "up" if curr_high > prev_high or curr_low > prev_low else "down"
                
                # 合并K线
                if direction == "up":
                    # 向上趋势：取高高、高低
                    new_high = max(curr_high, prev_high)
                    new_low = max(curr_low, prev_low)
                else:
                    # 向下趋势：取低高、低低
                    new_high = min(curr_high, prev_high)
                    new_low = min(curr_low, prev_low)
                
                # 更新最后一根合并K线
                prev.high = new_high
                prev.low = new_low
                prev.raw_indices.append(i)
                # 保持日期为最后一根的日期
                prev.date = row['date']
            else:
                # 无包含关系，直接添加新K线
                merged.append(MergedKline(
                    index=len(merged),
                    date=row['date'],
                    high=curr_high,
                    low=curr_low,
                    open_price=float(row['open']),
                    close=float(row['close']),
                    raw_indices=[i],
                ))
        
        return merged
    
    # ========================================
    # 2. 分型识别
    # ========================================
    
    def _calculate_fx(self, klines: List[MergedKline]) -> List[SimpleFX]:
        """在合并后的K线上识别分型
        
        顶分型：中间K线的高点是三根K线中最高的
        底分型：中间K线的低点是三根K线中最低的
        
        严格条件：
        - 顶分型：k[i].high > k[i-1].high AND k[i].high > k[i+1].high
        - 底分型：k[i].low < k[i-1].low AND k[i].low < k[i+1].low
        """
        if len(klines) < 3:
            return []
        
        fx_list: List[SimpleFX] = []
        
        for i in range(1, len(klines) - 1):
            prev = klines[i - 1]
            curr = klines[i]
            next_ = klines[i + 1]
            
            # 顶分型判断（严格大于）
            if curr.high > prev.high and curr.high > next_.high:
                fx = SimpleFX(
                    fx_type="ding",
                    index=i,
                    kline=curr,
                    price=curr.high,
                    time=curr.date,
                    raw_index=curr.raw_indices[-1] if curr.raw_indices else i,
                )
                fx_list.append(fx)
            
            # 底分型判断（严格小于）
            elif curr.low < prev.low and curr.low < next_.low:
                fx = SimpleFX(
                    fx_type="di",
                    index=i,
                    kline=curr,
                    price=curr.low,
                    time=curr.date,
                    raw_index=curr.raw_indices[-1] if curr.raw_indices else i,
                )
                fx_list.append(fx)
        
        return fx_list
    
    # ========================================
    # 3. 笔的生成
    # ========================================
    
    def _calculate_bi(
        self,
        fx_list: List[SimpleFX],
        klines: List[MergedKline]
    ) -> List[SimpleBi]:
        """根据分型生成笔
        
        笔的定义：
        1. 从顶分型到底分型，或从底分型到顶分型
        2. 两个分型之间至少有 bi_min_kline 根独立K线（不含分型的共用K线）
        3. 顶底分型必须交替出现
        
        特殊处理：
        - 同类型分型之间，保留更极端的那个
        - 笔的延伸：如果后续出现更高的顶或更低的底，延伸笔
        """
        if len(fx_list) < 2:
            return []
        
        # 第一步：过滤和修正分型，确保顶底交替且选择最极端的
        filtered_fx = self._filter_fx_alternating(fx_list)
        
        if len(filtered_fx) < 2:
            return []
        
        # 第二步：生成笔
        bis: List[SimpleBi] = []
        bi_index = 0
        
        i = 0
        while i < len(filtered_fx) - 1:
            start_fx = filtered_fx[i]
            end_fx = filtered_fx[i + 1]
            
            # 检查分型之间的K线数量
            kline_count = end_fx.index - start_fx.index
            if kline_count < self.bi_min_kline:
                # K线数量不足，跳过这对分型
                i += 1
                continue
            
            # 确定笔的方向
            if start_fx.type == "di" and end_fx.type == "ding":
                direction = "up"
            elif start_fx.type == "ding" and end_fx.type == "di":
                direction = "down"
            else:
                # 不应该发生（经过 filter 后应该是交替的）
                i += 1
                continue
            
            # 检查是否需要延伸笔
            # 向后查找是否有更极端的分型
            actual_end_fx = end_fx
            j = i + 2
            while j < len(filtered_fx):
                next_fx = filtered_fx[j]
                if direction == "up" and next_fx.type == "ding":
                    # 向上笔，检查是否有更高的顶
                    if next_fx.val > actual_end_fx.val:
                        actual_end_fx = next_fx
                        j += 1
                    else:
                        break
                elif direction == "down" and next_fx.type == "di":
                    # 向下笔，检查是否有更低的底
                    if next_fx.val < actual_end_fx.val:
                        actual_end_fx = next_fx
                        j += 1
                    else:
                        break
                else:
                    break
            
            # 创建笔
            # 获取原始K线索引
            start_raw_idx = start_fx.raw_index
            end_raw_idx = actual_end_fx.raw_index
            
            bi = SimpleBi(
                index=bi_index,
                direction=direction,
                start_fx=start_fx,
                end_fx=actual_end_fx,
                start_index=start_raw_idx,
                end_index=end_raw_idx,
                is_done=True,
            )
            
            # 检查与上一笔的方向是否交替
            if bis and bis[-1].type == direction:
                # 方向相同，需要合并或选择
                # 如果方向相同，说明有问题，跳过
                i += 1
                continue
            
            bis.append(bi)
            bi_index += 1
            
            # 移动到结束分型的位置
            # 找到 actual_end_fx 在 filtered_fx 中的索引
            try:
                next_i = filtered_fx.index(actual_end_fx)
                i = next_i
            except ValueError:
                i += 1
        
        # 最后一笔可能未完成
        if bis and len(filtered_fx) > 0:
            last_fx = filtered_fx[-1]
            if bis[-1].end_fx != last_fx:
                bis[-1]._is_done = False
        
        return bis
    
    def _filter_fx_alternating(self, fx_list: List[SimpleFX]) -> List[SimpleFX]:
        """过滤分型，确保顶底交替，同类型分型保留最极端的
        
        算法：
        1. 遍历所有分型
        2. 如果与前一个分型类型相同，保留更极端的
        3. 如果类型不同，直接添加
        """
        if not fx_list:
            return []
        
        result: List[SimpleFX] = [fx_list[0]]
        
        for fx in fx_list[1:]:
            last = result[-1]
            
            if fx.type == last.type:
                # 同类型，保留更极端的
                if fx.type == "ding":
                    # 顶分型，保留更高的
                    if fx.val > last.val:
                        result[-1] = fx
                else:
                    # 底分型，保留更低的
                    if fx.val < last.val:
                        result[-1] = fx
            else:
                # 类型不同，添加
                result.append(fx)
        
        return result
    
    # ========================================
    # 4. 笔的力度计算
    # ========================================
    
    def _calculate_bi_strength(self, df: pd.DataFrame) -> None:
        """计算笔的力度（多维度）
        
        力度计算包括：
        1. MACD 力度：MACD 柱子面积
        2. 价格力度：价格变化幅度
        3. 斜率力度：单位时间价格变化
        """
        if not self._bis or df is None or len(df) == 0:
            return
        
        # 计算 MACD
        close = df["close"].astype(float)
        ema_short = close.ewm(span=12, adjust=False).mean()
        ema_long = close.ewm(span=26, adjust=False).mean()
        dif = ema_short - ema_long
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_hist = (dif - dea) * 2
        hist_values = macd_hist.to_list()
        n = len(hist_values)
        
        for bi in self._bis:
            start_idx = bi.start_index
            end_idx = bi.end_index
            
            if start_idx is None or end_idx is None:
                continue
            
            s = max(0, min(start_idx, end_idx))
            e = min(n - 1, max(start_idx, end_idx))
            segment = hist_values[s:e + 1]
            
            # 1. MACD 力度
            if bi.type == "up":
                bi.macd_strength = float(sum(abs(v) for v in segment if v > 0))
            else:
                bi.macd_strength = float(sum(abs(v) for v in segment if v < 0))
            
            # 2. 价格力度
            bi.price_strength = abs(bi.end_price - bi.start_price)
            
            # 3. 斜率力度
            kline_count = abs(e - s) + 1
            bi.slope_strength = bi.price_strength / max(kline_count, 1)
            
            # 综合力度（加权平均）
            bi.strength = (
                0.5 * bi.macd_strength +
                0.3 * bi.price_strength +
                0.2 * bi.slope_strength * 100  # 斜率需要放大
            )
    
    # ========================================
    # 5. 线段的生成（特征序列法）
    # ========================================
    
    def _calculate_xd(self, bis: List[SimpleBi]) -> List[SimpleXD]:
        """根据笔生成线段（基于特征序列分型）
        
        线段定义：
        1. 线段由至少3笔组成
        2. 线段的结束需要特征序列出现反向分型
        
        特征序列：
        - 向上线段：取所有向下笔的高低点作为特征序列
        - 向下线段：取所有向上笔的高低点作为特征序列
        
        线段破坏条件：
        - 特征序列出现反向分型（底分型结束向上线段，顶分型结束向下线段）
        """
        if len(bis) < 3:
            return []
        
        xds: List[SimpleXD] = []
        xd_index = 0
        
        # 确定第一个线段的方向（使用前3笔）
        # 如果是上下上，则是向上线段；如果是下上下，则是向下线段
        if bis[0].type == "up":
            # 上下上...开始，第一个线段是向上的
            current_direction = "up"
            start_bi_idx = 0
        else:
            # 下上下...开始，第一个线段是向下的
            current_direction = "down"
            start_bi_idx = 0
        
        i = start_bi_idx + 2  # 从第3笔开始检查
        
        while i < len(bis):
            # 收集当前线段的笔
            segment_bis = bis[start_bi_idx:i + 1]
            
            if len(segment_bis) < 3:
                i += 1
                continue
            
            # 构建特征序列
            features = self._build_feature_sequence(segment_bis, current_direction)
            
            # 检查特征序列是否出现反向分型
            fx_type, fx_index = self._check_feature_fx(features, current_direction)
            
            if fx_type is not None:
                # 找到反向分型，线段结束
                # 确定线段结束的笔
                end_bi = segment_bis[-1]
                
                # 如果是向上线段，找到最高点对应的笔
                if current_direction == "up":
                    max_price = max(b.end_price for b in segment_bis if b.type == "up")
                    for b in reversed(segment_bis):
                        if b.type == "up" and b.end_price == max_price:
                            end_bi = b
                            break
                else:
                    min_price = min(b.end_price for b in segment_bis if b.type == "down")
                    for b in reversed(segment_bis):
                        if b.type == "down" and b.end_price == min_price:
                            end_bi = b
                            break
                
                # 创建线段
                start_bi = bis[start_bi_idx]
                xd = SimpleXD(
                    index=xd_index,
                    direction=current_direction,
                    start_bi=start_bi,
                    end_bi=end_bi,
                    bi_list=segment_bis[:segment_bis.index(end_bi) + 1] if end_bi in segment_bis else segment_bis,
                    is_done=True,
                )
                xds.append(xd)
                xd_index += 1
                
                # 切换方向，更新起始位置
                current_direction = "down" if current_direction == "up" else "up"
                # 新线段从结束点开始
                try:
                    start_bi_idx = bis.index(end_bi)
                except ValueError:
                    start_bi_idx = i
                i = start_bi_idx + 2
            else:
                i += 1
        
        # 处理最后可能未完成的线段
        if start_bi_idx < len(bis) - 2:
            remaining_bis = bis[start_bi_idx:]
            if len(remaining_bis) >= 3:
                start_bi = remaining_bis[0]
                end_bi = remaining_bis[-1]
                
                # 确定实际结束笔
                if current_direction == "up":
                    max_price = max(b.end_price for b in remaining_bis if b.type == "up")
                    for b in reversed(remaining_bis):
                        if b.type == "up" and b.end_price == max_price:
                            end_bi = b
                            break
                else:
                    min_price = min(b.end_price for b in remaining_bis if b.type == "down")
                    for b in reversed(remaining_bis):
                        if b.type == "down" and b.end_price == min_price:
                            end_bi = b
                            break
                
                xd = SimpleXD(
                    index=xd_index,
                    direction=current_direction,
                    start_bi=start_bi,
                    end_bi=end_bi,
                    bi_list=remaining_bis,
                    is_done=False,  # 未完成的线段
                )
                xds.append(xd)
        
        return xds
    
    def _build_feature_sequence(
        self,
        bis: List[SimpleBi],
        direction: str
    ) -> List[Tuple[float, float]]:
        """构建特征序列
        
        向上线段：取向下笔作为特征序列，每笔的(high, low)
        向下线段：取向上笔作为特征序列，每笔的(high, low)
        """
        features = []
        
        for bi in bis:
            if direction == "up" and bi.type == "down":
                # 向上线段，取向下笔
                features.append((bi.high, bi.low))
            elif direction == "down" and bi.type == "up":
                # 向下线段，取向上笔
                features.append((bi.high, bi.low))
        
        return features
    
    def _check_feature_fx(
        self,
        features: List[Tuple[float, float]],
        direction: str
    ) -> Tuple[Optional[str], Optional[int]]:
        """检查特征序列是否出现反向分型
        
        向上线段等待底分型：三个特征元素，中间的low最低
        向下线段等待顶分型：三个特征元素，中间的high最高
        
        返回：(分型类型, 分型索引) 或 (None, None)
        """
        if len(features) < 3:
            return None, None
        
        # 处理特征序列的包含关系
        merged_features = self._merge_features(features, direction)
        
        if len(merged_features) < 3:
            return None, None
        
        # 检查最后三个特征元素
        for i in range(len(merged_features) - 2):
            f1 = merged_features[i]
            f2 = merged_features[i + 1]
            f3 = merged_features[i + 2]
            
            if direction == "up":
                # 向上线段，等待底分型（中间最低）
                if f2[1] < f1[1] and f2[1] < f3[1]:
                    return "di", i + 1
            else:
                # 向下线段，等待顶分型（中间最高）
                if f2[0] > f1[0] and f2[0] > f3[0]:
                    return "ding", i + 1
        
        return None, None
    
    def _merge_features(
        self,
        features: List[Tuple[float, float]],
        direction: str
    ) -> List[Tuple[float, float]]:
        """处理特征序列的包含关系"""
        if len(features) < 2:
            return features
        
        merged = [features[0]]
        
        for feat in features[1:]:
            prev = merged[-1]
            
            # 检查包含关系
            has_contain = (
                (feat[0] <= prev[0] and feat[1] >= prev[1]) or
                (feat[0] >= prev[0] and feat[1] <= prev[1])
            )
            
            if has_contain:
                # 根据线段方向决定合并方式
                if direction == "up":
                    # 向上线段，特征序列向下，取低低
                    new_high = min(feat[0], prev[0])
                    new_low = min(feat[1], prev[1])
                else:
                    # 向下线段，特征序列向上，取高高
                    new_high = max(feat[0], prev[0])
                    new_low = max(feat[1], prev[1])
                merged[-1] = (new_high, new_low)
            else:
                merged.append(feat)
        
        return merged
    
    # ========================================
    # 6. 线段力度计算
    # ========================================
    
    def _calculate_xd_strength(self) -> None:
        """计算线段的力度"""
        for xd in self._xds:
            # 线段力度 = 包含的笔的力度之和
            xd.strength = sum(bi.strength for bi in xd.bi_list)
    
    # ========================================
    # 7. 中枢计算
    # ========================================
    
    def _calculate_zs(self, items: List[SimpleBi], level: str) -> List[SimpleZS]:
        """计算笔中枢
        
        中枢定义：
        - 至少3笔有重叠区间
        - ZG = min(所有笔的高点)
        - ZD = max(所有笔的低点)
        - 必须 ZD < ZG 才形成中枢
        """
        if len(items) < self.zs_min_bi:
            return []
        
        zss: List[SimpleZS] = []
        zs_index = 0
        i = 0
        
        def get_bi_range(bi: SimpleBi) -> Tuple[float, float]:
            """获取笔的价格区间 (low, high)"""
            return (bi.low, bi.high)
        
        while i <= len(items) - self.zs_min_bi:
            # 取连续的笔尝试形成中枢
            first_bis = items[i:i + self.zs_min_bi]
            ranges = [get_bi_range(bi) for bi in first_bis]
            
            # 计算重叠区间
            zd = max(r[0] for r in ranges)  # 所有低点的最大值
            zg = min(r[1] for r in ranges)  # 所有高点的最小值
            
            if zd < zg:
                # 形成中枢，尝试扩展
                zs_bis = list(first_bis)
                j = i + self.zs_min_bi
                
                while j < len(items):
                    next_bi = items[j]
                    next_low, next_high = get_bi_range(next_bi)
                    
                    # 检查是否与中枢有重叠
                    if next_low < zg and next_high > zd:
                        zs_bis.append(next_bi)
                        j += 1
                    else:
                        break
                
                # 计算最终的中枢参数
                all_ranges = [get_bi_range(bi) for bi in zs_bis]
                
                # ZG, ZD 使用前3笔确定
                first_three = all_ranges[:3]
                zd = max(r[0] for r in first_three)
                zg = min(r[1] for r in first_three)
                
                # GG, DD 使用所有笔
                gg = max(r[1] for r in all_ranges)
                dd = min(r[0] for r in all_ranges)
                
                # 判断中枢方向
                if gg > zg and dd < zd:
                    direction = "zd"  # 震荡
                elif gg > zg:
                    direction = "up"
                elif dd < zd:
                    direction = "down"
                else:
                    direction = "zd"
                
                # 计算与前一个中枢的关系
                relation = "new"
                if zss:
                    prev_zs = zss[-1]
                    if zd > prev_zs.zg:
                        relation = "up_trend"
                    elif zg < prev_zs.zd:
                        relation = "down_trend"
                    else:
                        relation = "extend"
                
                zs = SimpleZS(
                    index=zs_index,
                    zs_type=level,
                    direction=direction,
                    start_time=zs_bis[0].start_time,
                    end_time=zs_bis[-1].end_time,
                    zg=zg,
                    zd=zd,
                    gg=gg,
                    dd=dd,
                    level=1,
                    relation=relation,
                    bi_count=len(zs_bis),
                )
                zss.append(zs)
                zs_index += 1
                
                # 跳过已处理的笔
                i = j
            else:
                i += 1
        
        return zss
    
    def _calculate_zs_from_xd(self, xds: List[SimpleXD], level: str) -> List[SimpleZS]:
        """计算线段中枢"""
        if len(xds) < self.zs_min_bi:
            return []
        
        zss: List[SimpleZS] = []
        zs_index = 0
        i = 0
        
        def get_xd_range(xd: SimpleXD) -> Tuple[float, float]:
            return (xd.low, xd.high)
        
        while i <= len(xds) - self.zs_min_bi:
            first_xds = xds[i:i + self.zs_min_bi]
            ranges = [get_xd_range(xd) for xd in first_xds]
            
            zd = max(r[0] for r in ranges)
            zg = min(r[1] for r in ranges)
            
            if zd < zg:
                zs_xds = list(first_xds)
                j = i + self.zs_min_bi
                
                while j < len(xds):
                    next_xd = xds[j]
                    next_low, next_high = get_xd_range(next_xd)
                    
                    if next_low < zg and next_high > zd:
                        zs_xds.append(next_xd)
                        j += 1
                    else:
                        break
                
                all_ranges = [get_xd_range(xd) for xd in zs_xds]
                first_three = all_ranges[:3]
                zd = max(r[0] for r in first_three)
                zg = min(r[1] for r in first_three)
                gg = max(r[1] for r in all_ranges)
                dd = min(r[0] for r in all_ranges)
                
                if gg > zg and dd < zd:
                    direction = "zd"
                elif gg > zg:
                    direction = "up"
                elif dd < zd:
                    direction = "down"
                else:
                    direction = "zd"
                
                relation = "new"
                if zss:
                    prev_zs = zss[-1]
                    if zd > prev_zs.zg:
                        relation = "up_trend"
                    elif zg < prev_zs.zd:
                        relation = "down_trend"
                    else:
                        relation = "extend"
                
                zs = SimpleZS(
                    index=zs_index,
                    zs_type=level,
                    direction=direction,
                    start_time=zs_xds[0].start_time,
                    end_time=zs_xds[-1].end_time,
                    zg=zg,
                    zd=zd,
                    gg=gg,
                    dd=dd,
                    level=1,
                    relation=relation,
                    bi_count=len(zs_xds),
                )
                zss.append(zs)
                zs_index += 1
                i = j
            else:
                i += 1
        
        return zss
    
    # ========================================
    # 8. 买卖点和背驰计算
    # ========================================
    
    def _calculate_mmds_and_bcs(self) -> None:
        """计算买卖点和背驰"""
        # 1. 计算笔的背驰和一类买卖点
        self._calculate_bi_bcs_and_mmds()
        
        # 2. 计算线段的背驰和二类买卖点
        self._calculate_xd_bcs_and_mmds()
        
        # 3. 计算三类买卖点
        self._calculate_class3_mmds()
    
    def _calculate_bi_bcs_and_mmds(self) -> None:
        """计算笔的背驰和一类买卖点"""
        if len(self._bis) < 5:
            return
        
        for i in range(4, len(self._bis)):
            current_bi = self._bis[i]
            
            # 查找同向前笔（跳2笔）
            for j in range(i - 2, -1, -2):
                prev_bi = self._bis[j]
                
                if current_bi.type != prev_bi.type:
                    continue
                
                # 检测背驰
                is_bc = self._check_divergence(prev_bi, current_bi)
                
                if is_bc:
                    # 查找相关中枢
                    related_zs = self._find_related_zs(current_bi, self._bi_zss)
                    
                    # 添加背驰标记
                    current_bi.bcs.append(SimpleBC(
                        bc_type="bi",
                        is_bc=True,
                        zs=related_zs,
                        compare_item=prev_bi,
                    ))
                    
                    # 判断一类买卖点
                    if related_zs and self._is_leaving_zs(current_bi, related_zs):
                        if current_bi.type == "down":
                            current_bi.mmds.append(SimpleMMD(
                                name="1buy",
                                zs=related_zs,
                                msg="笔背驰一买"
                            ))
                        else:
                            current_bi.mmds.append(SimpleMMD(
                                name="1sell",
                                zs=related_zs,
                                msg="笔背驰一卖"
                            ))
                    break
    
    def _calculate_xd_bcs_and_mmds(self) -> None:
        """计算线段的背驰和二类买卖点"""
        if len(self._xds) < 3:
            return
        
        for i in range(2, len(self._xds)):
            current_xd = self._xds[i]
            
            for j in range(i - 2, -1, -2):
                prev_xd = self._xds[j]
                
                if current_xd.type != prev_xd.type:
                    continue
                
                is_bc = self._check_xd_divergence(prev_xd, current_xd)
                
                if is_bc:
                    related_zs = self._find_related_zs_for_xd(current_xd, self._xd_zss)
                    
                    current_xd.bcs.append(SimpleBC(
                        bc_type="xd",
                        is_bc=True,
                        zs=related_zs,
                        compare_item=prev_xd,
                    ))
                    
                    if related_zs and self._is_leaving_zs_for_xd(current_xd, related_zs):
                        if current_xd.type == "down":
                            current_xd.mmds.append(SimpleMMD(
                                name="2buy",
                                zs=related_zs,
                                msg="线段背驰二买"
                            ))
                        else:
                            current_xd.mmds.append(SimpleMMD(
                                name="2sell",
                                zs=related_zs,
                                msg="线段背驰二卖"
                            ))
                    break
    
    def _calculate_class3_mmds(self) -> None:
        """计算三类买卖点"""
        if not self._bi_zss or len(self._bis) < 3:
            return
        
        for zs in self._bi_zss:
            # 找中枢后的笔
            for bi in self._bis:
                if bi.start_time <= zs.end_time:
                    continue
                
                # 三买：向上笔回落不进中枢
                if bi.type == "down" and bi.low > zs.zd:
                    # 检查前一笔是否突破中枢上沿
                    bi_idx = self._bis.index(bi)
                    if bi_idx > 0:
                        prev_bi = self._bis[bi_idx - 1]
                        if prev_bi.type == "up" and prev_bi.high > zs.zg:
                            bi.mmds.append(SimpleMMD(
                                name="3buy",
                                zs=zs,
                                msg="三类买点"
                            ))
                            break
                
                # 三卖：向下笔反弹不进中枢
                if bi.type == "up" and bi.high < zs.zg:
                    bi_idx = self._bis.index(bi)
                    if bi_idx > 0:
                        prev_bi = self._bis[bi_idx - 1]
                        if prev_bi.type == "down" and prev_bi.low < zs.zd:
                            bi.mmds.append(SimpleMMD(
                                name="3sell",
                                zs=zs,
                                msg="三类卖点"
                            ))
                            break
    
    def _check_divergence(self, prev: SimpleBi, curr: SimpleBi) -> bool:
        """检测笔背驰（多维度）"""
        if prev.type != curr.type:
            return False
        
        # 力度比较
        prev_strength = prev.strength
        curr_strength = curr.strength
        
        if prev_strength <= 0 or curr_strength <= 0:
            # 力度无效，使用价格幅度
            prev_strength = prev.price_strength
            curr_strength = curr.price_strength
        
        if prev_strength <= 0:
            return False
        
        # 背驰条件：新高/新低 + 力度减弱
        strength_ratio = curr_strength / prev_strength
        
        if prev.type == "up":
            # 上笔：创新高但力度减弱
            return curr.end_price > prev.end_price and strength_ratio < 0.8
        else:
            # 下笔：创新低但力度减弱
            return curr.end_price < prev.end_price and strength_ratio < 0.8
    
    def _check_xd_divergence(self, prev: SimpleXD, curr: SimpleXD) -> bool:
        """检测线段背驰"""
        if prev.type != curr.type:
            return False
        
        prev_strength = prev.strength
        curr_strength = curr.strength
        
        if prev_strength <= 0 or curr_strength <= 0:
            return False
        
        strength_ratio = curr_strength / prev_strength
        
        if prev.type == "up":
            return curr.end_price > prev.end_price and strength_ratio < 0.8
        else:
            return curr.end_price < prev.end_price and strength_ratio < 0.8
    
    def _find_related_zs(self, bi: SimpleBi, zss: List[SimpleZS]) -> Optional[SimpleZS]:
        """查找与笔相关的中枢"""
        for zs in reversed(zss):
            if bi.start_time <= zs.end_time and bi.end_time >= zs.start_time:
                return zs
            if bi.start_time > zs.end_time:
                return zs
        return None
    
    def _find_related_zs_for_xd(self, xd: SimpleXD, zss: List[SimpleZS]) -> Optional[SimpleZS]:
        """查找与线段相关的中枢"""
        for zs in reversed(zss):
            if xd.start_time <= zs.end_time and xd.end_time >= zs.start_time:
                return zs
            if xd.start_time > zs.end_time:
                return zs
        return None
    
    def _is_leaving_zs(self, bi: SimpleBi, zs: SimpleZS) -> bool:
        """判断笔是否离开中枢"""
        if bi.type == "down":
            return bi.end_price < zs.zd
        else:
            return bi.end_price > zs.zg
    
    def _is_leaving_zs_for_xd(self, xd: SimpleXD, zs: SimpleZS) -> bool:
        """判断线段是否离开中枢"""
        if xd.type == "down":
            return xd.end_price < zs.zd
        else:
            return xd.end_price > zs.zg
    
    # ========================================
    # 对外接口
    # ========================================
    
    def get_bis(self) -> List[SimpleBi]:
        return self._bis
    
    def get_xds(self) -> List[SimpleXD]:
        return self._xds
    
    def get_bi_zss(self, zs_type: Optional[str] = None) -> List[SimpleZS]:
        return self._bi_zss
    
    def get_xd_zss(self, zs_type: Optional[str] = None) -> List[SimpleZS]:
        return self._xd_zss
    
    def get_zsd_zss(self) -> List[SimpleZS]:
        return self._zsd_zss
    
    def get_merged_klines(self) -> List[MergedKline]:
        """获取合并后的K线（调试用）"""
        return self._merged_klines
    
    def get_fx_list(self) -> List[SimpleFX]:
        """获取分型列表（调试用）"""
        return self._fx_list
    
    def get_macd_data(self) -> Dict[str, Any]:
        """获取 MACD 指标数据（用于可视化）
        
        返回：
        - dates: 日期列表
        - dif: DIF 线
        - dea: DEA 线 (信号线)
        - hist: MACD 柱状图 (DIF - DEA) * 2
        """
        if self._raw_df is None or len(self._raw_df) == 0:
            return {"dates": [], "dif": [], "dea": [], "hist": []}
        
        df = self._raw_df
        close = df["close"].astype(float)
        
        # 计算 MACD
        ema_short = close.ewm(span=12, adjust=False).mean()
        ema_long = close.ewm(span=26, adjust=False).mean()
        dif = ema_short - ema_long
        dea = dif.ewm(span=9, adjust=False).mean()
        hist = (dif - dea) * 2
        
        return {
            "dates": df["date"].tolist(),
            "dif": dif.tolist(),
            "dea": dea.tolist(),
            "hist": hist.tolist(),
        }


# 将 SimpleICL 作为 ICL 的别名，保持接口一致
ICL = SimpleICL


# ============================================================
# 引擎配置和封装类
# ============================================================

@dataclass
class EngineConfig:
    """缠论引擎配置"""
    
    options: Dict[str, Any] = None
    bi_min_kline: int = 4  # 笔的最小 K 线数量（合并后）
    xd_min_bi: int = 3     # 线段的最小笔数量
    zs_min_bi: int = 3     # 中枢的最小笔数量
    
    def __post_init__(self):
        if self.options is None:
            self.options = {}


@dataclass
class KlineInput:
    """供 engine 使用的最小 K 线输入结构"""
    
    date: Any
    open: float
    high: float
    low: float
    close: float
    volume: float


class ChanlunEngine:
    """面向上层的缠论引擎封装"""
    
    def __init__(self, config: EngineConfig) -> None:
        self._config = config
    
    def analyze_klines(
        self,
        *,
        code: str,
        frequency: str,
        klines: Iterable[KlineInput | Dict[str, Any]],
    ) -> ICL:
        """对一段完整 K 线序列进行缠论计算"""
        
        rows: List[Dict[str, Any]] = []
        for k in klines:
            if isinstance(k, KlineInput):
                row = {
                    "date": k.date,
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "volume": k.volume,
                }
            else:
                row = {
                    "date": k["date"],
                    "open": k["open"],
                    "high": k["high"],
                    "low": k["low"],
                    "close": k["close"],
                    "volume": k["volume"],
                }
            rows.append(row)
        
        if not rows:
            logger.error(f"[{code}] {frequency} - K 线序列为空")
            raise ValueError("analyze_klines 收到的 K 线序列为空，无法进行缠论计算")
        
        if len(rows) < 50:
            logger.error(f"[{code}] {frequency} - K 线数量不足: {len(rows)} 根")
            raise ValueError(f"K 线数量不足，至少需要 50 根，当前 {len(rows)} 根")
        
        logger.info(f"[{code}] {frequency} - 开始缠论分析，共 {len(rows)} 根 K 线")
        
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
        if df["date"].isna().any():
            logger.error(f"[{code}] {frequency} - K 线数据中存在无效的 date 字段")
            raise ValueError("K 线数据中存在无法转换为 datetime 的 date 字段")
        
        # 合并配置
        options = self._config.options.copy() if self._config.options else {}
        options['bi_min_kline'] = self._config.bi_min_kline
        options['xd_min_bi'] = self._config.xd_min_bi
        options['zs_min_bi'] = self._config.zs_min_bi
        
        icl = ICL(code=code, frequency=frequency, config=options)
        icl = icl.process_klines(df)
        
        bis_count = len(icl.get_bis())
        xds_count = len(icl.get_xds())
        bi_zss_count = len(icl.get_bi_zss())
        logger.info(
            f"[{code}] {frequency} - 缠论分析完成: "
            f"笔={bis_count}, 线段={xds_count}, 笔中枢={bi_zss_count}"
        )
        
        return icl
