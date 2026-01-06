"""缠论引擎封装（engine）

本模块的职责：
- 接收已经准备好的、完整的 K 线数据序列（不裁剪、不修改）
- 调用 chanlun-pro 提供的 ICL 接口进行缠论计算
- 返回 chanlun-pro 的原始 ICL 对象，供上层按需读取笔、线段、中枢、买卖点、背驰等结构

本模块不会做的事情：
- 不从交易所 / 本地文件加载原始数据（这部分交给 mapper.py）
- 不把结果转换成 JSON / dict（序列化交给上层）
- 不裁剪 K 线数量，不更改数据内容

参考文档：
- 缠论配置项说明
- 缠论买卖点和背驰规则
- 缠论数据对象与方法
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


# ============================================================
# 简化的缠论结构对象（不依赖 chanlun-pro）
# ============================================================

class SimpleBi:
    """简化的笔对象（占位实现）"""
    def __init__(
        self,
        index: int,
        direction: str,
        start_time: Any,
        end_time: Any,
        start_price: float,
        end_price: float,
    ):
        self.index = index
        self.type = direction  # 'up' or 'down'
        # 时间与价格信息（供 AI 使用）
        self.start_time = start_time
        self.end_time = end_time
        self.start_price = float(start_price)
        self.end_price = float(end_price)
        self.mmds = []  # 买卖点列表
        self.bcs = []   # 背驰列表
    
    def __repr__(self):
        return (
            f"<SimpleBi index={self.index} type={self.type} "
            f"start={self.start_time} end={self.end_time}>"
        )

class SimpleXD:
    """简化的线段对象（占位实现）"""
    def __init__(
        self,
        index: int,
        direction: str,
        start_time: Any,
        end_time: Any,
        start_price: float,
        end_price: float,
    ):
        self.index = index
        self.type = direction
        self.start_time = start_time
        self.end_time = end_time
        self.start_price = start_price
        self.end_price = end_price
        self.mmds: List[Any] = []
        self.bcs: List[Any] = []
    
    def __repr__(self) -> str:
        return (
            f"<SimpleXD index={self.index} type={self.type} "
            f"start={self.start_price} end={self.end_price}>"
        )

class SimpleZS:
    """简化的中枢对象（占位实现）"""
    def __init__(
        self,
        index: int,
        zs_type: str,
        start_time: Any,
        end_time: Any,
        high: float,
        low: float,
        level: int = 1,
        relation: str = "expand",
    ):
        self.index = index
        self.zs_type = zs_type  # "bi" 笔中枢 / "xd" 线段中枢
        self.start_time = start_time
        self.end_time = end_time
        self.high = high
        self.low = low
        self.level = level  # 中枢等级
        self.relation = relation  # expand/震荡/突破
    
    def __repr__(self) -> str:
        return (
            f"<SimpleZS index={self.index} type={self.zs_type} "
            f"high={self.high} low={self.low} level={self.level}>"
        )

class SimpleICL:
    """简化的 ICL 对象（不依赖 chanlun-pro）
    
    这是一个占位实现，用于：
    1. 在没有 chanlun-pro 授权的情况下让项目能跑起来
    2. 提供与真实 ICL 一致的接口（get_bis/get_xds 等）
    3. 后续可以替换为真实的缠论算法实现
    """
    
    def __init__(self, code: str, frequency: str, config: Dict[str, Any]):
        self.code = code
        self.frequency = frequency
        self.config = config
        self._bis: List[SimpleBi] = []
        self._xds: List[SimpleXD] = []
        self._bi_zss: List[SimpleZS] = []
        self._xd_zss: List[SimpleZS] = []
        self._zsd_zss: List[SimpleZS] = []
    
    def process_klines(self, df: pd.DataFrame) -> "SimpleICL":
        """处理 K 线数据（占位实现）
        
        当前只是生成一些模拟数据，实际缠论算法需要后续实现
        但现在会从真实 K 线中提取时间和价格信息
        """
        kline_count = len(df)
        
        if kline_count == 0:
            return self
        
        # 确保 df 有必要的字段
        required_cols = ['date', 'open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"缺少必须字段: {col}")
        
        # 模拟生成一些笔（每10根K线一笔）
        bi_step = 10
        for i in range(0, kline_count // bi_step):
            # 计算起始和结束的 K 线索引
            start_idx = i * bi_step
            end_idx = min((i + 1) * bi_step - 1, kline_count - 1)
            
            direction = "up" if i % 2 == 0 else "down"
            
            # 从 df 中提取时间和价格
            start_time = df.iloc[start_idx]['date']
            end_time = df.iloc[end_idx]['date']
            
            if direction == "up":
                # 上升笔：从低点到高点
                start_price = df.iloc[start_idx]['low']
                end_price = df.iloc[end_idx]['high']
            else:
                # 下降笔：从高点到低点
                start_price = df.iloc[start_idx]['high']
                end_price = df.iloc[end_idx]['low']
            
            self._bis.append(SimpleBi(
                index=i,
                direction=direction,
                start_time=start_time,
                end_time=end_time,
                start_price=start_price,
                end_price=end_price,
            ))
        
        # 模拟生成一些线段（每30根K线一段）
        xd_step = 30
        for i in range(0, kline_count // xd_step):
            start_idx = i * xd_step
            end_idx = min((i + 1) * xd_step - 1, kline_count - 1)
            
            direction = "up" if i % 2 == 0 else "down"
            
            start_time = df.iloc[start_idx]['date']
            end_time = df.iloc[end_idx]['date']
            
            if direction == "up":
                start_price = df.iloc[start_idx]['low']
                end_price = df.iloc[end_idx]['high']
            else:
                start_price = df.iloc[start_idx]['high']
                end_price = df.iloc[end_idx]['low']
            
            self._xds.append(SimpleXD(
                index=i,
                direction=direction,
                start_time=start_time,
                end_time=end_time,
                start_price=start_price,
                end_price=end_price,
            ))
        
        # 模拟生成一个中枢（使用中间一段 K 线）
        if kline_count >= 50:
            # 取中间 20% ~ 80% 的 K 线作为中枢区间
            zs_start_idx = int(kline_count * 0.2)
            zs_end_idx = int(kline_count * 0.8)
            
            zs_start_time = df.iloc[zs_start_idx]['date']
            zs_end_time = df.iloc[zs_end_idx]['date']
            
            # 中枢的高低点：取区间内的最高和最低
            zs_high = df.iloc[zs_start_idx:zs_end_idx+1]['high'].max()
            zs_low = df.iloc[zs_start_idx:zs_end_idx+1]['low'].min()
            
            self._bi_zss.append(SimpleZS(
                index=0,
                zs_type="bi",
                start_time=zs_start_time,
                end_time=zs_end_time,
                high=zs_high,
                low=zs_low,
                level=1,
                relation="expand",
            ))
        
        return self
    
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
    - 与 `config.yaml` 中的 `chanlun` 小节一一对应（或尽量贴近）。
    - 不强行规定所有字段，而是使用 `options` 自由承载 chanlun-pro 所需配置项，
      比如：kline_type、bi_type、zs_bi_type、zs_xd_type、fx_qj、zs_wzgx 等。
    - engine 只做“透传”：不会修改或二次解释这些配置。
    """

    # chanlun-pro 的配置字典，内容直接透传给 ICL(config=...) 参数
    options: Dict[str, Any]


@dataclass
class KlineInput:
    """供 engine 使用的最小 K 线输入结构

    说明：
    - engine 不关心数据来源（交易所 / 本地文件），也不关心更多业务字段。
    - 只要求这几个字段，以便转换为 ICL 需要的 DataFrame:
      - date:  datetime 或可被 pandas.to_datetime 转换的值
      - open:  开盘价
      - high:  最高价
      - low:   最低价
      - close: 收盘价
      - volume: 成交量
    - 你可以在 mapper.py 中将任意数据源统一转换为此结构。
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
        - code:       品种代码 / 交易对，例如 "BTC/USDT"。
        - frequency:  周期字符串，例如 "1m"、"5m"、"1h" 等，需要与 chanlun-pro 支持的周期一致。
        - klines:     已按时间顺序排好的一段完整 K 线序列：
                       - 可以是 KlineInput 实例的可迭代对象
                       - 也可以是包含 date/open/high/low/close/volume 键的 dict 可迭代对象

        关键约束：
        - 本方法不会对 K 线序列进行裁剪、过滤、排序等“修改操作”，
          只做最小必要的结构转换，以满足 ICL.process_klines 的 DataFrame 输入要求。

        返回：
        - chanlun-pro 的 ICL 实例，上层可通过其 get_xxx 方法获取笔、线段、中枢等结构。
        """

        # 1. 将传入的 klines 原样遍历，构造 DataFrame 所需的行数据
        #    这里不对数量做任何限制，不进行裁剪。
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

        # 2. 构造 pandas.DataFrame，并确保日期列为 datetime 类型
        #    注意：这里不改变数据的语义，只是结构化为 ICL 要求的形式。
        if not rows:
            raise ValueError("analyze_klines 收到的 K 线序列为空，无法进行缠论计算")

        df = pd.DataFrame(rows)
        # ICL 文档要求 date 为 datetime 类型，这里做一次安全转换
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # 若存在无法转换为 datetime 的值，可以选择在此抛错，避免静默使用无效时间
        if df["date"].isna().any():
            raise ValueError("K 线数据中存在无法转换为 datetime 的 date 字段，请在 mapper 中清洗")

        # 3. 初始化 ICL 对象
        #    - code:      交易对/标的代码
        #    - frequency: 周期
        #    - config:    直接透传 EngineConfig.options
        icl = ICL(code=code, frequency=frequency, config=self._config.options)

        # 4. 将完整的 DataFrame 传入 ICL 进行缠论计算
        #    ICL.process_klines 支持增量多次调用，这里一次性传入完整序列。
        #    该方法按文档返回“当前缠论数据对象”（通常即 self），我们直接使用其返回值。
        icl = icl.process_klines(df)  # type: ignore[assignment]

        # 5. 原样返回 ICL 实例（原始结构对象），不做 JSON 映射或字段抽取
        return icl
