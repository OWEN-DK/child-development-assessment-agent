# RAG 评估平台重构实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 RAG 评估平台，修复核心工作流断裂问题，建立以测试集为核心的诊断-调优-复测闭环系统，实现 6 层校验引擎、推荐模式面板、配置/提示词版本管理、提示词管理重构、配置管理优化。

**Architecture:** 采用分阶段原子变更策略，按 Phase 0→8 顺序推进，每个 Phase 内部按需求点拆分为原子文件，一个文件只对应一个需求点。

**Tech Stack:** Python 3.13, LangGraph 1.1.0, LlamaIndex 0.14.16, Chroma, FastAPI 0.135.1, SQLAlchemy 2.0 (MySQL 5.7), Redis 7.0, React 19.2.4, Vite 6.4, Ant Design 6.3.2, Zustand 5, React Router 7

**需求来源:** [docs/superpowers/specs/2026-04-16-rag-evaluation-page-refactoring/](../../specs/2026-04-16-rag-evaluation-page-refactoring/) (v15.0)

---

## ⚠️ 核心实施规则（必须遵守，不可偏离）

> **以下规则整合自 CLAUDE.md 与 spec 文档，适用于本方案的所有 Phase 和所有文件，实施时不得遗漏、跳过或偏离。**

### 🚫 绝对禁止

| # | 规则 | 来源 | 说明 |
|---|------|------|------|
| F1 | **禁止任何兼容方案** | CLAUDE.md + spec | 不写兼容代码、不写迁移脚本、不做双版本并行、不加 `@deprecated` 标记 |
| F2 | **禁止后续计划** | spec | 所有功能必须在本方案范围内给出完整实现，不拆分到"后续版本" |
| F3 | **禁止替用户决策** | spec | 推荐只是参考，不能自动应用配置；禁止"一键优化"式傻瓜操作 |
| F4 | **禁止隐藏决策依据** | spec | 每个推荐必须解释"为什么改"，用户必须能看到改动前后的差异 |
| F5 | **禁止跳过对比环节** | spec | 用户必须能看到改动前后的差异（配置值 diff、提示词内容 diff） |
| F6 | **禁止省略影响分析** | spec | 用户需要知道"改了会有什么后果"（预期指标变化、风险警告） |
| F7 | **禁止代码硬编码** | CLAUDE.md | 所有可配置参数定义在数据库或集中式配置中心 |
| F8 | **禁止直接写入本地 JSON 文件** | CLAUDE.md | 动态编辑必须使用 MySQL 共享存储 |
| F9 | **禁止跳过测试直接生成业务代码** | CLAUDE.md | 必须先写测试，确认失败后再实现（SDD+TDD） |

### ✅ 必须做到

| # | 规则 | 来源 | 说明 |
|---|------|------|------|
| R1 | **所有修改在需求文档中列出** | spec | 每个变更必须标注：修改位置（文件路径）、修改内容、删除的老代码 |
| R2 | **老代码直接删除** | spec | 实施计划中明确标注"删除 XXX"，不留残留 |
| R3 | **需求完整闭环** | spec | 不拆分到"后续版本"，所有需求一次性给全 |
| R4 | **必须展示前后对比** | spec | 配置值 diff、提示词内容 diff |
| R5 | **必须说明改动原因** | spec | 触发条件、指标短板、Bad Case 分析 |
| R6 | **必须预览改动影响** | spec | 预期指标变化、风险警告、历史参考 |
| R7 | **必须让用户手动确认** | spec | 采纳 → 审查 → 保存为新版本，三步分离 |
| R8 | **必须支持回溯** | spec | 每次修改留版本记录，可回滚 |
| R9 | **代码注释全中文** | CLAUDE.md | Python 和前端代码注释必须全中文 |
| R10 | **一个文件只对应一个需求点** | 本计划 | 如果有多个需求点就拆分为多个文件，不得合并 |
| R11 | **每一块代码都要写进方案** | 本计划 | 实施方案必须包含完整的代码实现，不得只写伪代码或描述 |
| R12 | **需求点与实现一一对应** | 本计划 | 不得遗漏和跳过任何需求点 |

### 📋 开发约束

| # | 约束 | 来源 | 落地要求 |
|---|------|------|---------|
| C1 | **前后端解耦** | CLAUDE.md | 后端仅提供 API 服务（及 SPA 回退路由），不包含任何前端业务路由逻辑 |
| C2 | **依赖管理** | CLAUDE.md | 后端依赖只允许在 `pyproject.toml` 中声明，使用 `uv add`；前端使用 `package.json` |
| C3 | **Enum 插入约束** | CLAUDE.md | 向 MySQL 插入 Enum 时，必须使用 SQLAlchemy Enum 类成员，不传字符串 |
| C4 | **Enum 映射规则** | CLAUDE.md | 定义 SQLAlchemy 模型时，必须显式传递 `values_callable=lambda obj: [e.value for e in obj]` |
| C5 | **SSE 推送异常** | CLAUDE.md | SSE 结果必须被 `jsonable_encoder` 处理为 JSON 序列化对象，直接传 Pydantic/ORM 会导致 ASGI 崩溃 |
| C6 | **异步任务签名** | CLAUDE.md | `AsyncTaskManager.start_task` 关键字参数必须与目标函数签名完全匹配；后台任务严禁抛出未捕获异常 |
| C7 | **JSON 修复** | CLAUDE.md | 请求 LLM 输出复杂 JSON 时，务必使用 `json-repair` 库作为后备 |
| C8 | **列表字段校验** | CLAUDE.md | 将 LLM 输出解析为 Pydantic 模型的 `List[str]` 时，若遇到单字符串需显式转换为数组 |
| C9 | **SPA 回退路由** | CLAUDE.md | 后端必须配置 SPA 回退路由，将非 API 路径的 404 请求返回 `index.html` |
| C10 | **ID 策略** | spec | 所有表主键统一使用 UUID (String(36))，不使用自增 INT |

### 🔐 权限策略

```
当前阶段：不需要 RBAC（基于角色的访问控制）
原因：项目处于内部开发/测试阶段，用户均为技术人员，无多租户/权限隔离需求
落地：
  - 所有资源（测试集/报告/配置/提示词）对登录用户可见可操作
  - 数据模型中的 created_by/ignored_by/annotated_by 字段仅用于审计追踪，不用于权限控制
  - SSE 连接不做用户级隔离
```

### 💡 核心原则

```
系统角色：辅助决策者（提供信息、分析、建议）
用户角色：最终决策者（审查、判断、执行）

错误设计：检测到问题 → 自动应用推荐配置
正确设计：检测到问题 → 展示原因+对比+影响 → 用户决定是否采纳
```

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
| [01-phase-0-overview.md](./phases/phase-0/00-overview.md) | Phase 0 总览：核心工作流修复 | 12 个需求点 |
| [02-phase-1-overview.md](./phases/phase-1/00-overview.md) | Phase 1 总览：数据模型创建 | 22 个需求点 |
| [03-phase-2-overview.md](./phases/phase-2/00-overview.md) | Phase 2 总览：SSE 工作流实现 | 10 个需求点 |
| [04-phase-3-overview.md](./phases/phase-3/00-overview.md) | Phase 3 总览：前端页面实现 | 10 个需求点 |
| [05-phase-4-overview.md](./phases/phase-4/00-overview.md) | Phase 4 总览：6 层校验引擎 | 17 个需求点 |
| [06-phase-5-overview.md](./phases/phase-5/00-overview.md) | Phase 5 总览：推荐模式面板 + 配置/提示词编辑 | 11 个需求点 |
| [07-phase-6-overview.md](./phases/phase-6/00-overview.md) | Phase 6 总览：趋势追踪 + 导出功能 | 8 个需求点 |
| [08-phase-7-overview.md](./phases/phase-7/00-overview.md) | Phase 7 总览：提示词管理重构 | 10 个需求点 |
| [09-phase-8-overview.md](./phases/phase-8/00-overview.md) | Phase 8 总览：配置管理优化 | 8 个需求点 |

### 需求点与实施文件映射

> **详细映射表见 [`DOCUMENT_STRUCTURE.md`](./DOCUMENT_STRUCTURE.md)**

每个需求点对应一个实施文件，文件命名规则：`{phase编号}-{需求点序号}-{需求点名称}.md`

示例：
- `phases/phase-0/01-eventsource-absolute-path.md` — Phase 0 第 1 个需求点：EventSource 相对路径修复
- `phases/phase-1/01-model-testset.md` — Phase 1 第 1 个需求点：TestSet 模型定义
- `phases/phase-4/02-layer1-rule-engine.md` — Phase 4 第 2 个需求点：Layer 1 规则引擎

---

## 🎯 项目背景与目标

### 背景
用户核心任务：诊断 RAG 检索质量 → 调优参数 → 验证效果 → 循环。当前工作流断裂：书籍导入失败 → 无法生成用例 → 无法运行诊断 → 页面空白。

### 核心目标

| # | 目标 | 验收标准 | 所属 Phase |
|---|------|---------|-----------|
| 1 | 修复 12 个核心工作流根因 | 书籍导入/批量测试全部正常 | Phase 0 |
| 2 | 建立 18 个数据模型 | UUID 主键，MySQL 存储，22 个索引 | Phase 1 |
| 3 | 实现 SSE 实时推送工作流 | 10 种事件，断线重连，心跳无泄漏 | Phase 2 |
| 4 | 构建 6 层校验引擎 | 13 种校验，分层递进诊断 | Phase 4 |
| 5 | 实现推荐模式面板 | 三种模式，采纳→审查→保存三步分离 | Phase 5 |
| 6 | 实现配置/提示词版本管理 | 原子保存，热重载，回滚 | Phase 5 |
| 7 | 实现趋势追踪与导出 | PDF/CSV/JSON，误差线，多指标叠加 | Phase 6 |
| 8 | 重构提示词管理 | 中文说明，影响分析，测试沙箱 | Phase 7 |
| 9 | 优化配置管理 | 分组展示，实时校验，冲突检测 | Phase 8 |

---

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React + Ant Design)                │
│  /rag-eval/test-sets  /rag-eval/runs  /rag-eval/reports/{id} │
│  /rag-eval/prompts    /system-config                         │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │  推荐模式面板     │  │  评估报告页       │                  │
│  │  推荐/向导/专家   │  │  6 层校验结果     │                  │
│  │  采纳→审查→保存   │  │  指标总览         │                  │
│  └──────────────────┘  └──────────────────┘                  │
└──────────────────────────┬────────────────────────────────────┘
                           │ REST API + SSE
┌──────────────────────────▼────────────────────────────────────┐
│                      后端 (FastAPI)                            │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐    │
│  │ Controller │  │  Service   │  │  ValidationEngine    │    │
│  │ 层         │→ │ 层         │→ │  (6 层校验)          │    │
│  └────────────┘  └────────────┘  └──────────────────────┘    │
│       │                  │                  │                 │
│       ▼                  ▼                  ▼                 │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐    │
│  │ SSE Pub    │  │ ConfigCache│  │  LLM (DashScope)     │    │
│  │ /Redis     │  │ (热重载)   │  │  (Layer 3 诊断)      │    │
│  └────────────┘  └────────────┘  └──────────────────────┘    │
└──────────────────────────┬────────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────────┐
│                      数据层                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐              │
│  │ MySQL 5.7  │  │ Redis 7.0  │  │ Chroma     │              │
│  │ (17+ 张表) │  │ (Pub/Sub)  │  │ (向量库)   │              │
│  └────────────┘  └────────────┘  └────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 核心工作流

```
创建/选择测试集 → 运行测试集 → 生成评估报告 → 6 层校验诊断
    → 输出调优建议 → 推荐模式面板展示 → 用户采纳 → 审查 → 保存为新版本
    → 复测验证 → 趋势追踪 → 循环
```

---

## 📦 依赖管理

### 新增依赖

```toml
# Phase 6: PDF 导出
weasyprint = "^60.0"

# Phase 4: JSON 修复（LLM 输出解析）
json-repair = "^0.30.0"
```

---

## 🔧 配置管理

### 新增配置项

```python
# Phase 4: 校验引擎
rag_validation_timeout_total: int = 300
rag_validation_timeout_per_layer: dict = {1: 30, 2: 30, 3: 120, 4: 30, 5: 30, 6: 60}
rag_validation_max_concurrent: int = 3
rag_validation_queue_max: int = 10
rag_bad_case_llm_threshold: int = 5
rag_bad_case_sample_max: int = 50
# Layer 1 规则引擎阈值（禁止硬编码，从配置中心读取）
rag_validation_threshold_p_at_5: float = 0.70
rag_validation_threshold_r_at_5: float = 0.85
rag_validation_threshold_f1: float = 0.75
rag_validation_threshold_mrr: float = 0.70
rag_validation_threshold_short_query_failure_rate: float = 0.30
rag_validation_threshold_cross_domain_failure_rate: float = 0.20

# Phase 5: 配置热重载
rag_config_cache_ttl: int = 300
rag_config_redis_channel: str = "config_changed"

# Phase 6: 导出
rag_export_pdf_timeout: int = 60
rag_export_pdf_max_concurrent: int = 2
rag_export_redis_ttl: int = 86400
```

---

## 📖 下一步

继续查看各个 Phase 的详细实施方案：

1. [Phase 0: 核心工作流修复](./phases/phase-0/00-overview.md) — 12 个需求点
2. [Phase 1: 数据模型创建](./phases/phase-1/00-overview.md) — 21 个需求点
3. [Phase 2: SSE 工作流实现](./phases/phase-2/00-overview.md) — 10 个需求点
4. [Phase 3: 前端页面实现](./phases/phase-3/00-overview.md) — 10 个需求点
5. [Phase 4: 6 层校验引擎](./phases/phase-4/00-overview.md) — 17 个需求点
6. [Phase 5: 推荐模式面板 + 配置/提示词编辑](./phases/phase-5/00-overview.md) — 11 个需求点
7. [Phase 6: 趋势追踪 + 导出功能](./phases/phase-6/00-overview.md) — 8 个需求点
8. [Phase 7: 提示词管理重构](./phases/phase-7/00-overview.md) — 10 个需求点
9. [Phase 8: 配置管理优化](./phases/phase-8/00-overview.md) — 8 个需求点

---

**返回索引：** [README.md](./README.md)
