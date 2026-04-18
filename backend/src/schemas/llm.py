"""LLM 模块模型

包含 LLM 调用相关的 Pydantic 模型：
- Message: 统一消息结构
- LLMMessage: LLM 消息结构
- LLMResponse: LLM 响应结构
- LLMRequest: LLM 请求结构
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """消息角色"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """统一消息结构，屏蔽框架差异"""

    role: MessageRole = Field(description="消息角色")
    content: str = Field(description="消息内容")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


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
    scenario: Optional[str] = None
    prompt_key: Optional[str] = None
