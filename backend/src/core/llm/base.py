from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from enum import Enum as PyEnum


class MessageRole(PyEnum):
    """消息角色枚举"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """统一消息结构，屏蔽框架差异"""

    role: MessageRole = Field(description="消息角色")
    content: str = Field(description="消息内容")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")

    def to_langchain(self) -> "BaseMessage":
        """转换为 LangChain 消息格式"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        if self.role == MessageRole.SYSTEM:
            return SystemMessage(content=self.content)
        elif self.role == MessageRole.USER:
            return HumanMessage(content=self.content)
        elif self.role == MessageRole.ASSISTANT:
            return AIMessage(content=self.content)
        else:
            raise ValueError(f"Unknown role: {self.role}")

    def to_llamaindex(self) -> "ChatMessage":
        """转换为 LlamaIndex 消息格式"""
        from llama_index.core.llms import ChatMessage, MessageRole as LIMessageRole

        role_map = {
            MessageRole.SYSTEM: LIMessageRole.SYSTEM,
            MessageRole.USER: LIMessageRole.USER,
            MessageRole.ASSISTANT: LIMessageRole.ASSISTANT,
        }

        return ChatMessage(
            role=role_map[self.role],
            content=self.content,
        )

    @classmethod
    def from_langchain(cls, message: "BaseMessage") -> "Message":
        """从 LangChain 消息转换"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        if isinstance(message, SystemMessage):
            role = MessageRole.SYSTEM
        elif isinstance(message, HumanMessage):
            role = MessageRole.USER
        elif isinstance(message, AIMessage):
            role = MessageRole.ASSISTANT
        else:
            raise ValueError(f"Unknown message type: {type(message)}")

        return cls(role=role, content=message.content)

    @classmethod
    def from_llamaindex(cls, message: "ChatMessage") -> "Message":
        """从 LlamaIndex 消息转换"""
        from llama_index.core.llms import MessageRole as LIMessageRole

        role_map = {
            LIMessageRole.SYSTEM: MessageRole.SYSTEM,
            LIMessageRole.USER: MessageRole.USER,
            LIMessageRole.ASSISTANT: MessageRole.ASSISTANT,
        }

        return cls(
            role=role_map[message.role],
            content=message.content or "",
        )


class LLMMessage(BaseModel):
    """LLM 消息结构"""

    role: str  # "system", "user", "assistant"
    content: str


class LLMResponse(BaseModel):
    """LLM 响应结构"""

    content: str
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: int
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)


class LLMRequest(BaseModel):
    """LLM 请求结构"""

    messages: list[LLMMessage]
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    timeout: int = 30
    scenario: Optional[str] = None  # 使用场景（用于监控和 A/B 测试）
    prompt_key: Optional[str] = None  # 提示词键（用于监控）


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
