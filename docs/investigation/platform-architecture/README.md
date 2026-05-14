# RAG 平台化改造——文档目录结构

> 本文件为文档体系的导航索引。按层级阅读：目标 → 需求 → 实施 → 决策 → 研究。
> 最后更新：2026-05-14

---

## 目录树

```
docs/investigation/platform-architecture/
│
├── README.md                             # ← 本文件：文档目录结构索引
├── core-objectives.md                    # 最高依据：8 大核心目标 + 不可妥协约束
│
├── requirements/                         # 功能需求（7 份，每份对应一个模块）
│   ├── 01-pipeline-model-and-engine.md   #   管道模型与执行引擎
│   ├── 02-pipeline-editor.md             #   管道工作台（前端编辑器）
│   ├── 03-knowledge-base.md              #   知识库管理
│   ├── 04-permission-and-multi-tenancy.md#   权限与多租户
│   ├── 05-pipeline-publishing-and-search-api.md # 管道发布与搜索 API
│   ├── 06-rag-evaluation.md              #   RAG 评估系统
│   └── 07-infrastructure-and-deployment.md # 系统基础设施与部署
│
├── implementation/                       # 实施方案（三维度）
│   ├── README.md                         #   实施方案总览 + 文档地图 + 编码规范 + MVP 阶段划分
│   │
│   ├── by-module/                        #   维度一：按模块拆分（完整 API 契约、DDL、组件树）
│   │   ├── 01-pipeline-engine.md         #     管道引擎：28 节点执行器、PipelineCompiler、NodeRegistry
│   │   ├── 02-pipeline-editor.md         #     管道编辑器：React Flow 组件树、状态管理、三视图
│   │   ├── 03-knowledge-base.md          #     知识库：向量后端适配器、分块引擎、Embedding 引擎
│   │   ├── 04-permission.md              #     权限：JWT 认证流、RBAC、双层 Pre-filter、租户 Provisioning
│   │   ├── 05-search-api.md              #     搜索 API：三种搜索方式、SSE 事件协议、限流
│   │   ├── 06-rag-evaluation.md          #     RAG 评估：指标计算引擎、报告生成、跨域评估
│   │   ├── 07-infrastructure.md          #     基础设施：Docker 部署、配置热重载、Tracing、Prometheus
│   │   └── vector-backend-extension-strategy.md # 向量后端扩展策略：Chroma/ES/Milvus 统一架构、分阶段实施、迁移
│   │
│   └── by-phase/                         #   维度二：按阶段拆分（实施顺序 + 测试策略 + 验收检查点）
│       ├── phase-0-infrastructure.md     #     阶段 0：项目骨架、数据库 Schema、Docker Compose
│       ├── phase-1-permission.md         #     阶段 1：认证核心、租户管理、RBAC、中间件
│       ├── phase-2-knowledge-base.md     #     阶段 2：向量存储适配器、ACL 过滤器、分块引擎
│       ├── phase-3-pipeline-engine.md    #     阶段 3：PipelineCompiler、NodeRegistry、28 种节点
│       ├── phase-4-search-api.md         #     阶段 4：搜索服务、发布 URL、动态路由、SSE 流式
│       ├── phase-5-pipeline-editor.md    #     阶段 5：React Flow 画布、节点面板、属性面板
│       ├── phase-6-knowledge-frontend.md #     阶段 6：知识库列表/详情页、文档上传、分块预览
│       ├── phase-7-evaluation.md         #     阶段 7：评估引擎适配、跨域指标、内联调优 UI
│       ├── phase-8-security-quality.md   #     阶段 8：安全合规节点、质量增强节点（后置实现）
│       ├── phase-9-admin-frontend.md     #     阶段 9：超管租户管理、God Mode、全局布局
│       └── phase-10-es-milvus.md         #     阶段 10：ES/Milvus 适配器验证、后端迁移流程
│
├── adr/                                  # 架构决策记录（ADR）
│   ├── 001-pipeline-compiler-orchestration-backend.md  # PipelineCompiler 选型（已决定）：Python 主体 + Rust 热点
│   ├── 002-configuration-layers-l0-l3.md               # L0-L3 四层配置架构
│   └── 003-zero-migration-principle.md                 # 零迁移原则
│
└── research/                             # 技术调研（选型参考）
    ├── rag-platforms-comparison.md       #   RAG 平台对比调研
    └── pipeline-builder-frontend.md      #   管道编辑器前端技术调研
```

---

## 文档层级关系

```
core-objectives.md          ← 最高依据，所有决策的源头
    │
    ├── requirements/*.md   ← 功能需求，定义"做什么"
    │       │
    │       ├── implementation/by-module/*.md  ← 模块实施规范，定义"怎么做"（接口契约、DDL、组件）
    │       │
    │       └── implementation/by-phase/*.md   ← 阶段实施指导，定义"按什么顺序做"（测试策略、验收）
    │
    ├── adr/*.md            ← 架构决策，记录"为什么这样做"
    │
    └── research/*.md       ← 技术调研，选型依据
```

---

## 各文件详细说明

### 根级文件

| 文件 | 定位 | 核心内容 | 阅读对象 |
|------|------|---------|---------|
| `core-objectives.md` | 最高依据 | 8 大核心目标（多域聚合、多知识库、双层权限、管道编辑发布、RAG 评估、搜索 API、模块化范围、技术选型）+ 每个目标的"不可妥协"约束 | 全员 |

### requirements/ — 功能需求

| 文件 | 模块 | 核心内容 | 关联核心目标 |
|------|------|---------|------------|
| `01-pipeline-model-and-engine.md` | 管道模型与执行引擎 | 28 种节点体系（22 域内 + 6 聚合）、配置格式、条件路由、降级路径、复合节点、版本管理、PipelineCompiler、节点注册机制、数据模型、API 端点 | §1 多域聚合、§4 管道编辑 |
| `02-pipeline-editor.md` | 管道工作台 | 管道列表页、三视图切换（编辑/评估/发布）、React Flow 画布布局、域容器交互、边类型、状态管理、前端组件树、性能约束 | §4 管道编辑 |
| `03-knowledge-base.md` | 知识库管理 | 知识库 CRUD、文档上传解析（PDF/TXT/MD/HTML/EPUB）、5 种分块策略、Embedding 向量化、3 种向量后端（Chroma/ES/Milvus）、后端迁移、索引重建、BM25 独立索引 | §2 多知识库管理 |
| `04-permission-and-multi-tenancy.md` | 权限与多租户 | 超管 + 租户角色层级、租户管理（创建/停用/归档/删除）、RBAC、双层 Pre-filter（库级别 + 文档级别）、ACLFilterBuilder、角色视角切换、God Mode 安全约束 | §3 双层权限控制 |
| `05-pipeline-publishing-and-search-api.md` | 管道发布与搜索 API | 发布 URL 配置、三种搜索方式（发布 URL / 通用端点 / SSE 流式）、认证叠加、速率限制（两层独立限流）、请求参数白名单、搜索结果大小控制、发布视图 | §4 发布、§6 搜索 API |
| `06-rag-evaluation.md` | RAG 评估系统 | 双轨评估（12 项三层指标 + 六层诊断）、跨域扩展指标、测试数据管理、评估运行、后处理流水线、报告生成、调优闭环（冲突检测）、知识库快照、继承/新增边界 | §5 RAG 评估 |
| `07-infrastructure-and-deployment.md` | 系统基础设施 | backend/ 继承清单（完整/不继承/去业务化）、租户 Provisioning、Docker Compose 部署、非功能需求（性能/可靠性/安全/可观测性）、配置管理、DDL 管理 | §0 弃旧攻新、§7 模块化 |

### implementation/by-module/ — 模块实施规范

| 文件 | 核心内容 | 与 requirements/ 的关系 |
|------|---------|----------------------|
| `01-pipeline-engine.md` | 28 种节点执行器的完整 Python 接口定义、PipelineCompiler 编译与执行流程、NodeRegistry 注册机制、全部管道 API 请求/响应 Schema、数据库 DDL | 01-pipeline-model 的实现级细化 |
| `02-pipeline-editor.md` | 前端组件树（PipelineListPage → PipelineWorkbench → EditView/EvaluateView/PublishView）、React Flow 自定义节点/边定义、Zustand 状态管理、API 客户端接口 | 02-pipeline-editor 的实现级细化 |
| `03-knowledge-base.md` | 向量后端适配器接口（VectorStoreAdapter ABC）、分块引擎接口、Embedding 引擎接口、ACLFilterBuilder 三种后端实现、知识库 API 请求/响应 Schema、DDL | 03-knowledge-base 的实现级细化 |
| `04-permission.md` | JWT 认证流程图、RBAC 权限矩阵、双层 Pre-filter 执行时序、租户 Provisioning 自动化流程、全部权限 API 请求/响应 Schema、DDL | 04-permission 的实现级细化 |
| `05-search-api.md` | 三种搜索方式的完整 API 契约、SSE 事件协议（10 种事件类型）、发布 URL 动态路由注册、管道级限流实现 | 05-pipeline-publishing 的实现级细化 |
| `06-rag-evaluation.md` | 评估运行执行流（BatchTestRunner → PipelineCompiler）、指标计算引擎接口（12 项计算器）、6 层诊断执行器、报告生成器、全部评估 API 请求/响应 Schema、DDL | 06-rag-evaluation 的实现级细化 |
| `07-infrastructure.md` | Docker Compose 完整配置、配置热重载流程、全链路 Tracing 接口、Prometheus 指标定义、健康检查端点、前端部署方案 | 07-infrastructure 的实现级细化 |
| `vector-backend-extension-strategy.md` | Chroma/ES/Milvus 统一适配架构（VectorStoreAdapter ABC + BM25IndexAdapter ABC + ACLFilterBuilder ABC）、工厂模式、三种后端实现对照、分阶段实施计划、后端迁移流程、BM25 独立索引设计、Docker profiles 配置 | 03-knowledge-base §1.5 的集中式扩展方案 |

### implementation/by-phase/ — 阶段实施指导

| 文件 | 阶段 | 范围 | 前置依赖 | 交付物 |
|------|------|------|---------|--------|
| `phase-0-infrastructure.md` | 0 | 项目骨架、数据库 Schema、Docker Compose、前后端基础设施 | 无 | 可启动的空项目 + 数据库 + Docker 环境 |
| `phase-1-permission.md` | 1 | 认证核心、租户管理、用户/角色、RBAC、中间件、Repository 改造 | Phase 0 | 完整的认证/授权系统 + 超管/租户管理 |
| `phase-2-knowledge-base.md` | 2 | 向量存储适配器、ACL 过滤器、分块引擎、Embedding 引擎、文档解析 | Phase 1 | 知识库 CRUD + 文档上传解析 + 向量化 |
| `phase-3-pipeline-engine.md` | 3 | PipelineCompiler、NodeRegistry、28 种节点执行器、管道 API | Phase 1 | 管道配置 CRUD + 编译验证 + 干运行 |
| `phase-4-search-api.md` | 4 | 搜索服务、发布 URL 管理、动态路由、SSE 流式、限流 | Phase 3 | 三种搜索方式可用 + 发布 URL 管理 |
| `phase-5-pipeline-editor.md` | 5 | React Flow 画布、节点面板、属性面板、域容器、三视图切换 | Phase 3 | 管道可视化编辑器可用 |
| `phase-6-knowledge-frontend.md` | 6 | 知识库列表/详情页、文档上传、分块预览、权限选项卡 | Phase 2 | 知识库管理前端可用 |
| `phase-7-evaluation.md` | 7 | 评估引擎适配 PipelineCompiler、跨域指标、内联调优 UI | Phase 3 + 6 | 完整评估闭环可用 |
| `phase-8-security-quality.md` | 8 | 安全合规节点、质量增强节点、性能优化节点（后置实现） | Phase 3 | 增强节点可用 |
| `phase-9-admin-frontend.md` | 9 | 超管租户管理、用户管理、角色管理、God Mode、全局布局 | Phase 1 | 超管前端可用 |
| `phase-10-es-milvus.md` | 10 | ES/Milvus 适配器验证、后端迁移流程、Docker profiles | Phase 2 | 三种向量后端全部可用 |

**关键路径**：Phase 0 → Phase 1 → Phase 3 → Phase 4 → Phase 7

### adr/ — 架构决策记录

| 文件 | 决策 | 状态 | 核心理由 |
|------|------|------|---------|
| `001-pipeline-compiler-orchestration-backend.md` | PipelineCompiler 技术选型 | **已决定** | Python 主体 + Rust 热点混合架构。23 个 I/O 密集型节点用 Python，5 个 CPU 密集型热点渐进式用 Rust+PyO3 重写。不选纯 Rust（LLM 生态缺失）/ 纯 Java（跨语言 RPC 开销）/ LangGraph（无原生降级/域并行支持） |
| `002-configuration-layers-l0-l3.md` | L0-L3 四层配置架构 | 已决定 | 多租户需要分层覆盖；L1 走 MySQL 支持热重载；L3 白名单防止安全参数被覆盖 |
| `003-zero-migration-principle.md` | 零迁移原则，直接覆盖旧实现 | 已决定 | 项目未上线无历史数据；减少复杂度；加速迭代 |

### research/ — 技术调研

| 文件 | 内容 |
|------|------|
| `rag-platforms-comparison.md` | RAG 平台技术选型对比（向量数据库、编排框架等） |
| `pipeline-builder-frontend.md` | 管道编辑器前端技术调研（React Flow vs 其他方案） |

---

## 阅读路径

**按角色**：

| 角色 | 推荐阅读顺序 |
|------|------------|
| **架构师** | `core-objectives.md` → `requirements/全部` → `adr/全部` → `implementation/by-module/` 接口契约章节 |
| **后端开发者** | `core-objectives.md` → 对应模块的 `requirements/` → 对应模块的 `implementation/by-module/` → 对应 `implementation/by-phase/` |
| **前端开发者** | `core-objectives.md` → `requirements/02+05+06` → `implementation/by-module/02+05+06` → `implementation/by-phase/phase-5,6,9` |
| **新成员入门** | `core-objectives.md` → `implementation/README.md` → 按需深入各模块 |

**按阶段**：

| 阶段 | 前置阅读 |
|------|---------|
| 准备开工 | `core-objectives.md` + `implementation/README.md` |
| Phase 0 | `requirements/07` + `implementation/by-phase/phase-0` + `implementation/by-module/07` |
| Phase 1 | `requirements/04` + `implementation/by-phase/phase-1` + `implementation/by-module/04` |
| Phase N | `requirements/对应模块` + `implementation/by-phase/对应阶段` + `implementation/by-module/对应模块` |

---

## 文档维护规则

| 规则 | 说明 |
|------|------|
| 权威来源 | `core-objectives.md` 是最高依据，其他文档不得与之冲突 |
| 同步更新 | 修改需求时必须同步更新对应的 implementation 文档 |
| ADR 记录 | 重大架构决策必须新增 ADR 文件，编号递增 |
| 编码规范 | 所有实现文档共享 `implementation/README.md` 中定义的编码规范 |
| 错误码注册 | 新增错误码必须先在 `implementation/README.md` 的错误码注册表中登记 |
