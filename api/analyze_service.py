#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI 分析服务 - 为 Web API 提供缠论 AI 分析功能"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from binance import get_klines
from chanlun_adapter import convert_to_chanlun_bars
from chanlun_icl import ICL
from chanlun_ai_exporter import ChanlunAIExporter
from prompt_builder import build_structured_prompt, build_table_format_prompt, build_structured_table_prompt
from ai.llm import call_ai
from ai_output_schema import validate_ai_output
from dotenv import load_dotenv

import pandas as pd


def load_api_config(provider: str = None, model: str = None, api_key_override: str = None):
    """
    加载 AI API 配置

    参数:
        provider: AI 服务提供商（从前端传入，优先使用）
        model: AI 模型（从前端传入，优先使用）
        api_key_override: API Key（从前端传入，优先使用，空字符串时忽略）

    返回:
        (api_key, provider, model, temperature, max_tokens)
    """
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # 优先使用传入的参数，否则使用环境变量
    _provider = provider or os.getenv("AI_PROVIDER", "siliconflow")
    _model = model or os.getenv("AI_MODEL", "Pro/deepseek-ai/DeepSeek-V3.2")
    temperature = float(os.getenv("AI_TEMPERATURE", "0.3"))
    max_tokens = int(os.getenv("AI_MAX_TOKENS", "4096"))

    # 获取 API Key（优先使用传入的，但空字符串时使用环境变量）
    if api_key_override and api_key_override.strip():
        api_key = api_key_override
    elif _provider == "siliconflow":
        api_key = os.getenv("SILICONFLOW_API_KEY")
    elif _provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
    elif _provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
    elif _provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
    else:
        api_key = None

    return api_key, _provider, _model, temperature, max_tokens


def analyze_chanlun(
    symbol: str,
    interval: str,
    limit: int = 500,
    test_mode: bool = False,
    mode: str = "structured",
    ai_provider: str = None,
    ai_model: str = None,
    api_key: str = None
):
    """
    执行缠论 AI 分析

    参数:
        symbol: 交易对，如 BTCUSDT
        interval: 周期，如 1h
        limit: K线数量
        test_mode: 测试模式，跳过 AI 调用
        mode: 输出模式，"structured" (JSON) 或 "table" (Markdown)
        ai_provider: AI 服务提供商（从前端传入）
        ai_model: AI 模型（从前端传入）
        api_key: API Key（从前端传入）

    返回:
        dict: AI 分析结果 (structured 或 table 格式)
    """
    # Check for test mode (uses parameter instead of global env var)
    if test_mode:
        return {
            "mock_data": True,
            "analysis": "Test mode - skipping AI call",
            "meta": {"symbol": symbol, "interval": interval}
        }

    try:
        # 1. 获取 K线数据
        klines = get_klines(symbol, interval, limit)
        if not klines or len(klines) < 10:
            return {"error": "Insufficient data"}

        # 2. 转换为缠论 bars
        bars = convert_to_chanlun_bars(klines)

        # 3. 缠论计算
        df = pd.DataFrame(bars)
        df = df.rename(columns={
            "date": "date",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "a": "volume",
        })

        # 周期映射
        frequency_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "60m", "4h": "240m", "1d": "1440m"
        }
        frequency = frequency_map.get(interval, interval)

        # 显示符号
        display_symbol = f"{symbol[:3]}/{symbol[3:]}" if len(symbol) > 3 else symbol

        icl = ICL(code=display_symbol, frequency=frequency, config=None)
        icl = icl.process_klines(df)

        # 4. 导出 AI JSON
        exporter = ChanlunAIExporter()
        ai_json = exporter.export(
            icl=icl,
            symbol=display_symbol,
            interval=interval,
            klines=klines,
        )

        latest_price = klines[-1]["close"]

        # 5. 构建 AI Prompt (根据 mode 选择)
        if mode == "table":
            # 表格模式：输出 Markdown 格式
            prompt = build_table_format_prompt(ai_json)
        else:
            # 结构化模式：输出 JSON 格式
            prompt = build_structured_prompt(ai_json)

        # 6. 调用 AI
        # 优先使用前端传入的配置，否则使用环境变量
        api_key, provider, model, temperature, max_tokens = load_api_config(
            provider=ai_provider,
            model=ai_model,
            api_key_override=api_key
        )
        if not api_key:
            return {"error": "AI API key not configured"}

        analysis_result = call_ai(
            prompt=prompt,
            model=model,
            api_key=api_key,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # 7. 根据 mode 处理返回结果
        if mode == "table":
            # 表格模式：直接返回 Markdown 文本
            return {
                "mode": "table",
                "content": analysis_result,  # Markdown 格式的分析文本
                "meta": {
                    "symbol": symbol,
                    "interval": interval,
                    "price": latest_price
                }
            }
        else:
            # 结构化模式：解析 JSON
            import json
            clean_result = analysis_result.strip()
            if clean_result.startswith("```json"):
                clean_result = clean_result[7:]
            if clean_result.startswith("```"):
                clean_result = clean_result[3:]
            if clean_result.endswith("```"):
                clean_result = clean_result[:-3]
            clean_result = clean_result.strip()

            try:
                structured_output = json.loads(clean_result)
            except json.JSONDecodeError:
                return {"error": "Failed to parse AI response", "raw": clean_result}

            # 验证
            validated_output = validate_ai_output(structured_output)

            # ⭐ v2.0 新增：状态机转换
            try:
                from state_machine_converter import scenarios_to_state_machine
                state_machine = scenarios_to_state_machine(
                    validated_output,
                    latest_price,
                    historical_winrate=None  # API 模式下暂不获取历史胜率
                )
                validated_output["state_machine"] = state_machine
                validated_output["output_mode"] = "state_machine"
                validated_output["version"] = "2.0"
            except Exception as sm_err:
                # 状态机转换失败不影响主流程
                pass

            # 添加当前价格信息
            if "meta" not in validated_output:
                validated_output["meta"] = {}
            validated_output["meta"]["price"] = latest_price
            validated_output["meta"]["symbol"] = symbol
            validated_output["meta"]["interval"] = interval
            validated_output["mode"] = "structured"

            return validated_output

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
