"""测试高级缠论功能：背驰识别和买卖点"""
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chanlun_local.engine import SimpleICL
from chanlun_local.mapper import icl_to_standard_json


def create_divergence_test_data(count: int = 300):
    """生成专门用于测试背驰的K线数据"""
    import math
    data = []
    base_time = datetime.now() - timedelta(hours=count)
    
    for i in range(count):
        time = base_time + timedelta(minutes=i)
        
        # 第一波：强势上涨
        if i < 100:
            base_price = 100 + i * 0.5
            volatility = 1.0
        # 第二波：弱势上涨（背驰）
        elif i < 200:
            base_price = 150 + (i - 100) * 0.2
            volatility = 0.5
        # 第三波：震荡下跌
        else:
            base_price = 170 - (i - 200) * 0.3
            volatility = 0.8
        
        # 添加震荡
        oscillation = 3 * math.sin(i / 5)
        
        open_price = base_price + oscillation
        high_price = open_price + volatility + 0.5
        low_price = open_price - volatility - 0.5
        
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


def test_divergence_detection():
    """测试背驰识别功能"""
    print("=" * 60)
    print("测试 1: 背驰识别功能")
    print("=" * 60)
    
    # 创建测试数据
    df = create_divergence_test_data(300)
    
    # 初始化SimpleICL
    icl = SimpleICL(code="BTC/USDT", frequency="1m", config={
        'bi_min_kline': 5,
        'xd_min_bi': 3,
        'zs_min_bi': 3
    })
    
    # 处理K线数据
    icl.process_klines(df)
    
    # 统计结果
    bis = icl.get_bis()
    xds = icl.get_xds()
    bi_zss = icl.get_bi_zss()
    xd_zss = icl.get_xd_zss()
    
    print(f"\n✓ 生成笔数量: {len(bis)}")
    print(f"✓ 生成线段数量: {len(xds)}")
    print(f"✓ 生成笔中枢数量: {len(bi_zss)}")
    print(f"✓ 生成线段中枢数量: {len(xd_zss)}")
    
    # 统计买卖点
    total_mmds = 0
    mmd_types = {}
    for bi in bis:
        for mmd in bi.mmds:
            total_mmds += 1
            mmd_types[mmd.name] = mmd_types.get(mmd.name, 0) + 1
    for xd in xds:
        for mmd in xd.mmds:
            total_mmds += 1
            mmd_types[mmd.name] = mmd_types.get(mmd.name, 0) + 1
    
    print(f"\n✓ 买卖点总数: {total_mmds}")
    if mmd_types:
        print("  买卖点分布:")
        for mmd_name, count in sorted(mmd_types.items()):
            print(f"    - {mmd_name}: {count}")
    
    # 统计背驰
    total_bcs = 0
    bc_types = {}
    for bi in bis:
        for bc in bi.bcs:
            if bc.bc:
                total_bcs += 1
                bc_types[bc.type] = bc_types.get(bc.type, 0) + 1
    for xd in xds:
        for bc in xd.bcs:
            if bc.bc:
                total_bcs += 1
                bc_types[bc.type] = bc_types.get(bc.type, 0) + 1
    
    print(f"\n✓ 背驰总数: {total_bcs}")
    if bc_types:
        print("  背驰分布:")
        for bc_type, count in sorted(bc_types.items()):
            print(f"    - {bc_type}: {count}")
    
    # 展示前几个买卖点的详细信息
    print("\n买卖点详细信息:")
    shown = 0
    for i, bi in enumerate(bis):
        if bi.mmds and shown < 3:
            for mmd in bi.mmds:
                print(f"  笔 {i}: {mmd.name} - {mmd.msg}")
                if mmd.zs:
                    print(f"    关联中枢: index={mmd.zs.index}, zg={mmd.zs.zg:.2f}, zd={mmd.zs.zd:.2f}")
                shown += 1
    
    # 展示中枢详细信息
    if bi_zss:
        print("\n笔中枢详细信息:")
        for i, zs in enumerate(bi_zss[:3]):
            print(f"  中枢 {i}:")
            print(f"    - type: {zs.type}")
            print(f"    - zg (中枢高点): {zs.zg:.2f}")
            print(f"    - zd (中枢低点): {zs.zd:.2f}")
            print(f"    - gg (高高点): {zs.gg:.2f}")
            print(f"    - dd (低低点): {zs.dd:.2f}")
            print(f"    - 中枢区间: [{zs.zd:.2f}, {zs.zg:.2f}]")
    
    return icl


def test_json_output(icl):
    """测试JSON输出"""
    print("\n" + "=" * 60)
    print("测试 2: JSON 输出验证")
    print("=" * 60)
    
    json_result = icl_to_standard_json(icl)
    
    print(f"\n✓ JSON转换成功:")
    print(f"  - bi数量: {len(json_result['bi'])}")
    print(f"  - xd数量: {len(json_result['xd'])}")
    print(f"  - zs数量: {len(json_result['zs'])}")
    print(f"  - bc数量: {len(json_result['bc'])}")
    print(f"  - signal数量: {len(json_result['signal'])}")
    
    # 验证买卖点JSON
    if json_result['signal']:
        print("\n买卖点JSON示例:")
        for signal in json_result['signal'][:3]:
            print(f"  - {signal['name']}: {signal['msg']}")
            if signal['zs_type']:
                print(f"    中枢类型: {signal['zs_type']}, 中枢索引: {signal['zs_index']}")
    
    # 验证背驰JSON
    if json_result['bc']:
        print("\n背驰JSON示例:")
        for bc in json_result['bc'][:3]:
            print(f"  - {bc['type']}: is_bc={bc['is_bc']}")
            if bc['zs_type']:
                print(f"    中枢类型: {bc['zs_type']}, 中枢索引: {bc['zs_index']}")
    
    # 验证中枢JSON
    if json_result['zs']:
        print("\n中枢JSON示例:")
        for zs in json_result['zs'][:2]:
            print(f"  - 中枢 {zs['index']}:")
            print(f"    type: {zs['type']}, zs_type: {zs['zs_type']}")
            print(f"    zg: {zs['zg']:.2f}, zd: {zs['zd']:.2f}")
            print(f"    gg: {zs['gg']:.2f}, dd: {zs['dd']:.2f}")


def main():
    """主测试流程"""
    print("\n" + "🎯 " * 20)
    print("高级缠论功能测试：背驰识别与买卖点")
    print("🎯 " * 20 + "\n")
    
    try:
        # 测试1: 背驰识别
        icl = test_divergence_detection()
        
        # 测试2: JSON输出
        test_json_output(icl)
        
        print("\n" + "=" * 60)
        print("✅ 所有高级功能测试通过！")
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
