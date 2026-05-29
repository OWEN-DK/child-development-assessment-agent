# Phase 5 问题修复方案 — S3/S4 格式失效 & Markdown 渲染异常

> 日期: 2026-05-28 | 基于 report-1779961272128 实际输出逆向诊断
> 前置: Phase 1-4 已实施 | 本文覆盖 Phase 5 的 4 个阻塞问题

---

## 〇、问题总览

实际运行一个 8 岁男孩问题，两次 report 输出完全一致，暴露出 4 类问题：

| # | 问题 | 严重度 | 现象 |
|---|------|--------|------|
| A | **S4 降级**：outline→expand→assemble 链路断裂 | P0 | S4 只有大纲无方案，weeks=0 |
| B | **S3 数据残缺**：MovNat 条目 5 字段为空 + category 截断 | P1 | 前端渲染不完整 |
| C | **Markdown 渲染空壳**：hasRenderableStructuredData 对降级数据返回 true | P1 | S4 渲染成空壳，比 outline content 更差 |
| D | **S5 结论上下文不足**：S3/S4 精简后结论节点拿不到完整上下文 | P1 | 结论缺少具体运动引用 |
| E | **plan_outline 1200 字限制**：正文强制截断限制了 LLM 输出详细度 | P0 | phases 结构不完整，间接导致 S4 降级 |

---

## 一、问题 A：S4 降级 — outline→expand→assemble 链路断裂

### 根因

```
plan_outline_node (LLM)
  ↓ phases 有顶层结构，但 weeks→days→exercises 缺少 name
plan_expand_parallel_node
  ↓ _extract_exercise_slots → filter ex.get("name") → slots=[]
  ↓ 返回 {"current_step": ["section_4_expand_empty"]}
  ↓ 未设置 section_4_slots / section_4_group_results
plan_assemble_node
  ↓ if not slots or not group_results → 降级路径
  ↓ 硬编码 plan_summary + 占位 phase + caution
```

**核心矛盾**：`Section4OutlineResponse` 的 `phases: List[Dict[str, Any]]` 只校验 `min_length=1`，不校验嵌套的 `weeks→days→exercises→name`。LLM 可以生成符合顶层约束但内部空心的结构。

### 方案 A1：plan_outline 后置校验 + 自动重试（推荐）

**位置**: `nodes/plan_outline.py:72`（`_invoke_llm_structured` 返回后）

```python
# plan_outline.py:72 后插入
data = response.model_dump() if hasattr(response, "model_dump") else response
if isinstance(data, str):
    data = {"title": "运动方案大纲", "content": data, "citations": [], "structured_data": {}}

# ─── 新增：校验 phases 中的 exercise 完整性 ───
exercise_count = _count_exercises_in_phases(data.get("phases", []))
if exercise_count == 0:
    logger.warning("plan_outline: phases 中无运动条目，触发重试")
    raise ValueError("plan_outline 生成的 phases 缺少 exercise 条目")


# ─── 新增辅助函数（同文件底部） ───
def _count_exercises_in_phases(phases: list) -> int:
    """统计 phases 中所有带 name 的 exercise 数量。"""
    count = 0
    for phase in (phases or []):
        for week in phase.get("weeks", []):
            for day in week.get("days", []):
                for ex in day.get("main_exercises", []):
                    if ex.get("name"):
                        count += 1
    return count
```

**效果**：plan_outline 生成无 exercise 的 outline 时触发 `Exception` → `plan_outline_node:101` catch → `errors` 写入 `section_4_outline_failed`。配合方案 A2 的图级重试实现自动恢复。

**改动量**: `plan_outline.py` +15 行

---

### 方案 A2：图级 section_4 重试机制（关键）

**位置**: `_assembly.py` + `knowledge_qa_service.py`

**现状**：图是线性的（`plan_outline → plan_expand_parallel → plan_assemble`），plan_outline 失败后整个 pipeline 缺少自动恢复。

**方案**：在 `_run_qa_pipeline` 外层包装一个 section_4 重试循环，最多 2 次。

```python
# knowledge_qa_service.py — _run_qa_pipeline 内

MAX_S4_RETRIES = 2

async def _run_qa_pipeline(self, task_id, question, book_ids, stream):
    # ... 现有 S1-S3 逻辑 ...

    # S4 带重试
    s4_ok = False
    for attempt in range(MAX_S4_RETRIES):
        try:
            # plan_outline
            outline_result = await plan_outline_node(state)
            state = {**state, **outline_result}
            if "section_4_outline_failed" in state.get("errors", []):
                raise RuntimeError("plan_outline failed")

            # plan_expand_parallel
            expand_result = await plan_expand_parallel_node(state)
            state = {**state, **expand_result}

            # plan_assemble
            assemble_result = await plan_assemble_node(state)
            state = {**state, **assemble_result}

            s4_ok = True
            break
        except Exception as e:
            logger.warning(f"S4 attempt {attempt + 1}/{MAX_S4_RETRIES} failed: {e}")
            if attempt == MAX_S4_RETRIES - 1:
                # 最后一次失败 → 走降级（plan_assemble 已有降级路径）
                state["section_4_outline"] = state.get("section_4_outline") or {
                    "title": "运动方案大纲",
                    "content": "方案生成失败，请稍后重试。",
                    "phases": [],
                }
                state["section_4_slots"] = None
                state["section_4_group_results"] = None
                assemble_result = await plan_assemble_node(state)
                state = {**state, **assemble_result}

    # ... 继续 S5 ...
```

**注意**：这需要将 S4 从编译后的 `StateGraph` 中拆出，或者改为在 service 层手动编排 S4 的三个节点。另一种更轻量的方式是让图本身支持 section_4 的条件回边——但 LangGraph 条件边改动较大，service 层重试更务实。

**改动量**: `knowledge_qa_service.py` +40 行

---

### 方案 A3：加强 Section4OutlineResponse schema（长效）

**位置**: `schemas/knowledge_qa.py:322`

将 `phases: List[Dict[str, Any]]` 改为带嵌套模型的严格类型：

```python
class OutlineExercise(BaseModel):
    exercise_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type_id: str = Field(default="")
    category: str = Field(default="")

class OutlineDay(BaseModel):
    day_index: int = Field(..., ge=1)
    main_exercises: List[OutlineExercise] = Field(default_factory=list)

class OutlineWeek(BaseModel):
    week_index: int = Field(..., ge=1)
    days: List[OutlineDay] = Field(default_factory=list)

class OutlinePhase(BaseModel):
    phase_id: str = Field(..., min_length=1)
    phase_name: str = Field(..., min_length=1)
    weeks: List[OutlineWeek] = Field(default_factory=list, min_length=1)

class Section4OutlineResponse(BaseModel):
    title: str = Field(default="运动方案大纲")
    content: str = Field(..., min_length=1)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    phases: List[OutlinePhase] = Field(default_factory=list, min_length=1)
    structured_data: Dict[str, Any] = Field(default_factory=dict)
```

**风险**：qwen3.5-27b 的 `with_structured_output` 可能不严格遵循嵌套模型（已知问题）。需要在测试环境验证 10+ 条真实 case。如果失败率高，回退到方案 A1（后置校验）作为最小可行方案。

**改动量**: `schemas/knowledge_qa.py` +40 行

---

## 二、问题 B：S3 数据残缺

### 根因

LLM 对超长名称运动（MovNat: 37 字符含括号）生成质量下降：
- `target_skills: []`
- `recommendation_rationale: ""`
- `citation_ids: []`
- `target_problem_ids: []`
- `category: "力量训练(综合"` ← 缺右括号
- `_original_name` 内部字段泄露到 API 输出

### 方案 B1：_validate_and_fix_s3_structured_data 增强修复

**位置**: `nodes/recommend_types.py:87`

现有函数只处理 `exercise_types` 为空的情况。需增加对单条 exercise 残缺字段的修复：

```python
def _validate_and_fix_s3_structured_data(s3: SectionOutput, exercise_list_path: str) -> SectionOutput:
    sd = s3.structured_data
    if not isinstance(sd, dict):
        return s3

    ets = sd.get("exercise_types", [])
    if not ets:
        # 现有逻辑：从 content 和运动清单提取
        return _extract_exercise_types_from_content(s3, exercise_list_path)

    # ─── 新增：逐条修复残缺字段 ───
    ets = _repair_exercise_fields(ets, exercise_list_path)
    sd["exercise_types"] = ets
    s3.structured_data = sd
    return s3


def _repair_exercise_fields(ets: list, exercise_list_path: str) -> list:
    """修复单条 exercise 的残缺字段：补全 category、移除内部字段、默认值填充。"""
    import json
    from pathlib import Path

    # 加载运动清单作为修复参考
    try:
        with open(exercise_list_path, "r", encoding="utf-8") as f:
            ex_data = json.load(f)
    except Exception:
        ex_data = {}

    repaired = []
    for et in ets:
        # 1. 移除内部字段
        et.pop("_original_name", None)

        # 2. 修复 category 截断（如 "力量训练(综合" → "力量训练(综合)"）
        cat = et.get("category", "")
        if cat and cat.count("(") != cat.count(")"):
            et["category"] = cat + ")" if cat.endswith("(综合") else cat

        # 3. 空字段给默认值
        if not et.get("target_skills"):
            et["target_skills"] = ["综合运动能力"]
        if not et.get("recommendation_rationale"):
            et["recommendation_rationale"] = (
                f"{et.get('name', '该运动')}可促进身体协调、专注力及神经发育。"
            )
        if not et.get("citation_ids"):
            et["citation_ids"] = []
        if not et.get("target_problem_ids"):
            et["target_problem_ids"] = []

        repaired.append(et)
    return repaired
```

**改动量**: `recommend_types.py` +35 行

---

### 方案 B2：_simplify_s3_content 增强摘要质量

**位置**: `nodes/recommend_types.py:63`

当前输出：`"针对孩子推荐4种运动类型，包括跑酷(核心)..."`（56 字，无年龄信息）

```python
def _simplify_s3_content(section: SectionOutput) -> str:
    sd = section.structured_data
    if not isinstance(sd, dict):
        return section.content[:100] if section.content else "运动类型推荐"

    ets = sd.get("exercise_types", [])
    if not ets:
        return "已根据孩子情况生成个性化运动类型推荐。"

    child_age = sd.get("child_age_group", "")
    age_prefix = f"针对{child_age}" if child_age else "根据孩子情况"

    tiers_cn = {"primary": "核心", "secondary": "辅助", "supplementary": "补充"}

    primary = [et for et in ets if et.get("tier") == "primary"]
    secondary = [et for et in ets if et.get("tier") == "secondary"]

    parts = []
    if primary:
        names = "、".join(et["name"] for et in primary)
        parts.append(f"核心推荐：{names}")
    if secondary:
        names = "、".join(et["name"] for et in secondary)
        parts.append(f"辅助推荐：{names}")

    detail = "；".join(parts) if parts else f"共 {len(ets)} 项运动类型"

    return f"{age_prefix}，{detail}。"
```

**效果**：
```
根据孩子情况，核心推荐：跑酷、武术/功夫；辅助推荐：慢跑、自然训练MovNat系统。
```

**改动量**: `recommend_types.py` +18 -12 行

---

## 三、问题 C：Markdown 渲染空壳

### 根因

`hasRenderableStructuredData` 对 S4 降级数据返回 `true`（`phases.length > 0` → 1 个占位 phase），触发 `renderS4Markdown`。但降级 phase 的 `weeks=[]`，渲染结果是空壳方案总览 + caution 警告——比直接用 outline content 更差。

### 方案 C1：S4 深度校验 hasRenderableStructuredData

**位置**: `frontend/src/features/knowledge-qa/utils/renderMarkdown.ts:168`

```typescript
function hasRenderableStructuredData(section: SectionOutput): boolean {
  const sd = section.structured_data || {};
  if (section.index === 3) {
    const ets = sd.exercise_types;
    return Array.isArray(ets) && ets.length > 0;
  }
  if (section.index === 4) {
    const phases = sd.phases;
    if (!Array.isArray(phases) || phases.length === 0) return false;
    // ─── 新增：深度校验——至少有一个 phase 包含非空 weeks ───
    return phases.some(
      (p: any) => Array.isArray(p.weeks) && p.weeks.length > 0
    );
  }
  return false;
}
```

**效果**：降级 S4（weeks=[]）走 `content.length > 80` fallback → 显示 outline 的完整 Markdown（203 字，含方案总述和核心原则），比空壳渲染好得多。

**改动量**: `renderMarkdown.ts` +3 行

---

### 方案 C2：S4 降级时前端友好提示

**位置**: `renderMarkdown.ts:47` `renderS4Markdown` 内

即使 `hasRenderableStructuredData` 已改为 false，降级场景下 structured_data 仍有 `caution` 字段。当前 `getDisplayContent` 的 fallback 路径不展示 caution。可选增强：

```typescript
// getDisplayContent 内 S3/S4 分支
if (section.index === 3 || section.index === 4) {
  if (hasRenderableStructuredData(section)) {
    return section.index === 3
      ? renderS3Markdown(section.structured_data)
      : renderS4Markdown(section.structured_data);
  }
  // fallback: 降级场景加 caution 提示
  const sd = section.structured_data || {};
  const caution = sd.caution || '';
  const content = section.content || '';
  if (caution && content.length > 10) {
    return `> ⚠️ ${caution}\n\n---\n\n${content}`;
  }
  if (section.content && section.content.length > 80) return section.content;
  return section.content || '';
}
```

**改动量**: `renderMarkdown.ts` +5 -1 行

---

## 四、问题 D：S5 结论上下文不足

### 根因

`conclusion_node.build_msg` 遍历 S1-S4，每节注入 `sec.content` + `_safe_truncate_json(sec.structured_data, 500)`。S3 content 精简后只有 56 字 + 500 字截断 JSON，S4 降级后只有 203 字 outline + 空壳 JSON。结论 LLM 无法获取 S3 的运动类型详情和 S4 的方案细节。

### 方案 D1：结论 build_msg 展开 S3/S4 structured_data（已有 Phase 5 计划）

**位置**: `nodes/conclusion.py:31`

当前：
```python
for i in range(1, 5):
    sec = s.sections.get(i)
    if sec:
        parts.append(f"## 第{i}节\n{sec.content}\n结构化数据：{_safe_truncate_json(sec.structured_data, 500)}")
```

改为展开 S3/S4 的结构化字段，而非依赖精简后的 content：

```python
for i in range(1, 5):
    sec = s.sections.get(i)
    if not sec:
        continue
    parts.append(f"## 第{i}节\n{sec.content}")
    if i == 3:
        ets = sec.structured_data.get("exercise_types", [])
        if ets:
            et_summary = "、".join(
                f"{e.get('name','')}({e.get('tier','')})"
                for e in ets
                if e.get("name")
            )
            parts.append(f"推荐运动: {et_summary}")
    elif i == 4:
        phases = sec.structured_data.get("phases", [])
        if phases:
            lines = []
            for ph in phases[:3]:
                phase_name = ph.get("phase_name", "")
                ex_names = []
                for wk in ph.get("weeks", [])[:1]:
                    for day in wk.get("days", [])[:2]:
                        for ex in day.get("main_exercises", [])[:3]:
                            n = ex.get("name", "")
                            if n:
                                ex_names.append(n)
                if ex_names:
                    lines.append(f"{phase_name}: {', '.join(ex_names)}")
            if lines:
                parts.append("方案概要: " + "; ".join(lines))
```

**改动量**: `conclusion.py` +20 -3 行

---

---

## 四-附加、问题 E：plan_outline 1200 字限制

### 根因

`Section4OutlineResponse` 的 system prompt 要求"正文 ≤ 1200 字"，加上 phases 结构化数据同时输出，形成容量竞争。LLM 在 1200 字内优先保证正文质量，phases 内的 week→day→exercise 细节被牺牲——与问题 A 形成级联效应。

### 方案 E1：移除 1200 字限制 ✅ 已实施

**位置**：

| 文件 | 改动 |
|------|------|
| `prompts/templates.py:200` | `"正文 ≤ 1200 字"` → 删除 |
| `schemas/knowledge_qa.py:326` | Field description `≤ 1200 字` → 删除 |

**⚠️ 注意**：`_get_prompt_pair` 的优先级为 DB 覆盖 > 文件默认。如果 DB 中 `knowledge_qa_section_4_outline_system` 存有旧版本（含 1200），需同步执行：

```sql
UPDATE prompts
SET content = REPLACE(content,
  '设计运动方案的大纲（正文 ≤ 1200 字）',
  '设计运动方案的大纲')
WHERE prompt_key = 'knowledge_qa_section_4_outline_system';
```

### 预期效果

去除 1200 字限制后，LLM 有更多 token 预算填充 phases→weeks→days→exercises 的完整层级，降低 `_extract_exercise_slots` 返回空的概率，间接减少 S4 降级触发。

---

## 五、实施建议

### 优先级排序

```
第一优先级（P0，阻塞上线）:
├── E1: 移除 1200 字限制             ← 已实施，2 行（需确认 DB 同步）
├── F2: S4 结构/content 拆分         ← 120 行，根因级修复（需验证 qwen 兼容性）
├── A1: plan_outline 后置校验        ← 15 行，零风险（配合 F2 的防御层）
├── C1: S4 hasRenderableStructuredData 深度校验  ← 3 行，零风险
└── A2: S4 重试机制                  ← 40 行，需测试

第二优先级（P1，质量提升）:
├── F1: S3 类型选择/详情拆分         ← 75 行，根因级修复
├── B1: S3 残缺字段修复             ← 35 行（F1 实施后可降级或跳过）
├── B2: _simplify_s3_content 增强    ← 18 行
└── D1: S5 结论上下文展开            ← 20 行

第三优先级（P2，长效加固）:
├── A3: Section4OutlineResponse schema 强化  ← 40 行，需验证 qwen 兼容性
└── C2: 降级场景 caution 提示        ← 5 行
```

### 改动汇总

| 文件 | A1 | A2 | B1 | B2 | C1 | D1 | 合计 |
|------|----|----|----|----|----|----|------|
| `nodes/plan_outline.py` | +15 | — | — | — | — | — | +15 |
| `knowledge_qa_service.py` | — | +40 | — | — | — | — | +40 |
| `nodes/recommend_types.py` | — | — | +35 | +18 | — | — | +53 |
| `utils/renderMarkdown.ts` | — | — | — | — | +3 | — | +3 |
| `nodes/conclusion.py` | — | — | — | — | — | +20 | +20 |
| `prompts/templates.py` | — | — | — | — | — | — | −1 |
| `schemas/knowledge_qa.py` | — | — | — | — | — | — | −1 |
| **合计** | +15 | +40 | +35 | +18 | +3 | +20 | **+131 / −2** |

### 验证策略

| 验证项 | 方式 | 通过标准 |
|--------|------|---------|
| S4 不再降级 | 相同问题重跑 3 次 | 至少 2/3 有完整 phases.weeks |
| S4 降级后前端展示 | 手动触发降级 → 看前端 | 显示 outline Markdown 而非空壳 |
| S3 MovNat 字段完整 | 检查 API 响应 | target_skills/rationable/citation 非空 |
| S3 摘要质量 | 对比前后 content | ≥ 80 字符且含分层信息 |
| S5 结论含运动引用 | 检查结论 content | 出现"跑酷""武术"等具体运动名 |
| 现有测试不回归 | `pytest backend/tests/` | 全绿 |

### 不在此次方案范围

| 问题 | 原因 |
|------|------|
| `child_age_group` 为空 | 属于 Phase 4 prompt 调整，本次聚焦代码修复 |
| `_original_name` 泄露根源 | 需要追踪 `_validate_and_fix_s3_structured_data` 内部赋值链，本次用 pop 防御 |
| 超长运动名称导致 LLM 质量下降 | 运动清单数据清洗问题，非本次范围 |
