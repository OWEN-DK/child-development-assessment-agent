# Phase 2: LLM 服务工厂重构

> 本文档是 MySQL + Redis 集成重构实施方案的一部分
> 
> **返回索引：** [README.md](./README.md) | [项目概览](./00-overview.md)

---

## Phase 2: LLM 服务工厂重构（周期：3 天）

### 目标
实现 LLM 服务统一抽象层，支持 LangChain 和 LlamaIndex 双适配器，通过工厂模式按场景动态生成实例，为提示词管理系统和 A/B 测试提供基础设施。

### 架构设计

```
┌─────────────────────────────────────────────────┐
│           业务层 (RAG Service / Nodes)           │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│              LLM Service Factory                │
│         (按场景动态生成 LLM 实例)                  │
└─────────────────────────────────────────────────┘
                      ↓
        ┌─────────────┴─────────────┐
        ↓                           ↓
┌──────────────────┐      ┌──────────────────┐
│ LangChain Adapter│      │ LlamaIndex Adapter│
│ (qwen-plus, etc) │      │ (qwen-plus, etc) │
└──────────────────┘      └──────────────────┘
        ↓                           ↓
┌─────────────────────────────────────────────────┐
│          提示词管理器 (MySQL + Redis)            │
│     (版本控制、A/B 测试、动态加载)                │
└─────────────────────────────────────────────────┘
```

### 9 大业务场景配置表

| 场景标识 | 用途 | 框架 | 默认模型 | temperature | max_tokens | retry_count | timeout |
|---------|------|------|---------|-------------|------------|-------------|---------|
| `report_generation` | 生成评估报告 | LlamaIndex | qwen-plus | 0.7 | 2048 | 3 | 30 |
| `assessment` | 儿童发展评估 | LlamaIndex | qwen-plus | 0.5 | 1024 | 3 | 30 |
| `validation` | 数据校验 | LlamaIndex | qwen-turbo | 0.3 | 512 | 2 | 15 |
| `query_rewrite` | RAG 查询优化 | LangChain | qwen-turbo | 0.6 | 256 | 2 | 10 |
| `metadata_extraction` | 元数据提取 | LlamaIndex | qwen-vl-max | 0.4 | 1024 | 3 | 30 |
| `vl_parsing` | 扫描版 PDF 解析 | LlamaIndex | qwen-vl-max | 0.3 | 2048 | 3 | 60 |
| `query_classification` | 查询路由分类 | LlamaIndex | qwen3-omni-flash | 0.2 | 128 | 2 | 10 |
| `ml_scoring` | 大模型评分 | LlamaIndex | qwen-plus | 0.5 | 512 | 3 | 30 |
| `synonym_expand` | 同义词扩展 | LangChain | qwen-turbo | 0.8 | 256 | 2 | 10 |

**配置说明：**
- `temperature`: 控制输出随机性，0.0-1.0
- `max_tokens`: 最大输出 token 数
- `retry_count`: 失败重试次数
- `timeout`: 请求超时时间（秒）

---

### Task 2.1: 定义 LLM 服务统一接口

**Files:**
- Create: `backend/src/core/llm/base.py`
- Create: `backend/src/core/llm/__init__.py`

- [ ] **Step 1: 创建 LLM 服务基类**

```python
from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

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
        self, 
        request: LLMRequest, 
        max_retries: int = 3
    ) -> LLMResponse:
        """带重试的聊天接口"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """获取当前模型名称"""
        pass
```

- [ ] **Step 2: 创建异常定义**

```python
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
```

- [ ] **Step 3: 导出到__init__.py**

```python
from .base import (
    LLMService,
    LLMMessage,
    LLMResponse,
    LLMRequest,
    LLMError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMUnavailableError,
)

__all__ = [
    "LLMService",
    "LLMMessage",
    "LLMResponse",
    "LLMRequest",
    "LLMError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMUnavailableError",
]
```

---

### 补充：统一消息结构定义

**Files:**
- Modify: `backend/src/core/llm/base.py`

- [ ] **Step: 添加 Message 统一类和双向转换方法**

在 `backend/src/core/llm/base.py` 中添加：

```python
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
```

---

### Task 2.2: 实现 LangChain LLM 适配器

**Files:**
- Create: `backend/src/core/llm/adapters/langchain.py`
- Create: `backend/src/core/llm/adapters/__init__.py`

- [ ] **Step 1: 创建 LangChain 适配器**

```python
import time
from typing import Any
from langchain.chat_models.base import BaseChatModel
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from src.core.llm.base import (
    LLMService,
    LLMRequest,
    LLMResponse,
    LLMMessage,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMUnavailableError,
)
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
        
        try:
            # 转换消息
            lc_messages = self._convert_messages(request.messages)
            
            # 调用 LangChain
            response = await self.llm.ainvoke(lc_messages)
            
            # 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 估算 Token（实际应从响应中获取，这里简化处理）
            input_tokens = sum(len(msg.content) for msg in request.messages) // 4
            output_tokens = len(response.content) // 4
            
            return LLMResponse(
                content=response.content,
                model_name=self._model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                duration_ms=duration_ms,
            )
            
        except TimeoutError as e:
            logger.error(f"LLM 调用超时：{e}")
            raise LLMTimeoutError(f"LLM 调用超时：{e}")
        except Exception as e:
            if "rate limit" in str(e).lower():
                raise LLMRateLimitError(f"LLM 频率限制：{e}")
            logger.error(f"LLM 调用失败：{e}")
            raise LLMUnavailableError(f"LLM 服务不可用：{e}")
    
    async def chat_with_retry(
        self, 
        request: LLMRequest, 
        max_retries: int = 3
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
```

- [ ] **Step 2: 测试 LangChain 适配器**

```bash
cd backend
uv run python -c "
import asyncio
from langchain_dashscope import ChatDashScope
from src.core.llm.adapters.langchain import LangChainLLMAdapter
from src.core.llm.base import LLMRequest, LLMMessage

async def test():
    # 创建 LangChain LLM 实例
    llm = ChatDashScope(
        model='qwen-plus',
        dashscope_api_key='your_api_key',
    )
    
    # 创建适配器
    adapter = LangChainLLMAdapter(llm, 'qwen-plus')
    
    # 测试聊天
    request = LLMRequest(
        messages=[
            LLMMessage(role='system', content='你是一个助手'),
            LLMMessage(role='user', content='你好'),
        ],
        model_name='qwen-plus',
        temperature=0.7,
    )
    
    response = await adapter.chat(request)
    print(f'响应：{response.content}')
    print(f'Token: {response.total_tokens}')
    print(f'耗时：{response.duration_ms}ms')

asyncio.run(test())
"
```

**Expected:** 成功调用 LLM，返回响应和 Token 信息。

---

### Task 2.3: 实现 LlamaIndex LLM 适配器

**Files:**
- Create: `backend/src/core/llm/adapters/llamaindex.py`

- [ ] **Step 1: 创建 LlamaIndex 适配器**

```python
import time
from typing import Any
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms import LLM as LlamaLLM
from src.core.llm.base import (
    LLMService,
    LLMRequest,
    LLMResponse,
    LLMMessage,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMUnavailableError,
)
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
                converted.append(ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=msg.content,
                ))
            elif msg.role == "user":
                converted.append(ChatMessage(
                    role=MessageRole.USER,
                    content=msg.content,
                ))
            elif msg.role == "assistant":
                converted.append(ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=msg.content,
                ))
        return converted
    
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """聊天接口实现"""
        start_time = time.time()
        
        try:
            # 转换消息
            li_messages = self._convert_messages(request.messages)
            
            # 调用 LlamaIndex
            response = await self.llm.achat(li_messages)
            
            # 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 估算 Token
            input_tokens = sum(len(msg.content) for msg in request.messages) // 4
            output_tokens = len(response.message.content) // 4 if response.message.content else 0
            
            return LLMResponse(
                content=response.message.content or "",
                model_name=self._model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                duration_ms=duration_ms,
            )
            
        except TimeoutError as e:
            logger.error(f"LLM 调用超时：{e}")
            raise LLMTimeoutError(f"LLM 调用超时：{e}")
        except Exception as e:
            if "rate limit" in str(e).lower():
                raise LLMRateLimitError(f"LLM 频率限制：{e}")
            logger.error(f"LLM 调用失败：{e}")
            raise LLMUnavailableError(f"LLM 服务不可用：{e}")
    
    async def chat_with_retry(
        self, 
        request: LLMRequest, 
        max_retries: int = 3
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
```

- [ ] **Step 2: 测试 LlamaIndex 适配器**

```bash
cd backend
uv run python -c "
import asyncio
from llama_index.llms.dashscope import DashScope
from src.core.llm.adapters.llamaindex import LlamaIndexLLMAdapter
from src.core.llm.base import LLMRequest, LLMMessage

async def test():
    # 创建 LlamaIndex LLM 实例
    llm = DashScope(
        model='qwen-plus',
        api_key='your_api_key',
    )
    
    # 创建适配器
    adapter = LlamaIndexLLMAdapter(llm, 'qwen-plus')
    
    # 测试聊天
    request = LLMRequest(
        messages=[
            LLMMessage(role='system', content='你是一个助手'),
            LLMMessage(role='user', content='你好'),
        ],
        model_name='qwen-plus',
        temperature=0.7,
    )
    
    response = await adapter.chat(request)
    print(f'响应：{response.content}')
    print(f'Token: {response.total_tokens}')
    print(f'耗时：{response.duration_ms}ms')

asyncio.run(test())
"
```

**Expected:** 成功调用 LLM，返回响应和 Token 信息。

---

### Task 2.4: 实现 LLM 服务工厂

**Files:**
- Create: `backend/src/core/llm/factory.py`

- [ ] **Step 1: 创建 LLM 工厂**

```python
from typing import Optional
from langchain_dashscope import ChatDashScope
from llama_index.llms.dashscope import DashScope
from src.config import settings
from src.core.llm.base import LLMService
from src.core.llm.adapters.langchain import LangChainLLMAdapter
from src.core.llm.adapters.llamaindex import LlamaIndexLLMAdapter
from src.utils.logger import logger

class LLMFramework:
    """LLM 框架枚举"""
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"

class LLMServiceFactory:
    """LLM 服务工厂（按场景动态生成实例）"""
    
    _instances: dict[str, LLMService] = {}
    
    @classmethod
    def create(
        cls,
        framework: str = LLMFramework.LANGCHAIN,
        model_name: Optional[str] = None,
        scenario: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMService:
        """
        创建 LLM 服务实例
        
        Args:
            framework: LLM 框架（langchain/llamaindex）
            model_name: 模型名称（默认从配置读取）
            scenario: 使用场景（用于 A/B 测试）
            temperature: 温度参数
            max_tokens: 最大 Token 数
        """
        # 生成缓存键
        cache_key = f"{framework}:{model_name}:{scenario}"
        
        # 检查缓存
        if cache_key in cls._instances:
            logger.debug(f"LLM 实例已缓存：{cache_key}")
            return cls._instances[cache_key]
        
        # 使用配置中的默认模型
        model_name = model_name or settings.llm.model
        
        # 创建 LLM 实例
        if framework == LLMFramework.LANGCHAIN:
            llm = ChatDashScope(
                model=model_name,
                dashscope_api_key=settings.llm.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            instance = LangChainLLMAdapter(llm, model_name)
            logger.info(f"LangChain LLM 实例已创建：{model_name}")
            
        elif framework == LLMFramework.LLAMAINDEX:
            llm = DashScope(
                model=model_name,
                api_key=settings.llm.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            instance = LlamaIndexLLMAdapter(llm, model_name)
            logger.info(f"LlamaIndex LLM 实例已创建：{model_name}")
            
        else:
            raise ValueError(f"不支持的 LLM 框架：{framework}")
        
        # 缓存实例
        cls._instances[cache_key] = instance
        
        return instance
    
    @classmethod
    def clear_cache(cls):
        """清空实例缓存（用于配置变更后）"""
        cls._instances.clear()
        logger.info("LLM 实例缓存已清空")
```

- [ ] **Step 2: 测试工厂模式**

```bash
cd backend
uv run python -c "
from src.core.llm.factory import LLMServiceFactory, LLMFramework

# 测试创建 LangChain 实例
llm1 = LLMServiceFactory.create(
    framework=LLMFramework.LANGCHAIN,
    model_name='qwen-plus',
    scenario='rag_query_rewrite',
)
print(f'LangChain 实例：{llm1.get_model_name()}')

# 测试创建 LlamaIndex 实例
llm2 = LLMServiceFactory.create(
    framework=LLMFramework.LLAMAINDEX,
    model_name='qwen-plus',
    scenario='assessment',
)
print(f'LlamaIndex 实例：{llm2.get_model_name()}')

# 测试缓存命中
llm3 = LLMServiceFactory.create(
    framework=LLMFramework.LANGCHAIN,
    model_name='qwen-plus',
    scenario='rag_query_rewrite',
)
print(f'缓存命中：{llm1 is llm3}')

# 测试清空缓存
LLMServiceFactory.clear_cache()
print('缓存已清空')
"
```

**Expected:** 工厂正确创建和缓存 LLM 实例。

---

### Task 2.5: 集成到 RAG 流水线

**Files:**
- Modify: `backend/src/service/retrieval_service.py`
- Modify: `backend/src/core/nodes/preprocessing.py`
- Modify: `backend/src/core/nodes/validation.py`
- Modify: `backend/src/core/nodes/assessment.py`
- Modify: `backend/src/core/nodes/reporting.py`

- [ ] **Step 1: 更新 retrieval_service.py 使用工厂**

```python
# 在文件顶部添加导入
from src.core.llm.factory import LLMServiceFactory, LLMFramework

# 替换原有的 LLM 调用
class RetrievalService:
    # ... 现有代码 ...
    
    async def _rewrite_query(self, query: str, age: float) -> str:
        """查询重写"""
        # 使用工厂创建 LLM 实例
        llm = LLMServiceFactory.create(
            framework=LLMFramework.LANGCHAIN,
            model_name='qwen-plus',
            scenario='rag_query_rewrite',
            temperature=0.3,
        )
        
        # 构建提示词
        from src.core.prompts import RAG_QUERY_REWRITE_PROMPT
        messages = [
            LLMMessage(role='system', content='你是一个查询优化专家'),
            LLMMessage(role='user', content=RAG_QUERY_REWRITE_PROMPT.format(query=query, age=age)),
        ]
        
        # 调用 LLM
        response = await llm.chat(
            LLMRequest(
                messages=messages,
                model_name='qwen-plus',
                temperature=0.3,
                max_tokens=512,
                scenario='rag_query_rewrite',
                prompt_key='rag_query_rewrite',
            )
        )
        
        return response.content
```

- [ ] **Step 2: 更新 assessment.py 使用工厂**

```python
# 在 assessment.py 中添加导入
from src.core.llm.factory import LLMServiceFactory, LLMFramework

# 替换 AssessmentNode 中的 LLM 调用
class AssessmentNode:
    async def __call__(self, state: AgentState) -> AgentState:
        # ... 现有代码 ...
        
        # 使用工厂创建 LLM 实例
        llm = LLMServiceFactory.create(
            framework=LLMFramework.LANGCHAIN,
            model_name='qwen-plus',
            scenario='child_assessment',
            temperature=0.7,
        )
        
        # 构建提示词
        from src.core.prompts import CHILD_ASSESSMENT_PROMPT
        messages = [
            LLMMessage(role='system', content='你是一个儿童发展评估专家'),
            LLMMessage(role='user', content=CHILD_ASSESSMENT_PROMPT.format(
                child_profile=state.child_profile,
                condensed_context=state.condensed_context,
            )),
        ]
        
        # 调用 LLM
        response = await llm.chat(
            LLMRequest(
                messages=messages,
                model_name='qwen-plus',
                temperature=0.7,
                max_tokens=2048,
                scenario='child_assessment',
                prompt_key='child_assessment',
            )
        )
        
        # 解析响应
        child_state = self._parse_response(response.content)
        state.child_state = child_state
        
        return state
```

- [ ] **Step 3: 更新 reporting.py 使用工厂**

```python
# 在 reporting.py 中添加导入
from src.core.llm.factory import LLMServiceFactory, LLMFramework

# 替换 ReportingNode 中的 LLM 调用
class ReportingNode:
    async def __call__(self, state: AgentState) -> AgentState:
        # ... 现有代码 ...
        
        # 使用工厂创建 LLM 实例
        llm = LLMServiceFactory.create(
            framework=LLMFramework.LANGCHAIN,
            model_name='qwen-plus',
            scenario='report_generation',
            temperature=0.7,
        )
        
        # 构建提示词
        from src.core.prompts import REPORT_GENERATION_PROMPT
        messages = [
            LLMMessage(role='system', content='你是一个专业的报告撰写人'),
            LLMMessage(role='user', content=REPORT_GENERATION_PROMPT.format(
                child_profile=state.child_profile,
                child_state=state.child_state,
                evaluation_result=state.evaluation_result,
                retrieved_docs=state.retrieved_docs,
            )),
        ]
        
        # 调用 LLM
        response = await llm.chat(
            LLMRequest(
                messages=messages,
                model_name='qwen-plus',
                temperature=0.7,
                max_tokens=4096,
                scenario='report_generation',
                prompt_key='report_generation',
            )
        )
        
        state.final_report = response.content
        
        return state
```

- [ ] **Step 4: 测试集成**

```bash
cd backend
uv run python -c "
import asyncio
from src.core.llm.factory import LLMServiceFactory, LLMFramework
from src.core.llm.base import LLMRequest, LLMMessage

async def test_integration():
    # 测试不同场景的 LLM 调用
    scenarios = [
        'rag_query_rewrite',
        'child_assessment',
        'report_generation',
    ]
    
    for scenario in scenarios:
        llm = LLMServiceFactory.create(
            framework=LLMFramework.LANGCHAIN,
            model_name='qwen-plus',
            scenario=scenario,
        )
        
        request = LLMRequest(
            messages=[
                LLMMessage(role='user', content=f'Test for {scenario}'),
            ],
            model_name='qwen-plus',
            scenario=scenario,
            prompt_key=f'test_{scenario}',
        )
        
        response = await llm.chat(request)
        print(f'{scenario}: {response.content[:50]}...')

asyncio.run(test_integration())
"
```

**Expected:** 所有场景的 LLM 调用正常。

### Task 2.6: 延迟显式释放机制
**Files:**
- Modify: `backend/src/core/llm/factory.py`

- [ ] **Step 1: 添加 delayed_dispose 协程**
```python
# backend/src/core/llm/factory.py
import asyncio
from src.utils.logger import logger

class LLMServiceFactory:
    # ... 现有代码 ...
    
    @classmethod
    async def _dispose_old_instance(cls, instance, delay: int = 60):
        """延迟显式释放 LLM 实例（等待进行中的请求完成）"""
        logger.info(f"LLM 实例延迟释放已调度：{delay} 秒后释放")
        await asyncio.sleep(delay)
        try:
            if hasattr(instance, 'dispose'):
                await instance.dispose()
                logger.info(f"LLM 实例已显式释放")
        except Exception as e:
            logger.warning(f"LLM 实例释放失败（可忽略）: {e}")
    
    @classmethod
    def invalidate_scene(cls, scene: str):
        """使指定场景的缓存实例失效（触发延迟释放）"""
        if scene in cls._instance_cache:
            old_instance = cls._instance_cache.pop(scene)
            asyncio.create_task(cls._dispose_old_instance(old_instance))
            logger.info(f"场景 {scene} 的 LLM 实例已标记失效")
```

### Task 2.7: API Key 脱敏工具
**Files:**
- Modify: `backend/src/core/crypto.py` (复用 Phase 1 创建的加密工具)

- [ ] **Step 1: 在配置接口返回时脱敏**
```python
# backend/src/controller/config_controller.py
from src.core.crypto import crypto_service

async def get_llm_config(scene: str):
    """获取 LLM 场景配置（API Key 脱敏）"""
    config = await config_manager.get_llm_config(scene)
    
    # 脱敏处理
    if config.get("api_key"):
        config["api_key"] = crypto_service.mask_api_key(config["api_key"])
    
    return config
```

### Phase 2 完成验证

- [ ] 运行单元测试，验证所有适配器功能正常
- [ ] 测试工厂模式，确认实例缓存生效
- [ ] 验证 RAG 流水线中 LLM 调用正常
- [ ] 检查日志中 LLM 调用记录完整
- [ ] 确认监控数据正确采集（Token、耗时、错误率）

---

**返回索引：** [README.md](./README.md)
