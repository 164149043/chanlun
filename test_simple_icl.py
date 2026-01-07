"""测试 SimpleICL 与 mapper 的兼容性"""
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chanlun_local.engine import SimpleICL, ChanlunEngine, EngineConfig, KlineInput
from chanlun_local.mapper import icl_to_standard_json


def create_test_data(count: int = 200):
    """生成测试K线数据（更真实的震荡走势）"""
    import math
    data = []
    base_time = datetime.now() - timedelta(hours=count)
    
    for i in range(count):
        time = base_time + timedelta(minutes=i)
        
        # 使用正弦波模拟震荡走势
        base_price = 100 + 10 * math.sin(i / 10)
        volatility = 2 * math.sin(i / 3)  # 波动性
        
        open_price = base_price + volatility
        high_price = open_price + abs(volatility) * 0.5 + 0.5
        low_price = open_price - abs(volatility) * 0.5 - 0.5
        
        # 收盘价随机波动
        if i % 3 == 0:
            close_price = high_price - 0.2
        elif i % 3 == 1:
            close_price = low_price + 0.2
        else:
            close_price = (high_price + low_price) / 2
        
        data.append({
            "date": time,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": 1000.0 + i * 10
        })
    
    return pd.DataFrame(data)


def test_simple_icl():
    """测试 SimpleICL 基本功能"""
    print("=" * 60)
    print("测试 1: SimpleICL 基本功能")
    print("=" * 60)
    
    # 创建测试数据
    df = create_test_data(200)
    
    # 初始化SimpleICL
    icl = SimpleICL(code="BTC/USDT", frequency="1m", config={})
    
    # 处理K线数据
    icl.process_klines(df)
    
    # 获取笔列表
    bis = icl.get_bis()
    print(f"\n✓ 生成笔数量: {len(bis)}")
    if bis:
        print(f"✓ 第一笔: {bis[0]}")
        print(f"\n第一笔属性检查:")
        print(f"  - index: {bis[0].index}")
        print(f"  - type: {bis[0].type}")
        print(f"  - start_time: {bis[0].start_time}")
        print(f"  - end_time: {bis[0].end_time}")
        print(f"  - start_price: {bis[0].start_price:.2f}")
        print(f"  - end_price: {bis[0].end_price:.2f}")
        print(f"  - high: {bis[0].high:.2f}")
        print(f"  - low: {bis[0].low:.2f}")
        print(f"  - has start: {hasattr(bis[0], 'start')}")
        print(f"  - has end: {hasattr(bis[0], 'end')}")
        print(f"  - mmds 数量: {len(bis[0].mmds)}")
        print(f"  - bcs 数量: {len(bis[0].bcs)}")
        
        # 检查买卖点
        if bis[0].mmds:
            print(f"\n第一笔的买卖点:")
            for mmd in bis[0].mmds:
                print(f"  - {mmd}")
        
        # 检查背驰
        if bis[0].bcs:
            print(f"\n第一笔的背驰:")
            for bc in bis[0].bcs:
                print(f"  - {bc}")
    
    # 获取线段列表
    xds = icl.get_xds()
    print(f"\n✓ 生成线段数量: {len(xds)}")
    if xds:
        print(f"✓ 第一段: {xds[0]}")
    
    # 获取中枢列表
    bi_zss = icl.get_bi_zss()
    print(f"\n✓ 生成笔中枢数量: {len(bi_zss)}")
    if bi_zss:
        print(f"✓ 第一个笔中枢: {bi_zss[0]}")
        print(f"\n第一个笔中枢属性检查:")
        print(f"  - index: {bi_zss[0].index}")
        print(f"  - zs_type: {bi_zss[0].zs_type}")
        print(f"  - type: {bi_zss[0].type}")
        print(f"  - zg: {bi_zss[0].zg:.2f}")
        print(f"  - zd: {bi_zss[0].zd:.2f}")
        print(f"  - gg: {bi_zss[0].gg:.2f}")
        print(f"  - dd: {bi_zss[0].dd:.2f}")
        print(f"  - level: {bi_zss[0].level}")
        print(f"  - done: {bi_zss[0].done}")
        print(f"  - real: {bi_zss[0].real}")
    
    return icl


def test_json_conversion(icl):
    """测试 JSON 转换功能"""
    print("\n" + "=" * 60)
    print("测试 2: JSON 转换功能")
    print("=" * 60)
    
    # 转换为JSON
    json_result = icl_to_standard_json(icl)
    
    print(f"\n✓ JSON转换成功:")
    print(f"  - bi数量: {len(json_result['bi'])}")
    print(f"  - xd数量: {len(json_result['xd'])}")
    print(f"  - zs数量: {len(json_result['zs'])}")
    print(f"  - bc数量: {len(json_result['bc'])}")
    print(f"  - signal数量: {len(json_result['signal'])}")
    
    # 检查笔的JSON结构
    if json_result['bi']:
        print(f"\n第一笔JSON结构:")
        for key, value in json_result['bi'][0].items():
            if isinstance(value, (list, dict)):
                print(f"  - {key}: {value}")
            else:
                print(f"  - {key}: {value}")
    
    # 检查中枢的JSON结构
    if json_result['zs']:
        print(f"\n第一个中枢JSON结构:")
        for key, value in json_result['zs'][0].items():
            print(f"  - {key}: {value}")
    
    # 检查买卖点的JSON结构
    if json_result['signal']:
        print(f"\n第一个买卖点JSON结构:")
        for key, value in json_result['signal'][0].items():
            print(f"  - {key}: {value}")
    
    # 检查背驰的JSON结构
    if json_result['bc']:
        print(f"\n第一个背驰JSON结构:")
        for key, value in json_result['bc'][0].items():
            print(f"  - {key}: {value}")
    
    return json_result


def test_chanlun_engine():
    """测试 ChanlunEngine"""
    print("\n" + "=" * 60)
    print("测试 3: ChanlunEngine 集成测试")
    print("=" * 60)
    
    # 创建测试K线数据
    klines = []
    base_time = datetime.now() - timedelta(hours=100)
    
    for i in range(100):
        time = base_time + timedelta(minutes=i)
        klines.append(KlineInput(
            date=time,
            open=100 + i * 0.1,
            high=100 + i * 0.1 + 0.5,
            low=100 + i * 0.1 - 0.5,
            close=100 + i * 0.1 + 0.2,
            volume=1000.0
        ))
    
    # 初始化引擎
    engine_cfg = EngineConfig(
        options={},
        bi_min_kline=5,
        xd_min_bi=3,
        zs_min_bi=3
    )
    engine = ChanlunEngine(engine_cfg)
    
    # 分析K线
    icl = engine.analyze_klines(
        code="BTC/USDT",
        frequency="1m",
        klines=klines
    )
    
    print(f"\n✓ 引擎分析完成:")
    print(f"  - 笔数量: {len(icl.get_bis())}")
    print(f"  - 线段数量: {len(icl.get_xds())}")
    print(f"  - 笔中枢数量: {len(icl.get_bi_zss())}")
    print(f"  - 线段中枢数量: {len(icl.get_xd_zss())}")
    
    # 统计买卖点
    total_mmds = 0
    for bi in icl.get_bis():
        total_mmds += len(bi.mmds)
    for xd in icl.get_xds():
        total_mmds += len(xd.mmds)
    print(f"  - 买卖点总数: {total_mmds}")
    
    # 统计背驰
    total_bcs = 0
    for bi in icl.get_bis():
        total_bcs += len(bi.bcs)
    for xd in icl.get_xds():
        total_bcs += len(xd.bcs)
    print(f"  - 背驰总数: {total_bcs}")
    
    return icl


def main():
    """主测试流程"""
    print("\n" + "🚀 " * 20)
    print("SimpleICL 与 Mapper 兼容性测试")
    print("🚀 " * 20 + "\n")
    
    try:
        # 测试1: SimpleICL基本功能
        icl1 = test_simple_icl()
        
        # 测试2: JSON转换功能
        json_result = test_json_conversion(icl1)
        
        # 测试3: ChanlunEngine集成测试
        icl2 = test_chanlun_engine()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
