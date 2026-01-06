"""LLM 调用封装模块

本模块只关心：
- 接收已经拼接完成的 prompt 字符串
- 调用兼容 Chat Completions 接口的服务（如 OpenAI / OpenRouter）
- 返回模型回复的纯文本内容

不关心任何业务细节，也不负责拼装 prompt 内容。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class LLMConfig:
    """LLM 客户端基础配置

    说明：
    - 不直接耦合具体业务，只描述调用一个 Chat Completions 接口所需的核心信息。
    - 通过 base_url 可以同时支持多种服务：
      - OpenAI 风格: 例如 "https://api.openai.com/v1"
      - OpenRouter:  "https://openrouter.ai/api/v1"
    """

    # 模型名称，例如："gpt-4.1-mini" 或 OpenRouter 上的具体模型名
    model: str

    # HTTP 接口的基础地址（不包含具体 path）
    # 例如："https://api.openai.com/v1" 或 "https://openrouter.ai/api/v1"
    base_url: str

    # 鉴权使用的 API Key（调用方负责安全管理，不在此模块持久化）
    api_key: str

    # 默认采样参数，可在调用时覆盖
    temperature: float = 0.2
    max_tokens: int = 1024

    # 请求超时时间（秒）
    timeout: float = 30.0

    # 允许调用方传入额外 HTTP 头，用于 OpenRouter 等特殊需求
    # 例如：{"HTTP-Referer": "https://your.site", "X-Title": "ChanLun AI"}
    extra_headers: Optional[Dict[str, str]] = None


class LLMClient:
    """简单的 LLM 客户端封装

    核心功能：
    - 提供一个 generate 方法：接收完整的 prompt 字符串，返回回复文本。
    - 不拼装业务 prompt，不解析业务字段，仅返回模型的主要回答内容。

    使用方式示意（伪代码）：

    >>> config = LLMConfig(
    ...     model="your-model",
    ...     base_url="https://openrouter.ai/api/v1",
    ...     api_key="YOUR_API_KEY",
    ... )
    >>> client = LLMClient(config)
    >>> reply = client.generate("已经拼好的完整 prompt 文本")
    >>> print(reply)
    """

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

        # 根据 base_url 构造 Chat Completions 的完整接口地址
        # 通常为：{base_url}/chat/completions
        self._endpoint = self._config.base_url.rstrip("/") + "/chat/completions"

    def generate(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """向模型发送 prompt 并返回回复文本

        参数：
        - prompt:  已经由上层业务拼装好的完整提示词字符串。
        - temperature: 可选，采样温度；不传则使用 LLMConfig 中的默认值。
        - max_tokens:  可选，最大生成长度；不传则使用 LLMConfig 中的默认值。

        返回：
        - 模型回复的主要文本内容（通常对应第一个 choice 的 message.content）。

        说明：
        - 本方法假设底层服务实现了兼容 OpenAI Chat Completions 的接口格式，
          包括 OpenRouter 在内的许多服务都是兼容这种格式的。
        - 若调用失败，将抛出 RuntimeError 并附带简单错误信息，上层可自行捕获处理。
        """

        # 使用传入参数覆盖配置中的默认值
        used_temperature = temperature if temperature is not None else self._config.temperature
        used_max_tokens = max_tokens if max_tokens is not None else self._config.max_tokens

        # 组装 HTTP 请求头
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

        # 若调用方提供了额外头信息（例如 OpenRouter 推荐附带的 HTTP-Referer 等），则合并
        if self._config.extra_headers:
            headers.update(self._config.extra_headers)

        # OpenAI / OpenRouter 风格的 Chat Completions 请求体
        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": used_temperature,
            "max_tokens": used_max_tokens,
        }

        try:
            response = requests.post(
                self._endpoint,
                headers=headers,
                json=payload,
                timeout=self._config.timeout,
            )
        except requests.RequestException as exc:  # 网络层异常（超时、连接失败等）
            raise RuntimeError(f"LLM 请求失败（网络错误）：{exc}") from exc

        # 非 2xx 状态码视为接口调用失败
        if not response.ok:
            # 尝试获取服务端返回的错误信息，方便调试
            error_text = response.text
            raise RuntimeError(
                f"LLM 请求失败，HTTP 状态码 {response.status_code}，响应内容：{error_text}"
            )

        try:
            data = response.json()
        except ValueError as exc:  # JSON 解析失败
            raise RuntimeError(f"LLM 响应不是有效的 JSON：{response.text}") from exc

        # 解析兼容 OpenAI 的返回结构：
        # {
        #   "choices": [
        #     {
        #       "message": {"role": "assistant", "content": "..."},
        #       ...
        #     },
        #     ...
        #   ],
        #   ...
        # }
        choices = data.get("choices")
        if not choices:
            raise RuntimeError(f"LLM 响应中未包含 choices 字段：{data}")

        first_choice = choices[0]
        message = first_choice.get("message") or {}
        content = message.get("content")

        if not isinstance(content, str):
            raise RuntimeError(f"LLM 响应中未找到有效的文本内容：{data}")

        return content


def call_ai(
    prompt: str,
    *,
    model: str,
    api_key: str,
    provider: str = "openrouter",
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    """通用 AI 调用入口

    参数：
    - prompt:      已经拼接好的完整提示词字符串。
    - model:       模型名称：
                    - 对于 OpenRouter：例如 "openrouter/claude-3.5-sonnet"、"openrouter/gpt-4.1" 等；
                    - 对于 DeepSeek：例如 "deepseek-chat"；
                    - 对于硅基流动：例如 "Pro/deepseek-ai/DeepSeek-V3.2"；
                    - 对于 Anthropic：例如 "claude-3.5-sonnet"（直连官方）。
    - api_key:     对应服务的 API Key。
    - provider:    服务提供方标识："openrouter" / "deepseek" / "siliconflow" / "anthropic"。
    - temperature: 采样温度。
    - max_tokens:  最大生成长度。

    返回：
    - analysis_text: 模型返回的主要文本内容。

    说明：
    - openrouter / deepseek / siliconflow 均走 OpenAI Chat Completions 风格接口，由上面的 LLMClient 实现；
    - anthropic (Claude) 使用官方 Messages 接口，单独走一套 HTTP 调用逻辑。
    """

    provider = provider.lower()

    # OpenRouter：推荐使用，统一聚合多个模型（包括 Claude / GPT 等）
    if provider == "openrouter":
        cfg = LLMConfig(
            model=model,
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        client = LLMClient(cfg)
        return client.generate(prompt)

    # DeepSeek：提供 OpenAI 兼容接口
    if provider == "deepseek":
        cfg = LLMConfig(
            model=model,
            base_url="https://api.deepseek.com/v1",
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        client = LLMClient(cfg)
        return client.generate(prompt)
    
    # 硅基流动（SiliconFlow）：提供 OpenAI 兼容接口
    if provider == "siliconflow":
        cfg = LLMConfig(
            model=model,
            base_url="https://api.siliconflow.cn/v1",
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=180.0,  # 硅基流动需要更长超时时间（3分钟），因为模型推理较慢
        )
        client = LLMClient(cfg)
        return client.generate(prompt)

    # Anthropic（Claude）：使用官方 Messages 接口
    if provider == "anthropic":
        return _call_anthropic(prompt, model=model, api_key=api_key, max_tokens=max_tokens)

    raise ValueError(f"不支持的 provider: {provider}")


def _call_anthropic(prompt: str, *, model: str, api_key: str, max_tokens: int) -> str:
    """调用 Anthropic 官方 Claude 接口

    使用 Messages API：
    POST https://api.anthropic.com/v1/messages

    参考文档：https://docs.anthropic.com/
    """

    import requests  # 局部导入，避免对未使用环境的影响

    url = "https://api.anthropic.com/v1/messages"

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        # 使用一个较新的版本号，具体可按官方文档调整
        "anthropic-version": "2023-06-01",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as exc:  # type: ignore[attr-defined]
        raise RuntimeError(f"Anthropic 请求失败（网络错误）：{exc}") from exc

    if not resp.ok:
        raise RuntimeError(
            f"Anthropic 请求失败，HTTP 状态码 {resp.status_code}，响应内容：{resp.text}"
        )

    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"Anthropic 响应不是有效的 JSON：{resp.text}") from exc

    # 预期结构：
    # {
    #   "content": [
    #     {"type": "text", "text": "..."},
    #     ...
    #   ],
    #   ...
    # }
    contents = data.get("content")
    if not contents:
        raise RuntimeError(f"Anthropic 响应中未找到 content 字段：{data}")

    first = contents[0]
    text = first.get("text") if isinstance(first, dict) else None
    if not isinstance(text, str):
        raise RuntimeError(f"Anthropic 响应中未找到有效的文本内容：{data}")

    return text
