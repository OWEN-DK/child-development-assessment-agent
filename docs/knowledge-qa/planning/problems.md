# 知识问答系统 — 问题严格分析与根因

> 日期: 2026-05-28 (v4 终审版) | 来源: CodeGraph AST 全量分析 + 逐行号验证
> 配套方案: [solutions.md](solutions.md)
> 方法论: CodeGraph 全符号索引 → 逐节点追踪 → 行号逐一 grep 验证 → 方案可行性审查

---

## 〇、分析范围与方法

本次分析覆盖以下代码（CodeGraph 索引 736 文件 / 9126 符号 / 16979 边）：

| 范围 | 关键文件 | 验证方式 |
|------|---------|---------|
| 图编排 | `_assembly.py` (12 节点) | `codegraph_node create_knowledge_qa_graph` |
| 通用框架 | `nodes/base.py` | `codegraph_node _run_section_node` |
| 标准节点 | `analyze_child.py`, `identify_problems.py`, `recommend_types.py`, `conclusion.py` | `codegraph_node` 逐个 |
| S4 自定义链 | 4 节点 | `codegraph_node` + `codegraph_callers` |
| Schema | `schemas/knowledge_qa.py` | `codegraph_explore` 5 个 Response |
| 死代码 | `sub_agents.py`, `nodes/plan_expand.py` | `codegraph_callers` = 0 |

**行号验证方式**：每处引用均通过 `grep -n` 在实际文件中确认，非推测。

---

## 一、架构级根因（三个系统性缺陷）

### 根因 A：标准节点 vs 自定义节点的分裂

**验证来源**: `_assembly.py:35-72` + 各节点源码逐行确认

**现象**：S1/S2/S3/S5 通过 `_run_section_node` 统一执行，S4 的 4 个子节点各有独立 LLM 调用逻辑。

```
标准节点（_run_section_node @ base.py:317-401）:
  ✅ 统一搜索 (_direct_search:336) + 模板 (_get_prompt_pair:348) + temperature (_get_temperature:360)
  ✅ knowledge_context 注入 (_build_full_user_message:351-357)
  ✅ exercise_context 注入 (S3 only, :356)
  ✅ 超时 (asyncio.wait_for:368-374) + 降级 (_section_fallback)
  ✅ structured_output + model_dump 提取 (:377)
  ❌ json.loads 不使用 json_repair (:380) — #17

S4 自定义链:
  plan_outline_node @ plan_outline.py:27
    ✅ _get_prompt_pair("section_4_outline") :46
    ✅ _get_temperature("plan_outline") :64
    ✅ knowledge_context 注入 :56
    ✅ exercise_context 注入 :61-62
    ❌ model_name 硬编码 :66
    ⚠️ user_template.format() 手动拼接 :47-57

  plan_expand_parallel_node @ plan_expand_parallel.py:198
    ✅ 共享 _direct_search :220, _get_prompt_pair :146, _get_temperature :147
    ❌ _build_group_prompt 不注入 knowledge_context — #16
    ✅ _build_group_prompt 注入 exercise_context :131-133
    ❌ user message 不走模板系统 — #27

  plan_assemble_node @ plan_assemble.py:291
    无主 LLM 调用（纯计算 + caution 小 LLM）
    ❌ _generate_caution: temperature 硬编码 0.3 :173, model_name 硬编码 :172

  generate_s4_citations_node @ generate_s4_citations.py:55
    ✅ _direct_search :95
    ❌ 完整硬编码 system prompt :103-128 — #31
    ❌ 不使用 knowledge_context — 与根因 C 相关
    ❌ temperature 硬编码 0.1 :166, model_name 硬编码 :168
```

**影响问题**：#1, #2, #3, #17, #18, #24, #27, #28, #30, #31

---

### 根因 B：`structured_data: Dict[str, Any]` 无类型约束

**验证来源**: `schemas/knowledge_qa.py` — grep 确认行号

**现象**：所有 Section Response 的 `structured_data` 字段均为 `Dict[str, Any]`。

```python
Section1Response.structured_data: Dict[str, Any]  # :200
Section2Response.structured_data: Dict[str, Any]  # :218
Section3Response.structured_data: Dict[str, Any]  # :236
Section4Response.structured_data: Dict[str, Any]  # :277 (死代码)
Section5Response.structured_data: Dict[str, Any]  # :293
```

**但注意**：S4 实际使用的结构化数据由 `plan_assemble_node` 构建，经过 `Section4StructuredData` Pydantic 校验（plan_assemble.py:363-425），包含完整的降级逻辑。所以 S4 的 `structured_data` 实际上有隐式的类型约束，只是 S1/S2/S3/S5 没有。

**影响问题**：#1, #2, #4, #23

---

### 根因 C：knowledge_context 预取后在 S4 链部分浪费

**验证来源**: `_build_group_prompt` @ plan_expand_parallel.py:69-135 源码逐行确认

| 节点 | knowledge_context？ | exercise_context？ | 代码位置 |
|------|-------------------|-------------------|---------|
| S1 | ✅ | — | base.py:355 |
| S2 | ✅ | — | base.py:355 |
| S3 | ✅ | ✅ | base.py:355-356 |
| plan_outline | ✅ | ✅ | plan_outline.py:56, :61-62 |
| **plan_expand_parallel** | **❌** | ✅ | plan_expand_parallel.py:131-133 |
| **generate_s4_citations** | **❌** | — | 完全不使用 |
| S5 | ✅ | — | base.py:355 |

**影响问题**：#7, #16

---

## 二、问题总览（v4 终审）

> 严重度标准：P0 = 数据丢失/功能不可用；P1 = 功能受损/可靠性差；P2 = 效率/质量下降；P3 = 代码卫生

| # | 问题 | 严重度 | 代码位置 (已验证) | v3 变化 | 方案覆盖 |
|---|------|--------|------------------|--------|---------|
| 1 | S3 structured_data 为空 | P1 | Section3Response :236 | = | ✓ P2 |
| 2 | S4 structured_data 残缺（级联） | P1 | plan_assemble 降级路径 :302-336 | = | ✓ P2 |
| 3 | plan_outline 间歇失败 | P2 | plan_outline.py:71-77 (timeout 90s) | = | ✓ P4 (retry) |
| 4 | 运动名称违规 | P1 | prompt 约束 + 代码无强制 | = | ✓ P2 |
| 5 | 无年龄适配过滤 | P1 | exercise JSON age 字段未使用 | = | ✓ P3 |
| 6 | match_books 搜索范围过宽 | P2 | match_books.py:209 `state.question` 无过滤 | = | 延后 |
| 7 | 全流程 8 次 _direct_search | P2 | codegraph_callers 验证 7 个调用者 | = | ✓ P3 |
| 16 | plan_expand_parallel 不注入 knowledge_context | P2 | _build_group_prompt :111-133 | = | ✓ P3 |
| 17 | json_repair 仅 S4 引用节点使用 | P2 | base.py:380 vs generate_s4_citations.py:184 | = | ✓ P1 |
| 18 | model_name 5 处硬编码 | P2 | base.py:362, plan_outline:66, plan_expand_parallel:152, plan_assemble:172, generate_s4_citations:168 | = | ✓ P1 |
| 19 | 死代码 3 处 | P3 | sub_agents.py, plan_expand.py, Section4Response | = | ✓ P1 |
| 20 | identify_problems 防御性检查 | P3 | identify_problems.py:19-20 | **降级** | 见注 |
| 21 | 模糊匹配 3 处不一致 | P2 | plan_assemble:109-116, verify_citations:64-74, S3 prompt | = | ✓ P2 |
| 22 | 路径 2 处硬编码 | P3 | verify_citations.py:30-32, knowledge_qa_service.py:41-42 | = | ✓ P1 |
| 23 | severity 无代码校验 | P2 | Section2Response :218 Dict[str,Any] | = | ✓ P2 |
| 24 | _generate_caution temperature 硬编码 | P3 | plan_assemble.py:173 | = | ✓ P1 |
| 25 | conclusion structured_data 截断 | P2 | conclusion.py:21 `[:500]` | = | ✓ P1 |
| 26 | 同名 _direct_search 2 处 | P3 | match_books.py:101 vs base.py:97 | = | ✓ P1 |
| 27 | plan_expand_parallel user message 不走模板 | P2 | _build_group_prompt :111-133 | = | ✓ P4 |
| 28 | 无 LLM 重试机制 | P2 | 全部 LLM 调用点 | = | ✓ P4 |
| 30 | generate_s4_citations temperature 硬编码 | P3 | generate_s4_citations.py:166 | = | ✓ P1 |
| 31 | generate_s4_citations system prompt 硬编码 | P2 | generate_s4_citations.py:103-128 (26行) | = | ✓ P3/P4 |
| 32 | plan_outline 手动 .format() 拼接 | P3 | plan_outline.py:47-57 | = | ✓ P1 |
| 33 | _merge_group_results 静默吞 IndexError | P2 | plan_assemble.py:85-86 | = | ✓ P1 |
| 34 | plan_assemble Pydantic 降级块静默丢弃整周/整阶段 | P2 | plan_assemble.py:398-411 (新增) | **新增** | ✓ P1 |

### v3 → v4 变更说明

| 变更 | 说明 |
|------|------|
| #20 降级 | identify_problems.py:19-20 的 `matched_book_ids` 空检查不是"死逻辑"——虽然 `_route_after_match_books` 已路由，但这是合理的**节点级防御代码**，类似 Guard Clause。删除价值低，保留更安全。建议从 P1 中移除 |
| #34 新增 | plan_assemble.py:398-411 有三层嵌套 `except Exception: continue`，比 #33 更严重——可静默丢失整周或整阶段数据而不报错。`safe_days` 和 `safe_weeks` 的构建过程中，任何 `Day()` 或 `Week()` 构造失败都会跳过，用户看到的是缺失的训练日或训练周 |
| 根因 B 补充 | S4 实际有隐式类型约束——`plan_assemble_node` 使用 `Section4StructuredData` Pydantic 校验。根因 B 主要影响 S1/S2/S3/S5 |
| 行号校正 | conclusion.py 截断在 :21（非 :19）；generate_s4_citations system prompt 在 :103-128（非 :103） |

### #34 详细说明

```python
# plan_assemble.py:394-411 — Pydantic 降级块中的静默丢弃
safe_days = []
for day in wk.get("days", []):
    try:
        safe_exs = []
        for ex in day.get("main_exercises", []):
            try:
                safe_exs.append(Exercise(**ex))
            except Exception:  # ← 单条运动失败 → 用默认值（OK）
                safe_exs.append(Exercise(...))
        safe_days.append(Day(..., main_exercises=safe_exs))
    except Exception:
        continue  # ← 整天被丢弃，不记录！
safe_weeks.append(Week(..., days=safe_days))
# ...
except Exception:
    continue  # ← 整周被丢弃，不记录！
```

**后果**：与 #33 不同（#33 是单条运动参数缺失），#34 是整日/整周消失。当 LLM 生成的运动数据大面积不符合 `Exercise` schema 时，最终 S4 方案可能从 4 周 28 天变成 2 周 10 天，且没有任何 error 日志。

---

## 三、问题间依赖关系图

```
根因 A（标准/自定义节点分裂）
  ├── #16 knowledge_context 不注入 plan_expand_parallel
  ├── #18 model_name 5 处硬编码
  ├── #27 plan_expand_parallel user message 不走模板
  ├── #31 generate_s4_citations system prompt 硬编码
  ├── #30 generate_s4_citations temperature 硬编码
  ├── #32 plan_outline 手动 format
  └── #28 所有 LLM 调用无重试

根因 B（Dict[str, Any] 无类型约束）— 主要影响 S1/S2/S3/S5
  ├── #1 S3 structured_data 为空
  ├── #2 S4 structured_data 残缺（级联效应，但 S4 有隐式约束）
  ├── #23 severity 无校验
  └── #4 运动名称违规（prompt 约束无法在代码层强制）

根因 C（knowledge_context 注入缺口）
  ├── #7 全流程 8 次搜索
  └── #16 S4 链 plan_expand_parallel + generate_s4_citations

独立问题
  ├── #3 plan_outline 间歇失败
  ├── #5 无年龄适配
  ├── #6 match_books 搜索范围
  ├── #17 json_repair 缺口
  ├── #19 死代码 3 处
  ├── #21 模糊匹配 3 处不一致
  ├── #22 路径 2 处硬编码
  ├── #24 _generate_caution temperature 硬编码
  ├── #25 conclusion 截断
  ├── #26 同名函数
  ├── #33 _merge_group_results 静默吞 IndexError
  └── #34 plan_assemble Pydantic 降级块静默丢弃整周/整阶段
```

---

## 四、辩证关系分析

| # | 关系对 | 当前偏向 | 偏向程度 | 修正方向 |
|---|--------|---------|---------|---------|
| A | 结构化输出准确性 ↔ 生成灵活性 | 灵活性（Dict[str,Any]） | 严重 | S2/S3 加子模型；S4 保持现状（已有隐式约束） |
| B | 搜索精确度 ↔ 搜索覆盖度 | 覆盖度 | 中等 | match_books 加 scope 过滤 |
| C | 内容完整性 ↔ 输出简洁 | 完整性 | 严重 | 各节加字数指导 |
| D | 节点统一性 ↔ S4 定制灵活性 | S4 定制 | 严重 | 提取公共 LLM 包装器 |
| E | 搜索去重 ↔ 节点独立性 | 独立性（8 次搜索） | 明显 | 注入 knowledge_context 减少 2 次 |

**核心矛盾**：D 是 A 的放大器。但不应试图把 S4 塞入 `_run_section_node`——S4 的 4 子节点有独特的并行/合并逻辑。应提取公共 LLM 调用包装器。

---

## 五、不在本次方案范围的问题

| 编号 | 问题 | 原因 |
|------|------|------|
| gap P1#2 | 非 Agent 驱动 | 27B 模板驱动当前场景已足够 |
| gap P2#1 | matched_books.author 永远为 null | 存量数据问题 |
| gap P2#3 | prompt 双写（DB vs 文件） | 架构变更 |
| gap P3#2 | citation_id 格式混用 | 低优先级 |

---

## 六、新增需求（2026-05-28）

### 新需求 N1：S3/S4 API JSON 输出精简化

**现状**：
- S3 `content` 由 LLM 生成复杂 Markdown（含详细描述、表格），单节可达 1-3KB
- S4 `content` 由后端 `_render_s4_markdown` 生成完整运动方案 Markdown（phases→weeks→days→exercises 全层级渲染），单节可达 3-8KB
- 两个 `content` 字段在前端仅用于 `ReactMarkdown` 展示，API JSON 传输纯为展示格式，冗余大

**需求**：
- S3/S4 API JSON 输出改为精简版本：`content` 仅含简短摘要（50-100 字），`structured_data` 保持不变作为数据源
- 复杂 Markdown 渲染移至前端：前端从 `structured_data` 生成完整 Markdown 用于展示和下载
- 后端 PDF 生成仍需要完整 Markdown：`_render_s4_markdown` 保留供 `generate_markdown` 调用

**影响范围**：

| 层 | 文件 | 改动 |
|----|------|------|
| 后端 | `nodes/recommend_types.py` | S3 content 精简 + `_simplify_s3_content` |
| 后端 | `nodes/plan_assemble.py` | S4 移除 `_render_s4_markdown` 调用 |
| 后端 | `knowledge_qa_service.py` | `generate_markdown` 从 structured_data 渲染 |
| 前端 | `utils/renderMarkdown.ts`（新增） | S3/S4 Markdown 生成函数 |
| 前端 | `components/SectionRenderer.tsx` | 根据节号选择渲染方式 |
| 前端 | `hooks/useReportDownload.ts` | 下载适配 |

**预期效果**：
- S3 API JSON 响应减少 ≥ 60%
- S4 API JSON 响应减少 ≥ 80%
- 前端展示效果不变

**严重度**：P2（性能优化，非功能缺陷）

**方案覆盖**：✓ Phase 5（solutions.md）
