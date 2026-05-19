"""管道节点 LLM 调用辅助

轻量级 LLM 调用封装，供管道节点使用。
避免依赖重量级 LLMServiceFactory（需要 ConfigManager）。
"""
import asyncio
import json
from typing import Any, Optional

import httpx

from src.utils.logger import logger


async def call_llm(
    prompt: str,
    model: str = "qwen-turbo",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    system_prompt: str = "",
) -> str:
    """调用 LLM 获取文本响应

    Args:
        prompt: 用户提示词
        model: 模型名称
        temperature: 温度
        max_tokens: 最大 token 数
        system_prompt: 系统提示词

    Returns:
        LLM 响应文本
    """
    # 检测提供商
    provider = _detect_provider(model)
    api_key = _get_api_key(provider)

    if not api_key:
        raise ValueError(f"未配置 {provider} API Key")

    if provider == "dashscope":
        return await _call_dashscope(prompt, model, temperature, max_tokens, system_prompt, api_key)
    elif provider == "openai":
        return await _call_openai(prompt, model, temperature, max_tokens, system_prompt, api_key)
    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")


def _detect_provider(model: str) -> str:
    """根据模型名称检测提供商"""
    if model.startswith("qwen") or model.startswith("text-embedding"):
        return "dashscope"
    elif model.startswith("gpt") or model.startswith("text-embedding"):
        return "openai"
    elif model.startswith("claude"):
        return "anthropic"
    elif model.startswith("deepseek"):
        return "deepseek"
    return "dashscope"  # 默认


def _get_api_key(provider: str) -> str:
    """获取 API Key（通过 Settings 统一管理）"""
    from src.config import settings

    key_map = {
        "dashscope": settings.dashscope_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "deepseek": settings.deepseek_api_key,
    }
    return key_map.get(provider, "")


async def _call_dashscope(
    prompt: str, model: str, temperature: float, max_tokens: int,
    system_prompt: str, api_key: str
) -> str:
    """调用 DashScope API"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def _call_openai(
    prompt: str, model: str, temperature: float, max_tokens: int,
    system_prompt: str, api_key: str
) -> str:
    """调用 OpenAI 兼容 API"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    from src.config import settings

    base_url = (
        settings.llm_providers.get("openai", None)
        and settings.llm_providers["openai"].base_url
    ) or "https://api.openai.com"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def call_llm_json(
    prompt: str,
    model: str = "qwen-turbo",
    temperature: float = 0.1,
    max_tokens: int = 2048,
    system_prompt: str = "",
) -> Any:
    """调用 LLM 获取 JSON 响应

    自动修复常见 JSON 格式问题。
    """
    raw = await call_llm(prompt, model, temperature, max_tokens, system_prompt)

    # 尝试解析 JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 尝试提取 JSON 块
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试 json-repair
        try:
            from json_repair import repair_json
            return json.loads(repair_json(raw))
        except Exception:
            logger.warning(f"JSON 解析失败: {raw[:200]}")
            return None
