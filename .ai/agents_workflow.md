# Agent 系统架构

本文档定义了儿童发展评估系统的 Agent 架构。系统包含两大 Agent：**评估 Agent**（6 节点 LangGraph 流水线）和**知识问答 Agent**（v1: 13 节点 / v2: 16 节点 + Neo4j 三层架构）。两者均基于 **LangGraph** 编排。

---

## 1. 评估 Agent 工作流

`网关 (Gateway)` → `预处理 (Preprocessing)` → `校验 (Validation)` → `评估 (Assessment)` → `检索 (Retrieval)` → `评分 (Scoring)` → `报告生成 (Report Generation)`

### 1.1 状态管理 (AgentState)

`AgentState` 是在节点间传递的共享内存结构。

```python
class AgentState(BaseModel):
    input_text: Optional[str] = None
    child_profile: ChildProfile
    proposed_plan: ProposedPlan
    child_state: Optional[ChildState] = None
    condensed_context: Optional[CondensedContext] = None
    history_context: Optional[List[HistoryRecord]] = Field(default_factory=list)
    retrieved_docs: List[KnowledgeItem] = Field(default_factory=list)
    evaluation_result: Optional[EvaluationResult] = None
    final_report: Optional[FinalReport] = None
    messages: List[Dict[str, str]] = Field(default_factory=list)
    report_prompts: Optional[List[str]] = Field(None)
    is_streaming: bool = Field(False)
```

### 1.2 节点定义

| 步骤 | 节点 | 角色 | 职责 | 代码入口 |
|------|------|------|------|----------|
| NodePre | `PreprocessingNode` | 上下文窗口优化器 | 将历史数据压缩为统计特征，降低 Token 消耗 | `backend/src/core/nodes/preprocessing.py` |
| Node1 | `ValidationNode` | 把关人 | 校验 Schema、标准化数据、智能补全参数 | `backend/src/core/nodes/validation.py` |
| Node2 | `AssessmentNode` | 画像师 | 映射感统维度，对标年龄里程碑，生成 `child_state` | `backend/src/core/nodes/assessment.py` |
| Node3 | `RetrievalNode` | 知识专家 | 在向量库中精准检索科学理论依据 | `backend/src/core/nodes/retrieval.py` |
| Node4 | `ScoringNode` | 裁判 | AHP+ML 多维打分（XGBoost + SHAP） | `backend/src/core/nodes/scoring.py` |
| Node5 | `ReportingNode` | 撰稿人 | 汇总信息，流式生成 Markdown 报告 | `backend/src/core/nodes/reporting.py` |

- **核心编排**: `create_agent_graph()` 定义图的边和节点顺序 → `backend/src/core/graph.py`
- **注意**: Node3 检索使用 `KnowledgeRetriever`（RAG 双流水线），详细检索流程参阅 `.ai/rag_pipeline.md`

---

## 2. 知识问答 Agent 工作流

知识问答系统是独立于评估 Agent 的 LangGraph 图，负责根据用户自然语言问题，匹配书籍、检索知识、生成结构化的 5 节报告。

### 2.1 版本概览

| 版本 | 节点数 | 特性 | 选择条件 |
|------|--------|------|----------|
| **v1** | 13 | 纯 Chroma 向量检索 + LazyGraphRAG | `NEO4J_ENABLED=False` |
| **v2** | 16 | 三层架构（Neo4j + Chroma + LazyGraphRAG）+ Bundle 统一检索 | `NEO4J_ENABLED=True` |

版本选择在 `KnowledgeQAService.__init__` 中根据 `neo4j_settings.neo4j_enabled` 特性开关自动决定。此外还支持 Neo4j 灰度发布（`neo4j_rollout_percentage`），通过 `question_id` 的 MD5 hash 稳定路由。

### 2.2 状态管理 (KnowledgeQAState)

```python
class KnowledgeQAState(BaseModel):
    # === 输入 ===
    question: str                           # 用户问题
    matched_book_ids: list[str]             # 匹配的书籍 ID
    matched_books_detail: list[MatchedBook] # 匹配详情（展示用）
    section_queries: dict[int, str]         # 逐节搜索 query

    # === 节点产出 ===
    sections: dict[int, SectionOutput]      # 1-5 节输出
    child_profile: dict                     # 儿童档案
    contradictions: list[dict]              # 跨书矛盾列表

    # === Bundle (v2) ===
    knowledge_bundle: KnowledgeBundle       # 不可变知识产物

    # === 自定义知识 ===
    custom_knowledge_context: str           # 自定义知识命中上下文
    custom_knowledge_entities: list[str]    # 自定义知识关联实体
    fast_knowledge_hit: bool                # 是否命中

    # === Neo4j (v2) ===
    neo4j_knowledge: dict                   # Neo4j 查询结果
    three_layer_synthesis: dict             # 三层知识综合结果

    # === 控制 ===
    errors: list[str]
    retry_counts: dict[str, int]
    s4_retry_count: int                     # S4 链路重试次数
    partial: bool                           # 是否部分完成
```

### 2.3 v1 图拓扑（13 节点）

```
match_books
    ├── (无匹配) → finalize → END
    └── (有匹配) → prefetch_context → analyze_child → identify_problems
        → recommend_types → plan_outline → plan_expand_parallel
        → plan_assemble
            ├── (需重试) → plan_outline (最多 2 次)
            └── (完成) → generate_s4_citations → contradiction_audit
                → conclusion → verify_citations → finalize → END
```

| 序号 | 节点 | 职责 |
|------|------|------|
| 1 | `match_books` | 直接搜索 Chroma + LLM 结构化匹配书籍（单次 27B 调用） |
| 2 | `prefetch_context` | 预取运动清单上下文、RAG 搜索结果缓存 |
| 3 | `analyze_child` | LLM 解析儿童年龄、性别、行为特征 → `child_profile` |
| 4 | `identify_problems` | LLM 识别问题列表 + 根因 → S2 `structured_data` |
| 5 | `recommend_types` | LLM 推荐运动类型（primary/secondary/supplementary） |
| 6 | `plan_outline` | LLM 生成运动方案大纲 |
| 7 | `plan_expand_parallel` | 并行扩展各运动条目的详细信息 |
| 8 | `plan_assemble` | 组装完整运动方案 + 权威清单校验 |
| 9 | `generate_s4_citations` | 为 S4 方案生成引用 |
| 10 | `contradiction_audit` | 跨书籍矛盾审计 |
| 11 | `conclusion` | 综合结论生成（S5） |
| 12 | `verify_citations` | 规则校验 + 降级信号检测 + 运动清单约束验证 |
| 13 | `finalize` | 汇总最终状态 |

**代码入口**: `backend/src/core/knowledge_qa/_assembly.py`

### 2.4 v2 图拓扑（16 节点，三层架构 + Bundle）

```
match_books
    ├── (无匹配) → finalize → END
    └── (有匹配) → fast_knowledge_match → prefetch_context
        → analyze_child_v2 → identify_problems_v2
        → build_bundle          ← ★ Phase 1: 统一检索
        → recommend_types_v2 → plan_outline_v2 → plan_expand_parallel_v2
        → plan_assemble
            ├── (需重试) → plan_outline_v2
            └── (完成) → generate_s4_citations
                → knowledge_synthesis_v2    ← ★ 三层综合
                → conclusion → verify_citations → finalize → END
```

**v2 相对 v1 的关键变更:**

| 变更 | 说明 |
|------|------|
| `fast_knowledge_match` | 新增节点，三通道匹配自定义知识（keyword→pattern→semantic），3 秒超时降级 |
| `build_bundle` | **Phase 1 核心**——S2 完成后统一检索，产出不可变 `KnowledgeBundle` |
| `_v2` 后缀节点 | analyze_child / identify_problems / recommend_types / plan_outline / plan_expand_parallel 的 v2 版本，消费 Bundle 零搜索 |
| `knowledge_synthesis_v2` | 替代 `contradiction_audit`，从 Bundle 提取三层综合（共识/互补/冲突） |
| 移除 `query_neo4j_graph` | 独立 Neo4j 查询节点被 `build_bundle` 内化 |

**代码入口**: `backend/src/core/knowledge_qa/_assembly_v2.py`

### 2.5 KnowledgeBundle（统一检索产物）

Bundle 是 v2 架构的核心抽象——一次检索的完整不可变知识产物，后续 Section 节点只消费不搜索。

```
KnowledgeBundle (frozen=True)
├── Layer 0: custom_rules      ← 自定义规则（最高优先级）
├── Layer 1: neo4j_entities    ← Neo4j 图谱实体（权威源）
│            neo4j_relations   ← 关系
│            cross_book_*      ← 跨书冲突/共识
├── Layer 2: passages          ← Chroma 原文证据
├── book_index                 ← 书籍白名单
├── passage_index              ← 段落 ID → Passage 映射
├── priority_conflicts         ← L1 vs L2 矛盾标记
└── retrieval_stats            ← 检索质量统计
```

**构建流程** (`bundle_builder.py`):
1. **Step 1a**: Neo4j 增强查询 — S2 problems + custom_entities 作为种子，1-2 跳扩展
2. **Step 1b**: Chroma 批量搜索 — entity_seeds 并行搜索，支持 source_para_ids 直接召回
3. **Step 1c**: LazyGraphRAG 增强遍历 — 社区树遍历补充上下文
4. **Step 1d**: 组装 Bundle — 去重（精确 + SequenceMatcher 近似）、截断、冲突检测

**消费模式** (`bundle_consumer.py`):
- `extract_for_section(bundle, section_index)` — 按节需求提取 passages（各节有配额）
- `build_priority_context(bundle, passages, ...)` — 构造 L0→L1→L2 优先级上下文注入 LLM

**配置开关**: `bundle_config.py` — 支持全局开关、Phase 1/2/3 独立开关、流量比例灰度

### 2.5 节点代码入口汇总

| 模块 | 文件路径 |
|------|----------|
| **v1 节点** | `backend/src/core/knowledge_qa/nodes/` |
| **v2 节点** | `backend/src/core/knowledge_qa/nodes_v2/` |
| **Bundle 数据模型** | `backend/src/core/knowledge_qa/bundle.py` |
| **Bundle 构建器** | `backend/src/core/knowledge_qa/bundle_builder.py` |
| **Bundle 消费器** | `backend/src/core/knowledge_qa/bundle_consumer.py` |
| **Bundle 配置** | `backend/src/core/knowledge_qa/bundle_config.py` |
| **自定义知识匹配** | `backend/src/core/knowledge_qa/nodes/fast_knowledge_match.py` |
| **三层知识综合** | `backend/src/core/knowledge_qa/nodes_v2/knowledge_synthesis_v2.py` |
| **Neo4j 增强查询** | `backend/src/core/knowledge_qa/neo4j/enhanced_query.py` |
| **引用核验** | `backend/src/core/knowledge_qa/nodes/verify_citations.py` |

---

## 3. 自定义知识系统

独立于 RAG 和知识图谱的最高优先级知识注入机制。

### 3.1 三通道匹配引擎

```
用户问题 → [keyword 精确匹配] → 命中 → 注入 L0 优先级
                ↓ 未命中
         [pattern 正则匹配] → 命中 → 注入 L0 优先级
                ↓ 未命中
         [semantic 语义匹配] → 命中 → 注入 L0 优先级
                ↓ 未命中
         继续正常流程
```

- **keyword**: MySQL 索引精确匹配
- **pattern**: 正则触发模式匹配（覆盖口语化变体）
- **semantic**: Embedding cosine ≥ 0.80

### 3.2 数据存储

- **Neo4j**: `CustomRule` 节点存储完整内容 + 关联实体
- **MySQL**: 关键词/正则索引 + embedding
- **双写**: 上传时同步写入 Neo4j 和 MySQL

### 3.3 代码入口

| 模块 | 文件路径 |
|------|----------|
| 自定义知识服务 | `backend/src/service/custom_knowledge_service.py` |
| 自定义知识控制器 | `backend/src/controller/custom_knowledge_controller.py` |
| 自定义知识 Repository | `backend/src/repository/custom_knowledge_repository.py` |
| 快速匹配节点 | `backend/src/core/knowledge_qa/nodes/fast_knowledge_match.py` |

---

## 4. 专家反馈循环 (未实现 - 规划中)
- **状态**: 尚未实现，当前图为纯线性 DAG，无反馈边。
- **规划职责**: 人在回路审核员，事后审查分数以微调系统。
- **规划动作**: 标记 Bad Case，提供修正分，更新金标准数据集。
