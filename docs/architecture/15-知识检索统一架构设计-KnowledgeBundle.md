# 知识检索统一架构设计 — KnowledgeBundle

> **版本**: v1.1
> **日期**: 2026-06-02
> **状态**: 📝 设计文档（已评审，已修订）
> **依赖**: [03-Phase3](03-Phase3-Agent引擎改造.md)、[07-D2G](07-知识图谱直提方案-D2G.md)、[09-自定义知识](09-自定义知识匹配方案.md)、[12-D2G修复](12-D2G跨章连通性修复方案.md)、[13-跨书融合](13-跨书知识融合方案-v2.md)
> **替代**: 当前分散在各节点中的搜索逻辑（`_direct_search`、`_analyze_and_search_books` 等）
> **设计原则**: 检索与生成解耦——检索一次产出不可变 KnowledgeBundle，后续所有 LLM 节点只消费不搜索

---

## 1. 问题诊断

### 1.1 当前架构的根因

详见 [14-知识问答全流程问题审查清单](14-知识问答全流程问题审查清单.md)。一句话概括：

> **检索与生成过度耦合**——搜索逻辑分散在 6 个文件、8-20 次独立 HTTP 调用，导致引用不可溯源、校验无锚点、知识源优先级无法贯彻。

| 症状 | 直接原因 | 根因 |
|------|---------|------|
| 同一 question+book_ids 被搜索 8-20 次 | `_run_section_node`、`plan_outline_node`、`plan_expand_parallel_node`、`generate_s4_citations_node` 各自独立调用 `_direct_search` | 检索未集中 |
| LLM 编造不存在的 book_title | `citations` 是自由文本，无白名单强制校验 | 引用无锚点 |
| 自定义规则命中后 LLM 仍可能忽略 | 规则只是拼在 prompt 前面，无结构性强制优先级 | 优先级无机制保障 |
| Neo4j 知识未被 LazyGraphRAG 使用 | `query_neo4j_graph` 和 `prefetch_context` 并行但独立 | 知识源未融合 |
| 跨书关系数据存在但知识问答未消费 | `query_dispatcher` 查了跨书关系，但后续节点未使用 | 数据有但链路断 |

### 1.2 矛盾分析结论

主要矛盾：**检索与生成的耦合度**。解决了它，其他矛盾（召回/精准、引用可信度、上下文预算、校验深度）全部随之缓解。

---

## 2. 业内参考

| 方案 | 核心思想 | 本项目借鉴 |
|------|---------|-----------|
| **Microsoft GraphRAG** | 实体提取→建图→社区检测→层级摘要。查询时做社区树遍历 + LLM 相关性判定 | 已有 LazyGraphRAG 作为社区遍历引擎 |
| **SAP Hybrid Retrieval** (arXiv:2507.03226) | 多粒度 embedding（实体/块/关系）+ 向量找种子→图 1-2 跳扩展→RRF 融合 | **图增强向量检索**：用 Neo4j 实体引导 LazyGraphRAG 遍历，用 Neo4j 关系邻居扩展搜索上下文 |
| **Agentic KG / CFR** (arXiv:2604.14220) | 图是所有知识的权威来源。引用可审计追踪到图中的实体和关系。95% 正确率 vs 25% 向量基线，0% 幻觉 | **图为准**：当 Neo4j 实体关系与 Chroma 原文矛盾时，以图谱为准。引用必须能追溯到 Graph 中的实体或 source 段落 |
| **Rule-First Router** (Strata RFC #1270) | 规则优先匹配，命中直接返回，不触发检索 | **优先级硬编码**：CustomRule > Neo4j > Chroma，不是软提示 |

---

## 3. 核心设计

### 3.1 一句话设计

**检索与生成解耦：match_books 之后，统一执行一次深度检索（规则 + Neo4j + Chroma + LazyGraphRAG），产出不可变的 KnowledgeBundle，后续 5 个 Section 节点纯消费，不再搜索。**

### 3.2 架构对比

```
当前（问题架构）:
  match_books → search ─┐
  fast_match             │
  query_neo4j            │  同一个 question+book_ids
  prefetch     → search ─┤  被 HTTP 搜索了 8-20 次
  S1           → search ─┤  LLM 编造的 book_title 无人校验
  S2           → search ─┤
  S3           → search ─┤
  S4-outline   → search ─┤
  S4-expand    → search × N 组 ─┤
  S4-citations → search ─┤
  S5           → search ─┘

目标架构:
  match_books ─┐
               │
               ├─ Phase 0: fast_knowledge_match（规则优先）
               │     custom_rules + associated_entities
               │
               ├─ Phase 1: build_knowledge_bundle（统一检索，一次性）
               │     ├─ 1a. Neo4j 查询（实体 + 关系 + 跨书 + source）
               │     ├─ 1b. Chroma 批量搜索（被 Neo4j 实体增强的 queries）
               │     └─ 1c. LazyGraphRAG 增强遍历（被 Neo4j 实体引导）
               │     → KnowledgeBundle（不可变）
               │
               ├─ Phase 2: S1→S2→S3→S4→conclusion（零搜索）
               │     每节从 Bundle 按需切片提取
               │     LLM 只能引用 Bundle 中的内容
               │
               └─ Phase 3: verify_citations（图谱增强校验）
                     ├─ 白名单: book_title ∈ Bundle.book_index
                     ├─ 溯源: excerpt ⊆ Bundle.passage_index
                     ├─ 图谱验证: 引用实体在 Neo4j 存在？
                     └─ 冲突检测: 引用与图谱关系矛盾？
```

### 3.3 三层优先级体系

| 层 | 来源 | 优先级 | 机制 | 在 prompt 中的效果 |
|----|------|--------|------|-------------------|
| **L0** | CustomRule | **最高（OVERRIDE）** | 放在 prompt 最前面，标注"⚡ 以下为专家知识，必须优先采纳。如有冲突，以下内容具有最高权威" | 结构化注入——不仅是文本，还携带 `OVERRIDES`/`ENHANCES` 关系指向的 Neo4j 实体 ID |
| **L1** | Neo4j 图谱 | **高（权威源）** | 实体属性 + 关系邻居 + 跨书共识/冲突。标注"📊 知识图谱权威数据" | 当 L0 未覆盖某话题时，L1 是最终权威。L1 与 L2 矛盾 → 取 L1 |
| **L2a** | Neo4j 实体的 source 原文 | **中（图验证过）** | 从 Neo4j 实体节点反查 source 字段或通过 CONTAINS_ENTITY 关系找到对应原文段落 | 标注"📖 知识图谱关联原文"——比未验证原文有更高的可信度权重 |
| **L2b** | Chroma 向量原文 | **中（未经图验证）** | Chroma 搜索命中的原文 chunks，标注"📄 知识库原文" | 当无 L1 覆盖时使用。提供 excerpt 素材 |
| **L3** | LazyGraphRAG 社区上下文 | **补充** | 社区检测产出的层级摘要 + 社区成员关系。标注"🔍 关联知识上下文" | 高层视角——用于理解概念的全书/跨书脉络，而非具体的 excerpt |

---

## 4. KnowledgeBundle 数据模型

### 4.1 核心结构

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)  # frozen=True 强制不可变——构建后任何修改都会触发 FrozenInstanceError
class KnowledgeBundle:
    """一次检索的完整知识产物，不可变。"""

    # ── 元数据 ──
    question: str
    matched_book_ids: list[str]
    generated_at: str  # ISO timestamp

    # ── Layer 0: 自定义规则（最高优先级）──
    custom_rules: list[CustomRuleMatch] = field(default_factory=list)
    # 命中 → custom_knowledge_context + custom_knowledge_entities 已设置

    # ── Layer 1: Neo4j 图谱（权威源）──
    neo4j_entities: dict[str, list[GraphEntity]] = field(default_factory=dict)
    # key: entity_type (e.g. "Problem", "Solution", "Exercise")
    neo4j_relations: list[GraphRelation] = field(default_factory=list)
    # 实体间的关系（包含跨书关系）
    cross_book_conflicts: list[CrossBookConflict] = field(default_factory=list)
    # 两书对同一实体的冲突观点
    cross_book_consensus: list[CrossBookConsensus] = field(default_factory=list)
    # 跨书共识/互补关系（解决 P1-8：S1-S4 节点也消费跨书数据）

    # ── Layer 2: 原文证据 ──
    passages: list[Passage] = field(default_factory=list)
    # 去重 + 优先级排序后的全部原文段落

    # ── 白名单索引（硬约束）──
    book_index: dict[str, BookMeta] = field(default_factory=dict)
    # "跑步改造大脑" → BookMeta(title, chapters, entity_count)
    passage_index: dict[str, Passage] = field(default_factory=dict)
    # passage_id → Passage（O(1) 查找，用于 excerpt 校验）

    # ── 冲突标记 ──
    priority_conflicts: list[PriorityConflict] = field(default_factory=list)
    # L1 与 L2 矛盾之处（如 Neo4j 说 A 有效，Chroma 原文说 A 无效）

    # ── 质量元数据 ──
    retrieval_stats: RetrievalStats = field(default_factory=RetrievalStats)


@dataclass
class GraphEntity:
    """Neo4j 中的实体"""
    name: str
    entity_type: str
    description: str
    book_id: str
    book_title: str
    source_chapter: str = ""
    source_para_ids: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)  # 相邻实体名


@dataclass
class GraphRelation:
    """Neo4j 中的关系"""
    source_entity: str
    target_entity: str
    relation_type: str  # CAUSES, TREATS, CROSS_TREATS, SAME_AS, …
    source_book: str
    target_book: str = ""
    evidence: str = ""
    is_cross_book: bool = False


@dataclass
class CrossBookConflict:
    """跨书矛盾"""
    entity_name: str
    books: list[str]  # 涉及的书
    positions: list[str]  # 各自立场
    neo4j_relation_type: str  # CROSS_BOOK_CONFLICTS


@dataclass
class CrossBookConsensus:
    """跨书共识/互补（解决 P1-8：跨书数据链路断裂）

    SAME_AS → 两书对同一实体观点一致
    CROSS_BOOK_COMPLEMENTS → 一书补充另一书的视角
    CROSS_TREATS → 跨书治疗方案关系
    """
    entity_name: str
    books: list[str]
    relation_type: str  # SAME_AS | CROSS_BOOK_COMPLEMENTS | CROSS_TREATS
    description: str = ""


@dataclass
class Passage:
    """原文段落"""
    id: str  # chunk_id
    book_id: str
    book_title: str  # 规范化后的书名
    chapter_title: str
    content: str  # 完整原文，不截断
    score: float
    source: str  # "chroma" | "neo4j_source" | "lazy_graph_rag"
    neo4j_verified: bool = False  # 是否被 Neo4j 实体关联


@dataclass
class BookMeta:
    """书籍元数据（白名单用）"""
    book_id: str
    title: str
    normalized_title: str  # 去扩展名 + trim
    chapter_list: list[str]
    entity_count: int = 0


@dataclass
class PriorityConflict:
    """优先级冲突"""
    entity_name: str
    l1_position: str  # Neo4j 说法
    l2_position: str  # Chroma 原文说法
    l2_passage_id: str


@dataclass
class CustomRuleMatch:
    """自定义规则命中"""
    rule_id: str
    title: str
    content: str
    match_channel: str  # "keyword" | "regex" | "semantic"
    priority: int
    associated_entities: list[str]  # OVERRIDES/ENHANCES/RELATES_TO 指向的 Neo4j 实体名


@dataclass
class RetrievalStats:
    """检索质量统计"""
    neo4j_entity_count: int = 0
    neo4j_relation_count: int = 0
    chroma_passage_count: int = 0
    lazy_graph_hit_count: int = 0
    total_passage_chars: int = 0
    retrieval_duration_ms: int = 0
    pruned_book_ids: list[str] = field(default_factory=list)  # 被精简掉的候选书 ID
    seed_source: str = ""  # "question_embedding" | "s2_problems_fallback"
```

### 4.2 Bundle 构建后的不变量

| 不变量 | 保障机制 |
|--------|---------|
| 所有 `Passage.book_title` 经过规范化，与 `book_index` 一致 | `_normalize_book_title` 统一处理 |
| 每个 `Passage` 有一条 `source` 标记（chroma / neo4j_source / lazy_graph_rag） | 检索阶段写入 |
| `book_index` 包含所有被检索到的书籍 | 检索完成后统一构建 |
| `passage_index` 支持 O(1) excerpt 校验 | `dict[str, Passage]` |
| Bundle 构建后不再追加或修改 | `@dataclass(frozen=True)` 强制不可变——构建后任何字段赋值触发 `FrozenInstanceError`。子对象（如 Passage）在加入 Bundle 前完成构造，之后不再修改引用 |

---

## 5. Phase 0: 规则优先匹配

### 5.1 流程

```
fast_knowledge_match（已实现，保持现有逻辑）:
  ├─ 三通道匹配: 关键词 → 正则 → 语义（embedding）
  ├─ 命中 → 产出 custom_knowledge_context + custom_knowledge_entities
  └─ 同时查询 CustomRule 的 OVERRIDES/ENHANCES/RELATES_TO 关系
       → 将关联的 Neo4j 实体名加入 custom_knowledge_entities
```

### 5.2 改进点（相对现状）

**现状**：`fast_knowledge_match_node` 已正确实现三通道匹配 + 关联实体提取。

**需改进**：命中规则后，`custom_knowledge_entities` 应传递给 Phase 1 的 Neo4j 查询和 LazyGraphRAG 遍历，**强制用规则关联实体引导搜索**。

```python
# 改进后：规则命中的实体作为 Neo4j 查询的增强种子
neo4j_knowledge = await query_all(
    question=state.question,
    child_profile=...,
    matched_book_ids=...,
    s2_problems=[...] + state.custom_knowledge_entities,  # ← 规则实体注入
    custom_entities=state.custom_knowledge_entities,       # ← 新参数
)
```

---

## 6. Phase 1: 统一检索（核心改造）

### 6.1 总体流程

```
build_knowledge_bundle(question, matched_book_ids, custom_entities, child_profile):
  │
  ├── Step 1a: Neo4j 查询（200-500ms）
  │     输入: question + custom_entities + matched_book_ids
  │     动作:
  │       1. embedding(question) → 在 Neo4j 中找语义相近的实体（seed entities）
  │       2. 从 seed entities 做 1-2 跳关系扩展
  │       3. 查询跨书关系（SAME_AS, CROSS_*）
  │       4. 按 entity_type 分组返回
  │       5. 提取实体的 source_chapter + source_para_ids（关联到原文）
  │     输出: neo4j_entities, neo4j_relations, cross_book_conflicts
  │           实体引导词列表（供 Step 1b 和 1c 使用）
  │
  ├── Step 1b: Chroma 批量搜索（并行，1-3s）
  │     输入: question + 实体引导词 + matched_book_ids
  │     动作:
  │       1. 用 Neo4j 实体名增强搜索 queries（每个实体名作为独立 query 维度）
  │       2. 对每本书做批量搜索（并行 HTTP，合并为 N 个并发请求）
  │       3. 语义去重（cosine ≥ 0.9 的 passages 只保留 score 最高的）
  │       4. 标记 neo4j_verified（passage 是否与 Neo4j 实体 source_para_ids 匹配）
  │     输出: passages（完整原文，不截断），book_index
  │
  ├── Step 1c: LazyGraphRAG 增强遍历（1-3s）
  │     输入: question + 实体引导词 + matched_book_ids（精简为 top-3 书）
  │     动作:
  │       1. 增强 query: "{question} {实体引导词.join(' ')}"
  │       2. 社区树遍历时，包含 Neo4j 实体的社区获得更高相关性分数
  │       3. 优先探索高相关社区，快速剪枝不相关社区
  │       4. 遍历结果中标记哪些来自"图谱验证"的社区
  │     输出: knowledge_context 文本 + lazy_graph_passages
  │
  └── Step 1d: 组装 Bundle（纯程序化，<50ms）
       ├─ 精简 book_ids（剔除命中 < 阈值的候选书）
       ├─ 合并 passages（neo4j_source 优先级最高）
       ├─ 构建 book_index（规范化书名白名单）
       ├─ 构建 passage_index（O(1) 查找）
       ├─ 检测 L1/L2 冲突（Neo4j 实体关系 vs Chroma 原文矛盾）
       └─ 记录 retrieval_stats
```

### 6.2 Step 1a: Neo4j 查询增强

**关键改进**：当前 `query_dispatcher.query_all` 只在 S2 问题确定后才查询——这导致 S1/S2 本身没有 Neo4j 数据可用。改进为：

```python
async def query_all_enhanced(
    question: str,
    child_profile: dict,
    matched_book_ids: list[str],
    custom_entities: list[str],  # 从 fast_knowledge_match 来
    embedding_helper,  # 用于问题→实体语义匹配
) -> EnhancedNeo4jResult:
    """增强 Neo4j 查询。

    改进：
    1. 用 embedding(question) 找语义相近实体（不依赖 S2 先输出 problems）
    2. 用 custom_entities 引导查询（规则优先级）
    3. 1-2 跳扩展获取关系邻居
    4. 提取实体的 source 段落 ID 供 Step 1b 标记
    """

    # Step 1: 问题 embedding → 语义相近实体（seed）
    question_emb = await embedding_helper.embed(question)
    seeds = await _find_seed_entities(session, question_emb, matched_book_ids, limit=20)

    # Step 2: 加入 custom_entities（规则关联实体）
    seed_names = {s["name"] for s in seeds} | set(custom_entities)

    # Step 3: 1-2 跳扩展
    expanded = await _expand_neighbors(session, seed_names, hops=2, max_neighbors=100)

    # Step 4: 查询跨书关系
    cross_rels = _query_cross_book(session, matched_book_ids)

    # Step 5: 提取 source 段落 ID（关联到 Chroma）
    source_para_ids = _extract_source_para_ids(expanded)

    return EnhancedNeo4jResult(
        entities=expanded["entities"],
        relations=expanded["relations"],
        cross_relations=cross_rels,
        entity_seeds=list(seed_names),  # 供 Step 1b 和 1c 使用
        source_para_ids=source_para_ids,  # 供 Step 1b 标记
    )
```

**Neo4j schema 需新增**：在实体节点上计算并存储 embedding 向量，支持向量相似度搜索（或使用 Neo4j 5.x 的 `db.index.vector.queryNodes()`）。

#### 6.2.1 种子实体查找的降级回退

**风险**：`embedding(question)` 在用户问句上是语义匹配，但用户的自然语言问句可能不如 S2 提取出的结构化 `problems` 精准。例如用户问"我孩子注意力不集中怎么办"，embedding 可能匹配到"注意力训练"实体而非"ADHD 运动干预"实体。

**解决方案**：两阶段种子查找——embedding 优先，S2 问题回退。

```python
async def _find_seed_entities_with_fallback(
    question: str,
    matched_book_ids: list[str],
    embedding_helper,
    session,
    s2_problems: list[str] | None = None,  # 可选——S2 产出前为 None
    limit: int = 20,
) -> tuple[list[dict], str]:  # (seeds, source_label)
    """两阶段种子实体查找。

    Phase 1 执行时 S2 尚未运行，先用 embedding(question) 找种子。
    如果种子质量差（数量 < 5 或最高相似度 < 阈值），且有 s2_problems 可用，
    则用 s2_problems 回退重试。

    注意：Phase 1 与 Phase 2 不是严格串行——S2 可能在 Phase 1 之前运行
    （如果图拓扑允许），也可以异步触发回退重查。
    """

    # Stage 1: embedding(question) → 语义种子
    question_emb = await embedding_helper.embed(question)
    seeds = await _find_seed_entities(session, question_emb, matched_book_ids, limit=limit)
    source = "question_embedding"

    # Stage 2: 质量不够 + S2 问题可用 → 回退
    max_score = max((s.get("score", 0) for s in seeds), default=0)
    if (len(seeds) < 5 or max_score < 0.7) and s2_problems:
        logger.info(
            f"种子实体质量不足（count={len(seeds)}, max_score={max_score:.3f}），"
            f"回退到 S2 problems: {s2_problems}"
        )
        problem_seeds = []
        for problem in s2_problems[:5]:
            problem_emb = await embedding_helper.embed(problem)
            p_seeds = await _find_seed_entities(
                session, problem_emb, matched_book_ids, limit=10
            )
            problem_seeds.extend(p_seeds)

        if len(problem_seeds) > len(seeds):
            seeds = problem_seeds
            source = "s2_problems_fallback"

    return seeds, source
```

**回退触发条件**：
| 条件 | 说明 |
|------|------|
| `len(seeds) < 5` | 种子太少，后续关系扩展覆盖面不足 |
| `max_score < 0.7` | 最佳匹配语义距离过大，种子噪声高 |
| `s2_problems is not None` | S2 已产出结构化问题列表 |
| 三条件同时满足 | 触发 S2 回退 |

**图拓扑调整**（可选优化）：如果验证发现 question-embedding 种子质量始终不足，可将 Step 1a 移到 S2 之后执行（S1 → S2 → Step 1a → S3-S5）。代价是 Step 1a-1c 的延迟叠加到用户等待时间。建议先用两阶段回退方案上线，根据实际日志数据决定是否调整图拓扑。

### 6.3 Step 1b: Chroma 批量搜索

**关键改进**：从"每节独立搜索"变为"一次批量搜索"，用 Neo4j 实体引导 queries 构建。

```python
async def _batch_chroma_search(
    question: str,
    entity_seeds: list[str],
    matched_book_ids: list[str],
    source_para_ids: dict[str, list[str]],  # 来自 Neo4j
) -> tuple[list[Passage], dict[str, BookMeta]]:
    """批量 Chroma 搜索。

    与当前 _direct_search 的关键区别：
    1. 一次调用覆盖所有书籍（而非逐本补充）
    2. 用 entity_seeds 构建多元化 queries（而非全部用原问题）
    3. neo4j_verified 标记（与 Neo4j source_para_ids 交叉验证）
    4. 完整原文不截断
    """

    # ── Query 构建：原问题 + 实体增强 ──
    queries = [question]
    # 实体维度 queries（去方案导向词）
    for ent_name in entity_seeds[:8]:
        queries.append(f"{ent_name}")

    # ── 并行搜索（semaphore 限流） ──
    all_results = []
    seen_ids = set()

    async def search_one(query):
        results = await chroma_client.search(query, book_ids=matched_book_ids, limit=30)
        return results

    # 并行执行所有 query 的搜索
    all_query_results = await asyncio.gather(*[search_one(q) for q in queries[:5]])

    for results in all_query_results:
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                all_results.append(r)

    # ── 语义去重 ──
    deduped = _semantic_dedup(all_results, threshold=0.9)

    # ── 标记 neo4j_verified ──
    for passage in deduped:
        para_ids = source_para_ids.get(passage.book_id, [])
        passage.neo4j_verified = any(
            pid in para_ids for pid in passage.source_para_ids
        )

    # ── 构建 book_index ──
    book_index = _build_book_index(deduped)

    return deduped, book_index
```

### 6.4 Step 1c: LazyGraphRAG 增强遍历

**关键改进**：当前 `prefetch_context` 用原始 question 遍历社区树。改进为**用 Neo4j 实体引导探索方向**。

```python
async def _enhanced_lazy_graph_traversal(
    question: str,
    entity_seeds: list[str],
    matched_book_ids: list[str],  # 精简为 top-3
    community_repo,
    max_tokens: int = 20000,
) -> str:
    """Neo4j 实体增强的 LazyGraphRAG 遍历。

    与当前 prefetch_context 的关键区别：
    1. query 被实体名增强: "{question} {entity_seeds}"
    2. 包含 Neo4j 实体的社区获得相关性加分（优先探索）
    3. 只对 top-3 书做遍历（而非全部候选书）
    4. 遍历结果去重 + 与 passages 交叉去重
    """

    enhanced_query = question
    if entity_seeds:
        enhanced_query += " " + " ".join(entity_seeds[:10])

    # 相关性判定时增加实体加分
    def _boosted_relevance_check(community, base_score):
        """包含更多 Neo4j 实体的社区获得加分"""
        community_entities = set(community.get("entity_names", []))
        neo4j_entities = set(entity_seeds)
        overlap = len(community_entities & neo4j_entities)
        boost = min(overlap * 0.15, 0.45)  # 最多 +0.45
        return base_score + boost

    # … 社区树遍历逻辑，使用增强 query + 加分判定 …
```

**改进效果预估**：

| 指标 | 当前 | 增强后 |
|------|------|--------|
| 遍历社区数 | 全部候选书 × 全部 root | top-3 书 × 实体相关 root |
| 无关社区剪枝率 | ~50% | ~80%（实体引导大幅提升剪枝精度） |
| 遍历耗时 | 经常超时 >10s | 预期 1-3s |
| 命中质量 | LLM 相关性判定有随机性 | 实体加分提供确定性信号 |

### 6.5 Step 1d: Bundle 组装

纯程序化步骤：

0. **精简 book_ids**（解决 P0-4）：统计每本书在 Neo4j 实体和 Chroma passages 中的实际命中次数，仅保留命中 ≥ 阈值的书籍。
   ```
   ┌─────────────────────────────────────────────────────┐
   │ match_books 产出 12 本候选书                           │
   │   ↓ Phase 1 检索（Neo4j + Chroma）                     │
   │ Book A: 35 entities + 45 passages = 80 hits  → 保留  │
   │ Book B: 20 entities + 25 passages = 45 hits  → 保留  │
   │ Book C: 15 entities + 18 passages = 33 hits  → 保留  │
   │ Book D: 2 entities  + 3 passages  = 5 hits   → 剔除  │
   │ Book E: 0 entities  + 1 passage   = 1 hit    → 剔除  │
   │ ...                                                   │
   │   ↓ 精简后 book_index 只含 3 本                         │
   └─────────────────────────────────────────────────────┘
   ```
   默认阈值：实体命中 ≥ 3 **或** passage 命中 ≥ 5（两项满足其一即保留）。阈值通过配置项 `BUNDLE_BOOK_MIN_ENTITY_HITS` / `BUNDLE_BOOK_MIN_PASSAGE_HITS` 可调。被剔除的书籍及其 passages 不进入后续消费阶段，但记录在 `retrieval_stats.pruned_book_ids` 中供诊断。

1. **合并 passages**：按优先级排序——`neo4j_source` > `chroma`（neo4j_verified=True） > `chroma`（未验证） > `lazy_graph_rag`
2. **构建索引**：book_index（按 book_id 索引）、passage_index（按 passage_id 索引）
3. **检测冲突**：遍历 Neo4j 关系和 passages，标记矛盾表述
4. **配额分配**：计算各 Section 的 passage 预算（S1:20%, S2:20%, S3:25%, S4:25%, S5:10%）

---

## 7. Phase 2: 分节生成（零搜索）

### 7.1 核心改动

**所有 Section 节点不再调用 `_direct_search`**。改为从 Bundle 中按需切片：

```python
async def _run_section_node_from_bundle(
    state: KnowledgeQAState,
    bundle: KnowledgeBundle,
    section_index: int,
    section_label: str,
    prompt_key: str,
    response_format: Type[BaseModel],
    step_label: str,
) -> Dict[str, Any]:
    """通用节生成节点 — 从 Bundle 消费知识，零 HTTP 搜索。"""

    # ── 从 Bundle 提取本节相关 passages ──
    section_passages = _extract_for_section(bundle, section_index, state)

    # ── 构建三层优先级上下文 ──
    context = _build_priority_context(bundle, section_passages, section_index, state)

    # ── 注入 prompt ──
    full_message = _build_full_user_message(
        user_message_from_template=...,
        search_context=context,  # ← 来自 Bundle，非 _format_search_context
        previous_sections=state.sections,
        custom_knowledge_context=state.custom_knowledge_context or "",
        knowledge_context=bundle.knowledge_context or "",  # ← 来自 Bundle
    )

    # ── LLM 生成（不变）──
    # … 现有 structured_output 调用逻辑 …

    # ── 后处理：citations 白名单预校验 ──
    # 对 LLM 产出的 citations 做初步 book_title 匹配，
    # 不匹配的直接剔除（不等到 Phase 3 统一校验）
    verified_citations = _prefilter_citations(data.get("citations", []), bundle.book_index)
```

### 7.2 各节提取策略

```python
def _extract_for_section(bundle: KnowledgeBundle, section_index: int, state) -> list[Passage]:
    """按节需求从 Bundle 中提取相关 passages。"""

    if section_index == 1:  # S1: 儿童状态分析
        # 偏好：与行为特征、认知发展相关的 passages
        keywords = state.section_queries.get(1, "").split()
        return _retrieve_by_keywords(bundle, keywords, top_k=15)

    elif section_index == 2:  # S2: 问题识别
        # 偏好：Neo4j Problem/RootCause 相关 + associated passages
        problem_entities = bundle.neo4j_entities.get("Problem", [])
        return _retrieve_by_entities(bundle, problem_entities, top_k=12)

    elif section_index == 3:  # S3: 运动类型推荐
        # 偏好：Neo4j Exercise 实体 + 运动相关 passages
        exercise_entities = bundle.neo4j_entities.get("Exercise", [])
        return _retrieve_by_entities(bundle, exercise_entities, top_k=15)

    elif section_index == 4:  # S4: 运动方案
        # 偏好：全部 Prescription 实体 + 最全文覆盖
        return _retrieve_all(bundle, top_k=20)

    elif section_index == 5:  # S5: 结论
        # 偏好：全部 + 跨书关系 + 冲突标记
        return _retrieve_all(bundle, top_k=25)

    return bundle.passages[:10]
```

### 7.3 三层优先级上下文构造

```python
def _build_priority_context(bundle, passages, section_index, state) -> str:
    """构造带优先级的上下文，注入 LLM prompt。"""

    parts = []

    # ── L0: 自定义规则（最高优先级）──
    if state.custom_knowledge_context:
        parts.append("## ⚡ 专家知识（最高优先级，必须优先采纳）")
        parts.append(state.custom_knowledge_context)
        parts.append("> ⚠️ 以下所有知识必须与上述专家知识对齐。如有冲突，以专家知识为准。")

    # ── L1: Neo4j 图谱权威数据 ──
    neo4j_context = _format_neo4j_for_section(bundle, section_index)
    if neo4j_context:
        parts.append("## 📊 知识图谱权威数据")
        parts.append(neo4j_context)
        parts.append("> ⚠️ 当知识图谱数据与下方原文存在矛盾时，以知识图谱为准。")

    # ── L1/L2 冲突提示 ──
    conflicts = _format_conflicts_for_section(bundle, section_index)
    if conflicts:
        parts.append("## ⚠️ 知识冲突提醒")
        parts.append(conflicts)

    # ── 跨书共识/互补（解决 P1-8：非 conclusion 节点也消费跨书数据）──
    consensus = _format_consensus_for_section(bundle, section_index)
    if consensus:
        parts.append("## 🤝 跨书共识与互补")
        parts.append(consensus)
        parts.append("> 📌 以下为多本书共同确认的观点——可信度高于单书来源。如有分歧，优先采信多书共识。")

    # ── L2a: Neo4j 验证过的原文 ──
    verified_passages = [p for p in passages if p.neo4j_verified]
    if verified_passages:
        parts.append("## 📖 知识图谱关联原文（已验证）")
        parts.append(_format_passages(verified_passages))

    # ── L2b: 未验证原文 ──
    unverified = [p for p in passages if not p.neo4j_verified]
    if unverified:
        parts.append("## 📄 知识库原文")
        parts.append(_format_passages(unverified))

    # ── 引用约束（硬约束）──
    parts.append(_format_citation_rules(bundle))

    return "\n\n".join(parts)


def _format_citation_rules(bundle: KnowledgeBundle) -> str:
    """构造引用硬约束规则。"""
    book_list = "、".join(f"《{meta.title}》" for meta in bundle.book_index.values())
    return f"""## 🔒 引用规则（必须严格遵守）

合法书名（仅限以下 {len(bundle.book_index)} 本）：
{book_list}

每条 citation 必须：
1. book_title: 必须精确使用上方的书名（包括《》符号）
2. chapter: 必须来自下方原文中的章节名
3. excerpt: 必须从下方原文中逐字复制（≥10 字符）
4. 禁止编造书名、禁止编造章节名、禁止概括 excerpt
5. 如果某条 citation 无法在上述原文中找到依据，不要生成该条引用"""


def _format_consensus_for_section(bundle: KnowledgeBundle, section_index: int) -> str:
    """为指定节提取跨书共识/互补数据。

    与 _format_conflicts_for_section 不同——conflicts 在 S1-S5 都注入，
    consensus 按节过滤：S1-S2 关注实体级共识，S3-S4 关注运动/方案级共识。
    """
    if not bundle.cross_book_consensus:
        return ""

    lines = []
    for c in bundle.cross_book_consensus:
        # SAME_AS — 所有节都相关
        if c.relation_type == "SAME_AS":
            lines.append(f"- 「{c.entity_name}」在《{'》《'.join(c.books)}》中观点一致")
        # CROSS_BOOK_COMPLEMENTS — S3/S4 运动方案最相关
        elif c.relation_type == "CROSS_BOOK_COMPLEMENTS":
            if section_index in (3, 4):
                lines.append(f"- 「{c.entity_name}」：《{'》《'.join(c.books)}》互为补充：{c.description}")
        # CROSS_TREATS — S4 方案设计最相关
        elif c.relation_type == "CROSS_TREATS":
            if section_index == 4:
                lines.append(f"- 跨书治疗方案「{c.entity_name}」：{c.description}（来源：{'、'.join(c.books)}）")

    return "\n".join(lines) if lines else ""
```

---

## 8. Phase 3: 图谱增强引用校验

### 8.1 四层校验

取代当前 `verify_citations_node` 仅做结构校验的不足：

```python
async def verify_citations_enhanced(
    state: KnowledgeQAState,
    bundle: KnowledgeBundle,
) -> Dict[str, Any]:
    """四层引用校验：结构 → 白名单 → 溯源 → 图谱验证"""

    sections = dict(state.sections)
    errors = list(state.errors)

    for i in range(1, 6):
        sec = sections.get(i)
        if not sec:
            continue

        verified = []
        for citation in sec.citations:
            verdict = _check_citation(citation, bundle, sec.content)

            if verdict.passed:
                verified.append(citation)
            else:
                errors.append(f"section_{i}_citation_{citation.get('citation_id','?')}: {verdict.reason}")

        # 重建 SectionOutput（剔除不合格引用）
        if len(verified) < len(sec.citations):
            sections[i] = SectionOutput(
                index=sec.index, title=sec.title,
                content=sec.content,
                citations=verified,
                structured_data=sec.structured_data,
            )

    return {"sections": sections, "errors": errors}


def _check_citation(citation: dict, bundle: KnowledgeBundle, sec_content: str = "") -> CitationVerdict:
    """单条引用五层校验：结构 → 白名单 → 溯源 → 图谱验证 → 语义一致性。"""

    # ── L1: 结构完整性（已有）──
    if not citation.get("excerpt") or len(citation["excerpt"].strip()) < 10:
        return CitationVerdict(False, "excerpt 过短或为空")
    if not citation.get("chapter") or not citation["chapter"].strip():
        return CitationVerdict(False, "chapter 为空")

    # ── L2: 白名单校验（新增）──
    book_title = citation.get("book_title", "")
    normalized = _normalize_book_title(book_title)
    if normalized not in {m.normalized_title for m in bundle.book_index.values()}:
        # 尝试模糊匹配修正
        corrected = _fuzzy_match_book(normalized, bundle.book_index)
        if corrected:
            citation["book_title"] = corrected.title
            citation["_book_title_corrected"] = True
        else:
            return CitationVerdict(False, f"book_title '{book_title}' 不在白名单中")

    # ── L3: 溯源校验（新增）──
    excerpt = citation["excerpt"].strip()
    source_verified = False
    for pid, passage in bundle.passage_index.items():
        if excerpt in passage.content:
            source_verified = True
            citation["_source_passage_id"] = pid
            break
    if not source_verified:
        # 模糊匹配
        for pid, passage in bundle.passage_index.items():
            if _fuzzy_excerpt_match(excerpt, passage.content) >= 0.85:
                source_verified = True
                citation["_source_passage_id"] = pid
                citation["_excerpt_fuzzy_matched"] = True
                break
    if not source_verified:
        return CitationVerdict(False, f"excerpt 在原文中未找到匹配（可能被 LLM 改写）")

    # ── L4: 图谱验证（新增）──
    # 检查 citation 中涉及的实体是否在 Neo4j 中存在
    entity_names = _extract_entity_names_from_text(citation.get("excerpt", ""))
    neo4j_verified_entities = []
    for ename in entity_names:
        for etype, entities in bundle.neo4j_entities.items():
            if any(e.name == ename for e in entities):
                neo4j_verified_entities.append(ename)
                break
    citation["_neo4j_verified_entities"] = neo4j_verified_entities

    # ── L5: 语义一致性校验（新增，解决 P1-5）──
    # 检查 citation excerpt 与正文中引用标记位置附近的文本是否语义一致。
    # 防止 LLM 为 [C001] 匹配了合法但文不对题的 excerpt。
    citation_id = citation.get("citation_id", "")
    if citation_id and sec_content:
        # 提取正文中引用标记附近的文本（前后各 80 字符）
        marker_pattern = re.compile(rf"\[?{re.escape(citation_id)}\]?")
        marker_match = marker_pattern.search(sec_content)
        if marker_match:
            start = max(0, marker_match.start() - 80)
            end = min(len(sec_content), marker_match.end() + 80)
            nearby_text = sec_content[start:end]

            # 用 bundle 中已验证的 passage content 与 nearby_text 做嵌入相似度
            # 阈值较低（0.4），只过滤明显文不对题的情况
            if _semantic_sim(excerpt, nearby_text) < 0.4:
                citation["_semantic_mismatch"] = True
                # 不剔除（避免过度过滤），但标记供前端展示警告

    return CitationVerdict(True, "ok")
```

**L5 的设计原则**：只标记不剔除。语义一致性校验的阈值调校需要数据积累，初期用低阈值（0.4）只拦截最明显的错配，保守标记、逐步收紧。
```

### 8.2 校验结果分层展示

前端展示引用时，按校验层级赋予不同的可信度标记：

| 标记 | 条件 | 前端样式 |
|------|------|---------|
| ✅ **已验证** | 五层全通过 | 绿色边框，显示"知识图谱验证" |
| ⚠️ **语义存疑** | L1-L4 通过，L5 未通过（excerpt 与正文引用位置文不对题） | 橙色边框，显示"引用与正文可能不一致" |
| ⚠️ **原文验证** | L1-L3 通过，L4 未通过（实体不在图谱中） | 黄色边框 |
| ⚠️ **已修正** | book_title 被模糊修正 | 黄色边框，显示修正前后对比 |
| ❌ **未通过** | L1-L3 任一失败 | 已从最终结果中剔除，不展示 |

---

## 9. 与现有架构的融合

### 9.1 需要改动的节点

| 节点 | 当前行为 | 改动 |
|------|---------|------|
| `match_books` | 搜索 + LLM 匹配 → `matched_book_ids` | **不变** |
| `fast_knowledge_match` | 三通道匹配 → `custom_knowledge_context` | **小幅增强**：关联实体的 Neo4j 查询（查 OVERRIDES/ENHANCES 关系） |
| `query_neo4j_graph` | 按 S2 problems 查询 | **重构为 Step 1a**：用 `embedding(question)` 找 seed entities → 两阶段查找（§6.2.1，S2 problems 回退）→ 1-2 跳扩展 → 提取 source 段落 |
| `prefetch_context` | 原始 question 遍历社区树 | **重构为 Step 1c**：Neo4j 实体增强的社区遍历 |
| `S1-S5 nodes` | 各自调用 `_direct_search` | **改为 Bundle 消费**：新增 `_run_section_node_from_bundle` |
| `plan_outline` | 独立搜索 + 两阶段 LLM | **改为 Bundle 消费**：从 Bundle 提取 prescription/passages |
| `plan_expand_parallel` | 每组独立专项搜索 | **改为 Bundle 消费**：从 Bundle 提取运动相关 passages（不再做独立 HTTP 搜索） |
| `generate_s4_citations` | 独立搜索 + LLM 生成引用 | **改为 Bundle 消费**：LLM 仍生成 citations，但搜索上下文来自 Bundle |
| `verify_citations` | 仅结构校验 | **重构为 Phase 3**：四层校验（结构→白名单→溯源→图谱验证） |
| `conclusion` | 拉取全量 content | **改为 Bundle 消费**：从 Bundle 提取 S1-S4 摘要 + 跨书关系 + 冲突标记 |
| `finalize` | 纯函数 | **不变** |

### 9.2 需要新增的文件

| 文件 | 说明 |
|------|------|
| `backend/src/core/knowledge_qa/bundle.py` | KnowledgeBundle 数据模型 + 白名单校验逻辑 |
| `backend/src/core/knowledge_qa/bundle_builder.py` | Phase 1 统一检索（Neo4j + Chroma + LazyGraphRAG → Bundle，含 book_ids 精简） |
| `backend/src/core/knowledge_qa/bundle_consumer.py` | Phase 2 Bundle 切片提取（`_extract_for_section`、`_build_priority_context`，含跨书共识注入） |
| `backend/src/core/knowledge_qa/neo4j/enhanced_query.py` | Neo4j 增强查询（embedding 种子 + S2 回退 + 1-2 跳扩展） |
| `backend/src/core/knowledge_qa/bundle_config.py` | Feature Flag 配置（`KnowledgeQABundleConfig`） |
| `backend/tests/unit/knowledge_qa/test_bundle.py` | Bundle 数据模型单元测试 |
| `backend/tests/unit/knowledge_qa/test_bundle_builder.py` | Phase 1 各步骤单元测试 |
| `backend/tests/unit/knowledge_qa/test_bundle_consumer.py` | Phase 2 切片提取 + 引用校验单元测试 |
| `backend/tests/integration/knowledge_qa/test_bundle_e2e.py` | Bundle 构建→消费→校验 集成测试 |

### 9.3 不需要改动的文件

| 文件 | 原因 |
|------|------|
| `chapter_parser.py` | EPUB 解析不变 |
| D2G 全量文件（`book_pipeline.py`, `chapter_extractor.py`, `entity_resolver.py` 等） | 图谱构建独立于检索 |
| `cross_book_phase5a.py` / `phase5b.py` | 跨书融合在知识入库阶段执行，Bundle 只查询其结果 |
| `fast_knowledge_match.py` | 小幅增强即可（+关联实体 Neo4j 查询） |
| `match_books.py` | 实体提取逻辑不变（P3-1 优化不在本方案范围，见 §15.2） |
| 前端组件 | Bundle 对外 API 不变——仍然是 SSE 推送 sections（metadata 中新增 retrieval_stats） |
| `_assembly_v2.py` | 图结构不变（节点实现改了但图拓扑不变，Feature Flag 在节点内部处理兼容） |

---

## 10. API 变更

Bundle 是内部数据结构，**外部 API 不变**。SSE 推送的仍然是 `{ sections, errors, partial, current_step, metadata }`。

唯一的变化：`metadata` 中新增 `retrieval_stats`：

```json
{
  "metadata": {
    "retrieval_stats": {
      "neo4j_entity_count": 45,
      "neo4j_relation_count": 82,
      "chroma_passage_count": 120,
      "lazy_graph_hit_count": 15,
      "total_passage_chars": 28500,
      "retrieval_duration_ms": 3200,
      "conflict_count": 2,
      "book_count": 3
    }
  }
}
```

---

## 11. 降级路径

| 场景 | 触发条件 | 降级行为 |
|------|---------|---------|
| Neo4j 不可用 | `NEO4J_ENABLED=False` 或连接失败 | Step 1a/1c 跳过 → Bundle 仅含 L2b Chroma passages + L3 LazyGraphRAG |
| LazyGraphRAG 遍历超时 | > 10s | 跳过 Step 1c → Bundle 无 L3 上下文 |
| Chroma 搜索不可用 | HTTP 不可达 | Step 1b 失败 → Bundle 仅含 L1 Neo4j + L3 LazyGraphRAG（图谱模式） |
| 全部不可用 | 极端情况 | 返回错误，提示用户检查知识库和 Neo4j 状态 |
| 某节 Bundle 切片为空 | 该节无相关 passages | 降级为空节（无引用），不阻塞其他节 |

---

## 12. 端到端时序估算

以 3 本书、每本 15 章、Neo4j 300 实体为例：

| 阶段 | 步骤 | 预估耗时 | 说明 |
|------|------|---------|------|
| Phase 0 | fast_knowledge_match | < 100ms | 规则匹配（关键词 O(1) + 正则 O(n)） |
| Phase 1 | Step 1a: Neo4j 查询 | 200-500ms | embedding → seed entities → 1-2 跳扩展 |
| Phase 1 | Step 1b: Chroma 批量搜索 | 1-3s | 3-5 个并行 HTTP 请求，每请求 2-8 本 |
| Phase 1 | Step 1c: LazyGraphRAG 遍历 | 1-3s | 实体引导，top-3 书，快速剪枝 |
| Phase 1 | Step 1d: Bundle 组装 | < 50ms | 纯程序化（含 book_ids 精简） |
| Phase 1 | S2 回退重查（条件触发） | +200-500ms | 仅当 embedding 种子质量不足时触发 |
| **Phase 1 合计** | | **2.5-7s** | |
| Phase 2 | S1-S5 生成 | 30-60s | LLM 生成时间（Bundle 消费零搜索开销） |
| Phase 3 | verify_citations | < 200ms | 纯程序化，O(citations × passages) |
| **总计** | | **35-70s** | vs 当前 60-180s（改善 ~50%）。S2 回退重查仅条件触发 |

---

## 13. 与已有方案的关系

| 已有方案 | 关系 |
|---------|------|
| [03-Phase3](03-Phase3-Agent引擎改造.md) | 本节方案的 Phase 0/1 替代了 03 中的 `query_neo4j_graph` + `prefetch_context` 的分散设计 |
| [07-D2G](07-知识图谱直提方案-D2G.md) | D2G 生产 Neo4j 数据，Step 1a 消费之。图质量影响检索质量——连通分量达标（≤3）是关键前提 |
| [09-自定义知识](09-自定义知识匹配方案.md) | Phase 0 消费 CustomRule，并通过 `OVERRIDES/ENHANCES` 关系引导 Neo4j 查询 |
| [12-D2G 修复](12-D2G跨章连通性修复方案.md) | 12 的修复是本文档的**前置条件**——连通分量不达标，Bundle 的 Neo4j 质量就差 |
| [13-跨书融合](13-跨书知识融合方案-v2.md) | Phase 5a/5b 产出的跨书关系被 Step 1a 查询并注入 Bundle |
| [14-问题审查](14-知识问答全流程问题审查清单.md) | 本文档是 14 中 P0-1（搜索重复）、P0-2（引用编造）、P1-1（prefetch 超时）、P1-3（S4 展开搜索）、P1-4（多书补充搜索）、P1-5（citation 不一致，L5 语义校验缓解）、P1-6（verify 缺校验）、P2-2（Section 不用 Neo4j）、P2-3（跨书数据未消费）的解决方案。P0-4（book_ids 范围）部分覆盖——LazyGraphRAG top-3 控制已解决，Chroma 搜索精度通过 §6.5 Step 0 book_ids 精简缓解。P1-2/P2-4/P3-1 不在检索架构改造范围内（见 §15.2） |

---

## 14. 迁移策略与风险控制（解决 G2）

### 14.1 灰度上线方案

大规模改造 11 个节点的行为存在回归风险。采用 **Feature Flag + 渐进式切换** 策略：

```
Week 1-2: 开发 + 单元测试（feature flag = OFF，新代码不执行）
Week 3:   集成测试环境全量开启（feature flag = ON）
Week 4:   生产环境 10% 流量 → 观察 3 天 → 50% → 100%
Week 5:   清理旧代码（_direct_search 在 Section 节点中的调用）
```

### 14.2 Feature Flag 设计

```python
# 在 config/modules/ 中新增配置项
class KnowledgeQABundleConfig:
    """Bundle 模式灰度开关。"""

    # 全局开关——关闭时走旧版分散搜索逻辑
    bundle_mode_enabled: bool = False  # 默认关闭，集成测试通过后开启

    # 细粒度开关——可单独控制 Phase 1/2/3
    bundle_phase1_enabled: bool = True   # Phase 1: 统一检索（Neo4j+Chroma+LazyGraphRAG）
    bundle_phase2_enabled: bool = True   # Phase 2: Bundle 消费（Section 节点零搜索）
    bundle_phase3_enabled: bool = True   # Phase 3: 四层引用校验

    # 流量比例（0.0-1.0）
    bundle_traffic_ratio: float = 0.1  # 初始 10%，递增至 1.0

    # 允许手动覆盖（用于单个请求调试）
    bundle_force_enabled: bool = False  # URL param ?bundle=1 强制开启
```

### 14.3 核心节点的 if/else 模式

```python
async def _run_section_node(state, section_index, ...):
    """兼容模式——Bundle 可用时消费 Bundle，不可用时走旧版搜索。"""
    if _use_bundle(state):
        return await _run_section_node_from_bundle(state, _get_bundle(state), section_index, ...)
    else:
        return await _run_section_node_legacy(state, section_index, ...)  # 保留旧实现

def _use_bundle(state) -> bool:
    """判定是否使用 Bundle 模式。"""
    config = get_config(KnowledgeQABundleConfig)
    if not config.bundle_mode_enabled:
        return False
    if config.bundle_force_enabled:
        return True
    # 流量比例控制
    import random
    return random.random() < config.bundle_traffic_ratio
```

### 14.4 回归测试用例

| 测试场景 | 验证点 | 方法 |
|---------|--------|------|
| Bundle OFF | 旧版搜索逻辑完整可用 | 回归测试套件 |
| Bundle ON + 3 本书 | 端到端输出与旧版一致（章节完整性 + citation 数量） | 对比测试 |
| Bundle ON + Neo4j 不可用 | 降级到 Chroma-only Bundle | 故障注入 |
| Bundle ON + Chroma 不可用 | 降级到 Neo4j-only Bundle | 故障注入 |
| Bundle ON + 全部不可用 | 返回明确错误 | 故障注入 |
| 流量比例 0.1 | 10% 请求走 Bundle，其他走旧版 | 日志统计 |

### 14.5 旧代码清理时间线

| 阶段 | 操作 | 条件 |
|------|------|------|
| 灰度上线 | 保留旧版 `_run_section_node_legacy` | Feature flag OFF 时使用 |
| 100% 流量（第 4 周） | 旧代码路径不再执行 | `bundle_traffic_ratio=1.0` |
| 稳定运行 1 周后 | 删除旧版搜索函数 | 无回退需求 |
| 删除对象 | `_direct_search`、`_format_search_context`（base.py）、S1-S5 中的独立搜索调用 | — |

---

## 15. 依赖与前置条件

### 15.1 实施前必须解决

| 前置条件 | 说明 | 负责 |
|---------|------|------|
| **P3-2: Schema 类型统一** | Step 1a 依赖 `entity_type` 枚举。当前 schema.py (8 种) / md_generator.py (11 种) / 前端 (6 种) / D2G (15 种) 四套不一致，必须在 Step 1a 编码前统一为 D2G 15 种类型 | D2G 维护者 |
| **D2G 连通性稳定** | 12 方案已修复但需要至少 3 本书的 Neo4j 质量验证（连通分量 ≤ 10） | D2G 维护者 |

### 15.2 已知不在此次改造范围内的问题

以下问题被 14-问题审查清单识别，但属于 LLM 调用结构或基础设施优化范畴，不在此次检索架构改造中解决。**在 15 方案实施完成后应排入独立改造计划**：

| 问题 | 描述 | 不在范围内原因 | 建议后续方案 |
|------|------|--------------|-------------|
| **P1-2** | S4 大纲 2 阶段 LLM + 多次重试 | 属于 LLM 调用结构优化，独立于检索层 | 评估合并为 1 次 LLM 调用 + 后处理前移到 prompt 约束 |
| **P2-4** | S4 后处理函数链 `_normalize_day_indices → _ensure_min_phases → _ensure_full_weeks → _enforce_rest_days` 4 层修补 | 属于 LLM 输出质量改进 | 通过结构化 prompt 减少修补，记录修补操作供审核展示 |
| **P3-1** | match_books 中 LLM 实体提取可改为纯规则 | 性能优化项，优先级低 | 实体提取用规则，LLM 只做意图分类 + 查询改写 |
| **P3-2** | Schema 类型定义四套不一致 | 已在 §15.1 中列为前置条件——实施 Step 1a 前必须统一 | — |

---

## 16. 实施计划

| 阶段 | 任务 | 工时 | 依赖 |
|------|------|------|------|
| 1 | 修复 D2G 连通性（12 方案根因 B/C） | 3d | — |
| 2 | 实现 `bundle.py` 数据模型 | 1d | — |
| 3 | 实现 Neo4j 增强查询（Step 1a） | 2d | 阶段 1 |
| 4 | 实现 Chroma 批量搜索（Step 1b） | 1d | — |
| 5 | 实现 LazyGraphRAG 增强遍历（Step 1c） | 1.5d | 阶段 3 |
| 6 | 实现 Bundle 组装（Step 1d） | 0.5d | 阶段 2-5 |
| 7 | 实现 Bundle 消费层（Phase 2） | 2d | 阶段 6 |
| 8 | 实现四层引用校验（Phase 3） | 1d | 阶段 6 |
| 9 | 替换现有节点引用（S1-S5 等改为消费 Bundle） | 2d | 阶段 7 |
| 10 | fast_knowledge_match 增强（关联实体 Neo4j 查询） | 0.5d | — |
| 11 | 端到端测试（3 本书 PoC） | 2d | 阶段 1-10 |
| 12 | 单元测试（bundle.py 数据模型） | 0.5d | 阶段 2 |
| 13 | 单元测试（bundle_builder.py Step 1a-1d） | 1d | 阶段 3-6 |
| 14 | 单元测试（bundle_consumer.py 切片提取） | 0.5d | 阶段 7 |
| 15 | 单元测试（四层引用校验） | 0.5d | 阶段 8 |
| 16 | 集成测试（Bundle 构建 + 消费 + 校验联调） | 1d | 阶段 1-9 |
| 17 | 回归测试（Feature Flag OFF → 旧版行为不变） | 1d | 阶段 9 |
| 18 | 故障注入测试（Neo4j/Chroma/LazyGraphRAG 降级） | 0.5d | 阶段 3-6 |
| 19 | 对比测试（Bundle ON vs OFF，3 本书 × 5 个 question） | 1d | 阶段 11 |
| **合计** | | **~22d** | |

**分阶段交付**：
- **里程碑 1**（阶段 1-6+12+13+18，~11d）：Bundle 构建完成 + 单元测试 + 故障注入——可独立验证检索质量和耗时
- **里程碑 2**（阶段 7-9+14+15+16，~6d）：Bundle 消费 + 引用校验 + 集成测试——端到端可用
- **里程碑 3**（阶段 10-11+17+19，~5d）：定制规则增强 + 回归测试 + 对比测试 + E2E 验证——灰度上线

---

## 17. 验证标准

| 验证项 | 标准 | 方法 |
|--------|------|------|
| 搜索次数 | 整个请求 ≤ 1 次批量 HTTP 搜索（Phase 1） | 日志统计 |
| 引用 book_title 合法性 | 100% 在白名单中 | 程序化校验 |
| excerpt 溯源率 | ≥ 95% 的 excerpt 可在 Bundle.passages 中找到匹配 | 程序化校验 |
| Neo4j 实体覆盖 | 至少 70% 的 passages 与 Neo4j 实体有关联 | Phase 1 日志统计 |
| LazyGraphRAG 遍历耗时 | P99 < 5s（3 本书） | 计时日志 |
| Bundle 构建总耗时 | P95 < 8s（3 本书） | 计时日志 |
| 端到端耗时改善 | 比当前方案减少 ≥ 40% | 对比测试 |
| 降级不阻塞 | Neo4j 或 Chroma 不可用时仍可产出结果 | 故障注入测试 |
| book_ids 精简 | 实际命中 < 阈值的候选书被正确剔除 | 日志统计（pruned_book_ids） |
| 跨书共识注入 | S1-S4 节 prompt 中包含跨书共识段落 | prompt 快照抽查 |
| 种子质量监控 | seed_source 字段记录实际采用的种子来源 | Phase 1 日志统计 |
| 回归安全 | Feature Flag OFF 时旧版搜索行为不变 | 回归测试套件 |

---

## 18. 开放问题

| # | 问题 | 建议 |
|---|------|------|
| 1 | Neo4j 实体 embedding 存储在哪？ | 方案 A：Neo4j 5.x 原生 vector index（`db.index.vector.createNodeIndex`）。方案 B：复用现有 Chroma。建议 A——减少依赖 |
| 2 | Bundle 的 passages 配额如何精确分配？ | 第一期用固定比例（S1:20%, S2:20%, S3:25%, S4:25%, S5:10%），第二期可动态分配（按 LLM 反馈） |
| 3 | 如果某节 LLM 因为 Bundle 覆盖面不足而无法生成？ | 降级为空节（当前已有此逻辑 `_build_empty_search_fallback`），但应记录缺失的具体实体/方向供 D2G 改进 |
| 4 | 跨书关系的 SAME_AS 合并实体在 Bundle 中如何表示？ | 在 `neo4j_entities` 中，合并实体以 representative name 出现，`aliases` 字段列出所有别名 |
| 5 | S2 回退种子的质量如何验证？ | 在 `RetrievalStats.seed_source` 中记录实际来源。统计 "s2_problems_fallback" 的比例——如果长期 > 30%，考虑调整图拓扑（Step 1a 移到 S2 之后） |
| 6 | Feature Flag 两个代码路径并存多久？ | 建议全量切换后稳定运行 1 周再删除旧代码（§14.5）。避免过早删除导致回退困难 |
| 7 | 单书场景（1 本书）的跨书共识和 book_ids 精简如何处理？ | 单书场景 `cross_book_consensus` 为空（正常），book_ids 精简阈值自动通过（只有 1 本书，不剔除）。无需特殊处理 |
| 8 | P1-2（S4 大纲优化）和 P2-4（后处理链简化）何时处理？ | 不在本方案范围（见 §15.2）。建议在 15 方案上线稳定后，作为独立改造排入下一迭代 |
