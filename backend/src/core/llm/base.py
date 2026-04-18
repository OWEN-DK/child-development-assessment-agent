from abc import ABC, abstractmethod
from typing import Any, Optional

from src.schemas import LLMRequest, LLMResponse


class LLMService(ABC):
    """LLM 服务统一接口"""

    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """聊天接口"""
        pass

    @abstractmethod
    async def chat_with_retry(
        self, request: LLMRequest, max_retries: int = 3
    ) -> LLMResponse:
        """带重试的聊天接口"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """获取当前模型名称"""
        pass

    async def chat_stream(self, request: LLMRequest):
        """流式聊天接口，返回 async generator of str chunks"""
        raise NotImplementedError("Streaming not supported by this adapter")


class LLMError(Exception):
    """LLM 调用基础异常"""

    pass


class LLMTimeoutError(LLMError):
    """LLM 调用超时"""

    pass


class LLMRateLimitError(LLMError):
    """LLM 调用频率限制"""

    pass


class LLMUnavailableError(LLMError):
    """LLM 服务不可用"""

    pass
