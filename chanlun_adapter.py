"""缠论适配模块（chanlun_adapter）

本模块的目标：
- 将来自 Binance 的标准化 K 线数据，转换为缠论引擎可直接使用的 Bar/Kline 结构数据
- K 线对象的字段定义：
  - date:  K线时间（datetime 对象）
  - o:     开盘价（open）
  - h:     最高价（high）
  - l:     最低价（low）
  - c:     收盘价（close）
  - a:     成交量（volume），若上游未提供则可填 0.0

说明：
- 这里不进行任何缠论计算，不创建 ICL 对象，仅做"数据形状转换"
- 不实现策略、不输出分析，仅返回 Bar 列表，供后续缠论计算使用
- Bar 定义为 Python dict，可以直接转换为 pandas.DataFrame 再交给 ICL.process_klines 使用
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List


# 为了兼容 Bar / Kline 的概念，这里将 Bar 定义为一个具有固定字段的字典：
# - date: datetime
# - o/h/l/c: float
# - a: float (volume)
Bar = Dict[str, Any]


@dataclass
class BinanceBar:
    """中间表示层：用于描述从 Binance 标准化 K 线解析出的最小信息

    说明：
    - upstream_data 中的时间字段为 datetime；
    - 不做任何技术分析，只做字段搬运与类型校验。
    """

    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    close_time: datetime


def _ensure_datetime(value: Any) -> datetime:
    """确保输入转为 datetime 类型

    支持：
    - 已经是 datetime
    - 整数/浮点数时间戳（秒）
    - 字符串（ISO 格式），若解析失败则抛出 ValueError
    """

    if isinstance(value, datetime):
        return value

    # 可能是时间戳（秒或毫秒）
    if isinstance(value, (int, float)):
        # 简单判断：大于 10^10 的视为毫秒，小于等于则视为秒
        ts = float(value)
        if ts > 1e10:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts)

    if isinstance(value, str):
        # 尝试按照常见格式解析
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

    raise ValueError(f"无法将值转换为 datetime: {value!r}")


def _parse_binance_bar(item: Dict[str, Any]) -> BinanceBar:
    """从标准 Binance K 线字典解析出 BinanceBar

    预期输入格式：
    {
      "open_time": datetime,
      "open": float,
      "high": float,
      "low": float,
      "close": float,
      "close_time": datetime
    }
    """

    try:
        open_time = _ensure_datetime(item["open_time"])
        close_time = _ensure_datetime(item["close_time"])
        open_price = float(item["open"])
        high_price = float(item["high"])
        low_price = float(item["low"])
        close_price = float(item["close"])
    except KeyError as exc:
        raise KeyError(f"缺少必需的 Binance K 线字段: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Binance K 线字段类型不正确: {item}") from exc

    return BinanceBar(
        open_time=open_time,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        close_time=close_time,
    )


def convert_to_chanlun_bars(klines: List[Dict[str, Any]]) -> List[Bar]:
    """将 Binance K 线数据转换为缠论引擎可用的 Bar 列表

    参数：
    - klines: 来自 Binance 模块标准化后的 K 线列表，每个元素包含：
      {
        "open_time": datetime,
        "open": float,
        "high": float,
        "low": float,
        "close": float,
        "close_time": datetime
      }

    返回：
    - List[Bar]，每个 Bar 的字段定义：
      {
        "date": datetime,  # 使用 open_time 作为 K 线时间
        "o": float,
        "h": float,
        "l": float,
        "c": float,
        "a": float,       # 成交量，这里如上游未提供则统一填 0.0
      }

    保证：
    - 时间顺序正确：按 open_time 升序排序，不合并、不拆分任何一根 K 线；
    - 数据类型正确：价格统一为 float，时间统一为 datetime；
    - 不丢失任何 K 线记录（长度与输入列表一致）。
    """

    # 1. 先将输入解析为 BinanceBar 列表，便于校验与排序
    bars: List[BinanceBar] = []
    for item in klines:
        if not isinstance(item, dict):
            raise TypeError(f"klines 中的元素必须是 dict，当前为: {type(item)}")
        bars.append(_parse_binance_bar(item))

    # 2. 按 open_time 升序排序，确保时间顺序正确
    bars.sort(key=lambda b: b.open_time)

    # 3. 映射为 Bar 字典
    result: List[Bar] = []
    for b in bars:
        bar: Bar = {
            "date": b.open_time,
            "o": b.open,
            "h": b.high,
            "l": b.low,
            "c": b.close,
            "a": 0.0,  # 上游未使用量能，这里统一填 0.0
        }
        result.append(bar)

    return result
