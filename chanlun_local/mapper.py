"""数据映射模块（mapper）

本模块当前主要职责：
- 将 Binance REST API 获取到的 K 线数据，转换为 `engine.KlineInput` 序列
- 严格遵守你定义的 Binance 行情规则：
  - 只使用 open_time / open / high / low / close / close_time 这 6 个字段
  - 不使用 volume / trade_num / quote_volume
  - 按固定周期映射表，将 Binance interval 映射为 chanlun-pro 的 frequency
  - 按推荐数量拉取 K 线，保证足够的历史结构

说明：
- 这里先实现「Binance → 内部 K 线结构」的映射逻辑；
- 至于「chanlun-pro 结构对象 → 你定义的标准 JSON」，还需要你给出最终的 JSON 字段规则，
  才能做到“严格按规则实现，不得新增字段”。在那之前，本文件不会臆造任何 JSON 结构。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from .engine import KlineInput

def _format_datetime(dt: Any) -> str:
    """将 datetime 或可转为字符串的时间值格式化为字符串

    说明：
    - 为了在 JSON 中保持可读性，我们统一使用 "YYYY-MM-DD HH:MM:SS" 格式字符串；
    - 若传入对象没有 strftime 方法，则直接使用 str()。
    """

    try:
        return dt.strftime("%Y-%m-%d %H:%M:%S")  # type: ignore[call-arg]
    except Exception:
        return str(dt)


def bi_to_json(bi: Any) -> Dict[str, Any]:
    """将单个 BI 对象转换为标准 JSON 结构

    字段来源说明：
    - index:            BI.index
    - direction:        BI.type ("up" / "down")
    - start_time:       BI.start.k.date
    - end_time:         BI.end.k.date
    - start_value:      BI.start.val
    - end_value:        BI.end.val
    - high / low:       BI.high / BI.low
    - finished:         BI.is_done()
    - buy_sells:        [m.name for m in BI.mmds]
    - divergences:      [bc.type for bc in BI.bcs if bc.bc]
    """

    start_fx = getattr(bi, "start", None)
    end_fx = getattr(bi, "end", None)

    start_dt = getattr(getattr(start_fx, "k", None), "date", None)
    end_dt = getattr(getattr(end_fx, "k", None), "date", None)

    start_time = _format_datetime(start_dt) if start_dt is not None else ""
    end_time = _format_datetime(end_dt) if end_dt is not None else ""

    start_val = getattr(start_fx, "val", None)
    end_val = getattr(end_fx, "val", None)

    # 买卖点名称列表
    buy_sells: List[str] = []
    for m in getattr(bi, "mmds", []) or []:
        name = getattr(m, "name", "") or ""
        if name:
            buy_sells.append(name)

    # 背驰类型列表
    divergences: List[str] = []
    for bc in getattr(bi, "bcs", []) or []:
        if getattr(bc, "bc", False):
            bc_type = getattr(bc, "type", "") or ""
            if bc_type:
                divergences.append(bc_type)

    try:
        finished = bool(bi.is_done())  # type: ignore[call-arg]
    except Exception:
        finished = False

    return {
        "index": getattr(bi, "index", None),
        "direction": getattr(bi, "type", "") or "",
        "start_time": start_time,
        "end_time": end_time,
        "start_value": float(start_val) if start_val is not None else None,
        "end_value": float(end_val) if end_val is not None else None,
        "high": getattr(bi, "high", None),
        "low": getattr(bi, "low", None),
        "finished": finished,
        "buy_sells": buy_sells,
        "divergences": divergences,
    }


def xd_to_json(xd: Any) -> Dict[str, Any]:
    """将单个 XD 对象转换为标准 JSON 结构

    字段来源说明：
    - index:       XD.index
    - direction:   XD.type
    - start_time:  XD.start.k.date
    - end_time:    XD.end.k.date
    - high / low:  XD.high / XD.low
    - ding_time:   XD.ding_fx.k.date
    - di_time:     XD.di_fx.k.date
    - buy_sells:   [m.name for m in XD.mmds]
    - divergences: [bc.type for bc in XD.bcs if bc.bc]
    """

    start_fx = getattr(xd, "start", None)
    end_fx = getattr(xd, "end", None)
    ding_fx = getattr(xd, "ding_fx", None)
    di_fx = getattr(xd, "di_fx", None)

    start_dt = getattr(getattr(start_fx, "k", None), "date", None)
    end_dt = getattr(getattr(end_fx, "k", None), "date", None)
    ding_dt = getattr(getattr(ding_fx, "k", None), "date", None)
    di_dt = getattr(getattr(di_fx, "k", None), "date", None)

    start_time = _format_datetime(start_dt) if start_dt is not None else ""
    end_time = _format_datetime(end_dt) if end_dt is not None else ""
    ding_time = _format_datetime(ding_dt) if ding_dt is not None else ""
    di_time = _format_datetime(di_dt) if di_dt is not None else ""

    buy_sells: List[str] = []
    for m in getattr(xd, "mmds", []) or []:
        name = getattr(m, "name", "") or ""
        if name:
            buy_sells.append(name)

    divergences: List[str] = []
    for bc in getattr(xd, "bcs", []) or []:
        if getattr(bc, "bc", False):
            bc_type = getattr(bc, "type", "") or ""
            if bc_type:
                divergences.append(bc_type)

    return {
        "index": getattr(xd, "index", None),
        "direction": getattr(xd, "type", "") or "",
        "start_time": start_time,
        "end_time": end_time,
        "high": getattr(xd, "high", None),
        "low": getattr(xd, "low", None),
        "ding_time": ding_time,
        "di_time": di_time,
        "buy_sells": buy_sells,
        "divergences": divergences,
    }


def zs_to_json(zs: Any) -> Dict[str, Any]:
    """将单个 ZS 对象转换为标准 JSON 结构

    字段来源说明：
    - index:   ZS.index
    - zs_type: ZS.zs_type ("bi" / "xd" / "zsd")
    - type:    ZS.type ("up" / "down" / "zd")
    - zg/zd:   ZS.zg / ZS.zd
    - gg/dd:   ZS.gg / ZS.dd
    - level:   ZS.level
    - done:    ZS.done
    - real:    ZS.real
    """

    return {
        "index": getattr(zs, "index", None),
        "zs_type": getattr(zs, "zs_type", "") or "",
        "type": getattr(zs, "type", "") or "",
        "zg": getattr(zs, "zg", None),
        "zd": getattr(zs, "zd", None),
        "gg": getattr(zs, "gg", None),
        "dd": getattr(zs, "dd", None),
        "level": getattr(zs, "level", None),
        "done": getattr(zs, "done", None),
        "real": getattr(zs, "real", None),
    }


def bc_to_json(bc: Any) -> Dict[str, Any]:
    """将单个 BC 对象转换为标准 JSON 结构

    字段来源说明：
    - type:     BC.type ("bi" / "xd" / "zsd" / "pz" / "qs")
    - is_bc:    bool(BC.bc)
    - zs_type:  BC.zs.zs_type (若存在)
    - zs_index: BC.zs.index (若存在)
    """

    zs = getattr(bc, "zs", None)
    return {
        "type": getattr(bc, "type", "") or "",
        "is_bc": bool(getattr(bc, "bc", False)),
        "zs_type": getattr(zs, "zs_type", None) if zs is not None else None,
        "zs_index": getattr(zs, "index", None) if zs is not None else None,
    }


def mmd_to_json(m: Any) -> Dict[str, Any]:
    """将单个买卖点对象转换为标准 JSON 结构

    字段来源说明：
    - name:     MMD.name (1buy/2buy/3sell 等)
    - zs_type:  MMD.zs.zs_type (若存在)
    - zs_index: MMD.zs.index (若存在)
    - msg:      MMD.msg
    """

    zs = getattr(m, "zs", None)
    return {
        "name": getattr(m, "name", "") or "",
        "zs_type": getattr(zs, "zs_type", None) if zs is not None else None,
        "zs_index": getattr(zs, "index", None) if zs is not None else None,
        "msg": getattr(m, "msg", None),
    }


def icl_to_standard_json(icl: Any) -> Dict[str, Any]:
    """将 chanlun-pro 的 ICL 对象映射为标准 JSON 结构

    顶层结构：

    {
        "bi": [...],
        "xd": [...],
        "zs": [...],
        "bc": [...],
        "signal": [...]
    }
    """

    # 1. 笔列表
    try:
        bis = icl.get_bis()  # type: ignore[attr-defined]
    except Exception:
        bis = []
    bi_json = [bi_to_json(bi) for bi in bis]

    # 2. 线段列表
    try:
        xds = icl.get_xds()  # type: ignore[attr-defined]
    except Exception:
        xds = []
    xd_json = [xd_to_json(xd) for xd in xds]

    # 3. 中枢列表（笔中枢 + 线段中枢 + 走势段中枢）
    zs_list: List[Any] = []
    for fn in ("get_bi_zss", "get_xd_zss", "get_zsd_zss"):
        getter = getattr(icl, fn, None)
        if getter is None:
            continue
        try:
            zss = getter(None) if fn != "get_zsd_zss" else getter()  # type: ignore[call-arg]
            zs_list.extend(zss)
        except Exception:
            continue
    zs_json = [zs_to_json(zs) for zs in zs_list]

    # 4. 背驰列表：从所有笔与线段的 bcs 汇总
    bc_json: List[Dict[str, Any]] = []
    for bi in bis:
        for bc in getattr(bi, "bcs", []) or []:
            bc_json.append(bc_to_json(bc))
    for xd in xds:
        for bc in getattr(xd, "bcs", []) or []:
            bc_json.append(bc_to_json(bc))

    # 5. 买卖点列表：从所有笔与线段的 mmds 汇总
    signal_json: List[Dict[str, Any]] = []
    for bi in bis:
        for m in getattr(bi, "mmds", []) or []:
            signal_json.append(mmd_to_json(m))
    for xd in xds:
        for m in getattr(xd, "mmds", []) or []:
            signal_json.append(mmd_to_json(m))

    return {
        "bi": bi_json,
        "xd": xd_json,
        "zs": zs_json,
        "bc": bc_json,
        "signal": signal_json,
    }
BINANCE_INTERVAL_TO_CHANLUN: Dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "60m",
    "4h": "240m",
    "1d": "1d",
}


# 各周期推荐的 K 线数量（用于 main.py 在决定拉取数量时参考）
RECOMMENDED_LIMITS: Dict[str, int] = {
    "1m": 3000,
    "5m": 2000,
    "15m": 1500,
    "60m": 1000,
    "240m": 800,
    "1d": 500,
}


@dataclass
class BinanceKline:
    """内部使用的 Binance K 线最小结构

    说明：
    - 仅保留你指定的 6 个字段；不引入 volume / trade_num / quote_volume。
    - open_time / close_time 使用毫秒时间戳，保持与 Binance REST 返回一致，
      真正喂给 chanlun-pro 时只会用 open_time 转换为 datetime，作为 K 线时间。
    """

    open_time: int  # 毫秒时间戳
    open: float
    high: float
    low: float
    close: float
    close_time: int  # 毫秒时间戳


def binance_interval_to_chanlun(interval: str) -> str:
    """将 Binance 的 interval 映射为 chanlun-pro 的 frequency

    若传入了未在映射表中的 interval，将抛出 ValueError，
    避免出现周期命名混乱的问题。
    """

    try:
        return BINANCE_INTERVAL_TO_CHANLUN[interval]
    except KeyError as exc:  # pragma: no cover - 显式错误分支
        raise ValueError(f"不支持的 Binance interval: {interval}") from exc


def get_recommended_limit_by_frequency(frequency: str) -> int:
    """根据 chanlun-pro 周期获取推荐 K 线数量

    说明：
    - 这里使用的是你给出的「推荐值（稳定）」表；
    - 若传入的 frequency 未在表中，则抛出异常，提醒调用方显式处理。
    - 该函数不会直接发起请求，只提供一个统一的推荐值查询入口。
    """

    try:
        return RECOMMENDED_LIMITS[frequency]
    except KeyError as exc:  # pragma: no cover
        raise ValueError(f"未配置周期 {frequency} 的推荐 K 线数量") from exc


def parse_binance_kline_item(item: Any) -> BinanceKline:
    """将单条 Binance K 线记录解析为 BinanceKline 对象

    支持两种常见形式：
    1. 字典形式（你示例中的 JSON 对象）：
       {
         "open_time": 1703721600000,
         "open": 87442.08,
         "high": 87984.00,
         "low": 87210.00,
         "close": 87803.01,
         "close_time": 1703725199999
       }
    2. Binance 官方 REST /klines 接口返回的列表形式：
       [
         open_time, open, high, low, close,
         volume, close_time, quote_asset_volume,
         number_of_trades, taker_buy_base, taker_buy_quote, ignore
       ]
       在这种情况下，我们只读取前 5 个字段 + 第 7 个 close_time，
       其余 volume / 交易次数等字段全部忽略。
    """

    # 情况一：字典形式
    if isinstance(item, dict):
        return BinanceKline(
            open_time=int(item["open_time"]),
            open=float(item["open"]),
            high=float(item["high"]),
            low=float(item["low"]),
            close=float(item["close"]),
            close_time=int(item["close_time"]),
        )

    # 情况二：列表 / 元组形式（/klines 原始返回）
    if isinstance(item, (list, tuple)) and len(item) >= 7:
        return BinanceKline(
            open_time=int(item[0]),
            open=float(item[1]),
            high=float(item[2]),
            low=float(item[3]),
            close=float(item[4]),
            close_time=int(item[6]),
        )

    raise TypeError("无法解析的 Binance K 线数据格式，仅支持 dict 或 /klines 列表形式")


def normalize_binance_klines(klines: Iterable[Any]) -> List[Dict[str, Any]]:
    """将 Binance 原始 K 线序列标准化为统一结构

    输入：
    - klines: /api/v3/klines 返回的列表，或等价的字典列表

    输出：
    - 按 open_time 升序排序的列表，每一项为：
      {
        "open_time": datetime,
        "open": float,
        "high": float,
        "low": float,
        "close": float,
        "close_time": datetime,
      }

    关键约束：
    - 不做任何技术计算，仅做字段映射与时间格式转换；
    - 不做增量更新，每次视为全量历史数据；
    - 调用方需确保 limit 足够大以支持缠论结构计算。
    """

    result: List[Dict[str, Any]] = []

    for raw in klines:
        bk = parse_binance_kline_item(raw)

        open_dt = datetime.fromtimestamp(bk.open_time / 1000.0, tz=timezone.utc)
        close_dt = datetime.fromtimestamp(bk.close_time / 1000.0, tz=timezone.utc)

        result.append(
            {
                "open_time": open_dt,
                "open": bk.open,
                "high": bk.high,
                "low": bk.low,
                "close": bk.close,
                "close_time": close_dt,
            }
        )

    # 明确按 open_time 升序排序，以防上游返回顺序不稳定
    result.sort(key=lambda x: x["open_time"])
    return result


def binance_klines_to_kline_inputs(klines: Iterable[Any]) -> List[KlineInput]:
    """将 Binance K 线序列转换为 engine.KlineInput 序列

    关键规则：
    - 只使用 open_time / open / high / low / close / close_time 6 个字段；
    - 不使用 volume / trade_num / quote_volume 等量能相关字段；
    - K 线时间使用 open_time（毫秒）转换为 UTC datetime；
    - 因 chanlun-pro 的 ICL 仍要求存在 volume 列，这里统一填充为 0.0，
      表示“无量能信息，仅做结构分析”。

    返回：
    - 已按输入顺序构造好的 KlineInput 列表；
      本函数不会对顺序进行重新排序，也不会裁剪数量。
    """

    result: List[KlineInput] = []

    for raw in klines:
        bk = parse_binance_kline_item(raw)

        # 将毫秒时间戳转换为 datetime 对象
        # 使用 UTC 时区，后续如需本地化，可在展示层处理。
        dt = datetime.fromtimestamp(bk.open_time / 1000.0, tz=timezone.utc)

        k = KlineInput(
            date=dt,
            open=bk.open,
            high=bk.high,
            low=bk.low,
            close=bk.close,
            volume=0.0,  # 严格遵守“缠论只关心结构，不关心成交量”的规则
        )
        result.append(k)

    return result
