"""Prompt 构造模块（prompt_builder）

本模块的唯一职责：
- 读取静态 Prompt 模板文件 `ai/prompt.txt`
- 将给定的结构化 JSON 数据（Python dict），序列化为 JSON 字符串
- 用序列化后的 JSON 字符串替换模板中的占位符 `{DATA}`，生成最终 Prompt 文本

约束：
- 不修改模板内容本身（除了替换 `{DATA}` 占位符）
- 不对 JSON 做美化或拆分，直接使用 `json.dumps` 结果
- 若模板中不存在 `{DATA}` 占位符，则抛出异常提示，以避免静默错误
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def build_prompt(structured_json: Dict[str, Any], template_path: Optional[Path] = None) -> str:
    """根据模板和结构化 JSON 构造最终 Prompt 字符串

    参数：
    - structured_json:  已经整理好的结构化数据（例如包含 bi/xd/zs/bc/signal 的 dict），
                        会整体序列化为一个 JSON 字符串填入模板。
    - template_path:    可选，自定义模板路径；
                        若不传，则默认使用当前文件所在目录下的 `prompt.txt`。

    返回：
    - final_prompt_string: 替换完 `{DATA}` 占位符后的完整 Prompt 文本。

    行为约束：
    - 不修改模板中除 `{DATA}` 外的任何内容；
    - 不对 JSON 做美化或手动换行，只使用 json.dumps 直接输出；
    - 若模板中不存在 `{DATA}`，将抛出 ValueError，提醒开发者修正模板。
    """

    # 1. 确定模板文件路径
    if template_path is None:
        # 默认模板文件为当前模块所在目录下的 prompt.txt
        template_path = Path(__file__).resolve().parent / "prompt.txt"

    if not template_path.is_file():
        raise FileNotFoundError(f"Prompt 模板文件不存在：{template_path}")

    template_text = template_path.read_text(encoding="utf-8")

    # 2. 将结构化 JSON 序列化为字符串
    #    使用 ensure_ascii=False，保留中文等非 ASCII 字符，方便阅读和调试。
    data_str = json.dumps(structured_json, ensure_ascii=False)

    # 3. 检查并替换占位符
    placeholder = "{DATA}"
    if placeholder not in template_text:
        raise ValueError(f"Prompt 模板中未找到占位符 {placeholder}，请在 prompt.txt 中预留位置")

    final_prompt = template_text.replace(placeholder, data_str)
    return final_prompt
