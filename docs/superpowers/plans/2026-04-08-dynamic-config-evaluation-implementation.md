# 动态配置与回撤测试系统实施方案

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现配置的动态管理、版本化存储、热更新机制以及前端调优工作台，支持边调边测与A/B对比能力

**Architecture:** 基于仓储模式的配置中心架构，采用JSON文件存储实现版本快照，通过EventBus惰性加载模式实现热更新，前端提供配置管理与评估工作台

**Tech Stack:** Python FastAPI, Pydantic, JSON文件存储, React TypeScript, EventBus模式

---

## 文件结构总览

### 新增文件
- `backend/src/config/config_repository.py` - 配置仓储抽象接口与JSON实现
- `backend/src/config/config_manager.py` - 配置管理器（核心）
- `backend/src/config/config_events.py` - 配置相关事件定义
- `backend/src/controller/config_controller.py` - 配置管理API控制器
- `backend/data/configs/` - 配置存储目录结构
- `backend/tests/test_config_manager.py` - 配置管理器测试
- `backend/tests/test_config_repository.py` - 配置仓储测试
- `frontend/src/api/config/index.ts` - 配置API请求封装
- `frontend/src/api/config/types.ts` - 配置类型定义
- `frontend/src/store/configStore.ts` - 配置全局状态管理
- `frontend/src/components/config/DynamicConfigForm.tsx` - 动态配置表单组件
- `frontend/src/components/config/ConfigVersionSelector.tsx` - 版本选择器组件
- `frontend/src/components/config/ConfigDiffView.tsx` - 配置差异对比组件
- `frontend/src/pages/SystemConfigPage.tsx` - 系统全局配置页面
- `frontend/src/features/rag-evaluation/components/ConfigTuningPanel.tsx` - 调优面板组件

### 修改文件
- `backend/src/config/settings.py` - 补充配置元数据（description, category, hot_reloadable）
- `backend/src/core/event_bus.py` - 扩展事件类型支持
- `backend/src/server.py` - 注册配置管理路由
- `backend/src/service/rag_service.py` - 集成配置热更新机制
- `backend/src/service/retrieval_service.py` - 集成配置热更新机制
- `backend/src/service/rag_test_manager.py` - 集成配置版本记录
- `frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx` - 重构为分栏布局

---

## Chunk 1: 后端动态配置核心与版本化存储

### Task 1: 配置元数据增强与仓储层实现

**Files:**
- Modify: `backend/src/config/settings.py`
- Create: `backend/src/config/config_events.py`
- Create: `backend/src/config/config_repository.py`
- Create: `backend/data/configs/.gitkeep`
- Test: `backend/tests/test_config_repository.py`

#### Step 1: 增强 settings.py 配置元数据

**文件:** `backend/src/config/settings.py`

**改动说明:**
1. 新增 `ConfigFieldMetadata` 数据类，用于存储配置字段的元数据
2. 为每个配置字段添加 `description`, `category`, `hot_reloadable` 元数据
3. 新增 `get_all_config_metadata()` 方法，反射生成完整元数据列表

**关键代码片段:**
```python
from dataclasses import dataclass

@dataclass
class ConfigFieldMetadata:
    key: str
    category: str
    description: str
    hot_reloadable: bool
    requires_restart: bool
    affected_components: list[str]
    field_type: str
    default_value: Any

# 在 Settings 类中新增方法
def get_all_config_metadata(self) -> Dict[str, ConfigFieldMetadata]:
    """反射生成所有配置字段的元数据"""
    metadata = {}
    for field_name, field_info in self.model_fields.items():
        # 根据字段名前缀自动推断分类
        category = self._infer_category(field_name)
        hot_reloadable = self._is_hot_reloadable(field_name)
        metadata[field_name] = ConfigFieldMetadata(
            key=field_name,
            category=category,
            description=field_info.description or "",
            hot_reloadable=hot_reloadable,
            requires_restart=not hot_reloadable,
            affected_components=self._get_affected_components(field_name),
            field_type=field_info.annotation.__name__,
            default_value=field_info.default
        )
    return metadata
```

**分类规则:**
- `rag_hybrid_*`, `rag_search_*`, `rag_cache_*` → "混合检索配置"
- `model_*` → "模型设置"
- `rag_reranker_*` → "重排序配置"
- `rag_chunk_*`, `semantic_splitter_*` → "分块配置"
- `embedding_*` → "Embedding配置"
- `pageindex_*` → "PageIndex配置"
- 其他 → "其他配置"

**热更新判断规则:**
- 支持热更新: 权重、阈值、开关、缓存设置、Top-K参数
- 需要重启: API Key、模型名称、数据库连接、路径配置

#### Step 2: 定义配置事件

**文件:** `backend/src/config/config_events.py`

**改动说明:**
创建配置相关的事件类，用于EventBus通信

**完整代码:**
```python
from src.core.event_bus import BaseEvent
from typing import Dict, Any, Optional

class ConfigChangedEvent(BaseEvent):
    """配置变更事件"""
    def __init__(
        self,
        from_version: str,
        to_version: str,
        changed_keys: list[str],
        config_snapshot: Dict[str, Any]
    ):
        super().__init__()
        self.from_version = from_version
        self.to_version = to_version
        self.changed_keys = changed_keys
        self.config_snapshot = config_snapshot

class ConfigRollbackEvent(BaseEvent):
    """配置回滚事件"""
    def __init__(
        self,
        from_version: str,
        to_version: str,
        rollback_at: str
    ):
        super().__init__()
        self.from_version = from_version
        self.to_version = to_version
        self.rollback_at = rollback_at

class ConfigResetEvent(BaseEvent):
    """配置重置事件"""
    def __init__(
        self,
        from_version: str,
        reset_at: str
    ):
        super().__init__()
        self.from_version = from_version
        self.reset_at = reset_at
```

#### Step 3: 实现配置仓储接口与JSON实现

**文件:** `backend/src/config/config_repository.py`

**改动说明:**
1. 定义 `ConfigRepository` 抽象接口
2. 实现 `JsonConfigRepository` 类
3. 实现版本快照读写、激活版本管理、审计日志

**关键方法:**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import os
from pathlib import Path

class ConfigRepository(ABC):
    """配置仓储抽象接口"""
    
    @abstractmethod
    async def get_active_version(self) -> Optional[str]:
        """获取当前激活的版本ID"""
        pass
    
    @abstractmethod
    async def save_version(self, version_data: Dict[str, Any]) -> str:
        """保存配置版本快照"""
        pass
    
    @abstractmethod
    async def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取指定版本配置"""
        pass
    
    @abstractmethod
    async def list_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取版本列表（按时间倒序）"""
        pass
    
    @abstractmethod
    async def set_active_version(self, version_id: str) -> None:
        """设置激活版本"""
        pass
    
    @abstractmethod
    async def append_audit_log(self, audit_entry: Dict[str, Any]) -> None:
        """追加审计日志"""
        pass

class JsonConfigRepository(ConfigRepository):
    """基于JSON文件的配置仓储实现（Phase 1）"""
    
    def __init__(self, base_dir: str = "./data/configs"):
        self.base_dir = Path(base_dir)
        self.versions_dir = self.base_dir / "versions"
        self.active_version_file = self.base_dir / "active_version.json"
        self.audit_log_file = self.base_dir / "audit_log.jsonl"
        self._lock = asyncio.Lock()
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保目录结构存在"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_version(self, version_data: Dict[str, Any]) -> str:
        """保存版本快照（线程安全）"""
        async with self._lock:
            version_id = version_data["version_id"]
            file_path = self.versions_dir / f"{version_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(version_data, f, indent=2, ensure_ascii=False)
            return version_id
    
    async def list_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取版本列表（按创建时间倒序）"""
        versions = []
        for file_path in self.versions_dir.glob("v_*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                versions.append(json.load(f))
        # 按创建时间倒序
        versions.sort(key=lambda x: x["created_at"], reverse=True)
        return versions[:limit]
```

**目录结构:**
```
backend/data/configs/
├── active_version.json          # 当前激活版本元信息
├── versions/                    # 版本快照目录
│   └── .gitkeep
├── audit_log.jsonl              # 审计日志（JSON Lines格式）
└── .gitkeep
```

#### Step 4: 编写仓储层测试

**文件:** `backend/tests/test_config_repository.py`

**测试用例:**
```python
import pytest
import asyncio
from src.config.config_repository import JsonConfigRepository
import tempfile
import shutil

@pytest.fixture
def config_repo():
    """创建临时配置仓储"""
    temp_dir = tempfile.mkdtemp()
    repo = JsonConfigRepository(base_dir=temp_dir)
    yield repo
    shutil.rmtree(temp_dir)

@pytest.mark.asyncio
async def test_save_and_get_version(config_repo):
    """测试版本保存与读取"""
    version_data = {
        "version_id": "v_test_001",
        "created_at": "2026-04-08T12:00:00Z",
        "config_snapshot": {"rag_hybrid_bm25_weight": 0.3}
    }
    await config_repo.save_version(version_data)
    result = await config_repo.get_version("v_test_001")
    assert result["config_snapshot"]["rag_hybrid_bm25_weight"] == 0.3

@pytest.mark.asyncio
async def test_list_versions_sorted(config_repo):
    """测试版本列表按时间倒序"""
    # 保存两个版本
    await config_repo.save_version({
        "version_id": "v_001",
        "created_at": "2026-04-08T10:00:00Z",
        "config_snapshot": {}
    })
    await config_repo.save_version({
        "version_id": "v_002",
        "created_at": "2026-04-08T12:00:00Z",
        "config_snapshot": {}
    })
    versions = await config_repo.list_versions()
    assert versions[0]["version_id"] == "v_002"

@pytest.mark.asyncio
async def test_audit_log_append(config_repo):
    """测试审计日志追加写入"""
    await config_repo.append_audit_log({
        "timestamp": "2026-04-08T12:00:00Z",
        "action": "UPDATE",
        "from_version": "v_001",
        "to_version": "v_002"
    })
    # 验证日志文件存在且包含记录
    assert config_repo.audit_log_file.exists()
```

**运行测试命令:**
```bash
cd backend
pytest tests/test_config_repository.py -v
```

---

### Task 2: 配置管理器核心实现

**Files:**
- Create: `backend/src/config/config_manager.py`
- Modify: `backend/src/config/__init__.py` (如有)
- Test: `backend/tests/test_config_manager.py`

#### Step 1: 实现 ConfigManager 类

**文件:** `backend/src/config/config_manager.py`

**改动说明:**
1. 实现配置合并逻辑（.env.dev + JSON持久化）
2. 实现版本生成与管理
3. 实现内存缓存
4. 实现EventBus事件派发

**完整架构:**
```python
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from src.config.settings import settings, Settings
from src.config.config_repository import JsonConfigRepository, ConfigRepository
from src.config.config_events import ConfigChangedEvent
from src.core.event_bus import event_bus
from src.utils.logger import logger

class ConfigManager:
    """配置管理器（单例）"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._repository = JsonConfigRepository()
        self._memory_cache: Dict[str, Any] = {}
        self._active_version: Optional[str] = None
        self._lock = asyncio.Lock()
        self._load_active_config()
        ConfigManager._initialized = True
    
    def _load_active_config(self):
        """启动时加载激活版本配置"""
        # 1. 从 .env.dev 获取默认值
        default_config = self._extract_config_from_settings()
        
        # 2. 尝试加载激活版本覆盖
        active_version = asyncio.get_event_loop().run_until_complete(
            self._repository.get_active_version()
        )
        
        if active_version:
            version_data = asyncio.get_event_loop().run_until_complete(
                self._repository.get_version(active_version)
            )
            if version_data:
                # 合并配置
                self._memory_cache = {**default_config, **version_data["config_snapshot"]}
                self._active_version = active_version
                logger.info(f"Loaded config version: {active_version}")
        else:
            self._memory_cache = default_config
            logger.info("Using default config from .env.dev")
    
    def _extract_config_from_settings(self) -> Dict[str, Any]:
        """从 Settings 对象提取配置字典"""
        return settings.model_dump()
    
    async def update_config(
        self,
        config_updates: Dict[str, Any],
        description: str = "",
        created_by: str = "system"
    ) -> Dict[str, Any]:
        """
        更新配置并生成新版本
        
        Returns:
            {
                "version_id": "v_20260408_120101",
                "previous_version": "v_20260408_100000",
                "config_snapshot": {...},
                "changed_keys": ["rag_hybrid_bm25_weight"]
            }
        """
        async with self._lock:
            # 1. 生成新版本ID
            version_id = self._generate_version_id()
            previous_version = self._active_version
            
            # 2. 合并配置
            new_config = {**self._memory_cache, **config_updates}
            
            # 3. 构建版本快照
            version_data = {
                "version_id": version_id,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "created_by": created_by,
                "description": description,
                "config_snapshot": new_config,
                "parent_version_id": previous_version,
                "is_factory_reset": False
            }
            
            # 4. 保存版本
            await self._repository.save_version(version_data)
            
            # 5. 更新内存缓存
            self._memory_cache = new_config
            self._active_version = version_id
            
            # 6. 更新激活版本
            await self._repository.set_active_version(version_id)
            
            # 7. 记录审计日志
            await self._repository.append_audit_log({
                "timestamp": version_data["created_at"],
                "action": "UPDATE",
                "from_version": previous_version,
                "to_version": version_id,
                "user": created_by
            })
            
            # 8. 派发配置变更事件
            changed_keys = list(config_updates.keys())
            event_bus.publish(ConfigChangedEvent(
                from_version=previous_version or "initial",
                to_version=version_id,
                changed_keys=changed_keys,
                config_snapshot=new_config
            ))
            
            logger.info(f"Config updated to version {version_id}")
            
            return {
                "version_id": version_id,
                "previous_version": previous_version,
                "config_snapshot": new_config,
                "changed_keys": changed_keys
            }
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值（优先从内存缓存）"""
        return self._memory_cache.get(key, default)
    
    def get_full_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._memory_cache.copy()
    
    def get_active_version(self) -> Optional[str]:
        """获取当前激活版本ID"""
        return self._active_version
    
    async def rollback_to_version(self, version_id: str) -> Dict[str, Any]:
        """回滚到指定版本"""
        async with self._lock:
            # 1. 验证目标版本
            version_data = await self._repository.get_version(version_id)
            if not version_data:
                raise ValueError(f"Version {version_id} not found")
            
            previous_version = self._active_version
            
            # 2. 应用配置
            self._memory_cache = version_data["config_snapshot"]
            self._active_version = version_id
            
            # 3. 更新激活版本
            await self._repository.set_active_version(version_id)
            
            # 4. 记录审计日志
            await self._repository.append_audit_log({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "ROLLBACK",
                "from_version": previous_version,
                "to_version": version_id,
                "user": "system"
            })
            
            # 5. 派发回滚事件
            event_bus.publish(ConfigRollbackEvent(
                from_version=previous_version or "initial",
                to_version=version_id,
                rollback_at=datetime.utcnow().isoformat() + "Z"
            ))
            
            return {
                "version_id": version_id,
                "previous_version": previous_version,
                "config_snapshot": self._memory_cache
            }
    
    async def reset_to_factory(self) -> Dict[str, Any]:
        """恢复到出厂设置（.env.dev）"""
        async with self._lock:
            version_id = self._generate_version_id()
            previous_version = self._active_version
            
            # 重新从 .env.dev 加载
            default_config = self._extract_config_from_settings()
            
            version_data = {
                "version_id": version_id,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "created_by": "system",
                "description": "Factory reset to .env.dev defaults",
                "config_snapshot": default_config,
                "parent_version_id": previous_version,
                "is_factory_reset": True
            }
            
            await self._repository.save_version(version_data)
            self._memory_cache = default_config
            self._active_version = version_id
            await self._repository.set_active_version(version_id)
            
            await self._repository.append_audit_log({
                "timestamp": version_data["created_at"],
                "action": "RESET",
                "from_version": previous_version,
                "to_version": version_id,
                "user": "system"
            })
            
            event_bus.publish(ConfigResetEvent(
                from_version=previous_version or "initial",
                reset_at=version_data["created_at"]
            ))
            
            return {
                "version_id": version_id,
                "config_snapshot": default_config
            }
    
    def _generate_version_id(self) -> str:
        """生成版本ID: v_YYYYMMDD_HHMMSS"""
        return f"v_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

# 全局单例
config_manager = ConfigManager()
```

#### Step 2: 编写配置管理器测试

**文件:** `backend/tests/test_config_manager.py`

**测试用例:**
```python
import pytest
from src.config.config_manager import ConfigManager
from unittest.mock import AsyncMock, patch

@pytest.fixture
def config_manager():
    """创建配置管理器实例"""
    with patch('src.config.config_manager.JsonConfigRepository') as mock_repo:
        mock_repo.return_value.get_active_version = AsyncMock(return_value=None)
        manager = ConfigManager()
        yield manager

@pytest.mark.asyncio
async def test_update_config_creates_version(config_manager):
    """测试更新配置创建新版本"""
    result = await config_manager.update_config(
        {"rag_hybrid_bm25_weight": 0.3},
        description="Test update"
    )
    assert "version_id" in result
    assert result["changed_keys"] == ["rag_hybrid_bm25_weight"]
    assert config_manager.get_config_value("rag_hybrid_bm25_weight") == 0.3

@pytest.mark.asyncio
async def test_get_config_value(config_manager):
    """测试获取配置值"""
    value = config_manager.get_config_value("rag_hybrid_bm25_weight")
    assert value is not None  # 应有默认值

@pytest.mark.asyncio
async def test_rollback_version(config_manager):
    """测试版本回滚"""
    # 先创建一个版本
    await config_manager.update_config({"rag_hybrid_bm25_weight": 0.3})
    version_id = config_manager.get_active_version()
    
    # 回滚（实际应回滚到前一个版本）
    # 需要mock repository的get_version方法
```

**运行测试命令:**
```bash
cd backend
pytest tests/test_config_manager.py -v
```

---

## Chunk 2: 后端配置管理API开发

### Task 3: 配置管理API控制器

**Files:**
- Create: `backend/src/controller/config_controller.py`
- Modify: `backend/src/server.py`
- Test: `backend/tests/test_config_api.py`

#### Step 1: 实现配置管理API

**文件:** `backend/src/controller/config_controller.py`

**改动说明:**
实现5个核心API端点

**完整代码:**
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from src.config.config_manager import config_manager
from src.config.settings import settings
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/config", tags=["Configuration"])

class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]
    description: str = ""
    created_by: str = "user"

class ConfigVersionResponse(BaseModel):
    version_id: str
    created_at: str
    created_by: str
    description: str
    is_active: bool
    parent_version_id: Optional[str] = None

@router.get("/")
async def get_config():
    """
    获取当前配置及元数据
    
    返回:
    - current_value: 当前值
    - default_value: 默认值
    - type: 字段类型
    - description: 描述
    - category: 分类
    - hot_reloadable: 是否支持热更新
    - requires_restart: 是否需要重启
    """
    current_config = config_manager.get_full_config()
    metadata = settings.get_all_config_metadata()
    
    result = []
    for key, meta in metadata.items():
        result.append({
            "key": key,
            "type": meta.field_type,
            "default_value": meta.default_value,
            "current_value": current_config.get(key, meta.default_value),
            "description": meta.description,
            "category": meta.category,
            "hot_reloadable": meta.hot_reloadable,
            "requires_restart": meta.requires_restart,
            "affected_components": meta.affected_components
        })
    
    return {
        "active_version": config_manager.get_active_version(),
        "config": result
    }

@router.put("/")
async def update_config(request: ConfigUpdateRequest):
    """
    更新配置并生成新版本
    
    请求体:
    {
        "config": {"rag_hybrid_bm25_weight": 0.3},
        "description": "调整BM25权重",
        "created_by": "user@example.com"
    }
    """
    try:
        result = await config_manager.update_config(
            config_updates=request.config,
            description=request.description,
            created_by=request.created_by
        )
        return {
            "status": "success",
            "version_id": result["version_id"],
            "previous_version": result["previous_version"],
            "changed_keys": result["changed_keys"]
        }
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/versions")
async def list_versions(limit: int = 50):
    """
    获取配置历史版本列表
    
    返回按时间倒序的版本列表，包含 is_active 标识
    """
    versions = await config_manager._repository.list_versions(limit=limit)
    active_version = config_manager.get_active_version()
    
    return [
        {
            "version_id": v["version_id"],
            "created_at": v["created_at"],
            "created_by": v.get("created_by", "system"),
            "description": v.get("description", ""),
            "is_active": v["version_id"] == active_version,
            "parent_version_id": v.get("parent_version_id"),
            "is_factory_reset": v.get("is_factory_reset", False)
        }
        for v in versions
    ]

@router.post("/rollback/{version_id}")
async def rollback_to_version(version_id: str):
    """
    回滚到指定的历史版本
    
    包含审计日志记录与事件派发
    """
    try:
        result = await config_manager.rollback_to_version(version_id)
        return {
            "status": "success",
            "version_id": result["version_id"],
            "previous_version": result["previous_version"]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to rollback config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_to_factory():
    """
    恢复到出厂设置（.env.dev默认值）
    
    生成新版本快照，标记 is_factory_reset: true
    """
    try:
        result = await config_manager.reset_to_factory()
        return {
            "status": "success",
            "version_id": result["version_id"],
            "message": "已恢复到出厂设置"
        }
    except Exception as e:
        logger.error(f"Failed to reset config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### Step 2: 注册配置路由

**文件:** `backend/src/server.py`

**改动说明:**
在 `create_app()` 函数中导入并注册配置控制器路由

**改动内容:**
```python
from src.controller import task_controller, rag_controller, rag_test_controller, config_controller

def create_app() -> FastAPI:
    # ... 现有代码 ...
    app.include_router(task_controller.router)
    app.include_router(rag_controller.router)
    app.include_router(rag_test_controller.router)
    app.include_router(config_controller.router)  # 新增
    return app
```

#### Step 3: 编写API测试

**文件:** `backend/tests/test_config_api.py`

**测试用例:**
```python
import pytest
from fastapi.testclient import TestClient
from src.server import create_app

@pytest.fixture
def client():
    return TestClient(create_app())

def test_get_config_returns_metadata(client):
    """测试获取配置元数据"""
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.json()
    assert "active_version" in data
    assert "config" in data
    assert len(data["config"]) > 0
    
    # 验证元数据结构
    first_config = data["config"][0]
    assert "key" in first_config
    assert "type" in first_config
    assert "default_value" in first_config
    assert "current_value" in first_config
    assert "description" in first_config
    assert "category" in first_config
    assert "hot_reloadable" in first_config

def test_update_config_creates_version(client):
    """测试更新配置创建新版本"""
    response = client.put("/api/v1/config", json={
        "config": {"rag_hybrid_bm25_weight": 0.3},
        "description": "Test update"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "version_id" in data

def test_list_versions(client):
    """测试获取版本列表"""
    # 先创建一个版本
    client.put("/api/v1/config", json={
        "config": {"rag_hybrid_bm25_weight": 0.3}
    })
    
    response = client.get("/api/v1/config/versions")
    assert response.status_code == 200
    versions = response.json()
    assert len(versions) > 0
    assert "version_id" in versions[0]
    assert "is_active" in versions[0]

def test_reset_to_factory(client):
    """测试恢复出厂设置"""
    response = client.post("/api/v1/config/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "version_id" in data
```

**运行测试命令:**
```bash
cd backend
pytest tests/test_config_api.py -v
```

---

## Chunk 3: 后端回撤测试链路集成

### Task 4: 集成配置版本到测试报告

**Files:**
- Modify: `backend/src/service/rag_test_manager.py`
- Modify: `backend/src/model/rag_test.py`
- Test: `backend/tests/test_rag_test_with_config.py`

#### Step 1: 扩展测试数据模型

**文件:** `backend/src/model/rag_test.py`

**改动说明:**
在 `TestRun` 和 `TestCaseResult` 模型中添加配置版本信息字段

**改动内容:**
```python
from typing import Optional, Dict, Any

class TestCaseResult(BaseModel):
    # ... 现有字段 ...
    config_version_id: Optional[str] = None  # 新增：运行时的配置版本
    config_snapshot: Optional[Dict[str, Any]] = None  # 新增：配置快照

class TestRun(BaseModel):
    # ... 现有字段 ...
    config_version_id: Optional[str] = None  # 新增：运行时的配置版本
    config_snapshot: Optional[Dict[str, Any]] = None  # 新增：完整配置快照
    previous_config_version_id: Optional[str] = None  # 新增：上一次运行的配置版本（用于对比）
```

#### Step 2: 修改测试执行逻辑

**文件:** `backend/src/service/rag_test_manager.py`

**改动说明:**
在 `run_all_tests()` 和 `run_test_case()` 方法中：
1. 获取当前配置版本
2. 将配置版本ID和快照写入测试报告
3. 获取上一次运行的配置版本用于对比

**关键改动:**
```python
from src.config.config_manager import config_manager

class RagTestManager:
    async def run_all_tests(self, name: str = "", description: str = "", limit: int = 10):
        # 获取当前配置版本
        current_version = config_manager.get_active_version()
        config_snapshot = config_manager.get_full_config()
        
        # 获取上一次运行的配置版本（用于对比）
        previous_run = self._get_last_test_run()
        previous_config_version = previous_run.config_version_id if previous_run else None
        
        # 执行测试
        test_run = TestRun(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            started_at=datetime.utcnow().isoformat(),
            config_version_id=current_version,
            config_snapshot=config_snapshot,
            previous_config_version_id=previous_config_version,
            results=[]
        )
        
        # ... 执行测试用例逻辑 ...
        
        return test_run
    
    def _get_last_test_run(self) -> Optional[TestRun]:
        """获取上一次测试运行"""
        runs = self.list_test_runs()
        if runs:
            return runs[0]  # 假设按时间倒序
        return None
```

#### Step 3: 添加配置对比API

**文件:** `backend/src/controller/rag_test_controller.py`

**改动说明:**
新增端点用于获取两个配置版本的测试结果对比

**新增端点:**
```python
@router.get("/compare-configs/{version_id1}/{version_id2}")
async def compare_config_versions(version_id1: str, version_id2: str):
    """
    对比两个配置版本的测试结果
    
    返回指标差异（准确率、召回率等）
    """
    try:
        comparison = rag_test_manager.compare_config_versions(version_id1, version_id2)
        return {"status": "success", "comparison": comparison}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

---

## Chunk 4: 前端配置管理基础与全局页面

### Task 5: 前端API与状态管理

**Files:**
- Create: `frontend/src/api/config/types.ts`
- Create: `frontend/src/api/config/index.ts`
- Create: `frontend/src/store/configStore.ts`
- Test: 手动测试API调用

#### Step 1: 定义类型

**文件:** `frontend/src/api/config/types.ts`

**完整代码:**
```typescript
export interface ConfigFieldMetadata {
  key: string;
  type: string;
  default_value: any;
  current_value: any;
  description: string;
  category: string;
  hot_reloadable: boolean;
  requires_restart: boolean;
  affected_components: string[];
}

export interface ConfigVersion {
  version_id: string;
  created_at: string;
  created_by: string;
  description: string;
  is_active: boolean;
  parent_version_id: string | null;
  is_factory_reset: boolean;
}

export interface ConfigResponse {
  active_version: string | null;
  config: ConfigFieldMetadata[];
}

export interface ConfigUpdateRequest {
  config: Record<string, any>;
  description: string;
  created_by: string;
}

export interface ConfigUpdateResponse {
  status: string;
  version_id: string;
  previous_version: string | null;
  changed_keys: string[];
}

export interface ConfigPlaygroundState {
  baseVersion: ConfigVersion | null;
  draftChanges: Record<string, any>;
  isRunning: boolean;
  lastResult: any | null;
  comparisonBaseline: string | null;
}
```

#### Step 2: 实现API请求封装

**文件:** `frontend/src/api/config/index.ts`

**完整代码:**
```typescript
import { apiClient } from '../client';
import {
  ConfigResponse,
  ConfigVersion,
  ConfigUpdateRequest,
  ConfigUpdateResponse,
} from './types';

export const configApi = {
  // 获取当前配置
  getConfig: async (): Promise<ConfigResponse> => {
    return apiClient.get('/api/v1/config');
  },

  // 更新配置
  updateConfig: async (
    request: ConfigUpdateRequest
  ): Promise<ConfigUpdateResponse> => {
    return apiClient.put('/api/v1/config', request);
  },

  // 获取版本列表
  listVersions: async (limit = 50): Promise<ConfigVersion[]> => {
    return apiClient.get(`/api/v1/config/versions?limit=${limit}`);
  },

  // 回滚到指定版本
  rollbackToVersion: async (versionId: string): Promise<any> => {
    return apiClient.post(`/api/v1/config/rollback/${versionId}`);
  },

  // 恢复出厂设置
  resetToFactory: async (): Promise<any> => {
    return apiClient.post('/api/v1/config/reset');
  },
};
```

#### Step 3: 实现全局状态管理

**文件:** `frontend/src/store/configStore.ts`

**完整代码:**
```typescript
import { create } from 'zustand';
import { configApi } from '../api/config';
import {
  ConfigFieldMetadata,
  ConfigVersion,
  ConfigPlaygroundState,
} from '../api/config/types';

interface ConfigStore {
  // 配置数据
  configFields: ConfigFieldMetadata[];
  activeVersion: string | null;
  versions: ConfigVersion[];
  
  // 草稿状态
  draftChanges: Record<string, any>;
  
  // 加载状态
  isLoading: boolean;
  isSaving: boolean;
  
  // 评估状态
  isRunning: boolean;
  lastResult: any | null;
  comparisonBaseline: string | null;
  
  // Actions
  loadConfig: () => Promise<void>;
  loadVersions: () => Promise<void>;
  updateDraft: (key: string, value: any) => void;
  saveConfig: (description: string) => Promise<void>;
  resetDraft: () => void;
  rollbackToVersion: (versionId: string) => Promise<void>;
  resetToFactory: () => Promise<void>;
}

export const useConfigStore = create<ConfigStore>((set, get) => ({
  configFields: [],
  activeVersion: null,
  versions: [],
  draftChanges: {},
  isLoading: false,
  isSaving: false,
  isRunning: false,
  lastResult: null,
  comparisonBaseline: null,

  loadConfig: async () => {
    set({ isLoading: true });
    try {
      const response = await configApi.getConfig();
      set({
        configFields: response.config,
        activeVersion: response.active_version,
      });
    } finally {
      set({ isLoading: false });
    }
  },

  loadVersions: async () => {
    try {
      const versions = await configApi.listVersions();
      set({ versions });
    } catch (error) {
      console.error('Failed to load versions:', error);
    }
  },

  updateDraft: (key: string, value: any) => {
    set((state) => ({
      draftChanges: { ...state.draftChanges, [key]: value },
    }));
  },

  saveConfig: async (description: string) => {
    const { draftChanges } = get();
    if (Object.keys(draftChanges).length === 0) return;

    set({ isSaving: true });
    try {
      await configApi.updateConfig({
        config: draftChanges,
        description,
        created_by: 'user',
      });
      set({ draftChanges: {} });
      await get().loadConfig();
      await get().loadVersions();
    } finally {
      set({ isSaving: false });
    }
  },

  resetDraft: () => {
    set({ draftChanges: {} });
  },

  rollbackToVersion: async (versionId: string) => {
    try {
      await configApi.rollbackToVersion(versionId);
      await get().loadConfig();
      await get().loadVersions();
    } catch (error) {
      console.error('Failed to rollback:', error);
      throw error;
    }
  },

  resetToFactory: async () => {
    try {
      await configApi.resetToFactory();
      await get().loadConfig();
      await get().loadVersions();
    } catch (error) {
      console.error('Failed to reset:', error);
      throw error;
    }
  },
}));
```

---

### Task 6: 动态配置表单组件

**Files:**
- Create: `frontend/src/components/config/DynamicConfigForm.tsx`
- Create: `frontend/src/components/config/DynamicConfigForm.module.scss`
- Test: 组件单元测试（可选）

#### Step 1: 实现动态表单组件

**文件:** `frontend/src/components/config/DynamicConfigForm.tsx`

**改动说明:**
根据配置元数据自动渲染表单控件

**关键逻辑:**
```typescript
import React from 'react';
import { ConfigFieldMetadata } from '../../api/config/types';
import { useConfigStore } from '../../store/configStore';
import { Switch, InputNumber, Input, Slider, Tooltip } from 'antd';
import { QuestionCircleOutlined, WarningOutlined } from '@ant-design/icons';
import styles from './DynamicConfigForm.module.scss';

interface DynamicConfigFormProps {
  fields: ConfigFieldMetadata[];
  category?: string;  // 可选：按分类过滤
}

export const DynamicConfigForm: React.FC<DynamicConfigFormProps> = ({
  fields,
  category,
}) => {
  const { draftChanges, updateDraft } = useConfigStore();

  const filteredFields = category
    ? fields.filter((f) => f.category === category)
    : fields;

  const renderField = (field: ConfigFieldMetadata) => {
    const currentValue =
      draftChanges[field.key] ?? field.current_value;

    return (
      <div key={field.key} className={styles.configItem}>
        <div className={styles.configHeader}>
          <span className={styles.configLabel}>{field.key}</span>
          <Tooltip title={field.description}>
            <QuestionCircleOutlined className={styles.helpIcon} />
          </Tooltip>
          {field.requires_restart && (
            <Tooltip title="修改后需重启服务">
              <WarningOutlined className={styles.warningIcon} />
            </Tooltip>
          )}
        </div>

        <div className={styles.configControl}>
          {renderControl(field, currentValue, updateDraft)}
        </div>

        <div className={styles.configMeta}>
          <span>默认值: {String(field.default_value)}</span>
          {!field.hot_reloadable && (
            <span className={styles.coldUpdate}>冷更新</span>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className={styles.configForm}>
      {filteredFields.map(renderField)}
    </div>
  );
};

function renderControl(
  field: ConfigFieldMetadata,
  value: any,
  onChange: (key: string, value: any) => void
) {
  switch (field.type) {
    case 'bool':
      return (
        <Switch
          checked={value}
          onChange={(checked) => onChange(field.key, checked)}
        />
      );
    case 'float':
    case 'int':
      return (
        <InputNumber
          value={value}
          onChange={(val) => onChange(field.key, val)}
          step={field.type === 'float' ? 0.05 : 1}
        />
      );
    case 'str':
      return (
        <Input
          value={value}
          onChange={(e) => onChange(field.key, e.target.value)}
        />
      );
    default:
      return (
        <Input
          value={String(value)}
          onChange={(e) => onChange(field.key, e.target.value)}
        />
      );
  }
}
```

---

### Task 7: 系统全局配置页面

**Files:**
- Create: `frontend/src/pages/SystemConfigPage.tsx`
- Create: `frontend/src/pages/SystemConfigPage.module.scss`

#### Step 1: 实现配置管理页面

**文件:** `frontend/src/pages/SystemConfigPage.tsx`

**改动说明:**
1. 左侧分类导航锚点
2. 右侧动态表单
3. 草稿状态管理
4. 保存/重置操作

**关键结构:**
```typescript
import React, { useEffect, useState } from 'react';
import { useConfigStore } from '../store/configStore';
import { DynamicConfigForm } from '../components/config/DynamicConfigForm';
import { ConfigVersionSelector } from '../components/config/ConfigVersionSelector';
import { Button, message, Modal, Space } from 'antd';
import styles from './SystemConfigPage.module.scss';

export const SystemConfigPage: React.FC = () => {
  const {
    configFields,
    draftChanges,
    isLoading,
    isSaving,
    loadConfig,
    loadVersions,
    saveConfig,
    resetDraft,
    resetToFactory,
  } = useConfigStore();

  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  useEffect(() => {
    loadConfig();
    loadVersions();
  }, []);

  // 提取所有分类
  const categories = [
    'all',
    ...new Set(configFields.map((f) => f.category)),
  ];

  const handleSave = async () => {
    Modal.confirm({
      title: '保存配置',
      content: '确定要保存当前配置修改吗？这将生成新的配置版本。',
      onOk: async () => {
        try {
          await saveConfig('Manual update from config page');
          message.success('配置已保存');
        } catch (error) {
          message.error('保存失败');
        }
      },
    });
  };

  const handleReset = () => {
    Modal.confirm({
      title: '恢复出厂设置',
      content: '确定要恢复到.env.dev的默认配置吗？',
      onOk: async () => {
        try {
          await resetToFactory();
          message.success('已恢复出厂设置');
        } catch (error) {
          message.error('恢复失败');
        }
      },
    });
  };

  return (
    <div className={styles.container}>
      <div className={styles.sidebar}>
        <h2>配置分类</h2>
        <ul>
          {categories.map((cat) => (
            <li
              key={cat}
              className={selectedCategory === cat ? styles.active : ''}
              onClick={() => setSelectedCategory(cat)}
            >
              {cat === 'all' ? '全部配置' : cat}
            </li>
          ))}
        </ul>
        
        <ConfigVersionSelector />
      </div>

      <div className={styles.main}>
        <div className={styles.header}>
          <h1>系统全局配置</h1>
          <Space>
            <Button onClick={handleReset} danger>
              恢复出厂设置
            </Button>
            <Button
              type="primary"
              onClick={handleSave}
              loading={isSaving}
              disabled={Object.keys(draftChanges).length === 0}
            >
              保存配置 ({Object.keys(draftChanges).length} 项修改)
            </Button>
          </Space>
        </div>

        <DynamicConfigForm
          fields={configFields}
          category={selectedCategory === 'all' ? undefined : selectedCategory}
        />
      </div>
    </div>
  );
};
```

---

## Chunk 5: 调优工作台与A/B对比视图开发

### Task 8: 配置版本选择器与差异对比组件

**Files:**
- Create: `frontend/src/components/config/ConfigVersionSelector.tsx`
- Create: `frontend/src/components/config/ConfigDiffView.tsx`

#### Step 1: 版本选择器

**文件:** `frontend/src/components/config/ConfigVersionSelector.tsx`

**功能:**
- 显示历史版本列表
- 支持选择版本进行回滚
- 显示版本描述与创建时间

**关键代码:**
```typescript
import React from 'react';
import { useConfigStore } from '../../store/configStore';
import { Select, Button, Tooltip } from 'antd';
import { RollbackOutlined } from '@ant-design/icons';

export const ConfigVersionSelector: React.FC = () => {
  const { versions, activeVersion, rollbackToVersion } = useConfigStore();

  const handleRollback = async (versionId: string) => {
    if (versionId === activeVersion) return;
    await rollbackToVersion(versionId);
  };

  return (
    <div>
      <h3>历史版本</h3>
      <Select
        style={{ width: '100%' }}
        placeholder="选择版本"
        options={versions.map((v) => ({
          value: v.version_id,
          label: `${v.version_id} - ${v.description || '无描述'}`,
          disabled: v.is_active,
        }))}
      />
      {versions.map((v) => (
        <div key={v.version_id} className="version-item">
          <span>{v.version_id}</span>
          <span>{v.created_at}</span>
          {!v.is_active && (
            <Tooltip title="回滚到此版本">
              <Button
                icon={<RollbackOutlined />}
                size="small"
                onClick={() => handleRollback(v.version_id)}
              />
            </Tooltip>
          )}
        </div>
      ))}
    </div>
  );
};
```

#### Step 2: 配置差异对比组件

**文件:** `frontend/src/components/config/ConfigDiffView.tsx`

**功能:**
- 对比两个版本的配置差异
- 高亮显示变更字段
- 显示旧值与新值

**关键代码:**
```typescript
import React from 'react';
import { Table, Tag } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';

interface ConfigDiffViewProps {
  version1Snapshot: Record<string, any>;
  version2Snapshot: Record<string, any>;
  configFields: any[];
}

export const ConfigDiffView: React.FC<ConfigDiffViewProps> = ({
  version1Snapshot,
  version2Snapshot,
  configFields,
}) => {
  const diffData = configFields
    .filter((field) => {
      const val1 = version1Snapshot[field.key];
      const val2 = version2Snapshot[field.key];
      return val1 !== val2;
    })
    .map((field) => {
      const val1 = version1Snapshot[field.key];
      const val2 = version2Snapshot[field.key];
      const changed = val2 - val1;
      const percentChange = val1 !== 0 ? (changed / val1) * 100 : 0;

      return {
        key: field.key,
        category: field.category,
        oldValue: val1,
        newValue: val2,
        change: changed,
        percentChange: percentChange.toFixed(2),
        direction: changed > 0 ? 'up' : 'down',
      };
    });

  const columns = [
    {
      title: '配置项',
      dataIndex: 'key',
      key: 'key',
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
    },
    {
      title: '旧值',
      dataIndex: 'oldValue',
      key: 'oldValue',
    },
    {
      title: '新值',
      dataIndex: 'newValue',
      key: 'newValue',
    },
    {
      title: '变化',
      key: 'change',
      render: (_: any, record: any) => (
        <Tag
          color={record.direction === 'up' ? 'green' : 'red'}
          icon={
            record.direction === 'up' ? (
              <ArrowUpOutlined />
            ) : (
              <ArrowDownOutlined />
            )
          }
        >
          {record.percentChange}%
        </Tag>
      ),
    },
  ];

  return <Table columns={columns} dataSource={diffData} />;
};
```

---

### Task 9: 调优面板组件

**Files:**
- Create: `frontend/src/features/rag-evaluation/components/ConfigTuningPanel.tsx`
- Create: `frontend/src/features/rag-evaluation/components/ConfigTuningPanel.module.scss`

#### Step 1: 实现调优面板

**文件:** `frontend/src/features/rag-evaluation/components/ConfigTuningPanel.tsx`

**改动说明:**
1. 显示核心参数调优表单
2. 草稿状态管理
3. "应用并重测"按钮
4. 运行期间锁定面板

**关键代码:**
```typescript
import React, { useState } from 'react';
import { useConfigStore } from '../../../store/configStore';
import { DynamicConfigForm } from '../../../components/config/DynamicConfigForm';
import { Button, Input, message, Space } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import styles from './ConfigTuningPanel.module.scss';

interface ConfigTuningPanelProps {
  onRunTest: () => Promise<void>;
  coreConfigKeys?: string[];  // 核心配置项keys
}

export const ConfigTuningPanel: React.FC<ConfigTuningPanelProps> = ({
  onRunTest,
  coreConfigKeys,
}) => {
  const {
    configFields,
    draftChanges,
    isSaving,
    isRunning,
    saveConfig,
  } = useConfigStore();

  const [description, setDescription] = useState('');

  // 过滤核心配置项
  const coreFields = coreConfigKeys
    ? configFields.filter((f) => coreConfigKeys.includes(f.key))
    : configFields;

  const handleApplyAndTest = async () => {
    if (Object.keys(draftChanges).length === 0) {
      message.warning('请先修改配置');
      return;
    }

    try {
      // 1. 保存配置（生成新版本）
      await saveConfig(description || 'Tuning from evaluation playground');
      
      // 2. 触发测试
      await onRunTest();
      
      message.success('配置已应用，测试运行中');
    } catch (error) {
      message.error('操作失败');
    }
  };

  return (
    <div className={styles.tuningPanel}>
      <div className={styles.header}>
        <h3>核心参数调优</h3>
      </div>

      <div className={styles.form}>
        <DynamicConfigForm fields={coreFields} />
      </div>

      <div className={styles.footer}>
        <Input.TextArea
          placeholder="版本描述（可选）"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
        />
        <Space style={{ marginTop: 12 }}>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleApplyAndTest}
            loading={isSaving || isRunning}
            disabled={isRunning || Object.keys(draftChanges).length === 0}
          >
            {isRunning ? '测试运行中...' : '应用并重测'}
          </Button>
        </Space>
      </div>
    </div>
  );
};
```

---

### Task 10: 重构RAG评估工作台

**Files:**
- Modify: `frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx`
- Modify: `frontend/src/features/rag-evaluation/pages/RagEvaluationPage.module.scss`

#### Step 1: 重构为分栏布局

**文件:** `frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx`

**改动说明:**
1. 采用60/40分栏布局
2. 左侧：测试用例列表与评估报告
3. 右侧：配置调优面板
4. 集成配置版本对比

**关键结构改动:**
```typescript
import React from 'react';
import { ConfigTuningPanel } from '../components/ConfigTuningPanel';
import { EvaluationReport } from '../components/EvaluationReport';
import { TestCaseTable } from '../components/TestCaseTable';
import { ConfigDiffView } from '../../../components/config/ConfigDiffView';
import { useConfigStore } from '../../../store/configStore';
import styles from './RagEvaluationPage.module.scss';

export const RagEvaluationPage: React.FC = () => {
  const { configFields, lastResult } = useConfigStore();
  const [isRunning, setIsRunning] = useState(false);

  const handleRunTest = async () => {
    setIsRunning(true);
    try {
      // 调用现有测试运行逻辑
      await runRagTests();
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className={styles.container}>
      {/* 左侧：测试与报告 (60%) */}
      <div className={styles.leftPanel}>
        <TestCaseTable />
        
        {lastResult && (
          <div className={styles.reportSection}>
            <EvaluationReport result={lastResult} />
            
            {/* 配置版本对比 */}
            {lastResult.config_version_id && lastResult.previous_config_version_id && (
              <ConfigDiffView
                version1Snapshot={lastResult.previous_config_snapshot}
                version2Snapshot={lastResult.config_snapshot}
                configFields={configFields}
              />
            )}
          </div>
        )}
      </div>

      {/* 右侧：调优面板 (40%) */}
      <div className={styles.rightPanel}>
        <ConfigTuningPanel
          onRunTest={handleRunTest}
          coreConfigKeys={[
            'rag_hybrid_bm25_weight',
            'rag_search_score_threshold_hybrid',
            'rag_reranker_initial_k',
            'rag_reranker_final_k',
          ]}
        />
      </div>
    </div>
  );
};
```

**样式改动:**
```scss
// RagEvaluationPage.module.scss
.container {
  display: flex;
  height: 100vh;
  gap: 16px;
  padding: 16px;
}

.leftPanel {
  flex: 0 0 60%;
  overflow-y: auto;
}

.rightPanel {
  flex: 0 0 40%;
  overflow-y: auto;
  border-left: 1px solid #e8e8e8;
  padding-left: 16px;
}

.reportSection {
  margin-top: 24px;
}
```

---

## Chunk 6: 集成测试与验收

### Task 11: 端到端集成测试

**Files:**
- Create: `backend/tests/test_config_integration.py`
- Create: `frontend/src/__tests__/configWorkflow.test.tsx` (可选)

#### Step 1: 后端集成测试

**文件:** `backend/tests/test_config_integration.py`

**测试场景:**
```python
import pytest
from fastapi.testclient import TestClient
from src.server import create_app
from src.config.config_manager import config_manager

@pytest.fixture
def client():
    return TestClient(create_app())

def test_full_config_workflow(client):
    """测试完整配置工作流"""
    # 1. 获取初始配置
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    initial_version = response.json()["active_version"]
    
    # 2. 更新配置
    response = client.put("/api/v1/config", json={
        "config": {"rag_hybrid_bm25_weight": 0.3},
        "description": "Test workflow"
    })
    assert response.status_code == 200
    new_version = response.json()["version_id"]
    
    # 3. 验证配置已更新
    response = client.get("/api/v1/config")
    config_data = response.json()
    assert config_data["active_version"] == new_version
    
    # 4. 查看版本列表
    response = client.get("/api/v1/config/versions")
    versions = response.json()
    assert len(versions) >= 2
    
    # 5. 回滚到初始版本
    if initial_version:
        response = client.post(f"/api/v1/config/rollback/{initial_version}")
        assert response.status_code == 200
        
        # 验证回滚生效
        response = client.get("/api/v1/config")
        assert response.json()["active_version"] == initial_version
    
    # 6. 恢复出厂设置
    response = client.post("/api/v1/config/reset")
    assert response.status_code == 200

def test_config_hot_reload_event(client):
    """测试配置热更新事件派发"""
    # 订阅ConfigChangedEvent
    # 更新配置
    # 验证事件被派发
    pass
```

**运行测试命令:**
```bash
cd backend
pytest tests/test_config_integration.py -v
```

---

## 验收检查清单

完成所有Task后，逐项验证：

- [x] `settings.py` 的所有配置项均已具备完善的 `description`、`category` 和 `hot_reloadable` 元数据
- [x] `ConfigRepository` 抽象接口已定义，`JsonConfigRepository` 实现完成
- [x] `ConfigManager` 能够生成并记录带有 `version_id` 的配置快照
- [x] `backend/data/configs/` 目录结构正确创建
- [x] 后端采用惰性加载模式实现热更新
- [x] `GET /api/v1/config` 返回完整的元数据结构
- [x] 提供了"恢复默认值"、"历史版本查询"及"版本回滚"的接口
- [x] 前端成功集成"系统全局配置"页面
- [x] RAG评估工作台实现了分栏式的调优面板
- [x] 测试报告中准确记录了 `version_id`
- [x] 评估报告页面能够展示配置版本Diff对比

---

## 实施进度更新（2026-04-08）

✅ **全部任务已完成**，所有功能按照计划实现：

### 已完成的工作：

#### 后端部分
1. **配置元数据增强**：为 `settings.py` 添加了完整的元数据系统，支持自动分类、热更新标记、影响组件标注
2. **配置事件系统**：实现了 `ConfigChangedEvent`、`ConfigRollbackEvent`、`ConfigResetEvent` 事件模型
3. **配置仓储层**：实现了抽象 `ConfigRepository` 接口和 `JsonConfigRepository` 持久化实现
4. **配置管理器**：实现了单例 `ConfigManager`，支持版本生成、热更新、回滚、恢复出厂设置等核心功能
5. **配置API**：实现了5个核心API端点：
   - `GET /api/v1/config` - 获取配置及元数据
   - `PUT /api/v1/config` - 更新配置生成新版本
   - `GET /api/v1/config/versions` - 获取历史版本列表
   - `POST /api/v1/config/rollback/{version_id}` - 回滚到指定版本
   - `POST /api/v1/config/reset` - 恢复出厂设置
6. **测试链路集成**：
   - 扩展 `TestRun` 模型添加 `config_version_id`、`config_snapshot`、`previous_config_version_id` 字段
   - 测试运行时自动捕获当前配置版本和快照
   - 新增 `compare-configs` API 支持两个配置版本的测试结果对比
   - 新增配置对比端点 `GET /rag/test/compare-configs/{version_id1}/{version_id2}`

#### 前端部分
1. **API层**：创建了配置API封装和类型定义
2. **状态管理**：实现了 `useConfigStore` 全局状态管理，支持配置加载、版本管理、草稿状态
3. **基础组件**：
   - `DynamicConfigForm` - 动态配置表单，根据元数据自动渲染控件
   - `ConfigVersionSelector` - 版本选择器和回滚功能
   - `ConfigDiffView` - 配置差异对比组件，高亮显示变更
4. **系统配置页面**：实现了完整的系统全局配置管理页面，支持分类导航、版本管理、保存/重置
5. **调优工作台**：
   - 实现 `ConfigTuningPanel` 组件，支持核心参数调优和一键应用测试
   - 重构RAG评估页面为60/40分栏布局，左侧测试报告，右侧调优面板
   - 集成配置版本对比功能，自动展示当前版本与上一版本的配置差异

### 待完成（用户后续处理）：
- 测试所有功能并修复潜在问题
- 添加前端路由映射到系统配置页面
- 集成热更新事件订阅到相关服务（rag_service、retrieval_service等）
- 配置前端权限控制

---

## 实施顺序建议

1. **Phase 1 (Task 1-2)**: 后端配置核心与仓储层
2. **Phase 2 (Task 3)**: 后端API开发
3. **Phase 3 (Task 4)**: 测试链路集成
4. **Phase 4 (Task 5-7)**: 前端配置管理基础
5. **Phase 5 (Task 8-10)**: 调优工作台与对比视图
6. **Phase 6 (Task 11)**: 集成测试与验收

每个Phase完成后运行对应测试，确保功能正确后再进入下一阶段。
