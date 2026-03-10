"""Prompt 构造器

本模块的职责：
- 根据 AI JSON 构造完整的 Prompt
- 使用专门针对缠论分析的提示词模板
- 强制 AI 输出结构化 JSON，不是自由文本
- 支持 A2.5 统计提示注入
- 包含缠论术语解释和结构摘要
"""
import json
import os
from typing import Dict, Any, Optional
from ai_output_schema import get_schema_template
from stat_hint import get_stat_hint


# ============================================
# Token 管理机制（新增）
# ============================================

# Token 配置（从环境变量读取，默认2800）
MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "2800"))
SAFE_TOKENS = MAX_TOKENS - 200  # 保留200 tokens buffer

# 内容优先级配置
CONTENT_PRIORITY = {
    "critical": [  # 必需内容，不可裁剪
        "system_block",      # 系统约束
        "structure_block",   # 缠论结构数据
        "output_block",      # 输出格式约束
    ],
    "important": [  # 重要内容，优先保留
        "summary_block",    # 当前结构摘要
        "stat_block",       # 统计提示
    ],
    "optional": [  # 可选内容，可裁剪
        "TERMINOLOGY_BLOCK", # 术语解释（较长）
        "learning_block",   # AI自我认知
        "history_block",    # 历史统计
        "similar_cases_block", # 相似案例
    ]
}


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量（粗略估算：中文≈0.7 token/字，英文≈0.25 token/字）"""
    import re
    # 统计中文字符
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 统计非中文字符
    non_chinese = len(text) - chinese_chars
    # 粗略估算
    return int(chinese_chars * 0.7 + non_chinese * 0.25)


def build_prompt_with_token_management(
    blocks: Dict[str, str],
    max_tokens: int = SAFE_TOKENS
) -> str:
    """根据 token 限制构建 Prompt

    参数：
    - blocks: 各个内容块的字典 {block_name: content}
    - max_tokens: 最大 token 数量

    返回：
    - 组装后的 Prompt
    """
    # 按优先级组装
    prompt_parts = []
    current_tokens = 0

    # 1. 添加必需内容
    for block_name in CONTENT_PRIORITY["critical"]:
        if block_name in blocks and blocks[block_name]:
            prompt_parts.append(blocks[block_name])
            current_tokens += estimate_tokens(blocks[block_name])

    # 2. 添加重要内容
    for block_name in CONTENT_PRIORITY["important"]:
        if block_name in blocks and blocks[block_name]:
            tokens = estimate_tokens(blocks[block_name])
            if current_tokens + tokens < max_tokens:
                prompt_parts.append(blocks[block_name])
                current_tokens += tokens

    # 3. 添加可选内容（按需裁剪）
    for block_name in CONTENT_PRIORITY["optional"]:
        if block_name in blocks and blocks[block_name]:
            tokens = estimate_tokens(blocks[block_name])
            if current_tokens + tokens < max_tokens:
                prompt_parts.append(blocks[block_name])
                current_tokens += tokens
            elif current_tokens < max_tokens:
                # 尝试添加裁剪后的版本
                content = blocks[block_name]
                # 裁剪到剩余空间
                remaining_tokens = max_tokens - current_tokens
                ratio = remaining_tokens / tokens
                # 简单裁剪：取前N%的内容
                lines = content.split('\n')
                keep_lines = int(len(lines) * ratio)
                trimmed = '\n'.join(lines[:keep_lines])
                if trimmed:
                    prompt_parts.append(trimmed)
                    current_tokens += estimate_tokens(trimmed)

    return "\n".join(prompt_parts)


def _format_strength_comparison(comparison: str) -> str:
    """格式化力度对比描述"""
    mapping = {
        "weakening": "力度减弱（可能背驰）",
        "strengthening": "力度增强（趋势延续）",
        "similar": "力度相当",
        "unknown": "无法判断",
    }
    return mapping.get(comparison, "未知")


# 缠论术语解释模板（精简版）
TERMINOLOGY_BLOCK = """
【缠论核心术语】
笔（Bi）：顶底分型连接的最小趋势单位
线段（XD）：3笔以上，特征序列反向分型结束
中枢（ZS）：3笔重叠区，ZG/ZD边界，GG/DD极值
买卖点：1buy（背驰低点）、2buy（不破前低）、3buy（突破回踩）
背驰（BC）：力度减弱预示反转
"""


def enhance_learning_feedback(
    learning_feedback: str,
    current_direction: str = None,
    current_signal: str = None,
) -> str:
    """深度化AI自我认知反馈（Step2改进）

    参数：
    - learning_feedback: 原始自我认知文本
    - current_direction: 当前预测方向（up/down/range），用于针对性警告
    - current_signal: 当前信号类型（1buy/2buy等），用于针对性警告

    返回：
    - 分层次、结构化的自我认知文本
    """
    if not learning_feedback:
        return ""

    # 如果反馈已经是结构化的，直接返回
    if "整体表现" in learning_feedback or "分维度表现" in learning_feedback:
        # 根据当前方向/信号添加特定警告
        if current_direction and current_direction in ["up", "down", "range"]:
            dir_name = {"up": "看涨", "down": "看跌", "range": "震荡"}.get(current_direction, current_direction)
            learning_feedback += f"\n  ⚠️ 本次预测方向：{dir_name}"
        if current_signal:
            learning_feedback += f"\n  ⚠️ 本次信号类型：{current_signal}"
        return learning_feedback

    # 简单增强：添加结构化标题
    lines = []
    lines.append("\n【AI自我认知报告】")
    lines.append("-" * 40)

    # 逐行处理原始反馈
    for line in learning_feedback.split('\n'):
        line = line.strip()
        if not line:
            continue
        lines.append(f"  {line}")

    # 添加当前场景特定警告
    if current_direction and current_direction in ["up", "down", "range"]:
        dir_name = {"up": "看涨", "down": "看跌", "range": "震荡"}.get(current_direction, current_direction)
        lines.append(f"  本次预测方向：{dir_name}")
    if current_signal:
        lines.append(f"  本次信号类型：{current_signal}")

    lines.append("-" * 40)

    return "\n".join(lines)


def build_structured_prompt(
    ai_json: Dict[str, Any],
    stats_context: str = "",
    history_context: str = "",
    learning_feedback: str = "",
) -> str:
    """构造结构化输出 Prompt（强制 JSON 输出，含统计提示 + 历史表现 + 相似案例 + 自我认知）

    参数：
    - ai_json: 符合规范的 AI 输入 JSON
    - stats_context: 历史统计上下文（可选，整体表现）
    - history_context: 相似案例上下文（可选，P0新增）
    - learning_feedback: AI自我认知/学习反馈（可选，Step1新增）

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

    # === 当前结构摘要（新增）===
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

    # === 系统约束（强约束，精简版）===
    system_block = """
【系统约束】
你是一个【缠论结构分析引擎】。
【严禁】使用技术指标、引入外部数据、超出数据推断。
"""

    # === 历史表现上下文（可选）===
    history_block = ""
    if stats_context:
        history_block = stats_context + "\n"

    # === 相似案例上下文（P0新增）===
    similar_cases_block = ""
    if history_context:
        similar_cases_block = history_context + "\n"

    # === AI自我认知（Step2改进：深度化）===
    learning_block = ""
    if learning_feedback:
        learning_block = enhance_learning_feedback(learning_feedback) + "\n"

    # === 缠论结构 JSON ===
    structure_block = f"""
【缠论结构 JSON】
{json_str}
"""

    # === 结构优先级说明（v2.1新增）===
    structure_priority_block = """
【缠论分析核心原则：结构优先】
在进行概率分配时，请严格遵循以下优先级：

1. **中枢关系 > 笔力度**
   - extend 状态：优先判定为震荡（震荡概率应最高，通常≥40%）
   - up_trend/down_trend 状态：优先判定为趋势方向（对应方向概率应最高）
   - new 状态：谨慎判断，分布应更均衡（避免某一方向概率>50%）

2. **价格位置作为辅助判断**
   - 价格在中枢内部（inside_zs）：震荡概率增加
   - 价格在中枢上方（above_zs）：偏多头，但需警惕回落
   - 价格在中枢下方（below_zs）：偏空头，但需警惕反弹

3. **买卖点信号作为加成（不是主判断）**
   - 1类买卖点：对应方向 +10%
   - 2类买卖点：对应方向 +8%
   - 3类买卖点：对应方向 +5%
   注意：买卖点是入场时机，不应改变基于结构的主方向判断

4. **背驰信号预警**
   - 力度背驰：注意可能的反转
   - 但需结合结构判断，不能仅凭背驰改变主方向
   例如：extend 状态下的背驰可能只是震荡中的小反转

5. **错误示例避免**：
   - ❌ 中枢 extend + 价格 below_zs + 向下笔力度增强 → 给做空最高概率
     ✅ 正确：extend 状态优先震荡，震荡概率应最高
   - ❌ 中枢 new 状态 → 给某单一方向 >50% 概率
     ✅ 正确：new 状态应谨慎判断，各方向概率分布更均衡
"""

    # === 输出格式约束（含 JSON Schema，增强版）===
    output_block = f"""
【输出格式】
1. 必须输出符合 Schema 的合法 JSON
2. scenarios 概率总和不超过 1.05
3. primary_scenario.direction 必须是 "up" 或 "down"
4. scenarios 中每个场景的 target_range 必须符合当前价格方向逻辑：
   - 做多(up): target_range 的两个值都应该高于当前价格
   - 做空(down): target_range 的两个值都应该低于当前价格
   - 震荡(range): target_range 必须包含当前价格在区间内
5. scenarios 中每个场景必须包含 entry_range（入场点位区间）：
   - entry_range 是建议的入场价格区间 [低, 高]
   - 做多: entry_range 应在当前价格附近或略下方
   - 做空: entry_range 应在当前价格附近或略上方
   - 震荡: entry_range 应在震荡区间内
6. analysis 字段必须包含（格式化给交易者看）：
   a) 当前结构判断（笔、线段、中枢状态，力度对比）
   b) 可能走势分析（2-3种场景，每种含：方向+概率+触发条件）
   c) 关键价位 ZG/ZD/GG/DD
   d) 【做多策略】（概率 XX%）：入场点位区间、目标、止损
   e) 【做空策略】（概率 XX%）：入场点位区间、目标、止损
   f) 【震荡策略】（概率 XX%）：价格区间、高抛低吸
   注：三种策略概率总和≈100%，与scenarios数组一致

【JSON Schema】
```json
{schema}
```
"""

    # === 使用 Token 管理（新增）===
    blocks = {
        "system_block": system_block,
        "structure_block": structure_block,
        "structure_priority_block": structure_priority_block,
        "output_block": output_block,
        "summary_block": summary_block,
        "stat_block": stat_block,
        "TERMINOLOGY_BLOCK": TERMINOLOGY_BLOCK,
        "learning_block": learning_block,
        "history_block": history_block,
        "similar_cases_block": similar_cases_block,
    }

    # 使用 Token 管理机制组装 Prompt
    return build_prompt_with_token_management(blocks, max_tokens=SAFE_TOKENS)


def build_prompt(
    ai_json: Dict[str, Any],
    stats_context: str = "",
    history_context: str = "",
    learning_feedback: str = "",
) -> str:
    """构造 AI 分析 Prompt（增强版，支持历史上下文注入）
    
    参数：
    - ai_json: 符合规范的 AI 输入 JSON
    - stats_context: 历史统计上下文（可选）
    - history_context: 相似案例上下文（可选）
    - learning_feedback: AI自我认知/学习反馈（可选）
    
    返回：
    - 完整的 Prompt 字符串
    """
    
    json_str = json.dumps(ai_json, ensure_ascii=False, indent=2)
    
    # 构建历史上下文块
    context_blocks = []
    
    if learning_feedback:
        context_blocks.append(f"""【AI历史表现自我认知】
{learning_feedback}
请根据上述历史表现，在分析时保持适度谨慎，尤其注意你的弱项领域。
""")
    
    if history_context:
        context_blocks.append(f"""【相似案例历史参考】
{history_context}
请参考上述相似案例的历史表现，合理评估预测的可靠性。
""")
    
    if stats_context:
        context_blocks.append(f"""【历史统计提示】
{stats_context}
""")
    
    context_section = "\n".join(context_blocks) if context_blocks else ""
    
    return f"""你是一名精通缠论的数字货币交易分析师。

{context_section}
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
- ✅ 如有历史表现数据，请在分析中体现谨慎程度

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


def build_table_format_prompt(
    ai_json: Dict[str, Any],
    stats_context: str = "",
    history_context: str = "",
    learning_feedback: str = "",
) -> str:
    """构造表格格式的缠论分析 Prompt（增强版，支持历史上下文）
    
    这个 Prompt 专门用于处理包含表格数据的输入，
    要求 AI 输出结构化的 Markdown 分析报告。
    
    参数：
    - ai_json: 符合规范的 AI 输入 JSON
    - stats_context: 历史统计上下文（可选）
    - history_context: 相似案例上下文（可选）
    - learning_feedback: AI自我认知/学习反馈（可选）
    
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
    
    # 构建历史上下文块
    context_blocks = []
    
    if learning_feedback:
        context_blocks.append(f"""## AI历史表现自我认知

{learning_feedback}

> 请根据上述历史表现，在分析时保持适度谨慎，尤其注意弱项领域。
""")
    
    if history_context:
        context_blocks.append(f"""## 相似案例历史参考

{history_context}

> 请参考上述相似案例的历史表现，合理评估预测的可靠性。
""")
    
    if stats_context:
        context_blocks.append(f"""## 历史统计提示

{stats_context}
""")
    
    context_section = "\n---\n\n".join(context_blocks) if context_blocks else ""
    if context_section:
        context_section = "\n---\n\n" + context_section
    
    return f"""# 缠论技术分析：{meta.get('symbol', 'Unknown')} 走势分析

请根据以下缠论数据，分析后续可能走势，并按照**标准格式**输出。
{context_section}
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
- 入场点位区间：[价格低点 - 价格高点]
- 止损位：[具体价格]
- 目标位：[价格区间]

**空头策略**：
- 入场点位区间：[价格低点 - 价格高点]
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


def build_state_machine_prompt(
    ai_json: Dict[str, Any],
    stats_context: str = "",
    history_context: str = "",
    learning_feedback: str = "",
) -> str:
    """
    构建状态机模式的 Prompt（v2.0 新增）

    强制 AI 输出状态机格式，而非多场景并列模式

    参数：
    - ai_json: 缠论结构 JSON
    - stats_context: 历史统计上下文
    - history_context: 相似案例上下文
    - learning_feedback: AI 自我认知

    返回：
    - 状态机模式的 Prompt
    """
    from ai_output_schema import get_state_machine_schema_template

    json_str = json.dumps(ai_json, ensure_ascii=False, indent=2)
    schema = get_state_machine_schema_template()

    meta = ai_json.get("meta", {})
    market = ai_json.get("market", {})
    symbol = meta.get("symbol", "Unknown")
    interval = meta.get("interval", "Unknown")
    latest_price = float(market.get("latest_price", 0.0))

    # 获取结构摘要
    structure_summary = ai_json.get("structure_summary", {})
    trend_desc = structure_summary.get("trend_description", "未知")
    position_desc = structure_summary.get("position_description", "未知")
    key_levels = structure_summary.get("key_levels", {})
    price_position = structure_summary.get("price_position", "unknown")

    # 统计提示
    in_zs = price_position == "inside_zs"
    stat = get_stat_hint(symbol=symbol, interval=interval, in_zs=in_zs)
    win_rate_str = f"{stat['win_rate']}" if stat.get("win_rate") is not None else "N/A"

    stat_block = f"""
【统计提示】
交易对：{symbol}，周期：{interval}，结构位置：{"中枢内" if in_zs else "中枢外"}
样本数量：{stat["sample"]}
历史胜率：{win_rate_str}
"""

    # 历史上下文块
    history_block = ""
    if history_context:
        history_block = history_context + "\n"

    # 学习反馈块
    learning_block = ""
    if learning_feedback:
        learning_block = learning_feedback + "\n"

    # 系统约束（状态机专用）
    system_block = """
【系统约束】
你是一个"交易决策状态机生成器"，不是分析师。

【强制规则】
1. 任意时刻，只能有一个 active_strategy
2. active_strategy 必须有明确状态（WAIT / READY / ACTIVE）
3. entry 必须是"结构触发 + 价格区间"，不能只有价格
4. 必须定义 invalidation 条件（什么情况下放弃当前策略）
5. 如果历史胜率 < 30%，必须输出 WAIT_CONFIRMATION 或 OBSERVE_ONLY 状态
6. 禁止同时给出做多 / 做空 / 震荡的完整策略（只能有一个激活）
"""

    # 缠论结构 JSON
    structure_block = f"""
【缠论结构 JSON】
{json_str}
"""

    # 输出格式约束
    output_block = f"""
【输出格式】
1. 必须输出符合 Schema 的合法 JSON
2. state_machine.current_state 必须是 STRATEGY_ACTIVE / WAIT_CONFIRMATION / OBSERVE_ONLY 之一
3. state_machine.active_strategy 必须包含：
   - direction: 策略方向（up/down）
   - status: 策略状态（WAIT/READY/ACTIVE/INVALIDATED）
   - entry_gate: 入场门槛（必须包含 price_zone 和 structure_required）
   - execution: 执行参数（stop_loss, target, rr）
4. structure_required 不能为空，必须是具体的缠论术语条件
5. 必须定义 invalidation.invalidate_active_if（至少1个条件）
6. 如果历史胜率低，自动降级状态：
   - 胜率 < 25% → OBSERVE_ONLY
   - 胜率 25-35% → WAIT_CONFIRMATION
   - 胜率 > 35% → STRATEGY_READY

【JSON Schema】
```json
{schema}
```
"""

    # 组装 Prompt
    blocks = {
        "system_block": system_block,
        "structure_block": structure_block,
        "output_block": output_block,
        "stat_block": stat_block,
        "TERMINOLOGY_BLOCK": TERMINOLOGY_BLOCK,
        "learning_block": learning_block,
        "history_block": history_block,
    }

    prompt = build_prompt_with_token_management(blocks, max_tokens=SAFE_TOKENS)

    return prompt

