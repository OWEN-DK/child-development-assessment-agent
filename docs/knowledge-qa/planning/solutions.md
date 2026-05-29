# 知识问答系统 — 分阶段优化方案

> 日期: 2026-05-28 (v4 终审版) | 配套问题文档: [problems.md](problems.md)
> 原则: 分阶段 → 每阶段独立可测 → 先低成本高收益 → 逐步解根因

## 实施进度

| 阶段 | 状态 | 测试 |
|------|------|------|
| **Phase 1: 快速修复** | ✅ **已实施** (2026-05-28) | 68 passed, 0 failed |
| **Phase 2: Schema 加固** | ✅ **已实施** (2026-05-28) | 90 passed, 0 failed |
| **Phase 3: 搜索优化** | ✅ **已实施** (2026-05-28) | 90 passed, 0 failed |
| **Phase 4: 框架统一** | ✅ **已实施** (2026-05-28) | 90 passed, 0 failed |
| **Phase 5: 前端渲染化** | ⏳ **待实施** | — |

---

## 核心策略

**v3 方案的问题**：
1. P1-2 `_get_model_name` 错误使用 `_get_prompt_pair`（返回 `{system, user_template}` 字典，语义不对）
2. P1-5 把合理防御代码标为"死逻辑"（identify_problems.py:19-20 是有效的 Guard Clause）
3. P1-7 `_safe_truncate_json` 截断逻辑有 bug（`rfind` 条件可能永远不满足）
4. P1-9 format fallback 方案会丢失其他占位符
5. P2-1 未标注 Schema 变更是前端 breaking change
6. P3-2 完全替代搜索有质量风险
7. P4-1 retry 不区分瞬时错误和持久错误

**v4 修正**：逐项修正以上问题，补充 #34。

---

## Phase 1：快速修复（1天）

> 目标：零风险修复代码质量问题，不改变任何业务逻辑

### P1-1: json_repair 补齐 (#17) ✅ 已实施

**位置**: `nodes/base.py:380`（已验证：`grep -n 'json.loads(data)' base.py` → line 380）

```python
# 当前 base.py:378-382
if isinstance(data, str):
    try:
        data = json.loads(data)
    except Exception:
        data = {"title": section_label, "content": data, "citations": [], "structured_data": {}}

# 改为
if isinstance(data, str):
    try:
        from json_repair import repair_json
        data = json.loads(repair_json(data))
    except Exception:
        data = {"title": section_label, "content": data, "citations": [], "structured_data": {}}
```

**改动量**: base.py +2 行

### P1-2: model_name 配置化 (#18) ✅ 已实施

**位置**: `nodes/base.py` 新增函数（5 处硬编码已验证）

```python
# nodes/base.py 新增（参照 _get_temperature @ :82 的模式）
async def _get_model_name(step_label: str) -> str:
    """获取模型名称。与 _get_temperature 对称，优先从 prompt manager 获取。"""
    try:
        pm = get_prompt_manager()
        name = await pm.get_prompt(prompt_key=f"knowledge_qa_{step_label}_model_name")
        if name and name.strip() and name != "You are a helpful assistant.":
            return name.strip()
    except Exception:
        pass
    return "qwen3.5-27b"
```

**v3 错误**：v3 用 `_get_prompt_pair("config_model_name")` 获取 model_name，但 `_get_prompt_pair` 返回 `{system, user_template}` 字典，且走 DB 默认值比较逻辑。应直接用 `get_prompt_manager().get_prompt()` 保持与 `_get_temperature` 一致的调用模式。

替换 5 处硬编码（已逐一 grep 验证）：

| 文件 | 行号 | 当前代码 |
|------|------|---------|
| `base.py` | :362 | `model_name="qwen3.5-27b"` |
| `plan_outline.py` | :66 | `model_name="qwen3.5-27b"` |
| `plan_expand_parallel.py` | :152 | `model_name="qwen3.5-27b"` |
| `plan_assemble.py` | :172 | `model_name="qwen3.5-27b"` |
| `generate_s4_citations.py` | :168 | `model_name="qwen3.5-27b"` |

**改动量**: base.py +12 行，其余 4 文件各 -1 +2 行

### P1-3: temperature 配置补齐 (#24, #30) ✅ 已实施

```python
# plan_assemble.py:173 — _generate_caution 内
# 当前: temperature=0.3
temperature = await _get_temperature("plan_assemble_caution")

# generate_s4_citations.py:166
# 当前: temperature = 0.1
temperature = await _get_temperature("generate_s4_citations")
```

**改动量**: 2 文件各 +1 -1 行

### P1-4: 死代码删除 (#19) ✅ 已实施

| 目标 | 行数 | 验证 |
|------|------|------|
| `sub_agents.py` | 488 行 | CodeGraph callers=0，无 import 引用 |
| `nodes/plan_expand.py` | ~450 行 | `plan_expand_content_node` 未注册到图 (:35-72) |
| `Section4Response` (schemas) | ~15 行 | 图使用 `Section4OutlineResponse`/`ExerciseGroupResponse`/`Section4StructuredData` |

**改动量**: 删除 3 文件/类，~950 行

### P1-5: 运动清单路径统一 (#22) ✅ 已实施

**已验证路径**: 两个文件通过不同 parent 层级到达同一文件：
- `verify_citations.py:30-32` — `parent.parent.parent.parent / "data" / ...`
- `knowledge_qa_service.py:41-42` — `parent.parent / "data" / ...`
- 两者均解析到 `backend/src/data/运动改变大脑_运动清单.json` ✅

```python
# nodes/base.py 新增（base.py 也需要 4 层 parent，与 verify_citations.py 相同）
def get_exercise_json_path() -> str:
    """运动清单 JSON 标准路径（单点定义）。"""
    return str(
        Path(__file__).resolve().parent.parent.parent.parent
        / "data" / "运动改变大脑_运动清单.json"
    )
```

替换 verify_citations.py:30-32 和 knowledge_qa_service.py:41-42 中的独立路径计算。

**改动量**: base.py +5 行，verify_citations.py -3 +1 行，knowledge_qa_service.py -2 +1 行

### P1-6: 安全截断 (#25) ✅ 已实施

**位置**: `conclusion.py:21`（已验证：`grep -n '[:500]' conclusion.py` → line 21）

```python
# 当前 conclusion.py:21
json.dumps(sec.structured_data, ensure_ascii=False)[:500]

# 替换为
_safe_truncate_json(sec.structured_data, 500)
```

**v3 错误**：v3 的 `_safe_truncate_json` 用 `rfind` + `len(truncated) - 50` 条件，当 JSON 无 `"}"` `"]"` 等后缀时条件不满足，返回 `truncated.rstrip('",') + '"'` 可能在错误位置添加引号。

**v4 修正**：

```python
def _safe_truncate_json(data: dict, max_len: int = 500) -> str:
    """安全截断 JSON，确保不在 UTF-8 多字节字符中间截断且不产生非法 JSON 片段。"""
    s = json.dumps(data, ensure_ascii=False)
    if len(s) <= max_len:
        return s
    # 向前搜索最后一个完整 JSON 值结束位置
    cut = s.rfind('",', 0, max_len)
    if cut > 0:
        return s[:cut + 1]  # 保留引号闭合
    cut = s.rfind('", ', 0, max_len)
    if cut > 0:
        return s[:cut + 1]
    # 退化为直接截断（JSON 可能在字段中间断裂，但这是 conclusion 展示用途，可接受）
    return s[:max_len]
```

**改动量**: conclusion.py +12 -1 行

### P1-7: 函数重命名 (#26) ✅ 已实施

`match_books.py:101` 的本地 `_direct_search` 重命名为 `_analyze_and_search_books`，消除与 `base.py:97` 同名函数的混淆。

**改动量**: match_books.py 4 处重命名

### P1-8: plan_outline format 安全化 (#32) ✅ 已实施

**位置**: `plan_outline.py:47-57`（已验证）

**v3 错误**：v3 建议用 `str.Template` 做降级，但 `str.Template` 使用 `$variable` 语法与 Python `.format()` 的 `{variable}` 不兼容。

**v4 修正**：使用 `string.Formatter` 提取可用变量并安全 format：

```python
import string

def _safe_format(template: str, **kwargs) -> str:
    """安全 format：忽略模板中存在但 kwargs 中不存在的占位符。"""
    formatter = string.Formatter()
    result = []
    for literal_text, field_name, _, _ in formatter.parse(template):
        result.append(literal_text)
        if field_name is not None:
            result.append(str(kwargs.get(field_name, f"{{{field_name}}}")))
    return "".join(result)

# plan_outline.py:47 改为
user_message = _safe_format(
    prompt["user_template"],
    question=state.question,
    section_1_content=s1.content if s1 else "",
    section_2_content=s2.content if s2 else "",
    section_3_content=s3.content if s3 else "",
    section_3_structured=json.dumps(s3.structured_data if s3 else {}, ensure_ascii=False),
    matched_book_ids=json.dumps(state.matched_book_ids),
    knowledge_context=state.knowledge_context or "",
)
```

**改动量**: base.py +10 行（共享工具函数），plan_outline.py +1 -1 行

### P1-9: _merge_group_results 异常统计 (#33, #34) ✅ 已实施

**位置**: `plan_assemble.py:85-86`（#33 单条运动失败）和 `plan_assemble.py:398-411`（#34 整周/整阶段被丢弃）

```python
# plan_assemble.py:_merge_group_results — 在函数开头初始化
failed_slots: List[int] = []

# :85-86 改为
except (IndexError, KeyError) as e:
    logger.warning(f"plan_assemble: slot[{si}] 回填失败: {e}")
    failed_slots.append(si)

# 函数末尾
if failed_slots:
    logger.warning(f"plan_assemble: {len(failed_slots)}/{len(slots)} 个 slot 回填失败")
```

```python
# plan_assemble.py:plan_assemble_node — Pydantic 降级块添加统计
skipped_days = 0
skipped_weeks = 0
# ...
# :398-399
except Exception:
    skipped_days += 1
    continue  # 整天丢弃
# :404-405
except Exception:
    skipped_weeks += 1
    continue  # 整周丢弃

# Step 6 之后
if skipped_days or skipped_weeks:
    logger.warning(f"plan_assemble Pydantic 降级: 跳过 {skipped_weeks} 周, {skipped_days} 天")
    errors_list = state.errors + [f"section_4_assemble: 降级跳过 {skipped_weeks}周{skipped_days}天"]
```

**改动量**: plan_assemble.py +10 行

### P1 改动汇总

| 文件 | 改动量 | 涉及问题 |
|------|--------|---------|
| `nodes/base.py` | +30 行 | #17, #18, #22, #32 |
| `nodes/conclusion.py` | +12 -1 行 | #25 |
| `nodes/plan_assemble.py` | +10 行 | #24, #33, #34 |
| `nodes/generate_s4_citations.py` | +1 -1 行 | #30 |
| `nodes/plan_outline.py` | +1 -1 行 | #32 |
| `nodes/plan_expand_parallel.py` | +1 -1 行 | #18 |
| `nodes/match_books.py` | 4 处重命名 | #26 |
| `schemas/knowledge_qa.py` | -15 行 | #19 |
| `service/knowledge_qa_service.py` | +1 -2 行 | #22 |
| `sub_agents.py` | **删除** | #19 |
| `nodes/plan_expand.py` | **删除** | #19 |
| `nodes/verify_citations.py` | +1 -3 行 | #22 |

**总改动**: ~55 行新增，~25 行修改，~950 行删除。零业务逻辑变更。

**v3 → v4 P1 变更**：
- 移除 #20（identify_problems 防御性检查保留）
- 新增 #34（Pydantic 降级块统计）
- 修正 P1-2、P1-6、P1-7、P1-9 的方案逻辑

---

## Phase 2：Schema 加固 + 类型安全（2天）

> 目标：解决根因 B，让 `with_structured_output` 真正引导 LLM 生成正确结构
> ⚠️ **前端 Breaking Change**：Schema 变更会改变 API 响应格式，前端需同步适配

### P2-1: S2/S3 structured_data 定义子模型

**⚠️ 风险评估**：
1. `with_structured_output` 会把 Pydantic 模型转换为 JSON Schema 发送给 LLM。嵌套 schema 在 qwen3.5-27b 上是否稳定需要验证（qwen 系列对复杂 schema 的遵循度不如 GPT-4）。
2. 前端 TypeScript 类型需同步更新。
3. 建议：先在测试环境用 10 条真实问题验证 S2/S3 的 `structured_data` 填充率，确认无退化后再上线。

**S2 问题识别**:

```python
class ProblemItem(BaseModel):
    description: str = Field(..., description="问题描述")
    severity: Literal["高", "中", "低", "待评估"] = Field(..., description="严重程度")
    category: str = Field(default="", description="问题分类")

class Section2StructuredData(BaseModel):
    problems: List[ProblemItem] = Field(default_factory=list, description="问题列表")

class Section2Response(BaseModel):
    title: str = Field(default="问题识别")
    content: str = Field(..., description="Markdown 正文")
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    structured_data: Section2StructuredData = Field(default_factory=Section2StructuredData)
```

**S3 运动推荐**:

```python
class ExerciseTypeItem(BaseModel):
    name: str = Field(..., description="运动类型名称")
    tier: Literal["核心推荐", "备选推荐", "辅助推荐"] = Field(default="备选推荐")
    rationale: str = Field(default="", description="推荐理由")

class Section3StructuredData(BaseModel):
    exercise_types: List[ExerciseTypeItem] = Field(default_factory=list, min_length=1)
    child_age_group: str = Field(default="", description="年龄段")

class Section3Response(BaseModel):
    title: str = Field(default="运动类型推荐")
    content: str = Field(..., description="Markdown 正文")
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    structured_data: Section3StructuredData = Field(default_factory=Section3StructuredData)
```

### P2-2: IntensityLevel 枚举 + 映射

```python
class IntensityLevel(str, Enum):
    LOW = "low"
    LOW_MODERATE = "low-moderate"
    MODERATE = "moderate"
    MODERATE_HIGH = "moderate-high"
    HIGH = "high"

INTENSITY_MAP: dict[str, IntensityLevel] = {
    "低强度": IntensityLevel.LOW,
    "中低强度": IntensityLevel.LOW_MODERATE,
    "中强度": IntensityLevel.MODERATE,
    "中高强度": IntensityLevel.MODERATE_HIGH,
    "高强度": IntensityLevel.HIGH,
    # ... 完整映射表（从运动清单 JSON 中提取所有变体）
}

def map_intensity(raw: str) -> IntensityLevel | None:
    """中文强度 → 枚举。前缀匹配兜底。"""
    if not raw:
        return None
    result = INTENSITY_MAP.get(raw.strip())
    if result:
        return result
    for cn, enum_val in INTENSITY_MAP.items():
        if cn[:2] in raw or raw[:2] in cn:
            return enum_val
    return None
```

### P2-3: 运动名称模糊匹配统一 (#21)

```python
# nodes/base.py 新增
def fuzzy_match_exercise(name: str, valid_names: List[str], cutoff: float = 0.6) -> str | None:
    """统一运动名称模糊匹配（精确 → 子串 → difflib）"""
    if not name or not valid_names:
        return None
    name_lower = name.strip().lower()
    valid_lower = {n.lower().strip(): n for n in valid_names if n.strip()}

    # 1. 精确
    if name_lower in valid_lower:
        return valid_lower[name_lower]

    # 2. 子串
    for vl, vo in valid_lower.items():
        if vl in name_lower or name_lower in vl:
            return vo

    # 3. difflib
    import difflib
    matches = difflib.get_close_matches(name, valid_names, n=1, cutoff=cutoff)
    return matches[0] if matches else None
```

替换 `plan_assemble.py:_validate_exercise_names`(:91-126) 和 `verify_citations.py:_fuzzy_match_exercise`(:52-75)。

**注意**：`_validate_exercise_names` 使用 cutoff=0.5 且用 `lower()` 字典匹配，`_fuzzy_match_exercise` 使用 cutoff=0.6 且区分大小写。统一为 cutoff=0.6 + case-insensitive。

### P2 改动汇总

| 文件 | 改动量 | 涉及问题 |
|------|--------|---------|
| `schemas/knowledge_qa.py` | +80 行 | #1, #2, #4, #23 |
| `nodes/base.py` | +20 行 | #21 |
| `nodes/plan_assemble.py` | -35 +5 行 | #21 |
| `nodes/verify_citations.py` | -25 +5 行 | #21 |
| 前端 `types/index.ts` | +20 行 | IntensityLevel 同步 |

---

## Phase 3：搜索优化 + knowledge_context 补齐（1天）

> 目标：解决根因 C，减少 _direct_search 调用 2 次

### P3-1: plan_expand_parallel 注入 knowledge_context (#16)

```python
# plan_expand_parallel.py:_build_group_prompt — 在 :123 "## 知识库检索结果" 之后新增
if state.knowledge_context:
    parts.append("")
    parts.append("## 预取知识上下文（高优先级）")
    parts.append(state.knowledge_context[:3000])

# 保留原有 exercise_context 注入 (:131-133)
```

### P3-2: generate_s4_citations 改进 (#7, #31)

**v3 错误**：v3 建议完全替代 `_direct_search`，但 knowledge_context 可能不覆盖运动名称相关的搜索需求。

**v4 修正**：保留搜索作为补充，但优先使用 knowledge_context：

```python
# generate_s4_citations.py — 替换 :94-100 的搜索逻辑

# 优先使用预取 context
search_parts = []
if state.knowledge_context:
    search_parts.append(state.knowledge_context[:5000])

# 补充搜索（仅当 context 不足时）
try:
    search_results = await _direct_search(search_terms, state.matched_book_ids)
    if search_results:
        search_parts.append(_format_search_context(search_results))
    logger.info(f"S4 引用: 预取 context={bool(state.knowledge_context)}, 补充搜索={len(search_results)} 条")
except Exception as e:
    logger.warning(f"S4 引用搜索失败: {e}")

search_context = "\n\n".join(search_parts) if search_parts else "（无可用上下文）"
```

**同时**将 system prompt 改为走模板系统：

```python
# 替换 :103-128 硬编码
prompt = await _get_prompt_pair("section_4_citations")
system_prompt = prompt["system"]
```

DB 中需新增 `knowledge_qa_section_4_citations_system` 和 `knowledge_qa_section_4_citations_user` prompt 条目。

### P3-3: 年龄适配过滤 (#5)

在 `exercise_context` 构建阶段（`knowledge_qa_service.py`）过滤运动清单：

```python
def filter_exercises_by_age(exercises: list, child_age: int | None) -> list:
    """根据年龄过滤运动清单"""
    if not child_age or child_age < 0:
        return exercises
    filtered = []
    for ex in exercises:
        age_range = ex.get("age", "")
        if not age_range:
            filtered.append(ex)
            continue
        nums = re.findall(r'\d+', str(age_range))
        if len(nums) >= 2:
            low, high = int(nums[0]), int(nums[1])
            if low <= child_age <= high:
                filtered.append(ex)
        else:
            filtered.append(ex)
    return filtered
```

**注意**：需先确认运动清单 JSON 中 `age` 字段的实际格式和可用性。

### P3 改动汇总

| 文件 | 改动量 | 涉及问题 |
|------|--------|---------|
| `nodes/plan_expand_parallel.py` | +5 行 | #16 |
| `nodes/generate_s4_citations.py` | +12 -8 行 | #7, #31 |
| `service/knowledge_qa_service.py` | +20 行 | #5 |
| DB prompt 表 | +2 行 | #31 |

---

## Phase 4：框架统一（3天，可选）

> 目标：解决根因 A，让 S4 链共享标准框架能力
> 前置条件：P1 + P2 + P3 完成且稳定运行

### P4-1: 提取 LLM 调用包装器

```python
# nodes/base.py 新增
async def _invoke_llm_structured(
    system_prompt: str,
    user_message: str,
    response_format: Type[BaseModel],
    step_label: str,
    timeout_seconds: int = 60,
    max_retries: int = 1,
) -> BaseModel:
    """统一 LLM 结构化调用：配置化 model_name/temperature + retry + timeout"""
    model_name = await _get_model_name(step_label)
    temperature = await _get_temperature(step_label)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            model = LLMServiceFactoryCompat.create_raw(
                model_name=model_name, temperature=temperature,
            )
            structured_model = model.with_structured_output(response_format)
            return await asyncio.wait_for(
                structured_model.ainvoke([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ]),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            last_error = asyncio.TimeoutError(f"超时 {timeout_seconds}s")
            if attempt < max_retries:
                logger.warning(f"LLM 超时 (attempt {attempt+1}), step={step_label}")
                continue
            raise last_error
        except (ConnectionError, OSError) as e:
            # 仅对瞬时网络错误重试
            last_error = e
            if attempt < max_retries:
                logger.warning(f"LLM 网络错误 (attempt {attempt+1}): {e}")
                await asyncio.sleep(1)
                continue
            raise
        # 其他异常（如 Pydantic 校验失败）不重试
        raise
    raise last_error  # unreachable safety
```

**v3 错误**：v3 对所有 Exception 做 retry，但 Pydantic 校验失败/JSON 解析错误等持久错误不应重试。

**v4 修正**：仅对 `TimeoutError` 和网络错误（`ConnectionError`, `OSError`）重试。其他异常直接抛出。

### P4-2: S4 节点渐进式迁移

不把 S4 塞入 `_run_section_node`，而是替换各节点的 LLM 调用部分：

| 节点 | 当前 | 改为 |
|------|------|------|
| `plan_outline_node` | create_raw + with_structured_output + ainvoke | `_invoke_llm_structured(prompt["system"], full_message, Section4OutlineResponse, "plan_outline")` |
| `_expand_single_group` | create_raw + with_structured_output + ainvoke | `_invoke_llm_structured(prompt["system"], user_message, ExerciseGroupResponse, "plan_expand")` |
| `generate_s4_citations_node` | 硬编码 prompt + create_raw | `_get_prompt_pair("section_4_citations")` + `_invoke_llm_structured(...)` |

### P4-3: plan_expand_parallel user message 模板化 (#27)

```python
# _expand_single_group 中替换 _build_group_prompt 调用
prompt = await _get_prompt_pair("section_4_expand_group")
user_template = prompt.get("user_template", "")
if user_template:
    user_message = _safe_format(
        user_template,
        exercises_json=json.dumps(exercises_json, ensure_ascii=False),
        previous_sections="\n\n".join(prev_parts),
        search_context=search_context,
        knowledge_context=state.knowledge_context or "",
        exercise_context=state.exercise_context or "",
        valid_names="、".join(valid_names) if valid_names else "",
    )
else:
    user_message = _build_group_prompt(group_slots, search_context, state)  # 降级
```

### P4 改动汇总

| 文件 | 改动量 | 涉及问题 |
|------|--------|---------|
| `nodes/base.py` | +35 行 | #28 |
| `nodes/plan_outline.py` | -15 +5 行 | #28, #32 |
| `nodes/plan_expand_parallel.py` | -10 +15 行 | #27, #28 |
| `nodes/generate_s4_citations.py` | -30 +10 行 | #31, #28 |
| `nodes/plan_assemble.py` | -5 +3 行 | #24, #28 |

---


## Phase 5：S3/S4 前端 Markdown 渲染化（2天，新增需求）

> 目标：S3/S4 API JSON 输出简化为精简版本，复杂 Markdown 渲染移至前端
> 注意：S5 结论节点依赖前序节的完整上下文，需同步补全 P5-8

### 背景

当前 S3（运动类型推荐）的 `content` 由 LLM 生成复杂 Markdown，S4（运动方案）的 `content` 由后端 `_render_s4_markdown` 生成复杂 Markdown。API JSON 响应体过大（S4 Markdown 单节可达 2-5KB 纯文本），且 Markdown 格式在前端传输时仅为展示用，不增加结构信息。

**设计原则**：后端 API 输出精简 JSON（摘要 + 结构化数据），前端从 `structured_data` 生成复杂 Markdown。`_render_s4_markdown` 保留供后端 PDF/下载生成使用。

### P5-1: 后端 S3 content 精简

**位置**: `nodes/recommend_types.py` + prompt 模板文件

S3 `content` 不再由 LLM 生成完整 Markdown，改为从 `structured_data` 自动生成简短摘要。

**LLM prompt 调整**（需同步修改 DB 中 `section_3` 的 system prompt）：
- 去掉"生成详细 Markdown 正文"的要求，只要求输出 `structured_data`
- `content` 字段保留简短的引导语（如"根据分析，为您推荐以下运动类型"）

```python
# nodes/recommend_types.py — _run_section_node 返回后，对 section_index==3 做后处理
def _simplify_s3_content(structured_data: dict) -> str:
    types = structured_data.get("exercise_types", [])
    if not types:
        return "暂无推荐的运动类型。"
    cores = [t["name"] for t in types if t.get("tier") == "核心推荐"]
    names = "、".join(cores[:3])
    suffix = "等" if len(cores) > 3 else ""
    return f"根据分析，核心推荐：{names}{suffix}，共 {len(types)} 项运动类型。"
```

> ⚠️ 注意：`Section3Response.content` 是 `Field(..., min_length=1)`（必填），LLM 仍需输出非空 content。

### P5-2: 后端 S4 content 精简

**位置**: `nodes/plan_assemble.py`

移除 `_render_s4_markdown` 调用（Step 6），用简短摘要替代。`PlanSummary` 只有 4 个字段（`total_duration_days`, `total_phases`, `daily_duration_min`, `weekly_frequency`），无 `total_weeks`。

```python
# plan_assemble_node Step 6 改为（s4_data 是 Pydantic Section4StructuredData）:
summary = s4_data.plan_summary
content = (
    f"方案共 {summary.total_phases} 个阶段，共 {summary.total_duration_days} 天，"
    f"每天约 {summary.daily_duration_min} 分钟，每周 {summary.weekly_frequency} 天。"
)
```

`_render_s4_markdown` 函数保留不动，供后端 PDF/下载生成使用（`knowledge_qa_service.py:generate_markdown`）。

### P5-3: 前端 S3 Markdown 渲染

**位置**: 新增 `frontend/src/features/knowledge-qa/utils/renderMarkdown.ts`

```typescript
export function renderS3Markdown(structuredData: Record<string, any>): string {
  const types: Array<{ name: string; tier: string; rationale: string }> =
    structuredData.exercise_types || [];
  const ageGroup: string = structuredData.child_age_group || '';

  if (types.length === 0) return '';

  let md = '## 运动类型推荐\n\n';
  if (ageGroup) md += `**适用年龄段**：${ageGroup}\n\n`;

  md += '| 运动类型 | 推荐层级 | 推荐理由 |\n';
  md += '|---------|---------|--------|\n';
  for (const t of types) {
    md += `| ${t.name} | ${t.tier} | ${t.rationale || '—'} |\n`;
  }
  md += '\n';
  return md;
}
```

### P5-4: 前端 S4 Markdown 渲染

**位置**: `renderMarkdown.ts`（同一文件）

将后端 `_render_s4_markdown`（plan_assemble.py:177-271）的核心逻辑移植为 TypeScript。**关键差异**：补充后端已有的 `intensity_hint` 处理（如"中（控制在5-8次）"），否则视觉效果不一致。

```typescript
export function renderS4Markdown(structuredData: Record<string, any>): string {
  const lines: string[] = ['## 运动方案', ''];

  // 降级路径兼容：structuredData 可能为空（plan_assemble 降级路径 #1/#2）
  const planSummary = structuredData.plan_summary || {};
  const phases = structuredData.phases || [];
  const caution = structuredData.caution || '';

  if (planSummary.total_duration_days) {
    lines.push(
      `> **方案总览**：共 ${planSummary.total_duration_days} 天，` +
      `${planSummary.total_phases} 个阶段，每天约 ${planSummary.daily_duration_min} 分钟，` +
      `每周 ${planSummary.weekly_frequency} 天\n`
    );
  }

  for (let pi = 0; pi < phases.length; pi++) {
    const phase = phases[pi];
    lines.push(`### 第${pi + 1}阶段：${phase.phase_name || '阶段' + (pi + 1)}`);
    if (phase.goal) lines.push(`> ${phase.goal}`);
    lines.push('');

    for (const week of phase.weeks || []) {
      lines.push(`#### 第${week.week_index}周`);
      if (week.focus) lines.push(`**本周重点**：${week.focus}`);
      lines.push('');

      for (const day of week.days || []) {
        const exercises = day.main_exercises || [];
        if (!exercises.length) {
          lines.push(`**${day.day_label || '第' + day.day_index + '天'}**：休息日\n`);
          continue;
        }
        const dayLabel = day.day_label || '第' + day.day_index + '天';
        lines.push(`**${dayLabel}**`);

        // Warmup
        if (day.warmup?.activity) {
          lines.push(`- 🏃 热身：${day.warmup.activity}（${day.warmup.duration_min || 0}分钟）`);
        }
        // Main exercises
        for (const ex of exercises) {
          const params: string[] = [];
          if (ex.duration_min) params.push(`${ex.duration_min}分钟`);
          if (ex.intensity) {
            const hint = ex.intensity_hint ? `（${ex.intensity_hint}）` : '';
            params.push(`${ex.intensity}${hint}`);
          }
          if (ex.sets) params.push(`${ex.sets}组`);
          if (ex.reps) params.push(String(ex.reps));
          const paramStr = params.length ? ` — ${params.join(' · ')}` : '';
          lines.push(`- 🎯 **${ex.name}**${paramStr}`);
          if (ex.notes) lines.push(`  > ${ex.notes}`);
        }
        // Cooldown
        if (day.cooldown?.activity) {
          lines.push(`- 🧘 放松：${day.cooldown.activity}（${day.cooldown.duration_min || 0}分钟）`);
        }
        if (day.total_duration_min) {
          lines.push(`  *当日总计：约${day.total_duration_min}分钟*`);
        }
        lines.push('');
      }
    }
  }

  if (caution) {
    lines.push('### ⚠️ 注意事项');
    lines.push(`> ${caution}\n`);
  }

  return lines.join('\n');
}
```

### P5-5: getDisplayContent 共享函数 + SectionRenderer 适配

**位置**: `renderMarkdown.ts`（新增） + `components/SectionRenderer.tsx`

提取 `getDisplayContent` 共享函数，避免 `SectionRenderer` 和 `buildMarkdown` 各自重复节号判定。前端渲染使用 `useMemo` 避免每次 re-render 重新生成 Markdown。

```typescript
// utils/renderMarkdown.ts
import type { SectionOutput } from '../types';

export function getDisplayContent(section: SectionOutput): string {
  if (section.index === 3) return renderS3Markdown(section.structured_data);
  if (section.index === 4) return renderS4Markdown(section.structured_data);
  return section.content;
}
```

```tsx
// components/SectionRenderer.tsx
import { useMemo } from 'react';
import { getDisplayContent } from '../utils/renderMarkdown';

const displayContent = useMemo(
  () => getDisplayContent(section),
  [section.index, section.content, section.structured_data],
);
// 在 JSX 中:
<ReactMarkdown ...>{displayContent}</ReactMarkdown>
```

### P5-6: buildMarkdown 适配（下载用）

**位置**: `hooks/useReportDownload.ts`

```typescript
import { getDisplayContent } from '../utils/renderMarkdown';

// 在 buildMarkdown 的 for 循环中，将 `sec.content` 替换为:
const displayContent = getDisplayContent(sec);
parts.push(`\n${displayContent}\n`);
```

### P5-7: 后端 PDF 生成适配

**位置**: `knowledge_qa_service.py:generate_markdown`

后端 PDF/下载生成仍需完整 Markdown。S4 复用 `_render_s4_markdown`，S3 从 `structured_data` 生成表格：

```python
from src.core.knowledge_qa.nodes.plan_assemble import _render_s4_markdown

for sec in response.sections:
    if sec.index == 4:
        parts.append(_render_s4_markdown(sec.structured_data))
        parts.append("\n\n")
    elif sec.index == 3:
        parts.append(sec.content)  # 精简摘要
        types = sec.structured_data.get("exercise_types", [])
        if types:
            parts.append("\n| 运动类型 | 推荐层级 | 推荐理由 |\n")
            parts.append("|---------|---------|--------|\n")
            for t in types:
                parts.append(f"| {t['name']} | {t['tier']} | {t.get('rationale', '—')} |\n")
        parts.append("\n")
    else:
        parts.append(f"{sec.content}\n\n")
```

### P5-8: S5 结论节点上下文补全 ⚠️ 新增

**位置**: `nodes/conclusion.py`

S3/S4 content 精简后，S5 `conclusion_node` 的 `build_msg` 获取的上下文大幅减少（S4 从 3-8KB 降为 ~50 字）。需对 S3/S4 额外展开 `structured_data` 关键字段，弥补 content 精简带来的信息损失。

```python
# conclusion.py build_msg 中对 S3/S4 额外注入:
def build_msg(s, prompt):
    parts = []
    for i in range(1, 5):
        sec = s.sections.get(i)
        if not sec:
            continue
        parts.append(f"## 第{i}节\n{sec.content}")
        if i == 3:
            # S3 额外注入运动类型列表（结论可能需要引用具体推荐）
            ets = sec.structured_data.get("exercise_types", [])
            if ets:
                et_summary = ", ".join(
                    f"{e['name']}({e['tier']})" for e in ets[:5]
                )
                parts.append(f"\n推荐运动类型: {et_summary}")
        elif i == 4:
            # S4 额外注入阶段和运动名称摘要（不注入完整方案避免 token 爆炸）
            phases = sec.structured_data.get("phases", [])
            if phases:
                phase_summary = []
                for ph in phases[:3]:
                    ex_names = []
                    for wk in ph.get("weeks", [])[:1]:
                        for day in wk.get("days", [])[:2]:
                            for ex in day.get("main_exercises", [])[:3]:
                                ex_names.append(ex.get("name", ""))
                    phase_summary.append(
                        f"{ph.get('phase_name', '')}: {', '.join(filter(None, ex_names))}"
                    )
                parts.append(f"\n方案概要: {'; '.join(phase_summary)}")
    ...
```

### P5 改动汇总

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `nodes/recommend_types.py` | +12 | S3 content 精简 + `_simplify_s3_content` |
| `nodes/plan_assemble.py` | -3 +5 | S4 移除 `_render_s4_markdown` 调用，用摘要替代 |
| `nodes/conclusion.py` | +20 | S5 上下文补全（从 S3/S4 structured_data 展开） |
| `utils/renderMarkdown.ts` | 新增 +105 | S3/S4 Markdown 渲染 + `getDisplayContent` 共享函数 |
| `components/SectionRenderer.tsx` | +5 +3 | 适配 S3/S4 渲染 + `useMemo` |
| `hooks/useReportDownload.ts` | +2 +2 | 下载适配 |
| `knowledge_qa_service.py` | +15 | 后端 PDF 生成从 structured_data 渲染 |
| prompt 模板（DB） | - | S3 system prompt 去掉详细 Markdown 要求 |

### P5 验证策略

| 验证项 | 方式 | 通过标准 |
|--------|------|---------|
| S3 JSON 精简 | 对比 P5 前后 API 响应大小 | S3 content ≤ 100 字 |
| S4 JSON 精简 | 对比 P5 前后 API 响应大小 | S4 content ≤ 100 字 |
| S4 intensity_hint | 检查包含 hint 的运动项渲染 | 与精简前一致（如"中（控制在5-8次）"） |
| 前端 S3 渲染 | 视觉对比 P5 前后 S3 展示 | 与精简前展示效果一致 |
| 前端 S4 渲染 | 视觉对比 P5 前后 S4 展示 | 与精简前展示效果一致 |
| 降级路径 | 空 structured_data 不报错 | 正常显示占位内容 |
| S5 结论质量 | 对比 P5 前后结论内容 | 结论包含具体运动类型引用 |
| 下载 Markdown | 下载文件对比前后内容 | S3/S4 部分内容一致 |
| PDF 生成 | 生成 PDF 对比前后效果 | S3/S4 部分展示一致 |
| 流式 SSE | SSE 过程中 section_done 事件 | 前端收到精简 JSON 后正确渲染 |

## 总体改动量估算

| 阶段 | 天数 | 改动行数 | 风险 | 覆盖问题 |
|------|------|---------|------|---------|
| P1 快速修复 | 1天 | +55 / -25 / 删 950 | 极低 | #17, #18, #19, #22, #24, #25, #26, #30, #32, #33, #34 |
| P2 Schema 加固 | 2天 | +120 / -60 | **中**（前端 breaking change + qwen schema 适配） | #1, #2, #4, #21, #23 |
| P3 搜索优化 | 1天 | +37 / -8 | 低 | #5, #7, #16, #31 |
| P4 框架统一 | 3天 | +50 / -60 | 中 | #27, #28, #31 (彻底) |
| P5 前端渲染化 | 2天 | +164 / -8 | 低 | 新增需求: S3/S4 JSON 精简 + S5 上下文补全 |
| **合计** | **9天** | **+426 / -161 / 删 950** | | **覆盖 34 个问题中的 31 个 + 新需求** |
### 未覆盖问题



| # | 问题 | 原因 |
|---|------|------|
| #3 | plan_outline 间歇失败 | P4 retry 可缓解但 LLM 生成质量是上游问题 |
| #6 | match_books 搜索范围 | 需业务评估搜索策略 |
| #20 | identify_problems 防御性检查 | 合理 Guard Clause，不修改 |

---

## 实施建议

1. **先做 P1** — 纯代码卫生，零业务风险，可立即部署
2. **P2 需要验证** — 在测试环境用 10+ 条真实问题验证 `with_structured_output` 对新 schema 的遵循度
3. **P3 先做 #16 和 #31** — 直接提升质量；#5 年龄过滤需确认数据格式
4. **P4 看情况** — 如果 P2+P3 已解决主要问题，可延后
5. **P5 按需实施** — 当前端发现 S3/S4 API JSON 过大导致加载慢时启动；需前后端协同，建议一次 PR 完成全链路

### 验证策略

| 阶段 | 验证方式 | 通过标准 |
|------|---------|---------|
| P1 | 现有 e2e 测试通过 + 无新 warning | 所有 test 全绿 |
| P2 | 10 条真实问题测试 S2/S3 structured_data | 填充率 ≥ 90% |
| P3 | 对比 _direct_search 调用次数 | 8→6 |
| P4 | S4 全链路 10 次连续运行 | 无超时 + structured_data 完整率 ≥ 95% |
| P5 | 视觉对比 P5 前后 S3/S4 展示 + API 响应大小对比 | JSON 减少 ≥ 60%，前端展示一致 |
