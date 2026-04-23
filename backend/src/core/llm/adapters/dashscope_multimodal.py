"""DashScope MultiModalConversation 适配器

将 DashScope 的 MultiModalConversation 和 Generation 包装为统一的 LLMService 接口，
支持纯文本和多模态模型统一调用。
"""

import asyncio
import time
import uuid
from typing import Any, Optional

from src.core.llm.base import (LLMRateLimitError, LLMService, LLMTimeoutError,
                                LLMUnavailableError)
from src.core.llm.log_collector import LLMLogCollector
from src.core.tracing.context import (create_span, get_current_span_id,
                                       get_current_trace_id, get_parent_span_id)
from src.core.tracing.truncation import truncate_content, truncate_messages
from src.core.tracing.writer import get_trace_writer
from src.schemas import LLMMessage, LLMRequest, LLMResponse
from src.utils.logger import logger


class DashScopeMultiModalAdapter(LLMService):
    """DashScope 多模态/文本统一适配器
    
    根据模型名称自动选择调用 API：
    - 多模态模型 → dashscope.MultiModalConversation.call()
    - 纯文本模型 → dashscope.Generation.call()
    通过 asyncio.to_thread() 包装为异步接口。
    """

    def __init__(self, model: str, api_key: str, multimodal_prefixes: Optional[list[str]] = None, **kwargs):
        """初始化适配器
        
        Args:
            model: 模型名称（如 qwen3.5-turbo, qwen3-omni-flash, qwen-vl-max）
            api_key: DashScope API Key
            multimodal_prefixes: 多模态模型前缀列表（从配置读取，未提供时使用默认值）
            **kwargs: 其他参数（temperature, max_tokens, top_p 等）
        """
        self._model = model
        self._api_key = api_key
        self._multimodal_prefixes = multimodal_prefixes or self._get_default_prefixes()
        self._default_params = {
            k: v for k, v in kwargs.items()
            if k in ('temperature', 'max_tokens', 'top_p', 'presence_penalty', 
                     'frequency_penalty', 'result_format')
        }
        # 默认使用 message 格式返回
        if 'result_format' not in self._default_params:
            self._default_params['result_format'] = 'message'

    @staticmethod
    def _get_default_prefixes() -> list[str]:
        """获取默认多模态模型前缀列表"""
        try:
            from src.config import settings
            return settings.llm_multimodal_model_prefixes
        except Exception:
            return [
                'qwen-vl',
                'qwen-audio',
                'qwen-omni',
                'qwen-vl-plus',
                'qwen-vl-max',
                'qwen-vl-max-latest',
                'qwen-audio-turbo',
                'qwen-audio-turbo-latest',
                'qwen-omni-turbo',
                'qwen-omni-flash',
                'qwen3-omni-flash',
                'qwen3-omni-turbo',
            ]

    def _is_multimodal_model(self) -> bool:
        """判断是否为多模态模型"""
        return any(self._model.startswith(prefix) for prefix in self._multimodal_prefixes)

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict]:
        """转换消息格式为 DashScope MultiModalConversation 格式
        
        Args:
            messages: LLMMessage 列表
            
        Returns:
            DashScope 消息格式列表
        """
        converted = []
        for msg in messages:
            if msg.role == "system":
                converted.append({
                    "role": "system",
                    "content": msg.content
                })
            elif msg.role == "user":
                converted.append({
                    "role": "user",
                    "content": msg.content
                })
            elif msg.role == "assistant":
                converted.append({
                    "role": "assistant",
                    "content": msg.content
                })
        return converted

    def _call_sync(self, messages: list[dict], **kwargs) -> str:
        """同步调用 DashScope API（自动选择文本或多模态 API）
        
        Args:
            messages: DashScope 格式消息列表
            **kwargs: 调用参数
            
        Returns:
            模型返回的文本内容
        """
        import dashscope
        from http import HTTPStatus
        
        # 合并默认参数和调用时参数
        call_params = {**self._default_params, **kwargs}
        
        if self._is_multimodal_model():
            response = dashscope.MultiModalConversation.call(
                model=self._model,
                messages=messages,
                api_key=self._api_key,
                **call_params
            )
        else:
            # 纯文本模型使用 Generation API
            # 将消息合并为单个 prompt（Generation API 格式）
            prompt = self._messages_to_prompt(messages)
            response = dashscope.Generation.call(
                model=self._model,
                prompt=prompt,
                api_key=self._api_key,
                **call_params
            )
        
        if response.status_code == HTTPStatus.OK:
            if response.output and response.output.choices:
                content = response.output.choices[0].message.content
                # content 可能是字符串或列表
                if isinstance(content, list):
                    return "".join(
                        [item["text"] for item in content if "text" in item]
                    )
                elif isinstance(content, str):
                    return content
                else:
                    return str(content)
            else:
                raise LLMUnavailableError(f"模型返回空响应")
        else:
            raise LLMUnavailableError(
                f"DashScope 调用失败：{response.code} - {response.message}"
            )

    def _messages_to_prompt(self, messages: list[dict]) -> str:
        """将消息列表转换为 Generation API 的 prompt 格式
        
        Args:
            messages: DashScope 格式消息列表
            
        Returns:
            合并后的 prompt 字符串
        """
        prompt_parts = []
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        prompt_parts.append("Assistant: ")
        return "\n".join(prompt_parts)

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """聊天接口实现（异步）"""
        start_time = time.time()
        request_id = str(uuid.uuid4())
        trace_id = get_current_trace_id()
        writer = get_trace_writer() if trace_id else None

        try:
            ds_messages = self._convert_messages(request.messages)

            # Tracing: 记录 LLM 调用开始
            span_id = None
            if writer:
                with create_span(f"llm_call_{self._model}") as span_id:
                    truncated_messages = truncate_messages(
                        [
                            {"role": msg.role, "content": msg.content}
                            for msg in request.messages
                        ]
                    )
                    await writer.record_llm_start(
                        trace_id=trace_id,
                        span_id=span_id,
                        parent_span_id=get_parent_span_id(),
                        prompt_messages=truncated_messages,
                        call_parameters={
                            "model": self._model,
                            "scenario": request.scenario,
                            "prompt_key": request.prompt_key,
                        },
                        request_id=request_id,
                    )

                    # 在线程池中执行同步调用
                    content = await asyncio.to_thread(
                        self._call_sync,
                        ds_messages,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                    )
                    
                    ttft = int((time.time() - start_time) * 1000)
                    duration_ms = int((time.time() - start_time) * 1000)

                    input_tokens = (
                        sum(len(msg.content) for msg in request.messages) // 4
                    )
                    output_tokens = len(content) // 4

                    # Tracing: 记录 LLM 调用完成
                    truncated_completion, _ = truncate_content(content)
                    await writer.record_llm_complete(
                        trace_id=trace_id,
                        span_id=span_id,
                        parent_span_id=get_parent_span_id(),
                        completion_message=truncated_completion,
                        tokens={
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": input_tokens + output_tokens,
                        },
                        ttft=ttft,
                        request_id=request_id,
                    )

                    llm_response = LLMResponse(
                        content=content,
                        model_name=self._model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=input_tokens + output_tokens,
                        duration_ms=duration_ms,
                    )

                    await LLMLogCollector.submit(
                        {
                            "request_id": request_id,
                            "model_name": self._model,
                            "prompt_key": request.prompt_key,
                            "scenario": request.scenario,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": input_tokens + output_tokens,
                            "duration_ms": duration_ms,
                            "status": "success",
                        }
                    )

                    return llm_response
            else:
                # 无 tracing 上下文，走简化逻辑
                content = await asyncio.to_thread(
                    self._call_sync,
                    ds_messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )

                duration_ms = int((time.time() - start_time) * 1000)

                input_tokens = sum(len(msg.content) for msg in request.messages) // 4
                output_tokens = len(content) // 4

                llm_response = LLMResponse(
                    content=content,
                    model_name=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    duration_ms=duration_ms,
                )

                await LLMLogCollector.submit(
                    {
                        "request_id": request_id,
                        "model_name": self._model,
                        "prompt_key": request.prompt_key,
                        "scenario": request.scenario,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                        "duration_ms": duration_ms,
                        "status": "success",
                    }
                )

                return llm_response

        except TimeoutError as e:
            # Tracing: 记录 LLM 调用错误
            if writer and span_id:
                await writer.record_llm_error(
                    trace_id=trace_id,
                    span_id=span_id,
                    error=str(e),
                )

            await LLMLogCollector.submit(
                {
                    "request_id": request_id,
                    "model_name": self._model,
                    "prompt_key": request.prompt_key,
                    "scenario": request.scenario,
                    "status": "timeout",
                    "error_message": str(e),
                }
            )
            logger.error(f"LLM 调用超时：{e}")
            raise LLMTimeoutError(f"LLM 调用超时：{e}")
        except Exception as e:
            # Tracing: 记录 LLM 调用错误
            if writer and span_id:
                await writer.record_llm_error(
                    trace_id=trace_id,
                    span_id=span_id,
                    error=str(e),
                )

            await LLMLogCollector.submit(
                {
                    "request_id": request_id,
                    "model_name": self._model,
                    "prompt_key": request.prompt_key,
                    "scenario": request.scenario,
                    "status": "failed",
                    "error_message": str(e),
                }
            )
            if "rate limit" in str(e).lower():
                raise LLMRateLimitError(f"LLM 频率限制：{e}")
            logger.error(f"LLM 调用失败：{e}")
            raise LLMUnavailableError(f"LLM 服务不可用：{e}")

    async def chat_with_retry(
        self, request: LLMRequest, max_retries: int = 3
    ) -> LLMResponse:
        """带重试的聊天接口"""
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        async def _chat_with_retry():
            return await self.chat(request)

        return await _chat_with_retry()

    def get_model_name(self) -> str:
        """获取模型名称"""
        return self._model

    async def chat_stream(self, request: LLMRequest):
        """流式聊天接口（自动选择文本或多模态 API）"""
        import dashscope
        from http import HTTPStatus
        
        ds_messages = self._convert_messages(request.messages)
        call_params = {**self._default_params}
        
        if self._is_multimodal_model():
            response = dashscope.MultiModalConversation.call(
                model=self._model,
                messages=ds_messages,
                api_key=self._api_key,
                stream=True,
                **call_params
            )
        else:
            # 纯文本模型使用 Generation API
            prompt = self._messages_to_prompt(ds_messages)
            response = dashscope.Generation.call(
                model=self._model,
                prompt=prompt,
                api_key=self._api_key,
                stream=True,
                **call_params
            )
        
        for chunk in response:
            if chunk.status_code == HTTPStatus.OK:
                if chunk.output and chunk.output.choices:
                    content = chunk.output.choices[0].message.content
                    if isinstance(content, list):
                        for item in content:
                            if "text" in item:
                                yield item["text"]
                    elif isinstance(content, str):
                        yield content
