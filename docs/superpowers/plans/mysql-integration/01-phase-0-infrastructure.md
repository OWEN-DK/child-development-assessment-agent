# Phase 0: MySQL + Redis 基础设施搭建

> 本文档是 MySQL + Redis 集成重构实施方案的一部分
> 
> **返回索引：** [README.md](./README.md) | [项目概览](./00-overview.md)

---

## Phase 0: MySQL + Redis 基础设施搭建（周期：3天）
### Task 0.1: 安装依赖
**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 添加依赖到 pyproject.toml**
```toml
[project]
dependencies = [
    "sqlalchemy>=2.0.29",
    "alembic>=1.13.1",
    "aiomysql>=0.2.0",
    "redis>=5.0.3",
    "hiredis>=2.3.2",
    "cachetools>=5.3.0",
    "pydantic-settings>=2.2.1",
    "python-dotenv>=1.0.1",
    "pybloom-live>=4.0.0",
]
```

- [ ] **Step 2: 安装依赖**
```bash
cd /Users/owen/project/ai/child-development-assessment-agent/backend
uv sync
```
**Expected:** 所有依赖安装成功，无版本冲突。

### Task 0.2: 新增数据库配置模块
**Files:**
- Create: `backend/src/config/modules/database.py`
- Modify: `backend/.env.dev`
- Modify: `backend/src/config/__init__.py`

- [ ] **Step 1: 创建database.py配置**
```python
from pydantic_settings import BaseSettings
from pydantic import Field

class DatabaseSettings(BaseSettings):
    """MySQL 数据库配置"""
    db_host: str = Field(default="localhost", validation_alias="MYSQL_HOST")
    db_port: int = Field(default=3306, validation_alias="MYSQL_PORT")
    db_user: str = Field(default="root", validation_alias="MYSQL_USER")
    db_password: str = Field(default="", validation_alias="MYSQL_PASSWORD")
    db_name: str = Field(default="child_development", validation_alias="MYSQL_DATABASE")
    
    pool_size: int = Field(default=10, validation_alias="MYSQL_POOL_SIZE")
    max_overflow: int = Field(default=20, validation_alias="MYSQL_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, validation_alias="MYSQL_POOL_TIMEOUT")
    pool_recycle: int = Field(default=1800, validation_alias="MYSQL_POOL_RECYCLE")
    
    @property
    def async_url(self) -> str:
        """异步数据库连接 URL"""
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )
    
    @property
    def sync_url(self) -> str:
        """同步数据库连接 URL（用于 Alembic 迁移）"""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

database_settings = DatabaseSettings()
```

- [ ] **Step 2: 添加.env.dev配置项**
```env
# MySQL Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=child_development
MYSQL_POOL_SIZE=10
MYSQL_MAX_OVERFLOW=20
MYSQL_POOL_TIMEOUT=30
MYSQL_POOL_RECYCLE=1800
```

- [ ] **Step 3: 聚合到config/__init__.py**
```python
# 在现有导入后添加
from .modules.database import database_settings

__all__ = [
    # 现有导出项
    "database_settings",
]
```

- [ ] **Step 4: 测试配置加载**
```bash
cd backend
uv run python -c "from src.config import database_settings; print('MySQL URL:', database_settings.async_url)"
```
**Expected:** 输出正确的 MySQL 连接 URL。

### Task 0.3: 新增 Redis 配置模块
**Files:**
- Create: `backend/src/config/modules/redis.py`
- Modify: `backend/.env.dev`
- Modify: `backend/src/config/__init__.py`

- [ ] **Step 1: 创建redis.py配置**
```python
from pydantic_settings import BaseSettings
from pydantic import Field

class RedisSettings(BaseSettings):
    """Redis 缓存加速层配置"""
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    redis_password: str = Field(default="", validation_alias="REDIS_PASSWORD")
    
    # 连接池配置
    redis_max_connections: int = Field(default=20, validation_alias="REDIS_MAX_CONNECTIONS")
    redis_socket_timeout: int = Field(default=5, validation_alias="REDIS_SOCKET_TIMEOUT")
    redis_socket_connect_timeout: int = Field(default=3, validation_alias="REDIS_SOCKET_CONNECT_TIMEOUT")
    
    # 缓存配置
    cache_enabled: bool = Field(default=True, validation_alias="REDIS_CACHE_ENABLED")
    cache_default_ttl: int = Field(default=3600, validation_alias="REDIS_CACHE_DEFAULT_TTL")  # 1小时
    cache_max_memory: str = Field(default="256mb", validation_alias="REDIS_CACHE_MAX_MEMORY")
    
    # 分布式锁配置
    lock_timeout: int = Field(default=30, validation_alias="REDIS_LOCK_TIMEOUT")  # 30秒
    lock_retry_interval: float = Field(default=0.1, validation_alias="REDIS_LOCK_RETRY_INTERVAL")
    
    # 会话存储配置
    session_ttl: int = Field(default=86400, validation_alias="REDIS_SESSION_TTL")  # 24小时
    
    # 消息队列配置
    pubsub_enabled: bool = Field(default=True, validation_alias="REDIS_PUBSUB_ENABLED")
    pubsub_channels: list[str] = Field(
        default=["config:changed", "llm:call", "test:progress"],
        validation_alias="REDIS_PUBSUB_CHANNELS"
    )

redis_settings = RedisSettings()
```

- [ ] **Step 2: 添加.env.dev配置项**
```env
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your_password
REDIS_MAX_CONNECTIONS=20
REDIS_CACHE_DEFAULT_TTL=3600
REDIS_LOCK_TIMEOUT=30
REDIS_SESSION_TTL=86400
REDIS_PUBSUB_ENABLED=true
```

- [ ] **Step 3: 聚合到config/__init__.py**
```python
# 在现有导入后添加
from .modules.redis import redis_settings

__all__ = [
    # 现有导出项
    "redis_settings",
]
```

- [ ] **Step 4: 测试配置加载**
```bash
cd backend
uv run python -c "from src.config import redis_settings; print('Redis URL:', redis_settings.redis_url)"
```
**Expected:** 输出正确的 Redis 连接 URL。

### Task 0.4: 创建数据库核心模块
**Files:**
- Create: `backend/src/core/database.py`

- [ ] **Step 1: 编写database.py代码**
```python
import time
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from src.config import database_settings, settings
from src.utils.logger import logger

# 创建异步引擎
engine = create_async_engine(
    database_settings.async_url,
    echo=settings.debug,
    pool_size=database_settings.pool_size,
    max_overflow=database_settings.max_overflow,
    pool_timeout=database_settings.pool_timeout,
    pool_recycle=database_settings.pool_recycle,
    pool_pre_ping=True,  # 连接前检测有效性
    pool_use_lifo=True,  # LIFO策略提高连接复用率
    echo_pool="debug" if settings.debug else None,
)

# 创建会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass

# 慢查询检测
SLOW_QUERY_THRESHOLD_MS = 100  # 慢查询阈值（毫秒）

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """记录 SQL 执行开始时间"""
    conn.info.setdefault("query_start_time", []).append(time.time())

@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """记录 SQL 执行结束时间，检测慢查询"""
    total = time.time() - conn.info["query_start_time"].pop(-1)
    duration_ms = total * 1000
    
    if duration_ms > SLOW_QUERY_THRESHOLD_MS:
        logger.warning(
            f"慢查询检测: {duration_ms:.2f}ms\n"
            f"SQL: {statement}\n"
            f"参数: {parameters}"
        )

async def get_pool_status() -> dict:
    """获取连接池当前状态"""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalidated": pool.invalidated(),
    }
```

- [ ] **Step 2: 测试数据库连接**
```bash
cd backend
uv run python -c "
import asyncio
from src.core.database import engine, async_session_factory, get_pool_status
from sqlalchemy import text

async def test():
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT VERSION()'))
        print('MySQL Version:', result.scalar_one())
    print('Connection Pool Status:', await get_pool_status())
    await engine.dispose()

asyncio.run(test())
"
```
**Expected:** 成功连接 MySQL，输出版本号和连接池状态。

- [ ] **Step 3: 导出数据库会话工厂**
```python
# 在 backend/src/core/database.py 末尾添加
db_session_factory = async_session_factory
```

- [ ] **Step 4: 在 config/__init__.py 中导出**
```python
# 在 backend/src/config/__init__.py 中添加
from src.core.database import db_session_factory
__all__.append("db_session_factory")
```

### Task 0.5: 创建 Redis 客户端
**Files:**
- Create: `backend/src/core/redis_client.py`

- [ ] **Step 1: 编写redis_client.py代码**
```python
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from src.config import redis_settings
from src.utils.logger import logger

class RedisClient:
    """Redis 异步客户端单例"""
    _instance: redis.Redis | None = None
    _pool: ConnectionPool | None = None
    
    @classmethod
    def get_client(cls) -> redis.Redis:
        """获取 Redis 客户端实例（懒加载）"""
        if cls._instance is None:
            cls._pool = ConnectionPool.from_url(
                redis_settings.redis_url,
                password=redis_settings.redis_password or None,
                max_connections=redis_settings.redis_max_connections,
                socket_timeout=redis_settings.redis_socket_timeout,
                socket_connect_timeout=redis_settings.redis_socket_connect_timeout,
                decode_responses=True,
            )
            cls._instance = redis.Redis(connection_pool=cls._pool)
            logger.info("Redis 客户端已初始化")
        return cls._instance
    
    @classmethod
    async def close(cls):
        """关闭 Redis 连接池"""
        if cls._pool:
            await cls._pool.disconnect()
            logger.info("Redis 连接池已关闭")

# ⚠️ 注意：不要在模块级别创建全局实例
# 应该在需要使用时再获取：
# from src.core.redis_client import RedisClient
# 
# async def my_function():
#     redis_client = RedisClient.get_client()
#     await redis_client.get('key')
```

- [ ] **Step 2: 测试 Redis 连接**
```bash
cd backend
uv run python -c "
import asyncio
from src.core.redis_client import RedisClient

async def test():
    redis_client = RedisClient.get_client()
    await redis_client.set('test_key', 'test_value', ex=10)
    value = await redis_client.get('test_key')
    print('Redis Value:', value)
    assert value == 'test_value'
    await redis_client.delete('test_key')
    await RedisClient.close()

asyncio.run(test())
"
```
**Expected:** 成功连接 Redis，读写正常。

- [ ] **Step 3: 懒加载说明**
```python
# ⚠️ 重要：Redis 客户端使用懒加载模式
# 1. 模块导入时不会立即创建连接
# 2. 首次调用 get_client() 时才初始化连接池
# 3. 避免应用启动时连接所有服务，提高启动速度

# ✅ 正确的使用方式
from src.core.redis_client import RedisClient

async def my_function():
    redis_client = RedisClient.get_client()
    # 首次使用时自动初始化
    await redis_client.get('key')

# 🔧 如果需要手动控制初始化时机
from src.core.redis_client import RedisClient

async def init_redis():
    # 应用启动时显式初始化
    client = RedisClient.get_client()
    await client.ping()
    logger.info("Redis 客户端已就绪")
```

### Task 0.6: 配置 Alembic 迁移
**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`

- [ ] **Step 1: 初始化Alembic**
```bash
cd backend
alembic init alembic
```

- [ ] **Step 2: 修改alembic.ini**
```ini
# 修改sqlalchemy.url为动态获取
sqlalchemy.url = %(db_url)s
```

- [ ] **Step 3: 修改alembic/env.py**
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from src.core.database import Base
from src.config import database_settings

# 导入所有模型，确保Base.metadata包含所有表
import src.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", database_settings.sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: 测试 Alembic 配置**
```bash
cd backend
alembic current
```
**Expected:** 输出当前数据库版本（初始为空）。

### Task 0.7: 定义所有 SQLAlchemy 模型
**Files:**
- Create: `backend/src/models/__init__.py`
- Create: `backend/src/models/config.py`
- Create: `backend/src/models/test_case.py`
- Create: `backend/src/models/test_run.py`
- Create: `backend/src/models/document.py`
- Create: `backend/src/models/monitor.py`
- Create: `backend/src/models/prompt.py`

- [ ] **Step 0: 创建 models/__init__.py（明确导入顺序，避免循环依赖）**
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
from .test_run import TestRun, TestRunResult, TestRunStatus
from .document import SourceDocument, DocumentRecord
from .monitor import ABTestMetrics, LLMCallLog, LLMCallStatus
from .prompt import PromptVersion, PromptABTest

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
    "TestRunStatus",
    "SourceDocument",
    "DocumentRecord",
    "ABTestMetrics",
    "LLMCallLog",
    "LLMCallStatus",
    "PromptVersion",
    "PromptABTest",
]
```

- [ ] **Step 1: 创建 config.py 模型**
```python
from sqlalchemy import String, Text, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional, Dict, List

class ConfigAction(PyEnum):
    UPDATE = "UPDATE"
    ROLLBACK = "ROLLBACK"
    RESET = "RESET"

class ConfigVersion(Base):
    __tablename__ = "config_versions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    created_by: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    parent_version_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("config_versions.id"))
    is_factory_reset: Mapped[bool] = mapped_column(default=False)
    
    parent_version: Mapped["ConfigVersion | None"] = relationship(remote_side=[id])

class ConfigAuditLog(Base):
    __tablename__ = "config_audit_log"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    action: Mapped[ConfigAction] = mapped_column(Enum(ConfigAction), index=True)
    from_version: Mapped[str | None] = mapped_column(String(64), index=True)
    to_version: Mapped[str | None] = mapped_column(String(64), index=True)
    user: Mapped[str | None] = mapped_column(String(64))
```

- [ ] **Step 2: 创建test_case.py模型**
```python
from sqlalchemy import String, Text, DECIMAL, Enum, Integer, JSON, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum

class TestDomain(PyEnum):
    GROSS_MOTOR = "gross_motor"
    FINE_MOTOR = "fine_motor"
    LANGUAGE = "language"
    COGNITIVE = "cognitive"
    SOCIAL_EMOTIONAL = "social_emotional"
    SENSORY_INTEGRATION = "sensory_integration"

class DifficultyLevel(PyEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class TestCaseStatus(PyEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    IMPORTED = "imported"

class TestRunStatus(PyEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TestSourceType(PyEnum):
    MANUAL = "manual"
    JSON_IMPORT = "json_import"
    BOOK_GENERATED = "book_generated"
    MIXED = "mixed"

class TestCase(Base):
    __tablename__ = "test_cases"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[float] = mapped_column(DECIMAL(4, 1), nullable=False)
    domain: Mapped[TestDomain] = mapped_column(Enum(TestDomain), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # 查询优化字段
    expected_knowledge_count: Mapped[int] = mapped_column(Integer, default=0)
    answer_points_summary: Mapped[str | None] = mapped_column(Text)
    min_age_requirement: Mapped[float | None] = mapped_column(DECIMAL(4, 1))
    max_age_requirement: Mapped[float | None] = mapped_column(DECIMAL(4, 1))
    difficulty_level: Mapped[DifficultyLevel | None] = mapped_column(Enum(DifficultyLevel))
    
    # JSON 字段
    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
    expected_keywords: Mapped[list[str] | None] = mapped_column(JSON)
    professional_terms: Mapped[list[str] | None] = mapped_column(JSON)
    relevance_scores: Mapped[dict[str, float] | None] = mapped_column(JSON)
    
    source_document_id: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    
    __table_args__ = (
        Index("idx_domain", "domain"),
        Index("idx_age", "age"),
        Index("idx_difficulty", "difficulty_level"),
        Index("idx_age_range", "min_age_requirement", "max_age_requirement"),
        Index("idx_source_doc", "source_document_id"),
    )

class TestCaseDraft(Base):
    __tablename__ = "test_case_drafts"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_document_id: Mapped[str] = mapped_column(String(64), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[float] = mapped_column(DECIMAL(4, 1), nullable=False)
    domain: Mapped[TestDomain] = mapped_column(Enum(TestDomain), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
    expected_keywords: Mapped[list[str] | None] = mapped_column(JSON)
    answer_points: Mapped[list[str] | None] = mapped_column(JSON)
    professional_terms: Mapped[list[str] | None] = mapped_column(JSON)
    age_requirement: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    generation_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    
    status: Mapped[TestCaseStatus] = mapped_column(Enum(TestCaseStatus), default=TestCaseStatus.DRAFT, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    
    __table_args__ = (
        Index("idx_source_doc", "source_document_id"),
        Index("idx_domain_status", "domain", "status"),
    )

class TestSet(Base):
    __tablename__ = "test_sets"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[TestSourceType] = mapped_column(Enum(TestSourceType), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class TestSetCase(Base):
    __tablename__ = "test_set_cases"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_set_id: Mapped[str] = mapped_column(String(64), ForeignKey("test_sets.id", ondelete="CASCADE"), nullable=False)
    test_case_id: Mapped[str] = mapped_column(String(64), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    __table_args__ = (
        Index("idx_test_set", "test_set_id"),
        Index("idx_test_case", "test_case_id"),
    )

class TestRun(Base):
    __tablename__ = "test_runs"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # 聚合指标
    overall_precision: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    overall_recall: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    overall_f1: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    overall_mrr: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    overall_ndcg: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    total_test_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_test_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    
    status: Mapped[TestRunStatus] = mapped_column(Enum(TestRunStatus), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    snapshot_id: Mapped[str | None] = mapped_column(String(64))
    config_version_id: Mapped[str | None] = mapped_column(String(64), index=True)
    config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    previous_config_version_id: Mapped[str | None] = mapped_column(String(64))

class TestRunResult(Base):
    __tablename__ = "test_run_results"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    test_case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 核心指标（独立列用于聚合）
    precision: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    recall: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    f1: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    passed: Mapped[bool | None] = mapped_column(index=True)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    expected_count: Mapped[int] = mapped_column(Integer, default=0)
    actual_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # JSON 字段（详情展示）
    expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
    actual_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
    
    error_message: Mapped[str | None] = mapped_column(Text)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index("idx_run_id", "run_id"),
    )
```

- [ ] **Step 3: 创建document.py模型**
```python
from sqlalchemy import String, Text, DECIMAL, Enum, Integer, JSON, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum

class DocumentStatus(PyEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    ARCHIVED = "archived"

class ImportStatus(PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"

class SourceDocument(Base):
    __tablename__ = "source_documents"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(Enum("pdf", "epub", "txt"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    content_summary: Mapped[str | None] = mapped_column(Text)
    
    # 查询优化字段
    page_count: Mapped[int | None] = mapped_column(Integer)
    chapter_count: Mapped[int | None] = mapped_column(Integer)
    quality_score: Mapped[float | None] = mapped_column(DECIMAL(3, 2), index=True)
    scan_page_ratio: Mapped[float | None] = mapped_column(DECIMAL(3, 2))
    
    # JSON 字段
    chapter_structure: Mapped[list[str] | None] = mapped_column(JSON)
    quality_report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    
    __table_args__ = (
        Index("idx_file_hash", "file_hash"),
        Index("idx_status", "status"),
        Index("idx_file_type", "file_type"),
    )

class DocumentRecord(Base):
    __tablename__ = "document_records"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # 查询优化字段
    total_pages: Mapped[int | None] = mapped_column(Integer)
    indexed_chunks: Mapped[int] = mapped_column(Integer, default=0, index=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    
    # JSON 字段
    ref_doc_ids: Mapped[list[str] | None] = mapped_column(JSON)
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus), nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: 创建monitor.py模型**
```python
from sqlalchemy import String, Integer, DateTime, DECIMAL, Enum, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum

class LLMCallStatus(PyEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"

class ABTestMetrics(Base):
    __tablename__ = "ab_test_metrics"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    variant_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    __table_args__ = (
        Index("idx_test_variant", "test_name", "variant_name"),
    )

class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt_key: Mapped[str | None] = mapped_column(String(255), index=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    scenario: Mapped[str | None] = mapped_column(String(100), index=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer, index=True)
    
    status: Mapped[LLMCallStatus] = mapped_column(Enum(LLMCallStatus), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
```

- [ ] **Step 5: 创建 prompt.py 模型**
```python
from sqlalchemy import String, Text, DateTime, JSON, Boolean, Float, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from datetime import datetime

class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(64))
    variables: Mapped[list | None] = mapped_column(JSON)  # 自动识别的变量列表
    tags: Mapped[list | None] = mapped_column(JSON)  # 标签
    fallback: Mapped[str | None] = mapped_column(Text)  # 降级提示词
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index("idx_prompt_key_version", "prompt_key", "version", unique=True),
    )

class PromptABTest(Base):
    __tablename__ = "prompt_ab_tests"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    variant_a_version: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_b_version: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_a_ratio: Mapped[float] = mapped_column(Float, default=0.5)  # A 版本流量比例
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index("idx_ab_test_prompt", "prompt_key", "is_active"),
    )
```

- [ ] **Step 6: 创建models/__init__.py**
```python
from .config import ConfigVersion, ConfigAuditLog
from .test_case import (
    TestCase, TestCaseDraft, TestSet, TestSetCase,
    TestRun, TestRunResult, TestDomain, DifficultyLevel,
    TestCaseStatus, TestRunStatus, TestSourceType
)
from .document import SourceDocument, DocumentRecord, DocumentStatus, ImportStatus
from .monitor import ABTestMetrics, LLMCallLog, LLMCallStatus
from .prompt import PromptVersion, PromptABTest

__all__ = [
    "ConfigVersion",
    "ConfigAuditLog",
    "TestCase",
    "TestCaseDraft",
    "TestSet",
    "TestSetCase",
    "TestRun",
    "TestRunResult",
    "TestDomain",
    "DifficultyLevel",
    "TestCaseStatus",
    "TestRunStatus",
    "TestSourceType",
    "SourceDocument",
    "DocumentRecord",
    "DocumentStatus",
    "ImportStatus",
    "ABTestMetrics",
    "LLMCallLog",
    "LLMCallStatus",
    "PromptVersion",
    "PromptABTest",
]
```

- [ ] **Step 6: 生成初始迁移**
```bash
cd backend
alembic revision --autogenerate -m "init mysql tables"
```

- [ ] **Step 7: 验证迁移脚本**
检查`backend/alembic/versions/`下生成的迁移文件，确保所有表结构正确，索引齐全。

- [ ] **Step 8: 应用迁移**
```bash
cd backend
alembic upgrade head
```
**Expected:** 所有表创建成功，无报错。

- [ ] **Step 9: 创建配置实体定义**
```python
# 创建 backend/src/config/core/entities.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Optional

class ConfigVersion(BaseModel):
    """配置版本实体"""
    id: str
    created_at: datetime
    created_by: Optional[str] = None
    description: Optional[str] = None
    config_snapshot: dict[str, Any]
    parent_version_id: Optional[str] = None
    is_factory_reset: bool = False
    
    model_config = {"arbitrary_types_allowed": True}
```

### Task 0.8: 实现分布式锁服务
**Files:**
- Create: `backend/src/core/distributed_lock.py`

- [ ] **Step 1: 编写distributed_lock.py代码**
```python
import asyncio
from redis.exceptions import LockError
from src.core.redis_client import RedisClient
from src.config import redis_settings
from src.utils.logger import logger

class DistributedLock:
    """基于 Redis 的分布式锁服务"""
    
    @classmethod
    async def _watchdog(cls, lock, timeout: int, stop_event: asyncio.Event):
        """锁自动续期看门狗"""
        renewal_interval = timeout / 3.0
        while not stop_event.is_set():
            await asyncio.sleep(renewal_interval)
            if not stop_event.is_set():
                try:
                    await lock.extend(timeout)
                except Exception as e:
                    logger.warning(f"分布式锁续期失败: {e}")
                    break

    @classmethod
    async def execute_with_lock(cls, lock_name: str, func, timeout: int = None, *args, **kwargs):
        """使用 redis 内置的健壮分布式锁包装器，并带有看门狗续期机制"""
        timeout = timeout or redis_settings.lock_timeout
        redis_client = RedisClient.get_client()
        lock = redis_client.lock(f"child-dev:lock:{lock_name}", timeout=timeout, blocking_timeout=5)
        try:
            async with lock:
                stop_event = asyncio.Event()
                watchdog_task = asyncio.create_task(cls._watchdog(lock, timeout, stop_event))
                try:
                    return await func(*args, **kwargs)
                finally:
                    stop_event.set()
                    watchdog_task.cancel()
        except LockError:
            logger.error(f"无法获取分布式锁: {lock_name}")
            raise RuntimeError(f"无法获取分布式锁: {lock_name}")
```

- [ ] **Step 2: 测试分布式锁**
```bash
cd backend
uv run python -c "
import asyncio
from src.core.distributed_lock import DistributedLock

async def test():
    async def critical_section():
        print('进入临界区')
        await asyncio.sleep(2)
        print('离开临界区')
        return 'success'
    
    # 测试正常获取锁
    result = await DistributedLock.execute_with_lock('test:lock', critical_section)
    assert result == 'success'
    
    # 测试锁冲突
    task1 = asyncio.create_task(DistributedLock.execute_with_lock('test:lock', critical_section))
    await asyncio.sleep(0.5)
    task2 = asyncio.create_task(DistributedLock.execute_with_lock('test:lock', critical_section))
    
    try:
        await task2
        assert False, '应该抛出锁获取失败异常'
    except RuntimeError as e:
        print('锁冲突测试通过:', str(e))
    
    await task1

asyncio.run(test())
"
```
**Expected:** 锁正常工作，冲突时抛出异常，看门狗续期正常。

### Task 0.9: 实现会话管理器
**Files:**
- Create: `backend/src/core/session_manager.py`

- [ ] **Step 1: 编写session_manager.py代码**
```python
import json
from src.core.redis_client import RedisClient
from src.config import redis_settings
from src.utils.logger import logger

class SessionManager:
    """基于 Redis 的会话管理器"""
    
    @classmethod
    async def save_session(cls, session_id: str, data: dict, ttl: int = None) -> None:
        """保存会话到 Redis Hash"""
        ttl = ttl or redis_settings.session_ttl
        redis_client = RedisClient.get_client()
        pipe = redis_client.pipeline()
        for key, value in data.items():
            pipe.hset(
                f"child-dev:session:{session_id}",
                key,
                json.dumps(value, ensure_ascii=False)
            )
        pipe.expire(f"child-dev:session:{session_id}", ttl)
        await pipe.execute()
        logger.debug(f"会话已保存: {session_id}")
    
    @classmethod
    async def load_session(cls, session_id: str) -> dict | None:
        """从 Redis Hash 加载会话"""
        redis_client = RedisClient.get_client()
        session_data = await redis_client.hgetall(f"child-dev:session:{session_id}")
        if not session_data:
            return None
        
        result = {}
        for key, value in session_data.items():
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                result[key] = value
        return result
    
    @classmethod
    async def update_session_field(cls, session_id: str, field: str, value: any, ttl: int = None) -> None:
        """更新会话单个字段"""
        redis_client = RedisClient.get_client()
        await redis_client.hset(
            f"child-dev:session:{session_id}",
            field,
            json.dumps(value, ensure_ascii=False)
        )
        if ttl:
            await redis_client.expire(f"child-dev:session:{session_id}", ttl)
    
    @classmethod
    async def delete_session(cls, session_id: str) -> None:
        """删除会话"""
        await redis_client.delete(f"child-dev:session:{session_id}")
        logger.debug(f"会话已删除: {session_id}")
```

- [ ] **Step 2: 测试会话管理器**
```bash
cd backend
uv run python -c "
import asyncio
from src.core.session_manager import SessionManager

async def test():
    session_id = 'test_session_123'
    data = {
        'user_id': 'user_123',
        'progress': 50,
        'status': 'running',
        'data': {'key': 'value'}
    }
    
    # 保存会话
    await SessionManager.save_session(session_id, data)
    
    # 加载会话
    loaded = await SessionManager.load_session(session_id)
    assert loaded['user_id'] == 'user_123'
    assert loaded['progress'] == 50
    assert loaded['data']['key'] == 'value'
    
    # 更新字段
    await SessionManager.update_session_field(session_id, 'progress', 100)
    updated = await SessionManager.load_session(session_id)
    assert updated['progress'] == 100
    
    # 删除会话
    await SessionManager.delete_session(session_id)
    deleted = await SessionManager.load_session(session_id)
    assert deleted is None
    
    print('会话管理器测试通过')

asyncio.run(test())
"
```
**Expected:** 会话 CRUD 正常工作。

### Task 0.10: 增强 EventBus 支持 Redis Pub/Sub
**Files:**
- Modify: `backend/src/core/event_bus.py`

- [ ] **Step 1: 修改 event_bus.py 代码**
```python
# 在现有导入基础上添加
import json
import uuid
import redis.asyncio as redis
from src.core.redis_client import RedisClient
from src.config import redis_settings
from src.utils.logger import logger

# 定义事件类型映射（用于动态加载事件）
EVENT_CLASSES = {
    "ConfigChangedEvent": ConfigChangedEvent,
    "ConfigVersionCreatedEvent": ConfigVersionCreatedEvent,
    "ConfigRollbackEvent": ConfigRollbackEvent,
    "ConfigFactoryResetEvent": ConfigFactoryResetEvent,
    # 可以扩展其他事件类型
}

# 修改 EventBus 类
class EventBus:
    """事件总线，支持内存事件 + Redis Pub/Sub跨实例传播"""
    _instance_id: str = str(uuid.uuid4())
    _subscribers: dict[type[BaseEvent], list[callable]] = defaultdict(list)
    _redis_subscriber: redis.client.PubSub | None = None
    
    @classmethod
    def subscribe(cls, event_type: type[BaseEvent], callback: callable) -> None:
        """订阅事件（内存，建议使用weakref或显式unsubscribe防止内存泄漏）"""
        cls._subscribers[event_type].append(callback)
        
    @classmethod
    def unsubscribe(cls, event_type: type[BaseEvent], callback: callable) -> None:
        """显式取消订阅，防止Controller等短生命周期对象内存泄漏"""
        if callback in cls._subscribers[event_type]:
            cls._subscribers[event_type].remove(callback)
    
    @classmethod
    def publish(cls, event: BaseEvent) -> None:
        """发布事件（内存 + Redis Pub/Sub）"""
        # 1. 内存事件传播
        event_type = type(event)
        for callback in cls._subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"事件回调执行失败: {e}")
        
        # 2. Redis Pub/Sub跨实例传播
        if redis_settings.pubsub_enabled:
            try:
                # Pydantic v2 兼容性处理
                event_data = event.model_dump() if hasattr(event, 'model_dump') else event.dict()
                
                payload = {
                    "publisher_id": cls._instance_id,
                    "event_type": event_type.__name__,
                    "event_data": event_data
                }
                asyncio.create_task(
                    RedisClient.get_client().publish(
                        f"child-dev:events:{event_type.__name__}",
                        json.dumps(payload, ensure_ascii=False)
                    )
                )
            except Exception as e:
                logger.warning(f"Redis Pub/Sub 消息发布失败: {e}")
    
    @classmethod
    async def start_redis_subscriber(cls):
        """启动Redis Pub/Sub订阅器（接收其他实例的事件）"""
        if not redis_settings.pubsub_enabled:
            logger.info("Redis Pub/Sub 已禁用，跳过订阅器启动")
            return
        
        try:
            cls._redis_subscriber = RedisClient.get_client().pubsub()
            await cls._redis_subscriber.psubscribe("child-dev:events:*")
            logger.info("Redis Pub/Sub 订阅器已启动")
            
            async for message in cls._redis_subscriber.listen():
                if message["type"] == "pmessage":
                    try:
                        payload = json.loads(message["data"])
                        # 过滤自身发送的消息，防止回声死循环
                        if payload.get("publisher_id") == cls._instance_id:
                            continue
                        
                        event_type_name = payload.get("event_type")
                        event_data = payload.get("event_data", {})
                        
                        # 查找对应的事件类
                        from src.core.events import EVENT_CLASSES  # noqa: F401
                        event_type = EVENT_CLASSES.get(event_type_name)
                        if not event_type:
                            logger.warning(f"未知事件类型: {event_type_name}")
                            continue
                        
                        # 解析事件并分发到内存回调
                        event = event_type(**event_data)
                        for callback in cls._subscribers.get(event_type, []):
                            try:
                                callback(event)
                            except Exception as e:
                                logger.error(f"跨实例事件回调执行失败: {e}")
                                
                    except Exception as e:
                        logger.error(f"Redis Pub/Sub 消息处理失败: {e}")
                        
        except Exception as e:
            logger.error(f"Redis Pub/Sub 订阅器启动失败: {e}")
    
    @classmethod
    async def stop_redis_subscriber(cls):
        """停止Redis订阅器"""
        if cls._redis_subscriber:
            await cls._redis_subscriber.close()
            cls._redis_subscriber = None
            logger.info("Redis Pub/Sub 订阅器已停止")
```

- [ ] **Step 2: 测试跨实例事件传播**
```bash
# 启动两个终端分别运行测试脚本
# 终端1
cd backend
uv run python -c "
import asyncio
from src.core.event_bus import EventBus
from src.core.events import ConfigChangedEvent

async def handle_event(event):
    print(f'收到配置变更事件: {event.version_id}')

async def test():
    EventBus.subscribe(ConfigChangedEvent, handle_event)
    await EventBus.start_redis_subscriber()
    print('订阅器已启动，等待事件...')
    await asyncio.sleep(30)
    await EventBus.stop_redis_subscriber()

asyncio.run(test())
"

# 终端2
cd backend
uv run python -c "
import asyncio
from src.core.event_bus import EventBus
from src.core.events import ConfigChangedEvent

async def test():
    event = ConfigChangedEvent(version_id='v_20260412_120000', changed_keys=['llm.model'])
    EventBus.publish(event)
    print('事件已发布')
    await asyncio.sleep(1)

asyncio.run(test())
"
```
**Expected:** 终端 1 收到终端 2 发布的事件。

### Task 0.11: 实现熔断器模式
**Files:**
- Create: `backend/src/core/circuit_breaker.py`

- [ ] **Step 1: 编写circuit_breaker.py代码**
```python
import time
from enum import Enum
from src.utils.logger import logger

class CircuitState(Enum):
    CLOSED = "closed"       # 正常状态
    OPEN = "open"           # 熔断状态
    HALF_OPEN = "half_open" # 半开状态（试探）

class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass

class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0
    
    async def execute(self, func, *args, **kwargs):
        """执行带熔断保护的方法"""
        if self.state == CircuitState.OPEN:
            # 检查是否可以进入半开状态
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info(f"熔断器 {self.name} 进入半开状态")
            else:
                raise CircuitBreakerOpenError(f"熔断器 {self.name} 处于打开状态，快速失败")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """成功回调"""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info(f"熔断器 {self.name} 恢复正常状态")
    
    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold and self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"熔断器 {self.name} 已打开（连续失败 {self.failure_count} 次），{self.recovery_timeout}秒后尝试恢复")

# 全局熔断器实例
mysql_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="mysql")
redis_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30, name="redis")
```

- [ ] **Step 2: 测试熔断器**
```bash
cd backend
uv run python -c "
import asyncio
from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

async def test():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=2, name='test')
    
    # 测试正常状态
    async def success_func():
        return 'success'
    
    result = await cb.execute(success_func)
    assert result == 'success'
    assert cb.state == 'closed'
    
    # 测试失败触发熔断
    async def fail_func():
        raise RuntimeError('测试错误')
    
    for i in range(2):
        try:
            await cb.execute(fail_func)
        except RuntimeError:
            pass
    
    # 第三次调用应该触发熔断
    try:
        await cb.execute(fail_func)
        assert False, '应该抛出熔断异常'
    except CircuitBreakerOpenError:
        print('熔断触发测试通过')
    
    # 等待恢复时间
    await asyncio.sleep(2.1)
    
    # 半开状态测试成功
    result = await cb.execute(success_func)
    assert result == 'success'
    assert cb.state == 'closed'
    print('熔断器恢复测试通过')

asyncio.run(test())
"
```
**Expected:** 熔断器工作正常，熔断、恢复逻辑符合预期。

### Task 0.12: 改造 CacheService 支持三级缓存
**Files:**
- Modify: `backend/src/service/cache_service.py`

- [ ] **Step 1: 修改 cache_service.py 代码**
```python
# 替换原有 CacheService 实现
import json
import asyncio
import random
import time  # ⚠️ 重要：用于缓存抖动、随机延迟等计算
from typing import Any, Optional
from cachetools import LRUCache
from src.config import redis_settings
from src.core.redis_client import RedisClient
from src.core.circuit_breaker import redis_circuit_breaker, mysql_circuit_breaker
from src.utils.logger import logger

class CacheService:
    """生产级统一缓存服务，支持三级缓存、细粒度失效、穿透/击穿/雪崩防护"""
    
    def __init__(self):
        self.enabled = redis_settings.cache_enabled
        # 内存缓存（热点数据）
        self.memory_cache = LRUCache(maxsize=10000)
        # Redis缓存（分布式全量数据）
        self.redis_client = RedisClient.get_client()
        # 默认TTL
        self.default_ttl = redis_settings.cache_default_ttl
        # 文档哈希到缓存键映射（细粒度失效）
        self.doc_hash_map = dict()
        # 缓存标签映射
        self.tag_map = dict()
    
    async def get(self, key: str, default: Any = None) -> Any:
        """获取缓存，优先内存，再 Redis，最后返回默认"""
        if not self.enabled:
            return default
            
        # 1. 查内存
        if key in self.memory_cache:
            logger.debug(f"内存缓存命中: {key}")
            return self.memory_cache[key]
        
        # 2. 查 Redis（带熔断保护）
        try:
            redis_value = await redis_circuit_breaker.execute(self.redis_client.get, key)
            if redis_value:
                value = json.loads(redis_value)
                self.memory_cache[key] = value  # 回写内存
                logger.debug(f"Redis缓存命中: {key}")
                return value
        except Exception as e:
            logger.warning(f"Redis读取失败，降级: {e}")
        
        return default
    
    async def set(self, key: str, value: Any, expire: int = None, tags: list[str] = None) -> None:
        """写入缓存，同步到 Redis"""
        if not self.enabled:
            return
            
        expire = expire or self.default_ttl
        # 写入内存
        self.memory_cache[key] = value
        # 写入 Redis（忽略错误，不阻塞主流程）
        try:
            await self.redis_client.setex(
                key, 
                expire, 
                json.dumps(value, ensure_ascii=False)
            )
            logger.debug(f"缓存已写入: {key}, TTL: {expire}s")
            
            # 添加标签
            if tags:
                for tag in tags:
                    if tag not in self.tag_map:
                        self.tag_map[tag] = set()
                    self.tag_map[tag].add(key)
                    
        except Exception as e:
            logger.warning(f"Redis写入失败: {e}")
    
    async def set_with_jitter(self, key: str, value: Any, base_ttl: int = None, tags: list[str] = None) -> None:
        """带随机偏移的缓存写入（防雪崩）"""
        base_ttl = base_ttl or self.default_ttl
        # 随机偏移 ±20%
        jitter = int(base_ttl * 0.2)
        actual_ttl = base_ttl + random.randint(-jitter, jitter)
        # 确保 TTL > 0
        actual_ttl = max(60, actual_ttl)
        await self.set(key, value, expire=actual_ttl, tags=tags)
    
    async def delete(self, key: str) -> None:
        """删除缓存"""
        if key in self.memory_cache:
            del self.memory_cache[key]
        
        try:
            await self.redis_client.delete(key)
            logger.debug(f"缓存已删除: {key}")
        except Exception as e:
            logger.warning(f"Redis删除失败: {e}")
    
    async def invalidate_tag(self, tag: str) -> None:
        """按标签批量失效缓存"""
        if tag not in self.tag_map:
            return
        
        keys = self.tag_map[tag]
        if not keys:
            return
        
        # 删除内存缓存
        for key in keys:
            if key in self.memory_cache:
                del self.memory_cache[key]
        
        # 删除Redis缓存
        try:
            await self.redis_client.delete(*keys)
            logger.debug(f"标签 {tag} 关联的 {len(keys)} 个缓存已失效")
        except Exception as e:
            logger.warning(f"Redis批量删除失败: {e}")
        
        del self.tag_map[tag]
    
    async def get_with_protection(self, key: str, query_func, ttl: int = None) -> Any:
        """带穿透防护的缓存查询（空值缓存短TTL）"""
        # 1. 查缓存
        value = await self.get(key)
        if value is not None:
            return value if value != "__NULL__" else None
        
        # 2. 查数据库（带熔断保护）
        result = await mysql_circuit_breaker.execute(query_func)
        
        # 3. 写入缓存（空值也缓存，短TTL防止穿透）
        if result is None:
            await self.set(key, "__NULL__", expire=300)  # 5分钟
        else:
            await self.set_with_jitter(key, result, base_ttl=ttl or self.default_ttl)
        
        return result
    
    async def get_with_lock(self, key: str, query_func, ttl: int = None) -> Any:
        """带互斥锁的缓存查询（防击穿，热点key过期时单线程回源）"""
        # 1. 查缓存
        value = await self.get(key)
        if value is not None:
            return value if value != "__NULL__" else None
        
        # 2. 尝试获取分布式锁
        lock_key = f"lock:cache:{key}"
        acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=10)
        
        if acquired:
            try:
                # 3. 获取锁成功，查询数据库
                result = await mysql_circuit_breaker.execute(query_func)
                # 4. 写入缓存
                if result is None:
                    await self.set(key, "__NULL__", expire=300)
                else:
                    await self.set_with_jitter(key, result, base_ttl=ttl or self.default_ttl)
                return result
            finally:
                await self.redis_client.delete(lock_key)
        else:
            # 4. 未获取锁，等待后重试
            await asyncio.sleep(0.1)
            return await self.get_with_lock(key, query_func, ttl)
    
    async def get_with_logical_expiry(self, key: str, query_func, physical_ttl: int = 86400) -> Any:
        """带逻辑过期的缓存查询（热点数据永不过期，后台异步刷新）"""
        cached = await self.get(key)
        if cached:
            # 检查逻辑过期
            if time.time() < cached.get("logical_expire", 0):
                return cached["value"]
            else:
                # 逻辑过期，异步刷新
                asyncio.create_task(self._refresh_cache(key, query_func, physical_ttl))
                return cached["value"]
        
        # 缓存不存在，同步加载
        return await self._refresh_cache(key, query_func, physical_ttl)
    
    async def _refresh_cache(self, key: str, query_func, physical_ttl: int) -> Any:
        """刷新缓存"""
        result = await mysql_circuit_breaker.execute(query_func)
        data = {
            "value": result,
            "logical_expire": time.time() + self.default_ttl,  # 逻辑过期 1 小时
        }
        await self.set(key, data, expire=physical_ttl)
        return result
    
    async def clear_all(self) -> None:
        """清空所有缓存（谨慎使用）"""
        self.memory_cache.clear()
        try:
            await self.redis_client.flushdb()
            logger.info("所有缓存已清空")
        except Exception as e:
            logger.warning(f"Redis清空失败: {e}")

# 全局实例
cache_service = CacheService()
```

- [ ] **Step 2: 测试三级缓存**
```bash
cd backend
uv run python -c "
import asyncio
from src.service.cache_service import cache_service

async def test():
    key = 'test:cache:key'
    value = {'data': 'test_value'}
    
    # 测试写入和读取
    await cache_service.set(key, value, expire=60)
    cached = await cache_service.get(key)
    assert cached == value
    print('缓存读写测试通过')
    
    # 测试穿透防护
    async def query_none():
        return None
    
    result = await cache_service.get_with_protection('test:none', query_none)
    assert result is None
    # 第二次读取应该命中空值缓存
    result2 = await cache_service.get_with_protection('test:none', query_none)
    assert result2 is None
    print('穿透防护测试通过')
    
    # 测试删除
    await cache_service.delete(key)
    deleted = await cache_service.get(key)
    assert deleted is None
    print('缓存删除测试通过')

asyncio.run(test())
"
```
**Expected:** 缓存功能正常，防护机制生效。

### Task 0.13: 更新配置示例和项目文档
**Files:**
- Modify: `backend/.env.dev.example`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- [ ] **Step 1: 添加MySQL和Redis配置到.env.dev.example**
```env
# MySQL Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=child_development
MYSQL_POOL_SIZE=10
MYSQL_MAX_OVERFLOW=20
MYSQL_POOL_TIMEOUT=30
MYSQL_POOL_RECYCLE=1800
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your_password
REDIS_MAX_CONNECTIONS=20
REDIS_CACHE_DEFAULT_TTL=3600
REDIS_LOCK_TIMEOUT=30
REDIS_SESSION_TTL=86400
REDIS_PUBSUB_ENABLED=true
```
- [ ] **Step 2: 更新AGENTS.md架构部分**
在架构总览的基础设施层和数据层更新MySQL和Redis相关内容，匹配新的架构设计。
- [ ] **Step 3: 更新CLAUDE.md技术栈和项目结构**
添加MySQL、Redis、SQLAlchemy、Alembic到技术栈，更新项目结构中的新增文件说明。

### Task 0.14: 集成布隆过滤器（防缓存穿透）
**Files:**
- Create: `backend/src/core/bloom_filter.py`

- [ ] **Step 1: 创建布隆过滤器服务**
```python
from pybloom_live import BloomFilter
from src.core.redis_client import RedisClient
from src.utils.logger import logger

class BloomFilterService:
    """布隆过滤器服务，用于快速判断 ID 是否存在"""
    
    def __init__(self, capacity: int = 100000, error_rate: float = 0.01):
        self.bloom = BloomFilter(capacity=capacity, error_rate=error_rate)
        self._loaded = False
    
    async def load_ids(self, ids: list[str]) -> None:
        """加载 ID 到布隆过滤器"""
        for id in ids:
            self.bloom.add(id)
        self._loaded = True
        logger.info(f"布隆过滤器已加载 {len(ids)} 个 ID")
    
    def might_contain(self, item_id: str) -> bool:
        """快速判断 ID 是否可能存在"""
        if not self._loaded:
            return True  # 未加载时放行
        return item_id in self.bloom
    
    def add(self, item_id: str) -> None:
        """添加单个 ID"""
        self.bloom.add(item_id)

# 全局单例
bloom_filter_service = BloomFilterService()
```

### Task 0.15: 连接池监控 API
**Files:**
- Modify: `backend/src/core/database.py`

- [ ] **Step 1: 添加连接池状态检查**
```python
# backend/src/core/database.py
async def get_pool_status() -> dict:
    """获取连接池当前状态"""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalidated": pool.invalidated(),
    }
```

- [ ] **Step 2: 添加告警阈值检查**
```python
async def check_pool_health() -> dict:
    """检查连接池健康状态"""
    status = await get_pool_status()
    alerts = []
    
    pool_size = status["pool_size"]
    if pool_size > 0:
        usage_rate = status["checked_out"] / pool_size
        if usage_rate > 0.8:
            alerts.append(f"连接池使用率过高: {usage_rate:.0%}")
    
    if status["overflow"] > 16:  # max_overflow * 0.8
        alerts.append(f"溢出连接过多: {status['overflow']}")
    
    return {
        "status": "healthy" if not alerts else "warning",
        "alerts": alerts,
        **status,
    }
```

### Phase 0 完成验证
- [ ] 运行项目所有单元测试，确保基础设施层功能正常
- [ ] 运行后端服务，验证MySQL和Redis连接正常
- [ ] 执行`alembic current`确认所有迁移已应用
- [ ] 验证缓存、分布式锁、事件总线等核心组件功能正常
---
