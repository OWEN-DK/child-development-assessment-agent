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
CREATE DATABASE IF NOT EXISTS `child_dev_assessment_dev`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `child_dev_assessment_dev`;

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
                                    `file_type` enum('pdf','epub','txt') NOT NULL COMMENT '文件类型',
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

-- ----------------------------
-- 6. 知识快照表
-- ----------------------------
DROP TABLE IF EXISTS `knowledge_snapshots`;

CREATE TABLE `knowledge_snapshots` (
                                       `id` varchar(64) NOT NULL COMMENT '快照ID (UUID)',
                                       `name` varchar(255) NOT NULL COMMENT '快照名称',
                                       `description` text DEFAULT NULL COMMENT '快照描述',
                                       `vector_store_path` varchar(512) NOT NULL COMMENT '向量存储路径',
                                       `document_count` int NOT NULL DEFAULT 0 COMMENT '文档数量',
                                       `chunk_count` int NOT NULL DEFAULT 0 COMMENT '分块数量',
                                       `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                       PRIMARY KEY (`id`),
                                       KEY `idx_knowledge_snapshots_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识快照表';

-- ----------------------------
-- 7. 测试用例表
-- ----------------------------

DROP TABLE IF EXISTS `test_cases`;

CREATE TABLE `test_cases` (
                              `id` varchar(64) NOT NULL COMMENT '用例ID (UUID)',
                              `query` text NOT NULL COMMENT '查询内容',
                              `age` decimal(4,1) NOT NULL COMMENT '适用年龄 (月)',
                              `domain` enum('gross_motor','fine_motor','language','cognitive','social_emotional','sensory_integration') NOT NULL COMMENT '发展领域',
                              `description` text DEFAULT NULL COMMENT '用例描述',
                              `expected_knowledge_count` int NOT NULL DEFAULT 0 COMMENT '期望知识数量',
                              `answer_points_summary` text DEFAULT NULL COMMENT '答案要点摘要',
                              `min_age_requirement` decimal(4,1) DEFAULT NULL COMMENT '最小年龄要求',
                              `max_age_requirement` decimal(4,1) DEFAULT NULL COMMENT '最大年龄要求',
                              `difficulty_level` enum('easy','medium','hard') DEFAULT NULL COMMENT '难度等级',
                              `expected_knowledge_ids` json DEFAULT NULL COMMENT '期望知识ID列表',
                              `expected_keywords` json DEFAULT NULL COMMENT '期望关键词列表',
                              `professional_terms` json DEFAULT NULL COMMENT '专业术语列表',
                              `relevance_scores` json DEFAULT NULL COMMENT '相关性分数',
                              `source_document_id` varchar(64) DEFAULT NULL COMMENT '源文档ID',
                              `version` int NOT NULL DEFAULT 1 COMMENT '版本号',
                              `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                              `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                              PRIMARY KEY (`id`),
                              KEY `idx_test_cases_domain` (`domain`),
                              KEY `idx_test_cases_age` (`age`),
                              KEY `idx_test_cases_difficulty` (`difficulty_level`),
                              KEY `idx_test_cases_age_range` (`min_age_requirement`, `max_age_requirement`),
                              KEY `idx_test_cases_source_doc` (`source_document_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试用例表';

-- ----------------------------
-- 8. 测试用例草稿表
-- ----------------------------
DROP TABLE IF EXISTS `test_case_drafts`;

CREATE TABLE `test_case_drafts` (
                                    `id` varchar(64) NOT NULL COMMENT '草稿ID (UUID)',
                                    `source_document_id` varchar(64) NOT NULL COMMENT '源文档ID',
                                    `query` text NOT NULL COMMENT '查询内容',
                                    `age` decimal(4,1) NOT NULL COMMENT '适用年龄 (月)',
                                    `domain` enum('gross_motor','fine_motor','language','cognitive','social_emotional','sensory_integration') NOT NULL COMMENT '发展领域',
                                    `description` text DEFAULT NULL COMMENT '草稿描述',
                                    `generation_batch_id` varchar(64) DEFAULT NULL COMMENT '生成批次ID',
                                    `expected_knowledge_ids` json DEFAULT NULL COMMENT '期望知识ID列表',
                                    `expected_keywords` json DEFAULT NULL COMMENT '期望关键词列表',
                                    `answer_points` json DEFAULT NULL COMMENT '答案要点',
                                    `professional_terms` json DEFAULT NULL COMMENT '专业术语列表',
                                    `age_requirement` json DEFAULT NULL COMMENT '年龄要求',
                                    `generation_params` json DEFAULT NULL COMMENT '生成参数',
                                    `status` enum('draft','reviewed','rejected','imported') NOT NULL DEFAULT 'draft' COMMENT '草稿状态',
                                    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                                    PRIMARY KEY (`id`),
                                    KEY `idx_drafts_source_doc` (`source_document_id`),
                                    KEY `idx_drafts_domain_status` (`domain`, `status`),
                                    KEY `idx_drafts_created_at` (`created_at`),
                                    KEY `idx_generation_batch` (`generation_batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试用例草稿表';

-- ----------------------------
-- 9. 测试集表
-- ----------------------------
DROP TABLE IF EXISTS `test_sets`;

CREATE TABLE `test_sets` (
                             `id` varchar(64) NOT NULL COMMENT '测试集ID (UUID)',
                             `name` varchar(255) NOT NULL COMMENT '测试集名称',
                             `description` text DEFAULT NULL COMMENT '测试集描述',
                             `source_type` enum('manual','json_import','book_generated','mixed') NOT NULL COMMENT '来源类型',
                             `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                             `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                             PRIMARY KEY (`id`),
                             KEY `idx_test_sets_name` (`name`),
                             KEY `idx_test_sets_source_type` (`source_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试集表';

-- ----------------------------
-- 10. 测试集关联用例表
-- ----------------------------
DROP TABLE IF EXISTS `test_set_cases`;

CREATE TABLE `test_set_cases` (
                                  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增主键',
                                  `test_set_id` varchar(64) NOT NULL COMMENT '测试集ID',
                                  `test_case_id` varchar(64) NOT NULL COMMENT '测试用例ID',
                                  `added_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '添加时间',
                                  PRIMARY KEY (`id`),
                                  KEY `idx_test_set_cases_set_id` (`test_set_id`),
                                  KEY `idx_test_set_cases_case_id` (`test_case_id`),
                                  UNIQUE KEY `uk_test_set_cases` (`test_set_id`, `test_case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试集关联用例表';

-- ----------------------------
-- 11. 测试执行记录表
-- ----------------------------
DROP TABLE IF EXISTS `test_runs`;

CREATE TABLE `test_runs` (
                             `id` varchar(64) NOT NULL COMMENT '执行ID (UUID)',
                             `name` varchar(255) NOT NULL COMMENT '执行名称',
                             `description` text DEFAULT NULL COMMENT '执行描述',
                             `overall_precision` decimal(5,4) DEFAULT NULL COMMENT '整体精确率',
                             `overall_recall` decimal(5,4) DEFAULT NULL COMMENT '整体召回率',
                             `overall_f1` decimal(5,4) DEFAULT NULL COMMENT '整体F1分数',
                             `overall_mrr` decimal(5,4) DEFAULT NULL COMMENT '整体MRR',
                             `overall_ndcg` decimal(5,4) DEFAULT NULL COMMENT '整体NDCG',
                             `total_test_cases` int NOT NULL COMMENT '总用例数',
                             `passed_test_cases` int NOT NULL COMMENT '通过用例数',
                             `test_set_ids` json NOT NULL COMMENT '测试集ID列表',
                             `custom_case_ids` json DEFAULT NULL COMMENT '自定义用例ID列表',
                             `report_export_format` enum('markdown','pdf','json') DEFAULT 'markdown' COMMENT '报告导出格式',
                             `report_storage_path` varchar(512) DEFAULT NULL COMMENT '报告存储路径',
                             `status` enum('running','completed','failed','cancelled') NOT NULL COMMENT '执行状态',
                             `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                             `started_at` datetime DEFAULT NULL COMMENT '开始时间',
                             `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
                             `created_by` int DEFAULT NULL COMMENT '创建人用户ID',
                             `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                             `snapshot_id` varchar(64) DEFAULT NULL COMMENT '知识快照ID',
                             `config_version_id` varchar(64) DEFAULT NULL COMMENT '配置版本ID',
                             `config_snapshot` json DEFAULT NULL COMMENT '配置快照',
                             `previous_config_version_id` varchar(64) DEFAULT NULL COMMENT '上一配置版本ID',
                             PRIMARY KEY (`id`),
                             KEY `idx_test_runs_status` (`status`),
                             KEY `idx_test_runs_created_at` (`created_at`),
                             KEY `idx_test_runs_config_version` (`config_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试执行记录表';

-- ----------------------------
-- 12. 测试执行结果表
-- ----------------------------
DROP TABLE IF EXISTS `test_run_results`;

CREATE TABLE `test_run_results` (
                                    `id` int NOT NULL AUTO_INCREMENT COMMENT '自增主键',
                                    `run_id` varchar(64) NOT NULL COMMENT '执行ID',
                                    `test_case_id` varchar(64) NOT NULL COMMENT '测试用例ID',
                                    `query` text NOT NULL COMMENT '查询内容',
                                    `precision` decimal(5,4) DEFAULT NULL COMMENT '精确率',
                                    `recall` decimal(5,4) DEFAULT NULL COMMENT '召回率',
                                    `f1` decimal(5,4) DEFAULT NULL COMMENT 'F1分数',
                                    `mrr` decimal(10,4) NOT NULL DEFAULT 0.0000 COMMENT '平均倒数排名',
                                    `ndcg` decimal(10,4) DEFAULT NULL COMMENT '归一化折损累计增益',
                                    `hit_rate_1` decimal(10,4) NOT NULL DEFAULT 0.0000 COMMENT '命中率@1',
                                    `hit_rate_3` decimal(10,4) NOT NULL DEFAULT 0.0000 COMMENT '命中率@3',
                                    `hit_rate_5` decimal(10,4) NOT NULL DEFAULT 0.0000 COMMENT '命中率@5',
                                    `passed` tinyint(1) DEFAULT NULL COMMENT '是否通过',
                                    `matched_count` int NOT NULL DEFAULT 0 COMMENT '匹配数量',
                                    `expected_count` int NOT NULL DEFAULT 0 COMMENT '期望数量',
                                    `actual_count` int NOT NULL DEFAULT 0 COMMENT '实际数量',
                                    `expected_knowledge_ids` json DEFAULT NULL COMMENT '期望知识ID列表',
                                    `actual_knowledge_ids` json DEFAULT NULL COMMENT '实际知识ID列表',
                                    `retrieved_doc_ids` json NOT NULL COMMENT '检索到的文档ID列表',
                                    `relevant_doc_ids` json NOT NULL COMMENT '相关文档ID列表',
                                    `error_message` text DEFAULT NULL COMMENT '错误信息',
                                    `execution_time_ms` int DEFAULT NULL COMMENT '执行时间 (毫秒)',
                                    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                    PRIMARY KEY (`id`),
                                    KEY `idx_run_results_run_id` (`run_id`),
                                    KEY `idx_run_results_case_id` (`test_case_id`),
                                    KEY `idx_run_results_passed` (`passed`),
                                    KEY `idx_run_results_matched_count` (`matched_count`),
                                    KEY `idx_run_results_execution_time` (`execution_time_ms`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试执行结果表';

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
                                 `completion_message` text DEFAULT NULL COMMENT '完成消息',
                                 `full_prompt_path` varchar(512) DEFAULT NULL COMMENT '完整提示词文件路径',
                                 `full_completion_path` varchar(512) DEFAULT NULL COMMENT '完整完成内容文件路径',
                                 `cost` decimal(10,4) DEFAULT NULL COMMENT '调用成本',
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
-- 15. 提示词版本表
-- ----------------------------
DROP TABLE IF EXISTS `prompt_versions`;

CREATE TABLE `prompt_versions` (
                                   `id` varchar(64) NOT NULL COMMENT '版本ID (UUID)',
                                   `prompt_key` varchar(255) NOT NULL COMMENT '提示词键',
                                   `version` varchar(64) NOT NULL COMMENT '版本号',
                                   `content` text NOT NULL COMMENT '提示词内容',
                                   `content_hash` varchar(64) NOT NULL COMMENT '内容哈希',
                                   `description` text DEFAULT NULL COMMENT '版本描述',
                                   `created_by` varchar(64) DEFAULT NULL COMMENT '创建人',
                                   `variables` json DEFAULT NULL COMMENT '变量列表',
                                   `tags` json DEFAULT NULL COMMENT '标签列表',
                                   `fallback` text DEFAULT NULL COMMENT '降级内容',
                                   `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                   PRIMARY KEY (`id`),
                                   KEY `idx_prompt_versions_prompt_key` (`prompt_key`),
                                   KEY `idx_prompt_versions_content_hash` (`content_hash`),
                                   UNIQUE KEY `uk_prompt_key_version` (`prompt_key`, `version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词版本表';

-- ----------------------------
-- 16. 提示词A/B测试表
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
-- RAG 评估系统新增表 (Phase 1: 数据模型创建)
-- 18 张 rag_eval_* 表，统一使用 varchar(36) UUID 主键
-- 不使用外键约束，由应用层保证数据一致性
-- ============================================================

-- ----------------------------
-- 17. RAG评估测试集表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_test_sets`;

CREATE TABLE `rag_eval_test_sets` (
                                      `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                      `name` varchar(255) NOT NULL COMMENT '测试集名称',
                                      `description` text DEFAULT NULL COMMENT '测试集描述',
                                      `source_type` enum('book_generated','json_imported','manual') NOT NULL COMMENT '来源类型',
                                      `source_document_id` varchar(36) DEFAULT NULL COMMENT '关联的源文档ID',
                                      `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                      `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                                      PRIMARY KEY (`id`),
                                      KEY `idx_rag_eval_test_set_created_at` (`created_at`),
                                      KEY `idx_rag_eval_test_set_source_doc` (`source_document_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAG评估测试集表';

-- ----------------------------
-- 18. RAG配置版本表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_config_versions`;

CREATE TABLE `rag_eval_config_versions` (
                                            `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                            `version_number` int NOT NULL COMMENT '自增序号，系统自动维护',
                                            `version_label` varchar(32) NOT NULL COMMENT '展示用语义版本号，如 v2.3',
                                            `config_snapshot` json NOT NULL COMMENT '完整配置快照',
                                            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                            `created_by` varchar(36) DEFAULT NULL COMMENT '创建人用户ID',
                                            `change_summary` text DEFAULT NULL COMMENT '变更摘要',
                                            PRIMARY KEY (`id`),
                                            KEY `idx_rag_eval_config_version_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAG配置版本表';

-- ----------------------------
-- 19. 提示词元数据表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_prompt_metadata`;

CREATE TABLE `rag_eval_prompt_metadata` (
                                            `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                            `prompt_key` varchar(255) NOT NULL COMMENT '提示词唯一标识key',
                                            `name_zh` varchar(255) NOT NULL COMMENT '中文名称',
                                            `purpose` text DEFAULT NULL COMMENT '用途说明',
                                            `category` varchar(64) NOT NULL COMMENT '分类',
                                            `subcategory` varchar(64) DEFAULT NULL COMMENT '子分类',
                                            `variables_schema` json DEFAULT NULL COMMENT '变量声明schema',
                                            `code_references` json DEFAULT NULL COMMENT '代码引用位置',
                                            `config_dependencies` json DEFAULT NULL COMMENT '配置参数依赖',
                                            `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
                                            `is_system` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否系统内置',
                                            `created_by` varchar(36) DEFAULT NULL COMMENT '创建人',
                                            `updated_by` varchar(36) DEFAULT NULL COMMENT '更新人',
                                            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                            `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                                            PRIMARY KEY (`id`),
                                            UNIQUE KEY `uk_rag_eval_prompt_metadata_key` (`prompt_key`),
                                            KEY `idx_rag_eval_prompt_metadata_category_active` (`category`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词元数据表';

-- ----------------------------
-- 20. 提示词版本表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_prompt_versions`;

CREATE TABLE `rag_eval_prompt_versions` (
                                            `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                            `prompt_key` varchar(255) NOT NULL COMMENT '提示词唯一标识key',
                                            `version_label` varchar(64) NOT NULL COMMENT '展示用版本号',
                                            `version_number` int NOT NULL COMMENT '该prompt_key下的自增序号',
                                            `content` text NOT NULL COMMENT '提示词完整内容',
                                            `variables_extracted` json DEFAULT NULL COMMENT '自动提取的变量列表',
                                            `change_impact` json DEFAULT NULL COMMENT '变更影响分析',
                                            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                            `created_by` varchar(36) DEFAULT NULL COMMENT '创建人用户ID',
                                            `change_summary` text DEFAULT NULL COMMENT '变更摘要',
                                            PRIMARY KEY (`id`),
                                            UNIQUE KEY `uk_rag_eval_prompt_key_version` (`prompt_key`, `version_label`),
                                            KEY `idx_rag_eval_prompt_key_created` (`prompt_key`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词版本表';

-- ----------------------------
-- 21. 测试用例草稿表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_test_case_drafts`;

CREATE TABLE `rag_eval_test_case_drafts` (
                                             `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                             `source_document_id` varchar(36) NOT NULL COMMENT '源文档ID',
                                             `query` text NOT NULL COMMENT '测试查询内容',
                                             `age_months` int DEFAULT NULL COMMENT '适用儿童月龄',
                                             `domain` enum('gross_motor','fine_motor','language','cognitive','social_emotional','sensory_integration') NOT NULL COMMENT '发展领域',
                                             `expected_key_points` json DEFAULT NULL COMMENT '期望知识点列表',
                                             `status` enum('draft','reviewed','rejected','imported') NOT NULL DEFAULT 'draft' COMMENT '草稿状态',
                                             `reviewed_by` varchar(36) DEFAULT NULL COMMENT '审核人ID',
                                             `reviewed_at` datetime DEFAULT NULL COMMENT '审核时间',
                                             `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                             PRIMARY KEY (`id`),
                                             KEY `idx_rag_eval_test_case_draft_doc_status` (`source_document_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试用例草稿表';

-- ----------------------------
-- 22. RAG评估测试用例表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_test_cases`;

CREATE TABLE `rag_eval_test_cases` (
                                       `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                       `query` text NOT NULL COMMENT '测试查询内容',
                                       `age_months` int DEFAULT NULL COMMENT '适用儿童月龄',
                                       `domain` enum('gross_motor','fine_motor','language','cognitive','social_emotional','sensory_integration') NOT NULL COMMENT '发展领域',
                                       `expected_document_ids` json DEFAULT NULL COMMENT '期望命中的文档ID列表',
                                       `expected_key_points` json DEFAULT NULL COMMENT '期望知识点列表',
                                       `source_draft_id` varchar(36) DEFAULT NULL COMMENT '来源草稿ID',
                                       `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                       PRIMARY KEY (`id`),
                                       KEY `idx_rag_eval_test_case_domain_age` (`domain`, `age_months`),
                                       KEY `idx_rag_eval_test_case_source_draft` (`source_draft_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAG评估测试用例表';

-- ----------------------------
-- 23. 测试集-测试用例关联表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_test_set_cases`;

CREATE TABLE `rag_eval_test_set_cases` (
                                           `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                           `test_set_id` varchar(36) NOT NULL COMMENT '测试集ID',
                                           `case_id` varchar(36) NOT NULL COMMENT '测试用例ID',
                                           `added_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '添加时间',
                                           `added_by` varchar(36) DEFAULT NULL COMMENT '添加用例的用户ID',
                                           PRIMARY KEY (`id`),
                                           UNIQUE KEY `uk_rag_eval_test_set_case` (`test_set_id`, `case_id`),
                                           KEY `idx_rag_eval_test_set_case_test_set` (`test_set_id`),
                                           KEY `idx_rag_eval_test_set_case_case` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试集-测试用例关联表';

-- ----------------------------
-- 24. RAG评估测试运行记录表
-- ----------------------------

DROP TABLE IF EXISTS `rag_eval_test_runs`;
CREATE TABLE `rag_eval_test_runs` (
                                      `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                      `name` varchar(255) NOT NULL COMMENT '运行名称',
                                      `status` enum('pending','running','completed','failed','cancelled') NOT NULL DEFAULT 'pending' COMMENT '运行状态',
                                      `test_set_id` varchar(36) NOT NULL COMMENT '测试集ID',
                                      `config_version_id` varchar(36) DEFAULT NULL COMMENT '配置版本ID',
                                      `created_by` varchar(36) DEFAULT NULL COMMENT '触发运行的用户ID',
                                      `overall_precision` float DEFAULT NULL COMMENT '汇总精确率',
                                      `overall_recall` float DEFAULT NULL COMMENT '汇总召回率',
                                      `overall_f1` float DEFAULT NULL COMMENT '汇总F1',
                                      `overall_mrr` float DEFAULT NULL COMMENT '汇总MRR',
                                      `overall_ndcg` float DEFAULT NULL COMMENT '汇总NDCG',
                                      `total_test_cases` int NOT NULL DEFAULT 0 COMMENT '总测试用例数',
                                      `passed_test_cases` int NOT NULL DEFAULT 0 COMMENT '通过测试用例数',
                                      `failed_at_case_id` varchar(36) DEFAULT NULL COMMENT '失败时的用例ID',
                                      `ab_test_id` varchar(36) DEFAULT NULL COMMENT 'A/B测试组ID',
                                      `ab_test_side` enum('A','B') DEFAULT NULL COMMENT 'A或B',
                                      `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                      `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
                                      PRIMARY KEY (`id`),
                                      KEY `idx_rag_eval_test_run_testset_status_created` (`test_set_id`, `status`, `created_at`),
                                      KEY `idx_rag_eval_test_run_config_version` (`config_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAG评估测试运行记录表';

-- ----------------------------
-- 25. 测试运行结果详情表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_test_run_results`;

CREATE TABLE `rag_eval_test_run_results` (
                                             `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                             `run_id` varchar(36) NOT NULL COMMENT '测试运行ID',
                                             `case_id` varchar(36) NOT NULL COMMENT '测试用例ID',
                                             `query` text NOT NULL COMMENT '查询文本快照',
                                             `hit_at_1` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Top1是否命中',
                                             `hit_at_3` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Top3是否命中',
                                             `hit_at_5` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Top5是否命中',
                                             `matched_doc_ids` json DEFAULT NULL COMMENT '实际命中的文档ID列表',
                                             `matched_doc_scores` json DEFAULT NULL COMMENT '命中文档的分数列表',
                                             `status` enum('passed','failed') NOT NULL COMMENT '执行状态',
                                             `duration_ms` int DEFAULT NULL COMMENT '单用例执行耗时(毫秒)',
                                             `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                             PRIMARY KEY (`id`),
                                             KEY `idx_rag_eval_test_run_result_run_id` (`run_id`),
                                             KEY `idx_rag_eval_test_run_result_run_status` (`run_id`, `status`),
                                             KEY `idx_rag_eval_test_run_result_case_id` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试运行结果详情表';

-- ----------------------------
-- 26. 测试用例意图标注表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_intent_annotations`;

CREATE TABLE `rag_eval_intent_annotations` (
                                               `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                               `case_id` varchar(36) NOT NULL COMMENT '关联的测试用例ID',
                                               `intent_type` varchar(64) NOT NULL COMMENT '标注的意图类型',
                                               `annotated_by` varchar(36) DEFAULT NULL COMMENT '标注人ID',
                                               `annotated_at` datetime DEFAULT NULL COMMENT '标注时间',
                                               PRIMARY KEY (`id`),
                                               UNIQUE KEY `uk_rag_eval_intent_annotation_case` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试用例意图标注表';

-- ----------------------------
-- 27. 配置变更集表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_config_change_sets`;

CREATE TABLE `rag_eval_config_change_sets` (
                                               `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                               `change_set_label` varchar(32) NOT NULL COMMENT '展示用标签，格式 CS-20260416-001',
                                               `config_version_id` varchar(36) DEFAULT NULL COMMENT '发布后生成的配置版本ID',
                                               `status` enum('committed','rolled_back') NOT NULL DEFAULT 'committed' COMMENT '变更集状态',
                                               `rollback_reason` varchar(500) DEFAULT NULL COMMENT '回滚原因',
                                               `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                               PRIMARY KEY (`id`),
                                               KEY `idx_rag_eval_config_change_set_status` (`status`),
                                               KEY `idx_rag_eval_config_change_set_config_version` (`config_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置变更集表';

-- ----------------------------
-- 28. 变更集-提示词版本关联表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_config_change_set_prompts`;

CREATE TABLE `rag_eval_config_change_set_prompts` (
                                                      `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                                      `change_set_id` varchar(36) NOT NULL COMMENT '变更集ID',
                                                      `prompt_version_id` varchar(36) NOT NULL COMMENT '提示词版本ID',
                                                      PRIMARY KEY (`id`),
                                                      UNIQUE KEY `uk_rag_eval_change_set_prompt` (`change_set_id`, `prompt_version_id`),
                                                      KEY `idx_rag_eval_change_set_prompt_version` (`prompt_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='变更集-提示词版本关联表';

-- ----------------------------
-- 29. 测试评估报告表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_test_reports`;

CREATE TABLE `rag_eval_test_reports` (
                                         `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                         `run_id` varchar(36) DEFAULT NULL COMMENT '测试运行ID（常规报告关联TestRun；A/B对比报告为NULL）',
                                         `test_set_id` varchar(36) NOT NULL COMMENT '测试集ID',
                                         `config_version_id` varchar(36) DEFAULT NULL COMMENT '配置版本ID',
                                         `status` enum('processing','completed','superseded') NOT NULL DEFAULT 'processing' COMMENT '报告状态',
                                         `prompt_version_snapshot` json DEFAULT NULL COMMENT '提示词版本快照',
                                         `overall_score` float DEFAULT NULL COMMENT '综合得分',
                                         `precision` float DEFAULT NULL COMMENT '精确率',
                                         `recall` float DEFAULT NULL COMMENT '召回率',
                                         `f1` float DEFAULT NULL COMMENT 'F1',
                                         `mrr` float DEFAULT NULL COMMENT 'MRR',
                                         `ndcg` float DEFAULT NULL COMMENT 'NDCG',
                                         `validation_results` json DEFAULT NULL COMMENT '6层校验结果',
                                         `tuning_suggestion_summary` json DEFAULT NULL COMMENT '调优建议摘要',
                                         `created_by` varchar(36) DEFAULT NULL COMMENT '生成报告的用户ID',
                                         `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                         PRIMARY KEY (`id`),
                                         KEY `idx_rag_eval_test_report_testset_created` (`test_set_id`, `created_at`),
                                         KEY `idx_rag_eval_test_report_run_id` (`run_id`),
                                         KEY `idx_rag_eval_test_report_config_version` (`config_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试评估报告表';

-- ----------------------------
-- 30. 参数调优建议记录表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_tuning_suggestion_records`;

CREATE TABLE `rag_eval_tuning_suggestion_records` (
                                                      `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                                      `report_id` varchar(36) NOT NULL COMMENT '测试报告ID',
                                                      `param_name` varchar(128) NOT NULL COMMENT '参数名称',
                                                      `current_value` json DEFAULT NULL COMMENT '当前参数值',
                                                      `suggested_value` json DEFAULT NULL COMMENT '建议参数值',
                                                      `action` varchar(36) DEFAULT NULL COMMENT '建议动作',
                                                      `reason` text DEFAULT NULL COMMENT '调优理由',
                                                      `expected_effect` json DEFAULT NULL COMMENT '预期效果',
                                                      `priority` varchar(32) DEFAULT NULL COMMENT '优先级',
                                                      `source` enum('rule_engine','history','llm') DEFAULT NULL COMMENT '来源',
                                                      `safe_range` json DEFAULT NULL COMMENT '安全范围',
                                                      `applied` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否已采纳',
                                                      `applied_config_version_id` varchar(36) DEFAULT NULL COMMENT '采纳后应用到的配置版本ID',
                                                      PRIMARY KEY (`id`),
                                                      KEY `idx_rag_eval_tuning_suggestion_report_applied` (`report_id`, `applied`),
                                                      KEY `idx_rag_eval_tuning_applied_config` (`applied_config_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='参数调优建议记录表';

-- ----------------------------
-- 31. 提示词调优建议记录表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_prompt_suggestion_records`;

CREATE TABLE `rag_eval_prompt_suggestion_records` (
                                                      `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                                      `report_id` varchar(36) NOT NULL COMMENT '测试报告ID',
                                                      `prompt_key` varchar(128) NOT NULL COMMENT '提示词key',
                                                      `current_version_id` varchar(36) DEFAULT NULL COMMENT '当前提示词版本ID',
                                                      `suggested_version_id` varchar(36) DEFAULT NULL COMMENT '建议的提示词版本ID',
                                                      `reason` text DEFAULT NULL COMMENT '调优理由',
                                                      `expected_effect` json DEFAULT NULL COMMENT '预期效果',
                                                      `priority` varchar(32) DEFAULT NULL COMMENT '优先级',
                                                      `source` enum('rule_engine','history','llm') DEFAULT NULL COMMENT '来源',
                                                      `suggestion_type` enum('add_constraint','rewrite','parameter_tweak') DEFAULT NULL COMMENT '建议类型',
                                                      `applied` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否已采纳',
                                                      `applied_version_id` varchar(36) DEFAULT NULL COMMENT '采纳后的提示词版本ID',
                                                      PRIMARY KEY (`id`),
                                                      KEY `idx_rag_eval_prompt_suggestion_report_applied` (`report_id`, `applied`),
                                                      KEY `idx_rag_eval_ps_current_version` (`current_version_id`),
                                                      KEY `idx_rag_eval_ps_suggested_version` (`suggested_version_id`),
                                                      KEY `idx_rag_eval_ps_applied_version` (`applied_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词调优建议记录表';

-- ----------------------------
-- 32. 忽略的调优建议记录表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_ignored_suggestions`;

CREATE TABLE `rag_eval_ignored_suggestions` (
                                                `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                                `test_set_id` varchar(36) NOT NULL COMMENT '绑定测试集',
                                                `report_id` varchar(36) DEFAULT NULL COMMENT 'report级别时填写',
                                                `param_name` varchar(255) NOT NULL COMMENT '参数名或prompt_key',
                                                `suggestion_type` enum('config','prompt') NOT NULL COMMENT '忽略建议类型',
                                                `ignore_scope` enum('report','test_set') NOT NULL COMMENT '忽略范围',
                                                `ignored_by` varchar(36) DEFAULT NULL COMMENT '操作用户',
                                                `ignored_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '忽略时间',
                                                `ignore_reason` varchar(500) DEFAULT NULL COMMENT '忽略原因',
                                                `restored` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否已恢复',
                                                `restored_at` datetime DEFAULT NULL COMMENT '恢复时间',
                                                PRIMARY KEY (`id`),
                                                KEY `idx_rag_eval_ignored_suggestion_testset_scope_restored` (`test_set_id`, `ignore_scope`, `restored`),
                                                KEY `idx_rag_eval_ignored_suggestion_report` (`report_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='忽略的调优建议记录表';

-- ----------------------------
-- 33. 查询意图自动分类日志表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_query_intent_logs`;

CREATE TABLE `rag_eval_query_intent_logs` (
                                              `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                              `run_id` varchar(36) NOT NULL COMMENT '测试运行ID',
                                              `case_id` varchar(36) DEFAULT NULL COMMENT '测试用例ID',
                                              `query` text NOT NULL COMMENT '查询文本',
                                              `predicted_intent` varchar(64) NOT NULL COMMENT 'LLM自动分类的意图',
                                              `confidence` float DEFAULT NULL COMMENT '置信度(0.0-1.0)',
                                              `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                              PRIMARY KEY (`id`),
                                              KEY `idx_rag_eval_query_intent_log_run` (`run_id`),
                                              KEY `idx_rag_eval_query_intent_log_case` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='查询意图自动分类日志表';

-- ----------------------------
-- 34. 同义查询对表
-- ----------------------------
DROP TABLE IF EXISTS `rag_eval_synonym_query_pairs`;

CREATE TABLE `rag_eval_synonym_query_pairs` (
                                                `id` varchar(36) NOT NULL COMMENT '主键UUID',
                                                `query_a` text NOT NULL COMMENT '查询A',
                                                `query_b` text NOT NULL COMMENT '查询B',
                                                `domain` varchar(64) NOT NULL COMMENT '发展领域',
                                                `created_by` varchar(36) DEFAULT NULL COMMENT '创建者',
                                                `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                                                `source` enum('builtin','auto_extracted','manual') NOT NULL COMMENT '同义词来源',
                                                `active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
                                                PRIMARY KEY (`id`),
                                                KEY `idx_rag_eval_synonym_domain_active` (`domain`, `active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='同义查询对表';

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- 初始化完成
-- ----------------------------
SELECT '数据库初始化完成，共创建33张业务表（原有15张 + RAG评估18张）' AS result;