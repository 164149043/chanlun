"""缠论引擎封装（engine）

本模块的职责：
- 接收已经准备好的、完整的 K 线数据序列（不裁剪、不修改）
- 进行缠论结构计算（笔、线段、中枢等）
- 返回 ICL 对象，供上层按需读取笔、线段、中枢、买卖点、背驰等结构

本模块不会做的事情：
- 不从交易所 / 本地文件加载原始数据（这部分交给 mapper.py）
- 不把结果转换成 JSON / dict（序列化交给上层）
- 不裁剪 K 线数量，不更改数据内容

说明：
- 当前使用简化的占位实现（SimpleICL），可后续替换为完整的缠论算法
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
import logging

import pandas as pd

# 设置日志
logger = logging.getLogger(__name__)


# ============================================================
# 简化的缠论结构对象（自实现）
# ============================================================

class SimpleKline:
    """简化的 K 线对象（用于分型）"""
    def __init__(self, date: Any, high: float, low: float, close: float):
        self.date = date
        self.high = high
        self.low = low
        self.close = close

class SimpleFX:
    """简化的分型对象（顶分型/底分型）"""
    def __init__(self, time: Any, price: float, kline: Any = None):
        self.k = kline if kline else SimpleKline(time, price, price, price)
        self.val = price

class SimpleBi:
    """简化的笔对象（兼容 mapper.py）"""
    def __init__(
        self,
        index: int,
        direction: str,
        start_time: Any,
        end_time: Any,
        start_price: float,
        end_price: float,
        start_index: Optional[int] = None,
        end_index: Optional[int] = None,
    ):
        self.index = index
        self.type = direction  # 'up' or 'down'
        
        # K 线索引范围（用于力度计算）
        self.start_index = start_index
        self.end_index = end_index
        
        # 基本时间与价格信息
        self.start_time = start_time
        self.end_time = end_time
        self.start_price = float(start_price)
        self.end_price = float(end_price)
        
        # mapper.py 需要的分型结构
        start_kline = SimpleKline(start_time, start_price, start_price, start_price)
        end_kline = SimpleKline(end_time, end_price, end_price, end_price)
        self.start = SimpleFX(start_time, start_price, start_kline)
        self.end = SimpleFX(end_time, end_price, end_kline)
        
        # 高低点
        if direction == "up":
            self.high = end_price
            self.low = start_price
        else:
            self.high = start_price
            self.low = end_price
        
        # 力度（MACD 柱子之和），默认 0
        self.strength: float = 0.0
        
        # 买卖点和背驰列表
        self.mmds = []  # 买卖点列表
        self.bcs = []   # 背驰列表
    
    def is_done(self) -> bool:
        """判断笔是否完成（简化实现：始终返回 True）"""
        return True
    
    def __repr__(self):
        return (
            f"<SimpleBi index={self.index} type={self.type} "
            f"start={self.start_time} end={self.end_time}>"
        )

class SimpleXD:
    """简化的线段对象（兼容 mapper.py）"""
    def __init__(
        self,
        index: int,
        direction: str,
        start_time: Any,
        end_time: Any,
        start_price: float,
        end_price: float,
        ding_time: Any = None,
        di_time: Any = None,
        start_bi_index: Optional[int] = None,
        end_bi_index: Optional[int] = None,
    ):
        self.index = index
        self.type = direction
        
        # 线段覆盖的笔索引范围（用于力度计算）
        self.start_bi_index = start_bi_index
        self.end_bi_index = end_bi_index
        
        # 基本时间与价格信息
        self.start_time = start_time
        self.end_time = end_time
        self.start_price = start_price
        self.end_price = end_price
        
        # mapper.py 需要的分型结构
        start_kline = SimpleKline(start_time, start_price, start_price, start_price)
        end_kline = SimpleKline(end_time, end_price, end_price, end_price)
        self.start = SimpleFX(start_time, start_price, start_kline)
        self.end = SimpleFX(end_time, end_price, end_kline)
        
        # 高低点
        if direction == "up":
            self.high = end_price
            self.low = start_price
            self.ding_fx = SimpleFX(ding_time or end_time, end_price, end_kline)
            self.di_fx = SimpleFX(di_time or start_time, start_price, start_kline)
        else:
            self.high = start_price
            self.low = end_price
            self.ding_fx = SimpleFX(ding_time or start_time, start_price, start_kline)
            self.di_fx = SimpleFX(di_time or end_time, end_price, end_kline)
        
        # 力度（MACD 柱子之和），默认 0
        self.strength: float = 0.0
        
        # 买卖点和背驰列表
        self.mmds: List[Any] = []
        self.bcs: List[Any] = []
    
    def __repr__(self) -> str:
        return (
            f"<SimpleXD index={self.index} type={self.type} "
            f"start={self.start_price} end={self.end_price}>"
        )

class SimpleZS:
    """简化的中枢对象（完整版）"""
    def __init__(
        self,
        index: int,
        zs_type: str,
        direction: str,
        start_time: Any,
        end_time: Any,
        high: float,
        low: float,
        level: int = 1,
        relation: str = "expand",
    ):
        self.index = index
        self.zs_type = zs_type  # "bi" 笔中枢 / "xd" 线段中枢
        self.direction = direction  # "up" / "down"
        
        # 时间信息
        self.start_time = start_time
        self.end_time = end_time
        
        # 价格信息
        self.high = high
        self.low = low
        
        # 中枢的四个关键价格（兼容 mapper.py）
        self.zg = high  # 中枢高点
        self.zd = low   # 中枢低点
        self.gg = high  # 高高点
        self.dd = low   # 低低点
        
        # 中枢类型（兼容 mapper.py）
        self.type = direction  # "up" / "down" / "zd"（震荡）
        
        # 中枢等级和状态
        self.level = level
        self.relation = relation
        self.done = True   # 中枢是否完成
        self.real = True   # 是否为真实中枢
    
    def __repr__(self) -> str:
        return (
            f"<SimpleZS index={self.index} type={self.zs_type} "
            f"direction={self.direction} zg={self.zg:.2f} zd={self.zd:.2f}>"
        )

class SimpleBC:
    """简化的背驰对象"""
    def __init__(
        self,
        bc_type: str,
        is_bc: bool = True,
        zs: Optional[SimpleZS] = None
    ):
        self.type = bc_type  # "bi" / "xd" / "zsd" / "pz" / "qs"
        self.bc = is_bc      # 是否背驰
        self.zs = zs         # 相关中枢
    
    def __repr__(self) -> str:
        return f"<SimpleBC type={self.type} is_bc={self.bc}>"

class SimpleMMD:
    """简化的买卖点对象"""
    def __init__(
        self,
        name: str,
        zs: Optional[SimpleZS] = None,
        msg: Optional[str] = None
    ):
        self.name = name  # "1buy"/"2buy"/"3buy"/"1sell"/"2sell"/"3sell"
        self.zs = zs      # 相关中枢
        self.msg = msg    # 说明信息
    
    def __repr__(self) -> str:
        return f"<SimpleMMD name={self.name} msg={self.msg}>"

class SimpleICL:
    """简化的 ICL 对象（自实现缠论引擎）
    
    这是一个占位实现，用于：
    1. 提供基本的缠论结构计算功能
    2. 提供统一的接口（get_bis/get_xds 等）
    3. 后续可以替换为更完整的缠论算法实现
    
    当前实现的算法简化逻辑：
    - 分型：使用 3 根 K 线识别顶分型/底分型
    - 笔：根据分型生成，满足最小 K 线数要求
    - 线段：根据笔生成，满足最小笔数要求
    - 中枢：识别笔/线段的震荡区间
    - 买卖点/背驰：未实现（返回空列表）
    """
    
    def __init__(self, code: str, frequency: str, config: Dict[str, Any]):
        self.code = code
        self.frequency = frequency
        self.config = config
        
        # 算法参数（从 config 中读取，或使用默认值）
        self.bi_min_kline = config.get('bi_min_kline', 5)  # 笔的最小 K 线数量
        self.xd_min_bi = config.get('xd_min_bi', 3)  # 线段的最小笔数量
        self.zs_min_bi = config.get('zs_min_bi', 3)  # 中枢的最小笔数量
        
        # 缠论结构结果
        self._bis: List[SimpleBi] = []
        self._xds: List[SimpleXD] = []
        self._bi_zss: List[SimpleZS] = []
        self._xd_zss: List[SimpleZS] = []
        self._zsd_zss: List[SimpleZS] = []
    
    def process_klines(self, df: pd.DataFrame) -> "SimpleICL":
        """对 K 线进行缠论结构计算
        
        计算流程：
        1. 计算分型（顶分型/底分型）
        2. 根据分型生成笔
        3. 根据笔生成线段
        4. 计算笔中枢和线段中枢
        5. 计算买卖点和背驰（简化实现中未实现）
        """
        kline_count = len(df)
        
        if kline_count == 0:
            return self
        
        # 确保 df 有必要的字段
        required_cols = ['date', 'open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"缺少必须字段: {col}")
        
        # 1. 计算分型
        fx_list = self._calculate_fx(df)
        
        # 2. 根据分型生成笔
        self._bis = self._calculate_bi(df, fx_list)
        
        # 3. 根据笔生成线段
        self._xds = self._calculate_xd(self._bis)
        
        # 3.5 计算笔和线段的力度（MACD 柱子之和）
        self._calculate_strengths(df)
        
        # 4. 计算中枢
        self._bi_zss = self._calculate_zs(self._bis, "bi")
        self._xd_zss = self._calculate_zs(self._xds, "xd")
        
        # 5. 计算买卖点和背驰（简化实现：生成模拟数据）
        self._calculate_mmds_and_bcs()
        
        return self
    
    def _calculate_fx(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """计算分型（顶分型和底分型）
        
        简化逻辑：
        - 顶分型：中间 K 线高点最高，且低点也高于两侧
        - 底分型：中间 K 线低点最低，且高点也低于两侧
        
        返回：
        - 分型列表，每个分型包含 type/index/time/price
        """
        fx_list = []
        
        for i in range(1, len(df) - 1):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]
            next_ = df.iloc[i + 1]
            
            # 顶分型：中间高点最高
            if (
                curr["high"] > prev["high"] and
                curr["high"] > next_["high"] and
                curr["low"] >= prev["low"]  # 简化条件
            ):
                fx_list.append({
                    "type": "ding",
                    "index": i,
                    "time": curr["date"],
                    "price": curr["high"],
                    "kline": curr,
                })
            
            # 底分型：中间低点最低
            elif (
                curr["low"] < prev["low"] and
                curr["low"] < next_["low"] and
                curr["high"] <= prev["high"]  # 简化条件
            ):
                fx_list.append({
                    "type": "di",
                    "index": i,
                    "time": curr["date"],
                    "price": curr["low"],
                    "kline": curr,
                })
        
        return fx_list
    
    def _calculate_bi(self, df: pd.DataFrame, fx_list: List[Dict[str, Any]]) -> List[SimpleBi]:
        """根据分型生成笔
        
        简化逻辑：
        - 从顶分型到底分型生成下笔
        - 从底分型到顶分型生成上笔
        - 需要满足最小 K 线数要求
        - 需要保证相邻笔的方向不同
        """
        if len(fx_list) < 2:
            return []
        
        bis = []
        bi_index = 0
        
        # 从第一个分型开始遍历
        for i in range(len(fx_list) - 1):
            fx_start = fx_list[i]
            fx_end = fx_list[i + 1]
            
            # 检查 K 线数量
            kline_count = fx_end["index"] - fx_start["index"]
            if kline_count < self.bi_min_kline:
                continue
            
            # 判断笔的方向
            if fx_start["type"] == "di" and fx_end["type"] == "ding":
                # 上笔
                direction = "up"
            elif fx_start["type"] == "ding" and fx_end["type"] == "di":
                # 下笔
                direction = "down"
            else:
                # 同类型分型，跳过
                continue
            
            # 检查与上一笔的方向是否一致（需要交替）
            if bis and bis[-1].type == direction:
                continue
            
            # 生成笔
            bi = SimpleBi(
                index=bi_index,
                direction=direction,
                start_time=fx_start["time"],
                end_time=fx_end["time"],
                start_price=fx_start["price"],
                end_price=fx_end["price"],
                start_index=fx_start["index"],
                end_index=fx_end["index"],
            )
            bis.append(bi)
            bi_index += 1
        
        return bis
    
    def _calculate_strengths(self, df: pd.DataFrame) -> None:
        """计算笔和线段的力度（基于 MACD 柱子之和）"""
        if not self._bis:
            return
        
        close = df["close"].astype(float)
        # 典型 MACD 参数：12, 26, 9
        ema_short = close.ewm(span=12, adjust=False).mean()
        ema_long = close.ewm(span=26, adjust=False).mean()
        dif = ema_short - ema_long
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_hist = (dif - dea) * 2  # 与常规 MACD 保持一致
        hist_values = macd_hist.to_list()
        n = len(hist_values)
        
        # 1) 为每一笔计算力度
        for bi in self._bis:
            start_idx = getattr(bi, "start_index", None)
            end_idx = getattr(bi, "end_index", None)
            if start_idx is None or end_idx is None:
                bi.strength = 0.0
                continue
            s = max(0, min(start_idx, end_idx))
            e = min(n - 1, max(start_idx, end_idx))
            segment = hist_values[s : e + 1]
            if bi.type == "up":
                bi.strength = float(sum(v for v in segment if v > 0))
            else:
                bi.strength = float(sum(-v for v in segment if v < 0))
        
        # 2) 为每一线段计算力度（笔力度之和）
        for xd in self._xds:
            start_bi_index = getattr(xd, "start_bi_index", None)
            end_bi_index = getattr(xd, "end_bi_index", None)
            if start_bi_index is None or end_bi_index is None:
                xd.strength = 0.0
                continue
            s = max(0, min(start_bi_index, end_bi_index))
            e = min(len(self._bis) - 1, max(start_bi_index, end_bi_index))
            xd.strength = float(sum(self._bis[i].strength for i in range(s, e + 1)))
    
    def _calculate_xd(self, bis: List[SimpleBi]) -> List[SimpleXD]:
        """根据笔生成线段
        
        简化逻辑：
        - 将连续的同方向笔合并为线段
        - 需要满足最小笔数要求
        """
        if len(bis) < self.xd_min_bi:
            return []
        
        xds = []
        xd_index = 0
        i = 0
        
        while i < len(bis):
            start_bi = bis[i]
            direction = start_bi.type
            
            # 找到方向变化的位置
            j = i + 1
            while j < len(bis) and bis[j].type == direction:
                j += 1
            
            # 检查笔数
            bi_count = j - i
            if bi_count >= self.xd_min_bi:
                end_bi = bis[j - 1]
                
                # 生成线段
                xd = SimpleXD(
                    index=xd_index,
                    direction=direction,
                    start_time=start_bi.start_time,
                    end_time=end_bi.end_time,
                    start_price=start_bi.start_price,
                    end_price=end_bi.end_price,
                    ding_time=end_bi.end_time if direction == "up" else start_bi.start_time,
                    di_time=start_bi.start_time if direction == "up" else end_bi.end_time,
                    start_bi_index=i,
                    end_bi_index=j - 1,
                )
                xds.append(xd)
                xd_index += 1
            
            i = j if j > i else i + 1
        
        return xds
    
    def _calculate_zs(self, items: List[Any], level: str) -> List[SimpleZS]:
        """计算中枢（修复版）
        
        缠论中枢定义：
        - 至少 3 个连续的笔/线段有重叠区间
        - 中枢是笔的「结束价」的重叠区间
        - 对于笔：
          - 上笔：从 start_price(低) 到 end_price(高)
          - 下笔：从 start_price(高) 到 end_price(低)
        - zg (中枢高点): 前 3 个笔的最低的顶部
        - zd (中枢低点): 前 3 个笔的最高的底部
        - gg (高高点): 中枢内所有笔的最高点
        - dd (低低点): 中枢内所有笔的最低点
        """
        if len(items) < self.zs_min_bi:
            return []
        
        zss = []
        zs_index = 0
        i = 0
        
        def get_bi_range(bi: Any) -> tuple:
            """获取笔的价格区间（低点、高点）"""
            if bi.type == "up":
                # 上笔：从低到高
                return (bi.start_price, bi.end_price)
            else:
                # 下笔：从高到低
                return (bi.end_price, bi.start_price)
        
        while i < len(items) - self.zs_min_bi + 1:
            # 取连续 3 个项作为中枢的起始项
            group = items[i:i + self.zs_min_bi]
            
            # 计算重叠区间（使用笔的价格区间）
            ranges = [get_bi_range(item) for item in group]
            
            # 中枢高点 zg：所有笔的最低的高点
            # 中枢低点 zd：所有笔的最高的低点
            lows = [r[0] for r in ranges]
            highs = [r[1] for r in ranges]
            
            zg = min(highs)  # 中枢高点：最低的高点
            zd = max(lows)   # 中枢低点：最高的低点
            
            # 如果有重叠，则形成中枢
            if zd < zg:
                # 扩展中枢：尝试将后续的项加入中枢
                zs_items = list(group)
                j = i + self.zs_min_bi
                
                while j < len(items):
                    next_item = items[j]
                    next_low, next_high = get_bi_range(next_item)
                    
                    # 检查下一项是否与中枢重叠
                    if next_low <= zg and next_high >= zd:
                        zs_items.append(next_item)
                        j += 1
                    else:
                        break
                
                # 计算最终的 zg, zd, gg, dd
                all_ranges = [get_bi_range(item) for item in zs_items]
                all_lows = [r[0] for r in all_ranges]
                all_highs = [r[1] for r in all_ranges]
                
                # 重新计算 zg, zd (使用前 3 项)
                first_three_ranges = all_ranges[:3]
                first_three_lows = [r[0] for r in first_three_ranges]
                first_three_highs = [r[1] for r in first_three_ranges]
                zg = min(first_three_highs)
                zd = max(first_three_lows)
                
                # 计算 gg, dd (使用所有项)
                gg = max(all_highs)
                dd = min(all_lows)
                
                # 判断中枢类型
                if gg > zg and dd < zd:
                    zs_type_name = "zd"  # 震荡
                elif gg > zg:
                    zs_type_name = "up"  # 向上
                elif dd < zd:
                    zs_type_name = "down"  # 向下
                else:
                    zs_type_name = "zd"  # 默认震荡
                
                zs = SimpleZS(
                    index=zs_index,
                    zs_type=level,
                    direction=zs_type_name,
                    start_time=zs_items[0].start_time,
                    end_time=zs_items[-1].end_time,
                    low=zd,
                    high=zg,
                )
                # 手动设置 gg 和 dd
                zs.zg = zg
                zs.zd = zd
                zs.gg = gg
                zs.dd = dd
                
                zss.append(zs)
                zs_index += 1
                
                # 跳过已处理的项
                i = j
            else:
                i += 1
        
        return zss
    
    def _calculate_mmds_and_bcs(self) -> None:
        """计算买卖点和背驰（真实算法）
        
        缠论背驰定义：
        - 笔背驰：两笔之间的力度对比，后笔力度更弱
        - 段背驰：两线段之间的力度对比，后段力度更弱
        
        买卖点定义：
        - 一买/一卖：笔背驰 + 离开中枢
        - 二买/二卖：线段背驰 + 离开中枢
        - 三买/三卖：走势背驰 + 离开中枢
        """
        # 1. 计算笔的背驰和买卖点
        self._calculate_bi_bcs_and_mmds()
        
        # 2. 计算线段的背驰和买卖点
        self._calculate_xd_bcs_and_mmds()
        
        # 3. 计算三类买卖点
        self._calculate_xd_class3_mmds()
        
        # 4. 计算类二/类三买卖点
        self._calculate_xd_like_class2_and_class3_mmds()
    
    def _calculate_bi_bcs_and_mmds(self) -> None:
        """计算笔的背驰和买卖点"""
        if len(self._bis) < 5:  # 至少需要 5 笔才能形成背驰
            return
        
        # 遍历每个笔，检测背驰
        for i in range(2, len(self._bis)):
            current_bi = self._bis[i]
            
            # 查找前面同方向的笔
            for j in range(i - 2, -1, -2):  # 每次跳 2 笔（同方向）
                prev_bi = self._bis[j]
                
                if current_bi.type != prev_bi.type:
                    continue
                
                # 检测背驰
                is_bc = self._check_bi_divergence(prev_bi, current_bi)
                
                if is_bc:
                    # 查找相关中枢
                    related_zs = self._find_related_zs(current_bi, self._bi_zss)
                    
                    # 添加背驰
                    current_bi.bcs.append(SimpleBC(
                        bc_type="bi",
                        is_bc=True,
                        zs=related_zs
                    ))
                    
                    # 判断是否为买卖点
                    if related_zs and self._is_leaving_zs(current_bi, related_zs):
                        if current_bi.type == "down":
                            # 下笔背驰且离开中枢 -> 一买
                            current_bi.mmds.append(SimpleMMD(
                                name="1buy",
                                zs=related_zs,
                                msg="笔背驰一买"
                            ))
                        else:
                            # 上笔背驰且离开中枢 -> 一卖
                            current_bi.mmds.append(SimpleMMD(
                                name="1sell",
                                zs=related_zs,
                                msg="笔背驰一卖"
                            ))
                    
                    break  # 找到背驰后跳出
    
    def _calculate_xd_bcs_and_mmds(self) -> None:
        """计算线段的背驰和买卖点"""
        if len(self._xds) < 3:
            return
        
        # 遍历每个线段，检测背驰
        for i in range(2, len(self._xds)):
            current_xd = self._xds[i]
            
            # 查找前面同方向的线段
            for j in range(i - 2, -1, -2):
                prev_xd = self._xds[j]
                
                if current_xd.type != prev_xd.type:
                    continue
                
                # 检测背驰
                is_bc = self._check_xd_divergence(prev_xd, current_xd)
                
                if is_bc:
                    # 查找相关中枢
                    related_zs = self._find_related_zs(current_xd, self._xd_zss)
                    
                    # 添加背驰
                    current_xd.bcs.append(SimpleBC(
                        bc_type="xd",
                        is_bc=True,
                        zs=related_zs
                    ))
                    
                    # 判断是否为买卖点
                    if related_zs and self._is_leaving_zs(current_xd, related_zs):
                        if current_xd.type == "down":
                            # 下线段背驰且离开中枢 -> 二买
                            current_xd.mmds.append(SimpleMMD(
                                name="2buy",
                                zs=related_zs,
                                msg="线段背驰二买"
                            ))
                        else:
                            # 上线段背驰且离开中枢 -> 二卖
                            current_xd.mmds.append(SimpleMMD(
                                name="2sell",
                                zs=related_zs,
                                msg="线段背驰二卖"
                            ))
                    
                    break
    
    def _calculate_xd_class3_mmds(self) -> None:
        """计算三类买卖点（基于线段和线段中枢）"""
        if not self._xds or not self._xd_zss:
            return
        
        xds = self._xds
        zss = self._xd_zss
        
        def get_xd_range(xd: SimpleXD) -> tuple:
            """获取线段价格区间（低点、高点）"""
            start_price = getattr(xd, "start_price", 0.0)
            end_price = getattr(xd, "end_price", 0.0)
            low = min(start_price, end_price)
            high = max(start_price, end_price)
            return low, high
        
        for zs in zss:
            # 找到属于该中枢时间区间内的线段索引
            indices_in_zs = []
            for idx, xd in enumerate(xds):
                start_time = getattr(xd, "start_time", None)
                end_time = getattr(xd, "end_time", None)
                if start_time is None or end_time is None:
                    continue
                if start_time >= zs.start_time and end_time <= zs.end_time:
                    indices_in_zs.append(idx)
            
            if not indices_in_zs:
                continue
            
            last_idx = indices_in_zs[-1]
            
            # 从离开中枢后的第一条线段开始寻找三类买卖点
            i = last_idx + 1
            while i < len(xds):
                xd = xds[i]
                start_price = getattr(xd, "start_price", None)
                if start_price is None:
                    i += 1
                    continue
                low, high = get_xd_range(xd)
                
                # 向上离开中枢，寻找三类买点
                if xd.type == "up" and zs.zd < start_price < zs.zg and high > zs.zg:
                    # 找后续的第一条向下线段
                    j = i + 1
                    while j < len(xds):
                        down_xd = xds[j]
                        if down_xd.type != "down":
                            j += 1
                            continue
                        down_low, _ = get_xd_range(down_xd)
                        # 不回中枢：最低点仍高于中枢下沿
                        if down_low > zs.zd:
                            down_xd.mmds.append(SimpleMMD(
                                name="3buy",
                                zs=zs,
                                msg="三类买点"
                            ))
                        break
                    break
                
                # 向下离开中枢，寻找三类卖点
                if xd.type == "down" and zs.zd < start_price < zs.zg and low < zs.zd:
                    j = i + 1
                    while j < len(xds):
                        up_xd = xds[j]
                        if up_xd.type != "up":
                            j += 1
                            continue
                        _, up_high = get_xd_range(up_xd)
                        # 不回中枢：最高点仍低于中枢上沿
                        if up_high < zs.zg:
                            up_xd.mmds.append(SimpleMMD(
                                name="3sell",
                                zs=zs,
                                msg="三类卖点"
                            ))
                        break
                    break
                
                i += 1
    
    def _calculate_xd_like_class2_and_class3_mmds(self) -> None:
        """计算类二、类三买卖点（基于已有二类/三类买卖点）"""
        if not self._xds:
            return
        
        def get_xd_range(xd: SimpleXD) -> tuple:
            start_price = getattr(xd, "start_price", 0.0)
            end_price = getattr(xd, "end_price", 0.0)
            low = min(start_price, end_price)
            high = max(start_price, end_price)
            return low, high
        
        last_2buy_xd: Optional[SimpleXD] = None
        last_2sell_xd: Optional[SimpleXD] = None
        last_3buy_xd: Optional[SimpleXD] = None
        last_3sell_xd: Optional[SimpleXD] = None
        
        for xd in self._xds:
            low, high = get_xd_range(xd)
            
            # 类第二类买点/卖点
            if last_2buy_xd is not None and xd.type == "up":
                prev_low, prev_high = get_xd_range(last_2buy_xd)
                # 与前一二类买点线段形成价格重叠（近似中枢），且当前低点抬高
                if min(high, prev_high) > max(low, prev_low) and low > prev_low:
                    xd.mmds.append(SimpleMMD(
                        name="class2buy",
                        zs=None,
                        msg="类第二类买点"
                    ))
            if last_2sell_xd is not None and xd.type == "down":
                prev_low, prev_high = get_xd_range(last_2sell_xd)
                if min(high, prev_high) > max(low, prev_low) and high < prev_high:
                    xd.mmds.append(SimpleMMD(
                        name="class2sell",
                        zs=None,
                        msg="类第二类卖点"
                    ))
            
            # 类第三类买点/卖点
            if last_3buy_xd is not None and xd.type == "up":
                prev_low, prev_high = get_xd_range(last_3buy_xd)
                if min(high, prev_high) > max(low, prev_low) and low > prev_low:
                    xd.mmds.append(SimpleMMD(
                        name="class3buy",
                        zs=None,
                        msg="类第三类买点"
                    ))
            if last_3sell_xd is not None and xd.type == "down":
                prev_low, prev_high = get_xd_range(last_3sell_xd)
                if min(high, prev_high) > max(low, prev_low) and high < prev_high:
                    xd.mmds.append(SimpleMMD(
                        name="class3sell",
                        zs=None,
                        msg="类第三类卖点"
                    ))
            
            # 更新最近的二类/三类买卖点线段
            mmd_names = [getattr(m, "name", "") for m in getattr(xd, "mmds", []) or []]
            if "2buy" in mmd_names and xd.type == "up":
                last_2buy_xd = xd
            if "2sell" in mmd_names and xd.type == "down":
                last_2sell_xd = xd
            if "3buy" in mmd_names and xd.type == "up":
                last_3buy_xd = xd
            if "3sell" in mmd_names and xd.type == "down":
                last_3sell_xd = xd
    
    def _check_bi_divergence(self, prev_bi: SimpleBi, current_bi: SimpleBi) -> bool:
        """检测笔背驰
        
        规则：
        - 同方向两笔比较；
        - 后一笔价格更极端（新高/新低）；
        - 后一笔力度（MACD 柱子之和）明显减弱。
        """
        if prev_bi.type != current_bi.type:
            return False
        
        prev_strength = getattr(prev_bi, "strength", 0.0)
        curr_strength = getattr(current_bi, "strength", 0.0)
        if prev_strength <= 0 or curr_strength <= 0:
            return False
        
        if prev_bi.type == "up":
            # 上笔：后笔高点更高但力度更弱
            return (
                current_bi.end_price > prev_bi.end_price
                and curr_strength < prev_strength * 0.8
            )
        else:
            # 下笔：后笔低点更低但力度更弱
            return (
                current_bi.end_price < prev_bi.end_price
                and curr_strength < prev_strength * 0.8
            )
    
    def _check_xd_divergence(self, prev_xd: SimpleXD, current_xd: SimpleXD) -> bool:
        """检测线段背驰（段背驰）"""
        if prev_xd.type != current_xd.type:
            return False
        
        prev_strength = getattr(prev_xd, "strength", 0.0)
        curr_strength = getattr(current_xd, "strength", 0.0)
        if prev_strength <= 0 or curr_strength <= 0:
            return False
        
        if prev_xd.type == "up":
            return (
                current_xd.end_price > prev_xd.end_price
                and curr_strength < prev_strength * 0.8
            )
        else:
            return (
                current_xd.end_price < prev_xd.end_price
                and curr_strength < prev_strength * 0.8
            )
    
    def _find_related_zs(self, item: Any, zss: List[SimpleZS]) -> Optional[SimpleZS]:
        """查找与笔/线段相关的中枢"""
        for zs in zss:
            # 检查时间重叠
            if (item.start_time <= zs.end_time and 
                item.end_time >= zs.start_time):
                return zs
        return None
    
    def _is_leaving_zs(self, item: Any, zs: SimpleZS) -> bool:
        """判断是否离开中枢
        
        离开中枢的定义：
        - 下笔/下线段：结束价低于中枢低点 zd
        - 上笔/上线段：结束价高于中枢高点 zg
        """
        if item.type == "down":
            return item.end_price < zs.zd
        else:
            return item.end_price > zs.zg
    
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


# 将 SimpleICL 作为 ICL 的别名，保持接口一致
ICL = SimpleICL


@dataclass
class EngineConfig:
    """缠论引擎配置

    说明：
    - 与 `config.yaml` 中的 `chanlun` 小节一一对应（或尽量贴近）
    - 使用 `options` 自由承载缠论引擎所需配置项
    - engine 只做"透传"：不会修改或二次解释这些配置
    """

    # 缠论引擎的配置字典，内容直接透传给 ICL(config=...) 参数
    options: Dict[str, Any] = None
    
    # 算法参数
    bi_min_kline: int = 5  # 笔的最小 K 线数量
    xd_min_bi: int = 3     # 线段的最小笔数量
    zs_min_bi: int = 3     # 中枢的最小笔数量
    
    def __post_init__(self):
        if self.options is None:
            self.options = {}


@dataclass
class KlineInput:
    """供 engine 使用的最小 K 线输入结构

    说明：
    - engine 不关心数据来源（交易所 / 本地文件），也不关心更多业务字段
    - 只要求这几个字段，以便转换为 ICL 需要的 DataFrame:
      - date:  datetime 或可被 pandas.to_datetime 转换的值
      - open:  开盘价
      - high:  最高价
      - low:   最低价
      - close: 收盘价
      - volume: 成交量
    - 可以在 mapper.py 中将任意数据源统一转换为此结构
    """

    date: Any
    open: float
    high: float
    low: float
    close: float
    volume: float


class ChanlunEngine:
    """面向上层的缠论引擎封装

    使用方式示意（伪代码）：

    >>> engine_cfg = EngineConfig(options={"kline_type": "kline_chanlun"})
    >>> engine = ChanlunEngine(engine_cfg)
    >>> icl = engine.analyze_klines(
    ...     code="BTC/USDT",
    ...     frequency="1m",
    ...     klines=kline_list,  # List[KlineInput] 或兼容结构
    ... )
    >>> bis = icl.get_bis()
    >>> xds = icl.get_xds()

    本类的核心目标：
    - 保证输入 K 线“原样”进入 ICL，只做必要的结构转换（list -> DataFrame）。
    - 保证输出为 ICL 原始对象，不做任何 JSON / dict 映射。
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config

    def analyze_klines(
        self,
        *,
        code: str,
        frequency: str,
        klines: Iterable[KlineInput | Dict[str, Any]],
    ) -> ICL:
        """对一段完整 K 线序列进行缠论计算

        参数：
        - code:       品种代码 / 交易对，例如 "BTC/USDT"
        - frequency:  周期字符串，例如 "1m"、"5m"、"1h" 等
        - klines:     已按时间顺序排好的一段完整 K 线序列：
                       - 可以是 KlineInput 实例的可迭代对象
                       - 也可以是包含 date/open/high/low/close/volume 键的 dict 可迭代对象

        关键约束：
        - 本方法不会对 K 线序列进行裁剪、过滤、排序等"修改操作"，
          只做最小必要的结构转换，以满足 ICL.process_klines 的 DataFrame 输入要求。
        
        返回：
        - ICL 实例，上层可通过其 get_xxx 方法获取笔、线段、中枢等结构。
        """

        # 1. 将传入的 klines 原样遍历，构造 DataFrame 所需的行数据
        rows: List[Dict[str, Any]] = []
        for k in klines:
            # 支持两类输入：KlineInput 或 dict
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
                # 约定 dict 至少包含以下字段；若字段名不同，应在 mapper.py 中统一
                row = {
                    "date": k["date"],
                    "open": k["open"],
                    "high": k["high"],
                    "low": k["low"],
                    "close": k["close"],
                    "volume": k["volume"],
                }
            rows.append(row)

        # 2. 输入验证
        if not rows:
            logger.error(f"[{code}] {frequency} - K 线序列为空")
            raise ValueError("analyze_klines 收到的 K 线序列为空，无法进行缠论计算")
        
        if len(rows) < 50:
            logger.error(f"[{code}] {frequency} - K 线数量不足: {len(rows)} 根（需要至少 50 根）")
            raise ValueError(f"K 线数量不足，至少需要 50 根，当前 {len(rows)} 根")
        
        logger.info(f"[{code}] {frequency} - 开始缠论分析，共 {len(rows)} 根 K 线")

        # 3. 构造 pandas.DataFrame，并确保日期列为 datetime 类型
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # 若存在无法转换为 datetime 的值，可以选择在此抛错，避免静默使用无效时间
        if df["date"].isna().any():
            logger.error(f"[{code}] {frequency} - K 线数据中存在无效的 date 字段")
            raise ValueError("K 线数据中存在无法转换为 datetime 的 date 字段，请在 mapper 中清洗")

        # 4. 初始化 ICL 对象
        icl = ICL(code=code, frequency=frequency, config=self._config.options)
        
        # 5. 将完整的 DataFrame 传入 ICL 进行缠论计算
        icl = icl.process_klines(df)  # type: ignore[assignment]
        
        # 记录结果统计
        bis_count = len(icl.get_bis())
        xds_count = len(icl.get_xds())
        bi_zss_count = len(icl.get_bi_zss())
        logger.info(
            f"[{code}] {frequency} - 缠论分析完成: "
            f"笔={bis_count}, 线段={xds_count}, 笔中枢={bi_zss_count}"
        )

        # 6. 原样返回 ICL 实例（原始结构对象），不做 JSON 映射或字段抽取
        return icl
