# RAG 平台化改造——实施方案

> 本目录提供三维度的完整实施方案。每个维度独立可读，交叉引用。
> **重要原则**：所有功能必须在需求文档和实施方案中有完整设计，不因延期而省略文档。MVP 划分仅影响实施顺序，不影响设计完整性。

## 文档地图

### 按模块拆分（含完整 API 契约、DDL、组件树）

| # | 文件 | 内容 |
|---|------|------|
| 1 | [01-pipeline-engine.md](by-module/01-pipeline-engine.md) | 28 节点执行器接口、PipelineCompiler、NodeRegistry、全部管道 API 契约、数据库 DDL |
| 2 | [02-pipeline-editor.md](by-module/02-pipeline-editor.md) | 前端组件树、React Flow 自定义节点/边、状态管理、管道工作台三视图 |
| 3 | [03-knowledge-base.md](by-module/03-knowledge-base.md) | 向量后端适配器、分块引擎、Embedding 引擎、全部知识库 API 契约、DDL |
| 4 | [04-permission.md](by-module/04-permission.md) | JWT 认证流、RBAC、双层 Pre-filter、租户 Provisioning、全部权限 API 契约、DDL |
| 5 | [05-search-api.md](by-module/05-search-api.md) | 三种搜索方式 API 契约、SSE 事件协议、发布 URL 管理、管道级限流 |
| 6 | [06-rag-evaluation.md](by-module/06-rag-evaluation.md) | 评估运行执行流、指标计算引擎、报告生成、全部评估 API 契约、DDL |
| 7 | [07-infrastructure.md](by-module/07-infrastructure.md) | Docker 部署、配置热重载、全链路 Tracing、Prometheus 指标、健康检查 |
| 8 | [vector-backend-extension-strategy.md](by-module/vector-backend-extension-strategy.md) | **向量后端扩展策略**：Chroma/ES/Milvus 统一适配架构、分阶段实施、迁移流程 |

### 按阶段拆分（含测试策略、验收检查点）

| # | 文件 | 范围 |
|---|------|------|
| 0 | [phase-0-infrastructure.md](by-phase/phase-0-infrastructure.md) | 项目骨架、数据库 Schema、Docker Compose、前后端基础设施 |
| 1 | [phase-1-permission.md](by-phase/phase-1-permission.md) | 认证核心、租户管理、用户/角色、RBAC、中间件、Repository 改造 |
| 2 | [phase-2-knowledge-base.md](by-phase/phase-2-knowledge-base.md) | 向量存储适配器、ACL 过滤器、分块引擎、Embedding 引擎、文档解析 |
| 3 | [phase-3-pipeline-engine.md](by-phase/phase-3-pipeline-engine.md) | PipelineCompiler、NodeRegistry、28 种节点执行器、管道 API |
| 4 | [phase-4-search-api.md](by-phase/phase-4-search-api.md) | 搜索服务、发布 URL 管理、动态路由、SSE 流式、限流 |
| 5 | [phase-5-pipeline-editor.md](by-phase/phase-5-pipeline-editor.md) | React Flow 画布、节点面板、属性面板、域容器、三视图切换 |
| 6 | [phase-6-knowledge-frontend.md](by-phase/phase-6-knowledge-frontend.md) | 知识库列表/详情页、文档上传、分块预览、权限选项卡 |
| 7 | [phase-7-evaluation.md](by-phase/phase-7-evaluation.md) | 评估引擎适配 PipelineCompiler、跨域指标、内联调优 UI |
| 8 | [phase-8-security-quality.md](by-phase/phase-8-security-quality.md) | 安全合规节点、质量增强节点、性能优化节点（后置实现） |
| 9 | [phase-9-admin-frontend.md](by-phase/phase-9-admin-frontend.md) | 超管租户管理、用户管理、角色管理、God Mode、全局布局 |
| 10 | [phase-10-es-milvus.md](by-phase/phase-10-es-milvus.md) | ES/Milvus 适配器验证、后端迁移流程、Docker profiles |

## 阅读路径

**按角色**：
- 后端开发者 → by-module (01,03,04,05,06,07) + by-phase (对应 phase)
- 前端开发者 → by-module (02,05,06) + by-phase (phase-5,6,9)
- 架构审查 → by-layer (从 by-module 各文档的 §接口契约 和 §数据流 交叉查阅)

**按顺序**：先读 by-module 理解完整模块接口，再读 by-phase 按实施顺序执行。

## 与上层文档的关系

```
core-objectives.md                    ← 最高依据
requirements/*.md                     ← 功能需求（全部功能必须有完整设计）
implementation/by-module/             ← 本目录：逐个模块的完整实现规范
implementation/by-phase/              ← 本目录：按阶段的实施指导 + 测试策略
adr/                                  ← 架构决策记录
  ├── 001-pipeline-compiler-orchestration-backend.md  ← 技术选型（待决定：Python/Java/Rust）
  ├── 002-configuration-layers-l0-l3.md
  └── 003-zero-migration-principle.md
```

## 编码规范（所有文档的约束）

| 约束 | 规则 |
|------|------|
| 实体类位置 | 所有 `class Xxx(BaseModel)` 必须在 `schemas/` 下 |
| 类长度 | ≤ 500 行，超限拆分 + 门面模式 |
| 注释 | 全中文 |
| 配置 | 禁止硬编码，L0-L3 层级覆盖 |
| 异常 | 继承 `AppException`，禁止 `HTTPException` |
| 响应 | 统一 `{code, message, data}` |
| 数据库 | 零迁移，直接改 DDL；Repository 基类自动注入 `tenant_id` |

## 错误码注册表

各模块错误码范围互不重叠，`code` 为数字（HTTP 语义），`error_code` 为字符串（业务语义）。

| 模块 | code 范围 | error_code 前缀 | 来源 |
|------|----------|-----------------|------|
| 管道引擎 | 40001–40006, 40401–40402, 50001 | `PIPELINE_*`、`COMPOUND_NODE_*`、`NODE_*` | [01-pipeline-engine.md](by-module/01-pipeline-engine.md) §1 |
| 知识库 | HTTP 400/403/409/422 | `KB_*`、`DOCUMENT_*`、`CHUNK_*` | [03-knowledge-base.md](by-module/03-knowledge-base.md) §1 |
| 权限认证 | HTTP 401/403/409 | `AUTH_*`、`TENANT_*`、`ROLE_*`、`USER_*`、`PERMISSION_*` | [04-permission.md](by-module/04-permission.md) §1 |
| 搜索发布 | HTTP 400/401/404/429/500 | `ENDPOINT_*`、`RATE_*`、`QUERY_*`、`URL_PATH_*` | [05-search-api.md](by-module/05-search-api.md) §1 |
| RAG 评估 | HTTP 400/404/409 | `TEST_CASE_*`、`TEST_RUN_*`、`REPORT_*`、`TUNING_*`、`SNAPSHOT_*` | [06-rag-evaluation.md](by-module/06-rag-evaluation.md) §1 |

> **规则**：新增错误码必须先在此表登记，确保 code 数值范围和 error_code 前缀无冲突。

---

## MVP 阶段划分

> **核心原则**：所有功能必须在需求文档和实施方案中有完整设计。MVP 划分仅决定实施顺序，不决定设计是否完整。延期的功能必须在对应的 requirements 和 by-module 文档中有完整接口定义。

### MVP（一期）：最小可用闭环

**目标**：单域搜索可运行 → 管道可编辑 → 基础评估可执行 → 权限生效

| Phase | 范围 | MVP 必须包含 | 可延期到二期 |
|-------|------|------------|------------|
| **Phase 0** | 基础设施 | 全部（项目骨架、DB Schema、Docker Compose、继承模块） | 无 |
| **Phase 1** | 权限与多租户 | JWT 认证、租户 CRUD、用户/角色 RBAC、库级别权限裁剪、Repository 基类 tenant_id 注入 | God Mode 审计日志、角色视角切换、文档级 ACL（二期） |
| **Phase 2** | 知识库管理 | 知识库 CRUD、文档上传解析（PDF/TXT/MD）、固定大小分块 + 语义分块、Chroma 向量化、BM25 独立索引 | ES/Milvus 适配器（Phase 10）、向量后端迁移、分块预览、EPUB/HTML 解析 |
| **Phase 3** | 管道引擎 | PipelineCompiler 基础框架、**闭环最小链路节点**（见下表）、管道 CRUD + 版本管理 | 条件边、降级边、复合节点、聚合层节点中的 cross_dedup/conflict_detect |
| **Phase 4** | 搜索 API | 通用端点 `POST /api/v1/search`、同步 JSON 响应、基础认证（JWT） | 发布 URL、SSE 流式、API Key 认证、参数白名单 |
| **Phase 5** | 管道编辑器 | 基础画布（React Flow）、节点拖拽连线、域容器（折叠/展开）、属性面板、保存/干运行 | 条件边/降级边渲染、复合节点、撤销/重做、版本对比、画布虚拟化 |
| **Phase 6** | 知识库前端 | 知识库列表页、详情页（文档选项卡 + 设置选项卡）、文档上传 | 分块&向量选项卡、权限选项卡、分块预览面板 |
| **Phase 7** | RAG 评估 | 继承 12 项指标 + 6 层诊断、评估运行 + SSE 进度、基础报告（Markdown） | 跨域指标、内联调优、管道版本对比、域贡献度可视化、报告导出 JSON/CSV |
| **Phase 8** | 安全/质量节点 | 延期 | 全部（敏感词、PII 脱敏、内容审核、幻觉检测、引用验证） |
| **Phase 9** | 超管前端 | 延期 | 全部（超管租户管理、God Mode、用户管理前端） |
| **Phase 10** | ES/Milvus | 延期 | 全部（ES/Milvus 适配器、迁移流程、Docker profiles） |

### Phase 3 MVP 节点清单

一期仅实现以下节点，即可完成单域搜索全链路闭环：

| 优先级 | 节点 | 说明 |
|--------|------|------|
| **P0 闭环** | `vector_search` | 向量检索 |
| **P0 闭环** | `bm25_search` | BM25 检索 |
| **P0 闭环** | `hybrid_search` | 混合检索（BM25 + 向量 + RRF 融合） |
| **P0 闭环** | `query_analyzer` | 查询分析（识别域 + 单域快捷路径检测） |
| **P0 闭环** | `domain_dispatch` | 域分发（含权限裁剪） |
| **P0 闭环** | `unified_generate` | 统一答案合成 |
| **P1 查询理解** | `query_rewrite` | 查询改写（LLM） |
| **P1 查询理解** | `synonym_expand` | 同义词扩展 |
| **P1 查询理解** | `term_normalize` | 术语标准化 |
| **P1 查询理解** | `stopword_filter` | 禁用词过滤 |
| **P2 聚合补全** | `cross_fusion` | 跨域融合 |
| **P2 聚合补全** | `result_fusion` | 结果融合 |
| **P3 质量增强** | `rerank` | 重排序 |
| **P3 质量增强** | `dedup` | 去重 |
| **P4 增强** | `semantic_cache` | 语义缓存 |
| **P4 增强** | `structured_output` | 结构化输出 |
| **延期** | `query_decompose` | 查询分解 |
| **延期** | `intent_classify` | 意图分类（需条件边支持） |
| **延期** | `query_expand` | 查询扩展 |
| **延期** | `multimodal_search` | 多模态检索 |
| **延期** | `sensitive_filter` | 敏感词过滤（Phase 8） |
| **延期** | `pii_mask` | PII 脱敏（Phase 8） |
| **延期** | `content_audit` | 内容审核（Phase 8） |
| **延期** | `hallucination_check` | 幻觉检测（Phase 8） |
| **延期** | `citation_verify` | 引用验证（Phase 8） |
| **延期** | `rate_limiter` | 速率限制（Phase 4 二期） |
| **延期** | `cross_dedup` | 跨域去重（需多域场景验证） |
| **延期** | `conflict_detect` | 冲突检测（需多域场景验证） |

**一期 16 个节点 + 延期 12 个节点 = 28 个节点全部有完整设计文档**。

### MVP 闭环链路

```
单域查询:
  query_analyzer → (单域快捷路径) → domain_dispatch →
  [域管道: vector_search / bm25_search / hybrid_search → rerank] →
  unified_generate → 答案

多域查询（一期简化版，跳过 cross_dedup/conflict_detect）:
  query_analyzer → domain_dispatch →
  [域1管道] + [域2管道] 并行 →
  cross_fusion → unified_generate → 答案
```

### 二期扩展清单

二期在 MVP 基础上叠加以下能力，每个扩展的设计文档已就绪：

| 扩展项 | 关联设计文档 | 说明 |
|--------|------------|------|
| 条件边 + 降级边 | [01-pipeline-model §1.2-1.3](../requirements/01-pipeline-model-and-engine.md) | PipelineCompiler 已有完整接口定义 |
| 复合节点 | [01-pipeline-model §1.4](../requirements/01-pipeline-model-and-engine.md) | 嵌套最多 3 层、导入导出 |
| 剩余 12 个节点 | [01-pipeline-model §1.1](../requirements/01-pipeline-model-and-engine.md) | 全部 28 节点的参数/输入/输出已定义 |
| 发布 URL + SSE 流式 | [05-pipeline-publishing](../requirements/05-pipeline-publishing-and-search-api.md) | 三种搜索方式全部定义 |
| 文档级 ACL | [04-permission §3.4](../requirements/04-permission-and-multi-tenancy.md) | ACLFilterBuilder 三种后端实现 |
| 跨域指标 + 内联调优 | [06-rag-evaluation §2.4+§7](../requirements/06-rag-evaluation.md) | 4 项跨域指标 + 调优闭环 |
| ES/Milvus 适配器 | [vector-backend-extension-strategy.md](by-module/vector-backend-extension-strategy.md) | 统一适配架构 + 迁移流程 |
| 超管前端 | [04-permission §2](../requirements/04-permission-and-multi-tenancy.md) | 租户管理 + God Mode |

---

## 关键架构决策（ADR）

| ADR | 决策 | 状态 |
|-----|------|------|
| [001-pipeline-compiler-orchestration-backend.md](../adr/001-pipeline-compiler-orchestration-backend.md) | PipelineCompiler 技术选型 | **已决定**：Python 主体 + Rust 热点混合架构。23 个 I/O 密集型节点用 Python，5 个 CPU 密集型热点（MinHash/RRF/BM25/PII/分块）渐进式用 Rust+PyO3 重写 |
| [002-configuration-layers-l0-l3.md](../adr/002-configuration-layers-l0-l3.md) | L0-L3 四层配置架构 | 已决定 |
| [003-zero-migration-principle.md](../adr/003-zero-migration-principle.md) | 零迁移原则 | 已决定 |
