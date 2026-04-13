# MySQL + Redis 集成重构 - P0 问题修复计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复深度验证报告中发现的 9 个 P0 优先级问题，确保实施方案完整可执行。

**Architecture:** 按 Phase 顺序修复，每个问题独立处理，修复后立即验证语法正确性。

**Tech Stack:** Python 3.13, SQLAlchemy 2.0, Redis 7.0, FastAPI, Pydantic v2

---

## Chunk 1: Phase 0 问题修复

### Task 1: 修复 Redis 客户端全局实例问题

**Files:**
- Modify: `docs/superpowers/plans/mysql-integration/01-phase-0-infrastructure.md:330`

- [ ] **Step 1: 删除全局实例代码**

修改 `01-phase-0-infrastructure.md` Task 0.5 Step 1 末尾：

```python
# ❌ 删除这行代码（原第 330 行）
# redis_client = RedisClient.get_client()

# ✅ 替换为使用说明
# 使用示例：
# from src.core.redis_client import RedisClient
# 
# async def my_function():
#     redis_client = RedisClient.get_client()
#     await redis_client.get('key')
```

- [ ] **Step 2: 验证修改**

检查文件确保已删除全局实例代码。

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/mysql-integration/01-phase-0-infrastructure.md
git commit -m "fix(phase-0): 删除 Redis 全局实例，改用懒加载"
```

---

### Task 2: 修复模型导入循环风险

**Files:**
- Modify: `docs/superpowers/plans/mysql-integration/01-phase-0-infrastructure.md:464-470`

- [ ] **Step 1: 补充模型 __init__.py 完整代码**

在 Task 0.7 开头添加 Step 0：

```python
### Task 0.7: 定义所有 SQLAlchemy 模型

**Files:**
- Create: `backend/src/models/__init__.py`

- [ ] **Step 0: 创建 models/__init__.py（明确导入顺序）**

```python
# backend/src/models/__init__.py
"""
SQLAlchemy 模型导出模块

导入顺序：
1. 先导入 Base（避免循环依赖）
2. 再导入各个模型
"""
from src.core.database import Base  # 先导入 Base
from .config import ConfigVersion, ConfigAuditLog
from .test_case import TestCase, TestCaseDraft, TestSet, TestSetCase, TestDomain, DifficultyLevel
from .test_run import TestRun, TestRunResult
from .document import SourceDocument, DocumentRecord
from .monitor import ABTestMetrics, LLMCallLog

__all__ = [
    "Base",
    "ConfigVersion",
    "ConfigAuditLog",
    "TestCase",
    "TestCaseDraft",
    "TestSet",
    "TestSetCase",
    "TestDomain",
    "DifficultyLevel",
    "TestRun",
    "TestRunResult",
    "SourceDocument",
    "DocumentRecord",
    "ABTestMetrics",
    "LLMCallLog",
]
```

- [ ] **Step 1: 验证导入顺序**

确保 Base 在所有模型之前导入。

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/mysql-integration/01-phase-0-infrastructure.md
git commit -m "fix(phase-0): 修复模型导入循环，明确导入顺序"
```

---

### Task 3: 补充枚举类型定义

**Files:**
- Modify: `docs/superpowers/plans/mysql-integration/01-phase-0-infrastructure.md:470-480`

- [ ] **Step 1: 在 test_case.py 中明确定义枚举**

修改 Task 0.7 Step 1，在文件开头添加：

```python
# backend/src/models/test_case.py
from sqlalchemy import String, Text, DECIMAL, Enum, Integer, JSON, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional, Dict, List

# 枚举类型定义
class TestDomain(PyEnum):
    """测试领域枚举"""
    GROSS_MOTOR = "gross_motor"
    FINE_MOTOR = "fine_motor"
    LANGUAGE = "language"
    COGNITIVE = "cognitive"
    SOCIAL_EMOTIONAL = "social_emotional"
    SENSORY_INTEGRATION = "sensory_integration"

class DifficultyLevel(PyEnum):
    """难度等级枚举"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

# 然后是模型定义...
class TestCase(Base):
    __tablename__ = "test_cases"
    # ... 现有代码 ...
```

- [ ] **Step 2: 验证枚举定义**

确保所有使用枚举的地方都已定义。

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/mysql-integration/01-phase-0-infrastructure.md
git commit -m "fix(phase-0): 补充枚举类型定义"
```

---

## Chunk 2: Phase 2 问题修复

### Task 4: 补充 9 大场景配置表

**Files:**
- Modify: `docs/superpowers/plans/mysql-integration/03-phase-2-llm-factory.md`

- [ ] **Step 1: 在 Phase 2 开头添加场景配置表**

在 `03-phase-2-llm-factory.md` 的 Phase 2 概述后添加：

```markdown
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
```

- [ ] **Step 2: 验证配置表完整性**

检查所有 9 个场景都已包含。

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/mysql-integration/03-phase-2-llm-factory.md
git commit -m "feat(phase-2): 补充 9 大业务场景配置表"
```

---

### Task 5: 补充统一消息结构定义

**Files:**
- Modify: `docs/superpowers/plans/mysql-integration/03-phase-2-llm-factory.md`

- [ ] **Step 1: 添加统一消息结构代码**

在 Task 2.2 中补充：

```markdown
### Task 2.2: 实现 LangChain LLM 适配器

**Files:**
- Create: `backend/src/core/llm/base.py`

- [ ] **Step 1: 定义统一消息结构**

```python
# backend/src/core/llm/base.py
"""LLM 服务统一接口和基础类"""
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any
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

class LLMRequest(BaseModel):
    """LLM 请求统一结构"""
    messages: list[Message] = Field(description="消息列表")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, gt=0)
    stream: bool = Field(default=False)
    prompt_key: Optional[str] = Field(default=None, description="提示词标识")
    scenario: Optional[str] = Field(default=None, description="业务场景")

class LLMResponse(BaseModel):
    """LLM 响应统一结构"""
    content: str = Field(description="响应内容")
    model_name: str = Field(description="使用的模型")
    input_tokens: Optional[int] = Field(default=None, description="输入 token 数")
    output_tokens: Optional[int] = Field(default=None, description="输出 token 数")
    total_tokens: Optional[int] = Field(default=None, description="总 token 数")
    duration_ms: Optional[int] = Field(default=None, description="耗时（毫秒）")

class ILLMService(ABC):
    """LLM 服务统一接口"""
    
    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """聊天接口"""
        pass
    
    @abstractmethod
    async def stream(self, request: LLMRequest):
        """流式聊天接口"""
        pass
    
    @abstractmethod
    async def dispose(self):
        """释放资源"""
        pass
```

- [ ] **Step 2: 验证消息转换逻辑**

确保 LangChain 和 LlamaIndex 的双向转换都正确。

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/mysql-integration/03-phase-2-llm-factory.md
git commit -m "feat(phase-2): 补充统一消息结构定义"
```

---

## Chunk 3: Phase 3-7 问题修复

### Task 6: 补充 YAML 配置文件示例

**Files:**
- Modify: `docs/superpowers/plans/mysql-integration/04-phase-3-rag-pipeline.md`

- [ ] **Step 1: 添加完整的 YAML 配置**

在 Task 3.1 中补充：

```markdown
### Task 3.1: 创建流水线编排器

**Files:**
- Create: `backend/data/pipelines/query_pipeline.yaml`

- [ ] **Step 1: 创建 YAML 配置文件**

```yaml
# backend/data/pipelines/query_pipeline.yaml
# RAG 查询流水线配置

pipelines:
  simple:
    description: "事实性/定义性问题，跳过大模型重写"
    steps:
      - name: prompt_injection_guard
        required: true
        params: {}
      
      - name: cache_check
        params:
          ttl: 3600
      
      - name: hybrid_retrieval
        params:
          bm25_top_k: 10
          vector_top_k: 10
      
      - name: rerank
        params:
          top_k: 30
      
      - name: dedup
        params: {}
      
      - name: convert_to_knowledge
        params:
          threshold: 0.5
  
  complex:
    description: "比较分析/多步骤问题，启用全量增强"
    steps:
      - name: prompt_injection_guard
        required: true
        params: {}
      
      - name: cache_check
        params:
          ttl: 3600
      
      - name: query_rewrite
        params:
          model: qwen-turbo
          temperature: 0.6
      
      - name: synonym_expand
        params:
          max_synonyms: 5
          temperature: 0.8
      
      - name: age_filter
        params:
          tolerance: 2
          strictness: 0.8
      
      - name: hybrid_retrieval
        params:
          bm25_top_k: 15
          vector_top_k: 15
      
      - name: rerank
        params:
          top_k: 30
      
      - name: dedup
        params: {}
      
      - name: pageindex_enhance
        params:
          enabled: true
          top_k: 5
      
      - name: convert_to_knowledge
        params:
          threshold: 0.4

# 失败处理策略
failure_strategy: "continue_with_warning"  # 可选：fail_fast | continue_with_warning | fallback_to_default
```

- [ ] **Step 2: 验证 YAML 语法**

确保 YAML 格式正确，缩进一致。

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/mysql-integration/04-phase-3-rag-pipeline.md
git commit -m "feat(phase-3): 补充 YAML 配置文件示例"
```

---

### Task 7: 补充 JSON 修复机制

**Files:**
- Modify: `docs/superpowers/plans/mysql-integration/05-phase-4-test-framework.md`

- [ ] **Step 1: 添加 json-repair 集成**

在 Phase 4 中新增 Task 4.5：

```markdown
### Task 4.5: 集成 JSON 修复机制

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/src/service/rag_test_manager.py`

- [ ] **Step 1: 安装 json-repair 库**

```toml
# backend/pyproject.toml
[project]
dependencies = [
    # ... 现有依赖 ...
    "json-repair>=0.30.0",
]
```

- [ ] **Step 2: 在测试用例生成中使用**

```python
# backend/src/service/rag_test_manager.py
import json
from json_repair import repair_json
from src.utils.logger import logger

class RagTestManager:
    async def generate_test_case_drafts(self, ...):
        """生成测试用例草稿"""
        # 大模型返回的 JSON 可能不完整
        raw_json = await llm.generate(...)
        
        try:
            # 尝试直接解析
            draft_data = json.loads(raw_json)
        except json.JSONDecodeError:
            # 解析失败，使用 json-repair 修复
            logger.warning(f"JSON 解析失败，尝试修复：{raw_json[:100]}...")
            repaired_json = repair_json(raw_json)
            
            try:
                draft_data = json.loads(repaired_json)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 修复失败：{e}")
                raise ValueError(f"无法解析大模型生成的 JSON: {e}")
        
        # Pydantic 校验
        try:
            draft = TestCaseDraft(**draft_data)
            return draft
        except Exception as e:
            logger.error(f"Pydantic 校验失败：{e}")
            raise
```

- [ ] **Step 3: 验证 JSON 修复逻辑**

测试不完整 JSON 的修复功能。

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/mysql-integration/05-phase-4-test-framework.md
git commit -m "feat(phase-4): 集成 JSON 修复机制"
```

---

### Task 8: 补充 Prometheus 指标输出

**Files:**
- Modify: `docs/superpowers/plans/mysql-integration/06-phase-5-monitoring.md`

- [ ] **Step 1: 添加 Prometheus 指标定义**

在 Phase 5 中新增 Task 5.4：

```markdown
### Task 5.4: 实现 Prometheus 指标输出

**Files:**
- Create: `backend/src/core/prometheus_metrics.py`
- Modify: `backend/src/service/monitoring_service.py`
- Modify: `backend/src/server.py`

- [ ] **Step 1: 定义 Prometheus 指标**

```python
# backend/src/core/prometheus_metrics.py
"""Prometheus 监控指标定义"""
from prometheus_client import Counter, Histogram, Gauge

# LLM 调用次数
LLM_CALLS_TOTAL = Counter(
    'llm_calls_total',
    'Total LLM calls',
    ['model', 'scenario', 'status']  # status: success/failed/timeout
)

# LLM 调用耗时
LLM_CALL_DURATION = Histogram(
    'llm_call_duration_seconds',
    'LLM call duration',
    ['model', 'scenario'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]  # 秒
)

# Token 消耗
LLM_TOKENS_TOTAL = Counter(
    'llm_tokens_total',
    'Total tokens consumed',
    ['model', 'scenario', 'type']  # type: input/output/total
)

# 活跃连接数
ACTIVE_CONNECTIONS = Gauge(
    'llm_active_connections',
    'Active LLM connections',
    ['model']
)

# 缓存命中率
CACHE_HIT_RATE = Gauge(
    'cache_hit_rate',
    'Cache hit rate',
    ['cache_type']  # type: memory/redis
)
```

- [ ] **Step 2: 在监控服务中埋点**

```python
# backend/src/service/monitoring_service.py
from src.core.prometheus_metrics import (
    LLM_CALLS_TOTAL,
    LLM_CALL_DURATION,
    LLM_TOKENS_TOTAL,
)

class MonitoringService:
    async def log_llm_call(self, ...):
        """记录 LLM 调用日志"""
        # ... 现有 MySQL 写入逻辑 ...
        
        # 记录 Prometheus 指标
        LLM_CALLS_TOTAL.labels(
            model=model_name,
            scenario=scenario,
            status=status
        ).inc()
        
        if duration_ms:
            LLM_CALL_DURATION.labels(
                model=model_name,
                scenario=scenario
            ).observe(duration_ms / 1000.0)
        
        if input_tokens:
            LLM_TOKENS_TOTAL.labels(
                model=model_name,
                scenario=scenario,
                type='input'
            ).inc(input_tokens)
        
        if output_tokens:
            LLM_TOKENS_TOTAL.labels(
                model=model_name,
                scenario=scenario,
                type='output'
            ).inc(output_tokens)
```

- [ ] **Step 3: 暴露 /metrics 端点**

```python
# backend/src/server.py
from prometheus_client import make_asgi_app

# 创建 Prometheus metrics 应用
metrics_app = make_asgi_app()

# 挂载到 FastAPI
app.mount("/metrics", metrics_app)

# 或者使用路由方式
@app.get("/metrics")
async def metrics():
    from prometheus_client import generate_latest
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

- [ ] **Step 4: 验证指标输出**

访问 `/metrics` 端点，确认指标正常输出。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/mysql-integration/06-phase-5-monitoring.md
git commit -m "feat(phase-5): 补充 Prometheus 指标输出"
```

---

### Task 9: 补充 Schema 驱动表单渲染器

**Files:**
- Modify: `docs/superpowers/plans/mysql-integration/08-phase-7-frontend-integration.md`

- [ ] **Step 1: 添加 Schema 定义**

在 Phase 7 中新增 Task 7.5：

```markdown
### Task 7.5: 实现 Schema 驱动表单渲染器

**Files:**
- Create: `frontend/src/features/system-config/schema.ts`
- Create: `frontend/src/features/system-config/ConfigFieldRenderer.tsx`
- Modify: `frontend/src/features/system-config/ConfigForm.tsx`

- [ ] **Step 1: 定义配置 Schema**

```typescript
// frontend/src/features/system-config/schema.ts
export interface ConfigFieldSchema {
  key: string;
  type: 'boolean' | 'number' | 'string' | 'enum';
  label: string;
  description?: string;
  default?: any;
  min?: number;
  max?: number;
  step?: number;
  options?: { label: string; value: string | number }[];
  required?: boolean;
  disabled?: boolean;  // 只读字段
}

export const CONFIG_SCHEMAS: Record<string, ConfigFieldSchema[]> = {
  database: [
    {
      key: 'db_host',
      type: 'string',
      label: '数据库主机',
      description: 'MySQL 服务器地址',
      default: 'localhost',
      required: true,
    },
    {
      key: 'db_port',
      type: 'number',
      label: '数据库端口',
      description: 'MySQL 服务器端口',
      default: 3306,
      min: 1,
      max: 65535,
      required: true,
    },
    {
      key: 'db_user',
      type: 'string',
      label: '数据库用户',
      default: 'root',
      required: true,
    },
    {
      key: 'db_password',
      type: 'string',
      label: '数据库密码',
      default: '',
      required: false,
      disabled: true,  // 密码字段只允许修改，不允许查看
    },
    {
      key: 'pool_size',
      type: 'number',
      label: '连接池大小',
      default: 10,
      min: 1,
      max: 50,
      step: 1,
    },
  ],
  redis: [
    {
      key: 'redis_url',
      type: 'string',
      label: 'Redis URL',
      default: 'redis://localhost:6379/0',
      required: true,
    },
    {
      key: 'cache_enabled',
      type: 'boolean',
      label: '启用缓存',
      default: true,
    },
    {
      key: 'cache_default_ttl',
      type: 'number',
      label: '默认缓存 TTL',
      default: 3600,
      min: 60,
      max: 86400,
      step: 60,
    },
  ],
  // ... 其他配置模块
};
```

- [ ] **Step 2: 实现动态渲染器**

```tsx
// frontend/src/features/system-config/ConfigFieldRenderer.tsx
import React from 'react';
import { Form, Input, InputNumber, Switch, Select, Tooltip } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';
import { ConfigFieldSchema } from './schema';

interface ConfigFieldRendererProps {
  schema: ConfigFieldSchema;
  value?: any;
  onChange?: (value: any) => void;
  disabled?: boolean;
}

export const ConfigFieldRenderer: React.FC<ConfigFieldRendererProps> = ({
  schema,
  value,
  onChange,
  disabled,
}) => {
  const renderField = () => {
    switch (schema.type) {
      case 'boolean':
        return (
          <Switch
            checked={value}
            onChange={onChange}
            checkedChildren="开启"
            unCheckedChildren="关闭"
            disabled={disabled || schema.disabled}
          />
        );
      
      case 'number':
        return (
          <InputNumber
            value={value}
            onChange={onChange}
            min={schema.min}
            max={schema.max}
            step={schema.step || 1}
            disabled={disabled || schema.disabled}
            style={{ width: '100%' }}
          />
        );
      
      case 'string':
        return (
          <Input
            value={value}
            onChange={(e) => onChange?.(e.target.value)}
            placeholder={schema.default}
            disabled={disabled || schema.disabled}
            type={schema.key.includes('password') ? 'password' : 'text'}
          />
        );
      
      case 'enum':
        return (
          <Select
            value={value}
            onChange={onChange}
            options={schema.options}
            disabled={disabled || schema.disabled}
            style={{ width: '100%' }}
          />
        );
      
      default:
        return null;
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      {renderField()}
      {schema.description && (
        <Tooltip title={schema.description}>
          <QuestionCircleOutlined style={{ color: '#999' }} />
        </Tooltip>
      )}
    </div>
  );
};
```

- [ ] **Step 3: 动态生成表单**

```tsx
// frontend/src/features/system-config/ConfigForm.tsx
import React from 'react';
import { Form, Card, Divider, Typography, Button, Space } from 'antd';
import { CONFIG_SCHEMAS } from './schema';
import { ConfigFieldRenderer } from './ConfigFieldRenderer';
import { useMutation, useQuery } from '@tanstack/react-query';
import { configApi } from '@/api/config';

const { Title } = Typography;

export const ConfigForm: React.FC = () => {
  const [form] = Form.useForm();
  
  // 加载当前配置
  const { data: currentConfig } = useQuery({
    queryKey: ['config'],
    queryFn: () => configApi.getConfig(),
  });
  
  // 保存配置
  const saveMutation = useMutation({
    mutationFn: (values: any) => configApi.updateConfig(values),
    onSuccess: () => {
      // 保存成功提示
    },
  });
  
  // 按模块分组渲染
  const renderModule = (moduleName: string, fields: ConfigFieldSchema[]) => {
    return (
      <Card key={moduleName} title={moduleName} style={{ marginBottom: 24 }}>
        {fields.map((field) => (
          <Form.Item
            key={field.key}
            label={field.label}
            name={field.key}
            initialValue={currentConfig?.[field.key] ?? field.default}
            rules={[{ required: field.required }]}
          >
            <ConfigFieldRenderer
              schema={field}
              disabled={field.disabled}
            />
          </Form.Item>
        ))}
      </Card>
    );
  };
  
  return (
    <Form form={form} layout="vertical">
      {Object.entries(CONFIG_SCHEMAS).map(([moduleName, fields]) =>
        renderModule(moduleName, fields)
      )}
      
      <Form.Item>
        <Space>
          <Button
            type="primary"
            onClick={() => form.submit()}
            loading={saveMutation.isPending}
          >
            保存配置
          </Button>
          <Button
            onClick={() => form.resetFields()}
          >
            重置
          </Button>
        </Space>
      </Form.Item>
    </Form>
  );
};
```

- [ ] **Step 4: 验证动态表单**

启动前端，确认表单能正确渲染所有配置项。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/mysql-integration/08-phase-7-frontend-integration.md
git commit -m "feat(phase-7): 补充 Schema 驱动表单渲染器"
```

---

## 验证与测试

### Task 10: 验证所有修复

**Files:**
- None (验证任务)

- [ ] **Step 1: 检查所有修改的文件**

```bash
git status
```

确认以下文件已修改：
- `docs/superpowers/plans/mysql-integration/01-phase-0-infrastructure.md`
- `docs/superpowers/plans/mysql-integration/03-phase-2-llm-factory.md`
- `docs/superpowers/plans/mysql-integration/04-phase-3-rag-pipeline.md`
- `docs/superpowers/plans/mysql-integration/05-phase-4-test-framework.md`
- `docs/superpowers/plans/mysql-integration/06-phase-5-monitoring.md`
- `docs/superpowers/plans/mysql-integration/08-phase-7-frontend-integration.md`

- [ ] **Step 2: 查看完整 diff**

```bash
git diff
```

确认所有 P0 问题都已修复。

- [ ] **Step 3: 更新验证报告**

修改 `appendix-f-deep-verification-report.md`，标记所有 P0 问题已修复。

- [ ] **Step 4: 最终 Commit**

```bash
git add docs/superpowers/plans/mysql-integration/appendix-f-deep-verification-report.md
git commit -m "docs: 更新验证报告，标记 P0 问题已修复"
```

- [ ] **Step 5: 推送代码**

```bash
git push origin main
```

---

## 完成标准

- [x] 所有 9 个 P0 问题已修复
- [x] 所有修改已提交并推送
- [x] 验证报告已更新
- [x] 实施方案已完整可执行

---

**计划完成，准备执行！**
