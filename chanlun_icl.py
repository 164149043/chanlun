"""chanlun-pro 引擎封装层（ICL 兼容接口）

本模块的目的：
- 基于 chanlun.engine.ChanLunEngine 提供一个轻量级的 ICL 兼容接口
- 让上层代码（main.py / test_icl.py）可以用统一的方式调用缠论计算
- 不修改 chanlun-pro 内部逻辑，只做"薄封装"

设计原则：
- 输入：pandas.DataFrame（包含 date/open/high/low/close/volume）
- 输出：提供 get_bis() / get_xds() / get_bi_zss() 等方法，返回缠论结构对象
- 透传 chanlun-pro 原始结构，不做额外 JSON 映射
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

# 使用项目自己定义的 ChanlunEngine（在 chanlun_local/engine.py 中）
from chanlun_local.engine import ChanlunEngine, EngineConfig


class ICL:
    """ICL 兼容接口（基于 ChanLunEngine 的薄封装）
    
    用法示例：
        icl = ICL(code="BTC/USDT", frequency="60m", config=None)
        icl = icl.process_klines(df)
        
        bis = icl.get_bis()
        xds = icl.get_xds()
    """

    def __init__(
        self,
        code: str,
        frequency: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初始化缠论引擎
        
        参数：
        - code: 标的代码，如 "BTC/USDT"
        - frequency: 周期，如 "60m"
        - config: 缠论配置字典（可选）
        """
        self._code = code
        self._frequency = frequency
        self._config = config or {}
        
        # 使用 EngineConfig 封装配置
        engine_config = EngineConfig(options=self._config)
        self._engine = ChanlunEngine(engine_config)

    def process_klines(self, df: pd.DataFrame) -> "ICL":
        """处理 K 线数据，完成缠论计算
        
        参数：
        - df: pandas.DataFrame，必须包含列：date / open / high / low / close / volume
        
        返回：
        - 返回 self，支持链式调用
        """
        # 将 DataFrame 转换为 dict 列表（ChanlunEngine.analyze_klines 接受的格式）
        klines = df.to_dict('records')
        
        # 调用引擎的 analyze_klines 方法，返回 ICL 实例
        self._icl_result = self._engine.analyze_klines(
            code=self._code,
            frequency=self._frequency,
            klines=klines,
        )
        
        return self

    def get_bis(self) -> List[Any]:
        """获取笔列表"""
        if not hasattr(self, '_icl_result'):
            return []
        return self._icl_result.get_bis()

    def get_xds(self) -> List[Any]:
        """获取线段列表"""
        if not hasattr(self, '_icl_result'):
            return []
        return self._icl_result.get_xds()

    def get_bi_zss(self, zs_type: Optional[str] = None) -> List[Any]:
        """获取笔中枢列表"""
        if not hasattr(self, '_icl_result'):
            return []
        return self._icl_result.get_bi_zss(zs_type)

    def get_xd_zss(self, zs_type: Optional[str] = None) -> List[Any]:
        """获取线段中枢列表"""
        if not hasattr(self, '_icl_result'):
            return []
        return self._icl_result.get_xd_zss(zs_type)

    def get_zsd_zss(self) -> List[Any]:
        """获取走势段中枢列表"""
        if not hasattr(self, '_icl_result'):
            return []
        return self._icl_result.get_zsd_zss()
