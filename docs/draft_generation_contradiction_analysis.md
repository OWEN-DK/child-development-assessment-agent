# 草稿生成质量矛盾分析

> 分析日期: 2026-04-29
> 触发: 草稿忠实度仅 28.1%，输出中英混杂，预期关键词与源文档脱节
> 更新: 2026-04-29 — 补充完整数据流追踪、代码引用和影响面评估

---

## 一句话概述

草稿生成质量低下的本质，是系统在 **效率（减少 LLM 调用）** 与 **质量（忠实度约束）** 之间选择了效率端，导致已设计好的质量保障机制（chunk-grounded prompt + PromptManager）被完全绕过。而 age/domain 组合机制的引入进一步放大了质量问题——目标本是测试 RAG 能力，而非按年龄×领域做精细评估。

---

## 问题现象

```
查询: 如果一个5岁半的孩子 watches a tall, narrow glass of water being poured into
      a short, wide bowl — and the water level looks much lower in the bowl —
      they are asked: 'Is there still the same amount of water, or did we lose
      some or gain some?' What would most children this age typically say, and why?
年龄段: 5岁6个月
忠实度: 28.1%
预期关键词: same amount, no, it just looks lower, didn't spill, still all there,
            height changed but width too
```

**可见缺陷:**
- 中英混杂：查询以中文开头，后接大段英文
- 忠实度极低：28.1%，远低于可用阈值
- 预期关键词全部为英文，与中文源文档语境不匹配

### 根因定位：数据流追踪

```
                         ┌─────────────────────┐
                         │   源文档 (中文 PDF)    │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
          ① BookMetadataAnalyzer              ② RAG 向量库
          (book_analyzer.py:30)               加载 chunks
                    │                               │
          LLM 推断 age_ranges                    content[:2500]
          LLM 推断 domains                          │
          content_summary = NULL ◀── 硬伤            │
          → 仅凭标题猜测                             │
                    │                               │
                    ▼                               ▼
          BookMetadata                       chunk.content
          (age_ranges, domains,                       │
           topic_summary)                              │
                    │                               │
                    └───────────┬───────────────────┘
                                ▼
                    ③ DraftGenerator.generate()
                    (generator.py:36-73)
                                │
                    age_ranges × domains 笛卡尔积
                    q_per_combo = max_qa / |combos|
                                │
                    构造硬编码 prompt (generator.py:122-132)
                    ⚠️ 无忠实性约束
                    ⚠️ 无语言约束
                    ⚠️ 无禁止编造规则
                    ⚠️ 无 skip 机制
                                │
                                ▼
                    ④ LLM 返回 JSON
                    → 中英混杂输出
                    → 编造原文未提及内容
                                │
                                ▼
                    ⑤ _build_drafts()
                    (generator.py:162-205)
                    解析 age/domain，构造 DraftCreate
                    → domain 不在白名单则丢弃
                                │
                                ▼
                    ⑥ FaithfulnessChecker
                    (faithfulness_checker.py)
                    embedding(query vs source)
                    → 疑问句 vs 陈述句 → 距离大
                    → 忠实度 28.1%
```

---

## 矛盾清单

| # | 矛盾 | 对立面 A | 对立面 B | 表现 |
|---|------|----------|----------|------|
| 1 | ⭐ 调用模式 | 单 chunk 批量多组合生成 | 单组合逐个生成 + skip 机制 | 当前 1 call/chunk 覆盖全部 age×domain 组合，prompt 无忠实性约束；chunk-grounded prompt 要求 1 call/combo 但有忠实性铁律 |
| 2 | 架构合规 | 硬编码 prompt 快速实现 | PromptManager 动态加载 | `generator.py:122-132` 和 `faithfulness_checker.py` 全部硬编码，绕过了 PromptManager + A/B 测试 + 版本管理 |
| 3 | 忠实度评分 | embedding 余弦速度 | 评分语义正确性 | 当前比较"问题文本 vs 原文片段"，问题是疑问句、原文是陈述句，语义距离天然大，分数必然偏低 |
| 4 | 上下文获取 | content_summary 填充成本 | 元数据推断准确性 | content_summary 永远为 NULL → BookMetadataAnalyzer 只能凭标题猜 age/domain → 后续全部基于错误的组合生成 |
| 5 | 🆕 目标错位 | age×domain 精细评估 | 纯 RAG 能力测试 | 系统目标当前是测试 RAG 检索/生成质量，但管道按 age×domain 组合生成 QA 对，增加复杂度且无助于 RAG 测试 |

### 矛盾 5 详细分析：目标错位

**发现过程：** 当前草稿生成表单 (`DraftGenerationForm.tsx:80-89`) 让用户选择"年龄段范围"和"目标领域"，后端 `generator.py:43-44` 按笛卡尔积拆分调用。但 RAG 测试的核心是验证检索准确性，不是按年龄段做精细评估。

**影响链路：**

| 环节 | 代码位置 | age/domain 做了什么 | 是否为 RAG 测试所需 |
|------|----------|---------------------|---------------------|
| 元数据分析 | `book_analyzer.py:30-70` | LLM 调用推断 age_ranges 和 domains | ❌ 额外消耗一次 LLM 调用 |
| 笛卡尔积构建 | `generator.py:94-119` | 按 age×domain 计算每个组合的问题数 | ❌ 稀释了每个组合的生成量 |
| prompt 构造 | `generator.py:122-132` | 将组合列表硬编码进 prompt | ❌ 占用 token，分散 LLM 注意力 |
| 输出解析 | `generator.py:162-204` | 解析 age/domain，domain 不在白名单则丢弃 | ❌ 无关 QA 被浪费 |
| 数据库存储 | `draft.py:21-32` (ORM) | age/domain 作为 NOT NULL 列持久化 | ❌ 增加了不必要的列 |
| 前端展示 | `DraftTable.tsx:34-35` | 表格显示领域和年龄段列 | ❌ 占用界面空间 |
| 前端筛选 | `DraftPage.tsx:129-131` | 提供领域筛选下拉框 | ❌ 用户不需要按领域过滤草稿 |

**结论：** age/domain 在整个草稿生成管道中从数据推断到 UI 展示全链路存在，但对 RAG 能力测试毫无贡献。将其移除可以：
- 消除矛盾 4（content_summary NULL 导致的错误推断）
- 简化矛盾 1（不再有笛卡尔积调用模式）
- 省去 BookMetadataAnalyzer 的一次额外 LLM 调用

---

## 主要矛盾判定

### ⭐ 主要矛盾：矛盾 5 — 目标错位（新判定）

**判断依据：** 原判定为主要矛盾的"调用模式"（矛盾 1）实际上是目标错位的下游表现。因为目标不是按 age×domain 做精细评估，整个组合机制从一开始就不应该存在。

**原判定：** 矛盾 1（调用模式）
**新判定：** 矛盾 5（目标错位）才是根本矛盾

**理由：**

| 维度 | 矛盾 1（调用模式） | 矛盾 5（目标错位） |
|------|---------------------|---------------------|
| 性质 | 技术实现问题 | 目标定义问题 |
| 覆盖面 | 只影响生成逻辑 | 影响从数据推断到 UI 全链路 |
| 解决后的连锁效应 | 缓解矛盾 2、3、4 | 直接消解矛盾 1 和 4，简化矛盾 2 |

### 解决矛盾 5 后的连锁效应

| 被影响的矛盾 | 效果 | 说明 |
|-------------|------|------|
| 矛盾 1 — 调用模式 | **直接消解** | 不再有 age×domain 笛卡尔积，生成逻辑简化为"每 chunk 直接生成 N 个 QA 对" |
| 矛盾 4 — 元数据推断 | **直接消解** | 不需要推断 age/domain → BookMetadataAnalyzer 简化为只提取 topic_summary |
| 矛盾 2 — 架构合规 | **简化** | prompt 大幅简化后，硬编码问题减轻（但仍应后续接入 PromptManager） |
| 矛盾 3 — 忠实度评分 | **不变** | embedding 对比对象的问题独立存在，需要单独解决 |

### 主要方面：当前「组合精细评估」占支配地位

当前系统由 age×domain 组合逻辑主导。需要将支配地位转移到「纯 RAG 内容质量」。

### 已设计但未启用的质量机制

| 机制 | 设计位置 | 当前状态 |
|------|----------|----------|
| 忠实性铁律 prompt | `prompts_fallback.py:150-194` (key=`test_case_generation_chunk_grounded`) | 已写好，已注册到 DB seed，但 DraftGenerator 未调用 |
| Skip 机制 | 同上 prompt 中 `{"skip": true}` | 未启用 |
| PromptManager 动态加载 | `core/prompt_impl/facade.py` | 完整实现（含缓存 + A/B 测试 + 版本管理），但 DraftGenerator 不使用 |
| content_summary 字段 | `book_analyzer.py:21-22` | 字段存在，但 DocumentManager 从不填充 |

---

## 影响面评估：age/domain 在系统中的完整分布

以下是 age/domain 字段从草稿生成到下游消费的完整影响链路。**仅标注草稿相关路径**，测试用例自身的 age/domain 独立处理。

### 后端

| 层级 | 文件 | 字段 | 用途 | 移除影响 |
|------|------|------|------|----------|
| Schema | `schemas/rag_eval/draft.py:15-17` | `age`, `age_stage_label`, `domain` (DraftCreate) | 草稿创建契约 | 删除三字段 |
| Schema | `schemas/rag_eval/draft.py:49-51` | 同上 (DraftUpdate) | 草稿编辑 | 删除三字段 |
| Schema | `schemas/rag_eval/draft.py:84-85` | `custom_age_ranges`, `custom_domains` (DraftGenerationConfig) | 用户覆盖配置 | 删除两字段 |
| Schema | `schemas/rag_eval/draft.py:91-92` | `age_ranges`, `domains` (BookMetadata) | 元数据输出 | 删除两字段 |
| ORM | `models/rag_eval/draft.py:21-32` | `age`, `age_stage_label`, `domain` (TestCaseDraft) | 数据库映射 | 删除三列 |
| DDL | `full_init_script_mysql57.sql:144-172` | 同上 + `idx_domain` 索引 | 数据库表定义 | 删除三列和索引 |
| Service | `service/rag_eval/draft/generator.py:43-44` | age_ranges/domains 解析 | 笛卡尔积构建 | 整段删除 |
| Service | `service/rag_eval/draft/generator.py:94-119` | combos_desc, combo_lines, q_per_combo | prompt 构造 | 整段重写 |
| Service | `service/rag_eval/draft/generator.py:122-132` | age/domain 硬编码进 prompt | LLM 指令 | prompt 重写 |
| Service | `service/rag_eval/draft/generator.py:162-204` | age/domain 解析 + 白名单过滤 | 输出解析 | 简化 |
| Service | `service/rag_eval/draft/book_analyzer.py:18-21` | _METADATA_PROMPT 要求返回 age_ranges/domains | LLM 调用 | prompt 简化 |
| Service | `service/rag_eval/draft/book_analyzer.py:54-59` | age_ranges/domains 解析 | 结果解析 | 删除 |
| Service | `service/rag_eval/draft/facade.py:61-62` | SSE 发布 age_ranges/domains | 进度推送 | 删除参数 |
| Service | `service/rag_eval/draft/facade.py:138-139` | 保存 age/domain 到 DB | 数据持久化 | 删除字段 |
| Service | `service/rag_eval/draft/facade.py:171-176` | domain 过滤 | 列表查询 | 删除参数 |
| Service | `service/rag_eval/draft/facade.py:262-263` | _tc_dict 复制 age/domain | 草稿→测试用例提升 | 使用默认值 |
| Controller | `controller/rag_eval/draft_controller.py:69` | domain Query 参数 | API 过滤 | 删除参数 |

### 前端

| 层级 | 文件 | 字段/组件 | 用途 | 移除影响 |
|------|------|-----------|------|----------|
| Types | `entities/rag-eval/types.ts:37-39` | `age`, `age_stage_label`, `domain` | 类型定义 | 删除三字段 |
| Types | `entities/rag-eval/types.ts:59-60` | `age_ranges`, `domains` | 生成配置 | 删除两字段 |
| Types | `entities/rag-eval/types.ts:67` | `domain` (DraftFilters) | 筛选类型 | 删除字段 |
| API | `api/rag-eval/drafts.ts:17` | `domain` 参数 | getDrafts 请求 | 删除参数 |
| API | `api/rag-eval/drafts.ts:34` | `age`, `domain` in Pick | updateDraft 类型 | 自动随类型变化 |
| Hooks | `hooks/useDrafts.ts:8` | `domain` (DraftFilters) | 筛选 hook | 删除字段 |
| Form | `components/draft/DraftGenerationForm.tsx:80-89` | age_ranges + domains Select | 表单控件 | 删除两个 Form.Item |
| Form | `components/draft/DraftGenerationForm.tsx:41-42` | age_ranges + domains 初始值 | 默认值 | 删除 |
| Table | `components/draft/DraftTable.tsx:34-35` | 领域列 + 年龄段列 | 表格列 | 删除两列 |
| Page | `pages/DraftPage.tsx:24,29` | domainFilter 状态 | 筛选状态 | 删除 |
| Page | `pages/DraftPage.tsx:83-91` | age_ranges/domains in handleGenerate | 生成请求 | 删除 |
| Page | `pages/DraftPage.tsx:129-131` | 领域筛选 Select | 筛选控件 | 删除 |
| Page | `pages/DraftPage.tsx:167,171` | DomainTag + formatAgeRange | 详情弹窗 | 删除 |

### 下游接口：草稿→测试用例提升

`facade.py:261-267` 的 `_tc_dict()` 是草稿提升为测试用例的桥梁。测试用例表 (test_cases) 仍有 age/domain NOT NULL 列。移除草稿的 age/domain 后，需为 `_tc_dict` 提供默认值：
- `age=0.0`（占位，用户在测试用例中手动修正）
- `age_stage_label=""`（已有默认值）
- `domain=待确认`（需选择一个合理的默认值，候选：`COGNITIVE`（通用性强）、`GROSS_MOTOR`（枚举首项），或改为让测试用例表 age/domain 列也允许 NULL）

---

## 矛盾性质与处理方向

矛盾性质：**非对抗性技术矛盾** — 效率和质量不是根本对立的，可以通过合理设计找到统一点。

### 矛盾 5 解法：移除 age/domain，简化为纯 RAG 测试

**核心洞察：** 当前目标是测试 RAG 能力，age/domain 组合机制是不必要的复杂度。将其移除后，生成逻辑简化为"每 chunk 基于原文内容直接生成 N 个 QA 对"。

### 矛盾 1 解法（修订）：简化 prompt，加入忠实性铁律

移除 age/domain 后，prompt 不再包含组合列表，改为：
- 忠实性铁律（query 必须能从原文直接找到答案）
- 禁止编造（不允许引入原文未提及的概念）
- 语言约束（输出语言与原文保持一致）
- answer_points / expected_keywords 必须来自原文

### 矛盾 4 解法（修订）：BookMetadataAnalyzer 简化

不再需要推断 age/domain → analyzer 简化为仅提取 `topic_summary`（用于辅助生成 prompt 的上下文）。如果认为 topic_summary 价值不大，可完全移除 analyzer 调用。

### 矛盾 3 解法：改对比对象

embedding 对比从 `(query vs source)` 改为 `(answer_points 拼接 vs source)`。answer_points 是答案要点，和原文语义对齐。

### 矛盾 2 解法：PromptManager 接入

所有 prompt 模板通过 `prompt_manager.get_prompt(key, variables=...)` 加载，不再硬编码。

---

## 信息缺口

在实施前需确认：

> 1. **草稿实际输出质量**：本文档的分析基于代码静态分析，28.1% 忠实度仅有一个示例。需确认数据库中实际生成的草稿是否系统性存在"中英混杂""低忠实度"问题，还是个例。
> 2. **测试用例表是否同步移除 age/domain**：如果 test_cases 表也允许移除 age/domain，则 `_tc_dict` 的默认值问题消失。否则需选定合理的占位值。
> 3. **BookMetadataAnalyzer 是否保留**：移除 age/domain 后，analyzer 仅剩 topic_summary 功能。需确认 topic_summary 对生成质量的实际贡献是否值得保留一次额外 LLM 调用。

---

## 监控要点

> ⚠️ **矛盾 2（架构合规）在移除 age/domain 后仍然存在。** prompt 虽然简化了，但仍是硬编码。需后续接入 PromptManager 实现动态加载和版本管理。
>
> ⚠️ **矛盾 3（忠实度评分）独立于 age/domain 移除。** embedding 对比"疑问句 vs 陈述句"的问题不会因为移除组合机制而消失。需单独解决：将对比对象从 `(query vs source)` 改为 `(answer_points vs source)`。
>
> ⚠️ **草稿提升为测试用例时的占位数据。** 如果 test_cases 表保留 age/domain NOT NULL 约束，提升后的测试用例将包含 `age=0` 等虚假数据，需在 UI 层做明确标记，防止被误用。
>
> ⚠️ **BookMetadataAnalyzer 的 LLM 调用成本。** 移除 age/domain 推断后，如果仅用于提取 topic_summary，需评估其 ROI — 每次生成多花一次 LLM 调用换取的 prompt 上下文质量提升是否值得。
