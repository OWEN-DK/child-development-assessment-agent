# 提示词管理系统实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的提示词配置管理系统，支持所有提示词在页面中可视化配置、版本管理、热重载、回滚等功能。

**Architecture:** 基于现有 ConfigManager 架构模式，创建独立的 PromptManager/PromptRepository 后端模块，PromptLoader 统一加载接口，PromptController RESTful API，以及前端独立一级管理页面。

**Tech Stack:** Python (FastAPI, asyncio), TypeScript (React, Ant Design, Zustand), JSON 文件存储

---

## Chunk 1: 后端核心模块实现

### 文件映射

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/src/config/prompt_repository.py` | 创建 | JSON 文件持久化存储仓库 |
| `backend/src/config/prompt_manager.py` | 创建 | 提示词业务逻辑、版本管理、缓存 |
| `backend/src/core/prompt_loader.py` | 创建 | 统一加载接口、变量渲染、降级 |
| `backend/src/controller/prompt_controller.py` | 创建 | RESTful API 路由 |
| `backend/src/server.py` | 修改 | 注册 PromptController 路由 |
| `backend/src/core/di_container.py` | 修改 | 注册 PromptManager 依赖 |
| `backend/data/prompts/` | 创建目录 | 提示词 JSON 存储目录 |

---

### Task 1: 创建 PromptRepository

**Files:**
- Create: `backend/src/config/prompt_repository.py`
- Test: `backend/tests/test_prompt_repository.py`

**职责:** JSON 文件持久化存储，类似 ConfigRepository 但更简单（每个提示词一个独立 JSON 文件）

**核心方法:**
```python
class PromptRepository:
    """提示词 JSON 文件持久化存储仓库"""
    
    def __init__(self, data_dir: str = "data/prompts"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
    
    def _get_prompt_path(self, key: str) -> Path:
        """获取提示词文件路径"""
        return self.data_dir / f"{key}.json"
    
    async def load_prompt(self, key: str) -> dict | None:
        """加载单个提示词 JSON 文件"""
        path = self._get_prompt_path(key)
        if not path.exists():
            return None
        async with self._lock:
            return json.loads(path.read_text(encoding="utf-8"))
    
    async def save_prompt(self, key: str, data: dict) -> None:
        """保存提示词到 JSON 文件"""
        path = self._get_prompt_path(key)
        async with self._lock:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    async def delete_prompt(self, key: str) -> None:
        """删除提示词 JSON 文件"""
        path = self._get_prompt_path(key)
        async with self._lock:
            if path.exists():
                path.unlink()
    
    async def list_all_prompts(self) -> list[str]:
        """列出所有提示词 key"""
        return [f.stem for f in self.data_dir.glob("*.json")]
```

**改动说明:**
- 复用 ConfigRepository 的异步锁模式
- 每个提示词独立存储为 `{key}.json`
- 不需要版本归档目录（版本信息内嵌在 JSON 的 `versions` 字段中）

---

### Task 2: 创建 PromptManager

**Files:**
- Create: `backend/src/config/prompt_manager.py`
- Test: `backend/tests/test_prompt_manager.py`

**职责:** 提示词业务逻辑，单例模式，类似 ConfigManager

**完整实现代码:**
```python
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from src.config.prompt_repository import PromptRepository
from src.core.event_bus import event_bus

class PromptManager:
    """提示词管理器 - 单例模式"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._repository = PromptRepository()
        self._cache: dict[str, dict] = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """初始化：加载所有提示词到缓存"""
        keys = await self._repository.list_all_prompts()
        for key in keys:
            data = await self._repository.load_prompt(key)
            if data:
                self._cache[key] = data
        logger.info(f"PromptManager initialized with {len(self._cache)} prompts")
    
    def get_prompt(self, key: str) -> Optional[dict]:
        """获取提示词完整数据"""
        return self._cache.get(key)
    
    def get_content(self, key: str) -> Optional[str]:
        """仅获取提示词内容"""
        prompt = self._cache.get(key)
        return prompt.get("content") if prompt else None
    
    async def update_prompt(self, key: str, content: str, change_log: str, updated_by: str = "system") -> dict:
        """更新提示词（自动创建新版本）"""
        async with self._lock:
            prompt = self._cache.get(key)
            if not prompt:
                raise ValueError(f"Prompt not found: {key}")
            
            old_version = prompt.get("current_version", "v0.0.0")
            new_version = self._bump_version(old_version)
            
            # 创建新版本
            prompt["versions"][new_version] = {
                "content": content,
                "change_log": change_log,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": updated_by,
            }
            prompt["current_version"] = new_version
            prompt["content"] = content
            prompt["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # 持久化
            await self._repository.save_prompt(key, prompt)
            
            # 发布事件
            event_bus.publish("prompt_changed", {"key": key, "version": new_version})
            
            logger.info(f"Prompt {key} updated to {new_version}")
            return prompt
    
    async def create_prompt(self, data: dict) -> dict:
        """创建新提示词"""
        async with self._lock:
            key = data["key"]
            if key in self._cache:
                raise ValueError(f"Prompt already exists: {key}")
            
            now = datetime.now(timezone.utc).isoformat()
            prompt = {
                "key": key,
                "name": data.get("name", key),
                "category": data.get("category", "metadata"),
                "content": data["content"],
                "variables": data.get("variables", []),
                "description": data.get("description", ""),
                "status": data.get("status", "active"),
                "current_version": "v1.0.0",
                "created_at": now,
                "updated_at": now,
                "versions": {
                    "v1.0.0": {
                        "content": data["content"],
                        "change_log": data.get("change_log", "初始版本"),
                        "created_at": now,
                        "created_by": data.get("created_by", "system"),
                    }
                }
            }
            
            self._cache[key] = prompt
            await self._repository.save_prompt(key, prompt)
            
            event_bus.publish("prompt_created", {"key": key})
            logger.info(f"Prompt {key} created")
            return prompt
    
    async def delete_prompt(self, key: str) -> bool:
        """删除提示词"""
        async with self._lock:
            if key not in self._cache:
                return False
            
            del self._cache[key]
            await self._repository.delete_prompt(key)
            
            event_bus.publish("prompt_deleted", {"key": key})
            logger.info(f"Prompt {key} deleted")
            return True
    
    def list_prompts(self, category: str = None, status: str = None) -> list[dict]:
        """列表查询（支持过滤）"""
        result = list(self._cache.values())
        if category:
            result = [p for p in result if p.get("category") == category]
        if status:
            result = [p for p in result if p.get("status") == status]
        return result
    
    def get_versions(self, key: str) -> list[dict]:
        """获取版本列表"""
        prompt = self._cache.get(key)
        if not prompt:
            return []
        
        versions = prompt.get("versions", {})
        return [
            {"version": v, **info}
            for v, info in versions.items()
        ]
    
    def get_version(self, key: str, version: str) -> Optional[dict]:
        """获取指定版本"""
        prompt = self._cache.get(key)
        if not prompt:
            return None
        
        version_data = prompt.get("versions", {}).get(version)
        if not version_data:
            return None
        
        return {"version": version, **version_data}
    
    async def rollback(self, key: str, version: str) -> dict:
        """回滚到指定版本"""
        async with self._lock:
            prompt = self._cache.get(key)
            if not prompt:
                raise ValueError(f"Prompt not found: {key}")
            
            version_data = prompt.get("versions", {}).get(version)
            if not version_data:
                raise ValueError(f"Version not found: {version}")
            
            # 创建新版本（基于回滚版本的内容）
            new_version = self._bump_version(prompt["current_version"])
            prompt["versions"][new_version] = {
                "content": version_data["content"],
                "change_log": f"回滚到 {version}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "system",
            }
            prompt["current_version"] = new_version
            prompt["content"] = version_data["content"]
            prompt["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            await self._repository.save_prompt(key, prompt)
            event_bus.publish("prompt_rollback", {"key": key, "from_version": version, "to_version": new_version})
            
            logger.info(f"Prompt {key} rolled back from {version} to {new_version}")
            return prompt
    
    def diff_versions(self, key: str, v1: str, v2: str) -> dict:
        """对比两个版本的差异"""
        prompt = self._cache.get(key)
        if not prompt:
            return {"error": "Prompt not found"}
        
        versions = prompt.get("versions", {})
        content1 = versions.get(v1, {}).get("content", "")
        content2 = versions.get(v2, {}).get("content", "")
        
        # 简单行级 diff
        lines1 = content1.splitlines()
        lines2 = content2.splitlines()
        
        added = []
        removed = []
        for line in lines2:
            if line not in lines1:
                added.append(line)
        for line in lines1:
            if line not in lines2:
                removed.append(line)
        
        return {
            "v1": v1,
            "v2": v2,
            "added": added,
            "removed": removed,
        }
    
    async def refresh(self):
        """热重载缓存"""
        async with self._lock:
            keys = await self._repository.list_all_prompts()
            for key in keys:
                data = await self._repository.load_prompt(key)
                if data:
                    self._cache[key] = data
            logger.info(f"PromptManager cache refreshed with {len(self._cache)} prompts")
    
    def _bump_version(self, version: str) -> str:
        """版本号递增 v{major}.{minor}.{patch} -> v{major}.{minor}.{patch+1}"""
        if version.startswith("v"):
            version = version[1:]
        parts = version.split(".")
        if len(parts) == 3:
            parts[2] = str(int(parts[2]) + 1)
        else:
            parts.append("1")
        return f"v{'.'.join(parts)}"


# 全局单例
prompt_manager = PromptManager()
```

**改动说明:**
- 单例模式复用 `__new__` + `_initialized` 模式（与 ConfigManager 一致）
- 内存缓存 `_cache` 存储所有提示词
- 每次更新自动创建新版本（版本号递增 patch）
- 通过 EventBus 发布变更事件
- 提供 diff 功能（简单行级对比，前端可用更复杂的 diff 库）

---

### Task 3: 创建 PromptLoader

**Files:**
- Create: `backend/src/core/prompt_loader.py`
- Test: `backend/tests/test_prompt_loader.py`

**职责:** 业务代码统一加载接口，支持变量渲染和降级到 prompts.py

**完整实现代码:**
```python
import re
from typing import Optional
from loguru import logger
from src.config.prompt_manager import prompt_manager

class PromptLoader:
    """业务代码统一提示词加载接口"""
    
    def __init__(self):
        self._variable_pattern = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")
    
    def load(self, key: str, **variables) -> str:
        """加载并渲染变量的提示词内容"""
        content = self._get_content_with_fallback(key)
        if content is None:
            raise ValueError(f"Prompt not found: {key}")
        return self._render_variables(content, **variables)
    
    def load_raw(self, key: str) -> str:
        """加载原始模板（不渲染变量）"""
        content = self._get_content_with_fallback(key)
        if content is None:
            raise ValueError(f"Prompt not found: {key}")
        return content
    
    def batch_load(self, keys: list[str], **variables) -> dict[str, str]:
        """批量加载多个提示词"""
        result = {}
        for key in keys:
            try:
                result[key] = self.load(key, **variables)
            except ValueError as e:
                logger.warning(f"Failed to load prompt {key}: {e}")
                result[key] = ""
        return result
    
    def _get_content_with_fallback(self, key: str) -> Optional[str]:
        """获取提示词内容，降级到 prompts.py"""
        # 优先从 PromptManager 获取
        content = prompt_manager.get_content(key)
        if content:
            return content
        
        # 降级到 prompts.py 硬编码值
        try:
            from src.core import prompts
            return getattr(prompts, key, None)
        except ImportError:
            logger.warning(f"Cannot fallback to prompts.py for {key}")
            return None
    
    def _render_variables(self, template: str, **variables) -> str:
        """渲染 {{variable}} 占位符"""
        def replace_match(match):
            var_name = match.group(1)
            # 支持嵌套变量 child_profile.name
            value = variables
            for part in var_name.split("."):
                if isinstance(value, dict):
                    value = value.get(part, match.group(0))  # 未提供则保持原样
                else:
                    return match.group(0)
            return str(value)
        
        return self._variable_pattern.sub(replace_match, template)
    
    def extract_variables(self, template: str) -> list[str]:
        """提取模板中的所有变量名"""
        return self._variable_pattern.findall(template)


# 全局单例
prompt_loader = PromptLoader()
```

**改动说明:**
- `load()` 方法支持变量渲染，调用方传入 `key` 和变量值
- `_get_content_with_fallback()` 实现降级机制：PromptManager → prompts.py
- `_render_variables()` 支持 `{{variable}}` 和 `{{nested.variable}}` 格式
- 未提供的变量保持原样不替换（避免报错）
- `extract_variables()` 用于前端变量校验

---

### Task 4: 创建 PromptController

**Files:**
- Create: `backend/src/controller/prompt_controller.py`
- Modify: `backend/src/server.py` (注册路由)

**职责:** RESTful API 路由，提供 CRUD、版本管理、业务加载接口

**完整实现代码:**
```python
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel
from src.config.prompt_manager import prompt_manager

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])

class CreatePromptRequest(BaseModel):
    key: str
    name: str
    category: str = "metadata"
    content: str
    variables: list[str] = []
    description: str = ""
    status: str = "active"
    change_log: str = "初始版本"
    created_by: str = "system"

class UpdatePromptRequest(BaseModel):
    content: str
    change_log: str
    updated_by: str = "system"

class RenderRequest(BaseModel):
    variables: dict = {}

# ========== 基础 CRUD 接口 ==========

@router.get("")
async def list_prompts(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    """获取提示词列表"""
    return prompt_manager.list_prompts(category=category, status=status)

@router.get("/{key}")
async def get_prompt(key: str):
    """获取单个提示词详情"""
    prompt = prompt_manager.get_prompt(key)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")
    return prompt

@router.post("")
async def create_prompt(data: CreatePromptRequest):
    """创建新提示词"""
    try:
        result = await prompt_manager.create_prompt(data.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{key}")
async def update_prompt(key: str, data: UpdatePromptRequest):
    """更新提示词（自动创建新版本）"""
    try:
        result = await prompt_manager.update_prompt(
            key, data.content, data.change_log, data.updated_by
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{key}")
async def delete_prompt(key: str):
    """删除提示词"""
    success = await prompt_manager.delete_prompt(key)
    if not success:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")
    return {"message": f"Prompt {key} deleted"}

# ========== 版本管理接口 ==========

@router.get("/{key}/versions")
async def get_versions(key: str):
    """获取提示词的所有版本列表"""
    versions = prompt_manager.get_versions(key)
    if not versions:
        prompt = prompt_manager.get_prompt(key)
        if not prompt:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")
    return versions

@router.get("/{key}/versions/{version}")
async def get_version(key: str, version: str):
    """获取指定版本详情"""
    version_data = prompt_manager.get_version(key, version)
    if not version_data:
        raise HTTPException(status_code=404, detail=f"Version not found: {version}")
    return version_data

@router.post("/{key}/rollback")
async def rollback(key: str, data: dict):
    """回滚到指定版本"""
    version = data.get("version")
    if not version:
        raise HTTPException(status_code=400, detail="version is required")
    try:
        result = await prompt_manager.rollback(key, version)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{key}/diff")
async def diff_versions(key: str, v1: str = Query(...), v2: str = Query(...)):
    """对比两个版本的差异"""
    return prompt_manager.diff_versions(key, v1, v2)

# ========== 业务加载接口 ==========

@router.get("/load/{key}")
async def load_prompt(key: str, variables: Optional[str] = Query(None)):
    """加载并渲染变量的提示词"""
    from src.core.prompt_loader import prompt_loader
    import json
    
    vars_dict = {}
    if variables:
        try:
            vars_dict = json.loads(variables)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid variables JSON")
    
    try:
        content = prompt_loader.load(key, **vars_dict)
        return {"key": key, "content": content}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/batch-load")
async def batch_load(data: dict):
    """批量加载多个提示词"""
    from src.core.prompt_loader import prompt_loader
    
    keys = data.get("keys", [])
    variables = data.get("variables", {})
    
    result = prompt_loader.batch_load(keys, **variables)
    return result

@router.post("/refresh")
async def refresh_cache():
    """刷新提示词缓存（热重载）"""
    await prompt_manager.refresh()
    return {"message": "Cache refreshed"}
```

**改动说明:**
- 路由前缀 `/api/v1/prompts`，独立于配置 API
- 所有接口返回标准 JSON 响应
- 错误处理使用 HTTPException
- 业务加载接口复用 PromptLoader 单例

---

### Task 5: 注册到 Server 和 DI 容器

**Files:**
- Modify: `backend/src/server.py`
- Modify: `backend/src/core/di_container.py`

**server.py 改动:**
```python
# 在现有路由注册处添加
from src.controller.prompt_controller import router as prompt_router

app.include_router(prompt_router)
```

**di_container.py 改动:**
```python
# 在依赖注入容器初始化处添加
from src.config.prompt_manager import prompt_manager

# 确保 PromptManager 在应用启动时初始化
async def initialize_prompt_manager():
    await prompt_manager.initialize()
```

**改动说明:**
- PromptController 路由注册到 FastAPI 应用
- PromptManager 需要在应用启动时调用 `initialize()` 加载缓存

---

## Chunk 2: 前端页面实现

### 文件映射

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/pages/PromptManagementPage.tsx` | 创建 | 提示词管理页面容器 |
| `frontend/src/features/prompt-management/components/PromptList.tsx` | 创建 | 提示词列表和筛选组件 |
| `frontend/src/features/prompt-management/components/PromptEditor.tsx` | 创建 | 代码编辑器组件 |
| `frontend/src/features/prompt-management/components/PromptPreview.tsx` | 创建 | 实时预览组件 |
| `frontend/src/features/prompt-management/components/VersionHistory.tsx` | 创建 | 版本历史组件 |
| `frontend/src/features/prompt-management/store/promptStore.ts` | 创建 | Zustand 状态管理 |
| `frontend/src/features/prompt-management/api/promptApi.ts` | 创建 | API 调用层 |
| `frontend/src/router/index.tsx` | 修改 | 添加路由配置 |
| `frontend/src/layouts/MainLayout.tsx` (或类似文件) | 修改 | 添加菜单项 |

---

### Task 6: 创建 API 调用层

**Files:**
- Create: `frontend/src/features/prompt-management/api/promptApi.ts`

**职责:** 封装所有提示词相关的 API 调用

**代码:**
```typescript
import request from '@/api/request'; // 根据项目实际请求封装调整

export interface PromptItem {
  key: string;
  name: string;
  category: string;
  content: string;
  variables: string[];
  description: string;
  status: 'active' | 'inactive';
  current_version: string;
  created_at: string;
  updated_at: string;
  versions: Record<string, VersionItem>;
}

export interface VersionItem {
  content: string;
  change_log: string;
  created_at: string;
  created_by: string;
}

export interface CreatePromptDto {
  key: string;
  name: string;
  category: string;
  content: string;
  variables?: string[];
  description?: string;
  status?: string;
  change_log?: string;
  created_by?: string;
}

export interface UpdatePromptDto {
  content: string;
  change_log: string;
  updated_by?: string;
}

// 基础 CRUD
export const fetchPrompts = (params?: { category?: string; status?: string }) =>
  request.get<PromptItem[]>('/api/v1/prompts', { params });

export const fetchPrompt = (key: string) =>
  request.get<PromptItem>(`/api/v1/prompts/${key}`);

export const createPrompt = (data: CreatePromptDto) =>
  request.post<PromptItem>('/api/v1/prompts', data);

export const updatePrompt = (key: string, data: UpdatePromptDto) =>
  request.put<PromptItem>(`/api/v1/prompts/${key}`, data);

export const deletePrompt = (key: string) =>
  request.delete(`/api/v1/prompts/${key}`);

// 版本管理
export const fetchVersions = (key: string) =>
  request.get<VersionItem[]>(`/api/v1/prompts/${key}/versions`);

export const fetchVersion = (key: string, version: string) =>
  request.get<VersionItem>(`/api/v1/prompts/${key}/versions/${version}`);

export const rollbackVersion = (key: string, version: string) =>
  request.post<PromptItem>(`/api/v1/prompts/${key}/rollback`, { version });

export const diffVersions = (key: string, v1: string, v2: string) =>
  request.get(`/api/v1/prompts/${key}/diff`, { params: { v1, v2 } });

// 业务加载
export const loadPrompt = (key: string, variables?: Record<string, any>) =>
  request.get(`/api/v1/prompts/load/${key}`, { 
    params: { variables: variables ? JSON.stringify(variables) : undefined } 
  });

export const batchLoadPrompts = (keys: string[], variables?: Record<string, any>) =>
  request.post('/api/v1/prompts/batch-load', { keys, variables });

export const refreshCache = () =>
  request.post('/api/v1/prompts/refresh');
```

---

### Task 7: 创建 Zustand 状态管理

**Files:**
- Create: `frontend/src/features/prompt-management/store/promptStore.ts`

**代码:**
```typescript
import { create } from 'zustand';
import * as promptApi from '../api/promptApi';

interface PromptState {
  prompts: promptApi.PromptItem[];
  currentPrompt: promptApi.PromptItem | null;
  versions: promptApi.VersionItem[];
  loading: boolean;
  error: string | null;
  
  fetchPrompts: (params?: { category?: string; status?: string }) => Promise<void>;
  fetchPrompt: (key: string) => Promise<void>;
  updatePrompt: (key: string, data: promptApi.UpdatePromptDto) => Promise<void>;
  createPrompt: (data: promptApi.CreatePromptDto) => Promise<void>;
  deletePrompt: (key: string) => Promise<void>;
  fetchVersions: (key: string) => Promise<void>;
  rollbackVersion: (key: string, version: string) => Promise<void>;
  refreshCache: () => Promise<void>;
  setCurrentPrompt: (prompt: promptApi.PromptItem | null) => void;
  clearError: () => void;
}

export const usePromptStore = create<PromptState>((set, get) => ({
  prompts: [],
  currentPrompt: null,
  versions: [],
  loading: false,
  error: null,

  fetchPrompts: async (params) => {
    set({ loading: true, error: null });
    try {
      const prompts = await promptApi.fetchPrompts(params);
      set({ prompts, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchPrompt: async (key) => {
    set({ loading: true, error: null });
    try {
      const prompt = await promptApi.fetchPrompt(key);
      set({ currentPrompt: prompt, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  updatePrompt: async (key, data) => {
    set({ loading: true, error: null });
    try {
      const updated = await promptApi.updatePrompt(key, data);
      set({ currentPrompt: updated, loading: false });
      // 刷新列表
      get().fetchPrompts();
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  createPrompt: async (data) => {
    set({ loading: true, error: null });
    try {
      await promptApi.createPrompt(data);
      set({ loading: false });
      get().fetchPrompts();
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  deletePrompt: async (key) => {
    set({ loading: true, error: null });
    try {
      await promptApi.deletePrompt(key);
      set({ currentPrompt: null, loading: false });
      get().fetchPrompts();
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchVersions: async (key) => {
    set({ loading: true, error: null });
    try {
      const versions = await promptApi.fetchVersions(key);
      set({ versions, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  rollbackVersion: async (key, version) => {
    set({ loading: true, error: null });
    try {
      const updated = await promptApi.rollbackVersion(key, version);
      set({ currentPrompt: updated, loading: false });
      get().fetchVersions(key);
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  refreshCache: async () => {
    await promptApi.refreshCache();
  },

  setCurrentPrompt: (prompt) => set({ currentPrompt: prompt }),
  clearError: () => set({ error: null }),
}));
```

---

### Task 8: 创建 PromptList 组件

**Files:**
- Create: `frontend/src/features/prompt-management/components/PromptList.tsx`

**职责:** 左侧提示词列表，支持搜索、分类筛选、状态筛选

**代码结构:**
```typescript
import React, { useEffect, useState } from 'react';
import { Input, Select, List, Tag, Button, Space } from 'antd';
import { usePromptStore } from '../store/promptStore';

const { Search } = Input;
const { Option } = Select;

const CATEGORY_MAP: Record<string, string> = {
  assessment: '评估',
  scoring: '评分',
  reporting: '报告',
  retrieval: '检索',
  metadata: '元数据',
  validation: '校验',
  memory: '记忆管理',
  security: '安全防护',
};

export const PromptList: React.FC<{ onSelect: (key: string) => void }> = ({ onSelect }) => {
  const { prompts, fetchPrompts, currentPrompt } = usePromptStore();
  const [searchText, setSearchText] = useState('');
  const [category, setCategory] = useState<string>();
  const [status, setStatus] = useState<string>();

  useEffect(() => {
    fetchPrompts({ category, status });
  }, [category, status, fetchPrompts]);

  const filteredPrompts = prompts.filter(p => 
    p.key.toLowerCase().includes(searchText.toLowerCase()) ||
    p.name.includes(searchText)
  );

  return (
    <div style={{ padding: 16 }}>
      <Search
        placeholder="搜索提示词名称或标识"
        value={searchText}
        onChange={e => setSearchText(e.target.value)}
        style={{ marginBottom: 12 }}
      />
      <Space direction="vertical" style={{ width: '100%', marginBottom: 12 }}>
        <Select
          placeholder="分类筛选"
          allowClear
          value={category}
          onChange={setCategory}
          style={{ width: '100%' }}
        >
          {Object.entries(CATEGORY_MAP).map(([key, label]) => (
            <Option key={key} value={key}>{label}</Option>
          ))}
        </Select>
        <Select
          placeholder="状态筛选"
          allowClear
          value={status}
          onChange={setStatus}
          style={{ width: '100%' }}
        >
          <Option value="active">启用</Option>
          <Option value="inactive">停用</Option>
        </Select>
      </Space>
      <List
        dataSource={filteredPrompts}
        renderItem={item => (
          <List.Item
            style={{
              cursor: 'pointer',
              backgroundColor: currentPrompt?.key === item.key ? '#e6f7ff' : 'transparent',
              padding: '8px 12px',
              borderRadius: 4,
            }}
            onClick={() => onSelect(item.key)}
          >
            <div style={{ width: '100%' }}>
              <div style={{ fontWeight: 500 }}>{item.name}</div>
              <div style={{ fontSize: 12, color: '#888' }}>
                {item.key} · {CATEGORY_MAP[item.category] || item.category}
              </div>
              <Space style={{ marginTop: 4 }}>
                <Tag color={item.status === 'active' ? 'green' : 'default'}>
                  {item.status === 'active' ? '启用' : '停用'}
                </Tag>
                <span style={{ fontSize: 12, color: '#888' }}>{item.current_version}</span>
              </Space>
            </div>
          </List.Item>
        )}
      />
    </div>
  );
};
```

---

### Task 9: 创建 PromptEditor 组件

**Files:**
- Create: `frontend/src/features/prompt-management/components/PromptEditor.tsx`

**职责:** 右侧编辑区域，支持基础信息编辑和提示词内容编辑

**代码结构:**
```typescript
import React, { useState } from 'react';
import { Form, Input, Button, Tabs, Select, Switch, Tag, Space, message } from 'antd';
import { usePromptStore } from '../store/promptStore';

const { TextArea } = Input;
const { Option } = Select;

const CATEGORY_MAP: Record<string, string> = {
  assessment: '评估',
  scoring: '评分',
  reporting: '报告',
  retrieval: '检索',
  metadata: '元数据',
  validation: '校验',
  memory: '记忆管理',
  security: '安全防护',
};

export const PromptEditor: React.FC = () => {
  const { currentPrompt, updatePrompt, fetchVersions } = usePromptStore();
  const [form] = Form.useForm();
  const [activeTab, setActiveTab] = useState('basic');
  const [saving, setSaving] = useState(false);

  React.useEffect(() => {
    if (currentPrompt) {
      form.setFieldsValue(currentPrompt);
    }
  }, [currentPrompt, form]);

  const handleSave = async (values: any) => {
    if (!currentPrompt) return;
    setSaving(true);
    try {
      await updatePrompt(currentPrompt.key, {
        content: values.content,
        change_log: values.change_log || '更新提示词内容',
      });
      message.success('保存成功');
      fetchVersions(currentPrompt.key);
    } catch (err: any) {
      message.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (!currentPrompt) {
    return <div style={{ padding: 24, textAlign: 'center', color: '#888' }}>请选择一个提示词</div>;
  }

  const variables = currentPrompt.variables || [];
  const content = form.getFieldValue('content') || '';
  const extractedVars = (content.match(/\{\{(\w+(?:\.\w+)*)\}\}/g) || [])
    .map(v => v.replace(/[{}]/g, ''));
  const undefinedVars = extractedVars.filter(v => !variables.includes(v.split('.')[0]));

  const items = [
    {
      key: 'basic',
      label: '基础信息',
      children: (
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="key" label="标识">
            <Input disabled />
          </Form.Item>
          <Form.Item name="name" label="名称">
            <Input />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select>
              {Object.entries(CATEGORY_MAP).map(([key, label]) => (
                <Option key={key} value={key}>{label}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="status" label="状态" valuePropName="checked" getValueFromEvent={checked => checked ? 'active' : 'inactive'}>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
          <Form.Item name="variables" label="变量列表">
            <Select mode="tags" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={saving}>保存</Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'editor',
      label: '提示词编辑器',
      children: (
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="content" label="提示词内容">
            <TextArea 
              rows={20} 
              style={{ fontFamily: 'monospace', fontSize: 14 }}
            />
          </Form.Item>
          {undefinedVars.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <Tag color="orange">未定义的变量: {undefinedVars.join(', ')}</Tag>
            </div>
          )}
          <Form.Item name="change_log" label="变更说明">
            <Input placeholder="请描述本次变更内容" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={saving}>保存并创建新版本</Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'preview',
      label: '实时预览',
      children: <PromptPreview />,
    },
    {
      key: 'versions',
      label: '版本历史',
      children: <VersionHistory />,
    },
  ];

  return <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />;
};
```

---

### Task 10: 创建 PromptPreview 组件

**Files:**
- Create: `frontend/src/features/prompt-management/components/PromptPreview.tsx`

**职责:** 实时预览，输入变量值后渲染完整提示词

**代码结构:**
```typescript
import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography } from 'antd';
import { usePromptStore } from '../store/promptStore';

const { TextArea } = Input;
const { Text } = Typography;

export const PromptPreview: React.FC = () => {
  const { currentPrompt } = usePromptStore();
  const [variableValues, setVariableValues] = useState<Record<string, string>>({});
  const [previewContent, setPreviewContent] = useState('');

  if (!currentPrompt) return null;

  const variables = currentPrompt.variables || [];

  const handlePreview = () => {
    let content = currentPrompt.content;
    variables.forEach(v => {
      const value = variableValues[v] || `{{${v}}}`;
      content = content.replace(new RegExp(`\\{\\{${v}\\}\\}`, 'g'), value);
    });
    setPreviewContent(content);
  };

  const tokenCount = new Blob([previewContent]).size;

  return (
    <div style={{ padding: 16 }}>
      <Card title="变量值输入" style={{ marginBottom: 16 }}>
        {variables.map(v => (
          <Form.Item key={v} label={v}>
            <Input
              value={variableValues[v] || ''}
              onChange={e => setVariableValues({ ...variableValues, [v]: e.target.value })}
              placeholder={`输入 ${v} 的值`}
            />
          </Form.Item>
        ))}
        <Button type="primary" onClick={handlePreview}>预览</Button>
      </Card>
      {previewContent && (
        <Card title={`预览结果 (Token 数: ~${Math.ceil(tokenCount / 4)})`}>
          <Text style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
            {previewContent}
          </Text>
        </Card>
      )}
    </div>
  );
};
```

---

### Task 11: 创建 VersionHistory 组件

**Files:**
- Create: `frontend/src/features/prompt-management/components/VersionHistory.tsx`

**职责:** 版本列表、版本对比、回滚功能

**代码结构:**
```typescript
import React, { useEffect, useState } from 'react';
import { List, Button, Tag, Space, Modal, message, Select } from 'antd';
import { usePromptStore } from '../store/promptStore';

export const VersionHistory: React.FC = () => {
  const { currentPrompt, versions, fetchVersions, rollbackVersion } = usePromptStore();
  const [compareMode, setCompareMode] = useState(false);
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const [diffResult, setDiffResult] = useState<any>(null);

  useEffect(() => {
    if (currentPrompt) {
      fetchVersions(currentPrompt.key);
    }
  }, [currentPrompt, fetchVersions]);

  if (!currentPrompt) return null;

  const handleRollback = async (version: string) => {
    Modal.confirm({
      title: '确认回滚',
      content: `确定要回滚到版本 ${version} 吗？`,
      onOk: async () => {
        try {
          await rollbackVersion(currentPrompt.key, version);
          message.success('回滚成功');
        } catch (err: any) {
          message.error(err.message);
        }
      },
    });
  };

  return (
    <div style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button onClick={() => setCompareMode(!compareMode)}>
          {compareMode ? '退出对比模式' : '版本对比'}
        </Button>
        {compareMode && selectedVersions.length === 2 && (
          <Button type="primary" onClick={handleCompare}>执行对比</Button>
        )}
      </Space>
      <List
        dataSource={versions}
        renderItem={item => (
          <List.Item
            actions={[
              compareMode ? (
                <Button
                  type={selectedVersions.includes(item.version) ? 'primary' : 'default'}
                  onClick={() => toggleVersionSelect(item.version)}
                >
                  选择
                </Button>
              ) : (
                <Button onClick={() => handleRollback(item.version)}>回滚</Button>
              ),
            ]}
          >
            <div>
              <Tag color="blue">{item.version}</Tag>
              <span style={{ marginLeft: 8 }}>{item.change_log}</span>
              <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                {item.created_by} · {new Date(item.created_at).toLocaleString()}
              </div>
            </div>
          </List.Item>
        )}
      />
      {diffResult && (
        <Card title="版本对比" style={{ marginTop: 16 }}>
          <div style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
            {diffResult.removed.map((line: string, i: number) => (
              <div key={i} style={{ color: 'red', backgroundColor: '#ffe6e6' }}>- {line}</div>
            ))}
            {diffResult.added.map((line: string, i: number) => (
              <div key={i} style={{ color: 'green', backgroundColor: '#e6ffe6' }}>+ {line}</div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};
```

---

### Task 12: 创建 PromptManagementPage 页面

**Files:**
- Create: `frontend/src/pages/PromptManagementPage.tsx`

**代码:**
```typescript
import React from 'react';
import { Row, Col } from 'antd';
import { PromptList } from '@/features/prompt-management/components/PromptList';
import { PromptEditor } from '@/features/prompt-management/components/PromptEditor';
import { usePromptStore } from '@/features/prompt-management/store/promptStore';

const PromptManagementPage: React.FC = () => {
  const { fetchPrompt } = usePromptStore();

  const handleSelect = (key: string) => {
    fetchPrompt(key);
  };

  return (
    <div style={{ height: '100vh', overflow: 'hidden' }}>
      <Row style={{ height: '100%' }}>
        <Col span={6} style={{ borderRight: '1px solid #f0f0f0', overflow: 'auto' }}>
          <PromptList onSelect={handleSelect} />
        </Col>
        <Col span={18} style={{ overflow: 'auto' }}>
          <PromptEditor />
        </Col>
      </Row>
    </div>
  );
};

export default PromptManagementPage;
```

---

### Task 13: 添加路由和菜单

**Files:**
- Modify: `frontend/src/router/index.tsx`
- Modify: `frontend/src/layouts/MainLayout.tsx` (或实际菜单布局文件)

**router/index.tsx 改动:**
```typescript
// 在路由配置中添加
import PromptManagementPage from '@/pages/PromptManagementPage';

// 在路由数组中添加
{
  path: '/prompts',
  element: <PromptManagementPage />,
  meta: { title: '提示词管理' },
}
```

**MainLayout.tsx 菜单改动:**
```typescript
// 在菜单配置项中添加
{
  key: '/prompts',
  icon: <MessageOutlined />, // 或使用其他合适图标
  label: '提示词管理',
}
```

---

## Chunk 3: 数据初始化和业务代码替换

### 文件映射

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/data/prompts/*.json` | 创建 (21个) | 初始化所有提示词 JSON 文件 |
| `backend/src/core/prompts.py` | 保留 | 作为降级默认值，不删除 |
| `backend/src/core/nodes/retrieval.py` | 修改 | 替换为 PromptLoader |
| `backend/src/service/retrieval_service.py` | 修改 | 替换为 PromptLoader |
| `backend/src/core/metadata_extractor.py` | 修改 | 替换为 PromptLoader |
| `backend/src/core/nodes/validation.py` | 修改 | 替换为 PromptLoader |
| `backend/src/core/nodes/assessment.py` | 修改 | 替换为 PromptLoader |
| `backend/src/core/nodes/reporting.py` | 修改 | 替换为 PromptLoader |
| `backend/src/core/layered_content_generator.py` | 修改 | 提取硬编码提示词，替换为 PromptLoader |
| `backend/src/core/ml/qwen_scorer.py` | 修改 | 提取硬编码提示词，替换为 PromptLoader |
| `backend/src/core/query_router.py` | 修改 | 提取硬编码提示词，替换为 PromptLoader |
| `backend/src/core/memory_manager.py` | 修改 | 提取硬编码提示词，替换为 PromptLoader |
| `backend/src/core/prompt_injection_guard.py` | 修改 | 提取硬编码提示词，替换为 PromptLoader |

---

### Task 14: 创建初始提示词 JSON 文件

**Files:**
- Create: `backend/data/prompts/RAG_QUERY_TEMPLATE.json`
- Create: `backend/data/prompts/QUERY_REWRITE_PROMPT.json`
- Create: `backend/data/prompts/SYNONYM_EXPANSION_PROMPT.json`
- Create: `backend/data/prompts/METADATA_EXTRACTION_PROMPT.json`
- Create: `backend/data/prompts/VALIDATION_SYSTEM_PROMPT.json`
- Create: `backend/data/prompts/INTENSITY_INFERENCE_PROMPT.json`
- Create: `backend/data/prompts/CATEGORY_INFERENCE_PROMPT.json`
- Create: `backend/data/prompts/ASSESSMENT_SYSTEM_PROMPT.json`
- Create: `backend/data/prompts/SCORING_SYSTEM_PROMPT.json`
- Create: `backend/data/prompts/REPORTING_SYSTEM_PROMPT.json`
- Create: `backend/data/prompts/LAYERED_CONTENT_L0_PROMPT.json`
- Create: `backend/data/prompts/LAYERED_CONTENT_L1_PROMPT.json`
- Create: `backend/data/prompts/LAYERED_CONTENT_BATCH_PROMPT.json`
- Create: `backend/data/prompts/LAYERED_CONTENT_MERGE_PROMPT.json`
- Create: `backend/data/prompts/QWEN_SCORER_SYSTEM_PROMPT.json`
- Create: `backend/data/prompts/QWEN_SCORER_USER_PROMPT.json`
- Create: `backend/data/prompts/QUERY_ROUTER_PROMPT.json`
- Create: `backend/data/prompts/MEMORY_PREFERENCE_PROMPT.json`
- Create: `backend/data/prompts/MEMORY_EXPERIENCE_PROMPT.json`
- Create: `backend/data/prompts/PROMPT_INJECTION_GUARD_PROMPT.json`
- Create: `backend/data/prompts/REPORTING_FALLBACK_TEMPLATE.json`

**每个 JSON 文件结构示例:**
```json
{
  "key": "ASSESSMENT_SYSTEM_PROMPT",
  "name": "评估系统提示词",
  "category": "assessment",
  "content": "从 prompts.py 中复制的实际内容...",
  "variables": ["milestones", "input_data"],
  "description": "用于 Node2 评估节点的系统提示词",
  "status": "active",
  "current_version": "v1.0.0",
  "created_at": "2026-04-09T10:00:00Z",
  "updated_at": "2026-04-09T10:00:00Z",
  "versions": {
    "v1.0.0": {
      "content": "从 prompts.py 中复制的实际内容...",
      "change_log": "初始版本，从 prompts.py 迁移",
      "created_at": "2026-04-09T10:00:00Z",
      "created_by": "system"
    }
  }
}
```

**改动说明:**
- 从 `backend/src/core/prompts.py` 中提取每个提示词的实际内容
- 分析每个提示词中的 `{{variable}}` 或 `.format()` 占位符，填入 `variables` 数组
- 对于硬编码在业务代码中的提示词，需要从对应文件中提取内容

---

### Task 15: 替换 nodes/retrieval.py

**Files:**
- Modify: `backend/src/core/nodes/retrieval.py`

**改动:**
```python
# 替换前 (L6, L17-19)
from src.core.prompts import RAG_QUERY_TEMPLATE

# 使用
prompt = RAG_QUERY_TEMPLATE.format(issues=issues, goals=goals)

# 替换后
from src.core.prompt_loader import prompt_loader

# 使用
prompt = prompt_loader.load("RAG_QUERY_TEMPLATE", issues=issues, goals=goals)
```

**改动说明:**
- 删除 `from src.core.prompts import RAG_QUERY_TEMPLATE`
- 添加 `from src.core.prompt_loader import prompt_loader`
- 将 `.format()` 调用改为 `prompt_loader.load()` 并传入变量

---

### Task 16: 替换 service/retrieval_service.py

**Files:**
- Modify: `backend/src/service/retrieval_service.py`

**改动:**
```python
# 替换前 (L16, L777, L852-856)
from src.core.prompts import QUERY_REWRITE_PROMPT, SYNONYM_EXPANSION_PROMPT

# L777
prompt = QUERY_REWRITE_PROMPT.format(age=age, query=query)

# L852-856
prompt_template = PromptTemplate.from_template(SYNONYM_EXPANSION_PROMPT)

# 替换后
from src.core.prompt_loader import prompt_loader

# L777
prompt = prompt_loader.load("QUERY_REWRITE_PROMPT", age=age, query=query)

# L852-856
template = prompt_loader.load_raw("SYNONYM_EXPANSION_PROMPT")
prompt_template = PromptTemplate.from_template(template)
```

**改动说明:**
- 删除 prompts.py 导入
- 添加 prompt_loader 导入
- `.format()` 改为 `prompt_loader.load()`
- 直接使用模板字符串的地方改用 `prompt_loader.load_raw()`

---

### Task 17: 替换 core/metadata_extractor.py

**Files:**
- Modify: `backend/src/core/metadata_extractor.py`

**改动:**
```python
# 替换前 (L8, L167)
from src.core.prompts import METADATA_EXTRACTION_PROMPT

# L167
prompt = METADATA_EXTRACTION_PROMPT.format(text=truncated_text)

# 替换后
from src.core.prompt_loader import prompt_loader

# L167
prompt = prompt_loader.load("METADATA_EXTRACTION_PROMPT", text=truncated_text)
```

---

### Task 18: 替换 nodes/validation.py

**Files:**
- Modify: `backend/src/core/nodes/validation.py`

**改动:**
```python
# 替换前 (L7, L49, L88)
from src.core.prompts import INTENSITY_INFERENCE_PROMPT, CATEGORY_INFERENCE_PROMPT

# L49
prompt = INTENSITY_INFERENCE_PROMPT.format(age=age, activity_name=activity_name)

# L88
prompt = CATEGORY_INFERENCE_PROMPT.format(age=age, activity_name=activity_name)

# 替换后
from src.core.prompt_loader import prompt_loader

# L49
prompt = prompt_loader.load("INTENSITY_INFERENCE_PROMPT", age=age, activity_name=activity_name)

# L88
prompt = prompt_loader.load("CATEGORY_INFERENCE_PROMPT", age=age, activity_name=activity_name)
```

---

### Task 19: 替换 nodes/assessment.py

**Files:**
- Modify: `backend/src/core/nodes/assessment.py`

**改动:**
```python
# 替换前 (L8, L46-49)
from src.core.prompts import ASSESSMENT_SYSTEM_PROMPT

# L46-49
system_prompt = ASSESSMENT_SYSTEM_PROMPT.format(
    milestones=milestones_text,
    input_data=input_text,
)

# 替换后
from src.core.prompt_loader import prompt_loader

# L46-49
system_prompt = prompt_loader.load(
    "ASSESSMENT_SYSTEM_PROMPT",
    milestones=milestones_text,
    input_data=input_text,
)
```

---

### Task 20: 替换 nodes/reporting.py

**Files:**
- Modify: `backend/src/core/nodes/reporting.py`

**改动:**
```python
# 替换前 (L14, L186)
from src.core.prompts import REPORTING_SYSTEM_PROMPT

# L186 (使用自定义 format_prompt 函数)
prompt = format_prompt(REPORTING_SYSTEM_PROMPT, **context)

# 替换后
from src.core.prompt_loader import prompt_loader

# L186
prompt = prompt_loader.load("REPORTING_SYSTEM_PROMPT", **context)
```

**改动说明:**
- 如果 `format_prompt()` 是自定义函数，确认其变量名与 JSON 中 `variables` 字段一致
- 如果不一致，需要调整 JSON 中的 variables 或修改调用方式

---

### Task 21: 替换 layered_content_generator.py

**Files:**
- Modify: `backend/src/core/layered_content_generator.py`

**改动:**
```python
# 替换前 (L129-133, L141-145, L186-192, L237-243)
# 硬编码的 4 个提示词字符串

# 替换后
from src.core.prompt_loader import prompt_loader

# L129-133 位置
l0_prompt = prompt_loader.load("LAYERED_CONTENT_L0_PROMPT", content=chunk_content)

# L141-145 位置
l1_prompt = prompt_loader.load("LAYERED_CONTENT_L1_PROMPT", content=chunk_content)

# L186-192 位置
batch_prompt = prompt_loader.load("LAYERED_CONTENT_BATCH_PROMPT", contents=batch_data)

# L237-243 位置
merge_prompt = prompt_loader.load("LAYERED_CONTENT_MERGE_PROMPT", results=results_data)
```

**改动说明:**
- 需要从代码中提取 4 个硬编码提示词的实际内容
- 创建对应的 JSON 文件到 `backend/data/prompts/` 目录
- 分析变量名并填入 JSON 的 `variables` 字段

---

### Task 22: 替换 ml/qwen_scorer.py

**Files:**
- Modify: `backend/src/core/ml/qwen_scorer.py`

**改动:**
```python
# 替换前 (L59-66, L68-89)
system_prompt = "你是一个专业的儿童发展评估评分专家..."
user_prompt = f"请对以下计划进行评分...\n\n计划: {plan_data}\n..."

# 替换后
from src.core.prompt_loader import prompt_loader

system_prompt = prompt_loader.load_raw("QWEN_SCORER_SYSTEM_PROMPT")
user_prompt = prompt_loader.load("QWEN_SCORER_USER_PROMPT", plan_data=plan_data, ...)
```

**改动说明:**
- 提取 2 个硬编码提示词内容
- 分析 user_prompt 中的 f-string 变量，填入 JSON 的 variables

---

### Task 23: 替换 query_router.py

**Files:**
- Modify: `backend/src/core/query_router.py`

**改动:**
```python
# 替换前 (L133-153)
# _llm_classify 方法中的硬编码提示词

# 替换后
from src.core.prompt_loader import prompt_loader

# 在 _llm_classify 方法中
prompt = prompt_loader.load("QUERY_ROUTER_PROMPT", query=query)
```

---

### Task 24: 替换 memory_manager.py

**Files:**
- Modify: `backend/src/core/memory_manager.py`

**改动:**
```python
# 替换前 (L173-179, L198-204)
# 用户偏好提取提示词
# 任务经验提取提示词

# 替换后
from src.core.prompt_loader import prompt_loader

# L173-179
prompt = prompt_loader.load("MEMORY_PREFERENCE_PROMPT", conversation=conversation_text)

# L198-204
prompt = prompt_loader.load("MEMORY_EXPERIENCE_PROMPT", task=task_data)
```

---

### Task 25: 替换 prompt_injection_guard.py

**Files:**
- Modify: `backend/src/core/prompt_injection_guard.py`

**改动:**
```python
# 替换前 (L123-135)
# safe_wrap_prompt 方法中的安全包装提示词

# 替换后
from src.core.prompt_loader import prompt_loader

# L123-135
template = prompt_loader.load_raw("PROMPT_INJECTION_GUARD_PROMPT")
# 使用 template 包装用户输入
```

---

## Chunk 4: 测试和优化

### Task 26: 编写后端单元测试

**Files:**
- Create: `backend/tests/test_prompt_repository.py`
- Create: `backend/tests/test_prompt_manager.py`
- Create: `backend/tests/test_prompt_loader.py`

**测试要点:**
- PromptRepository: JSON 读写、文件不存在处理、并发安全
- PromptManager: CRUD 操作、版本管理、缓存、热重载、版本号递增
- PromptLoader: 变量渲染、降级机制、批量加载、变量提取

---

### Task 27: 端到端测试验证

**验证清单:**
- [ ] 启动后端服务，访问 `/api/v1/prompts` 返回提示词列表
- [ ] 创建新提示词，验证 JSON 文件生成
- [ ] 更新提示词，验证版本号自动递增
- [ ] 回滚到历史版本，验证内容恢复
- [ ] 前端页面加载，列表和编辑功能正常
- [ ] 实时预览，输入变量后渲染正确
- [ ] 版本对比，差异高亮显示
- [ ] 业务代码通过 PromptLoader 加载提示词正常
- [ ] 删除 JSON 文件后，降级到 prompts.py 硬编码值生效

---

### Task 28: 更新文档

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`

**更新内容:**
- 在系统架构总览中添加 PromptManager/PromptLoader 模块
- 在配置系统架构中添加提示词管理子模块
- 更新代码规范中的提示词管理规则
- 在核心基础设施章节添加提示词管理系统说明

---

## 实施顺序和依赖关系

```
阶段1: 后端核心 (Task 1-5)
  Task 1: PromptRepository (无依赖)
  Task 2: PromptManager (依赖 Task 1)
  Task 3: PromptLoader (依赖 Task 2)
  Task 4: PromptController (依赖 Task 2, 3)
  Task 5: 注册路由 (依赖 Task 4)

阶段2: 前端页面 (Task 6-13)
  Task 6: API 层 (无依赖)
  Task 7: Store (依赖 Task 6)
  Task 8: PromptList (依赖 Task 7)
  Task 9: PromptEditor (依赖 Task 7)
  Task 10: PromptPreview (依赖 Task 7)
  Task 11: VersionHistory (依赖 Task 7)
  Task 12: 页面容器 (依赖 Task 8-11)
  Task 13: 路由和菜单 (依赖 Task 12)

阶段3: 数据初始化和替换 (Task 14-25)
  Task 14: 创建 JSON 文件 (无依赖)
  Task 15-25: 替换业务代码 (依赖 Task 3, 14)

阶段4: 测试和优化 (Task 26-28)
  Task 26: 单元测试 (依赖 Task 1-3)
  Task 27: 端到端测试 (依赖所有阶段)
  Task 28: 更新文档 (依赖所有阶段)
```

---

## 风险和注意事项

1. **JSON 并发写入**: PromptRepository 使用 asyncio.Lock 保证单进程并发安全，多进程部署需考虑文件锁
2. **变量渲染冲突**: 提示词中包含 `{{}}` 但不是变量的情况，需要在 JSON 的 variables 中声明或使用转义机制
3. **降级测试**: 确保 prompts.py 保留所有提示词作为降级默认值
4. **前端编辑器**: 考虑使用 Monaco Editor 或 CodeMirror 替代 TextArea，支持语法高亮和变量高亮
5. **Token 计数**: 前端预览中的 Token 计数是估算值（按字符/4），可接入 tiktoken 库精确计算
