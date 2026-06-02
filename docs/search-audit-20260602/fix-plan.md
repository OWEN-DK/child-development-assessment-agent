# 知识问答搜索链路修复方案

> 日期: 2026-06-02
> 范围: 搜索检索 + 引用生成 + 前端展示 + 运动约束
> 版本: v2（重审修订版）

---

## 一、问题全景

### 现象

| 问题 | 表现 |
|---|---|
| 引用来源单一 | 4 本书匹配，但引用集中在 2 本书（孩子如何思考 42%、运动改变大脑 32%） |
| S3 零引用 | 运动类型推荐节 citations 为空，但 structured_data 有 source_books |
| LLM 书籍匹配全部降级 | 4 本书的 match_reason 全是 "综合匹配"（Step 4 兜底） |
| 参考文献混乱 | 引用 ID 不全局唯一（每节独立 C001），合并后重复 |
| 进度展示混乱 | build_bundle 期间进度条不动，中间状态导致跳动 |
| 运动约束薄弱 | Neo4j Exercise 可能被清空，JSON 兜底不完善 |
| LazyGraphRAG 失效 | 图谱遍历返回 0 命中，跨书发现通道关闭 |
| 实体检索刚性 | 精确字符串匹配，"注意力" 不匹配 "专注力" |

### 数据流全景

```
match_books (Step 0)
├── _analyze_and_search_books: 多维度 RAG 搜索
├── _llm_match_books: LLM 评估书籍相关性 ← 全部降级
└── _build_section_queries: 构建逐节搜索 query ← 未使用 LLM 分析

build_bundle (Step 1)
├── Step 1a: Neo4j 增强查询
│   ├── 跨书关系: CROSS_BOOK_CONSENSUS/COMPLEMENTS/CONFLICTS
│   └── 输出: entity_seeds, source_para_ids, entities, relations
├── Step 1b: Chroma 批量搜索 (queries = section_queries + entity_seeds, ≤5)
├── Step 1c: LazyGraphRAG 遍历 ← 命中 0
└── Step 1d: Bundle 组装

S1-S5 生成
├── extract_for_section: 按实体类型提取 passages ← 不感知跨书关系
├── build_priority_context: 构建 LLM 上下文 ← 跨书关系只在 S5 展示
└── generate_s3_citations: 运动引用生成 ← 运动名精确匹配失败
```

### 根因：Neo4j 跨书关系从 S1 就应该指导检索，但只在 S4 之后使用

```
跨书关系闲置 → S3 不知道跨书共识运动 → 引用来源单一
    → section_queries 单调 → Chroma 返回相似段落 → 2 本书垄断
    → S3 citations 运动名精确匹配失败 → 零引用
    → LazyGraphRAG 返回 0 → 图谱遍历通道关闭
    → 实体检索刚性 → 相关段落因名称不一致丢失
    → 引用 ID 不唯一 → 前端参考文献混乱
    → 进度步骤缺失 → 进度条卡住/跳动
    → JSON 兜底不完善 → Neo4j 清空时无运动约束
```

---

## 二、修复方案（11 个模块）

---

### 模块 1: 跨书关系从 S1 开始注入 🔴

**文件**: `backend/src/core/knowledge_qa/bundle_consumer.py`

**目标**: 跨书共识/互补关系从 S1 就指导 passage 排序和 LLM 上下文。

#### 1a. extract_for_section — 跨书共识 boost

在 `_retrieve_by_entities` 中，对命中跨书共识实体的 passage 加分：

```python
def _retrieve_by_entities(bundle, entities, top_k):
    entity_names = {e.name.lower() for e in entities if e.name}

    # 跨书共识实体集合（用于 boost）
    consensus_names = set()
    for c in bundle.cross_book_consensus:
        if c.relation_type in ("SAME_AS", "CROSS_BOOK_CONSENSUS"):
            consensus_names.add(c.entity_name.lower())

    scored = []
    for p in bundle.passages:
        content_lower = p.content.lower()
        hits = sum(1 for name in entity_names if name in content_lower)
        if hits > 0:
            # 跨书共识 boost: 有共识关系的实体命中额外加分
            consensus_hits = sum(1 for n in consensus_names if n in content_lower)
            if consensus_hits > 0:
                hits += min(consensus_hits, 3)  # 上限 3，防止过拟合
            scored.append((p, hits))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:top_k]]
```

**boost 调参策略**：`min(consensus_hits, 3)` 上限 3 分。如果实测发现跨书共识 passage 仍然排不到前面，可调到 5；如果引入噪声，降到 1。

#### 1b. build_priority_context — S1 起展示跨书关系

新增 3 个格式化函数，在 `build_priority_context` 中按节调用：

```python
def _append_cross_book_section(parts, bundle, section_index):
    """按节注入跨书关系摘要。"""
    if section_index in (1, 2):
        # 展示跨书共识的实体和根因
        _append_consensus_by_type(parts, bundle, focus={"Problem", "RootCause", "Mechanism"})
    elif section_index == 3:
        # 展示跨书共识/互补的运动
        _append_consensus_by_type(parts, bundle, focus={"Exercise"})
        _append_complements_by_type(parts, bundle, focus={"Exercise"})
    elif section_index in (4, 5):
        # 展示全部跨书关系
        _append_all_cross_book(parts, bundle)

def _append_consensus_by_type(parts, bundle, focus):
    """按实体类型筛选跨书共识。"""
    relevant = [
        c for c in bundle.cross_book_consensus
        if any(ft in (c.entity_name) for ft in focus)  # 简化匹配
    ]
    if not relevant:
        return
    lines = ["## 📚 跨书共识（多本书认同的观点）"]
    for c in relevant[:5]:
        lines.append(f"- **{c.entity_name}**: {' / '.join(c.books)} — {c.description or '观点一致'}")
    parts.append("\n".join(lines))

def _append_complements_by_type(parts, bundle, focus):
    """按实体类型筛选跨书互补。"""
    relevant = [c for c in bundle.cross_book_consensus if c.relation_type in ("CROSS_BOOK_COMPLEMENTS", "CROSS_TREATS")]
    if not relevant:
        return
    lines = ["## 📚 跨书互补（不同书的补充视角）"]
    for c in relevant[:5]:
        lines.append(f"- **{c.entity_name}**: {' vs '.join(c.books)} — {c.description or '互补视角'}")
    parts.append("\n".join(lines))

def _append_all_cross_book(parts, bundle):
    """展示全部跨书关系。"""
    _append_consensus_by_type(parts, bundle, focus=set())
    _append_complements_by_type(parts, bundle, focus=set())
    # 冲突提醒
    if bundle.cross_book_conflicts:
        lines = ["## ⚠️ 跨书冲突（不同书的观点差异）"]
        for c in bundle.cross_book_conflicts[:3]:
            lines.append(f"- **{c.entity_name}**: {' vs '.join(c.books)} ({c.neo4j_relation_type})")
        parts.append("\n".join(lines))
```

在 `build_priority_context` 中调用：

```python
# 在 L1/L2 之间插入跨书关系（所有节都展示）
_append_cross_book_section(parts, bundle, section_index)
```

#### 1c. 数据质量防护

跨书关系可能有噪声。增加过滤：
- `description` 为空的共识跳过（无实际内容）
- 同一实体只保留 1 条共识（去重）
- `entity_name` 长度 < 2 的跳过（避免噪声实体）

```python
def _append_consensus_by_type(parts, bundle, focus):
    seen = set()
    relevant = []
    for c in bundle.cross_book_consensus:
        name = c.entity_name
        if len(name) < 2 or name in seen:
            continue
        if not c.description:  # 无实际内容的共识跳过
            continue
        seen.add(name)
        relevant.append(c)
    # ... 后续格式化 ...
```

---

### 模块 2: SAME_AS 别名扩展实体检索 🟡

**文件**: `backend/src/core/knowledge_qa/bundle_consumer.py`

**目标**: 用 Neo4j SAME_AS 关系的别名扩展实体匹配，解决 "注意力" 不匹配 "专注力" 的问题。

#### 2a. 前置条件：确保 aliases 被填充

`GraphEntity.aliases` 字段存在于 `bundle.py`，但 `_expand_from_seeds` 未从 Neo4j 填充。需要在 `enhanced_query.py` 的 `_expand_from_seeds` 中增加别名提取：

```python
# 在 _expand_from_seeds 中，查询实体的 SAME_AS 关系
for entity in entities:
    query = """
        MATCH (e {name: $name})-[:SAME_AS]->(alias)
        RETURN alias.name AS alias_name
    """
    rows = session.run(query, name=entity.name).data()
    entity.aliases = [r["alias_name"] for r in rows]
```

#### 2b. _retrieve_by_entities — 别名匹配

```python
def _retrieve_by_entities(bundle, entities, top_k):
    entity_names = set()
    for e in entities:
        entity_names.add(e.name.lower())
        for alias in e.aliases:  # SAME_AS 别名
            entity_names.add(alias.lower())

    scored = []
    for p in bundle.passages:
        content_lower = p.content.lower()
        hits = sum(1 for name in entity_names if name in content_lower)
        if hits > 0:
            scored.append((p, hits))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:top_k]]
```

#### 2c. _retrieve_by_keywords — 同义词扩展

```python
def _retrieve_by_keywords(passages, query, top_k, entity_aliases=None):
    keywords = [w.strip().lower() for w in query.split() if len(w.strip()) >= 2]

    # 用实体别名扩展关键词
    if entity_aliases:
        expanded = []
        for kw in keywords:
            expanded.append(kw)
            for alias in entity_aliases.get(kw, []):
                expanded.append(alias.lower())
        keywords = list(set(expanded))

    scored = []
    for p in passages:
        content_lower = p.content.lower()
        hits = sum(1 for kw in keywords if kw in content_lower)
        if hits > 0:
            scored.append((p, hits))

    scored.sort(key=lambda x: (x[1], x[0].score), reverse=True)
    return [p for p, _ in scored[:top_k]]
```

`entity_aliases` 从 bundle 的 `cross_book_consensus` 中提取 `SAME_AS` 关系构建。

---

### 模块 3: S3 citations 修复 🔴

**文件**: `backend/src/core/knowledge_qa/nodes/recommend_types.py`

**目标**: S3 从零引用恢复为正常引用。

#### 3a. 按运动名独立搜索

```python
# 现在: search_query = " ".join(search_terms[:8]) → 一个长 query
# 改为: 每个运动名独立搜索，结果合并

search_parts = []
exercise_contexts = {}
for name in search_terms[:5]:  # 限制 5 个，避免过多 HTTP 调用
    try:
        results = await _direct_search(name, state.matched_book_ids, state=state)
        exercise_contexts[name] = results
        if results:
            search_parts.append(f"### {name}\n" + _format_search_context(results))
    except Exception as e:
        logger.warning(f"S3 引用搜索失败 ({name}): {e}")

search_context = "\n\n".join(search_parts) if search_parts else "（无可用上下文）"
```

#### 3b. 模糊关键词匹配

```python
# 现在: if ex_name_clean in excerpt:
# 改为: 关键词交集（至少 1 个关键词匹配）

exercise_keywords = set(re.split(r'[/（）\s]+', ex_name_clean))
exercise_keywords = {kw for kw in exercise_keywords if len(kw) >= 2}
excerpt_lower = excerpt.lower()
matches = sum(1 for kw in exercise_keywords if kw in excerpt_lower)
if matches >= 1:
    matched_ids.append(c.get("citation_id", ""))
```

#### 3c. 优先引用跨书共识运动

从 bundle.cross_book_consensus 提取被多书推荐的运动，在 citations 排序时优先：

```python
consensus_exercises = {
    c.entity_name
    for c in bundle.cross_book_consensus
    if c.relation_type in ("SAME_AS", "CROSS_BOOK_CONSENSUS")
    and any(kw in c.entity_name for kw in ["运动", "训练", "爬行", "舞蹈", "武术"])
}

# 排序时优先引用跨书共识运动
def _sort_citations(citations):
    return sorted(citations, key=lambda c: (
        0 if c.get("book_title", "") in consensus_exercises else 1,
        c.get("citation_id", ""),
    ))
```

---

### 模块 4: section_queries 多样化 🟡

**文件**: `backend/src/core/knowledge_qa/nodes/match_books.py`

**目标**: 不同节搜索不同维度，命中不同书籍。

#### 4a. QueryAnalysisResult 新增 synonyms

```python
class QueryAnalysisResult(BaseModel):
    # ... 现有字段 ...
    synonyms: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="关键概念→同义词/英文映射，如 {'注意力': ['inattention', '分心'], '坐不住': ['hyperactivity']}"
    )
```

#### 4b. _analyze_query prompt 补充

在 system_prompt 中增加：

```
7. **同义词映射**：为每个关键概念生成 1-2 个同义词或英文对应词
   - 格式: {"概念": ["同义词1", "同义词2"]}
   - 示例: {"注意力": ["inattention", "分心"], "坐不住": ["hyperactivity", "restlessness"]}
```

#### 4c. 重写 _build_section_queries

返回类型不变（`dict[int, str]`），但内容来自 LLM 分析：

```python
def _build_section_queries(question: str, analysis: QueryAnalysisResult) -> dict:
    queries = {}

    # S1: 孩子状态分析
    if analysis.sub_questions and len(analysis.sub_questions) > 0:
        queries[1] = analysis.sub_questions[0]
    else:
        queries[1] = _fallback_s1(question, analysis)

    # S2: 问题识别
    if analysis.sub_questions and len(analysis.sub_questions) > 1:
        queries[2] = analysis.sub_questions[1]
    else:
        queries[2] = _fallback_s2(question, analysis)

    # S3: 运动推荐
    if analysis.rewritten_queries and len(analysis.rewritten_queries) > 0:
        queries[3] = analysis.rewritten_queries[0]
    else:
        queries[3] = _fallback_s3(question, analysis)

    # S4: 运动方案 — 运动类型维度
    if analysis.exercise_focus_queries:
        queries[4] = analysis.exercise_focus_queries[0]
    else:
        queries[4] = _fallback_s4(analysis)

    # S5: 总结 — 育儿整合维度
    if analysis.summary_queries:
        queries[5] = analysis.summary_queries[0]
    else:
        queries[5] = _fallback_s5(analysis)

    return queries

def _fallback_s1(question, analysis):
    """降级: 用规则提取的特征构建 query。"""
    parts = []
    if analysis.child_age:
        parts.append(f"{analysis.child_age}儿童")
    if analysis.behavior_traits:
        parts.append(" ".join(analysis.behavior_traits[:3]))
    return " ".join(parts) if parts else question

def _fallback_s2(question, analysis):
    parts = []
    if analysis.behavior_traits:
        parts.append(" ".join(analysis.behavior_traits[:2]))
    if analysis.cognitive_traits:
        parts.append(" ".join(analysis.cognitive_traits[:2]))
    parts.append("原因分析")
    return "儿童 " + " ".join(parts) if len(parts) > 1 else question

def _fallback_s3(question, analysis):
    parts = []
    if analysis.behavior_traits:
        parts.append(" ".join(analysis.behavior_traits[:2]))
    parts.append("运动改善")
    return "儿童 " + " ".join(parts) if len(parts) > 1 else question

def _fallback_s4(analysis):
    return "儿童运动类型 适合年龄 8岁"

def _fallback_s5(analysis):
    return "儿童注意力改善 家庭环境"
```

#### 4d. 查询扩展：同义词变体追加

在 `_analyze_and_search_books` 的 Phase 2 中，为每个 query 追加同义词变体：

```python
# Phase 2: 构建多维度搜索 query
queries = []
seen = set()

def _add(q):
    q = q.strip()
    if q and q not in seen and len(q) >= 2:
        seen.add(q)
        queries.append(q)

# 主 query
for sq in analysis.sub_questions[:3]:
    _add(sq)
for rq in analysis.rewritten_queries[:3]:
    _add(rq)

# 同义词变体（从 synonyms 字段生成）
if analysis.synonyms:
    for concept, alts in analysis.synonyms.items():
        for alt in alts[:2]:
            _add(f"{alt} 儿童")
```

**返回类型保持 `dict[int, str]`**，不改 API。同义词变体在 `_analyze_and_search_books` 阶段追加，不影响下游 `section_queries` 的消费方。

---

### 模块 5: 引用 ID 全局唯一化 🔴

**文件**: `backend/src/core/knowledge_qa/nodes/verify_citations.py`

**目标**: 引用 ID 全局唯一，不再每节独立编号。

#### 5a. 全局重编号

在 `verify_citations_node` 中，遍历所有节的 citations，用全局计数器重编号：

```python
global_counter = 0
all_id_mappings = {}  # {section_index: {old_id: new_id}}

for sec_idx in sorted(state.sections.keys()):
    sec = state.sections[sec_idx]
    if not sec or not sec.citations:
        continue

    id_map = {}
    for c in sec.citations:
        old_id = c.get("citation_id", "")
        global_counter += 1
        new_id = f"C{global_counter}"
        id_map[old_id] = new_id
        c["citation_id"] = new_id

    all_id_mappings[sec_idx] = id_map
```

#### 5b. 正文引用标记替换

用正则精确匹配 `[C123]` 和独立的 `C123`（避免误替换）：

```python
for sec_idx, id_map in all_id_mappings.items():
    sec = state.sections[sec_idx]
    if not sec or not sec.content:
        continue

    new_content = sec.content
    # 按 old_id 长度降序替换（避免短 ID 替换长 ID 的子串）
    for old_id in sorted(id_map.keys(), key=len, reverse=True):
        new_id = id_map[old_id]
        # 替换 [C123] 格式
        new_content = new_content.replace(f"[{old_id}]", f"[{new_id}]")
        # 替换独立 C123（前后非字母数字）
        new_content = re.sub(rf'(?<!\w){re.escape(old_id)}(?!\w)', new_id, new_content)

    sec.content = new_content
```

---

### 模块 6: 前端展示修复 🟡

**文件**:
- `frontend/src/features/knowledge-qa/components/CitationsList.tsx`
- `frontend/src/features/knowledge-qa/components/ProgressPanel.tsx`

#### 6a. CitationsList — 按书分组 + 去重

```tsx
const CitationsList: React.FC<Props> = ({ citations }) => {
  const grouped = useMemo(() => {
    const map = new Map<string, Citation[]>();
    const seen = new Set<string>();
    for (const c of citations) {
      const key = `${c.book_title}||${c.chapter}||${c.excerpt?.slice(0, 50)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const book = c.book_title || '未知';
      if (!map.has(book)) map.set(book, []);
      map.get(book)!.push(c);
    }
    return map;
  }, [citations]);

  if (!grouped.size) return null;

  return (
    <div style={{ marginTop: 32, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
      <Title level={4}>参考文献</Title>
      {Array.from(grouped.entries()).map(([book, cites]) => (
        <div key={book} style={{ marginBottom: 16 }}>
          <Title level={5} style={{ marginBottom: 4 }}>{book}</Title>
          {cites.map(c => (
            <div key={c.citation_id} style={{ marginBottom: 8, paddingLeft: 12 }}>
              <Text>[{c.citation_id}] {c.chapter}</Text>
              <br />
              <Paragraph style={{ marginLeft: 16, color: '#666' }} ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}>
                {c.excerpt}
              </Paragraph>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};
```

去重 key = `book_title + chapter + excerpt前50字`，精确去重不误删。

---

### 模块 7: 运动类型/运动约束 🟡

**文件**:
- `backend/src/core/knowledge_qa/nodes/recommend_types.py`
- `backend/src/core/knowledge_qa/neo4j/query_dispatcher.py`

**目标**: 运动类型和运动只来自预定义清单（`运动改变大脑_运动清单.json`，93 项）。

#### 7a. Neo4j Exercise 查询后验证

```python
# query_dispatcher._query_exercises
neo4j_exercises = session.run(query, ...).data()
authorized_names = {e["name"] for e in _load_exercise_data()["exercises"]}
validated = [
    e for e in neo4j_exercises
    if fuzzy_match_exercise(e["name"], authorized_names)
]
logger.info(f"Exercise 验证: {len(neo4j_exercises)} → {len(validated)}")
```

#### 7b. S3 推荐时验证

```python
# 在 _build_s3_result 中
authorized_names = {e["name"] for e in exercise_data["exercises"]}
for sel in valid_selections:
    ex = exercise_map.get(sel.type_id)
    if ex and not fuzzy_match_exercise(ex.get("name", ""), authorized_names):
        logger.warning(f"运动 '{ex.get('name')}' 不在预定义清单中，跳过")
        continue
    # ... 正常处理 ...
```

---

### 模块 8: 进度展示修复 🟡

**文件**: `frontend/src/features/knowledge-qa/components/ProgressPanel.tsx`

#### 8a. MAIN_STEPS 重设计

```tsx
const MAIN_STEPS = [
  { key: 'started',           label: '分析问题' },
  { key: 'books_matched',     label: '匹配书籍' },
  { key: 'build_bundle_done', label: '检索知识' },
  { key: 'section_1_done',    label: '分析孩子状态' },
  { key: 'section_2_done',    label: '识别问题' },
  { key: 'section_3_done',    label: '推荐运动类型' },
  { key: 'section_4_done',    label: '制定运动方案' },
  { key: 'section_5_done',    label: '总结建议' },
  { key: 'completed',         label: '完成' },
];
```

#### 8b. 中间状态处理

```tsx
const isMainStep = MAIN_STEPS.some(s => s.key === currentStep);
if (isMainStep) {
  lastValidIndexRef.current = currentStepIndex;
} else {
  // 中间步骤：只更新 message，current 不变
}
```

#### 8c. 移除 completedSections 实时预览

删除 ProgressPanel 中 `completedSections` 的 Card 预览，节内容只在最终 ReportViewer 中展示。

---

### 模块 9: 运动清单 JSON 兜底加固 🟡

**文件**:
- `backend/src/service/knowledge_qa_service.py`
- `backend/src/core/knowledge_qa/nodes/recommend_types.py`

#### 9a. JSON 加载增加完整性校验

```python
def _load_exercise_data() -> dict:
    if hasattr(_load_exercise_data, "_cache"):
        return _load_exercise_data._cache

    path = get_exercise_json_path()
    if not Path(path).exists():
        logger.error(f"运动清单文件不存在: {path}")
        return {"exercises": [], "brain_regions": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"运动清单 JSON 解析失败: {e}")
        return {"exercises": [], "brain_regions": []}

    exercises = data.get("exercises", [])
    valid = [e for e in exercises if e.get("name") and e.get("id")]
    if len(valid) < 50:
        logger.error(f"运动清单数据异常: 仅 {len(valid)}/{len(exercises)} 项有效")
        return {"exercises": [], "brain_regions": []}

    _load_exercise_data._cache = data
    return data
```

#### 9b. 服务层启动时预校验

```python
def _load_exercise_context() -> str:
    # ... 加载 JSON ...
    exercises = data.get("exercises", [])
    valid = [e for e in exercises if e.get("name") and e.get("id")]
    if len(valid) < 50:
        logger.error(f"运动清单异常: 仅 {len(valid)} 项有效，跳过运动约束")
        _exercise_context_cache = ""
        return ""
    # ... 正常构建 markdown ...
```

**注意**：校验失败返回空字符串是安全的——S3 会走 v1 node 的 JSON 加载（独立于 exercise_context），S4 没有运动约束时 LLM 会基于 S3 输出自由发挥。

---

### 模块 10: LazyGraphRAG 排查修复 🟡

**文件**:
- `backend/src/core/knowledge_qa/bundle_builder.py`

**目标**: LazyGraphRAG 从 0 命中恢复。

#### 10a. 添加详细日志

```python
# 在 _enhanced_lazy_graph_traversal 中
for book_id in top_book_ids:
    try:
        roots = await community_repo.get_roots(scope="book", book_id=book_id)
        logger.info(f"LazyGraphRAG book={book_id[:8]}: {len(roots)} roots")
        if not roots:
            logger.warning(f"LazyGraphRAG: book {book_id[:8]} 无社区根节点")
        for root in roots:
            hits = await explore_community_tree(
                question=enhanced_query,
                root_id=root.node_id,
                community_repo=community_repo,
                max_tokens=20000,
                entity_boost_names=set(all_seeds) if all_seeds else None,
            )
            logger.info(f"  root={root.node_id}: {len(hits)} hits")
    except Exception as e:
        logger.warning(f"LazyGraphRAG 遍历失败 (book={book_id[:8]}): {e}")
```

#### 10b. 检查社区树数据

```python
# 在 _enhanced_lazy_graph_traversal 开始时
roots = await community_repo.get_roots(scope="book", book_id=top_book_ids[0])
if not roots:
    logger.error("LazyGraphRAG: 社区树未构建或为空，跳过遍历")
    return "", 0
```

#### 10c. 降低相关性阈值

如果 `explore_community_tree` 的评分阈值过高，适当降低：

```python
# 检查 explore_community_tree 的默认阈值
# 如果 > 0.5，降到 0.3
```

---

### 模块 11: LLM 书籍匹配降级处理 🟡

**文件**: `backend/src/core/knowledge_qa/nodes/match_books.py`

**目标**: `_llm_match_books` 不再全部降级到 "综合匹配"。

#### 11a. 增加超时 + 重试

```python
async def _llm_match_books(question: str, candidates: List[Dict]) -> List[MatchedBookItem]:
    # ... 现有逻辑 ...

    model = LLMServiceFactoryCompat.create_raw(
        model_name="qwen3.5-27b",
        temperature=0.3,
    )

    # 增加重试
    for attempt in range(3):
        try:
            structured_model = model.with_structured_output(MatchBooksResponse)
            result = await asyncio.wait_for(
                structured_model.ainvoke(prompt),
                timeout=20,  # 从 15s 增加到 20s
            )
            if result.matched_books:
                return result.matched_books
            logger.warning(f"LLM 书籍匹配返回空 (attempt {attempt+1})")
        except asyncio.TimeoutError:
            logger.warning(f"LLM 书籍匹配超时 (attempt {attempt+1})")
        except Exception as e:
            logger.warning(f"LLM 书籍匹配异常 (attempt {attempt+1}): {e}")

    return []  # 3 次都失败才降级
```

#### 11b. 改进降级 prompt

```python
prompt = f"""你是一个文献检索专家。根据用户问题，评估每本候选书籍的相关性。

用户问题：{question}

候选书籍：
{candidate_text}

评估规则（宽松匹配）：
- 只要书籍主题与问题的任一方面相关，就应纳入
- 不要求完全匹配，只要有部分相关性即可
- 例如：问题关于"注意力"，书籍涉及"学习方法"也算相关
"""
```

---

## 三、实施顺序

```
第一轮（核心搜索链路）— 模块 1-3
  模块 1 (跨书注入) → 模块 2 (别名扩展) → 模块 3 (S3 citations)

第二轮（引用 + 展示）— 模块 5-6, 8
  模块 5 (引用 ID) → 模块 6 (前端展示) → 模块 8 (进度展示)

第三轮（约束 + 稳定性）— 模块 7, 9-11
  模块 7 (运动约束) → 模块 9 (JSON 兜底) → 模块 10 (LazyGraphRAG) → 模块 11 (LLM 匹配)

可并行
  模块 4 (section_queries) ← 与模块 1-3 并行
```

---

## 四、涉及文件汇总

| 文件 | 模块 |
|---|---|
| `backend/src/core/knowledge_qa/bundle_consumer.py` | 1, 2 |
| `backend/src/core/knowledge_qa/nodes/recommend_types.py` | 3, 7, 9 |
| `backend/src/core/knowledge_qa/nodes/match_books.py` | 4, 11 |
| `backend/src/core/knowledge_qa/nodes/verify_citations.py` | 5 |
| `backend/src/core/knowledge_qa/nodes/generate_s4_citations.py` | 5 |
| `backend/src/core/knowledge_qa/neo4j/query_dispatcher.py` | 7 |
| `backend/src/core/knowledge_qa/neo4j/enhanced_query.py` | 2 |
| `backend/src/service/knowledge_qa_service.py` | 9 |
| `backend/src/core/knowledge_qa/bundle_builder.py` | 10 |
| `backend/src/core/knowledge_qa/bundle.py` | 2 |
| `frontend/src/features/knowledge-qa/components/CitationsList.tsx` | 6a |
| `frontend/src/features/knowledge-qa/components/ProgressPanel.tsx` | 8 |
| `frontend/src/features/knowledge-qa/stores/knowledgeQAStore.ts` | 8c |
