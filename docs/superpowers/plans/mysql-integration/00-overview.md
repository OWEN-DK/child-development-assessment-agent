# 项目概览与文件结构变更

## 📋 文件结构变更总览

### 新增文件

| 文件路径 | 职责 |
|---------|------|
| `backend/src/config/modules/database.py` | MySQL 数据库配置 |
| `backend/src/config/modules/redis.py` | Redis 缓存配置 |
| `backend/src/core/database.py` | 数据库连接池、ORM 基类、慢查询检测 |
| `backend/src/core/redis_client.py` | Redis 异步客户端单例 |
| `backend/src/core/distributed_lock.py` | 分布式锁服务（带看门狗续期） |
| `backend/src/core/session_manager.py` | 会话管理器（Redis Hash 存储） |
| `backend/src/core/circuit_breaker.py` | 熔断器实现（故障降级） |
| `backend/src/models/config.py` | 配置版本、审计日志 SQLAlchemy 模型 |
| `backend/src/models/test_case.py` | 测试用例、草稿、测试集、运行结果模型 |
| `backend/src/models/document.py` | 源文档、导入记录模型 |
| `backend/src/models/monitor.py` | A/B 测试指标、LLM 调用日志模型 |
| `backend/src/config/core/repository.py` | MySQL 配置仓库实现 |
| `backend/src/core/llm/base.py` | LLM 服务统一接口、消息结构 |
| `backend/src/core/llm/adapters/langchain.py` | LangChain LLM 适配器 |
| `backend/src/core/llm/adapters/llamaindex.py` | LlamaIndex LLM 适配器 |
| `backend/src/core/llm/factory.py` | LLM 服务工厂（按场景动态生成实例） |
| `backend/src/core/pipeline/orchestrator.py` | RAG 查询流水线编排器 |
| `backend/src/core/prompt/manager.py` | 提示词管理器（MySQL 存储+Redis 缓存） |
| `backend/src/core/monitor/llm_monitor.py` | LLM 调用监控服务 |
| `backend/alembic.ini` | Alembic 迁移配置 |
| `backend/alembic/env.py` | Alembic 环境配置 |
| `backend/alembic/versions/*.py` | 数据库迁移脚本 |

### 修改文件

| 文件路径 | 变更内容 |
|---------|----------|
| `backend/src/config/__init__.py` | 新增 database、redis 配置聚合 |
| `backend/src/config/core/manager.py` | 改造 ConfigManager 使用 MySQL 存储+Redis 缓存 |
| `backend/src/service/cache_service.py` | 启用 Redis，实现三级缓存、穿透/击穿/雪崩防护 |
| `backend/src/core/event_bus.py` | 增强支持 Redis Pub/Sub 跨实例事件传播 |
| `backend/src/service/rag_test_manager.py` | 改造使用 MySQL 存储、分布式锁、批量写入 |
| `backend/src/service/retrieval_service.py` | 重构为 YAML 驱动的声明式流水线 |
| `backend/src/controller/rag_test_controller.py` | 新增批量执行、SSE 进度推送接口 |
| `backend/src/server.py` | 注册新 API、启动 Redis 订阅协程 |
| `backend/pyproject.toml` | 新增 SQLAlchemy、Alembic、aiomysql、redis 等依赖 |
| `backend/.env.dev` | 新增 MYSQL、REDIS 配置项 |
| `AGENTS.md` | 更新架构图、数据存储策略、核心模块说明 |
| `CLAUDE.md` | 更新技术栈、项目结构、核心功能说明 |

### 删除文件（迁移完成后）

```
app_data/data/configs/
app_data/storage/test_cases.json
app_data/storage/test_sets/
app_data/storage/test_case_drafts/
app_data/storage/test_runs/
app_data/storage/source_documents/
app_data/storage/document_store.json
app_data/storage/ab_test_metrics.json
app_data/cache/
```

---

## 🏗️ 架构说明

### 数据存储策略

- **MySQL 5.7**: 作为唯一持久化数据源，存储所有结构化数据
  - 配置版本和审计日志
  - 测试用例、草稿、测试集
  - 测试运行结果
  - LLM 调用日志
  - A/B 测试指标
  - 源文档元数据

- **Redis 7.0**: 作为全面加速层，承担四大角色
  - **分布式缓存**: 三级缓存（内存 LRU → Redis → MySQL）
  - **消息队列**: Redis Pub/Sub 实现跨实例事件传播
  - **分布式锁**: 基于 Redis 的分布式锁服务（带看门狗续期）
  - **会话存储**: Redis Hash 存储会话数据

- **Chroma**: 保持向量存储功能不变

- **JSON 文件**: 业务规则/静态数据保持不变

### 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端层 (React 19)                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  API 网关层 (FastAPI)                     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  业务服务层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ ConfigSvc   │  │  RAG Svc    │  │  Cache Svc  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  基础设施层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ EventBus    │  │  Dist Lock  │  │  Circuit    │     │
│  │             │  │             │  │  Breaker    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  数据持久化层                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   MySQL     │  │    Redis    │  │   Chroma    │     │
│  │  (主存储)    │  │  (缓存加速)  │  │  (向量库)   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 依赖管理

### 核心依赖

所有依赖已在 `backend/pyproject.toml` 中配置：

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

### 安装命令

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/backend
uv sync
```

---

## 🔧 配置管理

### 环境变量

所有 MySQL 和 Redis 配置项已在 `backend/.env.dev` 中定义：

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

---

## 📝 类型定义说明

### SQLAlchemy 模型类型规范

所有 JSON 和 List 字段已统一类型定义：

```python
from typing import Any, Optional, Dict, List
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

# ✅ 正确的类型定义
config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
expected_knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON)
professional_terms: Mapped[list[str] | None] = mapped_column(JSON)
relevance_scores: Mapped[dict[str, float] | None] = mapped_column(JSON)

# ❌ 避免使用不精确的类型
# config_snapshot: Mapped[dict] = mapped_column(JSON)  # 不推荐
# expected_knowledge_ids: Mapped[list | None] = mapped_column(JSON)  # 不推荐
```

---

## 📖 下一步

继续查看各个 Phase 的详细实施方案：

1. [Phase 0: MySQL + Redis 基础设施搭建](./01-phase-0-infrastructure.md)
2. [Phase 1: 配置系统 MySQL 迁移](./02-phase-1-config-migration.md)
3. [Phase 2: LLM 服务工厂重构](./03-phase-2-llm-factory.md)
4. [Phase 3: RAG 查询流水线重构](./04-phase-3-rag-pipeline.md)
5. [Phase 4: RAG 测试框架迁移](./05-phase-4-test-framework.md)
6. [Phase 5: LLM 监控系统](./06-phase-5-monitoring.md)
7. [Phase 6: 提示词管理系统](./07-phase-6-prompt-management.md)
8. [Phase 7: 前端集成测试](./08-phase-7-frontend-integration.md)
9. [Phase 8: 部署与上线](./09-phase-8-deployment.md)

---

**返回索引：** [README.md](./README.md)
