-- =============================================
-- 儿童发展评估系统 MySQL 5.7 完整初始化脚本
-- 基于线上数据库结构自动生成
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
-- Table structure for ab_test_metrics
-- ----------------------------
DROP TABLE IF EXISTS `ab_test_metrics`;
CREATE TABLE IF NOT EXISTS `ab_test_metrics` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `test_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '测试名称',
  `variant_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '变体名称',
  `metric_value` decimal(10,4) NOT NULL COMMENT '指标值',
  `metric_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '指标类型',
  `recorded_at` datetime NOT NULL COMMENT '记录时间',
  PRIMARY KEY (`id`),
  KEY `idx_ab_metrics_test_name` (`test_name`),
  KEY `idx_ab_metrics_variant_name` (`variant_name`),
  KEY `idx_ab_metrics_recorded_at` (`recorded_at`),
  KEY `idx_ab_metrics_test_variant` (`test_name`,`variant_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='A/B测试指标表';

-- ----------------------------
-- Table structure for alembic_version
-- ----------------------------
DROP TABLE IF EXISTS `alembic_version`;
CREATE TABLE IF NOT EXISTS `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for config_audit_log
-- ----------------------------
DROP TABLE IF EXISTS `config_audit_log`;
CREATE TABLE IF NOT EXISTS `config_audit_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  `action` enum('UPDATE','ROLLBACK','RESET') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '操作类型',
  `from_version` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '源版本ID',
  `to_version` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '目标版本ID',
  `user` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '操作人',
  PRIMARY KEY (`id`),
  KEY `idx_audit_log_timestamp` (`timestamp`),
  KEY `idx_audit_log_action` (`action`),
  KEY `idx_audit_log_from_version` (`from_version`),
  KEY `idx_audit_log_to_version` (`to_version`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置审计日志表';

-- ----------------------------
-- Table structure for config_versions
-- ----------------------------
DROP TABLE IF EXISTS `config_versions`;
CREATE TABLE IF NOT EXISTS `config_versions` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '版本ID (UUID)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `created_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建人',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '版本描述',
  `config_snapshot` json NOT NULL COMMENT '配置快照',
  `parent_version_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '父版本ID',
  `is_factory_reset` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否出厂重置',
  PRIMARY KEY (`id`),
  KEY `idx_config_versions_created_at` (`created_at`),
  KEY `idx_config_versions_parent` (`parent_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置版本表';

-- ----------------------------
-- Table structure for document_records
-- ----------------------------
DROP TABLE IF EXISTS `document_records`;
CREATE TABLE IF NOT EXISTS `document_records` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '记录ID (UUID)',
  `file_hash` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件哈希',
  `file_name` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件名',
  `upload_date` datetime NOT NULL COMMENT '上传日期',
  `total_pages` int(11) DEFAULT NULL COMMENT '总页数',
  `indexed_chunks` int(11) NOT NULL DEFAULT '0' COMMENT '已索引分块数',
  `category` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '分类',
  `metadata` json DEFAULT NULL COMMENT '元数据',
  `ref_doc_ids` json DEFAULT NULL COMMENT '关联文档ID列表',
  `status` enum('pending','processing','indexed','failed') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT '导入状态',
  `progress` int(11) NOT NULL DEFAULT '0' COMMENT '导入进度 (0-100)',
  `graph_ready` tinyint(1) NOT NULL DEFAULT '0' COMMENT '知识图谱是否构建完成',
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
-- Table structure for eval_config_change_sets
-- ----------------------------
DROP TABLE IF EXISTS `eval_config_change_sets`;
CREATE TABLE IF NOT EXISTS `eval_config_change_sets` (
  `id` varchar(64) NOT NULL,
  `change_set_label` varchar(255) NOT NULL COMMENT '变更集标签',
  `config_version_id` varchar(64) NOT NULL COMMENT '目标配置版本',
  `status` varchar(16) NOT NULL DEFAULT 'committed' COMMENT 'committed/rolled_back',
  `rollback_reason` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `rolled_back_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_config_version_id` (`config_version_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for eval_config_versions
-- ----------------------------
DROP TABLE IF EXISTS `eval_config_versions`;
CREATE TABLE IF NOT EXISTS `eval_config_versions` (
  `id` varchar(64) NOT NULL,
  `version_number` int(11) NOT NULL DEFAULT '1',
  `version_label` varchar(100) DEFAULT NULL COMMENT '版本标签',
  `config_snapshot` json NOT NULL COMMENT '完整配置快照',
  `change_summary` text COMMENT '变更摘要',
  `created_by` varchar(64) DEFAULT NULL COMMENT '创建者',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for eval_reports
-- ----------------------------
DROP TABLE IF EXISTS `eval_reports`;
CREATE TABLE IF NOT EXISTS `eval_reports` (
  `id` varchar(64) NOT NULL,
  `run_id` varchar(64) NOT NULL,
  `test_set_id` varchar(64) DEFAULT NULL COMMENT '主测试集 ID',
  `config_version_id` varchar(64) DEFAULT NULL COMMENT '配置版本 ID',
  `overall_score` decimal(5,4) DEFAULT NULL COMMENT '三层加权综合得分',
  `l1_score` decimal(5,4) DEFAULT NULL COMMENT 'L1 层得分',
  `l2_score` decimal(5,4) DEFAULT NULL COMMENT 'L2 层得分',
  `l3_score` decimal(5,4) DEFAULT NULL COMMENT 'L3 层得分',
  `precision` decimal(5,4) DEFAULT NULL,
  `recall` decimal(5,4) DEFAULT NULL,
  `f1` decimal(5,4) DEFAULT NULL,
  `mrr` decimal(5,4) DEFAULT NULL,
  `ndcg` decimal(5,4) DEFAULT NULL,
  `metrics_json` json NOT NULL COMMENT '三层指标 RunMetrics JSON',
  `diagnosis_json` json DEFAULT NULL COMMENT '六层诊断结果 JSON',
  `bad_cases_json` json DEFAULT NULL COMMENT '坏案列表 JSON',
  `suggestions_json` json DEFAULT NULL COMMENT '调优建议列表 JSON',
  `markdown_content` longtext COMMENT 'Markdown 报告内容',
  `status` varchar(16) NOT NULL DEFAULT 'processing' COMMENT 'processing/completed/superseded',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_run_id` (`run_id`),
  KEY `idx_test_set_id` (`test_set_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for graph_community_chunks
-- ----------------------------
DROP TABLE IF EXISTS `graph_community_chunks`;
CREATE TABLE IF NOT EXISTS `graph_community_chunks` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `community_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '社区节点ID',
  `chunk_id` int(11) NOT NULL COMMENT '块ID',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_community_chunk` (`community_id`,`chunk_id`),
  KEY `idx_community` (`community_id`),
  KEY `idx_chunk` (`chunk_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='块与社区关联表';

-- ----------------------------
-- Table structure for graph_community_tree
-- ----------------------------
DROP TABLE IF EXISTS `graph_community_tree`;
CREATE TABLE IF NOT EXISTS `graph_community_tree` (
  `node_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '社区节点ID',
  `parent_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '父节点ID',
  `level` int(11) NOT NULL DEFAULT '0' COMMENT '层级深度',
  `scope` enum('book','global') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'book' COMMENT '作用域',
  `book_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'scope=book 时非空(UUID)',
  `label` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '社区标签（实体名摘要）',
  `entity_names` json DEFAULT NULL COMMENT '社区内实体名列表',
  `chunk_ids` json DEFAULT NULL COMMENT '叶子节点关联的块ID列表',
  `is_leaf` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否叶子节点',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`node_id`),
  KEY `idx_comm_parent` (`parent_id`),
  KEY `idx_comm_scope_level` (`scope`,`level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='层级社区树表';

-- ----------------------------
-- Table structure for graph_entities
-- ----------------------------
DROP TABLE IF EXISTS `graph_entities`;
CREATE TABLE IF NOT EXISTS `graph_entities` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '实体名称',
  `entity_type` enum('development_concept','symptom_behavior','intervention_method','assessment_tool','brain_region','age_milestone','clinical_population') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '实体类型',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '实体描述',
  `aliases` json DEFAULT NULL COMMENT '别名列表 ["别名1", "别名2"]',
  `book_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属书籍ID(UUID)',
  `chunk_ids` json DEFAULT NULL COMMENT '关联块ID列表 [101, 102, 103]',
  `embedding` json DEFAULT NULL COMMENT '可选，跨书实体去重用',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_graph_entity_book` (`book_id`),
  KEY `idx_graph_entity_type` (`entity_type`)
) ENGINE=InnoDB AUTO_INCREMENT=270 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识图谱实体表';

-- ----------------------------
-- Table structure for graph_relations
-- ----------------------------
DROP TABLE IF EXISTS `graph_relations`;
CREATE TABLE IF NOT EXISTS `graph_relations` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `source_entity_id` int(11) NOT NULL COMMENT '源实体ID',
  `target_entity_id` int(11) NOT NULL COMMENT '目标实体ID',
  `relation_type` enum('causes','treats','assesses','related_to','contraindicates','develops_at') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '关系类型',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '关系描述',
  `confidence` float DEFAULT '1' COMMENT '置信度 0-1',
  `book_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属书籍ID(UUID)',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_graph_rel_source` (`source_entity_id`),
  KEY `idx_graph_rel_target` (`target_entity_id`),
  KEY `idx_graph_rel_type` (`relation_type`)
) ENGINE=InnoDB AUTO_INCREMENT=164 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识图谱关系表';

-- ----------------------------
-- Table structure for knowledge_qa_history
-- ----------------------------
DROP TABLE IF EXISTS `knowledge_qa_history`;
CREATE TABLE IF NOT EXISTS `knowledge_qa_history` (
  `id` varchar(64) NOT NULL,
  `task_id` varchar(64) NOT NULL,
  `question` text NOT NULL,
  `result_json` json NOT NULL COMMENT '完整的问答结果',
  `matched_books_json` json DEFAULT NULL COMMENT '匹配到的书籍列表',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `status` varchar(20) NOT NULL DEFAULT 'completed' COMMENT 'completed / partial / cancelled / timeout / error',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_knowledge_qa_history_task_id` (`task_id`),
  KEY `ix_knowledge_qa_history_created_at` (`created_at`),
  KEY `idx_kqa_history_task_id` (`task_id`),
  KEY `idx_kqa_history_created_at` (`created_at`),
  KEY `idx_kqa_history_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for knowledge_snapshots
-- ----------------------------
DROP TABLE IF EXISTS `knowledge_snapshots`;
CREATE TABLE IF NOT EXISTS `knowledge_snapshots` (
  `id` varchar(64) NOT NULL,
  `name` varchar(255) NOT NULL,
  `description` text,
  `vector_store_path` varchar(512) NOT NULL COMMENT '向量库存储路径',
  `document_count` int(11) NOT NULL DEFAULT '0',
  `chunk_count` int(11) NOT NULL DEFAULT '0',
  `config_version_id` varchar(64) DEFAULT NULL COMMENT '配置版本 ID',
  `config_snapshot` json DEFAULT NULL COMMENT '配置快照 JSON',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_config_version_id` (`config_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for llm_call_logs
-- ----------------------------
DROP TABLE IF EXISTS `llm_call_logs`;
CREATE TABLE IF NOT EXISTS `llm_call_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `request_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '请求ID',
  `prompt_key` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '提示词键',
  `prompt_version` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '提示词版本',
  `scenario` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '使用场景',
  `model_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '模型名称',
  `input_tokens` int(11) DEFAULT NULL COMMENT '输入Token数',
  `output_tokens` int(11) DEFAULT NULL COMMENT '输出Token数',
  `total_tokens` int(11) DEFAULT NULL COMMENT '总Token数',
  `duration_ms` int(11) DEFAULT NULL COMMENT '耗时 (毫秒)',
  `status` enum('success','failed','timeout') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '调用状态',
  `error_message` text COLLATE utf8mb4_unicode_ci COMMENT '错误信息',
  `trace_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Trace ID',
  `span_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Span ID',
  `parent_span_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '父 Span ID',
  `prompt_messages` json DEFAULT NULL COMMENT '提示词消息',
  `completion_message` text COLLATE utf8mb4_unicode_ci COMMENT '完成消息',
  `full_prompt_path` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '完整提示词文件路径',
  `full_completion_path` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '完整完成内容文件路径',
  `call_parameters` json DEFAULT NULL COMMENT '调用参数',
  `model_parameters` json DEFAULT NULL COMMENT '模型参数',
  `cost` decimal(10,4) DEFAULT NULL COMMENT '调用成本',
  `tags` json DEFAULT NULL COMMENT '标签列表',
  `tokens` int(11) DEFAULT NULL COMMENT 'Token 总数',
  `completion_start_time_ms` int(11) DEFAULT NULL COMMENT '完成开始时间 (毫秒)',
  `level` enum('DEBUG','INFO','WARNING','ERROR') COLLATE utf8mb4_unicode_ci DEFAULT 'INFO' COMMENT '日志级别',
  `user_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户 ID',
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '会话 ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_llm_span_id` (`span_id`),
  KEY `idx_llm_logs_request_id` (`request_id`),
  KEY `idx_llm_logs_prompt_key` (`prompt_key`),
  KEY `idx_llm_logs_scenario` (`scenario`),
  KEY `idx_llm_logs_model_name` (`model_name`),
  KEY `idx_llm_logs_duration_ms` (`duration_ms`),
  KEY `idx_llm_logs_status` (`status`),
  KEY `idx_llm_logs_created_at` (`created_at`),
  KEY `idx_llm_trace_id` (`trace_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1396 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='LLM 调用日志表';

-- ----------------------------
-- Table structure for md_metadata
-- ----------------------------
DROP TABLE IF EXISTS `md_metadata`;
CREATE TABLE IF NOT EXISTS `md_metadata` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `book_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `book_title` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `author` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '作者',
  `current_version_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `version` int(11) DEFAULT '1' COMMENT '当前版本号',
  `status` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `bind_source` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT 'kb_bind' COMMENT '来源: kb_bind=从知识库绑定, direct=直接上传',
  `total_entities` int(11) DEFAULT NULL,
  `total_claims` int(11) DEFAULT NULL,
  `total_prescriptions` int(11) DEFAULT NULL,
  `total_communities` int(11) DEFAULT '0' COMMENT '社区数',
  `neo4j_synced` int(11) DEFAULT NULL,
  `reviewed_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '审核者',
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `file_hash` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_md_metadata_book_id` (`book_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for md_version
-- ----------------------------
DROP TABLE IF EXISTS `md_version`;
CREATE TABLE IF NOT EXISTS `md_version` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `book_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `version` int(11) NOT NULL,
  `md_content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `cypher_count` int(11) DEFAULT NULL,
  `diff_summary` json DEFAULT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reviewed_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `published_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_md_version_book_id` (`book_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for prompt_ab_tests
-- ----------------------------
DROP TABLE IF EXISTS `prompt_ab_tests`;
CREATE TABLE IF NOT EXISTS `prompt_ab_tests` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'A/B测试ID (UUID)',
  `prompt_key` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '提示词键',
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '测试名称',
  `is_active` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否激活',
  `variant_a_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '变体A版本',
  `variant_b_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '变体B版本',
  `variant_a_ratio` float NOT NULL DEFAULT '0.5' COMMENT '变体A流量比例',
  `started_at` datetime DEFAULT NULL COMMENT '开始时间',
  `ended_at` datetime DEFAULT NULL COMMENT '结束时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_prompt_ab_tests_prompt_key` (`prompt_key`),
  KEY `idx_prompt_ab_tests_is_active` (`is_active`),
  KEY `idx_prompt_ab_test_prompt_active` (`prompt_key`,`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词A/B测试表';

-- ----------------------------
-- Table structure for prompt_metadata
-- ----------------------------
DROP TABLE IF EXISTS `prompt_metadata`;
CREATE TABLE IF NOT EXISTS `prompt_metadata` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '主键UUID',
  `prompt_key` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '提示词唯一标识key',
  `name_zh` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '中文名称',
  `purpose` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用途说明',
  `category` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '分类',
  `subcategory` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '子分类',
  `variables_schema` json DEFAULT NULL COMMENT '变量声明 schema',
  `code_references` json DEFAULT NULL COMMENT '代码引用位置',
  `config_dependencies` json DEFAULT NULL COMMENT '配置参数依赖',
  `is_active` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用',
  `is_system` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否系统内置',
  `created_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建人',
  `updated_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '更新人',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_prompt_key` (`prompt_key`),
  KEY `idx_prompt_category_active` (`category`,`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词元数据表';

-- ----------------------------
-- Table structure for prompt_versions
-- ----------------------------
DROP TABLE IF EXISTS `prompt_versions`;
CREATE TABLE IF NOT EXISTS `prompt_versions` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '主键UUID',
  `prompt_key` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '提示词唯一标识key',
  `version_label` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '展示用版本号',
  `version_number` int(11) NOT NULL COMMENT '该 prompt_key 下的自增序号',
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '提示词完整内容',
  `content_hash` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '内容 SHA256 哈希',
  `variables_extracted` json DEFAULT NULL COMMENT '自动提取的变量列表',
  `change_impact` json DEFAULT NULL COMMENT '变更影响分析',
  `change_summary` text COLLATE utf8mb4_unicode_ci COMMENT '变更摘要',
  `tags` json DEFAULT NULL COMMENT '标签列表',
  `fallback` text COLLATE utf8mb4_unicode_ci COMMENT '降级备用内容',
  `created_by` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建人用户ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_prompt_key_version` (`prompt_key`,`version_label`),
  KEY `idx_prompt_key_content_hash` (`content_hash`),
  KEY `idx_prompt_key_created` (`prompt_key`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词版本表';

-- ----------------------------
-- Table structure for source_documents
-- ----------------------------
DROP TABLE IF EXISTS `source_documents`;
CREATE TABLE IF NOT EXISTS `source_documents` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文档ID (UUID)',
  `title` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文档标题',
  `author` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '作者/编著者',
  `file_type` enum('pdf','epub','txt') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件类型',
  `source_type` enum('book','paper','guideline','manual') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'book' COMMENT '文献类型',
  `file_path` varchar(1000) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件路径',
  `file_hash` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件哈希 (SHA-256)',
  `content_summary` text COLLATE utf8mb4_unicode_ci COMMENT '内容摘要',
  `page_count` int(11) DEFAULT NULL COMMENT '页数',
  `chapter_count` int(11) DEFAULT NULL COMMENT '章节数',
  `quality_score` decimal(3,2) DEFAULT NULL COMMENT '质量评分 (0-1)',
  `scan_page_ratio` decimal(3,2) DEFAULT NULL COMMENT '扫描页比例',
  `chapter_structure` json DEFAULT NULL COMMENT '章节结构',
  `quality_report` json DEFAULT NULL COMMENT '质量报告',
  `status` enum('uploaded','parsing','ready','archived') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'uploaded' COMMENT '文档状态',
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
-- Table structure for test_case_drafts
-- ----------------------------
DROP TABLE IF EXISTS `test_case_drafts`;
CREATE TABLE IF NOT EXISTS `test_case_drafts` (
  `id` varchar(64) NOT NULL,
  `source_document_id` varchar(64) DEFAULT NULL COMMENT '来源文档 ID',
  `query` text NOT NULL COMMENT '测试问题',
  `description` text COMMENT '期望答案描述',
  `expected_knowledge_ids` json DEFAULT NULL COMMENT '期望检索的知识片段 ID 列表',
  `expected_keywords` json DEFAULT NULL COMMENT '期望关键词列表',
  `answer_points` json DEFAULT NULL COMMENT '答案要点列表',
  `professional_terms` json DEFAULT NULL COMMENT '专业术语列表',
  `difficulty_level` varchar(16) DEFAULT NULL COMMENT 'easy/medium/hard',
  `faithfulness_score` decimal(5,4) DEFAULT NULL COMMENT '忠实度评分(0-1)',
  `source_chunk_id` varchar(64) DEFAULT NULL COMMENT '来源分块 ID',
  `source_page` int(11) DEFAULT NULL COMMENT '来源页码',
  `source_content_snippet` text COMMENT '来源内容片段',
  `generation_params` json DEFAULT NULL COMMENT '生成参数快照',
  `batch_id` varchar(64) DEFAULT NULL COMMENT '生成批次 ID',
  `draft_index` int(11) DEFAULT '0' COMMENT '批次内序号',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/reviewed/rejected/imported',
  `version` int(11) NOT NULL DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_source_document_id` (`source_document_id`),
  KEY `idx_status` (`status`),
  KEY `idx_batch_id` (`batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for test_cases
-- ----------------------------
DROP TABLE IF EXISTS `test_cases`;
CREATE TABLE IF NOT EXISTS `test_cases` (
  `id` varchar(64) NOT NULL,
  `query` text NOT NULL COMMENT '测试问题',
  `age` decimal(4,1) DEFAULT NULL COMMENT '年龄（岁），从草稿提升时可留空',
  `age_stage_label` varchar(20) NOT NULL DEFAULT '' COMMENT '年龄段标签',
  `domain` varchar(32) DEFAULT NULL COMMENT '测试领域，从草稿提升时可留空',
  `description` text COMMENT '期望答案描述',
  `expected_knowledge_ids` json DEFAULT NULL COMMENT '期望检索的知识片段 ID 列表',
  `expected_keywords` json DEFAULT NULL COMMENT '期望关键词列表',
  `answer_points_summary` text COMMENT '答案要点摘要',
  `min_age_requirement` decimal(4,1) DEFAULT NULL COMMENT '最小年龄要求',
  `max_age_requirement` decimal(4,1) DEFAULT NULL COMMENT '最大年龄要求',
  `difficulty_level` varchar(16) DEFAULT NULL COMMENT 'easy/medium/hard',
  `professional_terms` json DEFAULT NULL COMMENT '专业术语列表',
  `relevance_scores` json DEFAULT NULL COMMENT '相关度评分',
  `book_ids` json DEFAULT NULL COMMENT '限定检索的书籍 file_hash 列表',
  `source` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual/draft/import',
  `source_draft_id` varchar(64) DEFAULT NULL COMMENT '来源草稿 ID',
  `source_document_id` varchar(64) DEFAULT NULL COMMENT '来源文档 ID',
  `version` int(11) NOT NULL DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_domain` (`domain`),
  KEY `idx_age_stage_label` (`age_stage_label`),
  KEY `idx_source` (`source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for test_run_results
-- ----------------------------
DROP TABLE IF EXISTS `test_run_results`;
CREATE TABLE IF NOT EXISTS `test_run_results` (
  `id` varchar(64) NOT NULL,
  `run_id` varchar(64) NOT NULL,
  `test_case_id` varchar(64) NOT NULL,
  `query` text NOT NULL,
  `retrieved_doc_ids` json DEFAULT NULL COMMENT '检索到的文档 ID 列表',
  `retrieved_contexts` json DEFAULT NULL COMMENT '检索上下文文本列表',
  `relevant_doc_ids` json DEFAULT NULL COMMENT '相关文档 ID 列表',
  `expected_knowledge_ids` json DEFAULT NULL COMMENT '期望知识片段 ID',
  `actual_knowledge_ids` json DEFAULT NULL COMMENT '实际匹配的知识片段 ID',
  `matched_count` int(11) DEFAULT '0',
  `expected_count` int(11) DEFAULT '0',
  `actual_count` int(11) DEFAULT '0',
  `precision` decimal(5,4) DEFAULT NULL,
  `recall` decimal(5,4) DEFAULT NULL,
  `f1` decimal(5,4) DEFAULT NULL,
  `mrr` decimal(5,4) DEFAULT '0.0000',
  `ndcg` decimal(5,4) DEFAULT NULL,
  `hit_rate_1` decimal(5,4) DEFAULT '0.0000',
  `hit_rate_3` decimal(5,4) DEFAULT '0.0000',
  `hit_rate_5` decimal(5,4) DEFAULT '0.0000',
  `actual_answer` text COMMENT 'RAG 生成的实际答案',
  `l1_metrics_json` json DEFAULT NULL COMMENT '单用例 L1 指标',
  `l2_metrics_json` json DEFAULT NULL COMMENT '单用例 L2 指标',
  `diagnosis_json` json DEFAULT NULL COMMENT '单用例诊断结果',
  `passed` tinyint(1) DEFAULT NULL COMMENT '是否通过',
  `error_message` text,
  `execution_time_ms` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_run_id` (`run_id`),
  KEY `idx_test_case_id` (`test_case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for test_runs
-- ----------------------------
DROP TABLE IF EXISTS `test_runs`;
CREATE TABLE IF NOT EXISTS `test_runs` (
  `id` varchar(64) NOT NULL,
  `name` varchar(255) NOT NULL,
  `description` text,
  `test_set_ids` json NOT NULL COMMENT '关联的测试集 ID 列表',
  `custom_case_ids` json DEFAULT NULL COMMENT '额外用例 ID 列表',
  `snapshot_id` varchar(64) DEFAULT NULL COMMENT '知识库快照 ID',
  `config_version_id` varchar(64) DEFAULT NULL COMMENT '配置版本 ID',
  `config_snapshot` json DEFAULT NULL COMMENT '配置快照',
  `previous_config_version_id` varchar(64) DEFAULT NULL COMMENT '前一配置版本 ID',
  `task_id` varchar(64) DEFAULT NULL COMMENT '异步任务 ID，用于取消运行',
  `status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed/cancelled',
  `total_test_cases` int(11) NOT NULL DEFAULT '0',
  `passed_test_cases` int(11) NOT NULL DEFAULT '0',
  `overall_precision` decimal(5,4) DEFAULT NULL COMMENT '整体精确率',
  `overall_recall` decimal(5,4) DEFAULT NULL COMMENT '整体召回率',
  `overall_f1` decimal(5,4) DEFAULT NULL COMMENT '整体F1',
  `overall_mrr` decimal(5,4) DEFAULT NULL COMMENT '整体MRR',
  `overall_ndcg` decimal(5,4) DEFAULT NULL COMMENT '整体NDCG',
  `l1_metrics_json` json DEFAULT NULL COMMENT 'L1 检索质量指标',
  `l2_metrics_json` json DEFAULT NULL COMMENT 'L2 生成质量指标',
  `l3_metrics_json` json DEFAULT NULL COMMENT 'L3 系统质量指标',
  `overall_score` decimal(5,4) DEFAULT NULL COMMENT '加权综合得分',
  `diagnosis_json` json DEFAULT NULL COMMENT '六层诊断结果',
  `started_at` datetime DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_status` (`status`),
  KEY `idx_snapshot_id` (`snapshot_id`),
  KEY `idx_config_version_id` (`config_version_id`),
  KEY `idx_task_id` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for test_set_cases
-- ----------------------------
DROP TABLE IF EXISTS `test_set_cases`;
CREATE TABLE IF NOT EXISTS `test_set_cases` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `test_set_id` varchar(64) NOT NULL,
  `test_case_id` varchar(64) NOT NULL,
  `added_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_set_case` (`test_set_id`,`test_case_id`),
  KEY `idx_test_case_id` (`test_case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for test_sets
-- ----------------------------
DROP TABLE IF EXISTS `test_sets`;
CREATE TABLE IF NOT EXISTS `test_sets` (
  `id` varchar(64) NOT NULL,
  `name` varchar(255) NOT NULL,
  `description` text,
  `source_type` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual/json_import/book_generated/mixed',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for traces
-- ----------------------------
DROP TABLE IF EXISTS `traces`;
CREATE TABLE IF NOT EXISTS `traces` (
  `trace_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Trace ID (UUID)',
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Trace 名称',
  `user_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户ID',
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '会话ID',
  `metadata` json DEFAULT NULL COMMENT '元数据',
  `start_time` datetime NOT NULL COMMENT '开始时间',
  `end_time` datetime DEFAULT NULL COMMENT '结束时间',
  `total_duration_ms` int(11) NOT NULL DEFAULT '0' COMMENT '总耗时（毫秒）',
  `total_tokens` int(11) NOT NULL DEFAULT '0' COMMENT '总Token数',
  `total_cost` decimal(10,4) NOT NULL DEFAULT '0.0000' COMMENT '总成本',
  `status` enum('success','failed','partial') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '执行状态',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`trace_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_trace_status` (`status`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Trace 跟踪表';

-- ----------------------------
-- Table structure for tuning_suggestions
-- ----------------------------
DROP TABLE IF EXISTS `tuning_suggestions`;
CREATE TABLE IF NOT EXISTS `tuning_suggestions` (
  `id` varchar(64) NOT NULL,
  `run_id` varchar(64) NOT NULL,
  `report_id` varchar(64) DEFAULT NULL COMMENT '关联报告 ID',
  `category` varchar(32) NOT NULL COMMENT 'retrieval/generation/configuration/cost/prompt',
  `severity` varchar(16) NOT NULL COMMENT 'critical/warning/info',
  `title` varchar(255) NOT NULL,
  `description` text NOT NULL,
  `current_value` json DEFAULT NULL COMMENT '当前值',
  `suggested_value` json DEFAULT NULL COMMENT '建议值',
  `expected_impact` text COMMENT '预期影响',
  `source` varchar(16) NOT NULL DEFAULT 'rule_engine' COMMENT 'rule_engine/llm/diagnosis',
  `priority` int(11) DEFAULT '0' COMMENT '优先级（数值越高越优先）',
  `safe_range` json DEFAULT NULL COMMENT '安全范围',
  `status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/adopted/rejected/ignored',
  `conflict_with` varchar(64) DEFAULT NULL COMMENT '冲突的建议 ID',
  `applied_config_version_id` varchar(64) DEFAULT NULL COMMENT '采纳后生成的配置版本 ID',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_run_id` (`run_id`),
  KEY `idx_report_id` (`report_id`),
  KEY `idx_status` (`status`),
  KEY `idx_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


SET FOREIGN_KEY_CHECKS = 1;
