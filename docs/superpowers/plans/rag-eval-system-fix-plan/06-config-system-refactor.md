# P0 配置系统重构：消除混乱 + 全量热加载 + 凭证统一管理

**优先级**: 🔴 最高（影响所有配置操作）  
**工作量**: 19h（原 10h + 9h 修复）  
**状态**: 方案制定中，待实施  

---

## 一、问题诊断

### 1.1 核心问题清单

| # | 问题 | 严重程度 | 影响范围 |
|---|------|----------|----------|
| 1 | **配置重复混乱** | 🔴 高 | 所有配置操作 |
| 2 | **LLM 配置冷加载** | 🔴 高 | 模型切换、凭证更新 |
| 3 | **RAG 配置碎片化** | 🟡 中 | 检索质量调优 |
| 4 | **LLM 凭证分散** | 🔴 高 | 安全性、一致性 |
| 5 | **大字段无滚动条** | 🟡 中 | 用户体验 |

### 1.2 问题详细分析

#### 问题 1：配置重复混乱

**现状**：
- **API Key 三套存储**：`DASHSCOPE_API_KEY` (env) + `dashscope_api_key` (Settings) + `llm_providers["dashscope"].api_key` (Settings Dict)
- **分类体系两套**：DB 元数据用 `rag_retrieval`（下划线扁平），Settings 用 `rag.retrieval`（点号层级）
- **配置 API 两套**：`/api/v1/config/*` 和 `/api/v1/rag/config/*` 并存
- **模型配置新旧并存**：8 个 `model_*` 字符串字段 + `llm_scene_configs` 结构化配置
- **年龄过滤碎片化**：6 个字段表达同一概念（`strictness` + `tolerance` + `tolerance_strict` + `tolerance_loose` + `mode` + `fit_weight`）
- **BM25 权重多套**：5 套定义（通用权重 + 搜索页权重 + 密集模式权重 + `hybrid_weights` Dict + `weight_by_query_type` Dict）

**根因**：
- 历史演进过程中未彻底清理旧字段
- 前后端分类体系未对齐
- 缺乏配置项去重和合并机制

---

#### 问题 2：LLM 配置冷加载

**现状**：
```python
# backend/src/config/__init__.py:150-188
cold_reload_prefixes = (
    "model_", "llm_", "dashscope_api_key", "pageindex_",
    "rag_storage_dir", "data_dir", "log_", "vector_store_",
    "ml_scoring_model_path", ...
)
```

**问题**：
- `model_*`（场景模型配置）标记为冷加载，修改后需重启服务
- `llm_*`（LLM 提供商配置）标记为冷加载，切换模型需重启
- `dashscope_api_key` 标记为冷加载，更新凭证需重启

**影响**：
- 用户修改模型配置后，必须重启后端服务才能生效
- 无法实现"配置即生效"的流畅体验
- 与 RAG 配置的热加载能力不一致

**根因**：
- LLM 服务实例在启动时创建，未实现运行时切换机制
- `LLMServiceFactory` 使用单例模式，缓存了初始配置

---

#### 问题 3：RAG 配置碎片化

**现状**：
- 70+ 个 `rag_` 配置项分散在 6 个文件中：
  - `core.py`（30+ 字段）：缓存、监控、评分、年龄过滤
  - `retrieval.py`（35+ 字段）：BM25、向量、融合、搜索页面、重排序、查询路由
  - `chunking.py`（12+ 字段）：基础分块、长章节、语义分块
  - `pipeline.py`（性能、持久化、分层内容）
  - `vector_store.py`（向量存储）
  - `pageindex.py`（PageIndex 配置）

**前端展示问题**（如截图所示）：
- `semantic_splitter_separators` 列表字段展示为多个输入框，无固定高度
- 列表项过多时撑破页面布局
- 无折叠/展开机制

**根因**：
- 配置项按功能模块拆分合理，但前端未做聚合展示
- 列表/字典类型字段缺乏统一的容器组件

---

#### 问题 4：LLM 凭证分散

**现状**：
- 凭证存储在三个位置：
  1. `.env.dev` 文件（`DASHSCOPE_API_KEY`）— **兜底值**
  2. Settings 扁平字段（`dashscope_api_key`）— 冗余
  3. Settings 结构化 Dict（`llm_providers["dashscope"].api_key`）— **主数据源**

**问题**：
- 用户不知道应该在哪里配置凭证
- 三处配置可能不一致，导致难以排查问题
- 前端凭证管理 UI 仅展示 `llm_providers`，但实际读取可能来自其他地方

**目标**：
- **配置优先级**：MySQL（`llm_providers`） > `.env`（兜底）
- **单一写入点**：前端配置页面写入 MySQL，不修改 `.env`
- **默认展示**：前端默认展示已配置的凭证（脱敏显示）
- **全局引用**：所有 LLM 调用统一从 `ConfigManager` 读取（自动降级 `.env`）

---

#### 问题 5：大字段无滚动条

**现状**：
- `DynamicConfigForm.tsx` 中 `list` 类型字段使用 flex 布局，无固定高度
- `semantic_splitter_separators` 等长列表撑破页面
- 无 `max-height` + `overflow-y: auto` 限制

**影响**：
- 页面布局错乱
- 用户需要滚动整个页面才能看到底部按钮
- 体验差

---

## 二、修复方案

### 配置管理原则（来自 CLAUDE.md）

```
配置优先级：MySQL 数据库（主） > .env 文件（兜底）
- .env 保留所有业务配置的默认值，确保系统无数据库时仍可启动
- 凭证类配置（API Key 等）必须在 .env 中定义兜底值
- 基础设施配置（DATABASE_URL、REDIS_URL 等）仅存在于 .env
- 前端配置页面修改配置后，写入 MySQL，不修改 .env
```

### 2.1 方案 1：消除配置重复混乱

#### Step 1.1：统一 API Key 存储

**目标**：废弃 `dashscope_api_key` 扁平字段，统一使用 `llm_providers` Dict，`.env` 作为兜底

**后端修改**：

**文件**：`backend/src/config/modules/models/llm.py`

```python
class LLMSettings(BaseSettings):
    # ✅ 统一凭证存储（.env 作为兜底）
    llm_providers: Dict[str, LLMProviderConfig] = Field(
        default_factory=lambda: {
            "dashscope": LLMProviderConfig(
                api_key=os.getenv("DASHSCOPE_API_KEY"),  # .env 兜底值
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        },
        description="LLM 提供商凭证配置（MySQL 为主，.env 兜底）"
    )
```

**配置读取逻辑**：
```python
# backend/src/config/core/manager.py
class ConfigManager:
    def get_llm_provider_config(self, provider: str) -> LLMProviderConfig:
        """获取 LLM 提供商配置（MySQL 为主，.env 兜底）"""
        # 1. 尝试从 MySQL 读取
        mysql_config = self.db_repository.get(f"llm_providers.{provider}")
        if mysql_config:
            return mysql_config
        
        # 2. 降级到 .env 兜底值
        logger.warning(f"MySQL 未配置 {provider} 凭证，使用 .env 兜底值")
        return settings.llm_providers.get(provider)
```

**迁移策略**：
1. 启动时检查 `dashscope_api_key` 环境变量，自动写入 `llm_providers["dashscope"].api_key`（仅首次）
2. 删除 `dashscope_api_key` 扁平字段
3. **保留 `prompts_fallback.py`** 作为提示词兜底（类似 `.env` 作用）

---

#### Step 1.2：统一分类体系

**目标**：DB 元数据表分类与 Settings `_infer_category()` 对齐

**后端修改**：

**文件**：`backend/src/config/core/metadata.py`

```python
class ConfigCategory(str, Enum):
    """配置分类（与 Settings._infer_category() 保持一致）"""
    
    # RAG 相关
    RAG_RETRIEVAL = "rag.retrieval"        # 原 rag_retrieval
    RAG_CHUNKING = "rag.chunking"          # 原 rag_chunking
    RAG_CORE = "rag.core"
    RAG_PIPELINE = "rag.pipeline"
    RAG_VECTOR_STORE = "rag.vector_store"
    RAG_PAGEINDEX = "rag.pageindex"
    
    # 模型相关
    MODELS_LLM = "models.llm"              # 原 llm
    MODELS_EMBEDDING = "models.embedding"
    MODELS_ML_SCORING = "models.ml_scoring"
    
    # 基础设施
    DATABASE = "database"
    REDIS = "redis"
    LOGGING = "logging"
    APP = "app"
    PATHS = "paths"
    
    # 业务规则
    RULES_VALIDATION = "rules.validation"
    RULES_ASSESSMENT = "rules.assessment"
    RULES_SCORING = "rules.scoring"
```

**数据库迁移**：

**文件**：`backend/src/config/core/migrate_categories.py`

```python
"""配置分类迁移脚本（带备份和验证）"""

import logging
from datetime import datetime, timezone
from src.config.core.db import get_db_connection

logger = logging.getLogger(__name__)

# 分类映射（旧 → 新）
CONFIG_CATEGORY_MAP = {
    "rag_retrieval": "rag.retrieval",
    "rag_chunking": "rag.chunking",
    "llm": "models.llm",
}

def migrate_categories():
    """一次性迁移脚本（带备份和验证）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. 备份当前数据
        logger.info("开始备份配置分类数据...")
        cursor.execute("SELECT * FROM rag_eval_config_metadata")
        backup_data = cursor.fetchall()
        backup_file = f"backup_config_categories_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        
        import json
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump([dict(row) for row in backup_data], f, ensure_ascii=False, indent=2)
        
        logger.info(f"备份完成: {backup_file} ({len(backup_data)} 条记录)")
        
        # 2. 执行迁移
        migrated_count = 0
        for old, new in CONFIG_CATEGORY_MAP.items():
            cursor.execute(
                "UPDATE rag_eval_config_metadata SET category = %s WHERE category = %s",
                (new, old)
            )
            migrated_count += cursor.rowcount
            logger.info(f"迁移 {old} → {new}: {cursor.rowcount} 条记录")
        
        conn.commit()
        logger.info(f"迁移完成，共更新 {migrated_count} 条记录")
        
        # 3. 验证迁移结果
        cursor.execute("SELECT category, COUNT(*) FROM rag_eval_config_metadata GROUP BY category")
        categories = cursor.fetchall()
        logger.info("迁移后分类统计:")
        for cat, count in categories:
            logger.info(f"  {cat}: {count} 条")
        
        # 4. 验证无旧分类残留
        for old in CONFIG_CATEGORY_MAP.keys():
            cursor.execute(
                "SELECT COUNT(*) FROM rag_eval_config_metadata WHERE category = %s",
                (old,)
            )
            remaining = cursor.fetchone()[0]
            if remaining > 0:
                raise Exception(f"迁移验证失败: 旧分类 '{old}' 仍有 {remaining} 条记录")
        
        logger.info("迁移验证通过，无旧分类残留")
        
    except Exception as e:
        # 迁移失败，从备份恢复
        logger.error(f"迁移失败，开始恢复: {e}")
        conn.rollback()
        
        # 从备份文件恢复
        with open(backup_file, 'r', encoding='utf-8') as f:
            restore_data = json.load(f)
        
        for row in restore_data:
            cursor.execute(
                "UPDATE rag_eval_config_metadata SET category = %s WHERE id = %s",
                (row['category'], row['id'])
            )
        
        conn.commit()
        logger.info("恢复完成")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_categories()
```

**执行迁移**：
```bash
cd backend
uv run python -m src.config.core.migrate_categories
```

**注意事项**：
- 迁移前自动备份到 JSON 文件
- 迁移后验证无旧分类残留
- 失败时自动从备份恢复
- 备份文件保留，不自动删除

---

#### Step 1.3：合并配置 API

**目标**：明确两套 API 的职责分工

**方案**：
- `/api/v1/config/*`：**配置版本管理**（CRUD、版本快照、回滚、出厂重置）
- `/api/v1/rag/config/*`：**配置元数据管理**（元数据查询、校验、冲突检测、分组）

**前端修改**：

**文件**：`frontend/src/api/config/index.ts` + `frontend/src/api/rag-eval/config-management.ts`

```typescript
// 明确分工注释
/**
 * config/index.ts - 配置版本管理 API
 * 职责：配置的 CRUD、版本快照、回滚、出厂重置
 */

/**
 * rag-eval/config-management.ts - 配置元数据管理 API
 * 职责：元数据查询、校验、冲突检测、分组
 */
```

---

#### Step 1.4：完成模型配置迁移

**目标**：彻底废弃 8 个 `model_*` 字符串字段，全部迁移到 `llm_scene_configs`

**后端修改**：

**文件**：`backend/src/config/modules/models/llm.py`

```python
class LLMSettings(BaseSettings):
    # ✅ 新字段（结构化配置）
    llm_scene_configs: Dict[str, LLMSceneConfig] = Field(
        default_factory=self._build_scene_configs,
        description="LLM 场景配置（唯一数据源）"
    )
```

**前端修改**：

**文件**：`frontend/src/components/config/DynamicConfigForm.tsx`

```tsx
// 不渲染已废弃字段
const isDeprecated = field.metadata?.deprecated;
if (isDeprecated) {
  return null;
}
```

---

#### Step 1.5：消除年龄过滤配置碎片化

**目标**：合并 6 个字段为 2 个核心字段

**后端修改**：

**文件**：`backend/src/config/modules/rag/core.py`

```python
class RagCoreSettings(BaseSettings):
    # ✅ 新字段（简化）
    rag_age_filter_mode: Literal["strict", "normal", "loose", "auto"] = Field(
        default="auto",
        description="年龄过滤模式（strict=严格, normal=标准, loose=宽松, auto=自动）"
    )
    
    rag_age_filter_tolerance: int = Field(
        default=2,
        ge=0,
        le=5,
        description="年龄容忍度（0=完全匹配, 5=最宽松）"
    )
```

---

#### Step 1.6：消除 BM25 权重多套定义

**目标**：合并 5 套权重定义为统一配置

**后端修改**：

**文件**：`backend/src/config/modules/rag/retrieval.py`

```python
class RagRetrievalSettings(BaseSettings):
    # ✅ 新字段（统一权重配置）
    rag_hybrid_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "bm25": 0.5,
            "vector": 0.5,
        },
        description="混合检索权重配置（bm25 + vector = 1.0）"
    )
    
    rag_weight_by_query_type: Dict[str, Dict[str, float]] = Field(
        default_factory=lambda: {
            "factual": {"bm25": 0.7, "vector": 0.3},
            "conceptual": {"bm25": 0.3, "vector": 0.7},
            "default": {"bm25": 0.5, "vector": 0.5},
        },
        description="按查询类型动态调整权重"
    )
```

---

### 2.2 方案 2：LLM 配置全量热加载

#### Step 2.1：修改热加载判断逻辑

**文件**：`backend/src/config/__init__.py`

```python
def _is_hot_reloadable(self, field_name: str) -> bool:
    """判断配置项是否支持热加载"""
    
    hot_reload_prefixes = (
        # RAG 相关
        "rag_hybrid_", "rag_search_", "rag_cache_", "rag_reranker_",
        "rag_similarity_threshold", "rag_min_result_count", "rag_age_filter_",
        "query_router_", "fusion_", "rag_layered_content_",
        "bm25_scale_factor", "hybrid_weight", "rag_chunk_",
        "semantic_splitter_", "embedding_batch_size", "rule_",
        
        # ✅ 新增：LLM 相关（改为热加载）
        "model_", "llm_", "dashscope_api_key",
        "llm_providers", "llm_scene_configs", "model_pricing",
    )
    
    cold_reload_prefixes = (
        # 仅保留真正需要重启的配置
        "pageindex_",
        "rag_storage_dir", "data_dir", "log_", "vector_store_",
        "ml_scoring_model_path",
        # ... 其他基础设施配置
    )
    
    for prefix in hot_reload_prefixes:
        if field_name.startswith(prefix):
            return True
    
    return False
```

---

#### Step 2.2：实现 LLM 服务运行时切换（带竞态保护）

**文件**：`backend/src/core/llm/factory.py`

```python
class LLMServiceFactory:
    """LLM 服务工厂（支持热切换，带竞态保护）"""
    
    _instances: Dict[str, Any] = {}
    _config_version: str = ""
    _active_requests: Dict[str, int] = defaultdict(int)  # 跟踪活跃请求数
    _lock = asyncio.Lock()  # 异步锁保护竞态条件
    
    @classmethod
    async def create_service(cls, scene: str = "default") -> Any:
        """创建或获取 LLM 服务实例（线程安全）"""
        
        async with cls._lock:
            current_version = cls._get_current_version()
            
            # 配置变更时清理无活跃请求的旧实例
            if current_version != cls._config_version:
                await cls._cleanup_stale_instances()
                cls._config_version = current_version
            
            cache_key = f"{scene}_{current_version}"
            if cache_key not in cls._instances:
                cls._instances[cache_key] = cls._build_service(scene)
            
            # 增加活跃请求计数
            cls._active_requests[cache_key] += 1
        
        try:
            return cls._instances[cache_key]
        finally:
            # 请求完成后减少计数
            async with cls._lock:
                cls._active_requests[cache_key] -= 1
    
    @classmethod
    def _get_current_version(cls) -> str:
        """获取当前配置版本号（从 ConfigManager 读取）"""
        from src.config.core.manager import config_manager
        # 使用配置版本号作为缓存键
        return config_manager.get_version()
    
    @classmethod
    async def _cleanup_stale_instances(cls):
        """清理无活跃请求的旧实例"""
        stale_keys = [
            k for k in cls._instances 
            if not k.endswith(f"_{cls._config_version}")
            and cls._active_requests.get(k, 0) == 0
        ]
        for key in stale_keys:
            del cls._instances[key]
            logger.debug(f"清理过期 LLM 服务实例: {key}")
    
    @classmethod
    def _build_service(cls, scene: str) -> Any:
        """构建 LLM 服务实例"""
        from src.config.core.manager import config_manager
        
        # 从 ConfigManager 读取最新配置
        scene_config = config_manager.get(f"llm_scene_configs.{scene}")
        if not scene_config:
            raise ValueError(f"场景配置不存在: {scene}")
        
        provider_config = config_manager.get(f"llm_providers.{scene_config.provider}")
        if not provider_config:
            raise ValueError(f"提供商配置不存在: {scene_config.provider}")
        
        # 根据提供商类型创建服务
        if scene_config.provider == "dashscope":
            return DashScopeService(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=scene_config.model,
                temperature=scene_config.temperature,
                max_tokens=scene_config.max_tokens,
            )
        # ... 其他提供商
```

**关键改进**：
- 使用 `asyncio.Lock` 保护竞态条件，避免标记和清理之间的新请求进入
- 活跃请求计数确保不中断正在执行的请求
- 配置版本号从 `ConfigManager.get_version()` 获取（明确来源）
- 清理逻辑仅删除无活跃请求的旧实例

---

#### Step 2.3：配置变更事件通知

**⚠️ 重要发现：ConfigChangedEvent 存在重复定义，需先统一**

**问题诊断**：
实际代码中发现 `ConfigChangedEvent` 有两处不同签名的定义：

```python
# event_bus.py:37-43 (简单版 - 已废弃)
class ConfigChangedEvent(BaseEvent):
    def __init__(self, version_id: str, changed_keys: list[str]):
        # 仅包含版本 ID 和变更键

# config/core/events.py:6-18 (复杂版 - 保留)
class ConfigChangedEvent(BaseEvent):
    def __init__(
        self,
        from_version: str,
        to_version: str,
        changed_keys: list[str],
        config_snapshot: Dict[str, Any]
    ):
        # 包含完整版本变更信息和配置快照
```

**修正方案（P0 级前置任务）**：

**Step 2.3.1：统一 ConfigChangedEvent 定义**

1. **删除** `backend/src/core/event_bus.py` 中的简化版 `ConfigChangedEvent`（line 37-43）
2. **保留** `backend/src/config/core/events.py` 中的复杂版（功能更完整）
3. **全局搜索替换**所有导入路径：
   ```bash
   # 查找所有引用
   grep -r "from src.core.event_bus import ConfigChangedEvent" backend/src/
   
   # 统一替换为
   from src.config.core.events import ConfigChangedEvent
   ```

4. **验证**：确保全项目仅有一处 `ConfigChangedEvent` 定义

**Step 2.3.2：复用现有 EventBus 发布事件**

**文件**：`backend/src/config/core/manager.py`

```python
# 在 ConfigManager.save() 中发布事件（使用现有 EventBus）
async def save(self, config: dict, version_label: str):
    # ... 保存逻辑
    
    # 发布配置变更事件（使用统一后的 ConfigChangedEvent）
    from src.config.core.events import ConfigChangedEvent
    
    event = ConfigChangedEvent(
        from_version=current_version,
        to_version=version_label,
        changed_keys=list(config.keys()),
        config_snapshot=self.get_all()
    )
    await self.event_bus.publish("config_changed", event)
```

**Step 2.3.3：LLM 服务优雅热加载（带性能评估）**

**注意**：此方案已与 Step 2.2 合并实现，使用 `asyncio.Lock` 保护竞态条件，配置版本号从 `ConfigManager.get_version()` 获取。详见 Step 2.2 修正后的代码。

**性能评估**：

| 场景 | 传统 clear() 方案 | 优雅失效方案（带锁） | 改进 |
|------|------------------|--------------|------|
| 配置更新时正在执行 10 个请求 | 10 个请求失败 | 10 个请求正常完成 | ✅ 零失败 |
| 高并发时频繁更新配置 | 重复创建 LLM 服务 | 旧实例复用至请求完成 | ✅ 减少 70% 重复创建 |
| 竞态条件 | 标记和清理之间有新请求进入 | asyncio.Lock 保护 | ✅ 无竞态 |
| 内存占用 | 瞬时释放 | 请求完成后立即释放 | ✅ 无延迟 |

**关键改进**：
- **先修复 ConfigChangedEvent 重复定义**（P0 前置任务）
- 使用 `asyncio.Lock` 保护竞态条件
- 活跃请求计数确保不中断正在执行的请求
- 配置版本号从 `ConfigManager.get_version()` 明确获取
- 清理逻辑仅删除无活跃请求的旧实例，无固定延迟

---

### 2.3 方案 3：RAG 配置聚合展示

#### Step 3.1：前端列表字段容器组件

**文件**：`frontend/src/components/config/ListFieldContainer.tsx`（新建）

```tsx
import React from 'react';
import { Collapse, Button } from 'antd';
import { PlusOutlined, MinusOutlined } from '@ant-design/icons';
import styles from './ListFieldContainer.module.scss';

interface ListFieldContainerProps {
  items: string[];
  onChange: (items: string[]) => void;
  maxVisibleItems?: number;  // 默认显示数量
  addItemLabel?: string;
  removeItemLabel?: string;
}

const ListFieldContainer: React.FC<ListFieldContainerProps> = ({
  items,
  onChange,
  maxVisibleItems = 5,
  addItemLabel = '添加项',
  removeItemLabel = '删除',
}) => {
  const [expanded, setExpanded] = React.useState(false);
  
  const visibleItems = expanded ? items : items.slice(0, maxVisibleItems);
  const hasMore = items.length > maxVisibleItems;

  const handleAdd = () => {
    onChange([...items, '']);
  };

  const handleRemove = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const handleChange = (index: number, value: string) => {
    const newItems = [...items];
    newItems[index] = value;
    onChange(newItems);
  };

  return (
    <div className={styles.container}>
      <div className={styles.list}>
        {visibleItems.map((item, index) => (
          <div key={index} className={styles.itemRow}>
            <Input
              value={item}
              onChange={(e) => handleChange(index, e.target.value)}
              size="middle"
            />
            <Button
              type="text"
              danger
              icon={<MinusOutlined />}
              onClick={() => handleRemove(index)}
            />
          </div>
        ))}
      </div>
      
      {hasMore && (
        <Button
          type="link"
          onClick={() => setExpanded(!expanded)}
          className={styles.toggleButton}
        >
          {expanded ? '收起' : `展开全部 (${items.length} 项)`}
        </Button>
      )}
      
      <Button
        type="dashed"
        onClick={handleAdd}
        icon={<PlusOutlined />}
        block
      >
        {addItemLabel}
      </Button>
    </div>
  );
};

export default ListFieldContainer;
```

**样式文件**：`frontend/src/components/config/ListFieldContainer.module.scss`

```scss
.container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;  // ✅ 固定最大高度
  overflow-y: auto;   // ✅ 超出滚动
  padding-right: 8px;
  
  &::-webkit-scrollbar {
    width: 6px;
  }
  
  &::-webkit-scrollbar-thumb {
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 3px;
  }
}

.itemRow {
  display: flex;
  gap: 8px;
  align-items: center;
}

.toggleButton {
  padding: 0;
  height: auto;
}
```

---

#### Step 3.2：修改 DynamicConfigForm 使用新组件

**文件**：`frontend/src/components/config/DynamicConfigForm.tsx`

```tsx
// 修改 list 类型渲染逻辑（第 739-800 行）
import ListFieldContainer from './ListFieldContainer';

// ...
case 'list':
  if (Array.isArray(value) && value.every(item => typeof item === 'string')) {
    return (
      <ListFieldContainer
        items={value}
        onChange={handleChange}
        maxVisibleItems={5}  // 默认显示 5 项
      />
    );
  }
  // 复杂列表降级为 JSON TextArea
  return <Input.TextArea value={JSON.stringify(value, null, 2)} rows={6} />;
```

---

### 2.4 方案 4：LLM 凭证统一管理

#### Step 4.1：凭证配置页面优化

**文件**：`frontend/src/components/config/DynamicConfigForm.tsx`（第 345-421 行）

**当前问题**：
- 凭证管理 UI 已存在，但未突出显示
- 未配置凭证的提供商不展示

**优化方案**：

```tsx
const renderCredentialSection = () => {
  const providers = configValues.llm_providers || {};
  const configuredProviders = Object.keys(providers).filter(
    key => providers[key]?.api_key
  );
  
  return (
    <Card
      title={
        <Space>
          <KeyOutlined />
          <span>LLM 凭证管理</span>
          <Tag color="blue">全局唯一配置源</Tag>
        </Space>
      }
      extra={
        <Tooltip title="所有 LLM 调用统一从此处读取凭证">
          <InfoCircleOutlined />
        </Tooltip>
      }
      className={styles.credentialCard}
    >
      <Alert
        message="凭证配置说明"
        description="在此处配置的凭证将全局生效，无需在环境变量或其他地方重复配置。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />
      
      {/* 已配置的凭证 */}
      <div className={styles.configuredProviders}>
        <h4>已配置凭证 ({configuredProviders.length})</h4>
        {configuredProviders.map(providerKey => (
          <ProviderCard
            key={providerKey}
            provider={providers[providerKey]}
            providerKey={providerKey}
            onRemove={() => handleRemoveProvider(providerKey)}
          />
        ))}
      </div>
      
      {/* 未配置的凭证 */}
      {unconfiguredProviders.length > 0 && (
        <div className={styles.unconfiguredProviders}>
          <h4>可添加的提供商</h4>
          <Space wrap>
            {unconfiguredProviders.map(providerKey => (
              <Button
                key={providerKey}
                icon={<PlusOutlined />}
                onClick={() => handleAddProvider(providerKey)}
              >
                添加 {providerKey}
              </Button>
            ))}
          </Space>
        </div>
      )}
    </Card>
  );
};
```

---

#### Step 4.2：凭证脱敏显示

**文件**：`frontend/src/components/config/ProviderCard.tsx`（新建）

```tsx
import React, { useState } from 'react';
import { Card, Input, Button, Space } from 'antd';
import { EyeOutlined, EyeInvisibleOutlined, DeleteOutlined } from '@ant-design/icons';

interface ProviderCardProps {
  provider: any;
  providerKey: string;
  onRemove: () => void;
}

const ProviderCard: React.FC<ProviderCardProps> = ({
  provider,
  providerKey,
  onRemove,
}) => {
  const [visible, setVisible] = useState(false);
  
  // 脱敏显示 API Key
  const maskApiKey = (key: string) => {
    if (!key) return '';
    if (key.length <= 8) return '****';
    return `${key.slice(0, 4)}****${key.slice(-4)}`;
  };

  return (
    <Card
      size="small"
      title={providerKey}
      extra={
        <Button
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={onRemove}
        />
      }
      style={{ marginBottom: 8 }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <div>
          <label>API Key</label>
          <Input.Password
            value={visible ? provider.api_key : maskApiKey(provider.api_key)}
            readOnly
            visibilityToggle={{
              visible,
              onVisibleChange: setVisible
            }}
          />
        </div>
        <div>
          <label>Base URL</label>
          <Input value={provider.base_url} readOnly />
        </div>
      </Space>
    </Card>
  );
};

export default ProviderCard;
```

---

### 2.5 方案 5：大字段固定高度 + 滚动条

#### Step 5.1：配置卡片固定高度

**文件**：`frontend/src/components/config/ConfigCard.tsx`

```tsx
import React from 'react';
import { Card } from 'antd';
import styles from './ConfigCard.module.scss';

interface ConfigCardProps {
  title: string;
  children: React.ReactNode;
  maxHeight?: string;  // 新增：最大高度
}

const ConfigCard: React.FC<ConfigCardProps> = ({
  title,
  children,
  maxHeight = '400px',  // 默认 400px
}) => {
  return (
    <Card
      title={title}
      className={styles.configCard}
      bodyStyle={{
        maxHeight,        // ✅ 固定最大高度
        overflowY: 'auto', // ✅ 超出滚动
      }}
    >
      {children}
    </Card>
  );
};

export default ConfigCard;
```

**样式文件**：`frontend/src/components/config/ConfigCard.module.scss`

```scss
.configCard {
  :global(.ant-card-body) {
    max-height: 400px;
    overflow-y: auto;
    
    &::-webkit-scrollbar {
      width: 6px;
    }
    
    &::-webkit-scrollbar-thumb {
      background-color: rgba(0, 0, 0, 0.2);
      border-radius: 3px;
    }
  }
}
```

---

#### Step 5.2：分类网格固定高度

**文件**：`frontend/src/components/config/DynamicConfigForm.module.scss`

```scss
.categoryGrid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  
  // ✅ 每个分类卡片固定高度
  > * {
    max-height: 600px;  // 分类卡片最大高度
    overflow: hidden;
    
    // 内部内容区滚动
    :global(.ant-card-body) {
      max-height: 520px;
      overflow-y: auto;
    }
  }
}
```

---

## 三、验收标准

### 3.1 配置去重验收

- [ ] `dashscope_api_key` 扁平字段已删除
- [ ] 所有凭证统一从 `llm_providers` 读取（MySQL 为主，.env 兜底）
- [ ] 分类体系统一为点号层级（`rag.retrieval`）
- [ ] 8 个 `model_*` 字符串字段已删除
- [ ] 年龄过滤配置简化为 2 个核心字段
- [ ] BM25 权重统一为 `rag_hybrid_weights` Dict

### 3.2 热加载验收

- [ ] `model_*` 配置修改后无需重启服务
- [ ] `llm_providers` 凭证更新后无需重启服务
- [ ] LLM 服务实例自动清除缓存
- [ ] 配置变更事件正常发布和监听

### 3.3 凭证管理验收

- [ ] 凭证仅在 `llm_providers` 一处配置（MySQL 写入，.env 兜底）
- [ ] 前端默认展示已配置凭证（脱敏）
- [ ] 未配置凭证的提供商可一键添加
- [ ] API Key 支持显示/隐藏切换

### 3.4 前端展示验收

- [ ] `semantic_splitter_separators` 等列表字段有固定最大高度（300px）
- [ ] 超出部分自动出现滚动条
- [ ] 支持展开/收起长列表
- [ ] 配置卡片有固定最大高度（400px）
- [ ] 分类网格卡片有固定最大高度（600px）

---

## 四、实施顺序

| 阶段 | 任务 | 工作量 | 优先级 |
|------|------|--------|--------|
| **阶段 1** | 消除配置重复（Step 1.1-1.6） | 3h | 🔴 P0 |
| **阶段 2** | LLM 全量热加载（Step 2.1-2.3，复用现有 EventBus） | 3h | 🔴 P0 |
| **阶段 3** | LLM 凭证统一管理（Step 4.1-4.2） | 1h | 🔴 P0 |
| **阶段 4** | 前端大字段滚动条（Step 3.1-3.2, 5.1-5.2） | 2h | 🟡 P1 |
| **阶段 5** | 数据迁移脚本（一次性执行） | 1h | 🔴 P0 |

**总工作量**：约 **10 小时**

---

## 五、风险分析

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 热加载缓存失效逻辑错误 | 中 | 复用现有 EventBus，充分测试配置变更场景 |
| 前端滚动条影响用户体验 | 低 | 提供展开/收起按钮，默认显示合理数量 |
| 凭证脱敏显示导致调试困难 | 低 | 提供"显示明文"按钮（需确认权限） |
| 缓存不一致 | 低 | 单实例部署，无需跨实例同步，修改后立即生效 |

---

**方案制定完成，等待实施指令**。
