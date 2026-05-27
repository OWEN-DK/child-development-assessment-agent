# 知识问答流程 — 现存问题清单

> 最后更新: 2026-05-26 | 已删除所有已修复项，仅保留未解决问题

---

## 测试环境

| 项目 | 值 |
|------|-----|
| 知识库书籍 | `test_child_dev_book.pdf`, `运动改变大脑 .epub`, `学习如何学习.epub` |
| 模型 | qwen3.5-27b (所有节点) |
| 图节点数 | 12 (match_books → prefetch_context → S1-S5 + generate_s4_citations + verify_citations + finalize) |
| 全局超时 | 无硬超时，各节点独立 timeout |

---

## 最新 e2e 结果 (2026-05-26)

| # | 问题 | 场景 | 耗时 | 节数 | S4引用 | S4 SD | partial | 备注 |
|---|------|------|------|------|--------|-------|---------|------|
| A | "注意力不集中…推荐运动改善方案" | 指定书名 | 345s | 5/5 | 5 | 1 phase | True | plan_outline 间歇失败(validator) |
| B | "社交能力偏弱，有什么方法可以改善？" | 未指定书名 | 361s | 5/5 | 5 | 空 | True | plan_extract_params 返回{} |
| C | "3岁儿童的大运动发展里程碑是什么？" | 其他知识类 | 134s | 5/5 | 0 | 跳过 | True | S3/S4 正确跳过 |

---

## P0 — 致命

### P0#1: plan_outline 间歇性失败 — `Section4OutlineResponse.phases` 缺 validator

**e2e 堆栈证据 (Case A):**
```
pydantic_core.ValidationError: 1 validation error for Section4OutlineResponse
phases
  Input should be a valid list [type=list_type, input_value='\n[{"phase_id": "PH01", ...}]', input_type=str]
```

**根因：** `Section4OutlineResponse.citations` 有 `@field_validator(mode="before")` 自动将 LLM 输出的 JSON 字符串转为 list，但 `phases` 字段漏加了同样的 validator。LLM 有时将 phases 输出为 JSON 字符串而非原生 list，Pydantic 收到 str → `list_type` 错误。

**影响链：**
```
plan_outline 抛异常
  → plan_expand_content 走 _generate_simplified_plan 降级路径
  → 产出自由格式 Markdown（无 phase/week/day 结构）
  → plan_extract_params 从自由文本中勉强提取（0-1 个 phase）
  → S4 structured_data 残缺
```

**修复：** `schemas/knowledge_qa.py` 中给 `Section4OutlineResponse.phases` 添加 `@field_validator(mode="before")` + `_parse_list_field`。1 行代码。

---

### P0#2: plan_extract_params 持续返回 {} — 逆向提取的结构性矛盾

**e2e 证据 (Case B):**
```
3 validation errors for Section4StructuredData
phases: Field required, plan_summary: Field required, caution: Field required
input_value={}  (LLM 返回空对象)
```

**根因：** 不是超时（已放宽到 60s），是生成流程的设计缺陷：

```
当前流程（有问题）：
  plan_outline → 大纲 → plan_expand_content → Markdown 正文（人类可读）
  → plan_extract_params → 从 Markdown 逆向提取 structured_data

应该是：
  plan_outline → 大纲 → plan_expand → structured_data（Pydantic 强制校验）
  → 从 structured_data 渲染 Markdown
```

`plan_expand_content` 生成的是给人读的 Markdown（"第1周：每天30分钟蹦床跳跃…"），`plan_extract_params` 要从中逆向提取 `phases → weeks → days → exercises` 四层嵌套结构。这是脆弱的逆向工程。

**修复方向：**
1. LLM 先用 `with_structured_output(Section4StructuredData)` 产出完整结构化数据（Pydantic 强制校验，字段不完整则拒绝）
2. 从 structured_data 直接拼接渲染 Markdown 正文（纯字符串操作，无需额外 LLM 调用）
3. 删除 `plan_extract_params_node`

---

## P1 — 重要偏离

### P1#1: S4 运动名称违规 — prompt 约束仍不足

**e2e 证据 (2026-05-26):** Case A S4 违规 7 项，模糊纠正 14 项。违规率 ~35%（修复前 ~100%）。

**已采取措施：** S4 prompt 注入 S3 已校验的合法名称短清单（5-8项）+ prompt 硬约束强化 + 后处理模糊纠正。减少 80% 违规但未根除。

**剩余根因：** LLM 在长篇方案生成中"创造性发散"，即使用了精确名称列表，仍倾向语义相近的替代名。

**方向：** 在 P0#2（翻转生成顺序）中同步解决——structured_data 产出时 Pydantic 可做后处理强校验。

---

### P1#2: 非 Agent 驱动 (FR-03 偏离)

需求 FR-03 要求 ReAct Agent（持有 `search_knowledge_base` 工具、自主决定检索时机/检索词/检索次数、最多 10 轮工具调用）。

当前实现：搜索由 Python 代码直接执行，LLM 做单次 `structured_output` 调用。Agent 自主性完全未实现。

**方向：** 27B 模型工具调用能力足够，可择机改为 `create_react_agent` + `search_knowledge_base` tool。需评估耗时增加。

---

### P1#3: 无年龄适配过滤

`运动改变大脑_运动清单.json` 93 项运动中无任何年龄元数据。清单包含明确不适合儿童的项目：#9 马拉松、#10 超级马拉松、#19 后空翻、#35 拳击、#36 格斗、#92 冷水浴。这些在当前架构下都可能被 LLM 选中推荐给孩子。

**方向：**
- 运动清单 JSON 增加 `min_age` / `suitable_for_children` 字段
- `_build_exercise_markdown()` 根据年龄信息过滤清单
- 或后处理：从推荐结果中剔除年龄不适配的运动

---

## P2 — 中度

### P2#1: matched_books.author 永远为 null

FR-11.4 要求 `SourceDocument.author` 支撑 `matched_books` 输出。DDL 已变更，但存量数据 `author` 列均为 NULL。

**方向：** 存量数据补填 author 字段。

---

### P2#2: 书籍误匹配 — 非运动问题仍匹配《运动改变大脑》

match_books 对非运动问题（Case C）仍返回运动类书籍。DB prompt 已同步领域分类逻辑，但效果待验证。

**方向：** 验证 DB prompt 版本是否生效，或在代码层增加硬过滤。

---

### P2#3: prompt 双写问题 (DB vs 文件)

两个 prompt 真相源：`templates.py`（文件默认）和 MySQL `prompts` 表（运行版本）。`_get_prompt_pair()` 当前为"文件优先，DB 覆盖"策略。但之前是"DB 优先"，修改后开发者不清楚优先级，改动可能不生效。

**方向：** 统一单一真相源 + seed/migration 机制。

---

## P3 — 轻微

### P3#1: S3 structured_data 偶发截断

LLM JSON 输出在 mid-token 被截断，string 字段内容不完整（如 `"适合低龄儿童，"`）。Pydantic 未报错（字段类型为 string）。

**方向：** `json-repair` 兜底或 output token 安全边界预留。

---

### P3#2: 需求文档偏差项

| 项 | 需求 | 实际 |
|---|------|------|
| `citation_id` 格式 | C001 (3位) | C1/C001 混用 (verify_citations auto-fix) |
| `excerpt` max_length | 500 字 | 300 (Citation schema 定义) |
| 图节点数 | 9 | 12 (多了 prefetch_context + plan_extract_params + generate_s4_citations) |

---

## 实施优先级

```
紧急 (下一轮):
  Step 1: P0#1 — Section4OutlineResponse.phases 加 _parse_list_field validator (1行代码)
  Step 2: P0#2 — 翻转 S4 生成顺序 (先 structured_data 再 Markdown, 删除 plan_extract_params)

重要:
  Step 3: P1#1 — S4 运动名称残余违规 (随 P0#2 修复)
  Step 4: P1#3 — 年龄适配过滤 (清单加 min_age 字段)
  Step 5: P0 耗时优化 — S1-S3 并行化
  Step 6: P1#2 — Agent 自主性 (ReAct Agent 重构)

打磨:
  Step 7: P2#1 — author 数据填充
  Step 8: P2#3 — prompt 双写问题
  Step 9: P3#1 — S3 JSON 截断兜底
```
