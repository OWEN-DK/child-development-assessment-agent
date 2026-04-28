# 01 - 统一数据模型

## 需求

废止 Legacy 体系（7张表）和 RagEval 体系（16张表），设计全新的 11 张核心表 + 保留并 ALTER 1 张旧表（`source_documents`）。

## 字段决策

| 决策点 | Legacy | RagEval | 选择 | 理由 |
|--------|--------|---------|------|------|
| 年龄格式 | `age` DECIMAL(4,1) | `age_months` INT | **DECIMAL(4,1)** | 支持半年（1.5岁） |
| 预期知识 | `expected_knowledge_ids` JSON | `expected_document_ids` | **`expected_knowledge_ids` JSON** | 与 RAG 系统一致 |
| 测试集关联 | `test_set_ids` JSON 数组 | `test_set_id` 单值 FK | **`test_set_ids` JSON 数组** | 支持跨集运行 |
| ID 格式 | VARCHAR(64) | VARCHAR(36) UUID | **VARCHAR(64)** | 与现有 ID 生成一致 |
| 指标存储 | 扁平字段 | `validation_results` JSON | **双轨**：扁平 + JSON | 向后兼容 + 扩展性 |
| 表前缀 | 无前缀 | `rag_eval_` | **无前缀** | 统一体系无需区分 |

## DDL

### 1. source_documents（保留旧表，ALTER 新增字段）

旧表已存在 `id`、`title`、`file_type`、`file_path`、`created_at`。RAG 文档导入管道（`DocumentIngestionFacade`）依赖旧字段，不破坏。

ALTER 增量见本文末尾"保留并 ALTER"章节。

完整字段参考（含旧字段 + 新增字段）：

```
id              VARCHAR(64)   PK（旧）
title           VARCHAR(255)  NOT NULL（旧）
file_type       VARCHAR(32)   NOT NULL（旧）
file_path       VARCHAR(512)  NOT NULL（旧）
file_hash       VARCHAR(64)   新增，SHA-256
content_summary TEXT          新增
page_count      INT           新增
status          VARCHAR(16)   新增，uploaded/parsing/ready/archived
created_at      DATETIME      （旧）
updated_at      DATETIME      新增
```

### 2. test_case_drafts

```sql
CREATE TABLE `test_case_drafts` (
    `id` VARCHAR(64) PRIMARY KEY,
    `source_document_id` VARCHAR(64) COMMENT '来源文档 ID',
    `query` TEXT NOT NULL COMMENT '测试问题',
    `age` DECIMAL(4,1) NOT NULL COMMENT '年龄（岁，如 1.5）',
    `age_stage_label` VARCHAR(20) NOT NULL DEFAULT '' COMMENT '年龄段标签(0-6m/1-2y等)',
    `domain` VARCHAR(32) NOT NULL COMMENT 'gross_motor/fine_motor/language/cognitive/social_emotional/sensory_integration',
    `description` TEXT COMMENT '期望答案描述',
    `expected_knowledge_ids` JSON COMMENT '期望检索的知识片段 ID 列表',
    `expected_keywords` JSON COMMENT '期望关键词列表',
    `answer_points` JSON COMMENT '答案要点列表',
    `professional_terms` JSON COMMENT '专业术语列表',
    `difficulty_level` VARCHAR(16) COMMENT 'easy/medium/hard',
    `faithfulness_score` DECIMAL(5,4) COMMENT '忠实度评分(0-1)',
    `source_chunk_id` VARCHAR(64) COMMENT '来源分块 ID',
    `source_page` INT COMMENT '来源页码',
    `source_content_snippet` TEXT COMMENT '来源内容片段',
    `generation_params` JSON COMMENT '生成参数快照',
    `batch_id` VARCHAR(64) COMMENT '生成批次 ID',
    `draft_index` INT DEFAULT 0 COMMENT '批次内序号',
    `status` VARCHAR(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/reviewed/rejected/imported',
    `version` INT NOT NULL DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_source_document_id` (`source_document_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_domain` (`domain`),
    INDEX `idx_batch_id` (`batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3. test_cases

```sql
CREATE TABLE `test_cases` (
    `id` VARCHAR(64) PRIMARY KEY,
    `query` TEXT NOT NULL COMMENT '测试问题',
    `age` DECIMAL(4,1) NOT NULL COMMENT '年龄（岁）',
    `age_stage_label` VARCHAR(20) NOT NULL DEFAULT '' COMMENT '年龄段标签',
    `domain` VARCHAR(32) NOT NULL COMMENT '测试领域',
    `description` TEXT COMMENT '期望答案描述',
    `expected_knowledge_ids` JSON COMMENT '期望检索的知识片段 ID 列表',
    `expected_keywords` JSON COMMENT '期望关键词列表',
    `answer_points_summary` TEXT COMMENT '答案要点摘要',
    `min_age_requirement` DECIMAL(4,1) COMMENT '最小年龄要求',
    `max_age_requirement` DECIMAL(4,1) COMMENT '最大年龄要求',
    `difficulty_level` VARCHAR(16) COMMENT 'easy/medium/hard',
    `professional_terms` JSON COMMENT '专业术语列表',
    `relevance_scores` JSON COMMENT '相关度评分',
    `source` VARCHAR(16) NOT NULL DEFAULT 'manual' COMMENT 'manual/draft/import',
    `source_draft_id` VARCHAR(64) COMMENT '来源草稿 ID',
    `source_document_id` VARCHAR(64) COMMENT '来源文档 ID',
    `version` INT NOT NULL DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_domain` (`domain`),
    INDEX `idx_age_stage_label` (`age_stage_label`),
    INDEX `idx_source` (`source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 4. test_sets

```sql
CREATE TABLE `test_sets` (
    `id` VARCHAR(64) PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT,
    `source_type` VARCHAR(16) NOT NULL DEFAULT 'manual' COMMENT 'manual/json_import/book_generated/mixed',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 5. test_set_cases

```sql
CREATE TABLE `test_set_cases` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `test_set_id` VARCHAR(64) NOT NULL,
    `test_case_id` VARCHAR(64) NOT NULL,
    `added_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_set_case` (`test_set_id`, `test_case_id`),
    INDEX `idx_test_case_id` (`test_case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 6. knowledge_snapshots

```sql
CREATE TABLE `knowledge_snapshots` (
    `id` VARCHAR(64) PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT,
    `vector_store_path` VARCHAR(512) NOT NULL COMMENT '向量库存储路径',
    `document_count` INT NOT NULL DEFAULT 0,
    `chunk_count` INT NOT NULL DEFAULT 0,
    `config_version_id` VARCHAR(64) COMMENT '配置版本 ID',
    `config_snapshot` JSON COMMENT '配置快照 JSON',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_config_version_id` (`config_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 7. test_runs

```sql
CREATE TABLE `test_runs` (
    `id` VARCHAR(64) PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT,
    `test_set_ids` JSON NOT NULL COMMENT '关联的测试集 ID 列表',
    `custom_case_ids` JSON COMMENT '额外用例 ID 列表',
    `snapshot_id` VARCHAR(64) COMMENT '知识库快照 ID',
    `config_version_id` VARCHAR(64) COMMENT '配置版本 ID',
    `config_snapshot` JSON COMMENT '配置快照',
    `previous_config_version_id` VARCHAR(64) COMMENT '前一配置版本 ID',
    `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed/cancelled',
    `total_test_cases` INT NOT NULL DEFAULT 0,
    `passed_test_cases` INT NOT NULL DEFAULT 0,
    -- 扁平指标（现有字段）
    `overall_precision` DECIMAL(5,4) COMMENT '整体精确率',
    `overall_recall` DECIMAL(5,4) COMMENT '整体召回率',
    `overall_f1` DECIMAL(5,4) COMMENT '整体F1',
    `overall_mrr` DECIMAL(5,4) COMMENT '整体MRR',
    `overall_ndcg` DECIMAL(5,4) COMMENT '整体NDCG',
    -- 三层指标（双轨之一）
    `l1_metrics_json` JSON COMMENT 'L1 检索质量指标',
    `l2_metrics_json` JSON COMMENT 'L2 生成质量指标',
    `l3_metrics_json` JSON COMMENT 'L3 系统质量指标',
    `overall_score` DECIMAL(5,4) COMMENT '加权综合得分',
    -- 六层诊断（双轨之二）
    `diagnosis_json` JSON COMMENT '六层诊断结果',
    `started_at` DATETIME,
    `completed_at` DATETIME,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_status` (`status`),
    INDEX `idx_snapshot_id` (`snapshot_id`),
    INDEX `idx_config_version_id` (`config_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 8. test_run_results

```sql
CREATE TABLE `test_run_results` (
    `id` VARCHAR(64) PRIMARY KEY,
    `run_id` VARCHAR(64) NOT NULL,
    `test_case_id` VARCHAR(64) NOT NULL,
    `query` TEXT NOT NULL,
    -- 检索结果
    `retrieved_doc_ids` JSON COMMENT '检索到的文档 ID 列表',
    `relevant_doc_ids` JSON COMMENT '相关文档 ID 列表',
    `expected_knowledge_ids` JSON COMMENT '期望知识片段 ID',
    `actual_knowledge_ids` JSON COMMENT '实际匹配的知识片段 ID',
    `matched_count` INT DEFAULT 0,
    `expected_count` INT DEFAULT 0,
    `actual_count` INT DEFAULT 0,
    -- 检索指标
    `precision` DECIMAL(5,4),
    `recall` DECIMAL(5,4),
    `f1` DECIMAL(5,4),
    `mrr` DECIMAL(5,4) DEFAULT 0,
    `ndcg` DECIMAL(5,4),
    `hit_rate_1` DECIMAL(5,4) DEFAULT 0,
    `hit_rate_3` DECIMAL(5,4) DEFAULT 0,
    `hit_rate_5` DECIMAL(5,4) DEFAULT 0,
    -- 生成答案
    `actual_answer` TEXT COMMENT 'RAG 生成的实际答案',
    -- 双轨指标
    `l1_metrics_json` JSON COMMENT '单用例 L1 指标',
    `l2_metrics_json` JSON COMMENT '单用例 L2 指标',
    `diagnosis_json` JSON COMMENT '单用例诊断结果',
    -- 执行信息
    `passed` TINYINT(1) COMMENT '是否通过',
    `error_message` TEXT,
    `execution_time_ms` INT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_run_id` (`run_id`),
    INDEX `idx_test_case_id` (`test_case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 9. eval_reports

```sql
CREATE TABLE `eval_reports` (
    `id` VARCHAR(64) PRIMARY KEY,
    `run_id` VARCHAR(64) NOT NULL,
    `test_set_id` VARCHAR(64) COMMENT '主测试集 ID',
    `config_version_id` VARCHAR(64) COMMENT '配置版本 ID',
    `overall_score` DECIMAL(5,4) COMMENT '三层加权综合得分',
    `l1_score` DECIMAL(5,4) COMMENT 'L1 层得分',
    `l2_score` DECIMAL(5,4) COMMENT 'L2 层得分',
    `l3_score` DECIMAL(5,4) COMMENT 'L3 层得分',
    -- 精简版扁平指标（向后兼容）
    `precision` DECIMAL(5,4),
    `recall` DECIMAL(5,4),
    `f1` DECIMAL(5,4),
    `mrr` DECIMAL(5,4),
    `ndcg` DECIMAL(5,4),
    -- 完整 JSON
    `metrics_json` JSON NOT NULL COMMENT '三层指标 RunMetrics JSON',
    `diagnosis_json` JSON COMMENT '六层诊断结果 JSON',
    `bad_cases_json` JSON COMMENT '坏案列表 JSON',
    `suggestions_json` JSON COMMENT '调优建议列表 JSON',
    `markdown_content` LONGTEXT COMMENT 'Markdown 报告内容',
    `status` VARCHAR(16) NOT NULL DEFAULT 'processing' COMMENT 'processing/completed/superseded',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_run_id` (`run_id`),
    INDEX `idx_test_set_id` (`test_set_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 10. tuning_suggestions

```sql
CREATE TABLE `tuning_suggestions` (
    `id` VARCHAR(64) PRIMARY KEY,
    `run_id` VARCHAR(64) NOT NULL,
    `report_id` VARCHAR(64) COMMENT '关联报告 ID',
    `category` VARCHAR(32) NOT NULL COMMENT 'retrieval/generation/configuration/cost/prompt',
    `severity` VARCHAR(16) NOT NULL COMMENT 'critical/warning/info',
    `title` VARCHAR(255) NOT NULL,
    `description` TEXT NOT NULL,
    `current_value` JSON COMMENT '当前值',
    `suggested_value` JSON COMMENT '建议值',
    `expected_impact` TEXT COMMENT '预期影响',
    `source` VARCHAR(16) NOT NULL DEFAULT 'rule_engine' COMMENT 'rule_engine/llm/diagnosis',
    `priority` INT DEFAULT 0 COMMENT '优先级（数值越高越优先）',
    `safe_range` JSON COMMENT '安全范围',
    `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/adopted/rejected/ignored',
    `conflict_with` VARCHAR(64) COMMENT '冲突的建议 ID',
    `applied_config_version_id` VARCHAR(64) COMMENT '采纳后生成的配置版本 ID',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_run_id` (`run_id`),
    INDEX `idx_report_id` (`report_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 11. config_versions

```sql
CREATE TABLE `config_versions` (
    `id` VARCHAR(64) PRIMARY KEY,
    `version_number` INT NOT NULL DEFAULT 1,
    -- ⚠️ 注意：version_number 不是 AUTO_INCREMENT，由应用层通过 MAX(version_number) + 1 维护序列号
    -- 原因：MySQL 5.7 不支持一个表同时有 VARCHAR PK 和 AUTO_INCREMENT，且业务 ID 和自增序列不应耦合
    `version_label` VARCHAR(100) COMMENT '版本标签',
    `config_snapshot` JSON NOT NULL COMMENT '完整配置快照',
    `change_summary` TEXT COMMENT '变更摘要',
    `created_by` VARCHAR(64) COMMENT '创建者',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
    -- 不设 uk_version_number 约束，允许应用层分配相同编号（如多实例同时创建）
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 12. config_change_sets

```sql
CREATE TABLE `config_change_sets` (
    `id` VARCHAR(64) PRIMARY KEY,
    `change_set_label` VARCHAR(255) NOT NULL COMMENT '变更集标签',
    `config_version_id` VARCHAR(64) NOT NULL COMMENT '目标配置版本',
    `status` VARCHAR(16) NOT NULL DEFAULT 'committed' COMMENT 'committed/rolled_back',
    `rollback_reason` TEXT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `rolled_back_at` DATETIME,
    INDEX `idx_config_version_id` (`config_version_id`),
    INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 枚举定义（统一位置）

所有枚举统一定义在 `models/rag_eval/enums.py`（重写），禁止在其他文件重复定义：

```python
class TestDomain(str, PyEnum):
    GROSS_MOTOR = "gross_motor"
    FINE_MOTOR = "fine_motor"
    LANGUAGE = "language"
    COGNITIVE = "cognitive"
    SOCIAL_EMOTIONAL = "social_emotional"
    SENSORY_INTEGRATION = "sensory_integration"

class TestCaseStatus(str, PyEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    IMPORTED = "imported"

class TestRunStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TestSourceType(str, PyEnum):
    MANUAL = "manual"
    JSON_IMPORT = "json_import"
    BOOK_GENERATED = "book_generated"
    MIXED = "mixed"

class DifficultyLevel(str, PyEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class DocumentStatus(str, PyEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    ARCHIVED = "archived"
```

### ORM Enum 映射（强制）

所有 ORM 模型中使用 Enum 的列，**必须**显式传递 `values_callable`，防止大小写导致 `LookupError`：

```python
from src.models.rag_eval.enums import TestDomain, TestRunStatus, TestSourceType, DifficultyLevel

# 正确写法示例（test_case.py ORM 模型中）
domain = Column(
    Enum(TestDomain, values_callable=lambda obj: [e.value for e in obj]),
    nullable=False,
    comment="测试领域",
)
status = Column(
    Enum(TestRunStatus, values_callable=lambda obj: [e.value for e in obj]),
    nullable=False,
    default=TestRunStatus.PENDING,
    comment="运行状态",
)

# 插入数据时必须使用枚举类成员（非字符串）
run.status = TestRunStatus.RUNNING  # ✅ 正确
run.status = "running"              # ❌ 禁止，会导致 DataError
```

### Import 迁移（Phase 0 执行）

现有代码中有两处重复定义 `TestDomain`：
- `schemas/test_case.py`：`class TestDomain(str, Enum)` — 用于 Pydantic Schema
- `models/test_case.py`：`class TestDomain(PyEnum)` — 用于 ORM 列定义

Phase 0 删除旧文件后，所有新代码统一从 `models/rag_eval/enums.py` 导入：

```python
# 后端 ORM 模型和 Schema 统一导入
from src.models.rag_eval.enums import TestDomain, TestRunStatus, TestSourceType, DifficultyLevel

# Pydantic Schema 中直接使用（Pydantic v2 自动序列化 str 子类枚举）
class TestCaseRead(BaseModel):
    domain: TestDomain
    model_config = ConfigDict(from_attributes=True)
```

Phase 0 需 grep 所有旧 import 路径并替换：
- `from src.schemas.test_case import TestDomain` → `from src.models.rag_eval.enums import TestDomain`
- `from src.models.test_case import TestDomain` → `from src.models.rag_eval.enums import TestDomain`

## 废止的旧表（23张）

### Legacy 体系（7张）

`test_cases`, `test_case_drafts`, `test_sets`, `test_set_cases`, `test_runs`, `test_run_results`, `knowledge_snapshots`

### RagEval 体系（16张）

`rag_eval_test_sets`, `rag_eval_test_set_cases`, `rag_eval_test_cases`, `rag_eval_test_case_drafts`, `rag_eval_test_runs`, `rag_eval_test_run_results`, `rag_eval_test_reports`, `rag_eval_intent_annotations`, `rag_eval_config_versions`, `rag_eval_config_change_sets`, `rag_eval_config_change_set_prompts`, `rag_eval_tuning_suggestion_records`, `rag_eval_prompt_suggestion_records`, `rag_eval_ignored_suggestions`, `rag_eval_query_intent_logs`, `rag_eval_synonym_query_pairs`

### 保留并 ALTER（基础设施）

- **`source_documents`**：保留旧表 DDL，ALTER 新增 `file_hash`、`content_summary`、`page_count`、`status`、`updated_at` 字段。旧表已有 `id`、`title`、`file_type`、`file_path`、`created_at`。旧字段 `file_type` 和 `file_path` 保持不变，不修改 RAG 文档导入管道（`DocumentIngestionFacade`）对旧字段的依赖。
  - **ORM 位置**：现有 ORM 在 `models/document.py`（`class SourceDocument`），**保留不动**，仅在该文件中新增字段映射。不迁移到 `models/rag_eval/` 下。
  - **Schema 位置**：新 Schema `SourceDocumentRead`、`SourceDocumentUpload` 定义在 `schemas/rag_eval/source_document.py`，引用 `models/document.py` 的 ORM。
- **`llm_call_logs`**（监控基础设施，不动）
- **`prompt_versions`** + **`prompt_metadata`**（提示词管理，本次不改）
- **`config`** 表（系统配置，不动）

```sql
-- source_documents ALTER 增量（仅新增字段，不破坏旧结构）
ALTER TABLE `source_documents`
    ADD COLUMN `file_hash` VARCHAR(64) COMMENT 'SHA-256' AFTER `file_path`,
    ADD COLUMN `content_summary` TEXT AFTER `file_hash`,
    ADD COLUMN `page_count` INT AFTER `content_summary`,
    ADD COLUMN `status` VARCHAR(16) NOT NULL DEFAULT 'uploaded' COMMENT 'uploaded/parsing/ready/archived' AFTER `page_count`,
    ADD COLUMN `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER `status`,
    ADD INDEX `idx_status` (`status`),
    ADD INDEX `idx_file_hash` (`file_hash`);
```

### 暂不保留

`rag_eval_audit_logs`（用 Prometheus + 日志替代）、`ab_test_metrics`（暂不需要）
