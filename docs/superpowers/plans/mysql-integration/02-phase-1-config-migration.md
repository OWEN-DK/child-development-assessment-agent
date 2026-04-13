# Phase 1: 配置系统MySQL迁移 + Redis缓存集成

> 本文档是 MySQL + Redis 集成重构实施方案的一部分
> 
> **返回索引：** [README.md](./README.md) | [项目概览](./00-overview.md)

---

## Phase 1: 配置系统MySQL迁移 + Redis缓存集成（周期：2天）
### Task 1.1: 实现MySQL配置仓库
**Files:**
- Create: `backend/src/config/core/repository.py`
- [ ] **Step 1: 编写MySQLConfigRepository代码**
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from src.models.config import ConfigVersion, ConfigAuditLog
from src.config.core.entities import ConfigVersion as ConfigVersionEntity
from datetime import datetime
class MySQLConfigRepository:
    """基于MySQL的配置仓库实现"""
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save_version(self, version: ConfigVersionEntity) -> None:
        """保存配置版本"""
        db_version = ConfigVersion(
            id=version.id,
            created_at=version.created_at,
            created_by=version.created_by,
            description=version.description,
            config_snapshot=version.config_snapshot.model_dump(),
            parent_version_id=version.parent_version_id,
            is_factory_reset=version.is_factory_reset
        )
        self.session.add(db_version)
        await self.session.flush()
    
    async def get_latest_version(self) -> ConfigVersionEntity | None:
        """获取最新配置版本"""
        result = await self.session.execute(
            select(ConfigVersion)
            .order_by(desc(ConfigVersion.created_at))
            .limit(1)
        )
        db_version = result.scalar_one_or_none()
        return self._to_entity(db_version) if db_version else None
    
    async def get_version_by_id(self, version_id: str) -> ConfigVersionEntity | None:
        """根据ID获取配置版本"""
        db_version = await self.session.get(ConfigVersion, version_id)
        return self._to_entity(db_version) if db_version else None
    
    async def list_versions(self, limit: int = 50) -> list[ConfigVersionEntity]:
        """列出配置版本"""
        result = await self.session.execute(
            select(ConfigVersion)
            .order_by(desc(ConfigVersion.created_at))
            .limit(limit)
        )
        return [self._to_entity(v) for v in result.scalars().all()]
    
    async def log_action(
        self,
        action: str,
        from_version: str | None,
        to_version: str | None,
        user: str | None = None,
    ) -> None:
        """记录配置操作日志"""
        log = ConfigAuditLog(
            action=action,
            from_version=from_version,
            to_version=to_version,
            user=user
        )
        self.session.add(log)
        await self.session.flush()
    
    def _to_entity(self, db_version: ConfigVersion) -> ConfigVersionEntity:
        """转换数据库模型为实体"""
        return ConfigVersionEntity(
            id=db_version.id,
            created_at=db_version.created_at,
            created_by=db_version.created_by,
            description=db_version.description,
            config_snapshot=db_version.config_snapshot,
            parent_version_id=db_version.parent_version_id,
            is_factory_reset=db_version.is_factory_reset
        )
```
- [ ] **Step 2: 测试配置仓库功能**
```bash
cd backend
uv run python -c "
import asyncio
from src.core.database import async_session_factory
from src.config.core.repository import MySQLConfigRepository
from src.config.core.entities import ConfigVersion
from datetime import datetime
async def test():
    async with async_session_factory() as session:
        repo = MySQLConfigRepository(session)
        # 测试保存版本
        version = ConfigVersion(
            id='v_test_001',
            created_at=datetime.now(),
            created_by='admin',
            description='测试版本',
            config_snapshot={'llm': {'model': 'qwen-plus'}},
            parent_version_id=None,
            is_factory_reset=False
        )
        await repo.save_version(version)
        await session.commit()
        # 测试获取最新版本
        latest = await repo.get_latest_version()
        assert latest.id == 'v_test_001'
        print('配置仓库测试通过')
asyncio.run(test())
"
```

### Task 1.2: 改造 ConfigManager 使用 MySQL 存储和 Redis 缓存
**Files:**
- Modify: `backend/src/config/core/manager.py`
- [ ] **Step 1: 更新ConfigManager代码，替换JSON文件存储为MySQL+Redis**
```python
import asyncio
from typing import Any
from datetime import datetime
import uuid
from src.config.core.repository import MySQLConfigRepository
from src.config.core.entities import ConfigVersion
from src.service.cache_service import cache_service
from src.core.event_bus import EventBus
from src.core.events import ConfigChangedEvent
from src.core.distributed_lock import DistributedLock
from src.config import settings as current_settings
from src.utils.logger import logger
class ConfigManager:
    """配置管理器，支持MySQL持久化、Redis缓存、热更新、版本控制"""
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        self._current_version: ConfigVersion | None = None
        self._cache_key_prefix = "config:version:"
        self._lock_name = "config:reload"
    
    async def load_latest_version(self) -> None:
        """加载最新配置版本"""
        # 优先从缓存获取
        cache_key = f"{self._cache_key_prefix}latest"
        cached = await cache_service.get(cache_key)
        if cached:
            self._current_version = ConfigVersion(**cached)
            logger.info(f"配置已从缓存加载，版本: {self._current_version.id}")
            return
        
        # 缓存未命中，从MySQL查询
        from src.core.database import db_session_factory
        from src.config.core.repository import MySQLConfigRepository
        
        async with db_session_factory() as session:
            repo = MySQLConfigRepository(session)
            latest = await repo.get_latest_version()
            if not latest:
                # 没有版本，创建初始版本
                latest = await self._create_initial_version(session)
            self._current_version = latest
            # 写入缓存
            await cache_service.set(cache_key, latest.model_dump(), expire=3600)
            logger.info(f"配置已从数据库加载，版本: {self._current_version.id}")
    
    async def _create_initial_version(self, session) -> ConfigVersion:
        """创建初始配置版本"""
        initial_snapshot = current_settings.model_dump()
        version = ConfigVersion(
            id=f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
            created_at=datetime.now(),
            created_by="system",
            description="初始配置版本",
            config_snapshot=initial_snapshot,
            parent_version_id=None,
            is_factory_reset=True
        )
        repo = MySQLConfigRepository(session)
        await repo.save_version(version)
        await repo.log_action(
            action="RESET",
            from_version=None,
            to_version=version.id,
            user="system"
        )
        await session.commit()
        return version
    
    async def save_new_version(
        self,
        config_snapshot: dict[str, Any],
        description: str,
        created_by: str = "system"
    ) -> ConfigVersion:
        """保存新的配置版本"""
        from src.core.database import db_session_factory
        from src.config.core.repository import MySQLConfigRepository
        
        async with db_session_factory() as session:
            async with DistributedLock.execute_with_lock(self._lock_name):
                # 创建新版本
                new_version = ConfigVersion(
                    id=f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
                    created_at=datetime.now(),
                    created_by=created_by,
                    description=description,
                    config_snapshot=config_snapshot,
                    parent_version_id=self._current_version.id if self._current_version else None,
                    is_factory_reset=False
                )
                repo = MySQLConfigRepository(session)
                await repo.save_version(new_version)
                # 记录操作日志
                await repo.log_action(
                    action="UPDATE",
                    from_version=self._current_version.id if self._current_version else None,
                    to_version=new_version.id,
                    user=created_by
                )
                await session.commit()
                # 更新当前版本
                self._current_version = new_version
                # 清除缓存
                await cache_service.delete(f"{self._cache_key_prefix}latest")
                await cache_service.invalidate_tag("config")
                # 发布配置变更事件
                EventBus.publish(ConfigChangedEvent(
                    version_id=new_version.id,
                    changed_keys=list(config_snapshot.keys())
                ))
                logger.info(f"新配置版本已保存: {new_version.id}")
                return new_version
    
    async def rollback_to_version(self, version_id: str, created_by: str = "system") -> ConfigVersion:
        """回滚到指定版本"""
        from src.core.database import db_session_factory
        from src.config.core.repository import MySQLConfigRepository
        
        async with db_session_factory() as session:
            async with DistributedLock.execute_with_lock(self._lock_name):
                repo = MySQLConfigRepository(session)
                target_version = await repo.get_version_by_id(version_id)
                if not target_version:
                    raise ValueError(f"配置版本不存在: {version_id}")
                
                # 创建回滚版本
                rollback_version = ConfigVersion(
                    id=f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
                    created_at=datetime.now(),
                    created_by=created_by,
                    description=f"回滚到版本: {version_id}",
                    config_snapshot=target_version.config_snapshot,
                    parent_version_id=self._current_version.id if self._current_version else None,
                    is_factory_reset=False
                )
                await repo.save_version(rollback_version)
                # 记录操作日志
                await repo.log_action(
                    action="ROLLBACK",
                    from_version=self._current_version.id if self._current_version else None,
                    to_version=rollback_version.id,
                    user=created_by
                )
                await session.commit()
                # 更新当前版本
                self._current_version = rollback_version
                # 清除缓存
                await cache_service.delete(f"{self._cache_key_prefix}latest")
                await cache_service.invalidate_tag("config")
                # 发布配置变更事件
                EventBus.publish(ConfigChangedEvent(
                    version_id=rollback_version.id,
                    changed_keys=list(target_version.config_snapshot.keys())
                ))
                logger.info(f"已回滚到配置版本: {version_id}, 新版本号: {rollback_version.id}")
                return rollback_version
    
    @property
    def current_config(self) -> dict[str, Any]:
        """获取当前配置"""
        if not self._current_version:
            raise RuntimeError("配置尚未加载")
        return self._current_version.config_snapshot
    
    @property
    def current_version_id(self) -> str:
        """获取当前配置版本ID"""
        if not self._current_version:
            raise RuntimeError("配置尚未加载")
        return self._current_version.id

# 全局实例
config_manager = ConfigManager()
```
- [ ] **Step 2: 更新config/__init__.py导出config_manager**
```python
# 现有导出基础上添加
from .core.manager import config_manager
__all__.append("config_manager")
```
- [ ] **Step 3: 测试配置管理器功能**
```bash
cd backend
uv run python -c "
import asyncio
from src.config import config_manager
async def test():
    await config_manager.load_latest_version()
    print(f'当前配置版本: {config_manager.current_version_id}')
    # 测试保存新版本
    new_config = config_manager.current_config.copy()
    new_config['llm']['model'] = 'qwen-max'
    new_version = await config_manager.save_new_version(
        new_config,
        '更新LLM模型为qwen-max',
        'admin'
    )
    print(f'新版本已创建: {new_version.id}')
    assert config_manager.current_config['llm']['model'] == 'qwen-max'
    # 测试回滚
    rollback_version = await config_manager.rollback_to_version(config_manager.current_version_id)
    print(f'已回滚到版本: {rollback_version.id}')
    print('配置管理器测试通过')
asyncio.run(test())
"
```

### Task 1.3: 更新配置相关 API 接口
**Files:**
- Modify: `backend/src/controller/config_controller.py`
- [ ] **Step 1: 重写配置控制器接口，使用新的ConfigManager**
```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Optional
from src.config import config_manager
from src.core.auth import get_current_user  # 假设存在认证依赖
router = APIRouter(prefix="/api/v1/config", tags=["config"])
class ConfigSaveRequest(BaseModel):
    """配置保存请求"""
    config_snapshot: dict[str, Any]
    description: str
class ConfigRollbackRequest(BaseModel):
    """配置回滚请求"""
    version_id: str
class ConfigVersionResponse(BaseModel):
    """配置版本响应"""
    id: str
    created_at: str
    created_by: Optional[str]
    description: Optional[str]
    parent_version_id: Optional[str]
    is_factory_reset: bool
@router.get("/current", response_model=dict[str, Any])
async def get_current_config():
    """获取当前配置"""
    try:
        return config_manager.current_config
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/versions", response_model=list[ConfigVersionResponse])
async def list_config_versions(limit: int = 50):
    """列出配置版本"""
    from src.core.database import db_session_factory
    from src.config.core.repository import MySQLConfigRepository
    
    async with db_session_factory() as session:
        repo = MySQLConfigRepository(session)
        versions = await repo.list_versions(limit)
        return [
            ConfigVersionResponse(
                id=v.id,
                created_at=v.created_at.isoformat(),
                created_by=v.created_by,
                description=v.description,
                parent_version_id=v.parent_version_id,
                is_factory_reset=v.is_factory_reset
            ) for v in versions
        ]
@router.get("/versions/{version_id}", response_model=dict[str, Any])
async def get_config_version(version_id: str):
    """获取指定版本配置"""
    from src.core.database import db_session_factory
    from src.config.core.repository import MySQLConfigRepository
    
    async with db_session_factory() as session:
        repo = MySQLConfigRepository(session)
        version = await repo.get_version_by_id(version_id)
        if not version:
            raise HTTPException(status_code=404, detail=f"配置版本不存在: {version_id}")
        return version.config_snapshot
@router.post("/save", response_model=ConfigVersionResponse)
async def save_new_config(
    request: ConfigSaveRequest,
    current_user = Depends(get_current_user)
):
    """保存新配置版本"""
    try:
        new_version = await config_manager.save_new_version(
            config_snapshot=request.config_snapshot,
            description=request.description,
            created_by=current_user.username if current_user else "system"
        )
        return ConfigVersionResponse(
            id=new_version.id,
            created_at=new_version.created_at.isoformat(),
            created_by=new_version.created_by,
            description=new_version.description,
            parent_version_id=new_version.parent_version_id,
            is_factory_reset=new_version.is_factory_reset
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")
@router.post("/rollback", response_model=ConfigVersionResponse)
async def rollback_config(
    request: ConfigRollbackRequest,
    current_user = Depends(get_current_user)
):
    """回滚到指定配置版本"""
    try:
        rollback_version = await config_manager.rollback_to_version(
            version_id=request.version_id,
            created_by=current_user.username if current_user else "system"
        )
        return ConfigVersionResponse(
            id=rollback_version.id,
            created_at=rollback_version.created_at.isoformat(),
            created_by=rollback_version.created_by,
            description=rollback_version.description,
            parent_version_id=rollback_version.parent_version_id,
            is_factory_reset=rollback_version.is_factory_reset
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回滚配置失败: {str(e)}")
@router.get("/schema", response_model=dict[str, Any])
async def get_config_schema():
    """获取配置JSON Schema，用于前端动态渲染表单"""
    # 从配置模型生成JSON Schema
    from src.config import settings
    return settings.model_json_schema()
```
- [ ] **Step 2: 在server.py中注册配置路由**
```python
# 在现有路由注册部分添加
from src.controller.config_controller import router as config_router
app.include_router(config_router)
```
- [ ] **Step 3: 测试配置API**
```bash
# 启动后端服务
cd backend
uv run python src/server.py
# 测试获取当前配置
curl http://localhost:8000/api/v1/config/current
# 测试获取配置版本列表
curl http://localhost:8000/api/v1/config/versions
# 测试获取配置Schema
curl http://localhost:8000/api/v1/config/schema
```

### Task 1.4: 迁移前端配置页面到独立路由
**Files:**
- Create: `frontend/src/pages/SystemConfig.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/Menu.vue`
- [ ] **Step 1: 创建系统配置页面组件**
```vue
<template>
  <div class="system-config">
    <PageHeader title="系统配置" subtitle="管理全局配置参数，支持版本控制和回滚" />
    <a-card class="mb-4">
      <template #title>
        <div class="flex items-center">
          <SettingOutlined class="mr-2" />
          配置管理
        </div>
      </template>
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="current" tab="当前配置">
          <ConfigForm
            :schema="configSchema"
            :model="currentConfig"
            @submit="handleSaveConfig"
            :loading="saving"
          />
        </a-tab-pane>
        <a-tab-pane key="versions" tab="版本历史">
          <VersionList
            :versions="versionList"
            :loading="loadingVersions"
            @rollback="handleRollback"
            @view="handleViewVersion"
          />
        </a-tab-pane>
      </a-tabs>
    </a-card>
    <!-- 版本详情查看模态框 -->
    <a-modal
      v-model:open="viewVersionVisible"
      title="配置版本详情"
      width="800px"
      :footer="null"
    >
      <JsonViewer :value="viewVersionConfig" :expand-depth="2" />
    </a-modal>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { SettingOutlined } from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import ConfigForm from './components/ConfigForm.vue'
import VersionList from './components/VersionList.vue'
import { 
  getCurrentConfig, 
  getConfigVersions, 
  saveNewConfig, 
  rollbackConfig, 
  getConfigSchema 
} from '@/api/config'
import type { ConfigVersion } from '@/types/config'
const activeTab = ref('current')
const configSchema = ref<any>({})
const currentConfig = ref<any>({})
const saving = ref(false)
const loadingVersions = ref(false)
const versionList = ref<ConfigVersion[]>([])
const viewVersionVisible = ref(false)
const viewVersionConfig = ref<any>({})
onMounted(() => {
  loadCurrentConfig()
  loadConfigSchema()
  loadVersions()
})
async function loadCurrentConfig() {
  currentConfig.value = await getCurrentConfig()
}
async function loadConfigSchema() {
  configSchema.value = await getConfigSchema()
}
async function loadVersions() {
  loadingVersions.value = true
  try {
    versionList.value = await getConfigVersions()
  } finally {
    loadingVersions.value = false
  }
}
async function handleSaveConfig(data: any) {
  saving.value = true
  try {
    await saveNewConfig({
      config_snapshot: data,
      description: '用户界面修改配置'
    })
    message.success('配置保存成功')
    await loadCurrentConfig()
    await loadVersions()
  } finally {
    saving.value = false
  }
}
async function handleRollback(version: ConfigVersion) {
  Modal.confirm({
    title: '确认回滚',
    content: `确定要回滚到配置版本 ${version.id} 吗？此操作会创建新的配置版本。`,
    onOk: async () => {
      await rollbackConfig({ version_id: version.id })
      message.success('配置回滚成功')
      await loadCurrentConfig()
      await loadVersions()
    }
  })
}
async function handleViewVersion(version: ConfigVersion) {
  // 这里调用获取版本详情的API
  viewVersionConfig.value = {} // 替换为实际API返回
  viewVersionVisible.value = true
}
</script>
<style scoped>
.system-config {
  padding: 20px;
}
</style>
```
- [ ] **Step 2: 添加配置页面路由**
```typescript
// 在router/index.ts中添加
{
  path: '/system/config',
  name: 'SystemConfig',
  component: () => import('@/pages/SystemConfig.vue'),
  meta: {
    title: '系统配置',
    requiresAuth: true
  }
}
```
- [ ] **Step 3: 在侧边栏菜单添加配置入口**
```vue
<!-- 在Menu.vue的菜单列表中添加 -->
<a-menu-item key="/system/config">
  <SettingOutlined />
  <span>系统配置</span>
</a-menu-item>
```
- [ ] **Step 4: 移除原有评估页面中的配置调优面板**
删除 `Assessment.vue` 中的 `ConfigTuningPanel` 相关代码。

### Task 1.5: AES 加密敏感配置
**Files:**
- Create: `backend/src/core/crypto.py`

- [ ] **Step 1: 创建加密工具类**
```python
# backend/src/core/crypto.py
import os
import base64
from cryptography.fernet import Fernet
from src.utils.logger import logger

class CryptoService:
    """AES 对称加密服务（用于敏感配置加密存储）"""
    
    def __init__(self, key: str = None):
        # 使用环境变量中的密钥，或生成新密钥
        if key:
            self._key = self._derive_key(key)
        else:
            self._key = Fernet.generate_key()
        self._fernet = Fernet(self._key)
    
    def _derive_key(self, password: str) -> bytes:
        """从密码派生 32 字节密钥"""
        import hashlib
        return base64.urlsafe_b64encode(
            hashlib.sha256(password.encode()).digest()
        )
    
    def encrypt(self, plaintext: str) -> str:
        """加密"""
        return self._fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """解密"""
        return self._fernet.decrypt(ciphertext.encode()).decode()
    
    @staticmethod
    def mask_api_key(key: str, visible_chars: int = 4) -> str:
        """API Key 脱敏显示（如 sk-****1234）"""
        if not key or len(key) <= visible_chars * 2:
            return "****"
        return f"{key[:visible_chars]}****{key[-visible_chars:]}"

# 全局单例
crypto_service = CryptoService(key=os.getenv("ENCRYPTION_KEY"))
```

- [ ] **Step 2: 在配置保存/读取时使用加密**
```python
# 在 ConfigManager 中
from src.core.crypto import crypto_service

async def save_sensitive_config(self, key: str, value: str):
    """保存敏感配置（自动加密）"""
    encrypted = crypto_service.encrypt(value)
    # 存储 encrypted 到 MySQL
    ...

async def get_sensitive_config(self, key: str) -> str:
    """读取敏感配置（自动解密）"""
    # 从 MySQL 读取 encrypted
    return crypto_service.decrypt(encrypted)
```

### Phase 1 完成验证
- [ ] 所有配置API接口测试通过
- [ ] 前端配置页面功能正常：查看当前配置、保存新版本、查看历史版本、回滚
- [ ] 配置变更事件能够正常发布和接收
- [ ] 配置缓存自动失效机制正常工作
---
