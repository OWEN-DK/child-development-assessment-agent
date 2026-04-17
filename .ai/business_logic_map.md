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
| **配置管理器** | 动态配置与热更新 | 负责系统参数的 MySQL 持久化与 Redis 缓存。支持配置原子保存、热重载与 ConfigCache 单例管理。 | `backend/src/config/core/manager.py` |
| **提示词管理器** | 动态 Prompt 与 A/B 测试 | 统管所有大模型的 Prompt，支持变量注入、版本对比、测试沙箱以及代码引用分析。 | `backend/src/core/prompt/manager.py` |
| **LLM 工厂** | 多提供商路由与场景隔离 | 统一生成适配的 LLM 实例，支持 DashScope/OpenAI/Anthropic/DeepSeek/Ollama。支持热重载。 | `backend/src/core/llm/factory.py` |
| **三级缓存** | 性能防穿透 | 提供 `内存LRU -> Redis -> 磁盘` 的三层缓存架构，加速高频检索和配置读取。 | `backend/src/service/cache_service.py` |
| **异步任务管理** | 实时推送与并发控制 | `AsyncTaskManager` 管理后台任务，通过 SSE 向前端推送进度，支持断线重连与并发限制。 | `backend/src/core/async_task_manager.py` |

---

## 4. 前端功能模块与交互逻辑
**逻辑概述**：基于 React 19 + TypeScript 构建的单页应用，负责所有用户交互、数据可视化及配置管理。

| 模块 | 业务逻辑 | 核心页面 / 代码入口 |
|---|---|---|
| **儿童发展评估** | 表单输入与报告展示 | 收集儿童画像与运动计划，调用 Agent 接口，渲染 Markdown 报告及多维雷达图。 | `frontend/src/features/assessment/pages/HomePage.tsx`<br>`frontend/src/components/assessment/AssessmentForm.tsx` |
| **知识库与检索** | 文档导入与智能搜索 | 管理 PDF/EPUB/TXT 知识文档的上传与分块；提供支持混合检索界面。 | `frontend/src/features/documents/pages/KnowledgeBasePage.tsx`<br>`frontend/src/features/knowledge/pages/KnowledgeSearchPage.tsx` |
| **RAG 评估与调优** | 测试集构建与6层诊断 | 从文档提取或批量导入测试用例，执行并发测试。展示6层校验诊断结果与调参建议，支持一键采纳和配置对比。 | `frontend/src/features/rag-eval/RagEvaluationPage.tsx` |
| **系统配置页** | 多模式配置热更新 | 提供向导模式/专家模式，动态修改系统参数，提供冲突检测与原子保存。 | `frontend/src/pages/SystemConfigPage.tsx` |
| **提示词与监控** | 沙箱测试与全链路追踪 | 在线编辑 Prompt 并进行沙箱预览；查看 LLM 调用的 Span 层级树、耗时与成本大盘。 | `frontend/src/features/prompts/PromptManagementPage.tsx`<br>`frontend/src/features/monitoring/LLMMonitoringDashboard.tsx` |

---

## 5. 自动化测试与评估 (SDD/TDD)
**逻辑概述**：保证 RAG 检索质量和 Agent 生成质量的自动化评估体系。

| 模块 | 业务逻辑 | 代码入口 |
|---|---|---|
| **测试与报告服务** | 自动化测试集运行 | 执行并发批量测试，生成 Markdown/PDF 评估报告。 | `backend/src/service/rag_test_manager.py`<br>`backend/src/service/rag_report_service.py` |
| **6层校验引擎** | 智能调参建议生成 | `ValidationEngine` 包含规则引擎、历史对比、LLM诊断等6层逻辑，自动生成调优建议。 | `backend/src/core/tuning/rule_engine.py`<br>`backend/src/core/tuning/llm_diagnoser.py` |
| **规范驱动** | SDD 业务契约 | 所有的复杂逻辑修改必须先在 `specs/` 下写明机器可读的契约与验收标准。 | `.trae/specs/` 或 `docs/specs/` |

---

> **💡 AI 使用提示 (For Agent)**：
> 当你收到用户的模糊需求（如“修改打分逻辑”、“调整检索权重”）时，请直接利用上表定位到**具体的代码入口**进行修改，而不要在根目录盲目 grep。