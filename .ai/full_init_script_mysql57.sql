-- =============================================
-- 儿童发展评估系统 MySQL 5.7 完整初始化脚本
-- 基于 SQLAlchemy ORM 模型生成
-- 包含：数据库创建 + 所有业务表创建 + 索引
-- 直接执行即可完成全新环境数据库初始化
-- 注意：不使用外键约束，由应用层保证数据一致性
-- =============================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 1. 创建数据库
-- ----------------------------
CREATE DATABASE IF NOT EXISTS `child_dev_assessment_test`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `child_dev_assessment_test`;

-- ----------------------------
-- 2. 配置版本表
-- ----------------------------
DROP TABLE IF EXISTS `config_versions`;

CREATE TABLE `config_versions` (
                                   `id` varchar(64) NOT NULL COMMENT '版本ID (UUID)',
                                   `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                   `created_by` varchar(64) DEFAULT NULL COMMENT '创建人',
                                   `description` text DEFAULT NULL COMMENT '版本描述',
                                   `config_snapshot` json NOT NULL COMMENT '配置快照',
                                   `parent_version_id` varchar(64) DEFAULT NULL COMMENT '父版本ID',
                                   `is_factory_reset` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否出厂重置',
                                   PRIMARY KEY (`id`),
                                   KEY `idx_config_versions_created_at` (`created_at`),
                                   KEY `idx_config_versions_parent` (`parent_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置版本表';

-- ----------------------------
-- 3. 配置审计日志表
-- ----------------------------
DROP TABLE IF EXISTS `config_audit_log`;

CREATE TABLE `config_audit_log` (
                                    `id` int NOT NULL AUTO_INCREMENT COMMENT '自增主键',
                                    `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
                                    `action` enum('UPDATE','ROLLBACK','RESET') NOT NULL COMMENT '操作类型',
                                    `from_version` varchar(64) DEFAULT NULL COMMENT '源版本ID',
                                    `to_version` varchar(64) DEFAULT NULL COMMENT '目标版本ID',
                                    `user` varchar(64) DEFAULT NULL COMMENT '操作人',
                                    PRIMARY KEY (`id`),
                                    KEY `idx_audit_log_timestamp` (`timestamp`),
                                    KEY `idx_audit_log_action` (`action`),
                                    KEY `idx_audit_log_from_version` (`from_version`),
                                    KEY `idx_audit_log_to_version` (`to_version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置审计日志表';

-- ----------------------------
-- 4. 源文档表
-- ----------------------------
DROP TABLE IF EXISTS `source_documents`;

CREATE TABLE `source_documents` (
                                    `id` varchar(64) NOT NULL COMMENT '文档ID (UUID)',
                                    `title` varchar(500) NOT NULL COMMENT '文档标题',
                                    `author` varchar(200) DEFAULT NULL COMMENT '作者/编著者',
                                    `file_type` enum('pdf','epub','txt') NOT NULL COMMENT '文件类型',
                                    `source_type` enum('book','paper','guideline','manual') NOT NULL DEFAULT 'book' COMMENT '文献类型',
                                    `file_path` varchar(1000) NOT NULL COMMENT '文件路径',
                                    `file_hash` varchar(64) NOT NULL COMMENT '文件哈希 (SHA-256)',
                                    `content_summary` text DEFAULT NULL COMMENT '内容摘要',
                                    `page_count` int DEFAULT NULL COMMENT '页数',
                                    `chapter_count` int DEFAULT NULL COMMENT '章节数',
                                    `quality_score` decimal(3,2) DEFAULT NULL COMMENT '质量评分 (0-1)',
                                    `scan_page_ratio` decimal(3,2) DEFAULT NULL COMMENT '扫描页比例',
                                    `chapter_structure` json DEFAULT NULL COMMENT '章节结构',
                                    `quality_report` json DEFAULT NULL COMMENT '质量报告',
                                    `status` enum('uploaded','parsing','ready','archived') NOT NULL DEFAULT 'uploaded' COMMENT '文档状态',
                                    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                                    PRIMARY KEY (`id`),
                                    UNIQUE KEY `uk_source_docs_file_hash` (`file_hash`),
                                    KEY `idx_source_docs_title` (`title`),
                                    KEY `idx_source_docs_file_type` (`file_type`),
                                    KEY `idx_source_docs_status` (`status`),
                                    KEY `idx_source_docs_quality_score` (`quality_score`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='源文档表';

-- ----------------------------
-- 5. 文档导入记录表
-- ----------------------------
DROP TABLE IF EXISTS `document_records`;

CREATE TABLE `document_records` (
                                    `id` varchar(64) NOT NULL COMMENT '记录ID (UUID)',
                                    `file_hash` varchar(64) NOT NULL COMMENT '文件哈希',
                                    `file_name` varchar(500) NOT NULL COMMENT '文件名',
                                    `upload_date` datetime NOT NULL COMMENT '上传日期',
                                    `total_pages` int DEFAULT NULL COMMENT '总页数',
                                    `indexed_chunks` int NOT NULL DEFAULT 0 COMMENT '已索引分块数',
                                    `category` varchar(100) DEFAULT NULL COMMENT '分类',
                                    `metadata` json DEFAULT NULL COMMENT '元数据',
                                    `ref_doc_ids` json DEFAULT NULL COMMENT '关联文档ID列表',
                                    `status` enum('pending','processing','indexed','failed') NOT NULL DEFAULT 'pending' COMMENT '导入状态',
                                    `progress` int NOT NULL DEFAULT 0 COMMENT '导入进度 (0-100)',
                                    `graph_ready` tinyint(1) NOT NULL DEFAULT 0 COMMENT '知识图谱是否构建完成',
                                    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                                    PRIMARY KEY (`id`),
                                    KEY `idx_doc_records_file_hash` (`file_hash`),
                                    KEY `idx_doc_records_file_name` (`file_name`),
                                    KEY `idx_doc_records_upload_date` (`upload_date`),
                                    KEY `idx_doc_records_status` (`status`),
                                    KEY `idx_doc_records_indexed_chunks` (`indexed_chunks`),
                                    KEY `idx_doc_records_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档导入记录表';

-- ============================================================
-- RAG评估 v2 统一数据模型（6-12）
-- 废止旧 Legacy 7张表 + RagEval 16张表，统一为11张核心表
-- 使用 varchar(64) ID，统一命名无 rag_eval_ 前缀
-- ============================================================

-- ----------------------------
-- 6. 知识快照表
-- ----------------------------
DROP TABLE IF EXISTS `knowledge_snapshots`;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 7. 测试用例草稿表
-- ----------------------------
DROP TABLE IF EXISTS `test_case_drafts`;

CREATE TABLE `test_case_drafts` (
    `id` VARCHAR(64) PRIMARY KEY,
    `source_document_id` VARCHAR(64) COMMENT '来源文档 ID',
    `query` TEXT NOT NULL COMMENT '测试问题',
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
    INDEX `idx_batch_id` (`batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 8. 测试用例表
-- ----------------------------
DROP TABLE IF EXISTS `test_cases`;

CREATE TABLE `test_cases` (
    `id` VARCHAR(64) PRIMARY KEY,
    `query` TEXT NOT NULL COMMENT '测试问题',
    `description` TEXT COMMENT '期望答案描述',
    `expected_knowledge_ids` JSON COMMENT '期望检索的知识片段 ID 列表',
    `expected_keywords` JSON COMMENT '期望关键词列表',
    `answer_points_summary` TEXT COMMENT '答案要点摘要',
    `difficulty_level` VARCHAR(16) COMMENT 'easy/medium/hard',
    `professional_terms` JSON COMMENT '专业术语列表',
    `relevance_scores` JSON COMMENT '相关度评分',
    `book_ids` JSON DEFAULT NULL COMMENT '限定检索的书籍 file_hash 列表',
    `source` VARCHAR(16) NOT NULL DEFAULT 'manual' COMMENT 'manual/draft/import',
    `source_draft_id` VARCHAR(64) COMMENT '来源草稿 ID',
    `source_document_id` VARCHAR(64) COMMENT '来源文档 ID',
    `version` INT NOT NULL DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_source` (`source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 9. 测试集表
-- ----------------------------
DROP TABLE IF EXISTS `test_sets`;

CREATE TABLE `test_sets` (
    `id` VARCHAR(64) PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT,
    `source_type` VARCHAR(16) NOT NULL DEFAULT 'manual' COMMENT 'manual/json_import/book_generated/mixed',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 10. 测试集关联用例表
-- ----------------------------
DROP TABLE IF EXISTS `test_set_cases`;

CREATE TABLE `test_set_cases` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `test_set_id` VARCHAR(64) NOT NULL,
    `test_case_id` VARCHAR(64) NOT NULL,
    `added_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_set_case` (`test_set_id`, `test_case_id`),
    INDEX `idx_test_case_id` (`test_case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 11. 测试执行记录表
-- ----------------------------
DROP TABLE IF EXISTS `test_runs`;

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
    `task_id` VARCHAR(64) COMMENT '异步任务 ID，用于取消运行',
    `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed/cancelled',
    `total_test_cases` INT NOT NULL DEFAULT 0,
    `passed_test_cases` INT NOT NULL DEFAULT 0,
    `overall_precision` DECIMAL(5,4) COMMENT '整体精确率',
    `overall_recall` DECIMAL(5,4) COMMENT '整体召回率',
    `overall_f1` DECIMAL(5,4) COMMENT '整体F1',
    `overall_mrr` DECIMAL(5,4) COMMENT '整体MRR',
    `overall_ndcg` DECIMAL(5,4) COMMENT '整体NDCG',
    `l1_metrics_json` JSON COMMENT 'L1 检索质量指标',
    `l2_metrics_json` JSON COMMENT 'L2 生成质量指标',
    `l3_metrics_json` JSON COMMENT 'L3 系统质量指标',
    `overall_score` DECIMAL(5,4) COMMENT '加权综合得分',
    `diagnosis_json` JSON COMMENT '六层诊断结果',
    `started_at` DATETIME,
    `completed_at` DATETIME,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_status` (`status`),
    INDEX `idx_snapshot_id` (`snapshot_id`),
    INDEX `idx_config_version_id` (`config_version_id`),
    INDEX `idx_task_id` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 12. 测试执行结果表
-- ----------------------------
DROP TABLE IF EXISTS `test_run_results`;

CREATE TABLE `test_run_results` (
    `id` VARCHAR(64) PRIMARY KEY,
    `run_id` VARCHAR(64) NOT NULL,
    `test_case_id` VARCHAR(64) NOT NULL,
    `query` TEXT NOT NULL,
    `retrieved_doc_ids` JSON COMMENT '检索到的文档 ID 列表',
    `retrieved_contexts` JSON COMMENT '检索上下文文本列表',
    `relevant_doc_ids` JSON COMMENT '相关文档 ID 列表',
    `expected_knowledge_ids` JSON COMMENT '期望知识片段 ID',
    `actual_knowledge_ids` JSON COMMENT '实际匹配的知识片段 ID',
    `matched_count` INT DEFAULT 0,
    `expected_count` INT DEFAULT 0,
    `actual_count` INT DEFAULT 0,
    `precision` DECIMAL(5,4),
    `recall` DECIMAL(5,4),
    `f1` DECIMAL(5,4),
    `mrr` DECIMAL(5,4) DEFAULT 0,
    `ndcg` DECIMAL(5,4),
    `hit_rate_1` DECIMAL(5,4) DEFAULT 0,
    `hit_rate_3` DECIMAL(5,4) DEFAULT 0,
    `hit_rate_5` DECIMAL(5,4) DEFAULT 0,
    `actual_answer` TEXT COMMENT 'RAG 生成的实际答案',
    `l1_metrics_json` JSON COMMENT '单用例 L1 指标',
    `l2_metrics_json` JSON COMMENT '单用例 L2 指标',
    `diagnosis_json` JSON COMMENT '单用例诊断结果',
    `passed` TINYINT(1) COMMENT '是否通过',
    `error_message` TEXT,
    `execution_time_ms` INT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_run_id` (`run_id`),
    INDEX `idx_test_case_id` (`test_case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 13. A/B测试指标表
-- ----------------------------
DROP TABLE IF EXISTS `ab_test_metrics`;

CREATE TABLE `ab_test_metrics` (
                                   `id` int NOT NULL AUTO_INCREMENT COMMENT '自增主键',
                                   `test_name` varchar(255) NOT NULL COMMENT '测试名称',
                                   `variant_name` varchar(255) NOT NULL COMMENT '变体名称',
                                   `metric_value` decimal(10,4) NOT NULL COMMENT '指标值',
                                   `metric_type` varchar(100) NOT NULL COMMENT '指标类型',
                                   `recorded_at` datetime NOT NULL COMMENT '记录时间',
                                   PRIMARY KEY (`id`),
                                   KEY `idx_ab_metrics_test_name` (`test_name`),
                                   KEY `idx_ab_metrics_variant_name` (`variant_name`),
                                   KEY `idx_ab_metrics_recorded_at` (`recorded_at`),
                                   KEY `idx_ab_metrics_test_variant` (`test_name`, `variant_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='A/B测试指标表';

-- ----------------------------
-- 14. LLM调用日志表
-- ----------------------------
DROP TABLE IF EXISTS `llm_call_logs`;

CREATE TABLE `llm_call_logs` (
                                 `id` int NOT NULL AUTO_INCREMENT COMMENT '自增主键',
                                 `request_id` varchar(64) NOT NULL COMMENT '请求ID',
                                 `prompt_key` varchar(255) DEFAULT NULL COMMENT '提示词键',
                                 `prompt_version` varchar(64) DEFAULT NULL COMMENT '提示词版本',
                                 `scenario` varchar(100) DEFAULT NULL COMMENT '使用场景',
                                 `model_name` varchar(255) NOT NULL COMMENT '模型名称',
                                 `input_tokens` int DEFAULT NULL COMMENT '输入Token数',
                                 `output_tokens` int DEFAULT NULL COMMENT '输出Token数',
                                 `total_tokens` int DEFAULT NULL COMMENT '总Token数',
                                 `duration_ms` int DEFAULT NULL COMMENT '耗时 (毫秒)',
                                 `status` enum('success','failed','timeout') NOT NULL COMMENT '调用状态',
                                 `error_message` text DEFAULT NULL COMMENT '错误信息',
                                 `trace_id` varchar(64) DEFAULT NULL COMMENT 'Trace ID',
                                 `span_id` varchar(64) DEFAULT NULL COMMENT 'Span ID',
                                  `parent_span_id` varchar(64) DEFAULT NULL COMMENT '父 Span ID',
                                  `prompt_messages` json DEFAULT NULL COMMENT '提示词消息',
                                  `completion_message` text DEFAULT NULL COMMENT '完成消息',
                                  `full_prompt_path` varchar(512) DEFAULT NULL COMMENT '完整提示词文件路径',
                                  `full_completion_path` varchar(512) DEFAULT NULL COMMENT '完整完成内容文件路径',
                                  `call_parameters` json DEFAULT NULL COMMENT '调用参数',
                                  `model_parameters` json DEFAULT NULL COMMENT '模型参数',
                                  `cost` decimal(10,4) DEFAULT NULL COMMENT '调用成本',
                                  `tags` json DEFAULT NULL COMMENT '标签列表',
                                  `tokens` int DEFAULT NULL COMMENT 'Token 总数',
                                 `completion_start_time_ms` int DEFAULT NULL COMMENT '完成开始时间 (毫秒)',
                                 `level` enum('DEBUG','INFO','WARNING','ERROR') DEFAULT 'INFO' COMMENT '日志级别',
                                 `user_id` varchar(64) DEFAULT NULL COMMENT '用户 ID',
                                 `session_id` varchar(64) DEFAULT NULL COMMENT '会话 ID',
                                 `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                 PRIMARY KEY (`id`),
                                 KEY `idx_llm_logs_request_id` (`request_id`),
                                 KEY `idx_llm_logs_prompt_key` (`prompt_key`),
                                 KEY `idx_llm_logs_scenario` (`scenario`),
                                 KEY `idx_llm_logs_model_name` (`model_name`),
                                 KEY `idx_llm_logs_duration_ms` (`duration_ms`),
                                 KEY `idx_llm_logs_status` (`status`),
                                 KEY `idx_llm_logs_created_at` (`created_at`),
                                 KEY `idx_llm_trace_id` (`trace_id`),
                                 UNIQUE KEY `uk_llm_span_id` (`span_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='LLM 调用日志表';

-- ----------------------------
-- 15. 提示词元数据表
-- ----------------------------
DROP TABLE IF EXISTS `prompt_metadata`;

CREATE TABLE `prompt_metadata` (
    `id` varchar(36) NOT NULL COMMENT '主键UUID',
    `prompt_key` varchar(255) NOT NULL COMMENT '提示词唯一标识key',
    `name_zh` varchar(255) NOT NULL COMMENT '中文名称',
    `purpose` text NOT NULL COMMENT '用途说明',
    `category` varchar(64) NOT NULL COMMENT '分类',
    `subcategory` varchar(64) DEFAULT NULL COMMENT '子分类',
    `variables_schema` json DEFAULT NULL COMMENT '变量声明 schema',
    `code_references` json DEFAULT NULL COMMENT '代码引用位置',
    `config_dependencies` json DEFAULT NULL COMMENT '配置参数依赖',
    `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
    `is_system` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否系统内置',
    `created_by` varchar(64) DEFAULT NULL COMMENT '创建人',
    `updated_by` varchar(64) DEFAULT NULL COMMENT '更新人',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_prompt_key` (`prompt_key`),
    KEY `idx_prompt_category_active` (`category`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词元数据表';

-- ----------------------------
-- 16. 提示词版本表
-- ----------------------------
DROP TABLE IF EXISTS `prompt_versions`;

CREATE TABLE `prompt_versions` (
    `id` varchar(36) NOT NULL COMMENT '主键UUID',
    `prompt_key` varchar(255) NOT NULL COMMENT '提示词唯一标识key',
    `version_label` varchar(36) NOT NULL COMMENT '展示用版本号',
    `version_number` int NOT NULL COMMENT '该 prompt_key 下的自增序号',
    `content` text NOT NULL COMMENT '提示词完整内容',
    `content_hash` varchar(64) NOT NULL COMMENT '内容 SHA256 哈希',
    `variables_extracted` json DEFAULT NULL COMMENT '自动提取的变量列表',
    `change_impact` json DEFAULT NULL COMMENT '变更影响分析',
    `change_summary` text DEFAULT NULL COMMENT '变更摘要',
    `tags` json DEFAULT NULL COMMENT '标签列表',
    `fallback` text DEFAULT NULL COMMENT '降级备用内容',
    `created_by` varchar(36) DEFAULT NULL COMMENT '创建人用户ID',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_prompt_key_version` (`prompt_key`, `version_label`),
    KEY `idx_prompt_key_content_hash` (`content_hash`),
    KEY `idx_prompt_key_created` (`prompt_key`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词版本表';

-- ----------------------------
-- 17. 提示词A/B测试表
-- ----------------------------
DROP TABLE IF EXISTS `prompt_ab_tests`;

CREATE TABLE `prompt_ab_tests` (
    `id` varchar(64) NOT NULL COMMENT 'A/B测试ID (UUID)',
    `prompt_key` varchar(255) NOT NULL COMMENT '提示词键',
    `name` varchar(255) NOT NULL COMMENT '测试名称',
    `is_active` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否激活',
    `variant_a_version` varchar(64) NOT NULL COMMENT '变体A版本',
    `variant_b_version` varchar(64) NOT NULL COMMENT '变体B版本',
    `variant_a_ratio` float NOT NULL DEFAULT 0.5 COMMENT '变体A流量比例',
    `started_at` datetime DEFAULT NULL COMMENT '开始时间',
    `ended_at` datetime DEFAULT NULL COMMENT '结束时间',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_prompt_ab_tests_prompt_key` (`prompt_key`),
    KEY `idx_prompt_ab_tests_is_active` (`is_active`),
    KEY `idx_prompt_ab_test_prompt_active` (`prompt_key`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词A/B测试表';

-- ============================================================
-- RAG评估 v2 报告与配置（18-21）
-- 统一命名，无 rag_eval_ 前缀，varchar(64) ID
-- ============================================================

-- ----------------------------
-- 18. 评估报告表
-- ----------------------------
DROP TABLE IF EXISTS `eval_reports`;

CREATE TABLE `eval_reports` (
    `id` VARCHAR(64) PRIMARY KEY,
    `run_id` VARCHAR(64) NOT NULL,
    `test_set_id` VARCHAR(64) COMMENT '主测试集 ID',
    `config_version_id` VARCHAR(64) COMMENT '配置版本 ID',
    `overall_score` DECIMAL(5,4) COMMENT '三层加权综合得分',
    `l1_score` DECIMAL(5,4) COMMENT 'L1 层得分',
    `l2_score` DECIMAL(5,4) COMMENT 'L2 层得分',
    `l3_score` DECIMAL(5,4) COMMENT 'L3 层得分',
    `precision` DECIMAL(5,4),
    `recall` DECIMAL(5,4),
    `f1` DECIMAL(5,4),
    `mrr` DECIMAL(5,4),
    `ndcg` DECIMAL(5,4),
    `metrics_json` JSON NOT NULL COMMENT '三层指标 RunMetrics JSON',
    `diagnosis_json` JSON COMMENT '六层诊断结果 JSON',
    `bad_cases_json` JSON COMMENT '坏案列表 JSON',
    `suggestions_json` JSON COMMENT '调优建议列表 JSON',
    `markdown_content` LONGTEXT COMMENT 'Markdown 报告内容',
    `status` VARCHAR(16) NOT NULL DEFAULT 'processing' COMMENT 'processing/completed/superseded',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_run_id` (`run_id`),
    INDEX `idx_test_set_id` (`test_set_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 19. 调优建议表
-- ----------------------------
DROP TABLE IF EXISTS `tuning_suggestions`;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 20. RAG评估配置版本表
-- ----------------------------
DROP TABLE IF EXISTS `eval_config_versions`;

CREATE TABLE `eval_config_versions` (
    `id` VARCHAR(64) PRIMARY KEY,
    `version_number` INT NOT NULL DEFAULT 1,
    `version_label` VARCHAR(100) COMMENT '版本标签',
    `config_snapshot` JSON NOT NULL COMMENT '完整配置快照',
    `change_summary` TEXT COMMENT '变更摘要',
    `created_by` VARCHAR(64) COMMENT '创建者',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 21. RAG评估配置变更集表
-- ----------------------------
DROP TABLE IF EXISTS `eval_config_change_sets`;

CREATE TABLE `eval_config_change_sets` (
    `id` VARCHAR(64) PRIMARY KEY,
    `change_set_label` VARCHAR(255) NOT NULL COMMENT '变更集标签',
    `config_version_id` VARCHAR(64) NOT NULL COMMENT '目标配置版本',
    `status` VARCHAR(16) NOT NULL DEFAULT 'committed' COMMENT 'committed/rolled_back',
    `rollback_reason` TEXT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `rolled_back_at` DATETIME,
    INDEX `idx_config_version_id` (`config_version_id`),
    INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 22. Trace 跟踪表（保留）
-- ----------------------------
DROP TABLE IF EXISTS `traces`;

CREATE TABLE `traces` (
    `trace_id` VARCHAR(64) NOT NULL COMMENT 'Trace ID (UUID)',
    `name` VARCHAR(255) NOT NULL COMMENT 'Trace 名称',
    `user_id` VARCHAR(64) DEFAULT NULL COMMENT '用户ID',
    `session_id` VARCHAR(64) DEFAULT NULL COMMENT '会话ID',
    `metadata` JSON DEFAULT NULL COMMENT '元数据',
    `start_time` DATETIME NOT NULL COMMENT '开始时间',
    `end_time` DATETIME DEFAULT NULL COMMENT '结束时间',
    `total_duration_ms` INT NOT NULL DEFAULT 0 COMMENT '总耗时（毫秒）',
    `total_tokens` INT NOT NULL DEFAULT 0 COMMENT '总Token数',
    `total_cost` DECIMAL(10,4) NOT NULL DEFAULT 0.0000 COMMENT '总成本',
    `status` ENUM('success','failed','partial') NOT NULL COMMENT '执行状态',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`trace_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_trace_status` (`status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Trace 跟踪表';

-- ----------------------------
-- 23-25. 知识图谱表（LazyGraphRAG）
-- ----------------------------

-- 23. 知识图谱实体表
DROP TABLE IF EXISTS `graph_entities`;

CREATE TABLE graph_entities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL COMMENT '实体名称',
    entity_type ENUM('development_concept','symptom_behavior','intervention_method',
                     'assessment_tool','brain_region','age_milestone','clinical_population') NOT NULL COMMENT '实体类型',
    description TEXT COMMENT '实体描述',
    aliases JSON COMMENT '别名列表 ["别名1", "别名2"]',
    book_id VARCHAR(64) NOT NULL COMMENT '所属书籍ID(UUID)',
    chunk_ids JSON COMMENT '关联块ID列表 [101, 102, 103]',
    embedding JSON COMMENT '可选，跨书实体去重用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_graph_entity_book (book_id),
    INDEX idx_graph_entity_type (entity_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识图谱实体表';

-- 24. 知识图谱关系表
DROP TABLE IF EXISTS `graph_relations`;

CREATE TABLE graph_relations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_entity_id INT NOT NULL COMMENT '源实体ID',
    target_entity_id INT NOT NULL COMMENT '目标实体ID',
    relation_type ENUM('causes','treats','assesses','related_to','contraindicates','develops_at') NOT NULL COMMENT '关系类型',
    description TEXT COMMENT '关系描述',
    confidence FLOAT DEFAULT 1.0 COMMENT '置信度 0-1',
    book_id VARCHAR(64) NOT NULL COMMENT '所属书籍ID(UUID)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_graph_rel_source (source_entity_id),
    INDEX idx_graph_rel_target (target_entity_id),
    INDEX idx_graph_rel_type (relation_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识图谱关系表';

-- 25. 层级社区树表
DROP TABLE IF EXISTS `graph_community_tree`;

CREATE TABLE graph_community_tree (
    node_id VARCHAR(64) PRIMARY KEY COMMENT '社区节点ID',
    parent_id VARCHAR(64) COMMENT '父节点ID',
    level INT NOT NULL DEFAULT 0 COMMENT '层级深度',
    scope ENUM('book','global') NOT NULL DEFAULT 'book' COMMENT '作用域',
    book_id VARCHAR(64) COMMENT 'scope=book 时非空(UUID)',
    label VARCHAR(500) COMMENT '社区标签（实体名摘要）',
    entity_names JSON COMMENT '社区内实体名列表',
    chunk_ids JSON COMMENT '叶子节点关联的块ID列表',
    is_leaf BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否叶子节点',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_comm_parent (parent_id),
    INDEX idx_comm_scope_level (scope, level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='层级社区树表';



-- ----------------------------
-- Table structure for knowledge_qa_history
-- 知识问答历史记录
-- ----------------------------
DROP TABLE IF EXISTS `knowledge_qa_history`;
CREATE TABLE `knowledge_qa_history` (
    id VARCHAR(64) NOT NULL COMMENT '记录ID (UUID)',
    task_id VARCHAR(64) NOT NULL COMMENT '任务ID',
    question TEXT NOT NULL COMMENT '用户问题',
    status VARCHAR(20) NOT NULL DEFAULT 'completed' COMMENT '状态: completed/partial/cancelled/timeout/error',
    result_json JSON NOT NULL COMMENT '完整的问答结果',
    matched_books_json JSON COMMENT '匹配到的书籍列表',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_task_id (task_id),
    INDEX idx_created_at (created_at),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识问答历史记录';

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- 初始化完成
-- ----------------------------
SELECT '数据库初始化完成，共创建25张业务表（基础4张 + RAG评估v2 11张 + 监控3张 + 提示词3张 + 知识图谱3张 + 知识问答历史1张）' AS result;