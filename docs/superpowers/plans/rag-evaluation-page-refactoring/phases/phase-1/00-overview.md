# Phase 1: 数据模型创建 — 总览

> **需求来源**: spec 文档 `02-data-model.md`
> **需求点数量**: 22 个
> **优先级**: P0（必须在 Phase 2 之前完成）

## 目标

创建全部 18 个数据模型 + 22 个索引 + Enum 映射验证，MySQL 表结构正确。

## 重要说明：与现有模型的关系

项目中已存在同名但不同表结构的旧模型（位于 `backend/src/models/test_case.py`、`config.py`、`prompt.py`）。新模型采用以下策略避免冲突：

- **类名加 `RagEval` 前缀**：如 `RagEvalTestSet`、`RagEvalTestCase`
- **表名加 `rag_eval_` 前缀**：如 `rag_eval_test_sets`、`rag_eval_test_cases`
- **Enum 策略**：`TestDomain` 复用现有 `src.models.test_case.TestDomain`，其余枚举在 `src/models/rag_eval/enums.py` 中统一定义
- **FK 策略**：
  - `users` 表不存在 → 所有 `created_by`/`annotated_by` 等字段改为 `String(36)` 弱引用，无外键约束
  - `documents` 表实际名为 `source_documents` → 引用 `source_documents.id`（使用 String(36) 弱引用，无外键约束）
  - **所有表间关联均采用弱引用（无外键约束）**，通过应用层保证数据一致性

## 需求点清单

### 核心业务模型 (7 个)

| # | 需求点 | 实施文件 | 类名 | 表名 | 主键 | 关键字段 |
|---|--------|---------|------|------|------|---------|
| 1 | TestSet 模型定义 | `01-model-testset.md` | RagEvalTestSet | rag_eval_test_sets | String(36) | name, source_type, source_document_id |
| 2 | TestSetCase 模型定义 | `02-model-testsetcase.md` | RagEvalTestSetCase | rag_eval_test_set_cases | String(36) | test_set_id, case_id, added_at |
| 3 | TestCase 模型定义 | `03-model-testcase.md` | RagEvalTestCase | rag_eval_test_cases | String(36) | query, age_months, domain, expected_document_ids |
| 4 | TestRun 模型定义 | `04-model-testrun.md` | RagEvalTestRun | rag_eval_test_runs | String(36) | name, status, test_set_id, config_version_id |
| 5 | TestRunResult 模型定义 | `05-model-testrunresult.md` | RagEvalTestRunResult | rag_eval_test_run_results | String(36) | run_id, case_id, query, hit_at_1/3/5 |
| 6 | TestCaseDraft 模型定义 | `06-model-testcasedraft.md` | RagEvalTestCaseDraft | rag_eval_test_case_drafts | String(36) | source_document_id, query, age_months, domain, status |
| 7 | IntentAnnotation 模型定义 | `07-model-intentannotation.md` | RagEvalIntentAnnotation | rag_eval_intent_annotations | String(36) | case_id, intent_type, annotated_by |

### 配置与提示词模型 (5 个)

| # | 需求点 | 实施文件 | 类名 | 表名 | 主键 | 关键字段 |
|---|--------|---------|------|------|------|---------|
| 8 | ConfigVersion 模型定义 | `08-model-configversion.md` | RagEvalConfigVersion | rag_eval_config_versions | String(36) | version_number, version_label, config_snapshot |
| 9 | PromptVersion 模型定义 | `09-model-promptversion.md` | RagEvalPromptVersion | rag_eval_prompt_versions | String(36) | prompt_key, version_label, version_number, content |
| 9.5 | PromptMetadata 模型定义 | ⚠️ **缺失** | RagEvalPromptMetadata | rag_eval_prompt_metadata | String(36) | prompt_key, name_zh, purpose, category, variables_schema |
| 10 | ConfigChangeSet 模型定义 | `10-model-configchangeset.md` | RagEvalConfigChangeSet | rag_eval_config_change_sets | String(36) | change_set_label, config_version_id, status |
| 11 | ConfigChangeSetPrompt 模型定义 | `11-model-configchangesetprompt.md` | RagEvalConfigChangeSetPrompt | rag_eval_config_change_set_prompts | String(36) | change_set_id, prompt_version_id |

### 报告与建议模型 (4 个)

| # | 需求点 | 实施文件 | 类名 | 表名 | 主键 | 关键字段 |
|---|--------|---------|------|------|------|---------|
| 12 | TestReport 模型定义 | `12-model-testreport.md` | RagEvalTestReport | rag_eval_test_reports | String(36) | run_id, test_set_id, config_version_id, validation_results (JSON) |
| 13 | TuningSuggestionRecord 模型定义 | `13-model-tuningsuggestionrecord.md` | RagEvalTuningSuggestionRecord | rag_eval_tuning_suggestion_records | String(36) | report_id, param_name, current_value, suggested_value |
| 14 | PromptSuggestionRecord 模型定义 | `14-model-promptsuggestionrecord.md` | RagEvalPromptSuggestionRecord | rag_eval_prompt_suggestion_records | String(36) | report_id, prompt_key, current_version_id, suggested_version_id |
| 15 | IgnoredSuggestion 模型定义 | `15-model-ignoredsuggestion.md` | RagEvalIgnoredSuggestion | rag_eval_ignored_suggestions | String(36) | test_set_id, report_id, param_name, ignore_scope |

### 辅助模型 (2 个)

| # | 需求点 | 实施文件 | 类名 | 表名 | 主键 | 关键字段 |
|---|--------|---------|------|------|------|---------|
| 16 | QueryIntentLog 模型定义 | `16-model-queryintentlog.md` | RagEvalQueryIntentLog | rag_eval_query_intent_logs | String(36) | run_id, case_id, query, predicted_intent, confidence |
| 17 | SynonymQueryPair 模型定义 | `17-model-synonymquerypair.md` | RagEvalSynonymQueryPair | rag_eval_synonym_query_pairs | String(36) | query_a, query_b, domain, source, active |

### 索引与枚举 (4 个)

| # | 需求点 | 实施文件 | 说明 |
|---|--------|---------|------|
| 18 | 22 个索引定义 | `18-indexes-definition.md` | 所有业务查询性能优化必需索引，使用 SQLAlchemy Index() |
| 19 | Enum 映射验证 | `19-enum-mapping-validation.md` | values_callable 显式传递，防止大小写 LookupError |
| 20 | RagEval Enums 定义 | `20-enums-definition.md` | 所有 Enum 统一定义在 enums.py，小写字符串值 |
| 21 | __init__.py 导出模块 | `21-init-module.md` | 模块入口，导出所有 17 个模型 + 10 个 Enum |

## 验收标准

- [ ] 18 个数据模型全部定义（Python + SQLAlchemy 2.0 Mapped/mapped_column 风格）
- [ ] MySQL 表全部创建成功
- [ ] UUID 主键统一（String(36)）
- [ ] 所有表间关联采用弱引用（无外键约束），应用层保证一致性
- [ ] 22 个索引全部创建
- [ ] Enum 映射正确（values_callable）
- [ ] 无循环依赖
- [ ] 类名加 RagEval 前缀，与现有模型不冲突

## ID 策略

所有表主键统一使用 String(36)，存储 UUID 字符串（含连字符，如 `550e8400-e29b-41d4-a716-446655440000`）。原因：
- UUID 标准长度为 36 字符，使用 String(36) 精确匹配，不浪费存储空间
- 分布式友好，无需协调 ID 生成器
- 前端可预生成 ID，支持离线操作
- 避免暴露业务量信息
- 关联表/中间表同样使用 String(36)

## 文件组织

所有新模型统一放在 `backend/src/models/rag_eval/` 目录下：

```
backend/src/models/rag_eval/
├── __init__.py              # 导出所有模型
├── enums.py                 # 所有 Enum 定义
├── test_set.py              # RagEvalTestSet
├── test_set_case.py         # RagEvalTestSetCase
├── test_case.py             # RagEvalTestCase
├── test_run.py              # RagEvalTestRun
├── test_run_result.py       # RagEvalTestRunResult
├── test_case_draft.py       # RagEvalTestCaseDraft
├── intent_annotation.py     # RagEvalIntentAnnotation
├── prompt_metadata.py       # RagEvalPromptMetadata
├── config_version.py        # RagEvalConfigVersion
├── prompt_version.py        # RagEvalPromptVersion
├── config_change_set.py     # RagEvalConfigChangeSet
├── config_change_set_prompt.py  # RagEvalConfigChangeSetPrompt
├── test_report.py           # RagEvalTestReport
├── tuning_suggestion.py     # RagEvalTuningSuggestionRecord
├── prompt_suggestion.py     # RagEvalPromptSuggestionRecord
├── ignored_suggestion.py    # RagEvalIgnoredSuggestion
├── query_intent_log.py      # RagEvalQueryIntentLog
└── synonym_query_pair.py    # RagEvalSynonymQueryPair
```

---

**文档索引**: 
- 上一节: [Phase 0 总览](../phase-0/00-overview.md)
- 下一节: [01-model-testset.md](./01-model-testset.md) — 需求点 1
