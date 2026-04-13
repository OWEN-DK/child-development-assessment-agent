import time
import uuid
from typing import Any
from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.core.llm.base import (
    LLMService,
    LLMRequest,
    LLMResponse,
    LLMMessage,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMUnavailableError,
)
from src.core.llm.log_collector import LLMLogCollector
from src.utils.logger import logger


class LangChainLLMAdapter(LLMService):
    """LangChain LLM 适配器"""

    def __init__(self, llm: BaseChatModel, model_name: str):
        self.llm = llm
        self._model_name = model_name

    def _convert_messages(self, messages: list[LLMMessage]) -> list:
        """转换消息格式为 LangChain 格式"""
        converted = []
        for msg in messages:
            if msg.role == "system":
                converted.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                converted.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                converted.append(AIMessage(content=msg.content))
        return converted

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """聊天接口实现"""
        start_time = time.time()
        request_id = str(uuid.uuid4())

        try:
            lc_messages = self._convert_messages(request.messages)

            response = await self.llm.ainvoke(lc_messages)

            duration_ms = int((time.time() - start_time) * 1000)

            input_tokens = sum(len(msg.content) for msg in request.messages) // 4
            output_tokens = len(response.content) // 4

            llm_response = LLMResponse(
                content=response.content,
                model_name=self._model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                duration_ms=duration_ms,
            )

            await LLMLogCollector.submit(
                {
                    "request_id": request_id,
                    "model_name": self._model_name,
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
            await LLMLogCollector.submit(
                {
                    "request_id": request_id,
                    "model_name": self._model_name,
                    "prompt_key": request.prompt_key,
                    "scenario": request.scenario,
                    "status": "timeout",
                    "error_message": str(e),
                }
            )
            logger.error(f"LLM 调用超时：{e}")
            raise LLMTimeoutError(f"LLM 调用超时：{e}")
        except Exception as e:
            await LLMLogCollector.submit(
                {
                    "request_id": request_id,
                    "model_name": self._model_name,
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
        return self._model_name

    async def chat_stream(self, request: LLMRequest):
        """流式聊天接口"""
        lc_messages = self._convert_messages(request.messages)
        async for chunk in self.llm.astream(lc_messages):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content
