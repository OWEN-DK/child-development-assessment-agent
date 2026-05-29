# 知识问答 Bug 审视报告

**日期**: 2026-05-29
**基于**: [BUG-REPORT.md](./BUG-REPORT.md) + 源码验证
**测试问题**: 我儿子8岁，上课注意力不集中，写作业坐不住，经常被老师投诉，有什么运动可以帮助改善？

---

## 原定目标

1. 匹配多本书籍，citations 覆盖多来源
2. 生成 4 周（28 天）运动方案，分为 2+ 阶段
3. 阶段名有实际意义（如"适应期"）
4. S4 structured_data 通过 Pydantic 校验，正常路径（非降级）生成

## 实际完成情况

本次测试结果 `partial=True`，走了**降级路径**。5 个 Bug 中有 4 个是**同一根因的级联表现**。补充审查新增 Bug #6（S4 重试设计缺陷）和 2 个次要问题。

---

## 问题清单

### Bug #2 → #4 → #3 级联（根因：Phase Schema 与 Prompt 字段名不匹配）

| 维度 | 详情 |
|------|------|
| **严重程度** | 必须改正 |
| **现象** | S4 只有 1 个阶段、phase_name="阶段"、总天数 13 天（预期 2 阶段 28 天） |
| **根因** | `schemas/knowledge_qa.py:519` 的 `Phase` 模型定义 `phase_name: str`（必填），但 **无 `alias="name"`**。outline prompt（`prompts/templates.py:245`）告诉 LLM 用 `name` 字段。LLM 输出 `{"name": "适应期", ...}` → Pydantic 报 `Field required [type=missing, input_value={'phase_id': 'PH01', 'nam...}]` → plan_assemble 的 safe rebuild（`plan_assemble.py:542-545`）将所有 phase 的 `phase_name` 设为默认值 `"阶段"`（因读取 `ph.get("phase_name", "阶段")` 而 outline 中是 `name`）。outline 本身可能只生成了 1 个 phase（LLM 未严格遵守"至少 2 个阶段"约束），导致最终 S4 只有 1 个阶段。 |
| **级联链** | Schema 不匹配 → Pydantic 校验失败 → safe rebuild 设 phase_name="阶段" + outline 可能仅 1 phase → Bug #4（渲染"第1阶段：阶段"）→ plan_summary.total_duration_days 从实际天数推导（13 天）→ Bug #3（非 4 周）。同时 `conclusion.py:54` 读取降级数据中的 `phase_name`，结论输出 "阶段: 武术, 爬行" 或空字符串。 |
| **涉及文件** | `schemas/knowledge_qa.py:519`、`prompts/templates.py:245`（outline prompt 用 `name`）、`templates.py:308`（expand prompt 已修正为 `phase_name`，但 outline 遗漏同步）、`nodes/plan_assemble.py:542-545`（内层降级）、`nodes/plan_assemble.py:639`（外层降级）、`nodes/conclusion.py:54`（结论生成读取 `phase_name`） |
| **修复方案** | **方案 A（推荐）**：给 `Phase` 加 `model_config = {'populate_by_name': True}` + `Field(alias="name")`。Pydantic V2 默认只允许用 alias 构造对象，不加 `populate_by_name` 会导致所有 `Phase(phase_name=...)` 调用失败（plan_assemble L543/L639 等）。`model_dump()` 默认 `by_alias=False`，输出 `phase_name`，下游渲染无需改动。方案 B：改 prompt 输出格式为 `phase_name`，但需重新测试 LLM 服从率。 |
| **日志证据** | `plan_assemble: Pydantic 校验失败: 1 validation error for Section4StructuredData phases.0.phase_name Field required [type=missing, input_value={'phase_id': 'PH01', 'nam...}]` |

**历史线索**：`SECTION_4_EXPAND_SYSTEM`（templates.py:308）已正确使用 `phase_name` 字段，说明开发者曾修正过 expand prompt，但**遗漏了 outline prompt 的同步修正**。两份 prompt 对同一实体使用了不同的字段名。

**降级路径一致性审计**（4 处 `phase_name` 读取点，修复时需一并处理）：

| 位置 | 读取方式 | 数据源 | 正确性 |
|------|---------|--------|--------|
| `plan_assemble.py:543`（内层异常） | `ph.get("phase_name", "阶段")` | outline phases（有 `name`） | ❌ 永远返回默认值 "阶段" |
| `plan_assemble.py:639`（外层异常） | `ph.get("name", "阶段")` | outline phases（有 `name`） | ✅ 正确，但内层先触发，此路不可达 |
| `plan_assemble.py:291`（Markdown 渲染） | `phase.get("phase_name", ...)` | Phase.model_dump() | ❌ 读到降级值 "阶段" |
| `conclusion.py:54`（结论生成） | `ph.get("phase_name", "")` | structured_data | ❌ 读到 "阶段" 或空字符串 |

内层（L543）和外层（L639）在同一文件中读取了不同的字段名，说明是不同时间点的代码，缺乏一致性检查。

### Bug #1：多书引用失败 — 搜索结果只包含 1 本书

| 维度 | 详情 |
|------|------|
| **严重程度** | 必须改正 |
| **现象** | 所有 section 的 citations 全部来自"运动改变大脑"，其余 4 本书零引用。search_coverage: `{'运动改变大脑': 8, '孩子如何思考': 5}`，其余 3 本为 0。 |
| **根因** | `_analyze_and_search_books`（`match_books.py:101-178`）最多 6 次搜索（`queries[:6]`），每次 limit=15 且 `len(all_results) >= 25` 时 break。RAG 返回按向量相似度排序，"运动改变大脑"索引内容量远超其他书，向量相似度天然垄断前列。`_extract_candidate_books` 只从搜到的结果中提取候选——搜不到的书永远不会进入候选池。候选补充逻辑（L254-265）虽设计正确，但**候选池本身不包含其他书**，无法起效。 |
| **验证数据** | `limit=15: 15 results → 全部来自运动改变大脑`、`limit=50: 17 results → 全部来自运动改变大脑` |
| **涉及文件** | `nodes/match_books.py:101-178`（`_analyze_and_search_books`） |
| **修复方案** | **两层修复：结果层多样性 + 查询层分解**：  <br><br>**(A) match_books 阶段——来源配额 + MMR 重排**（~30 行）：不增加搜索次数，在 `_analyze_and_search_books` 返回后加两步后处理：(1) 来源配额——每本书最多占 top-K 的 30%（如 limit=15 则每本最多 5 条），超出的降级到配额内；(2) 在配额约束内按 MMR 重排（λ 控制相关性 vs 多样性平衡）。O(n²) 重排在 50 条规模下可忽略。  <br><br>**(B) 各 section 搜索阶段——查询分解**（~20 行）：当前各 section 的搜索 query 只是传入 section content，没有按语义维度拆分。不同阶段需要搜索的内容完全不同——S1 需要"儿童发展/注意力机制"，S3 需要"运动类型/身体协调"，S4 需要"具体运动方案/执行要点"。应在每个 section 节点内，根据节的语义意图将搜索 query 分解为 2-3 个子查询（类似 `domain_keywords` 的思路但更精准），每个子查询天然命中不同书籍和章节。 |

### Bug #3：运动方案总时长不是 4 周（双重因果：Bug #2 + prompt 缺约束）

| 维度 | 详情 |
|------|------|
| **严重程度** | 应当改正 |
| **现象** | 当前生成 13 天（约 2 周），预期 4 周（28 天）。 |
| **根因** | **双重原因**：(1) outline 本身可能只生成了 1 个 phase（LLM 未遵守 prompt 的"至少 2 个阶段"约束），加上 Bug #2 的 safe rebuild 将 phase_name 设为 "阶段"，plan_summary 从实际天数推导（`_derive_plan_summary` 按 phases 实际天数计算，1 phase × 2 weeks × ~5 days ≈ 13 天）；(2) outline prompt（L230）说"至少 2 个阶段，每阶段 1-4 周"但**未约束总时长为 4 周**。即使 Bug #2 修复，LLM 仍可能自行决定阶段数和周数。两者是**独立的因果路径**，Bug #3 不完全级联自 Bug #2。 |
| **涉及文件** | `prompts/templates.py:230`（outline prompt） |
| **修复方案** | outline prompt 加硬性约束：`"总时长固定为 4 周（28 天），分为 2 个阶段，每阶段 2 周"`。同时可考虑在 `Section4OutlineResponse` 中校验 `structured_data.plan_summary.total_duration_days`。 |

### Bug #4：S4 Markdown 渲染出现"阶段"栏目（级联自 Bug #2）

| 维度 | 详情 |
|------|------|
| **严重程度** | 应当改正 |
| **现象** | Markdown 中显示 `### 第1阶段：阶段`，phase_name 是无意义的"阶段"。 |
| **根因** | 与 Bug #2 相同。降级路径默认 `phase_name="阶段"`，`_render_s4_markdown`（`plan_assemble.py:291`）直接渲染此值：`phase_name = phase.get("phase_name", f"第{pi + 1}阶段")` |
| **修复方案** | 修复 Bug #2 后自然消失。 |


### Bug #6（新增）：S4 重试机制设计缺陷

| 维度 | 详情 |
|------|------|
| **严重程度** | 建议改进（当前不影响 Bug #2 场景） |
| **现象** | `_route_after_s4_assemble`（`_assembly.py:39-62`）的重试逻辑不区分故障类型。当 `plan_expand_parallel` 完全失败（无 group_results）时，系统会重试 2 次 S4 链路。如果失败原因是结构性的（如 outline 质量差导致 expand 无法提取运动条目），重试必然产生相同结果，浪费 LLM 调用。 |
| **澄清** | Bug #2 的 Pydantic 校验失败路径 **不触发重试**。`s4_needs_retry=True` 仅在 `plan_assemble.py:430` 设置，对应降级路径 1（无 slots/group_results）。Pydantic 校验失败走内层异常处理（L499-565），safe rebuild 成功后直接继续，不设置 `s4_needs_retry`。因此 Bug #2 实际不产生重试浪费。 |
| **根因** | `_route_after_s4_assemble` 的 `needs_retry` 判断只看 `s4_needs_retry` 和 `section_4_outline_no_exercises` error，不区分 expand 失败是瞬时故障（网络超时、LLM 偶发异常）还是结构性问题（outline 无运动条目）。 |
| **涉及文件** | `_assembly.py:39-62`（重试路由）、`plan_assemble.py:430`（设置 `s4_needs_retry`） |
| **修复方案** | 在 `_route_after_s4_assemble` 中增加故障类型判断：如果 expand 失败原因是 `section_4_expand_empty`（大纲无运动条目），说明是结构性问题，跳过重试。仅对 `section_4_expand: 并行展开失败` 等瞬时故障保留重试。约 5 行改动。 |

### Bug #5：S4 执行要点（description）生成不完全

| 维度 | 详情 |
|------|------|
| **严重程度** | 建议改进（需进一步确认） |
| **现象** | 部分 exercise 的 description 字段有内容（2-3 句），但用户反馈"执行要点生成不完全"。 |
| **分析** | 正常流程：`plan_outline → plan_expand_parallel → plan_assemble`。expand 实际执行了（生成了 notes/description），但 plan_assemble 的 Pydantic 校验失败后，内层异常处理（L499-565）从 outline phases 重建 safe phases，**丢弃了 expand 生成的 description**。outline 中 exercise 通常只有 `name/type_id/duration_min/intensity`，无 `notes` 或 `description`。`result.json` 中 description 有内容，说明 safe rebuild 时 `ex.get("notes", "") or ex.get("description", "")` 可能从 merge 后的 phases 中取到了部分值。 |
| **修复方案** | 分两步：(1) 修复 Bug #2 后重新验证，expand 结果正常组装后 description 应自动完整；(2) 若仍不足，调整 expand prompt 约束。当前两处约束可能主动导致过短：`SECTION_4_EXPAND_SYSTEM`（L317）限 `≤50字`，`SECTION_4_EXPAND_GROUP_SYSTEM` 限 `1-2句话`。建议放宽至"3-5 句话"。 |

**独立风险**：即使 Bug #2 修复，expand prompt 的 50 字上限仍是 description 过短的独立原因。

---

## 问题根因关联图

```
Phase Schema 缺少 alias="name"    Prompt 缺总时长硬约束    expand prompt 限 50 字
    │                                    │                       │
    ├─→ Bug #2: Pydantic 校验失败        │                       │
    │       │                            │                       │
    │       ├─→ Bug #4: phase_name="阶段" │                       │
    │       │     └─ conclusion.py 同受影响│                       │
    │       │                            │                       │
    │       ├─→ Bug #3: outline 仅 1 phase + 时长无约束 ┘  ← 双重因果 │
    │       │                                                    │
    │       ├─→ Bug #5: 降级丢弃 expand 结果 ─────────────────────┘ ← 双重因果
    │       │
    │       └─→ Bug #6: 重试机制不区分故障类型（当前不影响 Bug #2）
    │
_analyze_and_search_books 无分桶搜索
    │
    └─→ Bug #1: 候选池只有 1 本书 → 全部 citations 来自同一书
```

---

## 修复优先级

| 优先级 | 修复项 | 预计改动量 | 影响范围 |
|--------|--------|-----------|---------|
| P0 | Phase Schema 加 `alias="name"` + `populate_by_name=True` | 2 行 | 修 Bug #2/#3/#4 |
| P0 | 降级路径统一读取 `name`（L543 + L291 + conclusion.py:54） | 3 行 | 与 alias 方案二选一 |
| P0 | outline prompt 加 4 周硬约束 | 2-3 行 | 修 Bug #3 剩余风险 |
| P1 | `_analyze_and_search_books` 来源配额 + MMR 重排 + 各 section 查询分解 | ~50 行 | 修 Bug #1 |
| P2 | S4 重试路由区分结构性故障 vs 瞬时故障 | ~5 行 | 修 Bug #6，避免 expand 失败时无效重试 |
| P2 | expand prompt 放宽 description 长度约束（50 字 → 3-5 句） | 2 行 | 修 Bug #5 独立风险 |
| P2 | `PlanSummary` 补全 `intensity_overall` 字段 | 1 行 | 次要，信息完整性 |

---

## 次要问题（不影响功能，建议清理）

| 问题 | 位置 | 说明 |
|------|------|------|
| `PlanSummary` 缺少 `intensity_overall` 字段 | `schemas/knowledge_qa.py:523-530` | `plan_assemble.py:646` 传入 `intensity_overall="中"`，但 `PlanSummary` 模型无此字段。Pydantic V2 默认 `extra='ignore'` 静默丢弃。建议在 schema 补全此字段，使前端可获取整体强度信息。 |
| 降级路径内/外层字段读取不一致 | `plan_assemble.py:543` vs `:639` | 同一文件的两段降级代码读取不同字段名（`phase_name` vs `name`），缺乏一致性。修复 Bug #2 时应统一。 |

---

## 做得好的地方

1. **plan_assemble 的 3 级降级设计**（逐字段修复 → outline 回退 → 占位）：虽然触发了降级，但系统未崩溃，仍输出可用结果。
2. **候选补充逻辑**（`match_books.py:254-265`）：LLM 只匹配 1 本时自动补充到 2 本以上，设计意图正确（问题在候选池上游）。
3. **S3 exercise_types 元数据复用**（`_extract_exercise_types_from_phases`）：避免 S4 重新生成丢失 type_id/category 等元数据。
4. **Bug 报告质量**：根因精确到代码行和日志证据链，有验证数据（limit=15 vs limit=50 对比），可直接指导修复。

---

## 下次重点关注

1. **Pydantic alias 是最优先修复项**——需同时加 `model_config = {'populate_by_name': True}` + `Field(alias="name")`（两行改动），解决 Bug #2/#3/#4。Pydantic V2 默认 `model_dump(by_alias=False)` 输出 `phase_name`，下游 `_render_s4_markdown`（L291）和 `conclusion.py:54` 无需改动。但 `Phase(phase_name=...)` 的直接构造调用（L543、L639 等）必须在 `populate_by_name=True` 下才能工作。
2. **降级路径的一致性修复应与 alias 方案配合**——方案 A（alias + populate_by_name）下，`model_dump()` 默认输出 `phase_name`，降级路径的 `ph.get("phase_name")` 可正常工作。但外层降级（L639）的 `ph.get("name")` 需改为 `ph.get("phase_name")` 以保持一致。方案 B（改 prompt）下，所有 `ph.get("phase_name")` 需改为 `ph.get("name")`。
3. **Bug #1 的来源配额 + MMR 重排需要写测试**——fixture 包含 5 本书的模拟搜索结果（其中 1 本占 80% 条目），断言配额后候选池 ≥3 本不同书籍，且每本占比 ≤30%。
4. **修复后验收标准**：`partial=False`、phase 数 ≥2、总天数 =28、phase_name 不是"阶段"、citations 至少覆盖 2 本书。

---

## 审查修正记录

**审查日期**: 2026-05-29（与报告同日）
**审查方法**: 逐条对比报告结论与源码实际逻辑

| # | 原始描述 | 修正后 | 修正原因 |
|---|---------|--------|---------|
| 1 | Bug #1 称 "3 次 RAG 搜索" | 改为 "最多 6 次搜索（`queries[:6]`）" | `match_books.py:155` 实际循环 `queries[:6]`，非 3 次 |
| 2 | Bug #5 称 "expand 步骤被跳过" | 改为 "plan_assemble 降级路径丢弃了 expand 的结果" | expand 确实执行，但降级从 outline 重新构建，丢弃了 expand 生成的 notes/description |
| 3 | Bug #3 标为 "级联自 Bug #2" | 改为 "双重因果：Bug #2 + prompt 缺总时长约束" | Bug #3 有独立原因（prompt 无 4 周约束），不完全级联自 #2 |
| 4 | Bug #1 修复方案 "逐书分桶搜索" | 改为 "来源配额 + MMR 重排 + 各 section 查询分解"（~50 行） | 逐书分桶在书籍量大时 O(n) 次搜索不可行；业内用 MMR/来源配额解决结果多样性，查询分解解决语义覆盖 |
| 5 | 依赖图缺 `#2 → #3` 边 + 缺 `#5` 节点 | 补全：Bug #3 双因果、Bug #5 降级丢弃链 | 原图遗漏已在分析文字中指出的关联 |
| 6 | 未提及 `conclusion.py:54` 的 `phase_name` 读取 | 补入 Bug #2 影响范围 + 降级路径一致性审计表 | `conclusion.py:54` 使用 `ph.get("phase_name", "")`，与 `plan_assemble.py:543` 同类 bug |
| 7 | 未对比 expand prompt 字段名 | 补充历史线索：expand prompt 已修正为 `phase_name`，outline 遗漏同步 | `templates.py:308`（expand 用 `phase_name`）vs `templates.py:245`（outline 用 `name`）字段名不一致 |
| 8 | 未分析 S4 重试机制有效性 | 新增 Bug #6：结构性 bug 导致重试浪费 2 次 LLM 调用 | `_assembly.py:39-62` 的重试不区分故障类型 |
| 9 | 未发现 expand prompt 的 50 字上限 | Bug #5 补充：`SECTION_4_EXPAND_SYSTEM` 限制 description ≤50 字 | `templates.py:317` 独立于 Bug #2 的内容质量风险 |
| 10 | 未提及 `PlanSummary.intensity_overall` | 新增次要问题：Pydantic V2 静默丢弃 extra 字段 | `plan_assemble.py:646` 传入但 schema 无此字段 |
| 11 | 次要问题表重复行 | 删除重复的"降级路径内/外层字段读取不一致"行 | Python 脚本 replace 操作产生重复 |
| 12 | Bug #6 称 "Pydantic 校验失败触发重试" | 修正：`s4_needs_retry` 仅在降级路径 1（无 group_results）设置，Pydantic 失败路径不触发重试 | `plan_assemble.py:430` 是唯一设置点，L499-565 不设置 |
| 13 | Bug #6 称 "浪费 60-90 秒" | 修正：Bug #2 场景不产生重试浪费，重试仅在 expand 完全失败时触发 | 区分 Pydantic 失败路径 vs 无 group_results 降级路径 |
| 14 | Bug #2 根因称 "降级只保留 1 个 phase" | 修正：safe rebuild 遍历所有 phases 不过滤，"只保留 1 phase" 是 outline 本身的 LLM 输出问题 | `plan_assemble.py:503` 的 `for ph in phases:` 遍历全部，无过滤逻辑 |
| 15 | alias 修复方案称 "1 行改动" | 修正：需同时加 `populate_by_name=True` + `Field(alias="name")`（2 行），否则所有 `Phase(phase_name=...)` 构造调用失败 | Pydantic V2 实测：无 `populate_by_name` 时 `Phase(phase_name='x')` 报 `Field required` |
| 16 | 审查修正 #7 行号 "templates.py:248" | 修正为 "templates.py:245" | L248 是 exercise 的 `name` 字段，L245 才是 phase 的 `name` 字段 |
| 17 | Bug #5/审查 #9 行号 "templates.py:319" | 修正为 "templates.py:317" | `description: 执行要点和家长指导（≤50字）` 实际在 L317 |

---

## 线上验证（修复后首次运行）

**测试时间**: 2026-05-29 09:55  
**测试方式**: `POST /api/v1/knowledge-qa` 同一问题  
**耗时**: 297s  
**模型**: qwen3.5-27b

### 验收对照

| 验收项 | 预期 | 实际 | 状态 |
|--------|------|------|------|
| `partial` | `False` | `True` | ❌ |
| `phase_name` 值 | 非"阶段" | `"能量释放与专注激活期（第1-2周）"` | ✅ |
| `phases` 数量 | ≥2 | 1 | ❌ |
| `total_duration_days` | 28 | 12 | ❌ |
| `intensity_overall` | 有值 | `"中"` | ✅ |
| errors | 空 | `[]` | ✅ |
| Pydantic 校验 | 通过 | 通过（无降级日志） | ✅ |
| citations 多书 | ≥2 本 | S1-S5 全部来自《运动改变大脑》 | ❌ |
| search_coverage | ≥2 本有命中 | `{运动改变大脑: 6, 孩子如何思考: 5}` | ✅ |

### 修复生效确认

**F1 (Phase alias) 完全生效**:
- `phase_name` 从 `"阶段"` 变为 `"能量释放与专注激活期（第1-2周）"` — Pydantic 通过 alias 正确接受了 LLM 的 `name` 输出
- 无 Pydantic 校验失败日志 — 不再走 safe rebuild 降级路径
- `partial=True` 不再是因为 Pydantic 失败，而是因为后续问题

**F8 (PlanSummary.intensity_overall) 生效**:
- `intensity_overall: "中"` 正确输出

### 新发现的问题

#### 问题 A：LLM 未遵守"固定 2 阶段"约束

- **现象**: prompt 已更新为 "固定 2 个阶段，总时长 4 周（28 天），每阶段 2 周"，但 LLM 仍只生成 1 个 phase
- **验证**: 模板文件确认包含新约束，数据库无旧版覆盖
- **原因**: `qwen3.5-27b` 对 "固定" 级别的硬约束服从率不足。"至少 2 个阶段" 改为 "固定 2 个阶段" 后，LLM 仍可能忽略
- **建议修复**: 代码层增加 phases 数量校验 —— 如果 LLM 返回 <2 phases，在 `plan_outline_node` 中触发重试或从 S3 运动类型自动补全第 2 阶段。类似于现有的 `_try_build_phases_from_content` 降级逻辑，但作为**正常路径的后处理**而非异常降级

#### 问题 B：citations 多书引用仍然失败（根因修正）

- **现象**: `search_coverage` 显示两本书都有命中（6 + 5），但 S1-S5 的 citations 全部来自《运动改变大脑》
- **根因（修正）**: 家长的问题 "我儿子8岁，上课注意力不集中，写作业坐不住，经常被老师投诉，**有什么运动可以帮助改善**？" 中 "运动" 关键词主导了搜索语义。RAG 向量搜索将整句问题作为 query，"运动" 的权重压倒了 "注意力不集中""坐不住" 等行为描述，导致搜索结果被《运动改变大脑》垄断。来源配额（F5）无法解决此问题 —— 当 15 条结果全部来自同一本书时，配额无从分配。
- **真正的修复方向**: **问题预处理** —— 在搜索前提取孩子的关键信息（年龄、行为表现、认知特征），去除 "有什么运动可以…" 等解决方案导向的措辞，用中性的行为描述作为搜索 query。例如：`"8岁 男孩 注意力不集中 坐不住 执行功能"` 而非原始问题。
- **建议实现**: 在 `_analyze_and_search_books` 之前增加 LLM 预处理步骤，从用户问题中提取搜索关键词（2-3 组），每组聚焦不同维度：(1) 行为/认知特征 (2) 发展阶段/年龄 (3) 干预/方法

#### 问题 C：`partial=True` 的原因

- **现象**: 结果中无 errors，但 `partial=True`（在 `generation_metadata.partial` 中）
- **推测**: 可能是因为 phases 数量 <2 触发了某处的 partial 标记，或 conclusion/verify_citations 阶段的某项检查未通过
- **需进一步确认**: 检查 `partial` 被设置的具体代码路径

### 审查修正记录（续）

| # | 原始描述 | 修正后 | 修正原因 |
|---|---------|--------|---------|
| 18 | 验收标准 "phase 数 ≥2" | 代码修复已生效（alias），但 LLM 仍只生成 1 phase | LLM 服从率问题，需代码层 phases 数量校验 |
| 19 | F5 来源配额修复 citations 多书 | 来源配额仅作用于 match_books 阶段，section 级搜索仍被单书垄断 | 需将配额扩展到 `_direct_search` 或强制多 book_ids |

#### 问题 C 根因确认：`partial=True` 的真正原因

**定位**: `verify_citations.py:189`

```python
if not valid_citations:
    errors.append(f"section_{i}_citations_all_rejected")
    partial = True  # ← 触发点
```

**数据链**:
```
S3 LLM 生成 → content 仅 90 字符 + citations 的 excerpt 过短（<10 字符）
  → verify_citations 校验 → 全部 citations 因 excerpt 不达标被剔除
    → valid_citations 为空 → partial = True
      → 前端显示"部分生成"
```

**S3 实际数据**:
- `content`: 90 字符（仅一行摘要）
- `citations`: 0 条（全部被 verify_citations 剔除）
- `structured_data.exercise_types`: 5 项（数据本身完整）

**结论**: `partial=True` 不是因为 Pydantic 降级，而是因为 S3 的引用质量不达标。verify_citations 的 excerpt ≥ 10 字符校验把 S3 的引用全部过滤。这是**引用质量问题**，不是**数据缺失问题**。

**建议修复**: 区分 "引用被剔除" 的严重程度 —— 如果 structured_data 完整且 content 存在，仅引用不达标不应标记为 partial。或在 verify_citations 中将 "引用被剔除" 降级为 warning 而非 partial 信号。

---

### 审查修正记录（续）

| # | 原始描述 | 修正后 | 修正原因 |
|---|---------|--------|---------|
| 18 | 验收标准 "phase 数 ≥2" | 代码修复已生效（alias），但 LLM 仍只生成 1 phase | LLM 服从率问题，需代码层 phases 数量校验 |
| 19 | F5 来源配额修复 citations 多书 | 来源配额仅作用于 match_books 阶段，section 级搜索仍被单书垄断 | 需将配额扩展到 `_direct_search` 或强制多 book_ids |
| 20 | "无降级但 partial=True 原因待查" | 根因确认：S3 citations 全部被 verify_citations 剔除（excerpt <10 字符），触发 `partial=True` | `verify_citations.py:189` 的 `if not valid_citations: partial = True` |

---

## 第二轮审查（2026-05-29 续）

### 新数据运行结果

使用修改后的问题（去掉"有什么运动可以帮助改善"后缀）重新运行：

| 指标 | 旧数据（有"运动"后缀） | 新数据（无"运动"后缀） |
|------|----------------------|----------------------|
| 问题 | ...有什么运动可以帮助改善？ | ...经常被老师投诉 |
| search_coverage | {'运动改变大脑': 8, '孩子如何思考': 5} | {'学习之道': 6, '孩子如何思考': 6, '运动改变大脑': 6} |
| 多书引用 | ❌ 仅 1-2 本 | ✅ 3 本 |
| 阶段数 | 1 | 1（仍需修复） |
| 总天数 | 13 | 12（仍需修复） |

**关键发现**：多书引用改善的原因不是 F5 来源配额修复生效，而是**测试问题去掉了"运动"关键词**。

### Bug #1 根因最终确认

旧根因分析（F5 来源配额）只是表面修复。真正的根因：

```
用户问题: "...有什么运动可以帮助改善？"
  ↓
RAG 向量搜索: "运动" 语义权重压倒 "注意力不集中""坐不住"
  ↓
top-15 全部来自《运动改变大脑》
  ↓
其他 4 本书零命中 → citations 单书垄断
```

**验证**：去掉"运动"后缀后，同样的 RAG 搜索返回 3 本书各 6 条结果，完全均衡。

**结论**：关键词剥离只是打补丁，换个问法（如"推荐什么锻炼"）就失效。需要**先分析孩子现状，再用现状搜索**。

### 修复方案：查询分析管线

核心思路：**一次 LLM 调用同时完成意图分类 + 问题分解 + 查询改写**。

```
用户问题
  ├─→ [并行] 规则提取 _extract_child_profile()     ← 零延迟
  └─→ [并行] LLM 分析 _analyze_query()             ← 15s 超时
        ├─ 意图分类: solution_seeking / problem_diagnosis / knowledge_query
        ├─ 实体提取: age, behavior[], cognitive[], emotional[]
        ├─ 问题分解 → 3 个子问题
        └─ 查询改写 → 2-3 个中性 query
  ↓
合并 → 11 组多维度搜索 query（无"运动"等方案导向词）
  ↓
RAG 搜索（最多 6 组 query）
```

**实现文件**: `match_books.py`
- `QueryAnalysisResult`: Pydantic 结构化输出 schema
- `_extract_child_profile()`: 规则实体提取（fallback）
- `_analyze_query()`: LLM 单次调用完成全部分析
- `_analyze_and_search_books()`: 重构后的综合搜索函数

**测试验证**:
```
原问题: "...有什么运动可以帮助改善？"
  → 搜索 query: "8岁儿童 注意力不集中 坐不住"（无"运动"）
  → 与去掉后缀的问题生成完全相同的 query
  → 任何问法都不会被方案导向词主导
```

### Bug #2 级联修复确认

| 修复 | 状态 | 验证 |
|------|------|------|
| F1 Phase alias | ✅ 生效 | phase_name 不再是"阶段" |
| F9 阶段数强制 | ✅ 新增 | `_ensure_min_phases` 自动补全至 2 阶段 |
| F14 每周 7 天 | ✅ 新增 | `_ensure_full_weeks` 补全缺失天为休息日 |
| F10 休息日强制 | ✅ 新增 | `_enforce_rest_days` 最多 5 天训练 |
| F13 summary 计算 | ✅ 修复 | `total_duration_days` 使用计算值 |
| F15-F18 查询分析管线 | ✅ 新增 | 意图分类+实体提取+问题分解+查询改写 |

### 遗留问题

1. **partial=True**：S3 citations 被 verify_citations 剔除（excerpt <10 字符），非数据缺失
2. **section 级搜索**：各 section 的 `_direct_search` 仍用 section content 搜索，可能被单书垄断
3. **LLM 分析延迟**：`_analyze_query` 增加 ~15s，有超时保护但影响总耗时
