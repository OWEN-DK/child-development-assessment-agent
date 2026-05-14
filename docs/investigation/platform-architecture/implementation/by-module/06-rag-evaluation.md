# 06 — RAG 评估系统 · 实现规格

> **定位**：测试搜索管道效果的完整评估体系。从 backend/ 继承核心评估逻辑，适配 PipelineCompiler + 多向量后端 + 多租户权限，新增跨域评估 + 管道版本对比。
> **关联需求**：[06-rag-evaluation.md](../requirements/06-rag-evaluation.md)

---

## 1. API 契约

所有端点基路径：`/api/v1/rag/eval`

统一响应格式：
```json
// 成功
{"code": 0, "message": "success", "data": {...}}
// 错误
{"code": 400, "message": "...", "error_code": "INVALID_PARAMS", "details": {...}}
```

### 1.1 测试用例与测试集

#### `GET /test-cases` — 列出用例

查询参数：
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | ≥1 |
| `page_size` | int | 20 | 1-100 |
| `source` | string | — | manual/draft/import |
| `difficulty` | string | — | easy/medium/hard |
| `domain` | string | — | 按 relevant_domains 过滤 |

响应：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [{
      "id": "tc_001",
      "query": "高血压合并糖尿病如何用药",
      "description": "跨学科综合用药咨询",
      "expected_knowledge_ids": ["高血压指南.pdf:chunk_12", "糖尿病用药共识.pdf:chunk_5"],
      "expected_keywords": ["ACEI", "二甲双胍", "联合用药"],
      "answer_points_summary": "建议使用ACEI类药物联合二甲双胍...",
      "difficulty_level": "hard",
      "professional_terms": ["ACEI", "ARB", "胰岛素抵抗"],
      "relevance_scores": {"高血压指南.pdf": 0.9, "糖尿病用药共识.pdf": 0.85},
      "relevant_domains": ["心血管内科", "内分泌科", "药学"],
      "expected_conflicts": [{
        "statement_a": "优先使用ACEI类药物",
        "source_a": "高血压指南.pdf",
        "statement_b": "肾功能不全禁用ACEI",
        "source_b": "糖尿病用药共识.pdf"
      }],
      "source": "manual",
      "source_draft_id": null,
      "source_document_id": null,
      "version": 1,
      "tenant_id": "tenant_001",
      "created_at": "2026-05-14T10:00:00Z",
      "updated_at": "2026-05-14T10:00:00Z"
    }],
    "total": 150,
    "page": 1,
    "page_size": 20
  }
}
```

#### `POST /test-cases` — 创建用例

请求：
```json
{
  "query": "儿童发热如何用药",
  "description": "儿科常见病症用药咨询",
  "expected_knowledge_ids": ["儿科用药指南.pdf:chunk_3"],
  "expected_keywords": ["布洛芬", "对乙酰氨基酚", "退热"],
  "answer_points_summary": "体温<38.5°C首选物理降温，≥38.5°C可选布洛芬或对乙酰氨基酚",
  "difficulty_level": "easy",
  "relevant_domains": ["儿科", "药学"],
  "expected_conflicts": []
}
```

响应：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "tc_002",
    "query": "儿童发热如何用药",
    "...": "...",
    "source": "manual",
    "version": 1,
    "created_at": "2026-05-14T10:05:00Z"
  }
}
```

#### `GET /test-cases/{id}` — 获取用例
#### `PUT /test-cases/{id}` — 更新用例

请求：
```json
{
  "query": "儿童发热如何用药（修订）",
  "difficulty_level": "medium",
  "relevant_domains": ["儿科", "药学", "急诊科"],
  "expected_conflicts": []
}
```

#### `DELETE /test-cases/{id}` — 删除用例
#### `DELETE /test-cases/batch` — 批量删除

请求：
```json
{"case_ids": ["tc_001", "tc_002", "tc_003"]}
```

#### `POST /test-cases/import` — 批量导入

请求：
```json
{
  "cases": [
    {
      "query": "...",
      "description": "...",
      "expected_knowledge_ids": ["doc.pdf:chunk_1"],
      "expected_keywords": ["关键词1"],
      "answer_points_summary": "...",
      "difficulty_level": "medium",
      "relevant_domains": ["域A", "域B"],
      "expected_conflicts": []
    }
  ]
}
```

响应：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [{ "id": "tc_050", "query": "...", "...": "..." }],
    "total": 3,
    "page": 1,
    "page_size": 20,
    "stats": { "created": 2, "duplicated": 1, "skipped": 0 }
  }
}
```

#### `GET /test-sets` — 列出测试集
#### `POST /test-sets` — 创建测试集

请求：
```json
{
  "name": "医学综合QA集",
  "description": "跨域医学综合测试数据",
  "case_ids": ["tc_001", "tc_002", "tc_003"],
  "visibility": "role_scoped"
}
```

响应：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "ts_001",
    "name": "医学综合QA集",
    "description": "跨域医学综合测试数据",
    "source_type": "manual",
    "case_count": 3,
    "case_ids": ["tc_001", "tc_002", "tc_003"],
    "visibility": "role_scoped",
    "owner_id": "user_001",
    "tenant_id": "tenant_001",
    "created_at": "2026-05-14T10:10:00Z",
    "updated_at": "2026-05-14T10:10:00Z"
  }
}
```

#### `GET/PUT/DELETE /test-sets/{id}` — 获取/更新/删除测试集
#### `POST /test-sets/{id}/cases` — 添加用例到测试集

请求：
```json
{"case_ids": ["tc_010", "tc_011"]}
```

#### `DELETE /test-sets/{id}/cases` — 从测试集移除用例

请求：
```json
{"case_ids": ["tc_010"]}
```

#### `GET /test-sets/{id}/export` — 导出测试集

响应：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "name": "医学综合QA集",
    "description": "跨域医学综合测试数据",
    "source_type": "manual",
    "exported_at": "2026-05-14T10:15:00Z",
    "cases": [{ "id": "tc_001", "query": "...", "...": "..." }]
  }
}
```

### 1.2 草稿

#### `GET /drafts` — 草稿列表

查询参数：`page`, `page_size`, `status` (draft/reviewed/rejected/imported), `source_document_id`

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "items": [{
      "id": "draft_001",
      "query": "高血压用药注意事项有哪些",
      "description": "高血压用药指导",
      "expected_knowledge_ids": ["高血压指南.pdf:chunk_12"],
      "expected_keywords": ["ACEI", "ARB", "CCB", "利尿剂"],
      "answer_points": ["首选ACEI或ARB", "可联合CCB", "注意肾功能监测"],
      "professional_terms": ["ACEI", "ARB", "CCB"],
      "difficulty_level": "medium",
      "source_document_id": "doc_001",
      "status": "draft",
      "version": 1,
      "faithfulness_score": 0.92,
      "batch_id": "batch_001",
      "draft_index": 1,
      "source_chunk_id": "chunk_012",
      "source_page": 42,
      "source_content_snippet": "高血压药物治疗首选ACEI或ARB...",
      "created_at": "2026-05-14T09:00:00Z",
      "updated_at": "2026-05-14T09:00:00Z"
    }],
    "total": 50,
    "page": 1,
    "page_size": 20
  }
}
```

#### `POST /drafts` — 创建草稿

请求：
```json
{
  "query": "...",
  "description": "...",
  "expected_knowledge_ids": ["doc.pdf:chunk_1"],
  "expected_keywords": ["k1"],
  "answer_points": ["point 1", "point 2"],
  "professional_terms": ["t1"],
  "difficulty_level": "easy",
  "source_chunk_id": "chunk_001",
  "source_page": 10,
  "source_content_snippet": "..."
}
```

#### `POST /drafts/generate` — 从文档自动生成草稿

请求：
```json
{
  "source_document_id": "doc_001",
  "max_qa_per_chunk": 3,
  "min_qa_per_chunk": 1
}
```

响应：
```json
{
  "code": 0, "message": "success",
  "data": { "task_id": "task_001", "document_id": "doc_001" }
}
```

#### `GET/PUT/DELETE /drafts/{id}` — 获取/更新/删除草稿
#### `POST /drafts/{id}/review` — 审核草稿

请求：
```json
{
  "action": "approve",
  "review_comment": "内容准确，可以导入"
}
```

#### `POST /drafts/{id}/import` — 将草稿导入为正式用例

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "case_id": "tc_060",
    "query": "高血压用药注意事项有哪些",
    "...": "..."
  }
}
```

### 1.3 评估运行

#### `POST /runs` — 创建运行

请求：
```json
{
  "name": "基线测试-综合问诊v3",
  "description": "基线性能评估",
  "test_set_ids": ["ts_001", "ts_002"],
  "custom_case_ids": [],
  "snapshot_id": "snap_001",
  "config_version_id": "cv_003",
  "auto_snapshot": true,
  "simulated_role": "普通医生"
}
```

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "id": "run_001",
    "name": "基线测试-综合问诊v3",
    "description": "基线性能评估",
    "test_set_ids": ["ts_001", "ts_002"],
    "custom_case_ids": [],
    "snapshot_id": "snap_001",
    "config_version_id": "cv_003",
    "task_id": null,
    "status": "pending",
    "total_test_cases": 50,
    "passed_test_cases": 0,
    "overall_precision": null,
    "overall_recall": null,
    "overall_f1": null,
    "overall_mrr": null,
    "overall_ndcg": null,
    "overall_score": null,
    "l1_metrics_json": null,
    "l2_metrics_json": null,
    "l3_metrics_json": null,
    "diagnosis_json": null,
    "run_as_user_id": "user_001",
    "simulated_role_id": "role_doctor",
    "pipeline_id": "pipe_001",
    "pipeline_version": 3,
    "started_at": null,
    "completed_at": null,
    "created_at": "2026-05-14T10:20:00Z"
  }
}
```

#### `GET /runs` — 列出运行

查询参数：`status`, `test_set_id`, `pipeline_id`, `page`, `page_size`

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "items": [{
      "id": "run_001",
      "name": "基线测试-综合问诊v3",
      "test_set_ids": ["ts_001"],
      "status": "completed",
      "overall_score": 0.84,
      "total_test_cases": 50,
      "passed_test_cases": 42,
      "pipeline_id": "pipe_001",
      "pipeline_version": 3,
      "run_as_user_id": "user_001",
      "simulated_role_id": "role_doctor",
      "started_at": "2026-05-14T10:20:01Z",
      "completed_at": "2026-05-14T10:20:10Z",
      "created_at": "2026-05-14T10:20:00Z"
    }],
    "total": 12,
    "page": 1,
    "page_size": 20
  }
}
```

#### `GET /runs/{id}` — 获取运行详情

包含完整 l1/l2/l3_metrics_json 和 diagnosis_json。

#### `DELETE /runs/{id}` — 删除运行（running 状态先取消）
#### `DELETE /runs/batch` — 批量删除

请求：
```json
{"run_ids": ["run_001", "run_002"]}
```

#### `POST /runs/{id}/execute` — 启动执行

响应：
```json
{
  "code": 0, "message": "success",
  "data": {"task_id": "task_run_001"}
}
```

#### `POST /runs/{id}/cancel` — 取消运行

只可取消 running 状态的运行。内部通过 AsyncTaskManager.cancel_task 取消后台任务。

#### `POST /runs/{id}/execute/{case_id}` — 执行单个用例

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "id": "rr_001",
    "run_id": "run_001",
    "test_case_id": "tc_005",
    "query": "...",
    "retrieved_doc_ids": ["doc_1:chunk_3"],
    "retrieved_contexts": ["..."],
    "expected_knowledge_ids": ["doc_1:chunk_3"],
    "actual_knowledge_ids": ["doc_1:chunk_3"],
    "precision": 1.0,
    "recall": 1.0,
    "f1": 1.0,
    "mrr": 1.0,
    "ndcg": 1.0,
    "actual_answer": "...",
    "domain_results_json": {
      "心血管内科": {"hit": true, "contribution": 0.6},
      "内分泌科": {"hit": true, "contribution": 0.4}
    },
    "passed": true,
    "execution_time_ms": 350,
    "created_at": "2026-05-14T10:20:05Z"
  }
}
```

#### `POST /runs/{id}/evaluate` — 触发双轨评估

手动触发（异步后台任务）。用于自动后处理失败后的重试。

响应：
```json
{
  "code": 0, "message": "success",
  "data": {"task_id": "task_eval_001"}
}
```

#### `GET /runs/{id}/metrics` — 获取三层指标

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "l1": {
      "context_precision": {"value": 0.78, "passed": true, "threshold": 0.7, "details": {"case_count": 50, "pass_count": 42}},
      "context_recall": {"value": 0.72, "passed": true, "threshold": 0.6, "details": {"case_count": 50}},
      "noise_sensitivity": {"value": 0.25, "passed": true, "threshold": 0.3, "details": {"case_count": 50}},
      "mrr": {"value": 0.72, "passed": true, "threshold": 0.5, "details": {"case_count": 50}},
      "ndcg": {"value": 0.68, "passed": true, "threshold": 0.6, "details": {"case_count": 50}}
    },
    "l2": {
      "faithfulness": {"value": 0.85, "passed": true, "threshold": 0.8, "details": {"case_count": 45}},
      "answer_relevancy": {"value": 0.76, "passed": true, "threshold": 0.7, "details": {"case_count": 45}},
      "groundedness": {"value": 0.80, "passed": true, "threshold": 0.75, "details": {"case_count": 45}}
    },
    "l3": {
      "rule_compliance": {"value": 0.98, "passed": true, "threshold": 1.0, "details": {"case_count": 50}},
      "regression_score": {"value": 0.92, "passed": true, "threshold": 0.9, "details": {}},
      "cost_efficiency": {"value": 0.65, "passed": true, "threshold": 0.5, "details": {}},
      "config_stability": {"value": 0.97, "passed": true, "threshold": 0.95, "details": {}}
    },
    "cross_domain": {
      "domain_activation_acc": {"value": 0.88, "passed": true, "threshold": 0.8, "details": {"case_count": 50}},
      "cross_domain_coverage": {"value": 0.82, "passed": true, "threshold": 0.7, "details": {"case_count": 50}},
      "conflict_detection_rate": {"value": 0.65, "passed": true, "threshold": 0.6, "details": {"case_count": 30}},
      "e2e_latency_p95": {"value": 0.0, "passed": true, "threshold": 0.0, "details": {"p50": 1800, "p95": 3500, "p99": 4200}}
    },
    "overall_score": 0.84,
    "weights": {"l1": 0.4, "l2": 0.4, "l3": 0.15, "cross_domain": 0.05},
    "calculated_at": "2026-05-14T10:20:10Z"
  }
}
```

#### `GET /runs/{id}/diagnosis` — 获取六层诊断

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "layer1": {
      "layer": 1, "name": "规则引擎",
      "status": "pass", "score": 1.0,
      "total_cases": 50, "affected_cases": 0,
      "issues": [],
      "details": {},
      "execution_time_ms": 15
    },
    "layer2": {
      "layer": 2, "name": "历史对比",
      "status": "warn", "score": 0.85,
      "total_cases": 50, "affected_cases": 5,
      "issues": [{
        "severity": "warning",
        "category": "回归-检索精度",
        "description": "precision 从 0.82 降至 0.78，退化 4.9%",
        "affected_items": ["tc_012", "tc_023"],
        "suggestion": "检查近期文档更新是否影响检索质量"
      }],
      "details": {"baseline_run_id": "run_000"},
      "execution_time_ms": 200
    },
    "layer3": {
      "layer": 3, "name": "LLM 诊断",
      "status": "pass", "score": 0.90,
      "total_cases": 5, "affected_cases": 1,
      "issues": [{
        "severity": "info",
        "category": "幻觉检测",
        "description": "用例 tc_045 答案包含未在检索上下文中出现的药物名称",
        "affected_items": ["tc_045"],
        "suggestion": "检查知识库是否缺失相关药物文档"
      }],
      "execution_time_ms": 4500
    },
    "layer4": {
      "layer": 4, "name": "数据质量",
      "status": "warn", "score": 0.70,
      "issues": [{
        "severity": "warning",
        "category": "时效性",
        "description": "5 篇文档超过 90 天未更新",
        "affected_items": ["doc_003", "doc_007", "doc_012", "doc_018", "doc_025"],
        "suggestion": "建议检查这些文档是否需要更新或归档"
      }]
    },
    "layer5": {
      "layer": 5, "name": "效果评估",
      "status": "warn", "score": 0.75,
      "issues": [{
        "severity": "warning",
        "category": "嵌入质量",
        "description": "3 个查询与答案的余弦相似度 <0.3",
        "affected_items": ["tc_018", "tc_029", "tc_041"],
        "suggestion": "检查 Embedding 模型是否适合当前领域文本"
      }]
    },
    "layer6": {
      "layer": 6, "name": "回归检测",
      "status": "pass", "score": 0.95,
      "issues": []
    },
    "overall_health": 0.86,
    "total_issues": 4,
    "critical_issues": 0,
    "diagnosed_at": "2026-05-14T10:20:12Z"
  }
}
```

#### `GET /runs/{id}/stream` — SSE 进度流

连接：`/api/v1/rag/eval/runs/{id}/stream`。事件序列见 §5.2。

#### `GET /runs/compare` — 对比两个运行

查询参数：`run1=run_001`, `run2=run_002`

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "run_1": { "id": "run_001", "overall_score": 0.84, "...": "..." },
    "run_2": { "id": "run_002", "overall_score": 0.90, "...": "..." },
    "metric_deltas": {"precision": 0.03, "recall": 0.02, "mrr": -0.01},
    "improved": ["precision", "recall"],
    "degraded": ["mrr"],
    "common_bad_cases": ["tc_012", "tc_045"],
    "new_bad_cases": [],
    "fixed_bad_cases": ["tc_018", "tc_029"]
  }
}
```

### 1.4 报告

#### `GET /reports` — 报告列表

查询参数：`page`, `page_size`, `run_id`, `test_set_id`

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "items": [{
      "id": "rpt_001",
      "run_id": "run_001",
      "test_set_id": "ts_001",
      "config_version_id": "cv_003",
      "status": "completed",
      "summary": {
        "overall_score": 0.84,
        "l1_score": 0.82, "l2_score": 0.85, "l3_score": 0.90,
        "diagnosis_health": 0.86,
        "total_issues": 4, "critical_issues": 0,
        "run_name": "基线测试-综合问诊v3",
        "total_cases": 50, "passed_cases": 42,
        "duration_ms": 8500
      },
      "scoring_dashboard": {
        "l1": [{"name": "Context Precision", "value": 0.78, "passed": true, "threshold": 0.7, "details": {}}],
        "l2": [], "l3": []
      },
      "diagnosis_details": [],
      "bad_cases": [],
      "tuning_suggestions": [],
      "markdown_content": "# 评估报告\n...",
      "run_name": "基线测试-综合问诊v3",
      "overall_score": 0.84,
      "total_test_cases": 50,
      "passed_test_cases": 42,
      "duration_seconds": 8.5,
      "created_at": "2026-05-14T10:20:15Z"
    }],
    "total": 5, "page": 1, "page_size": 20
  }
}
```

#### `POST /reports` — 生成报告

请求：
```json
{
  "run_id": "run_001",
  "force": false
}
```

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "status": "started",
    "task_id": "task_report_001",
    "run_id": "run_001"
  }
}
```

或（已存在且 force=false）：
```json
{
  "code": 0, "message": "success",
  "data": {
    "status": "existing",
    "report_id": "rpt_001",
    "run_id": "run_001"
  }
}
```

#### `GET /reports/{id}` — 报告详情
#### `DELETE /reports/{id}` — 删除报告
#### `DELETE /reports/batch` — 批量删除

请求：
```json
{"ids": ["rpt_001", "rpt_002"]}
```

#### `GET /reports/{id}/export` — 导出报告

查询参数：`format` = `markdown` | `json` | `csv`

响应：对应格式的二进制内容（Content-Type: text/markdown, application/json, text/csv）

#### `GET /reports/generation/{task_id}/stream` — 报告生成进度 SSE

事件序列：
```
metrics_computing → metrics_done → building_report → rendering → saving → report_completed
```

#### `GET /trends` — 指标趋势

查询参数：`metric` (可选，指定指标名), `limit` (默认 10, 1-50), `pipeline_id` (可选)

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "run_ids": ["run_005", "run_004", "run_003", "run_002", "run_001"],
    "timestamps": ["2026-05-14T10:20:00Z", "2026-05-13T09:00:00Z", "..."],
    "overall_scores": [0.84, 0.82, 0.80, 0.78, 0.76],
    "metric_trends": {
      "context_precision": [0.78, 0.76, 0.75, 0.74, 0.72],
      "mrr": [0.72, 0.70, 0.71, 0.68, 0.67],
      "domain_activation_acc": [0.88, 0.85, 0.83, 0.80, 0.78]
    },
    "config_version_ids": ["cv_003", "cv_003", "cv_002", "cv_001", "cv_001"]
  }
}
```

### 1.5 调优

#### `GET /runs/{id}/tuning` — 获取调优建议列表

响应：
```json
{
  "code": 0, "message": "success",
  "data": [{
    "id": "tune_001",
    "run_id": "run_001",
    "report_id": "rpt_001",
    "category": "retrieval",
    "severity": "critical",
    "title": "药学域 BM25 检索 top_k 过小",
    "description": "药学域检索 top_k=10，Hit Rate 仅 0.65，低于阈值 0.7",
    "current_value": {"target_node_id": "node_bm25_药学", "target_param": "top_k", "val": 10},
    "suggested_value": {"target_node_id": "node_bm25_药学", "target_param": "top_k", "val": 20},
    "expected_impact": "Hit Rate 预计提升 0.10-0.15",
    "source": "diagnosis",
    "priority": 8,
    "safe_range": "10-30",
    "status": "pending",
    "conflict_with": "tune_003",
    "applied_config_version_id": null,
    "created_at": "2026-05-14T10:20:20Z"
  }]
}
```

#### `POST /tuning/{id}/adopt` — 采纳建议

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "id": "cv_004",
    "version_number": 4,
    "version_label": "自动采纳: 药学域 BM25 top_k → 20",
    "config_snapshot": { "...": "..." },
    "change_summary": "调优建议 tune_001 采纳：药学域 BM25 节点 top_k 从 10 改为 20",
    "created_by": "user_001",
    "created_at": "2026-05-14T10:21:00Z"
  }
}
```

#### `POST /tuning/{id}/reject` — 驳回建议

请求：
```json
{"reason": "当前 top_k=10 已在生产环境验证，暂不调整"}
```

#### `POST /tuning/{id}/ignore` — 忽略建议
#### `GET /config-versions` — 配置版本列表

查询参数：`page`, `page_size`

#### `POST /config-versions/{id}/rollback` — 回滚配置版本

请求：
```json
{"reason": "新版本导致药学域召回率下降"}
```

### 1.6 快照

#### `POST /snapshots` — 创建知识库快照

请求：
```json
{
  "name": "v3评估基线",
  "description": "综合问诊管道 v3 评估使用",
  "kb_id": "kb_001"
}
```

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "id": "snap_001",
    "name": "v3评估基线",
    "description": "综合问诊管道 v3 评估使用",
    "kb_id": "kb_001",
    "vector_backend_type": "chroma",
    "vector_store_path": "/data/vector/kb_001",
    "document_count": 150,
    "chunk_count": 3200,
    "config_version_id": "cv_003",
    "config_snapshot": {"chunk_strategy": "semantic", "chunk_size": 512, "embedding_model": "text-embedding-v3"},
    "expires_at": "2026-06-13T10:22:00Z",
    "status": "active",
    "created_at": "2026-05-14T10:22:00Z"
  }
}
```

#### `GET /snapshots` — 快照列表

查询参数：`kb_id`, `status` (active/expired/invalid), `page`, `page_size`

#### `GET /snapshots/{id}` — 快照详情
#### `POST /snapshots/{id}/restore` — 恢复快照

响应：
```json
{
  "code": 0, "message": "success",
  "data": {
    "restored_snapshot_id": "snap_001",
    "pre_restore_snapshot_id": "snap_backup_001",
    "message": "快照已恢复，恢复前状态已保存为 snap_backup_001"
  }
}
```

---

## 2. 数据库 DDL

以下为 MySQL 5.7 完整建表语句（无外键约束，采用弱关联）。

### 2.1 test_cases

```sql
CREATE TABLE test_cases (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    query           TEXT         NOT NULL                  COMMENT '测试问题',
    description     TEXT         NULL                      COMMENT '期望答案描述',
    expected_knowledge_ids JSON  NULL                      COMMENT '期望检索的知识片段 ID 列表',
    expected_keywords       JSON  NULL                      COMMENT '期望关键词列表',
    answer_points_summary   TEXT NULL                      COMMENT '答案要点摘要',
    difficulty_level        VARCHAR(16) NULL               COMMENT 'easy/medium/hard',
    professional_terms      JSON  NULL                      COMMENT '专业术语列表',
    relevance_scores        JSON  NULL                      COMMENT '文档→相关度评分映射',
    relevant_domains        JSON  NULL                      COMMENT '[新增] 相关域列表，如["心血管内科","内分泌科"]',
    expected_conflicts      JSON  NULL                      COMMENT '[新增] 期望冲突列表:[{statement_a,source_a,statement_b,source_b}]',
    source          VARCHAR(16)  NOT NULL DEFAULT 'manual' COMMENT 'manual/draft/import',
    source_draft_id VARCHAR(64)  NULL                      COMMENT '来源草稿 ID',
    source_document_id VARCHAR(64) NULL                    COMMENT '来源文档 ID',
    version         INT          NOT NULL DEFAULT 1,
    tenant_id       VARCHAR(64)  NOT NULL DEFAULT ''       COMMENT '租户 ID',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_source (source),
    INDEX idx_tenant (tenant_id),
    INDEX idx_difficulty (difficulty_level),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试用例';
```

### 2.2 test_sets

```sql
CREATE TABLE test_sets (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL                  COMMENT '测试集名称',
    description     TEXT         NULL                      COMMENT '用途描述',
    source_type     VARCHAR(16)  NOT NULL DEFAULT 'manual' COMMENT 'manual/json_import/book_generated/mixed',
    visibility      VARCHAR(16)  NOT NULL DEFAULT 'private' COMMENT '[新增] public/role_scoped/private',
    owner_id        VARCHAR(64)  NOT NULL DEFAULT ''       COMMENT '创建者 ID',
    tenant_id       VARCHAR(64)  NOT NULL DEFAULT ''       COMMENT '租户 ID',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tenant (tenant_id),
    INDEX idx_owner (owner_id),
    INDEX idx_visibility (visibility),
    INDEX idx_source_type (source_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试集';
```

### 2.3 test_set_cases

```sql
CREATE TABLE test_set_cases (
    id              INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    test_set_id     VARCHAR(64) NOT NULL                  COMMENT '测试集 ID',
    test_case_id    VARCHAR(64) NOT NULL                  COMMENT '测试用例 ID',
    added_at        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_set_case (test_set_id, test_case_id),
    INDEX idx_test_case (test_case_id),
    INDEX idx_test_set (test_set_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试集-用例多对多关联';
```

### 2.4 test_runs

```sql
CREATE TABLE test_runs (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    description     TEXT         NULL,
    test_set_ids    JSON         NOT NULL                  COMMENT '关联的测试集 ID 列表',
    custom_case_ids JSON         NULL                      COMMENT '额外用例 ID 列表',
    snapshot_id     VARCHAR(64)  NULL                      COMMENT '知识库快照 ID',
    config_version_id VARCHAR(64) NULL                    COMMENT '配置版本 ID',
    config_snapshot JSON         NULL                      COMMENT '配置快照',
    previous_config_version_id VARCHAR(64) NULL            COMMENT '前一配置版本 ID',
    task_id         VARCHAR(64)  NULL                      COMMENT '异步任务 ID',
    status          VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed/cancelled',
    total_test_cases INT         NOT NULL DEFAULT 0,
    passed_test_cases INT        NOT NULL DEFAULT 0,
    overall_precision DECIMAL(5,4) NULL,
    overall_recall    DECIMAL(5,4) NULL,
    overall_f1        DECIMAL(5,4) NULL,
    overall_mrr       DECIMAL(5,4) NULL,
    overall_ndcg      DECIMAL(5,4) NULL,
    l1_metrics_json   JSON NULL                           COMMENT 'L1 检索质量指标',
    l2_metrics_json   JSON NULL                           COMMENT 'L2 生成质量指标',
    l3_metrics_json   JSON NULL                           COMMENT 'L3 系统质量指标',
    cross_domain_metrics_json JSON NULL                   COMMENT '[新增] 跨域扩展指标',
    overall_score     DECIMAL(5,4) NULL                    COMMENT '加权综合得分',
    diagnosis_json    JSON NULL                           COMMENT '六层诊断结果',
    pipeline_id       VARCHAR(64)  NULL                    COMMENT '[新增] 被评估的管道 ID',
    pipeline_version  INT          NULL                    COMMENT '[新增] 被评估的管道版本号',
    run_as_user_id    VARCHAR(64)  NULL                    COMMENT '[新增] 实际执行者用户 ID',
    simulated_role_id VARCHAR(64)  NULL                    COMMENT '[新增] 模拟的角色 ID',
    domain_results_json JSON NULL                         COMMENT '[新增] 汇总所有用例的域贡献结果',
    started_at    DATETIME NULL,
    completed_at  DATETIME NULL,
    tenant_id     VARCHAR(64)  NOT NULL DEFAULT ''         COMMENT '租户 ID',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_snapshot (snapshot_id),
    INDEX idx_task (task_id),
    INDEX idx_tenant (tenant_id),
    INDEX idx_pipeline (pipeline_id),
    INDEX idx_run_as_user (run_as_user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试运行';
```

### 2.5 test_run_results

```sql
CREATE TABLE test_run_results (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    run_id          VARCHAR(64)  NOT NULL                  COMMENT '测试运行 ID',
    test_case_id    VARCHAR(64)  NOT NULL                  COMMENT '测试用例 ID',
    query           TEXT         NOT NULL,
    retrieved_doc_ids       JSON NULL                      COMMENT '检索到的文档 ID 列表',
    retrieved_contexts      JSON NULL                      COMMENT '检索上下文文本列表',
    relevant_doc_ids        JSON NULL                      COMMENT '相关文档 ID 列表',
    expected_knowledge_ids  JSON NULL                      COMMENT '期望知识片段 ID',
    actual_knowledge_ids    JSON NULL                      COMMENT '实际匹配的知识片段 ID',
    matched_count   INT         NOT NULL DEFAULT 0,
    expected_count  INT         NOT NULL DEFAULT 0,
    actual_count    INT         NOT NULL DEFAULT 0,
    precision       DECIMAL(5,4) NULL,
    recall          DECIMAL(5,4) NULL,
    f1              DECIMAL(5,4) NULL,
    mrr             DECIMAL(5,4) NULL DEFAULT 0,
    ndcg            DECIMAL(5,4) NULL,
    hit_rate_1      DECIMAL(5,4) NULL DEFAULT 0,
    hit_rate_3      DECIMAL(5,4) NULL DEFAULT 0,
    hit_rate_5      DECIMAL(5,4) NULL DEFAULT 0,
    actual_answer   TEXT NULL                              COMMENT 'RAG 生成的实际答案',
    l1_metrics_json JSON NULL                              COMMENT '单用例 L1 指标',
    l2_metrics_json JSON NULL                              COMMENT '单用例 L2 指标',
    diagnosis_json  JSON NULL                              COMMENT '单用例诊断结果',
    domain_results_json JSON NULL                          COMMENT '[新增] 各域贡献结果:{"域A":{"hit":true,"contribution":0.6}}',
    passed          TINYINT(1) NULL                        COMMENT '是否通过',
    error_message   TEXT NULL,
    execution_time_ms INT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run (run_id),
    INDEX idx_test_case (test_case_id),
    INDEX idx_passed (passed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试运行结果';
```

### 2.6 eval_reports

```sql
CREATE TABLE eval_reports (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    run_id          VARCHAR(64)  NOT NULL                  COMMENT '测试运行 ID',
    test_set_id     VARCHAR(64)  NULL                      COMMENT '主测试集 ID',
    config_version_id VARCHAR(64) NULL                     COMMENT '配置版本 ID',
    overall_score   DECIMAL(5,4) NULL                      COMMENT '三层加权综合得分',
    l1_score        DECIMAL(5,4) NULL,
    l2_score        DECIMAL(5,4) NULL,
    l3_score        DECIMAL(5,4) NULL,
    cross_domain_score DECIMAL(5,4) NULL                   COMMENT '[新增] 跨域综合得分',
    precision       DECIMAL(5,4) NULL,
    recall          DECIMAL(5,4) NULL,
    f1              DECIMAL(5,4) NULL,
    mrr             DECIMAL(5,4) NULL,
    ndcg            DECIMAL(5,4) NULL,
    metrics_json    JSON         NOT NULL                  COMMENT '三层指标 RunMetrics JSON',
    diagnosis_json  JSON         NULL                      COMMENT '六层诊断结果 JSON',
    bad_cases_json  JSON         NULL                      COMMENT '坏案列表 JSON',
    suggestions_json JSON        NULL                      COMMENT '调优建议列表 JSON',
    cross_domain_json JSON      NULL                      COMMENT '[新增] 跨域分析章节 JSON',
    markdown_content TEXT        NULL                      COMMENT 'Markdown 报告内容',
    status          VARCHAR(16)  NOT NULL DEFAULT 'processing' COMMENT 'processing/completed/superseded',
    tenant_id       VARCHAR(64)  NOT NULL DEFAULT ''       COMMENT '租户 ID',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run (run_id),
    INDEX idx_test_set (test_set_id),
    INDEX idx_status (status),
    INDEX idx_tenant (tenant_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评估报告';
```

### 2.7 knowledge_snapshots

```sql
CREATE TABLE knowledge_snapshots (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    description     TEXT         NULL,
    kb_id           VARCHAR(64)  NOT NULL DEFAULT ''       COMMENT '[新增] 知识库 ID',
    vector_backend_type VARCHAR(32) NOT NULL DEFAULT 'chroma' COMMENT '[新增] chroma/elasticsearch/milvus',
    vector_store_path VARCHAR(512) NOT NULL                 COMMENT '向量库存储路径/连接信息',
    document_count  INT          NOT NULL DEFAULT 0,
    chunk_count     INT          NOT NULL DEFAULT 0,
    doc_ids_json    JSON         NULL                      COMMENT '[新增] 冻结文档 ID 列表（浅拷贝引用）',
    chunk_strategy_json JSON     NULL                      COMMENT '[新增] 分块策略快照',
    embedding_config_json JSON   NULL                      COMMENT '[新增] Embedding 配置快照',
    config_version_id VARCHAR(64) NULL                     COMMENT '配置版本 ID',
    config_snapshot JSON         NULL                      COMMENT '配置快照 JSON',
    status          VARCHAR(16)  NOT NULL DEFAULT 'active' COMMENT '[新增] active/expired/invalid',
    expires_at      DATETIME     NULL                      COMMENT '[新增] 过期时间',
    tenant_id       VARCHAR(64)  NOT NULL DEFAULT ''       COMMENT '租户 ID',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_kb (kb_id),
    INDEX idx_status (status),
    INDEX idx_tenant (tenant_id),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库快照';
```

### 2.8 tuning_suggestions

```sql
CREATE TABLE tuning_suggestions (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    run_id          VARCHAR(64)  NOT NULL                  COMMENT '测试运行 ID',
    report_id       VARCHAR(64)  NULL                      COMMENT '关联报告 ID',
    category        VARCHAR(32)  NOT NULL                  COMMENT 'retrieval/generation/system/permission',
    severity        VARCHAR(16)  NOT NULL                  COMMENT 'critical/warning/info',
    title           VARCHAR(255) NOT NULL,
    description     TEXT         NOT NULL,
    current_value   JSON         NULL                      COMMENT '当前参数值',
    suggested_value JSON         NULL                      COMMENT '建议参数值',
    expected_impact TEXT         NULL                      COMMENT '预期影响描述',
    source          VARCHAR(16)  NOT NULL DEFAULT 'auto'   COMMENT 'auto/manual',
    priority        INT          NOT NULL DEFAULT 0        COMMENT '优先级 1-10',
    safe_range      JSON         NULL                      COMMENT '安全调整范围',
    status          VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/adopted/rejected/ignored',
    conflict_with   JSON         NULL                      COMMENT '[改造] 冲突建议 ID 列表（从单个字符串改为 JSON 数组）',
    applied_config_version_id VARCHAR(64) NULL             COMMENT '采纳后生成的配置版本 ID',
    tenant_id       VARCHAR(64)  NOT NULL DEFAULT ''       COMMENT '租户 ID',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run (run_id),
    INDEX idx_report (report_id),
    INDEX idx_category (category),
    INDEX idx_status (status),
    INDEX idx_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调优建议';
```

### 2.9 eval_config_versions

```sql
CREATE TABLE eval_config_versions (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    version_number  INT          NOT NULL DEFAULT 1        COMMENT '版本序号（应用层维护）',
    version_label   VARCHAR(100) NULL,
    config_snapshot JSON         NOT NULL                  COMMENT '完整配置快照',
    change_summary  TEXT         NULL                      COMMENT '变更摘要',
    change_set_id   VARCHAR(64)  NULL                      COMMENT '[新增] 关联的变更集 ID',
    created_by      VARCHAR(64)  NULL                      COMMENT '创建者',
    tenant_id       VARCHAR(64)  NOT NULL DEFAULT ''       COMMENT '租户 ID',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tenant (tenant_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评估配置版本';
```

### 2.10 eval_config_change_sets

```sql
CREATE TABLE eval_config_change_sets (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    change_set_label VARCHAR(255) NOT NULL,
    config_version_id VARCHAR(64) NOT NULL                 COMMENT '目标配置版本',
    previous_version_id VARCHAR(64) NULL                   COMMENT '[新增] 回滚源版本 ID',
    status          VARCHAR(16)  NOT NULL DEFAULT 'committed' COMMENT 'committed/rolled_back',
    rollback_reason TEXT         NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rolled_back_at  DATETIME     NULL,
    tenant_id       VARCHAR(64)  NOT NULL DEFAULT ''       COMMENT '租户 ID',
    INDEX idx_config_version (config_version_id),
    INDEX idx_status (status),
    INDEX idx_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评估配置变更集';
```

### 2.11 test_case_drafts

```sql
CREATE TABLE test_case_drafts (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    source_document_id VARCHAR(64) NULL                    COMMENT '来源文档 ID',
    query           TEXT         NOT NULL                  COMMENT '测试问题',
    description     TEXT         NULL                      COMMENT '期望答案描述',
    expected_knowledge_ids JSON  NULL                      COMMENT '期望检索的知识片段 ID 列表',
    expected_keywords       JSON  NULL                      COMMENT '期望关键词列表',
    answer_points           JSON  NULL                      COMMENT '答案要点列表',
    professional_terms      JSON  NULL                      COMMENT '专业术语列表',
    difficulty_level VARCHAR(16) NULL                      COMMENT 'easy/medium/hard',
    faithfulness_score DECIMAL(5,4) NULL                   COMMENT '忠实度评分(0-1)',
    source_chunk_id VARCHAR(64) NULL                       COMMENT '来源分块 ID',
    source_page     INT         NULL                       COMMENT '来源页码',
    source_content_snippet TEXT NULL                       COMMENT '来源内容片段',
    generation_params JSON     NULL                        COMMENT '生成参数快照',
    batch_id        VARCHAR(64) NULL                       COMMENT '生成批次 ID',
    draft_index     INT         NOT NULL DEFAULT 0         COMMENT '批次内序号',
    status          VARCHAR(16) NOT NULL DEFAULT 'draft'   COMMENT 'draft/reviewed/rejected/imported',
    version         INT         NOT NULL DEFAULT 1,
    tenant_id       VARCHAR(64) NOT NULL DEFAULT ''        COMMENT '租户 ID',
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_source_doc (source_document_id),
    INDEX idx_batch (batch_id),
    INDEX idx_status (status),
    INDEX idx_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试用例草稿';
```

---

## 3. 服务层架构（继承+改造）

以下 7 个 Facade 的完整继承与改造标记，`[继承]` 表示从 `backend/src/service/rag_eval/` 直接继承无改动，`[改造]` 表示需适配修改，`[新增]` 表示从零构建。

### 3.1 RunEngineFacade

**来源**：`backend/src/service/rag_eval/run/facade.py`（306 行）

| 组件 | 标记 | 说明 |
|------|------|------|
| `RunEngineFacade` | `[改造]` | 新增 `pipeline_compiler` 注入；新增权限上下文传递；新增跨域指标收集 |
| `TestCaseExecutor` | `[改造]` | 从原 `IRetrievalService.retrieve_knowledge()` 替换为 **PipelineCompiler.execute()**；执行后提取 `domain_results`（各域贡献） |
| `BatchTestRunner` | `[改造]` | 新增 `run_as_user_id` / `simulated_role_id` 认证上下文注入；每次执行前设置权限 Scope |
| `ResultProcessor` | `[改造]` | 新增跨域结果聚合；新增 `domain_results_json` 汇总到 `test_run_results` |
| `SnapshotManager` | `[改造]` | 适配 3 种向量后端（Chroma/Elasticsearch/Milvus）；浅拷贝 + 冻结保护；快照失效检测 |
| `TestRunRepository` | `[继承]` | 无改动 |
| `TestRunResultRepository` | `[继承]` | 新增 `domain_results_json` 字段读写 |

**依赖注入变更**：
```python
# before
RunEngineFacade(executor, batch_runner, result_processor, snapshot_manager,
                test_run_repository, test_run_result_repository, case_engine,
                retrieval_service, generation_service, config_cache, async_task_manager)

# after — retrieval_service 替换为 pipeline_compiler + auth_context_provider
RunEngineFacade(executor, batch_runner, result_processor, snapshot_manager,
                test_run_repository, test_run_result_repository, case_engine,
                pipeline_compiler,           # [改造] PipelineCompiler 实例
                auth_context_provider,       # [新增] 权限上下文提供者
                generation_service,
                config_cache, async_task_manager)
```

### 3.2 MetricEngineFacade

**来源**：`backend/src/service/rag_eval/metrics/facade.py`（145 行）

| 组件 | 标记 | 说明 |
|------|------|------|
| `MetricEngineFacade` | `[改造]` | 新增 `calculate_cross_domain()` 方法；`calculate_and_diagnose()` 并行增加跨域指标计算 |
| `ScoringFacade` | `[继承]` | L1/L2/L3 12 项指标无改动 |
| `DiagnosisOrchestrator` | `[改造]` | L3 LLM 诊断的 prompt 去业务化（通用化）；新增跨域诊断维度 |
| `calculators/cross_domain_calc.py` | `[新增]` | 4 项跨域指标计算器：`DomainActivationAccCalc`, `CrossDomainCoverageCalc`, `ConflictDetectionRateCalc`, `E2ELatencyCalc` |

**新增跨域指标计算器接口**：
```python
class CrossDomainMetrics(BaseModel):
    domain_activation_acc: MetricScore
    cross_domain_coverage: MetricScore
    conflict_detection_rate: MetricScore
    e2e_latency_p95: MetricScore  # details 中存储 p50/p95/p99

class CrossDomainCalc(IMetricCalculator):
    """跨域扩展指标计算器基类"""
    def calculate(self, inputs: list[MetricInput]) -> MetricScore: ...
```

### 3.3 ReportEngineFacade

**来源**：`backend/src/service/rag_eval/report/facade.py`（300 行）

| 组件 | 标记 | 说明 |
|------|------|------|
| `ReportEngineFacade` | `[改造]` | `_generate_report_with_progress()` 流程不变；新增跨域章节数据注入 |
| `ReportBuilder` | `[改造]` | `build()` 方法新增跨域分析章节 `CrossDomainSection` |
| `MarkdownRenderer` | `[改造]` | 渲染模板新增跨域分析章节（域贡献度表格 + 冲突统计） |
| `TrendAnalyzer` | `[继承]` | 无改动 |
| `ReportExporter` | `[继承]` | 新增 `cross_domain_json` 导出支持 |

**跨域分析章节 Schema**：
```python
class CrossDomainSection(BaseModel):
    domain_contributions: list[DomainContribution]  # 各域贡献度
    overall_activation_accuracy: float
    overall_cross_coverage: float
    overall_conflict_detection_rate: float
    e2e_latency_distribution: E2ELatencyDistribution
    domain_conflicts: list[CrossDomainConflictSummary]

class DomainContribution(BaseModel):
    domain_name: str
    activation_accuracy: float
    hit_count: int
    total_queries: int
    avg_contribution_score: float

class CrossDomainConflictSummary(BaseModel):
    domain_pair: tuple[str, str]
    total_conflicts: int
    detected_conflicts: int
    detection_rate: float

class E2ELatencyDistribution(BaseModel):
    p50_ms: int
    p95_ms: int
    p99_ms: int
    avg_ms: int
```

### 3.4 TuningEngineFacade

**来源**：`backend/src/service/rag_eval/tuning/facade.py`（104 行）

| 组件 | 标记 | 说明 |
|------|------|------|
| `TuningEngineFacade` | `[改造]` | `analyze()` 新增加 pipeline_compiler 感知的调优建议 |
| `TuningAdvisor` | `[改造]` | 新增 `generate_cross_domain_suggestions()`；建议 `category` 新增 `permission` |
| `ConflictDetector` | `[改造]` | `conflict_with` 从单字符串改为 JSON 数组（支持多个冲突） |
| `ConfigChanger` | `[改造]` | 采纳后写入管道配置（通过 PipelineCompiler API），同时写入 eval_config_versions |

**内联调优 UI 支持**：
- 每条 `TuningSuggestion` 包含 `target_node_id` 和 `target_param`（在 `current_value`/`suggested_value` JSON 中），前端可直接定位到管道编辑器对应节点
- "🔧 去编辑器中打开" 按钮需路由到 `/pipelines/:id/edit` 并传入 `{highlightNode: target_node_id}` 参数

### 3.5 CaseEngineFacade

**来源**：`backend/src/service/rag_eval/case/facade.py`（83 行）

| 组件 | 标记 | 说明 |
|------|------|------|
| `CaseEngineFacade` | `[改造]` | 方法签名不变，内部透传 `relevant_domains` / `expected_conflicts` / `tenant_id` |
| `CaseService` | `[改造]` | `create()` / `update()` 新增 `relevant_domains`、`expected_conflicts` 字段处理；新增 `import_csv()` 支持 CSV 导入 |
| `SetService` | `[改造]` | 新增 `visibility` 字段读写；新增租户隔离查询 |

### 3.6 DraftEngineFacade

**来源**：`backend/src/service/rag_eval/draft/facade.py`

| 组件 | 标记 | 说明 |
|------|------|------|
| `DraftEngineFacade` | `[继承]` | 无改动 |
| `DraftGenerator` | `[继承]` | LLM 草稿生成逻辑无改动 |
| `FaithfulnessChecker` | `[继承]` | 忠实度验证无改动 |
| `DraftDeduplicator` | `[继承]` | MinHash 去重无改动 |
| `BookMetadataAnalyzer` | `[继承]` | 文档元数据分析无改动 |

### 3.7 RagEvalOrchestrator

**来源**：`backend/src/service/rag_eval/orchestrator.py`（210 行）

| 组件 | 标记 | 说明 |
|------|------|------|
| `RagEvalOrchestrator` | `[改造]` | `run_full_evaluation()` 新增 `pipeline_id` / `pipeline_version` / `simulated_role` 参数；`post_run_pipeline()` 流程不变 |

**新增的协调方法**：
```python
async def run_pipeline_comparison(
    self, test_set_ids: list[str], pipeline_id: str,
    version_a: int, version_b: int, config_version_id: str = None,
) -> dict:  # {"run_id_a": "...", "run_id_b": "..."}
    """同一数据集上对比两个管道版本的指标差异"""

async def run_cross_role_evaluation(
    self, test_set_ids: list[str], pipeline_id: str,
    roles: list[str],
) -> dict:  # {"run_ids": ["...", "..."], "role_comparison": {...}}
    """同一管道多个角色模拟评估"""
```

---

## 4. 关键改造点

### 4.1 PipelineCompiler 集成（TestCaseExecutor）

**当前实现**：`build_execution_functions()` 使用 `IRetrievalService.retrieve_knowledge()` 直调原 RAG 管线。

**改造后**：
```python
# 在 RunEngineFacade.build_execution_functions() 中
# before:
retrieval_fn = lambda query: self._retrieval.retrieve_knowledge(query, limit=5, ...)

# after:
retrieval_fn = lambda query: self._pipeline_compiler.execute(
    pipeline_id=run.pipeline_id,
    pipeline_version=run.pipeline_version,
    query=query,
    search_params={"top_k": 5},
    auth_context=self._auth_context_provider.get_context(
        user_id=run.run_as_user_id,
        simulated_role_id=run.simulated_role_id,
    ),
)

# PipelineCompiler.execute() 返回值包含 domain_results:
# {
#   "documents": [{"id": "...", "content": "...", "score": 0.9, "domain": "心血管内科"}],
#   "domain_results": {
#     "心血管内科": {"activated": True, "contribution": 0.6},
#     "内分泌科": {"activated": True, "contribution": 0.4},
#   },
#   "answer": "..."
# }
```

**关键变更**：
1. 检索路径从 `IRetrievalService` → `PipelineCompiler`
2. `TestCaseExecutor.execute()` 提取 `domain_results` 写入 `test_run_results.domain_results_json`
3. 评估运行走内部执行通道，不经过发布 URL / 通用端点的限流中间件（资源隔离，见需求 §5.2）

### 4.2 认证上下文注入（BatchTestRunner）

```python
# 在 BatchTestRunner.execute_run() 中
async def execute_run(self, run_id: str, test_cases: list, **kwargs):
    run = await self._run_repo.get_by_id(run_id)

    # [新增] 设置认证上下文
    auth_ctx = self._auth_context_provider.get_context(
        user_id=run.run_as_user_id,
        simulated_role_id=run.simulated_role_id,
    )

    for case in test_cases:
        # 每个用例执行前注入权限上下文
        result = await self._executor.execute(
            test_case=case,
            run_id=run_id,
            auth_context=auth_ctx,
            retrieval_fn=retrieval_fn,
            generation_fn=generation_fn,
        )
        # ...保存结果，推送 SSE
```

**权限模型**：
- 同一管道 + 同一测试集 + 不同角色 → 指标可能不同（设计意图，非 bug）
- 管道对比限制在同一角色视域内进行（苹果比苹果）

### 4.3 跨域指标计算器（新增 4 项）

**位置**：`backend/src/service/rag_eval/metrics/scoring/calculators/cross_domain_calc.py`

```python
class DomainActivationAccCalc(IMetricCalculator):
    """域激活准确率
    计算方式：|准确激活域 ∩ 期望激活域| / |期望激活域|
    Ground Truth：TestCase.relevant_domains
    实际值：PipelineCompiler.execute() 返回的 domain_results 中 activated=True 的域列表
    """
    def calculate(self, inputs: list[MetricInput]) -> MetricScore: ...

class CrossDomainCoverageCalc(IMetricCalculator):
    """跨域覆盖率
    计算方式：|有结果贡献的域 ∩ 期望激活域| / |期望激活域|
    """
    def calculate(self, inputs: list[MetricInput]) -> MetricScore: ...

class ConflictDetectionRateCalc(IMetricCalculator):
    """冲突检测率
    计算方式：|检测到的冲突 ∩ 期望冲突| / |期望冲突|
    若无 ground truth（expected_conflicts 为空），返回 N/A
    """
    def calculate(self, inputs: list[MetricInput]) -> MetricScore: ...

class E2ELatencyCalc(IMetricCalculator):
    """端到端延迟 P95
    计算方式：所有用例 execution_time_ms 的 P50/P95/P99 分布
    不设硬阈值，仅趋势监控
    """
    def calculate(self, inputs: list[MetricInput]) -> MetricScore: ...
```

**跨域综合得分权重**（可配置于 L2 评估配置版本）：

```python
# L0 默认
DEFAULT_CROSS_DOMAIN_WEIGHTS = {
    "domain_activation_acc": 0.30,
    "cross_domain_coverage": 0.30,
    "conflict_detection_rate": 0.20,
    "e2e_latency_p95": 0.20,
}
```

**跨域指标间的 N/A 处理**：
- 若某个用例的 `relevant_domains` 为空 → 域激活准确率和跨域覆盖率对该用例返回 N/A
- 若某个用例的 `expected_conflicts` 为空 → 冲突检测率对该用例返回 N/A，不计入分母
- 端到端延迟永远有值（即使执行失败，记录失败的 execution_time_ms）

### 4.4 报告跨域分析章节（ReportBuilder）

**新增章节** `CrossDomainSection`（见 §3.3 Schema）：

- `ReportBuilder.build()` 方法中新增 `_build_cross_domain_section(results, cross_domain_metrics)` 步骤
- `MarkdownRenderer` 渲染模板新增：

```markdown
## 跨域分析

| 域 | 激活准确率 | 命中次数 | 平均贡献度 |
|----|-----------|---------|-----------|
| 心血管内科 | 1.00 | 25/25 | 0.88 |
| 内分泌科 | 0.90 | 18/20 | 0.82 |
| 药学 | 0.70 | 14/20 | 0.65 ⚠️ |

### 跨域冲突统计
| 域对 | 期望冲突 | 检测到冲突 | 检测率 |
|------|---------|-----------|--------|
| 心血管 ↔ 内分泌 | 5 | 4 | 0.80 |
| 内分泌 ↔ 药学 | 3 | 2 | 0.67 |

### 端到端延迟分布
| P50 | P95 | P99 | 平均 |
|-----|-----|-----|------|
| 1800ms | 3500ms | 4200ms | 2100ms |
```

### 4.5 SnapshotManager 多向量后端适配

**当前实现**：假设单一 Chroma 后端，`vector_store_path` 是本地路径字符串。

**改造后**：

```python
class SnapshotManager:
    def __init__(self, vector_backend_registry: VectorBackendRegistry, ...):
        self._backends = vector_backend_registry
        # 支持 chroma / elasticsearch / milvus

    async def create_snapshot(self, kb_id: str, name: str, description: str) -> SnapshotRead:
        backend = await self._backends.get(kb_id)
        vector_ref = await backend.get_reference()  # 返回 {"type": "chroma", "path": "/data/...", "index": "kb_001"}

        # 获取当前文档列表和分块数
        docs = await self._doc_repo.get_by_kb(kb_id)
        total_chunks = sum(doc.chunk_count for doc in docs)

        # 标记文档和分块为"已冻结"
        await self._doc_repo.mark_frozen(doc_ids=[d.id for d in docs])

        # 创建浅拷贝快照记录
        return await self._snap_repo.create({
            "id": generate_id(),
            "name": name,
            "description": description,
            "kb_id": kb_id,
            "vector_backend_type": vector_ref["type"],
            "vector_store_path": vector_ref.get("path") or vector_ref.get("index"),
            "document_count": len(docs),
            "chunk_count": total_chunks,
            "doc_ids_json": [d.id for d in docs],
            "chunk_strategy_json": await self._config_cache.get_json("rag.chunk"),
            "embedding_config_json": await self._config_cache.get_json("rag.embedding"),
            "status": "active",
            "expires_at": datetime.now() + timedelta(days=30),
            "tenant_id": current_tenant_id(),
        })

    async def check_validity(self, snapshot_id: str) -> bool:
        """快照是否仍然有效（向量后端未迁移，数据未清理）"""
        snap = await self._snap_repo.get_by_id(snapshot_id)
        current_backend = await self._backends.get(snap.kb_id)
        return current_backend.type == snap.vector_backend_type  # 后端类型一致即有效
```

### 4.6 内联调优建议生成（TuningAdvisor）

**改造**：调优建议不再仅在 `post_run_pipeline` 中生成一次。改为：

1. **后处理生成**：与现有逻辑一致，`analyze()` 在指标+诊断完成后调用
2. **跨域调优建议**：新增 `generate_cross_domain_suggestions()` 方法，基于 `DomainContribution`、`E2ELatencyDistribution` 等生成域相关建议
3. **内联采纳**：前端评估详情页直接展示 `TuningSuggestion` 卡片，采纳触发 `config_changer.apply_suggestion()` 写入管道配置 + 创建配置版本

**跨域调优建议类型示例**：

| 类型 | 触发条件 | 建议内容 |
|------|---------|---------|
| `domain_activation_miss` | 某域激活准确率 < 0.7 | 建议检查该域的 `activation_rules.keywords` 是否完整 |
| `cross_domain_imbalance` | 多域查询中某域贡献度 < 0.3 | 建议调整该域在混合检索中的 `domain_weight` |
| `conflict_undetected` | 冲突检测率 < 0.5 | 建议开启/增强冲突检测节点 |
| `latency_bottleneck` | e2e P95 > 阈值 | 建议降低 `top_k` 或启用语义缓存 |

---

## 5. 数据流

### 5.1 完整评估执行流程

```
用户 → POST /runs (create_run)
          │
          ├── CaseEngineFacade.get_set() × N (收集所有用例)
          ├── SnapshotManager.create_snapshot() (auto_snapshot=true 时)
          ├── TestRunRepository.create() → status=pending
          └── return run_id

用户 → POST /runs/{run_id}/execute (start_run)
          │
          ├── RunRepository.update() → status=running, total_test_cases=N
          ├── AsyncTaskManager.start_task(
          │       task_type="test_run",
          │       task_func=BatchTestRunner.execute_run)
          └── return task_id

BatchTestRunner.execute_run() [后台任务]:
  │
  ├── SSE push: run_started {run_id, total_cases, pipeline_version}
  │
  ├── FOR 每个用例 (并发数: rag.eval.run.concurrency, 默认 5):
  │   │
  │   ├── SSE push: case_started {case_id, query}
  │   │
  │   ├── TestCaseExecutor.execute():
  │   │   ├── PipelineCompiler.execute(query, auth_context)
  │   │   │   └── 返回: documents[], domain_results{}, answer
  │   │   ├── 计算 RetrievalMetrics (precision/recall/f1/mrr/ndcg/hit_rate)
  │   │   └── 生成 actual_answer (LLM generation)
  │   │
  │   ├── TestRunResultRepository.create() → 保存单用例结果
  │   │
  │   ├── SSE push: case_completed {case_id, precision, recall, mrr, passed}
  │   │   或 SSE push: case_failed {case_id, error_message}
  │   │
  │   └── NEXT
  │
  ├── RunRepository.update() → status=completed, passed_test_cases=N, completed_at=now
  │
  ├── SSE push: run_completed {run_id, overall_score, passed_count, failed_count}
  │
  └── 触发 on_complete 回调 → RagEvalOrchestrator.post_run_pipeline(run_id)
```

### 5.2 后处理流水线 (post_run_pipeline)

```
RagEvalOrchestrator.post_run_pipeline(run_id):
  │
  ├── SSE push: metrics_computing {run_id}
  │
  ├── 并行步骤 A + B (asyncio.gather):
  │   │
  │   ├── [A] MetricEngineFacade.calculate_all(results):
  │   │   ├── ScoringFacade.calculate_layer(1) → L1 5 项指标
  │   │   ├── ScoringFacade.calculate_layer(2) → L2 3 项指标
  │   │   ├── ScoringFacade.calculate_layer(3) → L3 4 项指标
  │   │   └── [新增] ScoringFacade.calculate_cross_domain() → 4 项跨域指标
  │   │
  │   └── [B] MetricEngineFacade.diagnose_all(run_id, results):
  │       │
  │       ├── DiagnosisOrchestrator.run_layer(1) → L1 规则引擎
  │       ├── DiagnosisOrchestrator.run_layer(2) → L2 历史对比
  │       ├── DiagnosisOrchestrator.run_layer(3) → L3 LLM 诊断
  │       ├── DiagnosisOrchestrator.run_layer(4) → L4 数据质量
  │       ├── DiagnosisOrchestrator.run_layer(5) → L5 效果评估
  │       └── DiagnosisOrchestrator.run_layer(6) → L6 回归检测
  │
  ├── 验证结果有效性 (has case_count? l1_metrics 非空?)
  ├── RunEngineFacade.save_evaluation(run_id, metrics, diagnosis)
  │
  ├── SSE push: metrics_done {run_id, overall_score}
  │
  ├── 调优建议生成:
  │   └── TuningEngineFacade.analyze(run_id, metrics, diagnosis, bad_cases)
  │       ├── TuningAdvisor.generate_suggestions()
  │       ├── TuningAdvisor.generate_cross_domain_suggestions() [新增]
  │       ├── ConflictDetector.detect_conflicts()
  │       └── TuningSuggestionRepository.create() × N
  │
  ├── SSE push: report_generating {run_id, stage: "building"}
  │
  ├── 报告生成:
  │   ├── ReportBuilder.build(run_id)
  │   │   ├── _build_summary() → OverallSummary
  │   │   ├── _build_scoring_dashboard() → ScoringDashboard
  │   │   ├── _build_diagnosis_details() → list[DiagnosisSection]
  │   │   ├── [新增] _build_cross_domain_section() → CrossDomainSection
  │   │   ├── _collect_bad_cases() → list[BadCaseEntry]
  │   │   └── _collect_tuning_suggestions() → list[TuningEntry]
  │   │
  │   ├── SSE push: report_generating {run_id, stage: "rendering"}
  │   ├── MarkdownRenderer.render(data) → markdown_content
  │   │
  │   ├── 标记旧报告 superseded (ReportRepository.update())
  │   │
  │   ├── SSE push: report_generating {run_id, stage: "saving"}
  │   ├── ReportRepository.create() → 保存 EvalReport
  │   │
  │   └── SSE push: report_completed {run_id, report_id}
  │
  └── 完成
```

### 5.3 SSE 进度事件序列（完整）

```
Channel: test_run:{run_id}

1.  run_started        {run_id, total_cases, pipeline_version}
2.  case_started       {case_id, query}                    ← × N
3.  case_completed     {case_id, precision, recall, mrr, passed}  ← × N
    或 case_failed     {case_id, error_message}            ← × N
4.  run_completed      {run_id, overall_score, passed_count, failed_count}
5.  metrics_computing  {run_id}
6.  metrics_done       {run_id, overall_score}
7.  report_generating  {run_id, stage: "building"|"rendering"|"saving"}
8.  report_completed   {run_id, report_id}
    或 report_failed   {run_id, error}

额外事件（取消/异常）：
    run_cancelled      {run_id}
    run_failed         {run_id, error_message}
```

SSE 连接生命周期：
- 最大连接时长：10 分钟（超时后服务端关闭）
- 缓冲容量：最近 200 条事件
- 事件 ID 格式：`{run_id}:{seq}`
- 断线重连：客户端携带 `Last-Event-ID`，服务端从该事件 ID 后续推
- 完成保持：`run_completed` 推送后，连接保持 30 秒再关闭

### 5.4 调优建议 → 采纳 → 配置版本创建流程

```
用户: GET /runs/{run_id}/tuning
  └→ TuningEngineFacade.get_suggestions(run_id)
      └→ 返回 TuningSuggestion[] (含 conflict_with)

用户: POST /tuning/{id}/adopt
  └→ TuningEngineFacade.adopt(suggestion_id)
      │
      ├── 校验：status must be "pending"
      │
      ├── ConfigChanger.apply_suggestion(suggestion):
      │   ├── 解析 suggested_value 中的 target_node_id / target_param / val
      │   ├── PipelineCompiler.update_node_config(target_node_id, target_param, val)
      │   │   └── 直接写入管道配置（管道配置变更由 [01] 模块处理）
      │   ├── 生成变更摘要
      │   └── ConfigVersionRepository.create():
      │       ├── id = cv_003
      │       ├── config_snapshot = {...}  (完整配置快照)
      │       ├── change_summary = "调优建议 tune_001 采纳：..."
      │       ├── change_set_id = cs_001
      │       └── created_by = current_user.id
      │
      ├── ConfigChangeSetRepository.create():
      │   ├── id = cs_001
      │   ├── config_version_id = cv_003
      │   ├── previous_version_id = cv_002
      │   └── status = "committed"
      │
      ├── TuningSuggestionRepository.update(suggestion_id):
      │   ├── status = "adopted"
      │   └── applied_config_version_id = cv_003
      │
      └── 返回 ConfigVersionRead

用户: POST /config-versions/{id}/rollback
  └→ ConfigChanger.rollback(version_id, reason)
      ├── 读取目标版本的 config_snapshot
      ├── PipelineCompiler.restore_config(config_snapshot)
      ├── 创建新 ConfigVersion (快照 = 目标版本快照)
      ├── 标记原 ConfigChangeSet 为 rolled_back
      └── 创建新 ConfigChangeSet 记录回滚操作
```

### 5.5 知识库快照创建与冻结流程

```
用户: POST /snapshots (kb_id, name, description)
  └→ SnapshotManager.create_snapshot(kb_id, name, description)
      │
      ├── VectorBackendRegistry.get(kb_id) → 确定后端类型 (chroma/es/milvus)
      │
      ├── 获取知识库元数据:
      │   ├── DocumentRepository.get_by_kb(kb_id) → 文档列表
      │   ├── 当前分块策略 (config_cache)
      │   ├── 当前 Embedding 配置 (config_cache)
      │   └── 当前桶/索引路径 (vector_backend)
      │
      ├── 冻结保护:
      │   └── DocumentRepository.mark_frozen(doc_ids=[...])
      │       └── 被冻结文档: 不可删除 / 不可重新解析
      │       └── 被冻结分块: 不可被索引重建覆盖
      │
      ├── 创建快照记录 (KnowledgeSnapshotRepository.create()):
      │   ├── id = snap_001
      │   ├── kb_id = kb_001
      │   ├── vector_backend_type = "chroma"
      │   ├── vector_store_path = "/data/vector/kb_001"
      │   ├── doc_ids_json = ["doc_001", "doc_002", ...]
      │   ├── chunk_strategy_json = {...}
      │   ├── embedding_config_json = {...}
      │   ├── status = "active"
      │   └── expires_at = now + 30 days
      │
      └── 返回 SnapshotRead

定时清理 (APScheduler, 每天 03:00):
  → SnapshotManager.cleanup_expired_snapshots()
      ├── 查询 status=active AND expires_at < now
      ├── 标记为 expired
      └── 解冻对应文档 (DocumentRepository.unmark_frozen)

快照失效检测:
  → 若知识库执行了向量后端迁移：
      └── 所有引用旧后端的快照标记为 invalid
      └── 评估运行不可选择已失效的快照
```

---

## 6. 测试策略

### 6.1 单元测试

| 测试目标 | 测试文件 | 覆盖场景 |
|---------|---------|---------|
| **跨域指标计算器** | `tests/unit/metrics/test_cross_domain_calc.py` | 全部激活 / 部分激活 / 全未激活；空 relevant_domains → N/A；空 expected_conflicts → N/A；带 ground truth 冲突 |
| **L1/L2/L3 指标计算器** | `tests/unit/metrics/test_precision_recall.py` 等（继承） | 无改动，直接继承现有测试 |
| **诊断层 L1-L6** | `tests/unit/metrics/test_diagnosis_layer*.py`（继承） | L3 新增"L3 跳过"场景（LLM 不可用时 status=skipped） |
| **草稿生成与审核** | `tests/unit/draft/test_generator.py` 等（继承） | 无改动，继承现有测试 |
| **草稿去重** | `tests/unit/draft/test_deduplicator.py`（继承） | 无改动 |
| **调优建议生成** | `tests/unit/tuning/test_advisor.py`（继承 + 新增） | 跨域调优建议；冲突检测（多冲突 JSON 数组） |
| **冲突检测器** | `tests/unit/tuning/test_conflict_detector.py`（改造） | 参数直接冲突/间接冲突/效果对冲；多冲突 JSON 数组 format |
| **PipelineCompiler mock 适配** | `tests/unit/run/test_executor_pipeline.py`（新增） | 验证 TestCaseExecutor 正确调用 PipelineCompiler.execute()；验证 domain_results 提取 |
| **权限上下文注入** | `tests/unit/run/test_auth_context.py`（新增） | 验证 BatchTestRunner 在执行前注入正确的 auth_context；同一个 test_case 用不同 role 得到不同结果 |

### 6.2 集成测试

| 测试目标 | 测试文件 | 覆盖场景 |
|---------|---------|---------|
| **完整评估运行（mock PipelineCompiler）** | `tests/integration/test_run_full.py` | 创建 run → execute → post_run_pipeline → 报告生成 |
| **跨域指标完整链路** | `tests/integration/test_cross_domain_eval.py`（新增） | 用例含 relevant_domains / expected_conflicts → 运行 → 跨域指标计算 → 报告跨域章节 |
| **报告生成** | `tests/integration/test_report.py`（继承） | Markdown/JSON/CSV 导出；superseded 状态；跨域章节 |
| **快照创建与恢复** | `tests/integration/test_snapshot.py`（改造） | 浅拷贝创建；多向量后端 mock；冻结保护；过期清理；无效快照检测 |
| **调优采纳流程** | `tests/integration/test_tuning_adopt.py`（改造） | 采纳 → ConfigChanger → 配置版本创建 → 管道配置更新 |
| **SSE 进度事件** | `tests/integration/test_run_sse.py`（继承） | 完整事件序列验证；断线重连；心跳 |

### 6.3 关键测试场景（≥12）

| # | 场景 | 类型 | 验证点 |
|---|------|------|--------|
| 1 | **完整评估→报告**：创建含 10 个用例的运行，mock PipelineCompiler 返回预设结果，验证 post_run_pipeline 全链路 | 集成 | 创建 run → execute → 指标计算正确 → 诊断执行 → 调优建议生成 → 报告生成 → status=completed |
| 2 | **跨域指标 N/A 处理**：用例无 relevant_domains → 跨域指标返回 N/A → 综合得分分母正确排除 | 单元+集成 | DomainActivationAccCalc 对空 relevant_domains 返回 N/A；整体 overall_score 不受影响 |
| 3 | **跨域冲突检测**：用例标注 expected_conflicts → 检索结果实际检测到部分冲突 → 冲突检测率 ∈ [0,1] | 集成 | ConflictDetectionRateCalc 正确计算检测率；报告跨域章节展示冲突统计 |
| 4 | **权限注入验证**：管理员角色 vs 普通医生角色运行同一测试集 → 检索结果不同 → 指标不同 | 集成 | BatchTestRunner 正确注入 auth_context；PipelineCompiler 接收不同 context 返回不同结果 |
| 5 | **管道版本对比**：同一测试集 + pipeline v2 vs v3 → 指标有差异 → RunComparison 正确 | 集成 | compare_runs() 正确计算 metric_deltas；前端并排展示 |
| 6 | **SSE 断线重连**：模拟 SSE 客户端断开 → 携带 Last-Event-ID 重连 → 服务端从该 ID 后续推 | 集成 | sse_response() 正确处理 Last-Event-ID header；事件不丢失不重复 |
| 7 | **并发控制**：同时启动 3 个运行 → 第三个被拒绝（max_concurrent_runs=2） | 单元+集成 | AppException(RUN_LIMIT_EXCEEDED) 抛出；前端正确展示 |
| 8 | **快照冻结保护**：创建快照后尝试删除文档 → DocRepository 拒绝 → 返回 FROZEN_DOCUMENT 错误 | 集成 | SnapshotManager.mark_frozen() 生效；delete 被拦截 |
| 9 | **快照失效检测**：模拟向量后端迁移 → 旧快照标记为 invalid → 评估运行不可选择 | 单元 | SnapshotManager.check_validity() 正确判断 |
| 10 | **调优采纳冲突**：采纳一条建议后检测到与其他建议冲突 → ConflictDetector 标记 conflict_with → 前端展示警告 | 单元 | ConflictDetector.detect_conflicts() 正确返回 ConflictPair[] |
| 11 | **报告 superseded**：同一 run 生成两次报告 → 旧报告 status=superseded → 新报告 status=completed | 集成 | ReportEngineFacade._supersede() 正确标记；GET /reports 只返回最新 |
| 12 | **坏案 N/A 排除**：空答案用例 → 各项指标返回 N/A → 不计入 L2 分母 | 单元+集成 | MetricEngineFacade.calculate_all() 正确跳过 N/A 用例 |
| 13 | **L3 LLM 诊断降级**：LLM API 返回 429 → 诊断层返回 status=skipped → 不阻塞其他层 | 单元 | DiagnosisOrchestrator.run_layer(3) 正确将异常转为 skipped 状态 |
| 14 | **内联调优"去编辑器中打开"**：采纳操作生成 target_node_id → 前端路由跳转到管道编辑器并高亮节点 | 集成 | TuningSuggestion.suggested_value 包含正确的 target_node_id / target_param |

---

## 7. 验收标准映射

将需求 AC-6.1 至 AC-6.34 映射到测试场景：

| AC | 内容 | 测试场景 |
|----|------|---------|
| AC-6.1 | 全部 12 项三层指标正确计算，阈值校验有效 | 场景 1 (完整评估) + 单元测试 L1/L2/L3 计算器 |
| AC-6.2 | 六层诊断全部执行，每层输出正确的问题列表 | 场景 1 (完整评估) + 单元测试 L1-L6 诊断层 |
| AC-6.3 | 草稿自动生成 → 审核 → 导入为用例完整流程 | 现有单元测试（继承，无需重写） |
| AC-6.4 | 测试集创建、用例关联、导出功能完整 | 现有集成测试（继承，无需重写） |
| AC-6.5 | 评估运行 SSE 进度推送全部事件类型正确触发 | 场景 6 (SSE 断线重连) |
| AC-6.6 | 评估运行并发控制正确（全局 2 运行，单运行 5 并发） | 场景 7 (并发控制) |
| AC-6.7 | 后处理流水线自动触发，指标计算和报告生成成功 | 场景 1 (完整评估) |
| AC-6.8 | 报告导出正确（Markdown/JSON/CSV） | 集成测试 ReportExporter |
| AC-6.9 | 调优建议自动生成，采纳/驳回/忽略操作有效 | 场景 10 (调优采纳冲突) + 单元测试 TuningEngineFacade |
| AC-6.10 | 采纳建议后自动创建配置版本，回滚可用 | 场景 10 (调优采纳) + 集成测试 ConfigChanger.rollback() |
| AC-6.11 | 知识库快照创建/恢复正确冻结知识库状态 | 场景 8 (快照冻结) + 场景 9 (快照失效) |
| AC-6.12 | 坏案过滤正确——N/A 用例不计入指标分母 | 场景 12 (N/A 排除) |
| AC-6.13 | 报告 superseded 状态正确 | 场景 11 (报告 superseded) |
| AC-6.14 | 跨域指标正确计算 | 场景 2 (N/A 处理) + 场景 3 (冲突检测) |
| AC-6.15 | 评估运行注入权限上下文，不同角色指标不同 | 场景 4 (权限注入) |
| AC-6.16 | 评估数据集按租户隔离、按角色控制可见性 | 集成测试（tenant_id 隔离 + visibility 过滤） |
| AC-6.17 | 管道对比限制在同一角色视域内 | 场景 5 (管道版本对比) |
| AC-6.18 | 管道版本对比评估 | 场景 5 (管道版本对比) |
| AC-6.19 | 报告跨域分析章节正确展示 | 场景 3 (跨域冲突) + 场景 1 (报告跨域章节) |
| AC-6.20 | 测试数据在 `/knowledge/test-data` 下，三选项卡切换正常 | 前端集成测试（路由 + 组件渲染） |
| AC-6.21 | TestCase 创建表单含 expected_knowledge_ids、difficulty_level | 前端组件测试 |
| AC-6.22 | JSON 导入增加格式校验和预览 | 前端集成测试 |
| AC-6.23 | CaseTransferModal 分页加载，支持超过 100 条用例 | 前端组件测试（分页 + 虚拟滚动） |
| AC-6.24 | 管道评估视图正确展示评估历史 | 前端集成测试 |
| AC-6.25 | 新建评估抽屉正确加载测试集列表、管道版本、角色模拟选项 | 前端集成测试 |
| AC-6.26 | 模拟角色评估——管理员以普通医生身份运行 | 场景 4 (权限注入) + 前端集成测试 |
| AC-6.27 | 选中 2 个运行对比 → 并排展示指标差异 | 前端组件测试（RunComparison 组件） |
| AC-6.28 | 评估详情页一页内展示所有内容 | 前端集成测试 |
| AC-6.29 | 域分析区块展示各域贡献度、激活准确率、冲突统计 | 前端组件测试（DomainContribChart） |
| AC-6.30 | "去编辑器中打开"点击后切换到编辑视图并高亮对应节点 | 前端集成测试（路由跳转 + 节点高亮） |
| AC-6.31 | 内联调优"采纳"后自动修改管道参数 + 创建配置版本 | 场景 10 (调优采纳) + 前端集成测试 |
| AC-6.32 | conflict 正确检测多条建议修改同一参数 | 场景 10 (调优采纳冲突) |
| AC-6.33 | 4 个提示词页面存根已移除，提示词归入 `/settings/config` | 前端路由测试（验证旧路由 404）+ 新路由可访问 |
| AC-6.34 | TrendChart 正确部署 | 前端组件测试（TrendChart 渲染 + 数据绑定） |
