# 18 - 索引定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 18 - 索引定义

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `test_set_case.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

## 总览
本文件定义 spec 要求的全部 22 个索引，通过 SQLAlchemy `Index()` 在对应模型的 `__table_args__` 中定义。

## 索引清单（spec 要求 22 个）

| 序号 | 表名 | 索引名称 | 索引字段 | 类型 | 用途 |
|------|------|----------|----------|------|------|
| 1 | rag_eval_test_set_cases | idx_rag_eval_case_id | case_id | 普通索引 | 反向查询"用例被哪些测试集复用" |
| 2 | rag_eval_test_cases | idx_rag_eval_domain_age | domain, age_months | 复合索引 | 按领域/年龄筛选用例 |
| 3 | rag_eval_config_versions | idx_rag_eval_config_created_at | created_at | 普通索引 | 趋势图按时间查询配置版本 |
| 4 | rag_eval_prompt_versions | idx_rag_eval_key_created | prompt_key, created_at | 复合索引 | 版本列表查询 |
| 5 | rag_eval_config_change_sets | idx_rag_eval_change_set_status | status | 普通索引 | 查询活跃变更集 |
| 6 | rag_eval_test_reports | idx_rag_eval_report_testset_created | test_set_id, created_at | 复合索引 | 报告列表查询 |
| 7 | rag_eval_test_runs | idx_rag_eval_run_testset_status_created | test_set_id, status, created_at | 复合索引 | 运行历史筛选 |
| 8 | rag_eval_test_case_drafts | idx_rag_eval_draft_doc_status | source_document_id, status | 复合索引 | 草稿审核列表 |
| 9 | rag_eval_tuning_suggestion_records | idx_rag_eval_tuning_report_applied | report_id, applied | 复合索引 | 推荐面板查询 |
| 10 | rag_eval_prompt_suggestion_records | idx_rag_eval_prompt_report_applied | report_id, applied | 复合索引 | 推荐面板查询 |
| 11 | rag_eval_intent_annotations | uk_rag_eval_intent_case | case_id | 唯一索引 | 每个用例最多一条标注 |
| 12 | rag_eval_ignored_suggestions | idx_rag_eval_ignored_testset_scope_restored | test_set_id, ignore_scope, restored | 复合索引 | 推荐面板查询活跃忽略记录 |
| 13 | rag_eval_test_reports | idx_rag_eval_report_run_id | run_id | 普通索引 | 通过run_id反向查询报告 |
| 14 | rag_eval_test_reports | idx_rag_eval_report_config_version | config_version_id | 普通索引 | 查询某配置版本的所有报告 |
| 15 | rag_eval_test_runs | idx_rag_eval_run_config_version | config_version_id | 普通索引 | 查询某配置版本的所有运行 |
| 16 | rag_eval_config_change_sets | idx_rag_eval_change_set_config_version | config_version_id | 普通索引 | 查询某配置版本的变更集 |
| 17 | rag_eval_config_change_set_prompts | idx_rag_eval_csp_prompt_version | prompt_version_id | 普通索引 | 反向查询"哪些变更集包含某提示词版本" |
| 18 | rag_eval_ignored_suggestions | idx_rag_eval_ignored_report | report_id | 普通索引 | report删除时级联清理 |
| 19 | rag_eval_query_intent_logs | idx_rag_eval_intent_log_run | run_id | 普通索引 | Layer 5b按运行查询 |
| 20 | rag_eval_query_intent_logs | idx_rag_eval_intent_log_case | case_id | 普通索引 | 按用例查询意图标注 |
| 21 | rag_eval_test_run_results | idx_rag_eval_result_run_id | run_id | 普通索引 | 按运行查询所有用例结果 |
| 22 | rag_eval_test_run_results | idx_rag_eval_result_run_status | run_id, status | 复合索引 | 按运行+状态筛选Bad Case |
| 23 | rag_eval_synonym_query_pairs | idx_rag_eval_synonym_domain_active | domain, active | 复合索引 | 按领域查询启用的同义对 |

## SQLAlchemy 实现示例

```python
# test_set_case.py
__table_args__ = (
    Index("idx_rag_eval_case_id", "case_id"),
    {"comment": "测试集-测试用例关联表"},
)

# test_case.py
__table_args__ = (
    Index("idx_rag_eval_domain_age", "domain", "age_months"),
    {"comment": "RAG评估测试用例表"},
)

# config_version.py
__table_args__ = (
    Index("idx_rag_eval_config_created_at", "created_at"),
    {"comment": "RAG配置版本表"},
)

# prompt_version.py
__table_args__ = (
    Index("idx_rag_eval_key_created", "prompt_key", "created_at"),
    {"comment": "提示词版本表"},
)

# config_change_set.py
__table_args__ = (
    Index("idx_rag_eval_change_set_status", "status"),
    Index("idx_rag_eval_change_set_config_version", "config_version_id"),
    {"comment": "配置变更集表"},
)

# test_report.py
__table_args__ = (
    Index("idx_rag_eval_report_testset_created", "test_set_id", "created_at"),
    Index("idx_rag_eval_report_run_id", "run_id"),
    Index("idx_rag_eval_report_config_version", "config_version_id"),
    {"comment": "测试评估报告表"},
)

# test_run.py
__table_args__ = (
    Index("idx_rag_eval_run_testset_status_created", "test_set_id", "status", "created_at"),
    Index("idx_rag_eval_run_config_version", "config_version_id"),
    {"comment": "RAG评估测试运行记录表"},
)

# test_case_draft.py
__table_args__ = (
    Index("idx_rag_eval_draft_doc_status", "source_document_id", "status"),
    {"comment": "测试用例草稿表"},
)

# tuning_suggestion.py
__table_args__ = (
    Index("idx_rag_eval_tuning_report_applied", "report_id", "applied"),
    {"comment": "参数调优建议记录表"},
)

# prompt_suggestion.py
__table_args__ = (
    Index("idx_rag_eval_prompt_report_applied", "report_id", "applied"),
    {"comment": "提示词调优建议记录表"},
)

# intent_annotation.py
__table_args__ = (
    Index("uk_rag_eval_intent_case", "case_id", unique=True),
    {"comment": "测试用例意图标注表"},
)

# ignored_suggestion.py
__table_args__ = (
    Index("idx_rag_eval_ignored_testset_scope_restored", "test_set_id", "ignore_scope", "restored"),
    Index("idx_rag_eval_ignored_report", "report_id"),
    {"comment": "忽略的调优建议记录表"},
)

# query_intent_log.py
__table_args__ = (
    Index("idx_rag_eval_intent_log_run", "run_id"),
    Index("idx_rag_eval_intent_log_case", "case_id"),
    {"comment": "查询意图自动分类日志表"},
)

# test_run_result.py
__table_args__ = (
    Index("idx_rag_eval_result_run_id", "run_id"),
    Index("idx_rag_eval_result_run_status", "run_id", "status"),
    {"comment": "测试运行结果详情表"},
)

# synonym_query_pair.py
__table_args__ = (
    Index("idx_rag_eval_synonym_domain_active", "domain", "active"),
    {"comment": "同义查询对表"},
)

# config_change_set_prompt.py
__table_args__ = (
    Index("idx_rag_eval_csp_prompt_version", "prompt_version_id"),
    {"comment": "变更集-提示词版本关联表"},
)
```
