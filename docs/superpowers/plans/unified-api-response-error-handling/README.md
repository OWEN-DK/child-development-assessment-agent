# 统一接口返回与异常处理重构实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一后端接口返回格式、建立全局异常处理机制、集中管理实体类、拆分超长类、消除冗余代码、规范前端架构、对齐前后端错误码。

**Architecture:** 采用分阶段原子变更策略，按 Phase 1→7 顺序推进，每个 Phase 内部按需求点拆分为原子文件，一个文件只对应一个需求点。

**Tech Stack:** Python 3.13, FastAPI 0.135.1, SQLAlchemy 2.0 (MySQL 5.7), Pydantic, React 19.2.4, TypeScript 5.3, Ant Design 6.3.2, Zustand 5

**需求来源:** [docs/specs/unified-api-response-and-error-handling.md](../../specs/unified-api-response-and-error-handling.md)

---

## ⚠️ 核心实施规则（必须遵守，不可偏离）

> **以下规则整合自 CLAUDE.md 与 spec 文档，适用于本方案的所有 Phase 和所有文件，实施时不得遗漏、跳过或偏离。**

### 🚫 绝对禁止

| # | 规则 | 来源 | 说明 |
|---|------|------|------|
| F1 | **禁止在 service/controller/core 中定义 BaseModel** | CLAUDE.md | 所有 Pydantic 实体类必须统一放在 `backend/src/schemas/` |
| F2 | **禁止单类超过 200 行** | CLAUDE.md | 违反则必须拆分，使用门面模式协调子服务 |
| F3 | **禁止重复定义相同功能函数** | CLAUDE.md | 必须提取至 `utils/` 目录下的对应工具模块 |
| F4 | **禁止直接使用 HTTPException** | CLAUDE.md | 所有业务异常必须继承 `AppException` |
| F5 | **禁止代码硬编码** | CLAUDE.md | 所有可配置参数定义在数据库或集中式配置中心 |
| F6 | **禁止跳过测试直接生成业务代码** | CLAUDE.md | 必须先写测试，确认失败后再实现（SDD+TDD） |
| F7 | **禁止跨 feature 导入** | spec | 前端禁止从其他 feature 或 pages 导入 |
| F8 | **禁止页面组件直接调用 API** | spec | 所有 API 调用通过 entities/*/api.ts 或 features/*/hooks/ 封装 |

### ✅ 必须做到

| # | 规则 | 来源 | 说明 |
|---|------|------|------|
| R1 | **统一响应格式** | spec | 成功：`{code: 0, message: "success", data: {...}}`；错误：`{code, message, error_code, details}` |
| R2 | **保持 HTTP 语义** | spec | 200 成功、4xx 客户端错误、5xx 服务端错误 |
| R3 | **错误码双字段** | spec | `code`（数字）+ `error_code`（字符串大写蛇形） |
| R4 | **代码注释全中文** | CLAUDE.md | Python 和前端代码注释必须全中文 |
| R5 | **一个文件只对应一个需求点** | 本计划 | 如果有多个需求点就拆分为多个文件，不得合并 |
| R6 | **每一块代码都要写进方案** | 本计划 | 实施方案必须包含完整的代码实现，不得只写伪代码或描述 |
| R7 | **需求点与实现一一对应** | 本计划 | 不得遗漏和跳过任何需求点 |
| R8 | **Import 分组排序** | spec | stdlib → third-party → local，每组空行分隔，字母排序 |

### 📋 开发约束

| # | 约束 | 来源 | 落地要求 |
|---|------|------|---------|
| C1 | **前后端解耦** | CLAUDE.md | 后端仅提供 API 服务（及 SPA 回退路由） |
| C2 | **依赖管理** | CLAUDE.md | 后端 `pyproject.toml` + `uv add`；前端 `package.json` |
| C3 | **Enum 插入约束** | CLAUDE.md | 使用 SQLAlchemy Enum 类成员，不传字符串 |
| C4 | **Enum 映射规则** | CLAUDE.md | 显式传递 `values_callable=lambda obj: [e.value for e in obj]` |
| C5 | **SSE 推送异常** | CLAUDE.md | SSE 结果必须被 `jsonable_encoder` 处理 |
| C6 | **实体类命名规范** | spec | Request DTO: `{Entity}{Action}Request`；Response DTO: `{Entity}Response` |
| C7 | **FSD Lite 架构** | spec | 前端采用 pages → widgets → features → entities → shared 分层 |

---

## 📋 实施原则

1. **原子变更**：每个 Phase 内部必须一次性完成，避免中间状态不可用
2. **配置驱动**：所有权重、阈值、回滚开关通过配置管理，禁止硬编码
3. **测试驱动**：每个 Phase 必须以测试通过为验收标准
4. **零历史包袱**：项目未上线，全新设计，不写兼容代码
5. **SDD+TDD**：规范先行 → 测试生成（确认失败）→ 精准实现 → 循环推进
6. **一文件一需求点**：每个实施文件只对应一个需求点，多需求点必须拆分
7. **代码完整**：实施方案必须包含完整的代码实现，不得只写伪代码或描述

---

## 📖 文档导航与需求点映射

> **本计划将 spec 文档中的所有需求点拆分为原子实施文件，一个文件对应一个需求点，不得遗漏和跳过。**

### 入口文档

| 文档 | 说明 |
|------|------|
| [README.md](./README.md) | 主索引文件（入口） |
| [DOCUMENT_STRUCTURE.md](./DOCUMENT_STRUCTURE.md) | 文档结构说明 + 需求点与实施文件映射表 |
| [PROGRESS.md](./PROGRESS.md) | 实施进度追踪（按需求点 checkbox） |

### Phase 总览文档

| 文档 | 说明 | 需求点数量 |
|------|------|-----------|
| [00-overview.md](./00-overview.md) | 项目概览：背景目标、实施原则、验收标准、架构 | - |
| [01-phase-1-overview.md](./phases/phase-1/00-overview.md) | Phase 1: 实体类集中管理 | 8 个需求点 |
| [02-phase-2-overview.md](./phases/phase-2/00-overview.md) | Phase 2: 类职责拆分 | 7 个需求点 |
| [03-phase-3-overview.md](./phases/phase-3/00-overview.md) | Phase 3: 统一响应格式 | 5 个需求点 |
| [04-phase-4-overview.md](./phases/phase-4/00-overview.md) | Phase 4: 冗余代码消除 | 8 个需求点 |
| [05-phase-5-overview.md](./phases/phase-5/00-overview.md) | Phase 5: 代码引用规范 | 6 个需求点 |
| [06-phase-6-overview.md](./phases/phase-6/00-overview.md) | Phase 6: 前端架构重构 | 8 个需求点 |
| [07-phase-7-overview.md](./phases/phase-7/00-overview.md) | Phase 7: 错误码与后端实现 | 6 个需求点 |

### 需求点与实施文件映射

> **详细映射表见 [`DOCUMENT_STRUCTURE.md`](./DOCUMENT_STRUCTURE.md)**

每个需求点对应一个实施文件，文件命名规则：`{phase编号}-{需求点序号}-{需求点名称}.md`

示例：
- `phases/phase-1/01-schemas-directory-structure.md` — Phase 1 第 1 个需求点：schemas 目录结构创建
- `phases/phase-2/01-rag-test-manager-split.md` — Phase 2 第 1 个需求点：RagTestManager 拆分
- `phases/phase-3/01-api-response-model.md` — Phase 3 第 1 个需求点：APIResponse 模型定义

---

## 🎯 项目背景与目标

### 背景

当前系统存在以下问题：
- **后端接口返回格式不统一**：部分直接返回字典，部分使用 Pydantic，成功响应没有统一包装
- **异常处理混乱**：大量使用 HTTPException，错误信息格式不一致，没有全局异常处理器
- **前端错误处理薄弱**：拦截器仅打印日志，缺乏统一错误码映射和用户友好提示
- **实体类散落各处**：Pydantic 实体类散落在 controller/service/core/model/models 中
- **超长类违反 SRP**：40+ 个类超过 200 行，RagTestManager 达 1799 行
- **重复代码泛滥**：280+ 处重复代码（Session 管理、错误处理、序列化等）

### 核心目标

| # | 目标 | 验收标准 | 所属 Phase |
|---|------|---------|-----------|
| 1 | 实体类集中管理 | 所有 Pydantic 类迁移至 `schemas/`，按业务模块组织 | Phase 1 |
| 2 | 类职责拆分 | 40+ 个超长类拆分，单类 ≤ 200 行，门面模式对外 | Phase 2 |
| 3 | 统一响应格式 | 所有接口返回 `{code, message, data}`，错误返回 `{code, message, error_code, details}` | Phase 3 |
| 4 | 消除冗余代码 | 280+ 处重复代码提取至 `utils/`，消除重复 | Phase 4 |
| 5 | 规范代码引用 | 解决 model/models 冲突，补充 `__init__.py`，统一 import 分组 | Phase 5 |
| 6 | 前端架构重构 | 采用 FSD Lite，页面与逻辑分离，统一 API 调用模式 | Phase 6 |
| 7 | 错误码与后端实现 | 建立统一错误码字典，实现全局异常处理器，注册中间件 | Phase 7 |

---

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React + FSD Lite)                  │
│  pages → widgets → features → entities → shared              │
│  统一错误提示 + 错误码映射 + React Query 管理状态             │
└──────────────────────────┬────────────────────────────────────┘
                           │ REST API (统一响应格式)
┌──────────────────────────▼────────────────────────────────────┐
│                      后端 (FastAPI)                            │
│  Controller 层 → Service 层 (拆分后 ≤ 200 行)                 │
│  全局异常处理器 → ResponseWrapperMiddleware                    │
│  schemas/ (统一实体类) → utils/ (消除重复代码)                 │
└──────────────────────────┬────────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────────┐
│                      数据层                                    │
│  MySQL 5.7 (SQLAlchemy 2.0) → Redis 7.0                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 依赖管理

### 新增依赖

```toml
# Phase 5: Import 排序工具
isort = "^5.13.0"

# Phase 5: Lint 检查
ruff = "^0.3.0"
```

---

## 📖 下一步

继续查看各个 Phase 的详细实施方案：

1. [Phase 1: 实体类集中管理](./phases/phase-1/00-overview.md) — 8 个需求点
2. [Phase 2: 类职责拆分](./phases/phase-2/00-overview.md) — 7 个需求点
3. [Phase 3: 统一响应格式](./phases/phase-3/00-overview.md) — 5 个需求点
4. [Phase 4: 冗余代码消除](./phases/phase-4/00-overview.md) — 8 个需求点
5. [Phase 5: 代码引用规范](./phases/phase-5/00-overview.md) — 6 个需求点
6. [Phase 6: 前端架构重构](./phases/phase-6/00-overview.md) — 8 个需求点
7. [Phase 7: 错误码与后端实现](./phases/phase-7/00-overview.md) — 6 个需求点

---

**最后更新：** 2026-04-18
**文档版本：** 0.1 (初始框架)
**维护者：** AI Assistant
