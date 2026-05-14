import time
import uuid
from typing import Any

from llama_index.core.llms import LLM as LlamaLLM
from llama_index.core.llms import ChatMessage, MessageRole

from src.core.llm.base import (LLMRateLimitError, LLMService, LLMTimeoutError,
                               LLMUnavailableError)
from src.core.tracing.context import (create_span, get_current_span_id,
                                      get_current_trace_id, get_parent_span_id)
from src.core.tracing.writer import get_trace_writer
from src.schemas import LLMMessage, LLMRequest, LLMResponse
from src.utils.logger import logger


class LlamaIndexLLMAdapter(LLMService):
    """LlamaIndex LLM 适配器"""

    def __init__(self, llm: LlamaLLM, model_name: str):
        self.llm = llm
        self._model_name = model_name

    def _convert_messages(self, messages: list[LLMMessage]) -> list[ChatMessage]:
        """转换消息格式为 LlamaIndex 格式"""
        converted = []
        for msg in messages:
            if msg.role == "system":
                converted.append(
                    ChatMessage(
                        role=MessageRole.SYSTEM,
                        content=msg.content,
                    )
                )
            elif msg.role == "user":
                converted.append(
                    ChatMessage(
                        role=MessageRole.USER,
                        content=msg.content,
                    )
                )
            elif msg.role == "assistant":
                converted.append(
                    ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=msg.content,
                    )
                )
        return converted

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """聊天接口实现（统一使用 TraceWriter 记录）"""
        from src.core.tracing.context import trace_context as async_trace_context

        start_time = time.time()
        request_id = str(uuid.uuid4())
        trace_id = get_current_trace_id()

        # 无 trace context 时自动创建
        if not trace_id:
            async with async_trace_context(f"llm_call_{self._model_name}") as auto_tid:
                return await self._chat_inner(request, request_id, start_time, auto_tid)

        return await self._chat_inner(request, request_id, start_time, trace_id)

    async def _chat_inner(self, request: LLMRequest, request_id: str,
                          start_time: float, trace_id: str) -> LLMResponse:
        """chat 内部实现，统一走 TraceWriter"""
        writer = get_trace_writer()
        span_id = None

        try:
            li_messages = self._convert_messages(request.messages)

            with create_span(f"llm_call_{self._model_name}") as span_id:
                # 记录 LLM 调用开始
                full_messages = [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.messages
                ]
                await writer.record_llm_start(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=get_parent_span_id(),
                    prompt_messages=full_messages,
                    call_parameters={
                        "model": self._model_name,
                        "scenario": request.scenario,
                        "prompt_key": request.prompt_key,
                    },
                    request_id=request_id,
                )

                # 实际调用
                response = await self.llm.achat(li_messages)
                duration_ms = int((time.time() - start_time) * 1000)

                # 估算 token（LlamaIndex 不一定返回 usage）
                input_tokens = sum(len(msg.content) for msg in request.messages) // 4
                output_tokens = (
                    len(response.message.content) // 4 if response.message.content else 0
                )

                # 记录 LLM 调用完成（非流式：ttft=None，TTFT 仅对流式有意义）
                await writer.record_llm_complete(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=get_parent_span_id(),
                    completion_message=response.message.content or "",
                    tokens={
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                    ttft=None,
                    request_id=request_id,
                )

                return LLMResponse(
                    content=response.message.content or "",
                    model_name=self._model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    duration_ms=duration_ms,
                )

        except TimeoutError as e:
            if span_id:
                await writer.record_llm_error(trace_id=trace_id, span_id=span_id, error=str(e))
            logger.error(f"LLM 调用超时：{e}")
            raise LLMTimeoutError(f"LLM 调用超时：{e}")
        except Exception as e:
            if span_id:
                await writer.record_llm_error(trace_id=trace_id, span_id=span_id, error=str(e))
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
        return self._model_name

    async def chat_stream(self, request: LLMRequest):
        """流式聊天接口（带 Tracing）"""
        from src.core.tracing.context import trace_context as async_trace_context

        trace_id = get_current_trace_id()
        if not trace_id:
            async with async_trace_context(f"llm_stream_{self._model_name}") as auto_tid:
                async for chunk in self._stream_with_tracing(request, auto_tid):
                    yield chunk
        else:
            async for chunk in self._stream_with_tracing(request, trace_id):
                yield chunk

    async def _stream_with_tracing(self, request: LLMRequest, trace_id: str):
        """流式调用核心逻辑，带 Tracing 埋点"""
        writer = get_trace_writer()
        start_time = time.time()

        with create_span(f"llm_stream_{self._model_name}") as span_id:
            full_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]
            await writer.record_llm_start(
                trace_id=trace_id, span_id=span_id,
                parent_span_id=get_parent_span_id(),
                prompt_messages=full_messages,
                call_parameters={"model": self._model_name, "scenario": request.scenario, "prompt_key": request.prompt_key},
            )

            first_token_time = None
            accumulated_text = []

            try:
                li_messages = self._convert_messages(request.messages)
                async for response in self.llm.astream_chat(li_messages):
                    delta = response.delta if hasattr(response, "delta") else ""
                    if delta:
                        if first_token_time is None:
                            first_token_time = time.time()
                        accumulated_text.append(delta)
                        yield delta

                # 流式完成
                ttft = int((first_token_time - start_time) * 1000) if first_token_time else 0
                completion_text = "".join(accumulated_text)
                input_tokens = sum(len(msg.content) for msg in request.messages) // 4
                output_tokens = len(completion_text) // 4

                await writer.record_llm_complete(
                    trace_id=trace_id, span_id=span_id,
                    parent_span_id=get_parent_span_id(),
                    completion_message=completion_text,
                    tokens={"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens},
                    ttft=ttft,
                )

            except Exception as e:
                await writer.record_llm_error(trace_id=trace_id, span_id=span_id, error=str(e))
                raise
