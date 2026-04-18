# 00 - 项目概览

> **本文档包含**: 项目背景、核心目标、验收标准、整体架构、依赖管理

---

## 项目背景

当前系统存在以下核心问题：

**后端接口返回格式不统一**
- 部分接口直接返回字典：`{"status": "ok"}`、`{"tasks": [...]}`
- 部分接口使用 Pydantic `response_model` 返回结构化对象
- 成功响应没有统一包装，前端难以统一处理

**异常处理混乱**
- 大量使用 `HTTPException(status_code, detail)` 直接抛出
- 错误信息格式不一致：英文与中文混用
- 没有全局异常处理器，每个 Controller 自行处理异常

**前端错误处理薄弱**
- 拦截器仅打印日志，未做统一错误提示
- 缺乏统一的错误码映射
- 没有用户友好的错误提示机制

**代码结构问题**
- Pydantic 实体类散落在 controller/service/core/model/models 中
- 40+ 个类超过 200 行，违反单一职责
- 280+ 处重复代码（Session 管理、错误处理、序列化等）

---

## 核心目标

| # | 目标 | 验收标准 | 所属 Phase |
|---|------|---------|-----------|
| 1 | 实体类集中管理 | 所有 Pydantic 类迁移至 `schemas/`，按业务模块组织，0 处遗留 | Phase 1 |
| 2 | 类职责拆分 | 40+ 个超长类拆分，单类 ≤ 200 行，门面模式对外 | Phase 2 |
| 3 | 统一响应格式 | 所有接口返回统一包装，错误返回标准化 | Phase 3 |
| 4 | 消除冗余代码 | 280+ 处重复代码提取至 `utils/` | Phase 4 |
| 5 | 规范代码引用 | 解决 model/models 冲突，补充 `__init__.py`，import 分组 | Phase 5 |
| 6 | 前端架构重构 | 采用 FSD Lite，页面与逻辑分离，统一 API 调用 | Phase 6 |
| 7 | 错误码与后端实现 | 建立统一错误码字典，全局异常处理器注册 | Phase 7 |

---

## 验收标准总览

### Phase 1 验收
- `backend/src/schemas/` 目录结构正确创建
- 所有 Pydantic 实体类从 controller/service/core/model/models 迁移完成
- 按业务模块组织：`assessment.py`, `rag.py`, `test_case.py`, `config.py`, `prompt.py`, `monitoring.py`, `events.py`, `common.py`
- 导入规范统一：`from src.schemas import Xxx`
- 0 处 `class xxx(BaseModel)` 遗留在 service/controller/core 中

### Phase 2 验收
- RagTestManager (1799 行) 拆分为 8 个子服务 + 1 个门面
- RetrievalService (1060 行) 拆分为 5 个子服务 + 1 个门面
- MetadataProcessor (925 行) 拆分为 7 个子服务 + 1 个门面
- DocumentIngestionService (637 行) 拆分为 5 个子服务 + 1 个门面
- IndexManagerService (574 行) 拆分为 4 个子服务 + 1 个门面
- 所有单类 ≤ 200 行
- 对外 API 保持兼容

### Phase 3 验收
- `APIResponse` 模型定义正确
- 成功响应：`{code: 0, message: "success", data: {...}}`
- 错误响应：`{code, message, error_code, details, trace_id?}`
- 分页数据格式正确
- HTTP 状态码与业务码映射正确

### Phase 4 验收
- `utils/db.py`：消除 26 处 Session 重复
- `utils/response.py`：消除 100+ 处错误处理重复
- `utils/serializers.py`：消除 30+ 处序列化重复
- `utils/file_ops.py`：消除 70+ 处文件操作重复
- `utils/time_utils.py`：消除 50+ 处时间处理重复
- `utils/crypto.py`、`utils/id_generator.py`、`utils/auth_helpers.py` 创建

### Phase 5 验收
- `src/model/` 重命名为 `src/schemas/`
- 31 处引用全部更新
- `controller/`, `service/`, `core/`, `utils/` 补充 `__init__.py`
- Import 分组：stdlib → third-party → local
- 循环导入解决
- 函数内冗余 import 移至顶部
- `config/__init__.py` (614 行) 拆分为 4 个文件

### Phase 6 验收
- 前端采用 FSD Lite 架构：pages → widgets → features → entities → shared
- 页面与逻辑分离（RunListPage 217 行 → hook + component + page）
- `configStore.ts` (369 行) 拆分
- 统一 API 调用模式
- 消除 95+ 处 `message.*` 重复
- 统一 SSE 实现
- 类型定义统一，无循环 re-export
- ESLint 规则与路径别名配置

### Phase 7 验收
- 错误码分段定义：10000-10999 通用，11000-16999 各模块
- 通用错误码 10 个定义完整
- 各模块错误码定义完整
- `AppException` 基类及子类定义
- 全局异常处理器注册
- ResponseWrapperMiddleware 注册
- 前端错误码映射表

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React + FSD Lite)                  │
│  pages → widgets → features → entities → shared              │
│  统一错误提示 + 错误码映射 + React Query                      │
└──────────────────────────┬────────────────────────────────────┘
                           │ REST API + SSE
┌──────────────────────────▼────────────────────────────────────┐
│                      后端 (FastAPI)                            │
│  Controller → Service (拆分后) → schemas/ (统一实体类)         │
│  全局异常处理器 → ResponseWrapperMiddleware → utils/ (工具)    │
└──────────────────────────┬────────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────────┐
│                      数据层                                    │
│  MySQL 5.7 (SQLAlchemy 2.0) → Redis 7.0                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 依赖管理

### 新增依赖

```toml
# Phase 5: Import 排序工具
isort = "^5.13.0"

# Phase 5: Lint 检查
ruff = "^0.3.0"
```

---

**文档索引**: 
- 下一步: [Phase 1 总览](./phases/phase-1/00-overview.md)
- 需求映射: [DOCUMENT_STRUCTURE.md](./DOCUMENT_STRUCTURE.md)
- 进度追踪: [PROGRESS.md](./PROGRESS.md)
