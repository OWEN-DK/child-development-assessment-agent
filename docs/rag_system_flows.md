# RAG 系统核心流程详解

> 适用于技术分享 / PPT 演示材料

---

## 目录

1. [RAG 知识库上传流程](#1-rag-知识库上传流程)
2. [内容搜索流程](#2-内容搜索流程)
3. [RAG 评估流程](#3-rag-评估流程)
4. [三大流程关联关系](#4-三大流程关联关系)
5. [技术栈总览](#5-技术栈总览)

---

## 1. RAG 知识库上传流程

### 1.1 流程概览

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  文件上传    │ →  │  文档解析    │ →  │  分块索引    │ →  │  入库完成    │
│  PDF/EPUB   │    │  多模态降级  │    │  向量化存储  │    │  刷新检索器  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 1.2 详细步骤

| 阶段 | 操作 | 技术实现 | 进度范围 |
|------|------|----------|----------|
| **文件接收** | 用户上传 PDF/EPUB 文件 | FastAPI UploadFile, UUID 唯一文件名 | 0% |
| **任务创建** | 创建 TaskState（pending） | TaskStateService, Redis 持久化 | 5% |
| **文件解析** | 提取文本内容 | PyMuPDF / EbookLib / Qwen-VL 三级降级 | 10%-30% |
| **文档清洗** | 去除无效内容、标准化 | 正则清洗、章节识别 | 30%-40% |
| **语义分块** | 按语义边界切分文档 | SemanticSplitterNodeParser | 40%-60% |
| **元数据提取** | 提取主题、脑区等标签 | LLM 驱动的元数据提取 | 60%-70% |
| **向量化** | 文本转向量 | DashScope text-embedding-v4 | 70%-90% |
| **写入向量库** | 存储到 Chroma | ChromaDB (cosine 距离) | 90%-95% |
| **记录入库** | 保存文档元数据到 MySQL | SQLAlchemy ORM | 95%-98% |
| **刷新检索器** | 重新加载 BM25 + 向量检索器 | RetrieverManager.reload | 100% |

### 1.3 核心代码入口

```
Controller:  backend/src/controller/rag_controller.py
Service:     backend/src/service/rag_service.py
Ingestor:    backend/src/service/document_ingestion/book_ingestor.py
Parser:      backend/src/service/document_ingestion/document_parser.py
Chunking:    backend/src/service/document_ingestion/chunking_indexing.py
```

### 1.4 关键设计点

#### 并发控制
```
信号量 (Semaphore)
    ↓
限制同时上传任务数（可配置）
    ↓
防止资源耗尽
```

#### 断点续传
```
TaskState 持久化
    ↓
记录当前阶段（parsing/chunking/vectorizing）
    ↓
异常恢复时从断点继续
```

#### 实时进度推送
```
SSE (Server-Sent Events)
    ↓
前端实时显示：解析进度 → 分块进度 → 向量化进度
```

#### 三级降级解析
```
PyMuPDF（首选）
    ↓ 失败
EbookLib（EPUB 格式）
    ↓ 失败
Qwen-VL（扫描版 PDF，视觉大模型识别）
```

---

## 2. 内容搜索流程

### 2.1 流程概览

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  用户查询    │ →  │  查询处理    │ →  │  混合检索    │ →  │  结果返回    │
│  自然语言    │    │  重写/扩展   │    │  BM25+向量   │    │  排序/分页   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 2.2 详细步骤

| 阶段 | 操作 | 技术实现 | 说明 |
|------|------|----------|------|
| **查询接收** | 用户输入搜索词 | GET /rag/search | 支持分页参数 |
| **同义词扩展** | jieba 分词 + 同义词库 | LocalSynonymExpander | 提升召回率 |
| **BM25 检索** | 关键词匹配 | llama_index BM25Retriever | 精确匹配 |
| **向量检索** | 语义相似度 | Chroma + DashScope Embedding | 语义理解 |
| **结果融合** | RRF 算法合并 | HybridRetrievalMerger | 双路结果融合 |
| **分数校准** | Min-Max 归一化 | ScoreCalibrator | 映射到 0-100 分 |
| **结果去重** | MinHash 去重 | DedupEngine | 去除重复片段 |
| **分页截断** | 按 offset/limit 截取 | Python list slicing | 返回当前页 |

### 2.3 混合检索架构

```
                    ┌─────────────────────────────────────┐
                    │           用户查询 (Query)           │
                    └─────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │         同义词扩展 (Synonym)         │
                    │    jieba 分词 + 本地同义词库          │
                    └─────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
        ┌───────────────────────┐         ┌───────────────────────┐
        │   BM25 检索 (关键词)   │         │   向量检索 (语义)      │
        │   精确匹配            │         │   相似度计算           │
        │   Top-K 结果          │         │   Top-K 结果          │
        └───────────────────────┘         └───────────────────────┘
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      ▼
                    ┌─────────────────────────────────────┐
                    │    RRF 融合 (Reciprocal Rank Fusion) │
                    │    score = Σ 1/(k + rank_i)         │
                    └─────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │      分数校准 + Min-Max 归一化        │
                    │      映射到前端显示分数 (0-100)       │
                    └─────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │     MinHash 去重 + 分页返回           │
                    └─────────────────────────────────────┘
```

### 2.4 声明式 Pipeline（可选）

系统支持通过 YAML 配置定义检索流水线：

```yaml
# config/rag_pipeline.yaml
pipelines:
  simple:
    - name: cache_check        # 缓存检查
    - name: query_rewrite      # 查询重写
    - name: synonym_expansion  # 同义词扩展
    - name: hybrid_retrieval   # 混合检索
    - name: reranking          # Cross-Encoder 重排序
    - name: deduplication      # 去重

  complex:
    - name: query_router       # 查询路由
    - name: query_rewrite      # 查询重写
    - name: synonym_expansion  # 同义词扩展
    - name: hybrid_retrieval   # 混合检索
    - name: reranking          # 重排序
    - name: pageindex_enhancement  # PageIndex 增强
    - name: result_fusion      # 结果融合
```

### 2.5 复杂查询处理

```
复杂查询 (QueryType.COMPLEX)
    ↓
QueryDecomposer 拆解为子查询
    ↓
各子查询并行检索
    ↓
结果归并 + Reranker 精排
    ↓
返回最终结果
```

### 2.6 核心代码入口

```
Controller:    backend/src/controller/rag_controller.py
Service:       backend/src/service/rag_service.py
Retrieval:     backend/src/service/retrieval/facade.py
QueryRewriter: backend/src/service/retrieval/query_rewriter.py
ResultProc:    backend/src/service/retrieval/result_processor.py
HybridMerger:  backend/src/core/hybrid_retrieval.py
Pipeline:      backend/src/core/pipeline/orchestrator.py
```

### 2.7 关键配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rag_search_bm25_weight` | 0.4 | BM25 权重 |
| `rag_search_vector_weight` | 0.6 | 向量检索权重 |
| `rag_search_score_threshold` | 0.003 | RRF 分数阈值 |
| `rag_query_pipeline_enabled` | true | 是否启用声明式 Pipeline |
| `query_router_llm_enabled` | true | 是否启用 LLM 查询分类 |

---

## 3. RAG 评估流程

### 3.1 流程概览

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  草稿生成    │ →  │  测试运行    │ →  │  双轨评估    │ →  │  报告调优    │
│  LLM提取    │    │  并发执行    │    │  指标+诊断   │    │  一键采纳    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 3.2 六大引擎协作

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    RagEvalOrchestrator (评估编排器)                        │
│                    orchestrator.py                                        │
└──────────────────────────────────────────────────────────────────────────┘
        │              │              │              │              │
        ▼              ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ DraftEngine │ │ CaseEngine  │ │  RunEngine  │ │ MetricEngine│ │ ReportEngine│
│ 草稿引擎    │ │ 用例引擎    │ │ 运行引擎    │ │ 指标引擎    │ │ 报告引擎    │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
                                                       │
                                                       ▼
                                               ┌─────────────┐
                                               │ TuningEngine│
                                               │ 调优引擎    │
                                               └─────────────┘
```

### 3.3 Phase 1: 草稿生成

```
源文档 (PDF/EPUB)
    ↓
上传到 RAG 评估系统
    ↓
LLM 提取测试草稿
    ├── 从文档中提取问答对
    ├── 生成标准格式：问题 + 期望答案 + 上下文
    └── 批量生成（支持并发）
    ↓
忠实度验证
    ├── 检查答案是否可从上下文推导
    └── 过滤低质量草稿
    ↓
去重处理
    ├── MinHash 相似度计算
    └── 去除重复/近似草稿
    ↓
人工审核
    ├── 逐条审核
    ├── 批量通过/拒绝
    └── 编辑修改
    ↓
生成测试用例 + 测试集
```

**核心代码**:
```
Service:   backend/src/service/rag_eval/draft/facade.py
Generator: backend/src/service/rag_eval/draft/generator.py
```

### 3.4 Phase 2: 测试用例管理

```
测试用例结构:
┌─────────────────────────────────────────────────┐
│ TestCase                                        │
├─────────────────────────────────────────────────┤
│ id: 唯一标识                                    │
│ question: 测试问题                               │
│ expected_answer: 期望答案                        │
│ context: 参考上下文                              │
│ source_document: 来源文档                        │
│ tags: 标签（主题/难度等）                         │
└─────────────────────────────────────────────────┘

测试集结构:
┌─────────────────────────────────────────────────┐
│ TestSet                                         │
├─────────────────────────────────────────────────┤
│ id: 唯一标识                                    │
│ name: 测试集名称                                │
│ description: 描述                               │
│ case_ids: 关联的测试用例 ID 列表                  │
└─────────────────────────────────────────────────┘
```

**支持操作**:
- 单个/批量创建测试用例
- 从 CSV/JSON 导入
- 组织为测试集
- 导出测试集

**核心代码**:
```
Service:    backend/src/service/rag_eval/case/facade.py
Repository: backend/src/repository/rag_eval/test_case_repository.py
```

### 3.5 Phase 3: 测试运行

```
创建测试运行 (TestRun)
    ↓
收集测试用例
    ├── 从测试集加载
    └── 添加自定义用例
    ↓
创建知识库快照 (Snapshot)
    └── 保证测试期间知识库变更不影响结果
    ↓
启动后台任务 (BatchTestRunner)
    ↓
并发执行测试用例
    ├── 每个用例独立执行
    ├── 检索：调用 RAG 检索服务
    ├── 生成：调用 LLM 生成答案
    └── 记录：保存结果到数据库
    ↓
执行完成
    └── 触发 post_run_pipeline
```

**单个测试用例执行流程**:
```
TestCase
    ↓
Retrieval Function
    ├── 调用 retrieval_service.retrieve_knowledge()
    ├── 返回检索结果列表 [{id, content}, ...]
    └── 记录检索耗时
    ↓
Generation Function
    ├── 构建上下文（拼接检索结果）
    ├── 调用 LLM 生成答案
    └── 记录生成耗时
    ↓
ResultProcessor
    ├── 计算检索指标（Precision, Recall, MRR, NDCG）
    ├── 计算生成指标（Faithfulness, Relevancy, Groundedness）
    └── 保存 TestRunResult
```

**核心代码**:
```
Facade:       backend/src/service/rag_eval/run/facade.py
BatchRunner:  backend/src/service/rag_eval/run/batch_runner.py
Executor:     backend/src/service/rag_eval/run/executor.py
Snapshot:     backend/src/service/rag_eval/run/snapshot_manager.py
```

### 3.6 Phase 4: 双轨评估

#### 轨道一：指标计算

```
L1 指标（检索质量）
├── Precision@K: 前 K 个结果中相关文档的比例
├── Recall: 相关文档被检索到的比例
├── MRR (Mean Reciprocal Rank): 第一个相关结果的排名倒数
└── NDCG (Normalized Discounted Cumulative Gain): 排序质量

L2 指标（生成质量）
├── Faithfulness: 答案是否忠实于检索到的上下文
├── AnswerRelevancy: 答案与问题的相关性
└── Groundedness: 答案是否有依据

L3 指标（综合评分）
└── Overall Score: L1 + L2 加权综合
```

#### 轨道二：6 层诊断

```
Layer 1: 规则引擎 (Rules Engine)
    ├── 阈值检查：各指标是否低于阈值
    ├── 异常检测：分数分布是否异常
    └── 输出：规则命中列表

Layer 2: 历史对比 (History Comparison)
    ├── 与历史运行对比
    ├── 检测趋势（提升/下降）
    └── 输出：趋势分析

Layer 3: LLM 诊断 (LLM Diagnosis)
    ├── 分析失败用例
    ├── 识别根因（检索问题/生成问题/数据问题）
    └── 输出：根因分析报告

Layer 4: 质量校验 (Quality Check)
    ├── 结果一致性检查
    ├── 跨用例模式识别
    └── 输出：质量问题列表

Layer 5: 效果校验 (Effect Validation)
    ├── 改进效果评估
    ├── 配置变更影响分析
    └── 输出：效果评估报告

Layer 6: 回归校验 (Regression Check)
    ├── 防止性能退化
    ├── 与基线对比
    └── 输出：回归警告
```

**核心代码**:
```
Orchestrator:  backend/src/service/rag_eval/metrics/diagnosis/orchestrator.py
Layer1-Rules:  backend/src/service/rag_eval/metrics/diagnosis/layer1_rules.py
Layer2-Hist:   backend/src/service/rag_eval/metrics/diagnosis/layer2_history.py
Layer3-LLM:    backend/src/service/rag_eval/metrics/diagnosis/layer3_llm.py
Layer4-Quality:backend/src/service/rag_eval/metrics/diagnosis/layer4_quality.py
Layer5-Effect: backend/src/service/rag_eval/metrics/diagnosis/layer5_effect.py
Layer6-Regress:backend/src/service/rag_eval/metrics/diagnosis/layer6_regression.py
Scoring:       backend/src/service/rag_eval/metrics/scoring/facade.py
```

### 3.7 Phase 5: 报告生成

```
测试运行完成
    ↓
ReportBuilder.build(run_id)
    ├── 收集所有测试结果
    ├── 计算统计指标
    ├── 生成诊断详情
    ├── 识别 Bad Cases
    └── 生成调优建议
    ↓
ReportRenderer.render(data)
    └── 渲染为 Markdown 格式
    ↓
保存到数据库
    ├── 指标数据 (metrics_json)
    ├── 诊断结果 (diagnosis_json)
    ├── Bad Cases (bad_cases_json)
    ├── 调优建议 (suggestions_json)
    └── Markdown 内容 (markdown_content)
    ↓
支持导出
    ├── PDF 报告
    ├── CSV 数据
    └── JSON 数据
```

**报告内容结构**:
```
1. 执行摘要
   ├── 总体评分
   ├── 测试用例数/通过数
   └── 关键发现

2. 指标详情
   ├── L1 检索指标
   ├── L2 生成指标
   └── L3 综合指标

3. 诊断分析
   ├── 6 层诊断结果
   ├── 根因分析
   └── 趋势分析

4. Bad Cases
   ├── 失败用例列表
   ├── 失败原因分析
   └── 改进建议

5. 调优建议
   ├── 配置调整建议
   ├── 提示词优化建议
   └── 数据改进建议
```

**核心代码**:
```
Facade:   backend/src/service/rag_eval/report/facade.py
Builder:  backend/src/service/rag_eval/report/builder.py
Renderer: backend/src/service/rag_eval/report/renderer.py
```

### 3.8 Phase 6: 调优建议

```
诊断结果
    ↓
TuningAdvisor.generate_suggestions()
    ├── 配置调整建议
    │   ├── 检索参数（Top-K, 权重）
    │   ├── 分块参数（chunk_size, overlap）
    │   └── 重排序参数（模型选择）
    │
    ├── 提示词优化建议
    │   ├── 查询重写提示词
    │   ├── 生成提示词
    │   └── 元数据提取提示词
    │
    └── 数据改进建议
        ├── 补充知识库内容
        ├── 优化文档质量
        └── 调整测试用例
    ↓
冲突检测
    ├── 检查建议间是否冲突
    └── 标记冲突项
    ↓
用户操作
    ├── 一键采纳 → 自动应用配置变更
    ├── 拒绝 → 忽略建议
    ├── 忽略 → 标记为已读
    └── 手动调整 → 编辑后应用
    ↓
配置版本管理
    ├── 保存配置快照
    ├── 支持版本回滚
    └── 变更历史追踪
```

**核心代码**:
```
Facade:   backend/src/service/rag_eval/tuning/facade.py
Advisor:  backend/src/service/rag_eval/tuning/advisor.py
```

---

## 4. 三大流程关联关系

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RAG 系统整体架构                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   知识库上传流程     │     │    内容搜索流程      │     │    RAG 评估流程      │
│                     │     │                     │     │                     │
│  PDF/EPUB → 解析    │     │  Query → 检索       │     │  草稿 → 测试 → 评估  │
│  → 分块 → 向量化    │ ──→ │  → BM25 + 向量      │ ──→ │  → 指标 → 诊断      │
│  → Chroma 存储      │     │  → RRF 融合         │     │  → 报告 → 调优      │
│                     │     │  → 结果返回         │     │                     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              共享基础设施                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  Chroma 向量库  │  MySQL 数据库  │  Redis 缓存  │  LLM 服务  │  SSE 推送    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 数据流向

```
上传流程                      搜索流程                      评估流程
    │                            │                            │
    ▼                            ▼                            ▼
┌─────────┐                ┌─────────┐                ┌─────────┐
│ Chroma  │ ◄───────────── │ Chroma  │ ◄───────────── │ Chroma  │
│ 向量库  │    写入索引      │ 向量库  │    检索查询      │ 向量库  │
└─────────┘                └─────────┘                └─────────┘
    │                            │                            │
    ▼                            ▼                            ▼
┌─────────┐                ┌─────────┐                ┌─────────┐
│  MySQL  │ ◄───────────── │  MySQL  │ ◄───────────── │  MySQL  │
│  元数据  │    文档记录      │  元数据  │    查询日志      │  测试数据 │
└─────────┘                └─────────┘                └─────────┘
```

### 4.3 协作关系

| 流程 | 提供能力 | 依赖关系 |
|------|----------|----------|
| **上传流程** | 构建知识库索引 | 无依赖，是基础 |
| **搜索流程** | 智能检索能力 | 依赖上传流程构建的索引 |
| **评估流程** | 质量保障与调优 | 依赖搜索流程进行测试，反馈优化上传和搜索配置 |

### 4.4 闭环优化

```
┌─────────────────────────────────────────────────────────────────┐
│                         闭环优化流程                              │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────┐
    │  知识库上传  │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │  内容搜索    │ ◄─────────────────────────────────┐
    └──────┬──────┘                                   │
           │                                          │
           ▼                                          │
    ┌─────────────┐      ┌─────────────┐              │
    │  RAG 评估    │ ──→  │  调优建议    │              │
    └─────────────┘      └──────┬──────┘              │
                                │                     │
                                ▼                     │
                         ┌─────────────┐              │
                         │  配置变更    │ ─────────────┘
                         │  提示词优化  │     应用优化
                         │  数据补充    │
                         └─────────────┘
```

---

## 5. 技术栈总览

### 5.1 后端技术栈

| 组件 | 技术选型 | 用途 |
|------|----------|------|
| **Web 框架** | FastAPI | REST API 服务 |
| **RAG 框架** | LlamaIndex | 文档索引与检索 |
| **向量存储** | Chroma | 本地持久化向量库 |
| **Embedding** | DashScope text-embedding-v4 | 文本向量化 |
| **BM25 检索** | llama_index BM25 + jieba | 关键词检索 |
| **重排序** | BAAI/bge-reranker-v2-m3 | Cross-Encoder 精排 |
| **PDF 解析** | PyMuPDF + Qwen-VL | 多模态文档解析 |
| **语义分块** | SemanticSplitterNodeParser | 智能分块 |
| **数据库** | MySQL 5.7 | 元数据持久化 |
| **缓存** | Redis 7.0 | 高频数据缓存 |
| **任务队列** | APScheduler + AsyncTaskManager | 后台任务管理 |
| **实时推送** | SSE (Server-Sent Events) | 进度推送 |

### 5.2 算法与模型

| 算法/模型 | 用途 | 说明 |
|-----------|------|------|
| **RRF** | 结果融合 | Reciprocal Rank Fusion, 融合 BM25 和向量检索结果 |
| **MinHash** | 去重 | 计算文本相似度，去除重复片段 |
| **AHP + ML** | 评分 | 层次分析法 + XGBoost 融合评分 |
| **Cross-Encoder** | 重排序 | BGE Reranker, 精细化排序 |
| **TextRank** | 摘要 | 本地文本摘要生成 |

### 5.3 前端技术栈

| 组件 | 技术选型 | 用途 |
|------|----------|------|
| **框架** | React 19 + TypeScript | UI 开发 |
| **UI 库** | Ant Design 6 + ProComponents | 组件库 |
| **状态管理** | Zustand 5 | 复杂状态管理 |
| **数据请求** | TanStack Query 5 | 服务端状态管理 |
| **图表** | @ant-design/charts | 数据可视化 |
| **路由** | React Router 7 | 页面路由 |

---

## 附录：API 端点汇总

### 知识库管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/rag/upload` | POST | 上传文档 |
| `/rag/documents` | GET | 列出文档 |
| `/rag/documents/{filename}` | DELETE | 删除文档 |
| `/rag/status` | GET | 服务状态 |
| `/rag/tasks` | GET | 任务列表 |
| `/rag/tasks/{task_id}` | GET | 任务状态 |
| `/rag/tasks/{task_id}/cancel` | POST | 取消任务 |

### 内容搜索

| 端点 | 方法 | 说明 |
|------|------|------|
| `/rag/search` | GET | 搜索内容 |
| `/rag/documents/{file_hash}/chunks` | GET | 文档分块 |
| `/rag/chunks/{chunk_id}` | GET | 分块详情 |

### RAG 评估

| 端点前缀 | 说明 |
|----------|------|
| `/api/v1/rag/eval/source-documents/*` | 源文档管理 |
| `/api/v1/rag/eval/drafts/*` | 草稿管理 |
| `/api/v1/rag/eval/test-cases/*` | 测试用例 |
| `/api/v1/rag/eval/test-sets/*` | 测试集 |
| `/api/v1/rag/eval/runs/*` | 测试运行 |
| `/api/v1/rag/eval/reports/*` | 评估报告 |
| `/api/v1/rag/eval/tuning/*` | 调优建议 |
| `/api/v1/rag/eval/snapshots/*` | 快照管理 |

---

> 文档生成时间: 2026-05-14
> 基于代码版本: main branch
