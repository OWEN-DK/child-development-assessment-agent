# RAG Platform - AI 上下文规则

> 从根目录 CLAUDE.md 派生，去除 backend/ 引用，适配 rag-platform 独立部署。

---

## 项目定位

**RAG Platform** 是一个独立部署的 RAG（检索增强生成）平台，提供：
- 多业务域聚合搜索（跨域知识融合）
- 多知识库管理（独立向量存储、分块策略、Embedding 模型）
- 可视化管道编辑器（React Flow 画布式配置）
- 双层权限控制（库级别 × 文档级别）
- RAG 评估与调优闭环

**不依赖 `backend/`**，完全独立运行。

---

## 技术栈

- **后端**: Python 3.13, FastAPI, SQLAlchemy 2.0 (MySQL 5.7), Redis 7.0
- **前端**: React 19, Vite 6, Ant Design 6, @xyflow/react (React Flow), Zustand 5
- **向量库**: Chroma (默认), Elasticsearch (可选), Milvus (可选)
- **编排**: LangGraph, LangChain, LlamaIndex
- **包管理**: uv (后端), npm (前端)

---

## 目录结构

```
rag-platform/
├── backend/
│   ├── src/
│   │   ├── api/           # 统一响应、SSE
│   │   ├── config/        # 配置模块
│   │   ├── controller/    # API 控制器
│   │   │   ├── auth/      # 认证/租户/用户/角色
│   │   │   └── health_controller.py
│   │   ├── core/          # 核心业务
│   │   │   ├── auth/      # JWT、RBAC、密码、异常
│   │   │   ├── config/    # 配置缓存
│   │   │   ├── llm/       # LLM 工厂与适配器
│   │   │   ├── tracing/   # 全链路追踪
│   │   │   └── ...
│   │   ├── middleware/     # 中间件
│   │   ├── models/        # SQLAlchemy 模型
│   │   ├── repository/    # 数据访问层
│   │   ├── schemas/       # Pydantic 实体类
│   │   ├── service/       # 业务服务层
│   │   └── utils/         # 工具函数
│   ├── pyproject.toml
│   ├── .env
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/           # API 客户端
│   │   ├── app/           # 根组件
│   │   ├── components/    # 通用组件
│   │   ├── entities/      # 业务实体类型
│   │   ├── features/      # 业务特性
│   │   ├── pages/         # 独立页面
│   │   ├── router/        # 路由配置
│   │   └── shared/        # 共享层
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── docker-compose.dev.yml
└── init.sql              # 31 张表 DDL
```

---

## 核心约束

1. **前后端解耦**: 后端仅提供 API，不包含前端路由逻辑
2. **配置管理**: 所有可配置参数定义在 MySQL，`.env` 仅兜底基础设施凭证
3. **实体类集中管理**: 所有 Pydantic 实体类在 `schemas/` 目录
4. **类职责拆分**: 单类不超过 500 行
5. **统一响应格式**: `{code: 0, message: "success", data: {...}}`
6. **零迁移原则**: 直接修改，不保留兼容层
7. **全中文注释**: 所有代码注释使用中文
8. **租户隔离**: 所有数据访问通过 Repository 基类自动注入 `tenant_id`

---

## 常用命令

- **后端**: `cd backend && uv sync && uv run uvicorn src.server:create_app --host 0.0.0.0 --port 51002 --factory`
- **前端**: `cd frontend && npm install && npm run dev`
- **Docker**: `docker compose up -d`

---

## 权限体系

- **超管**: 不属于任何租户，JWT 中无 `tenant_id`
- **租户用户**: JWT 携带 `tenant_id` + `roles`
- **内置角色**: admin（全部权限）、editor（读写）、viewer（只读）
- **God Mode**: 超管进入租户上下文，30min 超时，Redis 并发限制

---

## API 路由前缀

| 前缀 | 用途 | 认证要求 |
|------|------|---------|
| `/health` | 健康检查 | 无 |
| `/metrics` | Prometheus 指标 | 无 |
| `/api/v1/auth` | 认证（登录/刷新） | 无（login/refresh 豁免） |
| `/api/v1/admin/tenants` | 租户管理 | 超管 |
| `/api/v1/users` | 用户管理 | 租户用户 |
| `/api/v1/roles` | 角色管理 | 租户用户 |
