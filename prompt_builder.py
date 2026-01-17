"""Prompt 构造器

本模块的职责：
- 根据 AI JSON 构造完整的 Prompt
- 使用专门针对缠论分析的提示词模板
- 强制 AI 输出结构化 JSON，不是自由文本
- 支持 A2.5 统计提示注入
- 包含缠论术语解释和结构摘要
"""
import json
from typing import Dict, Any
from ai_output_schema import get_schema_template
from stat_hint import get_stat_hint


def _format_strength_comparison(comparison: str) -> str:
    """格式化力度对比描述"""
    mapping = {
        "weakening": "力度减弱（可能背驰）",
        "strengthening": "力度增强（趋势延续）",
        "similar": "力度相当",
        "unknown": "无法判断",
    }
    return mapping.get(comparison, "未知")


# 缠论术语解释模板
TERMINOLOGY_BLOCK = """
【缠论核心术语解释】
1. **笔（Bi）**：由相邻的顶分型和底分型连接形成，是最小的趋势单位
2. **线段（XD）**：由至少3笔组成，当特征序列出现反向分型时线段结束
3. **中枢（ZhongShu/ZS）**：至少3笔重叠的价格区间
   - ZG：中枢高点（三笔重叠区间的上边界）
   - ZD：中枢低点（三笔重叠区间的下边界）
   - GG：中枢内所有笔的最高点
   - DD：中枢内所有笔的最低点
4. **买卖点**：
   - 1buy（一类买点）：下跌趋势背驰后的低点
   - 2buy（二类买点）：一买后回调不破低点
   - 3buy（三类买点）：中枢震荡后向上突破回踩不进中枢
   - 1sell/2sell/3sell：对应的卖点
5. **背驰（BC）**：走势延续但力度减弱，预示趋势可能反转
6. **力度（Strength）**：衡量笔的强弱，力度减弱（weakening）提示背驰可能
"""


def build_structured_prompt(ai_json: Dict[str, Any], stats_context: str = "") -> str:
    """构造结构化输出 Prompt（强制 JSON 输出，含 A2.5 统计提示 + 历史表现）
    
    参数：
    - ai_json: 符合规范的 AI 输入 JSON
    - stats_context: 历史统计上下文（可选）
    
    返回：
    - 强制约束的 Prompt 字符串
    """
    
    json_str = json.dumps(ai_json, ensure_ascii=False, indent=2)
    schema = get_schema_template()
    
    meta = ai_json.get("meta", {})
    market = ai_json.get("market", {})
    symbol = meta.get("symbol", "Unknown")
    interval = meta.get("interval", "Unknown")
    latest_price = float(market.get("latest_price", 0.0))
    
    # 获取结构摘要（新增）
    structure_summary = ai_json.get("structure_summary", {})
    trend_desc = structure_summary.get("trend_description", "未知")
    position_desc = structure_summary.get("position_description", "未知")
    key_levels = structure_summary.get("key_levels", {})
    strength_comparison = structure_summary.get("strength_comparison", "unknown")
    price_position = structure_summary.get("price_position", "unknown")
    
    # 计算当前结构是否在中枢内
    in_zs = price_position == "inside_zs"
    
    # === A2.5 统计提示 ===
    stat = get_stat_hint(symbol=symbol, interval=interval, in_zs=in_zs)
    win_rate_str = (
        f"{stat['win_rate']}" if stat.get("win_rate") is not None else "N/A"
    )
    pos_label = "中枢内" if in_zs else "中枢外"
    
    stat_block = f"""
【统计提示 A2.5｜仅供参考】
交易对：{symbol}，周期：{interval}，结构位置：{pos_label}
样本数量：{stat["sample"]}
历史胜率：{win_rate_str}
结论：{stat["hint"]}
"""
    
    # === 当前结构摘要（新增） ===
    summary_block = f"""
【当前结构摘要】
- 交易对：{symbol}，周期：{interval}
- 当前价格：{latest_price:.2f}
- 趋势判断：{trend_desc}
- 价格位置：{position_desc}
- 力度对比：{_format_strength_comparison(strength_comparison)}
- 中枢区间：ZG={key_levels.get('zg', 0):.0f}, ZD={key_levels.get('zd', 0):.0f}
- 中枢波动：GG={key_levels.get('gg', 0):.0f}, DD={key_levels.get('dd', 0):.0f}
"""
    
    # === 系统约束（强约束） ===
    system_block = """
【系统约束】
你是一个【缠论结构分析引擎】，不是聊天机器人。
你只能基于给定的缠论结构 JSON 进行分析。
【统计提示】仅用于背景参考，不得作为结论依据，不得反向推理。
【历史表现】可用于调整预测策略，但不得复述原文。

【严禁事项】
- 禁止使用技术指标（均线、MACD、RSI 等）
- 禁止引入外部行情、消息、情绪
- 禁止超出提供数据进行推断
- 禁止输出 Schema 之外的字段

【分析重点】
1. 基于中枢位置判断多空优势
2. 基于力度对比判断背驰可能
3. 基于买卖点信号确定操作方向
4. 给出具体的价格点位（入场/止损/目标）
"""
    
    # === 历史表现上下文（可选） ===
    history_block = ""
    if stats_context:
        history_block = stats_context + "\n"
    
    # === 缠论结构 JSON ===
    structure_block = f"""
【缠论结构 JSON】
{json_str}
"""
    
    # === 输出格式约束（含 JSON Schema） ===
    output_block = f"""
【输出格式约束】
1. 必须输出一个合法 JSON，严格符合下方 JSON Schema。
2. 不得复述或引用【统计提示】中的任何数字或文字。
3. 不得使用“因为历史胜率…”等基于统计的表述。
4. 字段名、层级、类型必须完全一致；数值使用 number，概率 0~1。
5. 不允许出现 markdown 代码块标记，不允许多余文本。
6. scenarios 的概率总和应不超过 1.05。
7. primary_scenario 必须填写，作为最主要场景，字段含义如下：
   - direction: "up" 或 "down"（不能是 "range"）
   - target_pct: 目标涨跌幅（正数，如 5.0 表示 5%）
     * 1h周期：建议 1.5-3.0%（BTC）、2.0-4.0%（ETH）
     * 4h周期：建议 3.0-6.0%（BTC）、4.0-8.0%（ETH）
     * 1d周期：建议 5.0-10.0%（BTC）、6.0-12.0%（ETH）
   - stop_pct: 止损幅度（正数，如 2.0 表示 2%）
     * 建议为 target_pct 的 40-60%
   - probability: 0~1 之间
   - trigger: 触发条件（使用缠论术语，如"突破中枢ZG"、"回踩不破ZD"）
   - reasoning: 逻辑推导（说明基于哪些缠论结构得出结论）
8. analysis 字段（必须填写）：
   - 3-5 段话的完整文字分析
   - 给交易者看的市场解读和操作策略
   - 必须包含以下内容：
     a) 当前结构判断（笔、线段、中枢状态，力度对比）
     b) 可能走势分析（2-3种场景）
     c) 关键价位（支撑位、阻力位、中枢区间 ZG/ZD/GG/DD）
     d) **做多策略（概率 XX%）**：入场点位、目标位、止损位（如果适合做多）
     e) **做空策略（概率 XX%）**：入场点位、目标位、止损位（如果适合做空）
     f) **震荡策略（概率 XX%）**：价格区间、高抛低吸点位（如果是震荡）
   - 概率应与 scenarios 中对应方向的概率一致
   - 使用缠论术语，通俗易懂，给出具体价格

【JSON Schema】
```json
{schema}
```

请直接输出符合 Schema 的 JSON，不要有任何其他内容：
"""
    
    return TERMINOLOGY_BLOCK + "\n" + system_block + "\n" + history_block + summary_block + "\n" + stat_block + "\n" + structure_block + "\n" + output_block


def build_prompt(ai_json: Dict[str, Any]) -> str:
    """构造 AI 分析 Prompt
    
    参数：
    - ai_json: 符合规范的 AI 输入 JSON
    
    返回：
    - 完整的 Prompt 字符串
    """
    
    json_str = json.dumps(ai_json, ensure_ascii=False, indent=2)
    
    return f"""你是一名精通缠论的数字货币交易分析师。

请根据以下【结构化缠论数据】，对后续走势进行判断。

【输出要求】
1. **当前市场结构判断**（1-2 段话，说明当前笔/线段/中枢状态）
2. **未来 2~3 种可能走势**（按概率排序，标注概率百分比）
3. **关键价格区间**（支撑位、阻力位、中枢区间）
4. **操作思路**（仅基于缠论结构逻辑，不做投资建议）

【严格规则】
- ❌ 禁止使用：均线、MACD、KDJ、RSI 等技术指标
- ❌ 禁止使用：消息面、情绪、舆论等非缠论因素
- ✅ 只能使用：笔、线段、中枢、买卖点、背驰、级别
- ✅ 输出格式：简洁、清晰、可直接给交易者看的分析文字
- ✅ 语言：中文

【缠论结构数据】
```json
{json_str}
```

请开始你的分析："""


def build_simple_prompt(ai_json: Dict[str, Any]) -> str:
    """构造简化版 Prompt（用于快速分析）
    
    参数：
    - ai_json: 符合规范的 AI 输入 JSON
    
    返回：
    - 简化的 Prompt 字符串（要求输出更简洁）
    """
    
    # 提取关键信息
    meta = ai_json.get("meta", {})
    market = ai_json.get("market", {})
    signal = ai_json.get("signal", {})
    centers = ai_json.get("center", [])
    
    # 构造简化的上下文
    context = f"""交易对: {meta.get('symbol', 'Unknown')}
周期: {meta.get('interval', 'Unknown')}
当前价格: {market.get('latest_price', 0)}
笔数量: {meta.get('data_size', {}).get('bi', 0)}
线段数量: {meta.get('data_size', {}).get('segment', 0)}
中枢数量: {len(centers)}
买卖点: {', '.join(signal.get('buy_sell_points', [])) or '无'}
背驰: {', '.join(signal.get('divergences', [])) or '无'}
"""
    
    json_str = json.dumps(ai_json, ensure_ascii=False, indent=2)
    
    return f"""作为缠论专家，基于以下数据做出简洁判断：

{context}

【要求】
- 用 3-5 句话总结当前结构状态
- 给出 2-3 种可能走势及概率
- 标注关键价格位
- 仅用缠论语言，不用指标

【完整数据】
```json
{json_str}
```

请简洁分析："""


def build_table_format_prompt(ai_json: Dict[str, Any]) -> str:
    """构造表格格式的缠论分析 Prompt（输出 Markdown）
    
    这个 Prompt 专门用于处理包含表格数据的输入，
    要求 AI 输出结构化的 Markdown 分析报告。
    
    参数：
    - ai_json: 符合规范的 AI 输入 JSON
    
    返回：
    - Markdown 格式的 Prompt
    """
    
    meta = ai_json.get("meta", {})
    market = ai_json.get("market", {})
    bi_list = ai_json.get("bi", [])
    segment_list = ai_json.get("segment", [])
    centers = ai_json.get("center", [])
    signals = ai_json.get("signal", {})
    
    # 构造表格数据
    bi_table = "起始时间\t结束时间\t方向\t起始值\t完成状态\t买点\t背驰\n"
    for bi in bi_list[-9:]:  # 只取最后9条
        start_time = bi.get('start_time', '').split('T')[0] + ' ' + bi.get('start_time', '').split('T')[1][:8] if 'T' in bi.get('start_time', '') else bi.get('start_time', '')
        end_time = bi.get('end_time', '').split('T')[0] + ' ' + bi.get('end_time', '').split('T')[1][:8] if 'T' in bi.get('end_time', '') else bi.get('end_time', '')
        direction = "向上" if bi.get('direction') == 'up' else "向下"
        price_range = f"{bi.get('start_price', 0):.2f} - {bi.get('end_price', 0):.2f}"
        is_done = "True" if bi.get('is_done') else "False"
        buy_sell = bi.get('buy_sell_point', '') or ''
        divergence = bi.get('divergence', '') or ''
        
        bi_table += f"{start_time}\t{end_time}\t{direction}\t{price_range}\t{is_done}\t{buy_sell}\t{divergence}\n"
    
    segment_table = "起始时间\t结束时间\t方向\t起始值\t完成状态\t买点\t背驰\n"
    for seg in segment_list[-3:]:  # 只取最后3条
        start_time = seg.get('start_time', '').split('T')[0] + ' ' + seg.get('start_time', '').split('T')[1][:8] if 'T' in seg.get('start_time', '') else seg.get('start_time', '')
        end_time = seg.get('end_time', '').split('T')[0] + ' ' + seg.get('end_time', '').split('T')[1][:8] if 'T' in seg.get('end_time', '') else seg.get('end_time', '')
        direction = "向上" if seg.get('direction') == 'up' else "向下"
        price_range = f"{seg.get('start_price', 0):.2f} - {seg.get('end_price', 0):.2f}"
        is_done = "True" if seg.get('is_done') else "False"
        buy_sell = seg.get('buy_sell_point', '') or ''
        divergence = seg.get('divergence', '') or ''
        
        segment_table += f"{start_time}\t{end_time}\t{direction}\t{price_range}\t{is_done}\t{buy_sell}\t{divergence}\n"
    
    # 中枢表格
    center_table = "起始时间\t结束时间\t类型\t最高值\t最低值\t级别\t关系\n"
    for zs in centers[-2:]:  # 只取最后2个
        start_time = zs.get('start_time', '').split('T')[0] + ' ' + zs.get('start_time', '').split('T')[1][:8] if 'T' in zs.get('start_time', '') else zs.get('start_time', '')
        end_time = zs.get('end_time', '').split('T')[0] + ' ' + zs.get('end_time', '').split('T')[1][:8] if 'T' in zs.get('end_time', '') else zs.get('end_time', '')
        zs_type = "笔中枢" if zs.get('type') == 'bi' else "线段中枢"
        high = f"{zs.get('high', 0):.2f}"
        low = f"{zs.get('low', 0):.2f}"
        level = zs.get('level', 1)
        relation = zs.get('relation', 'unknown')
        
        center_table += f"{start_time}\t{end_time}\t{zs_type}\t{high}\t{low}\t{level}\t{relation}\n"
    
    return f"""# 缠论技术分析：{meta.get('symbol', 'Unknown')} 走势分析

请根据以下缠论数据，分析后续可能走势，并按照**标准格式**输出。

---

## 输入数据

### 当前品种
- **代码/名称**：{meta.get('symbol', 'Unknown')}
- **数据周期**：{meta.get('interval', 'Unknown')}
- **当前时间**：{meta.get('timestamp', '')}
- **最新价格**：{market.get('latest_price', 0):.2f}

### 最新的 9 条缠论笔数据
{bi_table}

### 最新的 3 条缠论线段数据
{segment_table}

### 中枢信息
**最新两个中枢的位置关系**：{centers[-1].get('relation', 'unknown') if centers else '无'}

{center_table}

**数据说明**：中枢级别的意思，1表示是本级别，根据中枢内的线段数量计算，小于等于9表示本级别，大于1表示中枢内的线段大于9，中枢级别升级。

---

## 输出要求

请严格按照以下格式输出 Markdown 分析报告：

### 一、技术形态概述
根据提供的缠论数据，对 {meta.get('symbol', 'Unknown')} {meta.get('interval', 'Unknown')} 周期的走势进行分析如下：

### 二、当前市场状态
- 最新价格：[具体价格]
- 处于什么级别的中枢内/外
- 中枢范围变化情况
- 最后一笔的状态（向上/向下，是否完成）

### 三、关键技术信号
- 买卖点信号：{', '.join(signals.get('buy_sell_points', [])) or '无'}
- 背驰信号：{', '.join(signals.get('divergences', [])) or '无'}
- 中枢关系：[中枢的扩展/收缩/移动情况]

### 四、可能走势分析（概率排序）

#### 走势一：[走势描述]（概率：X%）
**技术依据**：
- [依据1]
- [依据2]
- [依据3]

**预期走势**：
- [短期预期]
- [目标位置]
- [关键价格位]

#### 走势二：[走势描述]（概率：Y%）
**技术依据**：
- [依据1]
- [依据2]

**预期走势**：
- [短期预期]
- [目标位置]
- [触发条件]

#### 走势三：[走势描述]（概率：Z%）
**技术依据**：
- [依据1]
- [依据2]

**预期走势**：
- [横盘/震荡预期]
- [价格区间]

### 五、操作建议

**多头策略**：
- 介入点位：[具体价格]
- 止损位：[具体价格]
- 目标位：[价格区间]

**空头策略**：
- 介入点位：[具体价格]
- 止损位：[具体价格]
- 目标位：[价格区间]

**震荡策略**：
- 上沿做空：[具体价格]
- 下沿做多：[具体价格]
- 止损止盈设置：[建议]

### 六、风险提示
- [风险因素1]
- [风险因素2]
- [风险因素3]
- 请结合其他分析工具和市场消息综合判断，不建议单纯依据本分析进行交易决策。

---

**严格约束**：
- ❌ 禁止使用技术指标（均线、MACD、RSI、KDJ等）
- ❌ 禁止引入外部消息、舆论、情绪分析
- ❌ 禁止超出提供数据进行推断
- ✅ 只能基于提供的缠论结构数据（笔、线段、中枢、买卖点、背驰）
- ✅ 使用缠论专业术语和逻辑
- ✅ 输出格式必须完全符合上述结构
- ✅ 概率总和应为 100%

请严格按照上述格式输出分析报告：
"""


def build_structured_table_prompt(ai_json: Dict[str, Any]) -> str:
    """构造表格格式 + 结构化 JSON 输出的 Prompt
    
    这个 Prompt 要求 AI 根据表格数据输出结构化 JSON
    
    参数：
    - ai_json: 符合规范的 AI 输入 JSON
    
    返回：
    - 强制 JSON 输出的 Prompt
    """
    
    # 重用表格格式构建逻辑
    table_content = build_table_format_prompt(ai_json)
    schema = get_schema_template()
    
    return f"""{table_content}

---

## 输出要求

你是一个【缠论结构分析引擎】，不是聊天机器人。

**严格按照以下 JSON Schema 输出，不允许有任何额外文字：**

```json
{schema}
```

请直接输出符合 Schema 的 JSON，不要有任何其他内容：
"""


def build_multi_level_prompt(multi_level_data: Dict[str, Any]) -> str:
    """构造多级别联立分析 Prompt
    
    参数：
    - multi_level_data: 多级别分析数据，包含 large/medium/small 三个级别
    
    返回：
    - 多级别分析的结构化 Prompt
    """
    
    schema = get_schema_template()
    symbol = multi_level_data.get("symbol", "Unknown")
    latest_price = multi_level_data.get("latest_price", 0)
    levels = multi_level_data.get("levels", {})
    
    # 提取各级别摘要
    large = levels.get("large", {})
    medium = levels.get("medium", {})
    small = levels.get("small", {})
    
    large_summary = large.get("summary", {})
    medium_summary = medium.get("summary", {})
    small_summary = small.get("summary", {})
    
    # 构造级别摘要表格
    def format_level_summary(name: str, interval: str, summary: Dict) -> str:
        trend = summary.get("trend", "unknown")
        trend_map = {"up_trend": "上升趋势", "down_trend": "下降趋势", "consolidation": "震荡盘整", "unknown": "未知"}
        pos = summary.get("price_vs_zs", "unknown")
        pos_map = {"above": "中枢上方", "below": "中枢下方", "inside": "中枢内部", "unknown": "无中枢"}
        
        zs_info = ""
        if summary.get("latest_zs"):
            zs = summary["latest_zs"]
            zs_info = f"ZG={zs['zg']:.0f}, ZD={zs['zd']:.0f}"
        
        signals = ", ".join(summary.get("recent_mmds", [])) or "无"
        
        return f"""### {name} ({interval})
- 趋势: {trend_map.get(trend, trend)}
- 价格位置: {pos_map.get(pos, pos)}
- 中枢: {zs_info or '无'}
- 买卖点信号: {signals}
- 笔数量: {summary.get('bi_count', 0)}, 线段数量: {summary.get('xd_count', 0)}, 中枢数量: {summary.get('zs_count', 0)}
"""
    
    large_text = format_level_summary(large.get("name", "大级别"), large.get("interval", "4h"), large_summary)
    medium_text = format_level_summary(medium.get("name", "中级别"), medium.get("interval", "1h"), medium_summary)
    small_text = format_level_summary(small.get("name", "小级别"), small.get("interval", "15m"), small_summary)
    
    # 详细数据（中级别的完整 JSON）
    medium_json = json.dumps(medium.get("ai_json", {}), ensure_ascii=False, indent=2)
    
    return f"""# 缠论多级别联立分析

你是一名精通缠论的数字货币交易分析师。请根据以下【多级别缠论数据】进行综合分析。

{TERMINOLOGY_BLOCK}

## 多级别分析核心原则

1. **大级别定方向**：大级别趋势决定主要操作方向
2. **中级别找买卖点**：中级别结构确定买卖点位置
3. **小级别精入场**：小级别结构确定精确入场时机

## 当前品种
- **交易对**: {symbol}
- **当前价格**: {latest_price:.2f}

---

## 多级别结构摘要

{large_text}
{medium_text}
{small_text}

---

## 中级别详细数据

```json
{medium_json}
```

---

## 输出要求

【系统约束】
你是一个【缠论多级别联立分析引擎】。
必须综合三个级别的结构进行分析，不能只看单一级别。

【分析重点】
1. 三级别趋势是否一致？（一致性越高，信号越可靠）
2. 大级别处于什么位置？（决定操作方向）
3. 中级别有无买卖点？（确定交易信号）
4. 小级别是否可以入场？（确定入场时机）

【严禁事项】
- 禁止使用技术指标（均线、MACD、RSI 等）
- 禁止引入外部行情、消息、情绪
- 禁止只分析单一级别

【输出格式】
严格按照以下 JSON Schema 输出：

```json
{schema}
```

【特殊要求】
1. analysis 字段必须包含多级别联立分析内容：
   - 大级别趋势判断
   - 中级别买卖点分析
   - 小级别入场时机
   - 三级别一致性评估
2. primary_scenario 的 reasoning 必须说明多级别配合关系
3. 概率评估需要考虑多级别趋势一致性

请直接输出符合 Schema 的 JSON：
"""
