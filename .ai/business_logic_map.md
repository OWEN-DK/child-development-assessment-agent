# 核心业务逻辑导航 (Business Logic Map)

为了让 AI 和开发者在接手任务时能够快速定位代码并理解“这一块是干什么的”，本文档按业务模块梳理了系统的核心逻辑和对应代码入口。

当你需要修改某个具体功能时，请直接查阅下方的对应模块。

---

## 1. Agent 评估工作流 (LangGraph)
**逻辑概述**：控制儿童评估报告生成的完整有向无环图（DAG）。状态数据通过 `AgentState` 对象在各个节点间流转。

| 步骤 | 节点名称 | 业务逻辑 | 代码入口 |
|---|---|---|---|
| **核心编排** | `create_agent_graph` | 定义图的边和节点顺序。 | `backend/src/core/graph.py` |
| **NodePre** | `PreprocessingNode` | 预处理：压缩用户上传的历史训练记录（如运动数据）为统计特征，减少 Token 消耗。 | `backend/src/core/nodes/preprocessing.py` |
| **Node1** | `ValidationNode` | 校验：清洗并标准化家长输入的“拟定运动计划”，智能补全缺失的参数。 | `backend/src/core/nodes/validation.py` |
| **Node2** | `AssessmentNode` | 评估：将家长描述映射到感统维度，对比同龄儿童里程碑，生成儿童发展状态 (`child_state`)。 | `backend/src/core/nodes/assessment.py` |
| **Node3** | `RetrievalNode` | 检索：根据儿童画像和拟定计划，在向量库中精准检索科学理论依据。 | `backend/src/core/nodes/retrieval.py` |
| **Node4** | `ScoringNode` | 评分：结合客观检索结果(AHP算法)与机器学习模型(QwenScorer)进行多维打分。 | `backend/src/core/nodes/scoring.py` |
| **Node5** | `ReportingNode` | 报告：汇总上述所有信息，流式生成家长友好的 Markdown 报告。 | `backend/src/core/nodes/reporting.py` |

---

## 2. RAG 知识库与检索系统
**逻辑概述**：负责书籍/PDF的解析入库，以及根据用户 Query 进行混合检索。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **门面调度** | RAG 聚合入口 | 暴露统一的搜索和状态查询接口给 Controller。 | `backend/src/service/rag_service.py` |
| **文档导入流水线** | 多模态解析与分块 | 负责 PDF/EPUB 的解析（支持视觉大模型兜底），使用语义分块，提取主题/脑区等元数据，存入 Chroma 向量库。支持断点续传。 | `backend/src/service/document_ingestion_service.py` |
| **知识检索流水线** | 混合检索与重排序 | 基于 `rag_pipeline.yaml` 驱动。执行查询重写 -> 同义词扩展 -> 年龄过滤 -> BM25+向量混合检索 -> CrossEncoder重排序。 | `backend/src/service/retrieval_service.py` |

---

## 3. 核心基础设施与动态调度
**逻辑概述**：支撑系统高性能、高可用运行的底层组件，完全解耦且配置驱动。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **配置管理器** | 动态配置与热更新 | 负责系统参数（如检索权重、阈值）的 MySQL 持久化与 Redis 缓存。支持配置版本切换和 EventBus 热重载。 | `backend/src/config/core/manager.py` |
| **提示词管理器** | 动态 Prompt 与 A/B 测试 | 统管所有大模型的 Prompt，支持变量注入、版本回滚以及基于流量比例的 A/B 测试。 | `backend/src/core/prompt/manager.py` |
| **LLM 工厂** | 场景隔离的模型适配 | 统一生成适配 LangChain 或 LlamaIndex 的模型实例。定义了 9 大业务场景，支持热重载清理旧实例。 | `backend/src/core/llm/factory.py` |
| **三级缓存** | 性能防穿透 | 提供 `内存LRU -> Redis -> 磁盘` 的三层缓存架构，加速高频检索和配置读取。 | `backend/src/service/cache_service.py` |

---

## 4. 前端功能模块与交互逻辑
**逻辑概述**：基于 React 19 + TypeScript 构建的单页应用，负责所有用户交互、数据可视化及配置管理。

| 模块 | 业务逻辑 | 核心页面 / 代码入口 |
|---|---|---|
| **儿童发展评估** | 表单输入与报告展示 | 收集儿童画像与运动计划，调用 Agent 接口，渲染 Markdown 报告及多维雷达图。 | `frontend/src/features/assessment/pages/HomePage.tsx`<br>`frontend/src/components/assessment/AssessmentForm.tsx` |
| **知识库与检索** | 文档导入与智能搜索 | 管理 PDF/EPUB 知识文档的上传与分块；提供支持 BM25 + 向量语义的混合检索界面。 | `frontend/src/features/documents/pages/KnowledgeBasePage.tsx`<br>`frontend/src/features/knowledge/pages/KnowledgeSearchPage.tsx` |
| **RAG 自动化测试** | 测试集构建与运行结果对比 | 批量导入测试用例，从书籍自动生成测试草稿，执行并发测试并可视化展示大模型打分结果与 Bad Case。 | `frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx` |
| **系统与提示词配置** | 在线调优与版本控制 | 动态修改系统运行参数（如检索权重）；在线编辑 Prompt，配置 A/B 测试流量分配及版本回滚。 | `frontend/src/pages/SystemConfigPage.tsx`<br>`frontend/src/features/prompts/PromptManagementPage.tsx` |
| **LLM 监控大盘** | 调用与成本统计 | 实时汇总大模型在各业务场景下的调用次数、Token 消耗、平均耗时与错误告警。 | `frontend/src/features/monitoring/LLMMonitoringDashboard.tsx` |

---

## 5. 自动化测试与评估 (SDD/TDD)
**逻辑概述**：保证 RAG 检索质量和 Agent 生成质量的自动化评估体系。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **测试管理器** | 自动化测试集运行 | 支持从 JSON 批量导入或由 LLM 从文档自动提取测试用例。执行并发批量测试，并对比不同配置版本的质量差异。 | `backend/src/service/rag_test_manager.py` |
| **规范驱动** | SDD 业务契约 | 所有的复杂逻辑修改（如评分算法变更）必须先在 `specs/` 下写明机器可读的契约与验收标准。 | `.trae/specs/` 或 `docs/specs/` |

---

> **💡 AI 使用提示 (For Agent)**：
> 当你收到用户的模糊需求（如“修改打分逻辑”、“调整检索权重”）时，请直接利用上表定位到**具体的代码入口**进行修改，而不要在根目录盲目 grep。