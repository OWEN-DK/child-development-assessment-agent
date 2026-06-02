# 核心业务逻辑导航 (Business Logic Map)

为了让 AI 和开发者在接手任务时能够快速定位代码并理解"这一块是干什么的"，本文档按业务模块梳理了系统的核心逻辑和对应代码入口。

当你需要修改某个具体功能时，请直接查阅下方的对应模块。

---

## 1. Agent 评估工作流 (LangGraph)
**逻辑概述**：控制儿童评估报告生成的完整有向无环图（DAG）。状态数据通过 `AgentState` 对象在各个节点间流转。

| 步骤 | 节点名称 | 业务逻辑 | 代码入口 |
|---|---|---|---|
| **核心编排** | `create_agent_graph` | 定义图的边和节点顺序。 | `backend/src/core/graph.py` |
| **NodePre** | `PreprocessingNode` | 预处理：压缩用户上传的历史训练记录（如运动数据）为统计特征，减少 Token 消耗。 | `backend/src/core/nodes/preprocessing.py` |
| **Node1** | `ValidationNode` | 校验：清洗并标准化家长输入的"拟定运动计划"，智能补全缺失的参数。 | `backend/src/core/nodes/validation.py` |
| **Node2** | `AssessmentNode` | 评估：将家长描述映射到感统维度，对比同龄儿童里程碑，生成儿童发展状态 (`child_state`)。 | `backend/src/core/nodes/assessment.py` |
| **Node3** | `RetrievalNode` | 检索：根据儿童画像和拟定计划，在向量库中精准检索科学理论依据。 | `backend/src/core/nodes/retrieval.py` |
| **Node4** | `ScoringNode` | 评分：结合客观检索结果(AHP算法)与机器学习模型(QwenScorer)进行多维打分。 | `backend/src/core/nodes/scoring.py` |
| **Node5** | `ReportingNode` | 报告：汇总上述所有信息，流式生成家长友好的 Markdown 报告。 | `backend/src/core/nodes/reporting.py` |

---

## 2. 知识问答 Agent (LangGraph v1/v2)
**逻辑概述**：独立于评估 Agent 的知识问答系统，根据用户自然语言问题匹配书籍、检索知识、生成 5 节结构化报告。v1 纯 Chroma 检索，v2 融合 Neo4j 知识图谱 + Bundle 统一检索。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **服务门面** | 并发限制、LangGraph 执行、SSE 推送、Markdown/PDF 导出 | `backend/src/service/knowledge_qa_service.py` |
| **API 控制器** | 触发问答、任务状态查询、SSE 流、下载报告、历史管理 | `backend/src/controller/knowledge_qa_controller.py` |
| **Schema 定义** | `KnowledgeQAState` 状态、业务实体、错误码、进度推送 ContextVar | `backend/src/schemas/knowledge_qa.py` |
| **v1 图组装** | 13 节点 DAG，S4 重试路由 | `backend/src/core/knowledge_qa/_assembly.py` |
| **v2 图组装** | 16 节点 DAG，Bundle 统一检索 + 三层综合 | `backend/src/core/knowledge_qa/_assembly_v2.py` |
| **v1 节点实现** | match_books / prefetch_context / analyze_child / identify_problems / recommend_types / plan_outline / plan_expand_parallel / plan_assemble / generate_s4_citations / contradiction_audit / conclusion / verify_citations / finalize | `backend/src/core/knowledge_qa/nodes/` |
| **v2 节点实现** | fast_knowledge_match / analyze_child_v2 / identify_problems_v2 / recommend_types_v2 / plan_outline_v2 / plan_expand_parallel_v2 / knowledge_synthesis_v2 / query_neo4j_graph | `backend/src/core/knowledge_qa/nodes_v2/` |
| **Bundle 数据模型** | `KnowledgeBundle` 不可变知识产物（L0 自定义规则 + L1 Neo4j + L2 原文） | `backend/src/core/knowledge_qa/bundle.py` |
| **Bundle 构建器** | Phase 1: Neo4j 增强查询 → Chroma 批量搜索 → LazyGraphRAG 遍历 → 组装 | `backend/src/core/knowledge_qa/bundle_builder.py` |
| **Bundle 消费器** | Phase 2: 按节提取 passages + 构造优先级上下文 | `backend/src/core/knowledge_qa/bundle_consumer.py` |
| **Bundle 灰度配置** | 全局开关、Phase 1/2/3 独立开关、流量比例 | `backend/src/core/knowledge_qa/bundle_config.py` |
| **历史记录 Repository** | 问答历史持久化 | `backend/src/repository/knowledge_qa_history_repository.py` |
| **历史记录模型** | SQLAlchemy 模型 | `backend/src/models/knowledge_qa_history.py` |

---

## 3. 自定义知识系统
**逻辑概述**：独立于 RAG 和知识图谱的最高优先级知识注入机制。三通道匹配（keyword→pattern→semantic），命中后以 L0 优先级注入下游。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **匹配引擎** | keyword 精确 → pattern 正则 → semantic 语义(cos≥0.80) 三通道短路匹配 | `backend/src/service/custom_knowledge_service.py` |
| **API 控制器** | 上传 .md 文件、列表查询、匹配测试、CRUD | `backend/src/controller/custom_knowledge_controller.py` |
| **数据存储** | Neo4j `CustomRule` 节点 + MySQL 关键词/正则索引 + embedding 双写 | `backend/src/repository/custom_knowledge_repository.py` |
| **匹配节点** | LangGraph 节点: 3 秒超时，命中后注入 `custom_knowledge_context` + entities | `backend/src/core/knowledge_qa/nodes/fast_knowledge_match.py` |

---

## 4. 知识图谱与 D2G 流水线
**逻辑概述**：将书籍文档转化为 Neo4j 知识图谱，支持实体提取、关系推理、跨书消歧和社区检测。查询时通过 Bundle 构建器和增强查询模块消费图谱数据。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **D2G 书→图谱流水线** | 实体提取 → 图构建 → 社区检测 → 层级树存储 → 持久化 | `backend/src/core/knowledge_qa/d2g/book_pipeline.py` |
| **D2G 书籍阅读器** | PDF/EPUB 文档解析为可处理结构 | `backend/src/core/knowledge_qa/d2g/book_reader.py` |
| **D2G 章节提取器** | 从文档结构中提取章节层级 | `backend/src/core/knowledge_qa/d2g/chapter_extractor.py` |
| **D2G 实体消歧器** | 跨书同义实体识别与合并 | `backend/src/core/knowledge_qa/d2g/entity_resolver.py` |
| **D2G 全局关系推理** | 跨书语义关系推断 | `backend/src/core/knowledge_qa/d2g/global_relation_inference.py` |
| **D2G 图谱写入器** | 将实体和关系写入 Neo4j | `backend/src/core/knowledge_qa/d2g/graph_committer.py` |
| **D2G 图谱质量检查** | 图谱质量校验 | `backend/src/core/knowledge_qa/d2g/graph_quality.py` |
| **D2G 长章节处理** | 超长章节的分段处理 | `backend/src/core/knowledge_qa/d2g/long_chapter.py` |
| **D2G 主图管理** | 全局主图谱的维护 | `backend/src/core/knowledge_qa/d2g/master_graph.py` |
| **LazyGraphRAG 实体提取器** | LLM 驱动的实体/关系提取 | `backend/src/core/knowledge_qa/graph/extractor.py` |
| **LazyGraphRAG 图构建器** | NetworkX 图构建 + 社区分配 + 层级树 | `backend/src/core/knowledge_qa/graph/builder.py` |
| **LazyGraphRAG 社区检测** | Louvain 社区检测 | `backend/src/core/knowledge_qa/graph/community.py` |
| **LazyGraphRAG 遍历器** | 层级树遍历 + LCA 查找 + 知识上下文构建 | `backend/src/core/knowledge_qa/graph/traversal.py` |
| **LazyGraphRAG 导入流水线** | 单本书完整导入编排 | `backend/src/core/knowledge_qa/graph/pipeline.py` |
| **全局图谱重建** | 跨书实体去重 + 全局社区检测 | `backend/src/core/knowledge_qa/graph/global_rebuild.py` |
| **Neo4j Driver 管理** | 同步/异步 Driver 单例 | `backend/src/core/knowledge_qa/neo4j/driver.py` |
| **Neo4j Schema** | 节点类型(27种) + 关系类型(30+种) + 跨书关系组合矩阵 | `backend/src/core/knowledge_qa/neo4j/schema.py` |
| **Neo4j 增强查询** | Bundle Step 1a: S2 problems + custom_entities 作为种子，1-2 跳扩展 | `backend/src/core/knowledge_qa/neo4j/enhanced_query.py` |
| **Neo4j 查询调度器** | 运动推荐 / 跨书关系 / 问题上下文 / 覆盖度查询 | `backend/src/core/knowledge_qa/neo4j/query_dispatcher.py` |
| **Neo4j 章节解析器** | Markdown 章节结构解析 | `backend/src/core/knowledge_qa/neo4j/chapter_parser.py` |
| **Neo4j 跨书清理** | 跨书关系清理 | `backend/src/core/knowledge_qa/neo4j/cross_book_cleanup.py` |
| **Neo4j 跨书 Phase5a/5b** | 跨书消歧与关系推理 | `backend/src/core/knowledge_qa/neo4j/cross_book_phase5a.py`<br>`backend/src/core/knowledge_qa/neo4j/cross_book_phase5b.py` |
| **Neo4j 跨书关系解析器** | 跨书实体解析 | `backend/src/core/knowledge_qa/neo4j/cross_book_resolver.py` |
| **Neo4j 多样性重排** | 检索结果多样性优化 | `backend/src/core/knowledge_qa/neo4j/diversity_rerank.py` |
| **Neo4j 同义词注册** | 同义词管理 | `backend/src/core/knowledge_qa/neo4j/synonym_registry.py` |
| **Neo4j Delta Cypher** | 增量更新 Cypher | `backend/src/core/knowledge_qa/neo4j/delta_cypher.py` |

---

## 5. RAG 知识库与检索系统
**逻辑概述**：负责书籍/PDF的解析入库，以及根据用户 Query 进行混合检索。与知识问答 Agent 独立——RAG 为评估 Agent 的 Node3 提供检索服务，同时也为知识问答的 Bundle 构建提供 Chroma 原文证据。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **门面调度** | RAG 聚合入口 | 暴露统一的搜索和状态查询接口给 Controller。 | `backend/src/service/rag_service.py` |
| **文档导入流水线** | 多模态解析与分块 | 负责 PDF/EPUB 的解析（支持视觉大模型兜底），使用语义分块，提取主题/脑区等元数据，存入 Chroma 向量库。支持断点续传。 | `backend/src/service/document_ingestion/facade.py`<br>`backend/src/service/document_ingestion_service.py` |
| **知识检索流水线** | 混合检索与重排序 | 基于 `rag_pipeline.yaml` 驱动。执行查询重写 -> 同义词扩展 -> 年龄过滤 -> BM25+向量混合检索 -> CrossEncoder重排序。 | `backend/src/service/retrieval/facade.py`<br>`backend/src/service/retrieval_service.py` |
| **知识检索器** | 底层检索执行 | BM25+向量混合检索、A/B 测试权重、缓存、KnowledgeItem 转换 | `backend/src/service/retrieval/knowledge_retriever.py` |
| **索引管理服务** | 向量索引生命周期 | 管理向量库的创建、加载、持久化、重建，支持快照备份和恢复。 | `backend/src/service/index_manager/facade.py`<br>`backend/src/service/index_manager_service.py` |

---

## 6. 核心基础设施与动态调度
**逻辑概述**：支撑系统高性能、高可用运行的底层组件，完全解耦且配置驱动。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **配置管理器** | 动态配置与热更新 | 负责系统参数的 MySQL 持久化与 Redis 缓存。支持配置原子保存、热重载与 ConfigCache 单例管理。 | `backend/src/config/core/manager.py` |
| **提示词管理器** | 动态 Prompt 与 A/B 测试 | 统管所有大模型的 Prompt，支持变量注入、版本对比、测试沙箱以及代码引用分析。 | `backend/src/core/prompt/manager.py` |
| **LLM 工厂** | 多提供商路由与场景隔离 | 统一生成适配的 LLM 实例，支持 DashScope/OpenAI/Anthropic/DeepSeek/Ollama。支持热重载。 | `backend/src/core/llm/factory.py` |
| **三级缓存** | 性能防穿透 | 提供 `内存LRU -> Redis -> 磁盘` 的三层缓存架构，加速高频检索和配置读取。 | `backend/src/service/cache/facade.py` |
| **异步任务管理** | 实时推送与并发控制 | `AsyncTaskManager` 管理后台任务，通过 SSE 向前端推送进度，支持断线重连与并发限制。 | `backend/src/core/async_task.py` |
| **全链路追踪** | Span 追踪与成本分析 | 实现全链路 Span 追踪，异步队列写入，支持耗时与成本分析。 | `backend/src/core/tracing/writer.py`<br>`backend/src/core/tracing/context.py` |
| **中间件层** | 请求处理与异常处理 | 全局异常处理、响应包装、追踪中间件，统一请求处理流程。 | `backend/src/middleware/exception_handler.py`<br>`backend/src/middleware/response_wrapper.py`<br>`backend/src/middleware/trace_middleware.py` |
| **LLM 适配器** | 多框架适配 | LangChain/LlamaIndex/DashScope 适配器，统一 LLM 调用接口。 | `backend/src/core/llm/adapters/langchain.py`<br>`backend/src/core/llm/adapters/llamaindex.py`<br>`backend/src/core/llm/adapters/dashscope_multimodal.py` |

---

## 7. 前端功能模块与交互逻辑
**逻辑概述**：前端 SPA 应用，使用 React 19 + Ant Design 6 + TanStack Query 5 + Zustand 5，按业务模块划分 feature 目录。首页即知识问答页。

### 7.1 知识问答 (`features/knowledge-qa/`)
**逻辑概述**：系统的主入口页面。用户输入自然语言问题 → SSE 实时推送进度 → 流式渲染 5 节结构化报告。支持历史记录侧边栏、Markdown/JSON 双视图、报告下载。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **API 客户端** | 历史记录列表/详情/删除 | `frontend/src/features/knowledge-qa/api/knowledgeQAApi.ts` |
| **类型定义** | MatchedBook/Citation/ExerciseTypeItem/Section3/4StructuredData/ContradictionItem/ProgressState/QAStatus | `frontend/src/features/knowledge-qa/types/index.ts` |
| **Zustand Store** | SSE 生命周期管理（connect/subscribe/disconnect）、localStorage 任务恢复、增量 section 收集 | `frontend/src/features/knowledge-qa/stores/knowledgeQAStore.ts` |
| **useKnowledgeQA Hook** | 薄包装层，组件挂载/卸载时触发 SSE 生命周期 | `frontend/src/features/knowledge-qa/hooks/useKnowledgeQA.ts` |
| **useHistory Hook** | 历史记录列表加载、详情加载 | `frontend/src/features/knowledge-qa/hooks/useHistory.ts` |
| **useReportDownload Hook** | Markdown/JSON 报告构建与浏览器下载 | `frontend/src/features/knowledge-qa/hooks/useReportDownload.ts` |
| **QuestionInput** | 多行文本输入、Shift+Enter 换行、提交/中断/返回按钮切换 | `frontend/src/features/knowledge-qa/components/QuestionInput.tsx` |
| **ProgressPanel** | 垂直 Steps 进度条（11 步单调前进）、增量 section 内容预览 | `frontend/src/features/knowledge-qa/components/ProgressPanel.tsx` |
| **ReportViewer** | Markdown/JSON 双视图切换、跨书矛盾 Alert、下载按钮 | `frontend/src/features/knowledge-qa/components/ReportViewer.tsx` |
| **SectionRenderer** | ReactMarkdown 渲染单节内容（S1-S5 分色标签、自定义 blockquote/table 样式） | `frontend/src/features/knowledge-qa/components/SectionRenderer.tsx` |
| **BookInfoCard** | 匹配书籍信息卡片 | `frontend/src/features/knowledge-qa/components/BookInfoCard.tsx` |
| **CitationsList** | 引用列表汇总展示 | `frontend/src/features/knowledge-qa/components/CitationsList.tsx` |
| **HistorySidebar** | 左侧历史记录侧边栏（状态标签、新建对话、运行中标记） | `frontend/src/features/knowledge-qa/components/HistorySidebar.tsx` |
| **BookSelector** | 书籍选择器（指定书籍提问） | `frontend/src/features/knowledge-qa/components/BookSelector.tsx` |
| **KnowledgeQAPage** | 主页面编排：Layout.Sider + QuestionInput + ProgressPanel + ReportViewer | `frontend/src/features/knowledge-qa/pages/KnowledgeQAPage.tsx` |
| **renderMarkdown 工具** | S3/S4 结构化数据→Markdown 渲染、节内容显示逻辑 | `frontend/src/features/knowledge-qa/utils/renderMarkdown.ts` |

### 7.2 知识管理 / Curation (`features/curation/`)
**逻辑概述**：知识库管理后台——书籍绑定、D2G 草稿生成与编辑、知识图谱可视化、自定义知识管理、跨书关系管理。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **API 客户端** | 书籍/草稿/图谱/自定义知识/跨书 API | `frontend/src/features/curation/api/curationApi.ts` |
| **Zustand Store** | 全局状态管理 | `frontend/src/features/curation/stores/curationStore.ts` |
| **useDraftEditor Hook** | 草稿编辑器逻辑 | `frontend/src/features/curation/hooks/useDraftEditor.ts` |
| **useGraphData Hook** | 图谱数据加载与交互 | `frontend/src/features/curation/hooks/useGraphData.ts` |
| **useSSEGeneration Hook** | D2G 生成进度 SSE 监听 | `frontend/src/features/curation/hooks/useSSEGeneration.ts` |
| **BookListPage** | 书籍列表（绑定/解绑/状态） | `frontend/src/features/curation/pages/BookListPage.tsx` |
| **BindBookPage** | 书籍绑定流程 | `frontend/src/features/curation/pages/BindBookPage.tsx` |
| **GeneratePage** | D2G 草稿生成（SSE 进度） | `frontend/src/features/curation/pages/GeneratePage.tsx` |
| **DraftEditorPage** | 草稿编辑器（章节级编辑/对比） | `frontend/src/features/curation/pages/DraftEditorPage.tsx` |
| **GraphPage** | 知识图谱可视化（Cytoscape.js 画布 + 实体导航 + 关系卡片） | `frontend/src/features/curation/pages/GraphPage.tsx` |
| **PendingQueuePage** | 待处理队列管理 | `frontend/src/features/curation/pages/PendingQueuePage.tsx` |
| **CustomKnowledgePage** | 自定义知识管理（上传/列表/匹配测试） | `frontend/src/features/curation/pages/CustomKnowledgePage.tsx` |
| **CrossBookPage** | 跨书关系管理（冲突/共识/互补） | `frontend/src/features/curation/pages/CrossBookPage.tsx` |
| **GraphCanvas** | Cytoscape.js 图谱画布组件 | `frontend/src/features/curation/components/GraphCanvas.tsx` |
| **NodeDetail** | 图谱节点详情面板 | `frontend/src/features/curation/components/NodeDetail.tsx` |
| **CrossBookPanel** | 跨书关系面板 | `frontend/src/features/curation/components/CrossBookPanel.tsx` |
| **EntityNav** | 实体导航组件 | `frontend/src/features/curation/components/EntityNav.tsx` |

### 7.3 知识库文档管理 (`features/documents/`)
| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **KnowledgeBasePage** | 文档上传/列表/任务进度 | `frontend/src/features/documents/pages/KnowledgeBasePage.tsx` |
| **useDocumentManagement Hook** | 文档管理逻辑（上传/删除/刷新） | `frontend/src/features/documents/hooks/useDocumentManagement.ts` |
| **通用组件** | DocumentList / DocumentUploader / TaskProgressList | `frontend/src/components/documents/` |

### 7.4 知识搜索 (`features/knowledge/`)
| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **KnowledgeSearchPage** | 知识库内容搜索（混合检索） | `frontend/src/features/knowledge/pages/KnowledgeSearchPage.tsx` |
| **useKnowledgeSearch Hook** | 搜索逻辑 | `frontend/src/features/knowledge/hooks/useKnowledgeSearch.ts` |
| **通用组件** | SearchInput / SearchResultList / ResultDetailModal | `frontend/src/components/knowledge/` |

### 7.5 RAG 评估 (`features/rag-eval/`)
**逻辑概述**：RAG 检索质量评估与调优的完整工作台。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **草稿管理** | 测试草稿生成、审核、批量导入 | `frontend/src/features/rag-eval/pages/DraftPage.tsx` |
| **测试用例** | 测试用例和测试集管理 | `frontend/src/features/rag-eval/pages/TestCasePage.tsx`<br>`frontend/src/features/rag-eval/pages/TestSetPage.tsx` |
| **测试运行** | 批量测试执行、进度监控、对比 | `frontend/src/features/rag-eval/pages/RunPage.tsx` |
| **报告管理** | 报告生成、趋势分析、详情查看 | `frontend/src/features/rag-eval/pages/ReportPage.tsx`<br>`frontend/src/features/rag-eval/pages/ReportDetailPage.tsx` |
| **调优建议** | 调优建议管理、一键采纳 | `frontend/src/features/rag-eval/pages/TuningPage.tsx` |
| **提示词管理** | 提示词列表/编辑/版本对比/测试沙箱 | `frontend/src/features/rag-eval/pages/PromptListPage.tsx`<br>`PromptEditPage.tsx`<br>`PromptVersionComparisonPage.tsx`<br>`PromptTestSandboxPage.tsx` |
| **状态管理** | 3 个 Zustand Store | `frontend/src/features/rag-eval/stores/` |
| **业务 Hooks** | 13 个 Hooks（useDrafts/useTestCases/useTestRuns/useReports/useMetrics/usePrompts/useTuning/useSnapshots/useDraftGenerationProgress/useSSEProgress 等） | `frontend/src/features/rag-eval/hooks/` |
| **业务组件** | 16 个组件（7 个子目录: common/diagnosis/draft/metrics/report/test-set/tuning） | `frontend/src/features/rag-eval/components/` |

### 7.6 其他前端模块
| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **评估特性** | 儿童评估表单与报告查看 | `frontend/src/features/assessment/` |
| **系统配置** | 动态配置管理 UI | `frontend/src/features/config/` + `frontend/src/pages/SystemConfigPage.tsx` |
| **LLM 监控** | 调用统计、趋势图、模型分布 | `frontend/src/features/monitoring/LLMMonitoringDashboard.tsx` |
| **链路追踪** | Trace/Span 查询与可视化 | `frontend/src/components/monitoring/`（8 个组件） |
| **API 客户端层** | 按业务模块组织（assessment/config/documents/knowledge/monitoring/rag-eval/tracing） | `frontend/src/api/` |
| **实体层** | 类型定义、枚举、映射器、常量 | `frontend/src/entities/`（assessment/rag-eval/tracing） |
| **共享层** | 通用 API client / Hooks / 库 / 类型 / UI | `frontend/src/shared/` |
| **路由配置** | BrowserHistory + 路由懒加载（提示词管理页面） | `frontend/src/router/index.tsx` |

---

## 8. 自动化测试与评估 (SDD/TDD)
**逻辑概述**：保证 RAG 检索质量和 Agent 生成质量的自动化评估体系，支持全链路回测、6层诊断和回归验证。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **RAG评估编排器** | 评估全流程入口 | 对外提供统一的评估执行、结果查询、报告生成接口，内部协调 6 个子引擎。 | `backend/src/service/rag_eval/orchestrator.py` |
| **测试运行引擎** | 并发批量测试 | 支持多并发执行测试用例，自动关联知识库快照、配置版本、模型版本，保证测试可复现。 | `backend/src/service/rag_eval/run/facade.py`<br>`backend/src/service/rag_eval/run/executor.py`<br>`backend/src/service/rag_eval/run/batch_runner.py` |
| **草稿生成引擎** | 测试用例生成与审核 | LLM自动从文档提取测试草稿，支持人工审核、批量导入，生成标准化测试用例和测试集。 | `backend/src/service/rag_eval/draft/facade.py`<br>`backend/src/service/rag_eval/draft/generator.py` |
| **快照管理服务** | 知识库版本管理 | 生成和管理知识库快照，支持快照恢复和对比，保证测试环境一致性和可复现。 | `backend/src/service/rag_eval/run/snapshot_manager.py` |
| **6层校验编排器** | 全链路诊断编排 | 协调6层校验引擎的执行顺序，收集各层诊断结果，生成结构化的校验报告。 | `backend/src/service/rag_eval/metrics/diagnosis/orchestrator.py` |
| **6层校验引擎** | 智能调参建议生成 | 包含规则引擎、历史对比、LLM诊断、质量校验、效果校验、回归校验6层逻辑，自动生成调优建议。 | `backend/src/service/rag_eval/metrics/diagnosis/layer1_rules.py` ~ `layer6_regression.py` |
| **指标评分引擎** | 多维度量化评分 | 计算 Precision@K、Recall、MRR、NDCG、Faithfulness、AnswerRelevancy、Groundedness 等指标。 | `backend/src/service/rag_eval/metrics/scoring/facade.py`<br>`backend/src/service/rag_eval/metrics/scoring/calculators/` |
| **报告生成引擎** | 可视化评估报告 | 生成多维度指标统计报告，支持趋势分析、版本对比、调优建议展示，可导出为PDF/CSV/JSON。 | `backend/src/service/rag_eval/report/facade.py`<br>`backend/src/service/rag_eval/report/builder.py` |
| **调优引擎** | 智能调参建议 | 基于诊断结果生成调优建议，支持一键采纳、冲突检测、配置变更管理。 | `backend/src/service/rag_eval/tuning/facade.py`<br>`backend/src/service/rag_eval/tuning/advisor.py` |
| **规范驱动** | SDD 业务契约 | 所有的复杂逻辑修改必须先在 `specs/` 下写明机器可读的契约与验收标准。 | `docs/specs/` |
| **ML 评分引擎** | AHP+ML 融合评分 | XGBoost + SHAP + scikit-learn 实现 AHP 基准评分与 ML 模型融合，支持特征重要度分析。 | `backend/src/core/ml/qwen_scorer.py`<br>`backend/src/core/nodes/scoring.py` |

## 9. 前端测试与类型安全
**逻辑概述**：前端代码质量保障体系，包含单元测试、集成测试与类型检查。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **单元测试** | Vitest + RTL | 组件渲染、交互逻辑、Hook 测试。 | `frontend/src/**/*.test.tsx` |
| **类型检查** | TypeScript 严格模式 | `npm run typecheck`，禁止 `any` 类型。 | `frontend/tsconfig.json` |
| **代码规范** | ESLint 10 | `npm run lint` 自动修复格式问题。 | `frontend/package.json`（eslint 10 + typescript-eslint 插件） |
| **RAG 评估测试** | 业务逻辑测试 | 测试 RAG 评估相关的 Hooks、工具函数、实体映射。 | `frontend/src/features/rag-eval/hooks/ragEvalHooks.test.ts`<br>`frontend/src/features/rag-eval/hooks/useSSEProgress.test.ts`<br>`frontend/src/features/rag-eval/utils/sse.test.ts` |
| **实体层测试** | 类型安全测试 | 测试实体类型定义、枚举、映射器、常量。 | `frontend/src/entities/rag-eval/constants.test.ts`<br>`frontend/src/entities/rag-eval/enums.test.ts`<br>`frontend/src/entities/rag-eval/mappers.test.ts` |

---

> **💡 AI 使用提示 (For Agent)**：
> 当你收到用户的模糊需求（如"修改打分逻辑"、"调整检索权重"）时，请直接利用上表定位到**具体的代码入口**进行修改，而不要在根目录盲目 grep。
