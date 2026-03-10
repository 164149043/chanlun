#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""流式分析服务 - 支持 SSE 日志输出"""

import sys
import os
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Dict, Any

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from binance import get_klines
from chanlun_adapter import convert_to_chanlun_bars
from chanlun_icl import ICL
from chanlun_ai_exporter import ChanlunAIExporter
from prompt_builder import build_structured_prompt, build_table_format_prompt
from ai.llm import call_ai
from ai_output_schema import validate_ai_output
from dotenv import load_dotenv
import pandas as pd


# 全局进度存储（直接存储，避免循环导入）
_analysis_progress_storage = {}


def get_analysis_progress():
    """获取全局分析进度存储"""
    return _analysis_progress_storage


async def analyze_streaming_async(
    symbol: str,
    interval: str,
    mode: str,
    test_mode: bool,
    task_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    流式分析主函数

    返回: 异步生成器，产生日志事件
    """

    def emit_log(level: str, message: str, step: int = None, total_steps: int = None):
        """发送日志事件"""
        return {
            "level": level,
            "message": message,
            "step": step,
            "total_steps": total_steps,
            "timestamp": asyncio.get_event_loop().time()
        }

    async def async_yield(log_data: Dict[str, Any]):
        """异步 yield，让控制权返回给事件循环"""
        yield log_data
        # 小延迟确保数据被发送
        await asyncio.sleep(0)

    # 总步骤数
    TOTAL_STEPS = 6

    # 显示符号格式化
    display_symbol = f"{symbol[:3]}/{symbol[3:]}" if len(symbol) > 3 else symbol

    # 步骤 0: 开始
    yield emit_log("step", f"🚀 开始分析 {display_symbol} {interval} (500 根K线)", 0, TOTAL_STEPS)
    await asyncio.sleep(0.01)

    # 步骤 1: 获取 K 线数据
    yield emit_log("step", f"📊 步骤 1/{TOTAL_STEPS}: 获取 Binance K 线数据...", 1, TOTAL_STEPS)
    await asyncio.sleep(0.01)

    try:
        klines = get_klines(symbol, interval, 500)
        if not klines or len(klines) < 10:
            yield emit_log("error", "✗ 获取数据失败：数据不足")
            return

        yield emit_log("success", f"   ✓ 获取到 {len(klines)} 根 K 线", 1, TOTAL_STEPS)
        await asyncio.sleep(0.01)

    except Exception as e:
        yield emit_log("error", f"✗ 获取数据失败: {str(e)}")
        return

    # 步骤 2: 缠论结构计算
    yield emit_log("step", f"🧮 步骤 2/{TOTAL_STEPS}: 缠论结构计算...", 2, TOTAL_STEPS)
    await asyncio.sleep(0.01)

    try:
        bars = convert_to_chanlun_bars(klines)
        df = pd.DataFrame(bars).rename(columns={
            "date": "date", "o": "open", "h": "high", "l": "low",
            "c": "close", "a": "volume"
        })

        frequency_map = {"15m": "15m", "1h": "60m", "4h": "240m", "1d": "1440m"}
        frequency = frequency_map.get(interval, interval)

        icl = ICL(code=display_symbol, frequency=frequency, config=None)
        icl = icl.process_klines(df)

        yield emit_log("success", "   ✓ 缠论计算完成", 2, TOTAL_STEPS)
        await asyncio.sleep(0.01)

    except Exception as e:
        yield emit_log("error", f"✗ 缠论计算失败: {str(e)}")
        return

    # 步骤 3: 构造 AI 输入数据
    yield emit_log("step", f"📦 步骤 3/{TOTAL_STEPS}: 构造 AI 输入数据...", 3, TOTAL_STEPS)
    await asyncio.sleep(0.01)

    yield emit_log("success", "   ✓ 数据构造完成", 3, TOTAL_STEPS)
    await asyncio.sleep(0.01)

    # 导出数据并显示结构快览
    try:
        exporter = ChanlunAIExporter()
        ai_json = exporter.export(icl=icl, symbol=display_symbol, interval=interval, klines=klines)

        # 显示结构快览
        yield emit_log("info", f"💰 当前价格：{klines[-1]['close']:.2f}")
        await asyncio.sleep(0.01)

        if ai_json.get("center"):
            centers = ai_json["center"][-3:]  # 显示最后3个中枢
            for i, zs in enumerate(centers, 1):
                zg = zs.get("zg", 0)
                zd = zs.get("zd", 0)
                relation = zs.get("relation", "")
                yield emit_log("info", f"🧱 中枢 #{i}（1 级）：{zd:.2f} ~ {zg:.2f}   关系：{relation}")
                await asyncio.sleep(0.01)

        bi = ai_json.get("bi", [])[-1] if ai_json.get("bi") else None
        if bi:
            direction = "↑" if bi.get("type") == "up" else "↓"
            status = "（已完成）" if bi.get("is_done") else "（进行中）"
            yield emit_log("info", f"📊 最新一笔：{direction} {status}")
            await asyncio.sleep(0.01)

        signals = ai_json.get("signal", {})
        if signals.get("buy_sell_points"):
            yield emit_log("info", f"🚨 近期信号：买卖点：{', '.join(signals.get('buy_sell_points', []))}")
            await asyncio.sleep(0.01)
        if signals.get("divergences"):
            yield emit_log("info", f"   背驰：{', '.join(signals.get('divergences', []))}")
            await asyncio.sleep(0.01)
    except Exception as e:
        yield emit_log("warning", f"⚠️ 结构快览生成失败: {str(e)}")
        await asyncio.sleep(0.01)

    # 步骤 4: 调用 AI 分析
    yield emit_log("step", f"🤖 步骤 4/{TOTAL_STEPS}: 调用 AI 进行分析...", 4, TOTAL_STEPS)
    await asyncio.sleep(0.01)

    # 获取 AI 配置
    api_key, provider, model, temperature, max_tokens = load_api_config()

    config_display = model if provider == "deepseek" or "anthropic" else f"{provider}/{model.split('/')[-1]}"
    yield emit_log("info", f"   ⚙️  配置信息：Provider: {provider}  Model: {config_display}")
    await asyncio.sleep(0.01)

    # 构建提示词
    try:
        if mode == "table":
            prompt = build_table_format_prompt(ai_json)
        else:
            prompt = build_structured_prompt(ai_json)
    except Exception as e:
        yield emit_log("error", f"✗ 提示词构建失败: {str(e)}")
        return

    # 调用 AI
    yield emit_log("step", f"⏳ 等待 AI 响应（可能需要20-60 秒）...", 4, TOTAL_STEPS)
    await asyncio.sleep(0.01)

    try:
        if not api_key:
            yield emit_log("error", "✗ AI API key 未配置")
            return

        analysis_result = call_ai(
            prompt=prompt, model=model, api_key=api_key,
            provider=provider, temperature=temperature, max_tokens=max_tokens
        )

        yield emit_log("success", "   ✓ AI 分析完成", 4, TOTAL_STEPS)
        await asyncio.sleep(0.01)

    except Exception as e:
        yield emit_log("error", f"✗ AI 调用失败: {str(e)}")
        return

    # 步骤 5: 处理结果
    yield emit_log("step", f"📋 步骤 5/{TOTAL_STEPS}: 处理分析结果...", 5, TOTAL_STEPS)
    await asyncio.sleep(0.01)

    try:
        if mode == "table":
            result = {
                "mode": "table",
                "content": analysis_result,
                "meta": {"symbol": symbol, "interval": interval, "price": klines[-1]["close"]}
            }
        else:
            import json
            clean_result = analysis_result.strip()
            if clean_result.startswith("```json"): clean_result = clean_result[7:]
            if clean_result.startswith("```"): clean_result = clean_result[3:]
            if clean_result.endswith("```"): clean_result = clean_result[:-3]

            structured_output = json.loads(clean_result.strip())
            result = validate_ai_output(structured_output)
            result["meta"] = result.get("meta", {})
            result["meta"]["price"] = klines[-1]["close"]
            result["meta"]["symbol"] = symbol
            result["meta"]["interval"] = interval
            result["mode"] = "structured"

            # 尝试添加状态机转换（如果存在）
            try:
                from state_machine_converter import scenarios_to_state_machine
                state_machine = scenarios_to_state_machine(
                    result,
                    klines[-1]["close"],
                    historical_winrate=None
                )
                result["state_machine"] = state_machine
                result["output_mode"] = "state_machine"
                result["version"] = "2.0"
            except Exception:
                pass  # 状态机转换失败不影响主流程

        # 保存结果到全局存储
        get_analysis_progress()[task_id] = result

        yield emit_log("success", "   ✓ 结果处理完成", 5, TOTAL_STEPS)
        await asyncio.sleep(0.01)

        # 步骤 6: 完成
        yield emit_log("success", f"✅ 分析完成！(任务ID: {task_id})", 6, TOTAL_STEPS)
        await asyncio.sleep(0.01)

    except Exception as e:
        yield emit_log("error", f"✗ 结果处理失败: {str(e)}")
        return


def load_api_config():
    """加载 AI API 配置"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    provider = os.getenv("AI_PROVIDER", "siliconflow")
    model = os.getenv("AI_MODEL", "Pro/deepseek-ai/DeepSeek-V3.2")
    temperature = float(os.getenv("AI_TEMPERATURE", "0.3"))
    max_tokens = int(os.getenv("AI_MAX_TOKENS", "4096"))

    api_key = None
    if provider == "siliconflow":
        api_key = os.getenv("SILICONFLOW_API_KEY")
    elif provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
    elif provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")

    return api_key, provider, model, temperature, max_tokens
