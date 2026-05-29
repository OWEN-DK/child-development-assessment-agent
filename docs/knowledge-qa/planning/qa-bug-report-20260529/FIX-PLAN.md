# 知识问答系统修复方案

**基于**: [analysis.md](./analysis.md) 第 17 轮审查  
**日期**: 2026-05-29  
**修复范围**: 6 个 Bug + 2 个次要问题

---

## 修复清单

| # | Bug | 文件 | 改动量 | 优先级 |
|---|-----|------|--------|--------|
| F1 | #2 Phase schema alias | `schemas/knowledge_qa.py` | 3 行 | P0 |
| F2 | #2 降级路径字段读取统一 | `nodes/plan_assemble.py` | 2 行 | P0 |
| F3 | #2 conclusion 字段读取 | `nodes/conclusion.py` | 1 行 | P0 |
| F4 | #2+#3 outline prompt 修正 | `prompts/templates.py` | 4 行 | P0 |
| F5 | #1 问题预处理 + 来源配额 | `nodes/match_books.py` | ~50 行 | P1 |
| F6 | #6 重试路由故障分类 | `_assembly.py` | ~8 行 | P2 |
| F7 | #5 expand prompt 放宽 | `prompts/templates.py` | 2 行 | P2 |
| F8 | 次要 PlanSummary | `schemas/knowledge_qa.py` | 1 行 | P2 |

---

## F1: Phase Schema — `alias="name"` + `populate_by_name` (P0)

**文件**: `backend/src/schemas/knowledge_qa.py` L516-520

**改动前**:
```python
class Phase(BaseModel):
    """训练阶段"""
    phase_name: str = Field(..., description="阶段名称，如 '适应期'、'强化期'")
    weeks: List[Week] = Field(default_factory=list)
```

**改动后**:
```python
class Phase(BaseModel):
    """训练阶段"""
    model_config = {'populate_by_name': True}
    phase_name: str = Field(..., alias="name", description="阶段名称，如 '适应期'、'强化期'")
    weeks: List[Week] = Field(default_factory=list)
```

**原理**:
- `alias="name"`: 接受 LLM 输出的 `{"name": "适应期"}` 作为 `phase_name` 的输入
- `populate_by_name=True`: 同时允许 `Phase(phase_name="适应期")` 的直接构造（plan_assemble L543/L639 等 5 处使用）
- `model_dump()` 默认 `by_alias=False`，输出 `{"phase_name": "适应期"}`，下游 `_render_s4_markdown` 和 `conclusion.py` 无需改动

**验证**:
```python
from pydantic import BaseModel, Field
class Phase(BaseModel):
    model_config = {'populate_by_name': True}
    phase_name: str = Field(..., alias="name")
    weeks: list = Field(default_factory=list)

# LLM 输出格式（用 alias）
assert Phase(name="适应期", weeks=[]).phase_name == "适应期"
# 代码直接构造（用 field name）
assert Phase(phase_name="适应期", weeks=[]).phase_name == "适应期"
# model_dump 输出 field name
assert Phase(name="适应期").model_dump()["phase_name"] == "适应期"
# alias 输入 → dump 输出不同
assert "name" not in Phase(name="适应期").model_dump()
assert Phase(name="适应期").model_dump(by_alias=True)["name"] == "适应期"
```

---

## F2: plan_assemble 降级路径字段读取统一 (P0)

**文件**: `backend/src/core/knowledge_qa/nodes/plan_assemble.py`

### F2a: 内层异常处理 L543

**改动前**:
```python
                    safe_phases.append(Phase(
                        phase_name=ph.get("phase_name", "阶段"),
                        weeks=safe_weeks,
                    ))
```

**改动后**:
```python
                    safe_phases.append(Phase(
                        phase_name=ph.get("phase_name") or ph.get("name", "阶段"),
                        weeks=safe_weeks,
                    ))
```

**原理**: 优先读 `phase_name`（正常路径 model_dump 输出），降级读 `name`（outline 原始数据）。

### F2b: 外层异常处理 L639

**改动前**:
```python
                        fallback_phases.append(Phase(
                            phase_name=ph.get("name", "阶段"),
                            weeks=safe_weeks,
                        ))
```

**改动后**:
```python
                        fallback_phases.append(Phase(
                            phase_name=ph.get("phase_name") or ph.get("name", "阶段"),
                            weeks=safe_weeks,
                        ))
```

**原理**: 与 F2a 保持一致，两个降级路径用相同的字段读取策略。

---

## F3: conclusion.py 字段读取统一 (P0)

**文件**: `backend/src/core/knowledge_qa/nodes/conclusion.py` L54

**改动前**:
```python
            phase_name = ph.get("phase_name", "")
```

**改动后**:
```python
            phase_name = ph.get("phase_name") or ph.get("name", "")
```

**原理**: structured_data 可能来自正常路径（有 `phase_name`）或降级路径（有 `name`）。

---

## F4: outline Prompt 修正 (P0)

**文件**: `backend/src/core/knowledge_qa/prompts/templates.py`

### F4a: 输出格式字段名统一 L245

**改动前**:
```
- phases[]: 每阶段含 phase_id(PH01)、name、goal、duration_weeks、citation_ids、weeks[]
```

**改动后**:
```
- phases[]: 每阶段含 phase_id(PH01)、phase_name、goal、duration_weeks、citation_ids、weeks[]
```

### F4b: 加总时长硬约束 L230

**改动前**:
```
2. 划分阶段（**至少 2 个阶段**，每阶段 1-4 周），设定目标和每周重点
```

**改动后**:
```
2. 划分阶段（**固定 2 个阶段，总时长 4 周（28 天），每阶段 2 周**），设定目标和每周重点
```

### F4c: 阶段命名要求段落同步 L270

**改动前**:
```
- phase_name 必须有实际含义，不能使用"阶段"这种空泛名称
```

**改动后**:
```
- phase_name 字段必须有实际含义，不能使用"阶段"这种空泛名称
```

（微调：加"字段"二字，与 `phase_name` 字段名对应，避免歧义）

### F4d: 自审核检查项同步 L260

确认自审核中 `phase_id` 格式检查无冲突。当前写的是 `phase_id 格式必须是 PH01-PH99`，不涉及 `name`/`phase_name`，无需改动。

---

## F5: match_books 问题预处理 + 来源配额 (P1)

**文件**: `backend/src/core/knowledge_qa/nodes/match_books.py`

**根因修正**: 家长问题中「有什么运动可以帮助改善」的「运动」关键词主导搜索语义。RAG 向量搜索将整句作为 query，「运动」的权重压倒「注意力不集中」「坐不住」等行为描述，15 条结果全部来自《运动改变大脑》。来源配额无法解决 —— 单源时无从分配。

**真正的修复方向**: 问题预处理 —— 搜索前用 LLM 提取孩子关键信息（年龄、行为、认知特征），去除「运动」「方法」等解决方案导向措辞，用中性行为描述搜索。

### F5a: 新增 _preprocess_question（核心修复）

```python
async def _preprocess_question(question: str) -> List[str]:
    # LLM 提取 2-3 组搜索关键词：
    # 第 1 组: 行为/认知特征（注意力不集中、坐不住、冲动）
    # 第 2 组: 发展阶段/年龄（8岁、学龄期、执行功能）
    # 第 3 组: 干预领域（感觉统合、前庭系统、自我调节）
    # 不包含「运动」「方法」「建议」等解决方案类词汇
    ...
```

### F5b: 来源配额（防御性后处理，保留）

当多源结果存在但分布不均时生效，作为预处理的补充保障。代码同前次提交。

### F5c: 调用位置

```python
# match_books_node 中
preprocessed = await _preprocess_question(state.question)
all_results = await _analyze_and_search_books(state.question, extra_queries=preprocessed)
all_results = _apply_source_quota(all_results)  # 防御性
candidates = await _extract_candidate_books(all_results)
```

## F6: S4 重试路由故障分类 (P2)

**文件**: `backend/src/core/knowledge_qa/_assembly.py` L39-62

**改动前**:
```python
    needs_retry = state.s4_needs_retry or any(
        "section_4_outline_no_exercises" in e for e in (state.errors or [])
    )
```

**改动后**:
```python
    # 区分结构性故障（重试无意义）和瞬时故障（重试可能成功）
    structural_errors = (
        "section_4_expand_empty" in str(state.errors)
        or "section_4_outline_no_exercises" in str(state.errors)
    )
    needs_retry = state.s4_needs_retry and not structural_errors
```

**原理**: `section_4_expand_empty` 表示大纲无运动条目（结构性问题），重试不会改善。`s4_needs_retry` 仅在 expand 完全失败时设置，此时应区分失败原因。

---

## F7: expand Prompt 放宽描述约束 (P2)

**文件**: `backend/src/core/knowledge_qa/prompts/templates.py`

### F7a: SECTION_4_EXPAND_SYSTEM L317

**改动前**:
```
     * description: 执行要点和家长指导（≤50字）
```

**改动后**:
```
     * description: 执行要点和家长指导（2-4句话，包含动作要领和呼吸提示）
```

### F7b: SECTION_4_EXPAND_GROUP_SYSTEM L373

**改动前**:
```
- notes: 执行要点/教练提示（1-2句话）
```

**改动后**:
```
- notes: 执行要点/教练提示（2-3句话，包含动作要领、呼吸提示和家长配合要点）
```

---

## F8: PlanSummary 补全 intensity_overall (P2)

**文件**: `backend/src/schemas/knowledge_qa.py` L523-530

**改动前**:
```python
class PlanSummary(BaseModel):
    """方案摘要"""
    total_duration_days: int = Field(..., description="总天数")
    total_phases: int = Field(..., description="阶段数")
    daily_duration_min: int = Field(..., description="每日训练时长(分钟)")
    weekly_frequency: int = Field(..., description="每周训练频率(天)")
```

**改动后**:
```python
class PlanSummary(BaseModel):
    """方案摘要"""
    total_duration_days: int = Field(..., description="总天数")
    total_phases: int = Field(..., description="阶段数")
    daily_duration_min: int = Field(..., description="每日训练时长(分钟)")
    weekly_frequency: int = Field(..., description="每周训练频率(天)")
    intensity_overall: str = Field(default="中", description="整体强度: 低/中/高")
```

---

## 验收测试方案

### 测试用例

**输入**: `我儿子8岁，上课注意力不集中，写作业坐不住，经常被老师投诉，有什么运动可以帮助改善？`

### 验收标准

| # | 检查项 | 预期 | 对应修复 |
|---|--------|------|---------|
| 1 | `partial` | `False` | F1+F2 |
| 2 | `phases` 数量 | ≥2 | F1+F4b |
| 3 | `phase_name` 值 | 非 "阶段"（如"适应期"、"强化期"） | F1 |
| 4 | `total_duration_days` | =28 | F4b |
| 5 | citations 覆盖书籍数 | ≥2 本不同书 | F5 |
| 6 | `search_coverage` | 至少 2 本书有命中 | F5 |
| 7 | `description` 长度 | 每条 ≥30 字 | F7 |
| 8 | 无 `s4_needs_retry` | 不触发无效重试 | F6 |
| 9 | Markdown 渲染 | 无"第X阶段：阶段" | F1 |

### 运行方式

```bash
cd backend
python -m pytest tests/integration/knowledge_qa/test_live_pipeline.py -v -k "attention"
```

或手动调用 API:

```bash
curl -X POST http://localhost:8000/api/v1/knowledge-qa \
  -H "Content-Type: application/json" \
  -d '{"question": "我儿子8岁，上课注意力不集中，写作业坐不住，经常被老师投诉，有什么运动可以帮助改善？"}'
```

---

## 修复依赖顺序

```
F1 (schema) ─→ F2 (降级读取) ─→ F3 (conclusion)
                                    ↓
F4 (prompt) ──────────────────→ 整体验证
F5 (来源配额) ────────────────→ 整体验证
F6 (重试路由) ────────────────→ 整体验证
F7 (expand prompt) ───────────→ 整体验证
F8 (PlanSummary) ─────────────→ 整体验证
```

F1 是前置依赖（F2/F3 的字段读取策略依赖 F1 的 alias 方案）。其余修复相互独立。

---

## 已知局限

### F5 来源配额的局限性

`_apply_source_quota` 只在搜索结果中**存在多本书**时有效。当 RAG 返回的结果完全来自同一本书（如 Bug #1 的实际场景：15 条全部来自"运动改变大脑"），配额无法凭空创造多样性。

**实测结果**:
| 场景 | 配额前候选 | 配额后候选 |
|------|-----------|-----------|
| A=13, B=2 | A, B | A, B |
| A=15（完全垄断） | A | A |

**补充方案**（不在本次修复范围，建议后续迭代）:
1. **RAG 层面**: 调用 `/rag/books` 获取全部已索引书籍列表，对每本书做一次独立搜索，合并结果
2. **查询分解**: 将用户问题按语义维度拆分为 2-3 个子查询（注意力机制 + 运动干预 + 儿童发展），每个子查询天然命中不同书籍

### 预存测试问题

以下测试在改动前已失败，与本次修复无关:
- `tests/unit/knowledge_qa/test_phase2_schema.py` × 3: `ExerciseTypeItem` 测试数据使用 `tier="核心推荐"`（应为 `"primary"/"secondary"/"supplementary"`）且缺少 `type_id`
- `tests/unit/tracing/test_trace_model.py` × 1: tracing 序列化测试

---

## 线上验证结果（2026-05-29）

### 代码修复生效确认

| 修复 | 验证结果 |
|------|---------|
| F1 Phase alias | ✅ `phase_name="能量释放与专注激活期（第1-2周）"`，不再为"阶段" |
| F2 降级路径统一 | ✅ Pydantic 校验通过，未触发降级 |
| F3 conclusion 统一 | ✅ 无报错 |
| F4 outline prompt | ✅ 模板已正确加载（数据库无覆盖） |
| F5 来源配额 | ⚠️ match_books 阶段有效，section 级搜索无效 |
| F6 重试路由 | ✅ 未触发重试（正常路径） |
| F7 expand prompt | ✅ 模板已更新 |
| F8 PlanSummary | ✅ `intensity_overall="中"` |

### 待修复的新问题

#### F9: phases 数量校验（P1）

**位置**: `plan_outline_node` 后处理

**问题**: LLM 不遵守 "固定 2 个阶段" 约束，只生成 1 个 phase。prompt 已更新但模型服从率不足。

**方案**: 在 `plan_outline_node` 的 phases 校验逻辑中（约 L95），增加数量检查：

```python
# 现有逻辑
if not phases:
    # 重试或降级

# 新增: phases 数量不足时补全
if len(phases) < 2:
    logger.warning(f"plan_outline: LLM 只生成 {len(phases)} 个阶段，自动补全第 2 阶段")
    phases = _ensure_min_phases(phases, state, min_phases=2)
```

新增 `_ensure_min_phases` 函数，从已有 phase 的 weeks 结构推导第 2 阶段（复制结构、调整 phase_name 和 week_index）。

#### F10: section 级搜索问题预处理（P1）

**位置**: `nodes/base.py` 的 `_direct_search`

**问题**: 各 section 的 `_direct_search` 用 section content 搜索，content 中可能包含「运动」等偏向性词汇，导致搜索结果仍被单书垄断。

**方案**: 对搜索 query 做轻量预处理 —— 去除解决方案导向词汇，保留行为/认知描述：

```python
# base.py _direct_search 中
bias_words = ['运动', '锻炼', '方法', '建议', '训练', '改善']
for word in bias_words:
    query = query.replace(word, '')
```

或复用 F5 的 `_preprocess_question` 为每个 section 生成针对性搜索 query。

#### F11: partial 标记过于激进（P2）

**文件**: `nodes/verify_citations.py:189`

**问题**: `verify_citations` 在某节所有 citations 被剔除时设置 `partial=True`。但 citations 被剔除（excerpt < 10 字符）不代表内容不完整 —— S3 的 `structured_data.exercise_types` 有 5 项完整数据，仅 citations 质量不达标。

**根因确认**: 线上测试中 S3 的 LLM 生成了过短的 excerpt（< 10 字符），verify_citations 全部剔除 → `partial=True` → 前端显示"部分生成"。

**方案**: 将 "citations 全部被剔除" 的严重程度从 `partial=True` 降级为 warning：

```python
# verify_citations.py:187-190
# 改动前:
if not valid_citations:
    errors.append(f"section_{i}_citations_all_rejected")
    partial = True

# 改动后:
if not valid_citations:
    errors.append(f"section_{i}_citations_all_rejected")
    # 仅在 content 也为空时标记 partial（内容缺失）
    # citations 质量不达标不等于内容不完整
    if not sec.content or len(sec.content.strip()) < 20:
        partial = True
```

同理检查 L244（S3 运动名称不在清单）和 L276（S4 运动名称不在清单）的 `partial=True` 是否过于激进。
