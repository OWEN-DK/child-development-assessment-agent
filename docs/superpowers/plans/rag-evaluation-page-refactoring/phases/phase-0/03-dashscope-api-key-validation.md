# DASHSCOPE_API_KEY 环境变量校验 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DASHSCOPE_API_KEY 环境变量校验

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/controller/health_controller.py`
- Create: `frontend/src/api/health/index.ts`
- Modify: `backend/src/config/__init__.py`
- Modify: `backend/src/server.py`
- Modify: `frontend/src/App.tsx` 或布局组件`
- Test: `backend/tests/test_health_check.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.1` 节
> **所属 Phase**: Phase 0
> **根因**: 环境变量缺失时 LLM 调用失败，但系统不报错，导致后续操作静默失败

---

## 需求定义

当前系统在启动时不校验 `DASHSCOPE_API_KEY` 等关键环境变量。Embedding 模型在 `config/__init__.py` 的模块导入时初始化，失败时仅记录日志，应用继续启动。用户在后续使用 LLM 功能时才会遇到错误，且错误信息不清晰。

**修复要求**：
1. 系统启动时必须校验 `DASHSCOPE_API_KEY` 环境变量
2. 缺失时在前端展示明确的错误提示："LLM 服务未配置，请联系管理员"
3. 后端提供健康检查端点，返回 LLM 配置状态

---

## 验收标准

- [ ] 启动时 `DASHSCOPE_API_KEY` 缺失，后端日志输出明确警告
- [ ] 前端调用健康检查接口时，能获取 LLM 配置状态
- [ ] LLM 未配置时，前端显示"LLM 服务未配置，请联系管理员"
- [ ] LLM 配置正常时，系统正常运行不受影响

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/config/__init__.py` | 修改 | 新增启动时环境变量校验 |
| `backend/src/server.py` | 修改 | 启动流程中调用校验函数 |
| `backend/src/controller/health_controller.py` | 新增 | 健康检查端点 |
| `frontend/src/api/health/index.ts` | 新增 | 健康检查 API 客户端 |
| `frontend/src/App.tsx` 或布局组件 | 修改 | 启动时检查 LLM 状态 |

---

## 实现方案

### 后端实现

**步骤 1：在 `config/__init__.py` 中新增校验函数**

```python
# backend/src/config/__init__.py

import os
import logging

logger = logging.getLogger(__name__)

def validate_required_env_vars() -> list[str]:
    """校验必需的环境变量是否已配置
    
    注意：
    1. 此函数在 settings 创建之后调用
    2. LLM API Key 优先从数据库 system_configs 表读取（符合 CLAUDE.md 配置管理规范）
    3. 环境变量作为兜底方案（数据库不可用时）
    
    返回:
        缺失的环境变量名称列表
    """
    # 延迟导入，避免在模块加载时引用尚未创建的 settings
    from src.config import settings
    
    missing = []
    
    # LLM 相关：优先检查 settings（来自数据库），兜底检查环境变量
    # 注意：settings.dashscope_api_key 字段需在 config/settings.py 中定义
    # 如尚未定义，请先在 settings 模型中添加该字段
    settings_key = getattr(settings, 'dashscope_api_key', None)
    env_key = os.environ.get('DASHSCOPE_API_KEY')
    if not settings_key and not env_key:
        missing.append('DASHSCOPE_API_KEY')
    
    # 数据库（如使用环境变量而非 .env.dev）
    # if not os.environ.get('DATABASE_URL'):
    #     missing.append('DATABASE_URL')
    
    # Redis（可选，系统可降级到内存模式）
    # if not os.environ.get('REDIS_URL'):
    #     logger.warning('REDIS_URL 未配置，SSE 将降级到内存队列模式')
    
    return missing
```

**步骤 2：在 `server.py` 启动流程中调用校验**

```python
# backend/src/server.py

from src.config import validate_required_env_vars
import sys

def create_app() -> FastAPI:
    app = FastAPI(...)
    
    # 校验环境变量
    missing_vars = validate_required_env_vars()
    if missing_vars:
        logger.critical(f'关键环境变量缺失: {", ".join(missing_vars)}')
        # 注意：不阻止应用启动，但标记为不可用状态
        # 前端通过健康检查端点获取此状态
        app.state.env_vars_missing = missing_vars
    else:
        app.state.env_vars_missing = []
    
    # ... 其余初始化逻辑
    
    return app
```

**步骤 3：新增健康检查控制器**

```python
# backend/src/controller/health_controller.py

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])

class HealthResponse(BaseModel):
    status: str  # "healthy" | "degraded"
    llm_configured: bool
    missing_vars: list[str] = []

@router.get("/", response_model=HealthResponse)
async def health_check(request: Request):
    """健康检查端点
    
    返回系统各组件的配置状态。
    前端据此判断是否展示"LLM 未配置"的提示。
    
    通过 request.app.state 获取配置状态，避免循环导入。
    
    参数:
        request: FastAPI 请求对象
        
    返回:
        HealthResponse: 包含 LLM 配置状态和缺失的环境变量列表
    """
    missing_vars = getattr(request.app.state, 'env_vars_missing', [])
    llm_configured = 'DASHSCOPE_API_KEY' not in missing_vars
    
    return HealthResponse(
        status="healthy" if llm_configured else "degraded",
        llm_configured=llm_configured,
        missing_vars=missing_vars
    )
```

**步骤 4：在 `server.py` 中注册健康检查路由**

```python
# backend/src/server.py

from src.controller.health_controller import router as health_router

def create_app() -> FastAPI:
    app = FastAPI(...)
    
    # ... 其他路由注册
    
    app.include_router(health_router)
    
    return app
```

### 前端实现

**步骤 1：新增健康检查 API 客户端**

```typescript
// frontend/src/api/health/index.ts

import { apiClient } from '@/api/client';

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  llm_configured: boolean;
  missing_vars: string[];
}

export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health/');
  return data;
}
```

**步骤 2：在应用启动时检查 LLM 状态**

在根布局组件或 `App.tsx` 中添加检查：

```typescript
// frontend/src/App.tsx 或 src/layouts/MainLayout.tsx

import { useEffect, useState } from 'react';
import { Alert } from 'antd';
import { checkHealth } from '@/api/health';

function App() {
  const [llmNotConfigured, setLlmNotConfigured] = useState(false);

  useEffect(() => {
    const checkLLM = async () => {
      try {
        const health = await checkHealth();
        setLlmNotConfigured(!health.llm_configured);
      } catch {
        // 健康检查接口不可用时，不阻断应用运行
        console.warn('健康检查失败，无法确认 LLM 配置状态');
      }
    };
    checkLLM();
  }, []);

  return (
    <>
      {llmNotConfigured && (
        <Alert
          message="LLM 服务未配置"
          description="DASHSCOPE_API_KEY 环境变量缺失，请联系管理员配置后重试。"
          type="warning"
          showIcon
          closable
          style={{ borderRadius: 0 }}
        />
      )}
      {/* 其余应用内容 */}
    </>
  );
}
```

---

## 测试方案

### 单元测试

```python
# backend/tests/test_health_check.py

import pytest
from src.config import validate_required_env_vars
from unittest.mock import patch

class TestEnvVarValidation:
    @patch.dict('os.environ', {'DASHSCOPE_API_KEY': 'test-key'}, clear=True)
    def test_all_vars_present(self):
        """测试所有环境变量都存在时"""
        missing = validate_required_env_vars()
        assert missing == []
    
    @patch.dict('os.environ', {}, clear=True)
    def test_dashscope_missing(self):
        """测试 DASHSCOPE_API_KEY 缺失时"""
        missing = validate_required_env_vars()
        assert 'DASHSCOPE_API_KEY' in missing
```

### 手动测试

1. 临时删除 `.env.dev` 中的 `DASHSCOPE_API_KEY`
2. 重启后端，检查日志是否输出警告
3. 访问 `http://localhost:8000/health/`，确认返回 `{"status": "degraded", "llm_configured": false}`
4. 打开前端，确认顶部显示警告横幅
5. 恢复 `DASHSCOPE_API_KEY`，重启后端，确认一切正常

---

## 注意事项

1. **不阻止启动**：即使环境变量缺失，应用仍然启动。这是因为部分功能（如文档上传、测试集管理）不依赖 LLM。前端通过健康检查端点判断哪些功能可用。
2. **Settings 加载时机**：`settings` 单例在 `config/__init__.py` 导入时创建，校验函数必须在 `settings` 创建之后调用。
3. **多实例部署**：健康检查端点返回的是当前实例的状态。多实例部署时，每个实例独立检查。
4. **安全性**：健康检查端点不返回敏感信息（如 API Key 的部分值），只返回是否已配置。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
