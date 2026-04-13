# LangChain + LlamaIndex 全模型支持实施方案

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现支持多模型提供商、双框架、热更新的统一大模型服务层，替换所有硬编码模型调用
**Architecture:** 统一抽象接口 + 双框架适配器 + 工厂模式 + 事件总线热更新 + DI工厂注入
**Tech Stack:** Python 3.13, LangChain, LlamaIndex, Injector, Pydantic

> **当前进度**: 已完成阶段1（基础架构搭建）的所有7个任务，包括抽象接口定义、多框架适配器实现、事件总线扩展、配置系统扩展、LLM服务工厂实现、DI容器改造。当前已进入阶段2（业务代码迁移），正在进行Task 8（LangGraph节点迁移）。

---

## 阶段 1：基础架构搭建

### Task 1: 创建LLM基础抽象接口 ✅ 已完成

**Files:**
- Create: `backend/src/core/llm/base.py`

- [x] **Step 1: 编写接口代码**

```python
from abc import ABC, abstractmethod
from typing import Optional, Any, AsyncGenerator, List
from pathlib import Path


class ILLMService(ABC):
    """大模型服务统一抽象接口（与框架无关）"""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """同步生成文本"""
        pass
    
    @abstractmethod
    async def agenerate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """异步生成文本"""
        pass
    
    @abstractmethod
    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Any:
        """同步流式生成"""
        pass
    
    @abstractmethod
    async def astream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """异步流式生成"""
        pass
    
    def dispose(self) -> None:
        """清理资源（关闭连接池、释放异步资源等）"""
        pass


class IVLMService(ABC):
    """多模态大模型服务接口（支持图片输入）"""
    
    @abstractmethod
    async def agenerate_with_images(
        self,
        prompt: str,
        images: List[Any],  # 可以是 PIL.Image、base64 字符串或文件路径
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """异步生成文本（支持图片输入）"""
        pass
    
    def dispose(self) -> None:
        """清理资源"""
        pass
```

- [x] **Step 2: 验证语法正确性**

Run: `cd backend && python -c "from src.core.llm.base import ILLMService, IVLMService; print('Interfaces loaded successfully')"`
Expected: `Interfaces loaded successfully`
> 验证结果：✅ 已通过

- [x] **Step 3: Commit**

```bash
git add backend/src/core/llm/base.py
git commit -m "feat: add LLM service abstract interfaces"
```

---

### Task 2: 实现LangChain适配器 ✅ 已完成

**Files:**
- Create: `backend/src/core/llm/adapters/langchain/__init__.py`
- Create: `backend/src/core/llm/adapters/langchain/tongyi.py`
- Create: `backend/src/core/llm/adapters/langchain/openai.py`
- Create: `backend/src/core/llm/adapters/langchain/anthropic.py`
- Create: `backend/src/core/llm/adapters/langchain/ollama.py`

- [ ] **Step 1: 编写通义千问适配器**

```python
# backend/src/core/llm/adapters/langchain/tongyi.py
from typing import Optional, Any, AsyncGenerator
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.llm.base import ILLMService


class LangChainTongyiLLMService(ILLMService):
    """LangChain 通义千问适配器"""
    
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None, **kwargs):
        self._model = ChatTongyi(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )
    
    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return messages
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = self._build_messages(prompt, system_prompt)
        return self._model.invoke(messages, **kwargs).content
    
    async def agenerate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = self._build_messages(prompt, system_prompt)
        response = await self._model.ainvoke(messages, **kwargs)
        return response.content
    
    def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Any:
        messages = self._build_messages(prompt, system_prompt)
        return self._model.stream(messages, **kwargs)
    
    async def astream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        messages = self._build_messages(prompt, system_prompt)
        async for chunk in self._model.astream(messages, **kwargs):
            yield chunk.content
    
    def dispose(self) -> None:
        """LangChain 模型无需特殊清理"""
        self._model = None
```

- [ ] **Step 2: 编写OpenAI适配器**

```python
# backend/src/core/llm/adapters/langchain/openai.py
from typing import Optional, Any, AsyncGenerator
from langchain_community.chat_models import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.llm.base import ILLMService


class LangChainOpenAILLMService(ILLMService):
    """LangChain OpenAI 适配器"""
    
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None, **kwargs):
        self._model = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )
    
    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return messages
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = self._build_messages(prompt, system_prompt)
        return self._model.invoke(messages, **kwargs).content
    
    async def agenerate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = self._build_messages(prompt, system_prompt)
        response = await self._model.ainvoke(messages, **kwargs)
        return response.content
    
    def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Any:
        messages = self._build_messages(prompt, system_prompt)
        return self._model.stream(messages, **kwargs)
    
    async def astream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        messages = self._build_messages(prompt, system_prompt)
        async for chunk in self._model.astream(messages, **kwargs):
            yield chunk.content
    
    def dispose(self) -> None:
        self._model = None
```

- [ ] **Step 3: 编写Anthropic适配器**

```python
# backend/src/core/llm/adapters/langchain/anthropic.py
from typing import Optional, Any, AsyncGenerator
from langchain_community.chat_models import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.llm.base import ILLMService


class LangChainAnthropicLLMService(ILLMService):
    """LangChain Anthropic 适配器"""
    
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None, **kwargs):
        self._model = ChatAnthropic(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )
    
    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return messages
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = self._build_messages(prompt, system_prompt)
        return self._model.invoke(messages, **kwargs).content
    
    async def agenerate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = self._build_messages(prompt, system_prompt)
        response = await self._model.ainvoke(messages, **kwargs)
        return response.content
    
    def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Any:
        messages = self._build_messages(prompt, system_prompt)
        return self._model.stream(messages, **kwargs)
    
    async def astream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        messages = self._build_messages(prompt, system_prompt)
        async for chunk in self._model.astream(messages, **kwargs):
            yield chunk.content
    
    def dispose(self) -> None:
        self._model = None
```

- [ ] **Step 4: 编写Ollama适配器**

```python
# backend/src/core/llm/adapters/langchain/ollama.py
from typing import Optional, Any, AsyncGenerator
from langchain_community.chat_models.ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.llm.base import ILLMService


class LangChainOllamaLLMService(ILLMService):
    """LangChain Ollama 适配器"""
    
    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        self._model = ChatOllama(
            model=model,
            base_url=base_url,
            **kwargs
        )
    
    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return messages
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = self._build_messages(prompt, system_prompt)
        return self._model.invoke(messages, **kwargs).content
    
    async def agenerate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = self._build_messages(prompt, system_prompt)
        response = await self._model.ainvoke(messages, **kwargs)
        return response.content
    
    def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Any:
        messages = self._build_messages(prompt, system_prompt)
        return self._model.stream(messages, **kwargs)
    
    async def astream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        messages = self._build_messages(prompt, system_prompt)
        async for chunk in self._model.astream(messages, **kwargs):
            yield chunk.content
    
    def dispose(self) -> None:
        self._model = None
```

- [ ] **Step 5: 编写通义千问多模态适配器**

```python
# backend/src/core/llm/adapters/langchain/tongyi_vl.py
from typing import Optional, List, Any
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.llm.base import IVLMService


class LangChainTongyiVLService(IVLMService):
    """LangChain 通义千问多模态适配器"""
    
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None, **kwargs):
        self._model = ChatTongyi(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )
    
    async def agenerate_with_images(
        self,
        prompt: str,
        images: List[Any],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        
        # 构建包含图片的消息内容
        content = [{"type": "text", "text": prompt}]
        for img in images:
            if isinstance(img, str):
                # 支持base64或url
                content.append({"type": "image_url", "image_url": {"url": img}})
            else:
                # 支持PIL Image
                import base64
                from io import BytesIO
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}})
        
        messages.append(HumanMessage(content=content))
        
        # 调用模型
        params = {}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        params.update(kwargs)
        
        response = await self._model.ainvoke(messages, **params)
        return response.content
    
    def dispose(self) -> None:
        self._model = None
```

- [ ] **Step 6: 编写__init__.py导出适配器**

```python
# backend/src/core/llm/adapters/langchain/__init__.py
from .tongyi import LangChainTongyiLLMService
from .openai import LangChainOpenAILLMService
from .anthropic import LangChainAnthropicLLMService
from .ollama import LangChainOllamaLLMService

__all__ = [
    "LangChainTongyiLLMService",
    "LangChainOpenAILLMService",
    "LangChainAnthropicLLMService",
    "LangChainOllamaLLMService",
]
```

- [ ] **Step 6: 验证适配器语法**

Run: `cd backend && python -c "from src.core.llm.adapters.langchain import *; print('LangChain adapters loaded successfully')"`
Expected: `LangChain adapters loaded successfully`

- [ ] **Step 7: Commit**

```bash
git add backend/src/core/llm/adapters/langchain/
git commit -m "feat: implement LangChain adapters for all providers"
```

---

### Task 3: 实现LlamaIndex适配器 ✅ 已完成

**Files:**
- Create: `backend/src/core/llm/adapters/llamaindex/__init__.py`
- Create: `backend/src/core/llm/adapters/llamaindex/tongyi.py`
- Create: `backend/src/core/llm/adapters/llamaindex/openai.py`
- Create: `backend/src/core/llm/adapters/llamaindex/ollama.py`

- [ ] **Step 1: 编写通义千问适配器**

```python
# backend/src/core/llm/adapters/llamaindex/tongyi.py
from typing import Optional, Any, AsyncGenerator
from llama_index.llms.dashscope import DashScope
from llama_index.core.llms import ChatMessage, MessageRole
from src.core.llm.base import ILLMService


class LlamaIndexTongyiLLMService(ILLMService):
    """LlamaIndex 通义千问适配器"""
    
    def __init__(self, model: str, api_key: str, **kwargs):
        self._model = DashScope(
            model=model,
            api_key=api_key,
            **kwargs
        )
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        response = self._model.chat(messages, **kwargs)
        return str(response.message.content)
    
    async def agenerate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        response = await self._model.achat(messages, **kwargs)
        return str(response.message.content)
    
    def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Any:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        return self._model.stream_chat(messages, **kwargs)
    
    async def astream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        async for response in await self._model.astream_chat(messages, **kwargs):
            yield str(response.delta)
    
    def dispose(self) -> None:
        """LlamaIndex 模型无需特殊清理"""
        self._model = None
```

- [ ] **Step 2: 编写OpenAI适配器**

```python
# backend/src/core/llm/adapters/llamaindex/openai.py
from typing import Optional, Any, AsyncGenerator
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import ChatMessage, MessageRole
from src.core.llm.base import ILLMService


class LlamaIndexOpenAILLMService(ILLMService):
    """LlamaIndex OpenAI 适配器"""
    
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None, **kwargs):
        self._model = OpenAI(
            model=model,
            api_key=api_key,
            api_base=base_url,
            **kwargs
        )
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        response = self._model.chat(messages, **kwargs)
        return str(response.message.content)
    
    async def agenerate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        response = await self._model.achat(messages, **kwargs)
        return str(response.message.content)
    
    def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Any:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        return self._model.stream_chat(messages, **kwargs)
    
    async def astream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        async for response in await self._model.astream_chat(messages, **kwargs):
            yield str(response.delta)
    
    def dispose(self) -> None:
        self._model = None
```

- [ ] **Step 3: 编写Ollama适配器**

```python
# backend/src/core/llm/adapters/llamaindex/ollama.py
from typing import Optional, Any, AsyncGenerator
from llama_index.llms.ollama import Ollama
from llama_index.core.llms import ChatMessage, MessageRole
from src.core.llm.base import ILLMService


class LlamaIndexOllamaLLMService(ILLMService):
    """LlamaIndex Ollama 适配器"""
    
    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        self._model = Ollama(
            model=model,
            base_url=base_url,
            **kwargs
        )
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        response = self._model.chat(messages, **kwargs)
        return str(response.message.content)
    
    async def agenerate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        response = await self._model.achat(messages, **kwargs)
        return str(response.message.content)
    
    def stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Any:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        return self._model.stream_chat(messages, **kwargs)
    
    async def astream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        async for response in await self._model.astream_chat(messages, **kwargs):
            yield str(response.delta)
    
    def dispose(self) -> None:
        self._model = None
```

- [ ] **Step 4: 编写__init__.py导出适配器**

```python
# backend/src/core/llm/adapters/llamaindex/__init__.py
from .tongyi import LlamaIndexTongyiLLMService
from .openai import LlamaIndexOpenAILLMService
from .ollama import LlamaIndexOllamaLLMService

__all__ = [
    "LlamaIndexTongyiLLMService",
    "LlamaIndexOpenAILLMService",
    "LlamaIndexOllamaLLMService",
]
```

- [ ] **Step 5: 验证适配器语法**

Run: `cd backend && python -c "from src.core.llm.adapters.llamaindex import *; print('LlamaIndex adapters loaded successfully')"`
Expected: `LlamaIndex adapters loaded successfully`

- [ ] **Step 6: Commit**

```bash
git add backend/src/core/llm/adapters/llamaindex/
git commit -m "feat: implement LlamaIndex adapters for all providers"
```

---

### Task 4: 扩展事件总线支持模型配置变更 ✅ 已完成

**Files:**
- Modify: `backend/src/core/event_bus.py`

- [ ] **Step 1: 更新事件总线代码**

```python
import asyncio
import time
from collections import defaultdict
from typing import Type, Dict, List, Callable, Any
from src.utils.logger import logger


class BaseEvent:
    """事件基类"""
    def __init__(self):
        self.timestamp = time.time()


class ModelConfigChangedEvent(BaseEvent):
    """模型配置变更事件"""
    def __init__(self, changed_scenes: List[str]):
        super().__init__()
        self.changed_scenes = changed_scenes


class EventBus:
    """事件总线，支持同步和异步回调"""
    _sync_subscribers: Dict[Type[BaseEvent], List[Callable[[Any], None]]] = defaultdict(list)
    _async_subscribers: Dict[Type[BaseEvent], List[Callable[[Any], Any]]] = defaultdict(list)
    
    @classmethod
    def subscribe(cls, event_type: Type[BaseEvent], callback: Callable[[Any], None]) -> None:
        """订阅同步事件"""
        cls._sync_subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to sync event: {event_type.__name__}")
    
    @classmethod
    def subscribe_async(cls, event_type: Type[BaseEvent], callback: Callable[[Any], Any]) -> None:
        """订阅异步事件"""
        cls._async_subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to async event: {event_type.__name__}")
    
    @classmethod
    def publish(cls, event: BaseEvent) -> None:
        """发布事件（同步+异步）"""
        event_type = type(event)
        logger.debug(f"Publishing event: {event_type.__name__}")
        
        # 同步回调
        for callback in cls._sync_subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Sync event callback failed for {event_type.__name__}: {e}")
        
        # 异步回调
        for callback in cls._async_subscribers.get(event_type, []):
            try:
                asyncio.create_task(callback(event))
            except Exception as e:
                logger.error(f"Async event callback failed for {event_type.__name__}: {e}")


# 全局事件总线实例
event_bus = EventBus()
```

- [ ] **Step 2: 验证语法正确性**

Run: `cd backend && python -c "from src.core.event_bus import event_bus, ModelConfigChangedEvent; event = ModelConfigChangedEvent(['test']); print('Event bus loaded successfully')"`
Expected: `Event bus loaded successfully`

- [ ] **Step 3: Commit**

```bash
git add backend/src/core/event_bus.py
git commit -m "feat: extend event bus with ModelConfigChangedEvent and async support"
```

---

### Task 5: 扩展配置系统增加模型相关配置 ✅ 已完成

**Files:**
- Modify: `backend/src/config/modules/models/llm.py`
- Modify: `backend/.env.dev.example`

- [ ] **Step 1: 更新模型配置类**

```python
from pydantic import Field
from pydantic_settings import BaseSettings


class ModelSettings(BaseSettings):
    # ========== 原有配置保留 ==========
    dashscope_api_key: str = Field(default="", validation_alias="DASHSCOPE_API_KEY", description="阿里云百炼API密钥")
    model_report_generation: str = Field("qwen3.5-plus", validation_alias="MODEL_REPORT_GENERATION", description="报告生成使用的模型")
    model_assessment: str = Field("qwen3.5-plus", validation_alias="MODEL_ASSESSMENT", description="评估使用的模型")
    model_validation: str = Field("qwen3.5-turbo", validation_alias="MODEL_VALIDATION", description="校验使用的模型")
    model_query_rewrite: str = Field("qwen3-omni-flash", validation_alias="MODEL_QUERY_REWRITE", description="查询重写使用的模型")
    model_metadata_extraction: str = Field("qwen3-omni-flash", validation_alias="MODEL_METADATA_EXTRACTION", description="元数据提取使用的模型")
    model_vl_parsing: str = Field("qwen3-omni-flash", validation_alias="MODEL_VL_PARSING", description="多模态解析使用的模型")
    model_query_classification: str = Field("qwen3-omni-flash", validation_alias="MODEL_QUERY_CLASSIFICATION", description="查询分类使用的模型")
    ml_scoring_qwen_model: str = Field("qwen3.5-turbo", validation_alias="ML_SCORING_QWEN_MODEL", description="ML评分使用的模型")
    model_synonym_expand: str = Field("qwen3-omni-flash", validation_alias="MODEL_SYNONYM_EXPAND", description="同义词扩展使用的模型")
    model_memory_extraction: str = Field("qwen-turbo", validation_alias="MODEL_MEMORY_EXTRACTION", description="记忆提取使用的模型")
    
    # ========== 新增通用模型提供商配置 ==========
    default_provider: str = Field(default="tongyi", validation_alias="DEFAULT_PROVIDER", description="默认模型提供商")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY", description="OpenAI API密钥")
    openai_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL", description="OpenAI接口地址")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY", description="Anthropic API密钥")
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL", description="Ollama服务地址")
    
    # ========== 新增场景提供商配置 ==========
    provider_report_generation: str = Field(default="tongyi", validation_alias="PROVIDER_REPORT_GENERATION", description="报告生成提供商")
    provider_assessment: str = Field(default="tongyi", validation_alias="PROVIDER_ASSESSMENT", description="评估场景提供商")
    provider_validation: str = Field(default="tongyi", validation_alias="PROVIDER_VALIDATION", description="校验场景提供商")
    provider_query_rewrite: str = Field(default="tongyi", validation_alias="PROVIDER_QUERY_REWRITE", description="查询重写提供商")
    provider_metadata_extraction: str = Field(default="tongyi", validation_alias="PROVIDER_METADATA_EXTRACTION", description="元数据提取提供商")
    provider_vl_parsing: str = Field(default="tongyi", validation_alias="PROVIDER_VL_PARSING", description="多模态解析提供商")
    provider_query_classification: str = Field(default="tongyi", validation_alias="PROVIDER_QUERY_CLASSIFICATION", description="查询分类提供商")
    provider_ml_scoring: str = Field(default="tongyi", validation_alias="PROVIDER_ML_SCORING", description="ML评分提供商")
    provider_synonym_expand: str = Field(default="tongyi", validation_alias="PROVIDER_SYNONYM_EXPAND", description="同义词扩展提供商")
    provider_memory_extraction: str = Field(default="tongyi", validation_alias="PROVIDER_MEMORY_EXTRACTION", description="记忆提取提供商")
    
    # ========== 高级配置 ==========
    llm_temperature: float = Field(default=0.7, validation_alias="LLM_TEMPERATURE", description="默认生成温度")
    llm_max_tokens: int = Field(default=2048, validation_alias="LLM_MAX_TOKENS", description="默认最大生成长度")
    llm_retry_count: int = Field(default=3, validation_alias="LLM_RETRY_COUNT", description="调用失败重试次数")
    llm_timeout_seconds: int = Field(default=60, validation_alias="LLM_TIMEOUT_SECONDS", description="请求超时秒数")
```

- [ ] **Step 2: 更新.env.dev.example新增配置项示例**

在文件末尾添加：
```ini
# ========== 新增多模型配置 ==========
DEFAULT_PROVIDER=tongyi
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
ANTHROPIC_API_KEY=your-anthropic-api-key
OLLAMA_BASE_URL=http://localhost:11434

# 场景提供商配置
PROVIDER_REPORT_GENERATION=tongyi
PROVIDER_ASSESSMENT=tongyi
PROVIDER_VALIDATION=tongyi
PROVIDER_QUERY_REWRITE=tongyi
PROVIDER_METADATA_EXTRACTION=tongyi
PROVIDER_VL_PARSING=tongyi
PROVIDER_QUERY_CLASSIFICATION=tongyi
PROVIDER_ML_SCORING=tongyi
PROVIDER_SYNONYM_EXPAND=tongyi
PROVIDER_MEMORY_EXTRACTION=tongyi

# LLM高级配置
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
LLM_RETRY_COUNT=3
LLM_TIMEOUT_SECONDS=60
```

- [ ] **Step 3: 验证配置加载**

Run: `cd backend && python -c "from src.config import settings; print(f'Default provider: {settings.default_provider}'); print('Config loaded successfully')"`
Expected: 
```
Default provider: tongyi
Config loaded successfully
```

- [ ] **Step 4: 扩展ConfigManager支持配置变更事件触发**

修改`backend/src/config/core/manager.py`，在配置更新回调中添加模型配置变更检测逻辑：
```python
# 在配置更新完成后的回调函数中添加
from src.core.event_bus import event_bus, ModelConfigChangedEvent

def _on_config_updated(self, old_config, new_config):
    # 检测哪些场景的模型配置发生了变更
    changed_scenes = []
    model_config_prefixes = ["model_", "provider_", "temperature_", "max_tokens_"]
    
    for key in new_config.__dict__:
        # 检查是否是模型相关配置
        if any(key.startswith(prefix) for prefix in model_config_prefixes):
            # 提取场景名称
            scene = key.split("_", 1)[1]
            if scene not in changed_scenes and getattr(old_config, key, None) != getattr(new_config, key, None):
                changed_scenes.append(scene)
    
    # 如果有模型配置变更，发布事件
    if changed_scenes:
        event_bus.publish(ModelConfigChangedEvent(changed_scenes))
        logger.info(f"检测到模型配置变更，已发布更新事件，变更场景：{changed_scenes}")
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/config/modules/models/llm.py backend/.env.dev.example
git commit -m "feat: extend config system with multi-model provider support"
```

---

### Task 6: 实现LLM服务工厂 ✅ 已完成

**Files:**
- Create: `backend/src/core/llm/factory.py`
- Modify: `backend/pyproject.toml` (新增依赖)

- [ ] **Step 1: 补充依赖到pyproject.toml**
在`pyproject.toml`的dependencies中新增：
```toml
langchain-openai = "^0.1.0"
langchain-anthropic = "^0.1.0"
llama-index-llms-openai = "^0.1.0"
```

- [ ] **Step 2: 编写工厂代码**

```python
import threading
from typing import Dict, Type, Optional
from src.core.llm.base import ILLMService, IVLMService
from src.core.llm.adapters.langchain import *
from src.core.llm.adapters.llamaindex import *
from src.config import settings
from src.core.event_bus import event_bus, ModelConfigChangedEvent
from src.utils.logger import logger


class LLMServiceFactory:
    """LLM 服务工厂（支持热更新、线程安全）"""
    
    _instances: Dict[str, ILLMService] = {}
    _lock: threading.Lock = threading.Lock()  # 实例创建锁，避免多线程重复创建
    
    # LangChain 适配器映射
    _langchain_adapters: Dict[str, Type[ILLMService]] = {
        "tongyi": LangChainTongyiLLMService,
        "openai": LangChainOpenAILLMService,
        "anthropic": LangChainAnthropicLLMService,
        "ollama": LangChainOllamaLLMService,
    }
    
    # LlamaIndex 适配器映射
    _llamaindex_adapters: Dict[str, Type[ILLMService]] = {
        "tongyi": LlamaIndexTongyiLLMService,
        "openai": LlamaIndexOpenAILLMService,
        "ollama": LlamaIndexOllamaLLMService,
    }
    
    def __init__(self):
        # 监听配置变更事件
        event_bus.subscribe(ModelConfigChangedEvent, self._on_config_changed)
    
    @classmethod
    def get_for_scene(cls, scene: str, framework: str = "llamaindex") -> ILLMService:
        """
        获取指定场景的 LLM 服务实例
        
        Args:
            scene: 场景名称（如 assessment、report_generation）
            framework: 框架类型（langchain 或 llamaindex）
        """
        cache_key = f"{framework}:{scene}"
        if cache_key not in cls._instances:
            # 双重检查锁保证线程安全
            with cls._lock:
                if cache_key not in cls._instances:
                    cls._instances[cache_key] = cls._create_instance(scene, framework)
        return cls._instances[cache_key]
    
    @classmethod
    def _create_instance(cls, scene: str, framework: str) -> ILLMService:
        """根据场景配置创建对应的 LLM 实例"""
        provider = getattr(settings, f"provider_{scene}", settings.default_provider)
        
        # 配置校验，友好提示
        try:
            model_name = getattr(settings, f"model_{scene}")
        except AttributeError:
            error_msg = f"场景 {scene} 对应的 model_{scene} 配置不存在，请检查配置文件"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 校验适配器是否存在
        adapter_map = cls._langchain_adapters if framework == "langchain" else cls._llamaindex_adapters
        if provider not in adapter_map:
            error_msg = f"不支持的模型提供商 {provider}，可用提供商：{list(adapter_map.keys())}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        adapter_cls = adapter_map[provider]
        
        # 构建适配器参数
        kwargs = cls._build_adapter_kwargs(provider, scene)
        
        return adapter_cls(model=model_name, **kwargs)
    
    @classmethod
    def _build_adapter_kwargs(cls, provider: str, scene: str) -> dict:
        """构建适配器初始化参数"""
        base_kwargs = {
            "temperature": getattr(settings, f"temperature_{scene}", settings.llm_temperature),
            "max_tokens": getattr(settings, f"max_tokens_{scene}", settings.llm_max_tokens),
            "timeout": settings.llm_timeout_seconds,
            "max_retries": settings.llm_retry_count,
        }
        
        if provider == "tongyi":
            base_kwargs["api_key"] = settings.dashscope_api_key
        elif provider == "openai":
            base_kwargs["api_key"] = settings.openai_api_key
            base_kwargs["base_url"] = settings.openai_base_url
        elif provider == "anthropic":
            base_kwargs["api_key"] = settings.anthropic_api_key
        elif provider == "ollama":
            base_kwargs["base_url"] = settings.ollama_base_url
        
        return base_kwargs
    
    @classmethod
    def _on_config_changed(cls, event: ModelConfigChangedEvent) -> None:
        """配置变更时清理旧实例"""
        for scene in event.changed_scenes:
            # 清理 LangChain 实例
            lc_key = f"langchain:{scene}"
            if lc_key in cls._instances:
                cls._instances[lc_key].dispose()
                del cls._instances[lc_key]
            
            # 清理 LlamaIndex 实例
            li_key = f"llamaindex:{scene}"
            if li_key in cls._instances:
                cls._instances[li_key].dispose()
                del cls._instances[li_key]
```

- [ ] **Step 2: 验证工厂语法**

Run: `cd backend && python -c "from src.core.llm.factory import LLMServiceFactory; factory = LLMServiceFactory(); print('LLM factory loaded successfully')"`
Expected: `LLM factory loaded successfully`

- [ ] **Step 3: Commit**

```bash
git add backend/src/core/llm/factory.py
git commit -m "feat: implement LLM service factory with hot update support"
```

---

### Task 7: 修改DI容器为工厂注入模式 ✅ 已完成

**Files:**
- Modify: `backend/src/core/di_container.py`

- [ ] **Step 1: 更新DI容器配置**

在现有模块中添加LLM模块：
```python
# 在文件头部导入
from src.core.llm import LLMServiceFactory

# 添加LLM模块
class LLMModule(Module):
    """LLM 依赖注入模块"""
    
    @provider
    @singleton
    def provide_llm_factory(self) -> LLMServiceFactory:
        """注入工厂本身，而非实例"""
        return LLMServiceFactory()
    
    @provider
    def provide_assessment_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入评估场景的 LLM 工厂函数"""
        return lambda: factory.get_for_scene("assessment", framework="llamaindex")
    
    @provider
    def provide_report_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入报告场景的 LLM 工厂函数"""
        return lambda: factory.get_for_scene("report_generation", framework="llamaindex")
    
    @provider
    def provide_validation_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入校验场景的 LLM 工厂函数"""
        return lambda: factory.get_for_scene("validation", framework="llamaindex")
    
    @provider
    def provide_query_rewrite_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入查询重写场景的 LLM 工厂函数（LangChain）"""
        return lambda: factory.get_for_scene("query_rewrite", framework="langchain")
    
    @provider
    def provide_synonym_expand_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入同义词扩展场景的 LLM 工厂函数（LangChain）"""
        return lambda: factory.get_for_scene("synonym_expand", framework="langchain")
    
    @provider
    def provide_metadata_extraction_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入元数据提取场景的 LLM 工厂函数"""
        return lambda: factory.get_for_scene("metadata_extraction", framework="llamaindex")
    
    @provider
    def provide_vl_parsing_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入多模态解析场景的 LLM 工厂函数"""
        return lambda: factory.get_for_scene("vl_parsing", framework="llamaindex")
    
    @provider
    def provide_query_classification_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入查询分类场景的 LLM 工厂函数"""
        return lambda: factory.get_for_scene("query_classification", framework="llamaindex")
    
    @provider
    def provide_ml_scoring_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入ML评分场景的 LLM 工厂函数"""
        return lambda: factory.get_for_scene("ml_scoring", framework="llamaindex")
    
    @provider
    def provide_memory_extraction_llm_factory(self, factory: LLMServiceFactory) -> callable:
        """注入记忆提取场景的 LLM 工厂函数"""
        return lambda: factory.get_for_scene("memory_extraction", framework="llamaindex")

# 在Injector初始化时添加LLMModule
injector = Injector([
    # 原有模块...
    LLMModule(),
])
```

- [ ] **Step 2: 验证DI容器加载**

Run: `cd backend && python -c "from src.core.di_container import injector; factory = injector.get(LLMServiceFactory); print('DI container loaded successfully')"`
Expected: `DI container loaded successfully`

- [ ] **Step 3: Commit**

```bash
git add backend/src/core/di_container.py
git commit -m "feat: update DI container to use factory injection pattern"
```

---

---

## 进度总结 ✅ 阶段1已完成

### 已完成的核心工作：
1. **统一LLM抽象层**：定义了ILLMService通用接口和IVLMService多模态接口，支持同步/异步生成、流式输出
2. **多框架适配器**：实现了LangChain和LlamaIndex双框架对通义千问、OpenAI、Anthropic、Ollama的适配
3. **配置系统扩展**：新增多模型提供商配置、场景级提供商独立配置、LLM通用参数配置
4. **事件总线增强**：新增ModelConfigChangedEvent事件，支持同步和异步回调，实现配置热更新通知
5. **LLM服务工厂**：实现线程安全、实例缓存、配置热更新的统一LLM实例工厂
6. **DI容器改造**：更新依赖注入配置，支持按场景和框架注入LLM工厂函数

### 下一步计划：
- 迁移LangGraph节点（ValidationNode/AssessmentNode/ReportingNode）
- 迁移RAG流水线步骤（QueryRewrite/SynonymExpand）
- 迁移其他核心服务（元数据提取/查询路由/ML评分/多模态解析等）
- 编写单元测试并进行全功能回归验证

---

## 阶段 2：业务代码迁移

### Task 8: 迁移LangGraph节点（LlamaIndex框架）

**Files:**
- Modify: `backend/src/core/nodes/validation_node.py`
- Modify: `backend/src/core/nodes/assessment_node.py`
- Modify: `backend/src/core/nodes/reporting_node.py`

- [ ] **Step 1: 迁移ValidationNode**

替换原有的DashScope初始化代码，改为工厂注入：
```python
# 原代码删除：
# from llama_index.llms.dashscope import DashScope
# self.llm = DashScope(model=settings.model_validation, api_key=settings.dashscope_api_key)

# 新代码：
from src.core.llm.base import ILLMService

class ValidationNode:
    def __init__(self, llm_factory: callable):
        self._llm_factory = llm_factory
    
    async def execute(self, state: AgentState) -> dict:
        llm = self._llm_factory()
        # 原有调用逻辑不变，使用llm.agenerate/llm.generate
        response = await llm.agenerate(prompt, system_prompt)
        return {"result": response}
```

- [ ] **Step 2: 迁移AssessmentNode**

```python
# 原代码删除：
# from llama_index.llms.dashscope import DashScope
# self.llm = DashScope(model=settings.model_assessment, api_key=settings.dashscope_api_key)

# 新代码：
class AssessmentNode:
    def __init__(self, llm_factory: callable):
        self._llm_factory = llm_factory
    
    async def execute(self, state: AgentState) -> dict:
        llm = self._llm_factory()
        response = await llm.agenerate(prompt, system_prompt)
        return {"result": response}
```

- [ ] **Step 3: 迁移ReportingNode**

```python
# 原代码删除：
# from llama_index.llms.dashscope import DashScope
# self.llm = DashScope(model=settings.model_report_generation, api_key=settings.dashscope_api_key)

# 新代码：
class ReportingNode:
    def __init__(self, llm_factory: callable):
        self._llm_factory = llm_factory
    
    async def execute(self, state: AgentState) -> dict:
        llm = self._llm_factory()
        response = await llm.agenerate(prompt, system_prompt)
        return {"result": response}
```

- [ ] **Step 4: 验证节点迁移**

Run: `cd backend && python -c "from src.core.nodes.validation_node import ValidationNode; from src.core.di_container import injector; node = injector.get(ValidationNode); print('Validation node loaded successfully')"`
Expected: `Validation node loaded successfully`

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/nodes/
git commit -m "feat: migrate LangGraph nodes to use LLM factory injection"
```

---

### Task 9: 迁移RAG流水线步骤（LangChain框架）

**Files:**
- Modify: `backend/src/core/query_rewrite.py`
- Modify: `backend/src/core/synonym_expand.py`

- [ ] **Step 1: 迁移QueryRewriteStep**

```python
# 原代码删除：
# from langchain_community.chat_models import ChatTongyi
# self.llm = ChatTongyi(model=settings.model_query_rewrite, api_key=settings.dashscope_api_key)

# 新代码：
class QueryRewriteStep:
    def __init__(self, llm_factory: callable):
        self._llm_factory = llm_factory
    
    def process(self, query: str) -> str:
        llm = self._llm_factory()
        response = llm.generate(prompt, system_prompt)
        return response
```

- [ ] **Step 2: 迁移SynonymExpandStep**

```python
# 原代码删除：
# from langchain_community.chat_models import ChatTongyi
# self.llm = ChatTongyi(model=settings.model_synonym_expand, api_key=settings.dashscope_api_key)

# 新代码：
class SynonymExpandStep:
    def __init__(self, llm_factory: callable):
        self._llm_factory = llm_factory
    
    def process(self, query: str) -> list:
        llm = self._llm_factory()
        response = llm.generate(prompt, system_prompt)
        return response
```

- [ ] **Step 3: 验证迁移**

Run: `cd backend && python -c "from src.core.query_rewrite import QueryRewriteStep; from src.core.di_container import injector; step = injector.get(QueryRewriteStep); print('Query rewrite step loaded successfully')"`
Expected: `Query rewrite step loaded successfully`

- [ ] **Step 4: Commit**

```bash
git add backend/src/core/query_rewrite.py backend/src/core/synonym_expand.py
git commit -m "feat: migrate RAG pipeline steps to use LLM factory injection"
```

---

### Task 10: 迁移其他服务

**Files:**
- Modify: `backend/src/core/metadata_processor.py`
- Modify: `backend/src/core/query_router.py`
- Modify: `backend/src/core/ml/qwen_scorer.py`
- Modify: `backend/src/core/memory_manager.py`
- Modify: `backend/src/core/parsers.py` (PDFVLParser，多模态适配)

- [ ] **Step 1: 迁移MetadataExtractor**
- [ ] **Step 2: 迁移QueryRouter**
- [ ] **Step 3: 迁移QwenScorer**
- [ ] **Step 4: 迁移MemoryManager**
- [ ] **Step 5: 迁移PDFVLParser（多模态IVLMService适配）**
- [ ] **Step 6: 验证所有服务迁移成功**
- [ ] **Step 7: Commit**

```bash
git add backend/src/core/
git commit -m "feat: migrate all remaining services to use LLM factory injection"
```

---

## 阶段 3：验证与测试

### Task 11: 编写单元测试

**Files:**
- Create: `backend/tests/core/llm/test_base.py`
- Create: `backend/tests/core/llm/test_adapters.py`
- Create: `backend/tests/core/llm/test_factory.py`
- Create: `backend/tests/core/test_event_bus.py`

- [ ] **Step 1: 编写基础接口测试**
- [ ] **Step 2: 编写适配器测试**
- [ ] **Step 3: 编写工厂热更新测试**
- [ ] **Step 4: 编写事件总线测试**
- [ ] **Step 5: 运行测试确保全部通过**

Run: `cd backend && uv run pytest tests/core/llm/ -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/tests/core/
git commit -m "feat: add unit tests for LLM service layer"
```

---

### Task 12: 全功能回归测试

- [ ] **Step 1: 运行现有所有单元测试**
- [ ] **Step 2: 运行集成测试验证评估流程正常**
- [ ] **Step 3: 运行RAG测试验证检索流程正常**
- [ ] **Step 4: 验证所有原有功能100%兼容**

---

### Task 13: 热更新功能验证

- [ ] **Step 1: 修改模型配置**
- [ ] **Step 2: 发布ModelConfigChangedEvent**
- [ ] **Step 3: 验证工厂已清除旧实例**
- [ ] **Step 4: 验证新调用使用新配置的模型**
- [ ] **Step 5: 验证热更新过程中服务无中断**

---

### Task 14: 多模型兼容性测试

- [ ] **Step 1: 配置切换为OpenAI模型，验证调用正常**
- [ ] **Step 2: 配置切换为Ollama模型，验证调用正常**
- [ ] **Step 3: 不同场景配置不同提供商，验证独立生效**
- [ ] **Step 4: 验证资源清理无泄漏**

---

## 验收标准确认

- [ ] ✅ 支持所有 LangChain 和 LlamaIndex 官方模型，无需修改业务代码
- [ ] ✅ 支持页面可视化配置所有模型相关参数
- [ ] ✅ 配置修改后热生效，无需重启服务
- [ ] ✅ 不同业务场景可独立配置不同的模型提供商和框架
- [ ] ✅ 原有业务功能 100% 兼容，无破坏性变更
- [ ] ✅ 支持配置版本回滚和变更历史记录
- [ ] ✅ 模型调用错误统一处理，自动重试
- [ ] ✅ 热更新时旧实例正确清理，无资源泄漏
- [ ] ✅ LangChain 和 LlamaIndex 双框架均支持热更新

---

## 执行说明

本计划已按最小粒度拆分，每个任务均可独立执行并验证。建议使用subagent-driven-development模式并行执行独立任务，或按顺序逐步执行。

**计划完成保存路径:** `/Users/owen/project/ai/child-development-assessment-agent/docs/superpowers/plans/2026-04-11-langchain-model-support-implementation.md`
