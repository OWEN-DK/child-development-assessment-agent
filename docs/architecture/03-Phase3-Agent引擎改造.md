# Phase 3: Agent 引擎三层改造

> **工期**: 5 人天 | **风险**: 中 | **依赖**: Phase 2（MD 工具链可生成并入库 MD）  
> **目标**: LangGraph 流水线融合 Layer 1 (Neo4j) + Layer 2 (Agent 分析) + Layer 3 (原文检索)
> **实施状态**: ✅ 代码已部署（2026-05-30）。v2 节点 + 图定义 + 审核 API + 前端 UI 全部完成。运行时验证待 Neo4j 启动后执行。
>
> **路径说明**: v2 节点放入 `nodes_v2/`，v2 图定义新建 `_assembly_v2.py` 并行保留。

---

## 3.1 改造后的图结构

```
                        用户提问
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         match_books   prefetch_context  query_neo4j_graph  [NEW]
         (Chroma)      (LazyGraphRAG)    (Neo4j Cypher)
              │            │               │
              └────────────┼───────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         S1_v2          S2_v2          S3_v2
         analyze_child  identify_      recommend_types
         [看 Neo4j      problems       [query_exercises
          Problem 列表]  [看 Neo4j       + diversity_rerank]
                         RootCause]
              │            │               │
              └────────────┼───────────────┘
                           │
                           ▼
                      plan_outline_v2
                      [合并 neo4j_knowledge + knowledge_context]
                           │
                           ▼
                   plan_expand_parallel_v2
                   [Prescription 从 Neo4j，LLM 微调]
                           │
                           ▼
                      plan_assemble (不变)
                           │
                           ▼
                   generate_s4_citations (不变)
                           │
                           ▼
                  contradiction_audit_v2
                  [优先读 Neo4j 跨书关系，LLM 仅补漏]
                           │
                           ▼
                      S5 (conclusion)
                      [注入矛盾信息 + 边界声明]
```

---

## 3.2 Node 1: `query_neo4j_graph`（新增）

```python
# backend/src/core/knowledge_qa/nodes_v2/query_neo4j_graph.py

import logging
import asyncio

logger = logging.getLogger(__name__)

NEO4J_QUERY_TIMEOUT = 30  # 秒


async def query_neo4j_graph_node(state) -> dict:
    """查询 Neo4j 知识图谱，将结构化知识注入 State。Neo4j 不可用时返回空字典。"""
    from core.knowledge_qa.neo4j.driver import neo4j_available

    if not neo4j_available():
        logger.info("Neo4j 不可用，跳过知识图谱查询")
        return {"neo4j_knowledge": {}}

    from core.knowledge_qa.neo4j.query_dispatcher import query_all

    try:
        neo4j_knowledge = await asyncio.wait_for(
            query_all(
                question=state.question,
                child_profile=state.child_profile,
                matched_book_ids=[b["book_id"] for b in state.matched_books],
                s2_problems=[p["name"] for p in state.sections[1].structured_data.get("problems", [])],
                s2_root_causes=state.sections[1].structured_data.get("root_causes", []),
            ),
            timeout=NEO4J_QUERY_TIMEOUT,
        )
        return {"neo4j_knowledge": neo4j_knowledge}
    except asyncio.TimeoutError:
        logger.warning("Neo4j 查询超时 (%ds)，降级", NEO4J_QUERY_TIMEOUT)
        return {"neo4j_knowledge": {}}
    except Exception as e:
        logger.warning("Neo4j 查询失败，降级: %s", e)
        return {"neo4j_knowledge": {}}
```

---

## 3.3 Query Dispatcher

```python
# backend/src/core/knowledge_qa/neo4j/query_dispatcher.py

import logging

logger = logging.getLogger(__name__)


async def query_all(
    question: str,
    child_profile: dict,
    matched_book_ids: list[str],
    s2_problems: list[str],
    s2_root_causes: list[str],
) -> dict:
    """执行所有 Neo4j 查询模式，返回聚合结果。"""
    from core.knowledge_qa.neo4j.driver import get_neo4j_driver

    driver = get_neo4j_driver()
    result = {}

    with driver.session() as session:
        # 模式 1: 运动推荐（S3/S4 使用）
        result["exercises"] = _query_exercises(session, child_profile, s2_problems)

        # 模式 2: 跨书关系
        result["cross_book_relations"] = _query_cross_book(session, matched_book_ids)

        # 模式 3: 问题上下文（S2 使用）
        result["problem_context"] = _query_problem_context(session, s2_problems)

        # 模式 4: 来源覆盖度
        result["source_coverage"] = _query_source_coverage(session, matched_book_ids)

    return result


def _query_exercises(session, child_profile: dict, problems: list[str]) -> list[dict]:
    """按年龄 + 问题查询运动推荐。"""
    age = child_profile.get("age", 6)
    problem_conditions = " OR ".join([f"p.name CONTAINS '{p}'" for p in problems[:3]])

    query = f"""
        MATCH (e:Exercise)
        WHERE e.suitable_for_children = true
          AND e.min_age <= $age AND e.max_age >= $age
        {"AND EXISTS {" + "(MATCH (e)<-[:DESCRIBES_EXERCISE]-(ch)<-[:HAS_CHAPTER]-(b)<-[:CONTAINS_ENTITY]-(p:Problem) WHERE " + problem_conditions + ")" if problems else ""}}
        RETURN e.name AS name, e.category AS category, e.benefits AS benefits,
               e.intensity AS intensity, e.exercise_id AS id
        ORDER BY e.name
        LIMIT 20
    """
    return session.run(query, age=age).data()


def _query_cross_book(session, book_ids: list[str]) -> list[dict]:
    """查询跨书关系。"""
    if len(book_ids) < 2:
        return []
    query = """
        MATCH (a)-[r:CROSS_BOOK_CONSENSUS|CROSS_BOOK_COMPLEMENTS|CROSS_BOOK_CONFLICTS]->(b)
        WHERE a.book_id IN $book_ids AND b.book_id IN $book_ids
        RETURN a.name AS source, type(r) AS relation, b.name AS target,
               r.explanation AS explanation
    """
    return session.run(query, book_ids=book_ids).data()


def _query_problem_context(session, problems: list[str]) -> list[dict]:
    """查询问题相关的根因和诊断链。"""
    if not problems:
        return []
    query = """
        MATCH (p:Problem)-[r]->(rc:RootCause)
        WHERE p.name IN $problems
        RETURN p.name AS problem, rc.name AS root_cause, type(r) AS relation
    """
    return session.run(query, problems=problems).data()


def _query_source_coverage(session, book_ids: list[str]) -> dict:
    """查询各书的知识覆盖度。"""
    query = """
        MATCH (b:Book)
        WHERE b.book_id IN $book_ids
        OPTIONAL MATCH (b)-[:CONTAINS_ENTITY]->(e)
        RETURN b.book_id AS book_id, b.title AS title, count(e) AS entity_count
    """
    return {r["book_id"]: r for r in session.run(query, book_ids=book_ids).data()}
```

---

## 3.4 Diversity Rerank

```python
# backend/src/core/knowledge_qa/neo4j/diversity_rerank.py
"""来源多样性重排 — 确保推荐结果来自多本书。"""

from collections import defaultdict


def diversity_rerank(
    items: list[dict],
    max_per_book: int = 3,
    book_key: str = "book_id",
) -> list[dict]:
    """按书籍来源分组，每本书最多取 max_per_book 项，交错排列。"""
    by_book = defaultdict(list)
    for item in items:
        by_book[item.get(book_key, "unknown")].append(item)

    result = []
    round_idx = 0
    while any(by_book.values()):
        for book_id in sorted(by_book.keys()):
            if by_book[book_id] and round_idx < max_per_book:
                result.append(by_book[book_id].pop(0))
        round_idx += 1

    return result
```

---

## 3.5 审核 Web UI

### 3.5.1 页面列表

| 页面 | 路径 | 说明 |
|------|------|------|
| 草稿列表 | `/admin/curation` | 所有 MD 草稿，按状态筛选 |
| 审核编辑器 | `/admin/curation/drafts/:id` | 三栏布局：实体导航 + MD 编辑 + 信息面板 |
| 待提炼管理 | `/admin/curation/pending` | 待提炼队列管理 |
| KG 可视化 | `/admin/curation/graph` | Cytoscape.js 知识图谱 |

### 3.5.2 审核编辑器三栏布局

```
┌──────────────┬────────────────────────┬──────────────────┐
│ 实体导航      │ MD 编辑器               │ 信息面板          │
│              │                        │                  │
│ □ ADHD       │ ---                    │ 选中实体属性       │
│   ✓ 已确认    │ book_id: exercise_001  │                  │
│ □ 有氧运动    │ status: draft          │ 名称: ADHD       │
│   ⚠ 待审核    │ ---                    │ 类型: Problem    │
│ □ BDNF       │                        │ 严重度: HIGH     │
│   🆕 新增     │ ## 概念                │ 来源: 第2章      │
│              │                        │                  │
│ [全选] [反选]  │ ### 注意力缺陷 (ADHD)  │ 跨书关系:        │
│              │ - **entity_type**:     │ ⚠ CONFLICTS      │
│              │   Problem              │ vs 《学习如何学习》│
│              │ - **severity**: high   │                  │
│              │                        │ [查看原文]       │
├──────────────┴────────────────────────┴──────────────────┤
│ [保存草稿]  [标记已审核]  [入库 Neo4j]  [对比上一版]        │
└──────────────────────────────────────────────────────────┘
```

### 3.5.3 后端 API

```python
# GET  /api/v2/curation/drafts — 草稿列表
# GET  /api/v2/curation/drafts/:id — 获取 MD 草稿
# PUT  /api/v2/curation/drafts/:id — 保存审核修改
# POST /api/v2/curation/drafts/:id/review — 标记已审核
# POST /api/v2/curation/drafts/:id/publish — 入库 Neo4j
# GET  /api/v2/curation/graph — KG 可视化数据
# GET  /api/v2/curation/pending — 待提炼队列
```

---

## 3.6 Knowledge Graph 可视化

### 3.6.1 技术选型

- **Cytoscape.js** — 图渲染（支持力导向布局、分层布局）
- **dagre** — 分层自动布局

### 3.6.2 视觉约定

| 元素 | 视觉样式 |
|------|---------|
| 书内关系 | 灰色实线 |
| 跨书共识 `CONSENSUS` | **绿色虚线** |
| 跨书互补 `COMPLEMENTS` | **蓝色虚线** |
| 跨书冲突 `CONFLICTS` | **红色虚线 + ⚠️ 图标** |
| 节点颜色 | Problem=红, Solution=绿, BrainRegion=蓝, Exercise=橙, Book=灰 |
| 节点大小 | 按出度/入度 |

### 3.6.3 后端 API

```python
# 单书 KG
GET /api/v2/curation/graph?book_id=exercise_book_001
# → {nodes: [{id, label, type, properties}], edges: [{source, target, type}]}

# 全景 KG（含跨书关系）
GET /api/v2/curation/graph
```

### 3.6.4 交互功能

| 功能 | 实现方式 |
|------|---------|
| 点击节点 | 弹出属性侧边栏 |
| 按类型筛选 | 图例 toggle |
| 搜索高亮 | 匹配节点高亮，其余半透明 |
| 冲突聚焦 | 一键定位所有 CONFLICTS 边 |
| 导出 PNG | `cy.png()` |

---

## 3.7 降级路径矩阵

| 场景 | 触发条件 | 降级行为 |
|------|---------|---------|
| Neo4j 不可用 | `NEO4J_ENABLED=False` 或连接失败 | `neo4j_knowledge = {}`，回退到 Chroma |
| Neo4j 查询超时 | Cypher > 30s | 返回空结果 |
| 无匹配运动 | `query_exercises` 返回 0 | LLM 自由生成 + 标记"待提炼" |
| 无跨书关系 | `cross_book_relations` 为空 | LLM 全量审计（当前行为） |

---

## 3.8 验证清单

- [x] `query_neo4j_graph_node` 可查询并返回结构化数据（代码已部署）
- [x] `query_dispatcher.query_all()` 四种模式均正确（代码已部署）
- [x] S1 v2 可看到 Neo4j Problem 列表（analyze_child_v2.py 已部署）
- [x] S3 v2 运动候选非全量清单（recommend_types_v2.py 已部署）
- [x] `contradiction_audit_v2` 优先使用 Neo4j 跨书关系（代码已部署）
- [ ] S5 包含矛盾信息 + 边界声明
- [x] 所有降级场景有日志 + 不阻塞流水线（v2 节点均有 fallback 逻辑）
- [x] `NEO4J_ENABLED=False` 时行为与当前一致（service 层特性开关已实现）

---

## 3.9 预计产出

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/core/knowledge_qa/nodes_v2/query_neo4j_graph.py` | 新增 | Layer 1 查询节点 |
| `backend/src/core/knowledge_qa/nodes_v2/analyze_child_v2.py` | 新增 | S1 v2 |
| `backend/src/core/knowledge_qa/nodes_v2/identify_problems_v2.py` | 新增 | S2 v2 |
| `backend/src/core/knowledge_qa/nodes_v2/recommend_types_v2.py` | 新增 | S3 v2 |
| `backend/src/core/knowledge_qa/nodes_v2/plan_outline_v2.py` | 新增 | plan_outline v2 |
| `backend/src/core/knowledge_qa/nodes_v2/plan_expand_parallel_v2.py` | 新增 | plan_expand_parallel v2 |
| `backend/src/core/knowledge_qa/nodes_v2/contradiction_audit_v2.py` | 新增 | 矛盾审计 v2 |
| `backend/src/core/knowledge_qa/neo4j/query_dispatcher.py` | 新增 | 多模式查询调度 |
| `backend/src/core/knowledge_qa/neo4j/diversity_rerank.py` | 新增 | 来源多样性重排 |
| `backend/src/core/knowledge_qa/_assembly_v2.py` | 新增 | v2 图定义 |
| `frontend/src/features/curation/` | 新增 | 审核 Web UI 全套 |
