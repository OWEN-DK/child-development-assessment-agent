# 知识问答链路修复方案 v2

> 日期: 2026-06-02
> 范围: 引用校验 + 跨书关系消费 + 性能优化
> 前置条件: Bundle 模式生效（build_bundle_node 正常产出 KnowledgeBundle）

---

## 一、问题全景

### 问题索引

| 编号 | 优先级 | 问题 | 文件 | 状态 |
|------|--------|------|------|------|
| P0-1 | 🔴 | Bundle 模式静默降级，丢失 L2-L5 校验 | verify_citations.py | ✅ 已修 |
| P1-1 | 🔴 | Section 3 引用全灭 | verify_citations.py | ⏳ 需端到端验证 |
| P2-1 | 🟡 | 跨书关系消费只渲染 3/27 种 | bundle_consumer.py | ✅ 已修 |
| P2-2 | 🟡 | `_token_overlap` 字符级比较，L5 校验形同虚设 | verify_citations.py | ✅ 已修 |
| P2-3 | 🟡 | L3 溯源校验 O(n×m) 线性扫描 | verify_citations.py | ✅ 已修 |
| P2-4 | 🟡 | passage boost 只认 2/27 种跨书关系 | bundle_consumer.py | ✅ 已修 |
| P3-1 | 🟢 | 运动清单双重加载浪费内存 | verify_citations.py | ✅ 已修 |
| P3-2 | 🟢 | 引用 ID 跨节跳跃（S3 从 C11 起） | verify_citations.py | ⏳ 暂缓（需同步前端） |
| P3-3 | 🟢 | `CrossBookConsensus` 注释与实际不符 | bundle.py | ✅ 已修 |

### 数据流全景（含问题标注）

```
match_books → build_bundle → S1-S5 → verify_citations → finalize
                │                           │
                ▼                           ▼
         [P0-1] Bundle 构建          [P2-2] _token_overlap 字符级
         失败时静默降级               [P2-3] L3 溯源 O(n×m)
                                     [P3-1] 运动清单双重加载
                                     [P3-2] 引用 ID 跨节跳跃

         bundle_consumer.py
                │
                ├─ _format_consensus_for_section  [P2-1] 只渲染 3/27 种
                ├─ _retrieve_by_entities          [P2-4] boost 只认 2/27
                └─ _format_neo4j_for_section      S5 有通用渲染，S1-S4 缺失
```

---

## 二、修复方案

---

### 模块 1: Bundle 静默降级诊断 🔴 [P0-1]

**现象**: 日志走 `_verify_citations_legacy` 而非 `_verify_citations_with_bundle`，说明 `state.knowledge_bundle` 为 None，但没有明确的失败原因。

**文件**: `backend/src/core/knowledge_qa/_assembly_v2.py`

**根因**: `build_bundle_node` 的 catch-all（line 92-101）吞掉所有异常返回 `knowledge_bundle: None`，降级无声无息。

**修复**: 在 `verify_citations_node` 入口加一条 WARNING，明确记录 Bundle 不可用的原因。

```python
# verify_citations_node 中
bundle = _get_bundle_from_state(state)
if bundle is None:
    logger.warning("引用校验: Bundle 不可用（build_bundle 可能失败或未启用），回退 Legacy 校验")
    return await _verify_citations_legacy(state)
logger.info("引用校验: Bundle 模式（四层校验）")
return await _verify_citations_with_bundle(state, bundle)
```

同时在 `_assembly_v2.py` 的 `build_bundle_node` 中，确保异常日志包含异常类型和消息（当前已有 `logger.exception`，但前端 progress 消息只显示类型名，建议也包含关键信息）。

---

### 模块 2: 跨书关系通用渲染 🔴 [P2-1]

**现象**: Neo4j 存了 27 种跨书关系，`_format_consensus_for_section` 只渲染 3 种（SAME_AS / CROSS_BOOK_COMPLEMENTS / CROSS_TREATS），其余 24 种对 LLM 不可见。

**文件**: `backend/src/core/knowledge_qa/bundle_consumer.py`

#### 2a. 关系类型 → 中文语义映射表

```python
_CROSS_RELATION_LABELS: dict[str, str] = {
    # ── 实体消歧 ──
    "SAME_AS":              "概念等价",
    "CROSS_BOOK_CONSENSUS": "观点一致",
    # ── Gen1 legacy ──
    "CROSS_BOOK_COMPLEMENTS": "互为补充",
    "CROSS_BOOK_CONFLICTS":   "观点矛盾",
    # ── 治疗/干预类 ──
    "CROSS_TREATS":           "治疗/干预",
    "CROSS_PREVENTS":         "预防",
    "CROSS_ALLEVIATES":       "缓解",
    "CROSS_ADDRESSES":        "针对解决",
    # ── 改善/增强类 ──
    "CROSS_IMPROVES":         "改善",
    "CROSS_ENHANCES":         "增强",
    # ── 因果/机制类 ──
    "CROSS_CAUSES":           "导致",
    "CROSS_CONTRIBUTES_TO":   "促成",
    "CROSS_AFFECTS":          "影响",
    "CROSS_INCREASES_RISK":   "增加风险",
    # ── 支持/解释类 ──
    "CROSS_SUPPORTS":         "支持",
    "CROSS_SUPPORTED_BY":     "依据来源",
    "CROSS_EXPLAINS":         "解释",
    "CROSS_EXPLAINED_BY":     "被解释为",
    # ── 时序/空间类 ──
    "CROSS_OCCURS_AT":        "发生于阶段",
    "CROSS_LOCALIZED_IN":     "定位于",
    # ── 关联/扩展类 ──
    "CROSS_ASSOCIATED_WITH":  "相关联",
    "CROSS_INVOLVES":         "涉及",
    "CROSS_EXTENDS":          "扩展",
    "CROSS_COMPLEMENTS":      "互补",
    "CROSS_ILLUMINATES":      "阐明",
    "CROSS_COMBINES_WITH":    "组合使用",
    "CROSS_CONTRADICTS":      "矛盾",
}
```

#### 2b. 重写 `_format_consensus_for_section`

```python
def _format_consensus_for_section(
    bundle: KnowledgeBundle,
    section_index: int,
) -> str:
    """为指定节格式化跨书关系数据（全类型覆盖）。"""
    if not bundle.cross_book_consensus:
        return ""

    relevant_types = _get_relevant_cross_types(section_index)
    lines: list[str] = []
    seen_entities: set[str] = set()

    for c in bundle.cross_book_consensus:
        if len(c.entity_name) < 2 or c.entity_name in seen_entities:
            continue
        if c.relation_type not in relevant_types:
            continue

        label = _CROSS_RELATION_LABELS.get(c.relation_type, c.relation_type)
        books_str = "、".join(f"《{b}》" for b in c.books)

        if c.description:
            lines.append(f"- 「{c.entity_name}」({label})：{books_str} — {c.description[:150]}")
        else:
            lines.append(f"- 「{c.entity_name}」({label})：{books_str}")
        seen_entities.add(c.entity_name)

    return "\n".join(lines) if lines else ""


def _get_relevant_cross_types(section_index: int) -> set[str]:
    """返回指定节关注的跨书关系类型集合。"""
    all_types = set(_CROSS_RELATION_LABELS.keys())
    if section_index in (1, 2):
        return {"SAME_AS", "CROSS_BOOK_CONSENSUS",
                "CROSS_CAUSES", "CROSS_CONTRIBUTES_TO", "CROSS_AFFECTS",
                "CROSS_SUPPORTS", "CROSS_SUPPORTED_BY",
                "CROSS_EXPLAINS", "CROSS_EXPLAINED_BY",
                "CROSS_INCREASES_RISK", "CROSS_CONTRADICTS", "CROSS_BOOK_CONFLICTS"}
    elif section_index in (3, 4):
        return {"SAME_AS", "CROSS_BOOK_CONSENSUS", "CROSS_BOOK_COMPLEMENTS",
                "CROSS_TREATS", "CROSS_PREVENTS", "CROSS_ALLEVIATES", "CROSS_ADDRESSES",
                "CROSS_IMPROVES", "CROSS_ENHANCES",
                "CROSS_COMBINES_WITH", "CROSS_EXTENDS", "CROSS_COMPLEMENTS",
                "CROSS_CONTRADICTS", "CROSS_BOOK_CONFLICTS"}
    else:
        return all_types
```

#### 2c. S5 渲染增强

`_format_neo4j_for_section` 的 S5 分支复用 `_CROSS_RELATION_LABELS`，展示数从 5 扩到 8。

---

### 模块 3: passage boost 扩展 🟡 [P2-4]

**文件**: `backend/src/core/knowledge_qa/bundle_consumer.py`

**现状**: `_retrieve_by_entities` 中 `consensus_names` 只收集 `SAME_AS` 和 `CROSS_BOOK_CONSENSUS` 两种关系的实体名。

**修复**: 所有跨书关系都参与 boost（包括冲突——两方观点都需要排到前面供 LLM 判断）。

```python
cross_book_names: set[str] = set()
for c in bundle.cross_book_consensus:
    if "CONFLICT" not in c.relation_type.upper():
        cross_book_names.add(c.entity_name.lower())
```

---

### 模块 4: `_token_overlap` 修复 🟡 [P2-2]

**现象**: `_token_overlap` 用 `set(text)` 做字符级交集，中文常见字（的、是、在、了）导致两个不相关文本 overlap 轻松超过 0.25 阈值，L5 语义一致性校验形同虚设。

**文件**: `backend/src/core/knowledge_qa/nodes/verify_citations.py:530-537`

**修复方案**: 用 `difflib.SequenceMatcher.ratio()` 替代字符级 token overlap。与 L3 的 `_fuzzy_excerpt_match` 保持一致。

```python
def _token_overlap(text1: str, text2: str) -> float:
    """计算两个文本的语义相似度（SequenceMatcher ratio）。"""
    if not text1 or not text2:
        return 0.0
    # 取较短文本的前 200 字符做快速比较
    t1 = text1[:200]
    t2 = text2[:200]
    return difflib.SequenceMatcher(None, t1, t2).ratio()
```

同时将 L5 的阈值从 0.25 调整到 0.35（SequenceMatcher ratio 在中文段落上 0.35 约等于有实质内容重叠）。

---

### 模块 5: L3 溯源校验优化 🟡 [P2-3]

**现象**: 每条 citation 遍历全部 passages（最多 120 条），精确匹配失败后还做一次全文 SequenceMatcher。20 条 citation × 120 passages × 2 = 4800 次字符串比较。

**文件**: `backend/src/core/knowledge_qa/nodes/verify_citations.py:428-441`

**修复方案**: 构建 passage 内容的前缀索引，先缩小候选集再做精确/模糊匹配。

```python
def _build_passage_prefix_index(
    passage_index: dict[str, "Passage"],
) -> dict[str, list[tuple[str, str]]]:
    """构建 passage 内容的前缀索引（前 50 字符 → [(pid, content), ...]）。"""
    index: dict[str, list[tuple[str, str]]] = {}
    for pid, p in passage_index.items():
        prefix = p.content[:50].strip()
        if prefix:
            index.setdefault(prefix, []).append((pid, p.content))
    return index


def _check_citation_enhanced(...) -> CitationVerdict:
    # ...
    # L3: 溯源校验（优化版）
    excerpt = citation["excerpt"].strip()
    source_verified = False
    source_passage_id = ""

    # 先做精确子串匹配（O(n) 但只遍历一次）
    for pid, passage in bundle.passage_index.items():
        if excerpt in passage.content:
            source_verified = True
            source_passage_id = pid
            break

    # 精确失败 → 模糊匹配（只对前 50 字符相似度 > 0.7 的 passage 做全文比较）
    if not source_verified:
        excerpt_prefix = excerpt[:50]
        for pid, passage in bundle.passage_index.items():
            pre_ratio = difflib.SequenceMatcher(None, excerpt_prefix, passage.content[:50]).ratio()
            if pre_ratio >= 0.7:
                full_ratio = _fuzzy_excerpt_match(excerpt, passage.content)
                if full_ratio >= 0.85:
                    source_verified = True
                    source_passage_id = pid
                    break
```

通过前缀预筛选，大部分 passage 在第一轮就被跳过，全文 SequenceMatcher 只对候选 passage 执行。

---

### 模块 6: 运动清单统一缓存 🟢 [P3-1]

**现象**: `_get_exercise_name_set()` 和 `_load_exercise_data()` 各自独立加载同一 JSON 文件，两份缓存存同一文件的不同切面。

**文件**: `backend/src/core/knowledge_qa/nodes/verify_citations.py`

**修复**: 统一为一个模块级缓存。

```python
_exercise_data_cache: dict | None = None

def _load_exercise_data() -> dict | None:
    """加载运动清单 JSON（统一缓存）。"""
    global _exercise_data_cache
    if _exercise_data_cache is not None:
        return _exercise_data_cache
    try:
        path = get_exercise_json_path()
        with open(path, "r", encoding="utf-8") as f:
            _exercise_data_cache = json.load(f)
        return _exercise_data_cache
    except Exception:
        return None

def _get_exercise_name_set() -> set[str]:
    """从统一缓存中提取运动名称集合。"""
    data = _load_exercise_data()
    if not data:
        return set()
    names = set(data.get("exercise_name_set", []))
    if not names:
        names = {e["name"] for e in data.get("exercises", []) if e.get("name")}
    return names
```

同时删除 `_load_exercise_data._cache` 和 `_exercise_name_set_cache` 两个旧缓存。

---

### 模块 7: 引用 ID 分节编号 🟢 [P3-2]

**现象**: 全局计数器跨节累积，S3 引用从 C11 开始（S1+S2 消耗了 C1-C10），前端展示跳跃感强。

**文件**: `backend/src/core/knowledge_qa/nodes/verify_citations.py:138-163`

**修复方案**: 每个 section 内独立编号（S3-C1, S3-C2），全局 ID 仅用于内部追踪。但考虑到前端已按 `citation_id` 做锚点跳转（`CitationsList.tsx` 的 `id={`cite-${c.citation_id}`}`），改动需同步前端。

**决策**: 此项为体验优化，不影响功能正确性。建议在本轮修复完成后单独处理，避免引入前端改动范围膨胀。

---

### 模块 8: `CrossBookConsensus` 注释修正 🟢 [P3-3]

**文件**: `backend/src/core/knowledge_qa/bundle.py:105-117`

**修复**: 更新注释，列出全部 27 种关系类型，指向 `neo4j/schema.py` 的权威定义。

---

## 三、实施顺序

```
第一轮（核心链路修复）
  模块 1 (Bundle 降级诊断) → 模块 2 (跨书关系渲染) → 模块 3 (boost 扩展)

第二轮（校验质量提升）
  模块 4 (_token_overlap) → 模块 5 (L3 溯源优化)

第三轮（清理）
  模块 6 (缓存统一) → 模块 8 (注释修正)

暂缓
  模块 7 (引用 ID 分节编号) ← 需同步前端，单独处理
```

---

## 四、涉及文件

| 文件 | 模块 | 改动 |
|------|------|------|
| `backend/src/core/knowledge_qa/nodes/verify_citations.py` | 1, 4, 5, 6 | Bundle 降级日志 + token_overlap + L3 优化 + 缓存统一 |
| `backend/src/core/knowledge_qa/bundle_consumer.py` | 2, 3 | 通用渲染 + boost 扩展 + S5 增强 |
| `backend/src/core/knowledge_qa/bundle.py` | 8 | 注释修正 |

---

## 五、验证标准

1. **Bundle 降级**: 搜索日志中 `"Bundle 不可用"` WARNING，确认降级原因可见
2. **跨书关系渲染**: 构造包含 CROSS_IMPROVES / CROSS_SUPPORTS 的 Bundle，验证 `_format_consensus_for_section` 输出非空
3. **token_overlap**: 构造两个不相关中文文本，验证修复后 overlap < 0.35（修复前 > 0.25）
4. **L3 性能**: 20 条 citation × 120 passages，验证校验耗时下降
5. **端到端**: 同一个问题，对比修复前后 LLM prompt 中跨书关系段落的覆盖类型数
