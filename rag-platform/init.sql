-- ============================================================
-- RAG Platform 数据库初始化脚本
-- MySQL 5.7 兼容，utf8mb4，无外键约束（弱关联）
-- 共 31 张表：9 权限 + 3 管道 + 4 知识库 + 11 评估 + 1 搜索 + 3 基础设施
-- ============================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 一、权限与多租户（9 张）
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- 1. 租户表
DROP TABLE IF EXISTS `tenants`;
CREATE TABLE `tenants` (
    `id` VARCHAR(36) NOT NULL COMMENT '租户ID (UUID)',
    `name` VARCHAR(255) NOT NULL COMMENT '租户名称',
    `slug` VARCHAR(100) NOT NULL COMMENT '租户标识（全局唯一，用于存储路径和 API 上下文）',
    `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '状态：active/disabled/archived/deleted',
    `resource_limits` JSON COMMENT '资源配额 {"max_knowledge_bases":10,"max_documents":1000000,...}',
    `deleted_at` DATETIME DEFAULT NULL COMMENT '软删除时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_tenants_slug` (`slug`),
    KEY `idx_tenants_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户表';

-- 2. 用户表
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    `id` VARCHAR(36) NOT NULL COMMENT '用户ID (UUID)',
    `tenant_id` VARCHAR(36) DEFAULT NULL COMMENT '租户ID（NULL=超管）',
    `username` VARCHAR(100) NOT NULL COMMENT '用户名',
    `email` VARCHAR(255) NOT NULL COMMENT '邮箱',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '状态：active/disabled',
    `deleted_at` DATETIME DEFAULT NULL COMMENT '软删除时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_users_email_tenant` (`email`, `tenant_id`),
    KEY `idx_users_tenant_id` (`tenant_id`),
    KEY `idx_users_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 3. 角色表
DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
    `id` VARCHAR(36) NOT NULL COMMENT '角色ID (UUID)',
    `tenant_id` VARCHAR(36) NOT NULL COMMENT '租户ID',
    `name` VARCHAR(100) NOT NULL COMMENT '角色名称',
    `slug` VARCHAR(100) NOT NULL COMMENT '角色标识',
    `permissions` JSON NOT NULL COMMENT '权限列表 ["kb:read","kb:write","pipeline:read",...]',
    `is_builtin` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否内置角色',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_roles_slug_tenant` (`slug`, `tenant_id`),
    KEY `idx_roles_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

-- 4. 用户角色关联表
DROP TABLE IF EXISTS `user_roles`;
CREATE TABLE `user_roles` (
    `user_id` VARCHAR(36) NOT NULL COMMENT '用户ID',
    `role_id` VARCHAR(36) NOT NULL COMMENT '角色ID',
    PRIMARY KEY (`user_id`, `role_id`),
    KEY `idx_user_roles_role_id` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联表';

-- 5. 用户邀请表
DROP TABLE IF EXISTS `user_invitations`;
CREATE TABLE `user_invitations` (
    `id` VARCHAR(36) NOT NULL COMMENT '邀请ID (UUID)',
    `tenant_id` VARCHAR(36) NOT NULL COMMENT '租户ID',
    `email` VARCHAR(255) NOT NULL COMMENT '被邀请邮箱',
    `roles` JSON NOT NULL COMMENT '角色列表',
    `token` VARCHAR(255) NOT NULL COMMENT '邀请令牌',
    `expires_at` DATETIME NOT NULL COMMENT '过期时间',
    `accepted_at` DATETIME DEFAULT NULL COMMENT '接受时间',
    `created_by` VARCHAR(36) NOT NULL COMMENT '邀请人ID',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_invitations_token` (`token`),
    KEY `idx_invitations_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户邀请表';

-- 6. God Mode 审计日志
DROP TABLE IF EXISTS `god_mode_audit_log`;
CREATE TABLE `god_mode_audit_log` (
    `id` VARCHAR(36) NOT NULL COMMENT '日志ID',
    `tenant_id` VARCHAR(36) NOT NULL COMMENT '租户ID',
    `actor_id` VARCHAR(36) NOT NULL COMMENT '超管ID',
    `action` VARCHAR(50) NOT NULL COMMENT '操作：enter/exit/read/write/extend',
    `target_type` VARCHAR(50) DEFAULT NULL COMMENT '目标类型',
    `target_id` VARCHAR(64) DEFAULT NULL COMMENT '目标ID',
    `details` TEXT COMMENT '操作详情',
    `session_started_at` DATETIME DEFAULT NULL COMMENT '会话开始时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_god_mode_tenant_id` (`tenant_id`),
    KEY `idx_god_mode_actor_id` (`actor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='God Mode 审计日志';

-- 7. 租户删除快照表
DROP TABLE IF EXISTS `tenant_deletion_snapshots`;
CREATE TABLE `tenant_deletion_snapshots` (
    `id` VARCHAR(36) NOT NULL COMMENT '快照ID',
    `tenant_id` VARCHAR(36) NOT NULL COMMENT '租户ID',
    `snapshot_path` VARCHAR(500) NOT NULL COMMENT '快照文件路径',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态：pending/ready/expired',
    `expires_at` DATETIME NOT NULL COMMENT '过期时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_snapshots_tenant_id` (`tenant_id`),
    KEY `idx_snapshots_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户删除快照表';

-- 8. 权限审计日志
DROP TABLE IF EXISTS `permission_audit_log`;
CREATE TABLE `permission_audit_log` (
    `id` VARCHAR(36) NOT NULL COMMENT '日志ID',
    `tenant_id` VARCHAR(36) NOT NULL COMMENT '租户ID',
    `actor_id` VARCHAR(36) NOT NULL COMMENT '操作人ID',
    `action` VARCHAR(50) NOT NULL COMMENT '操作类型',
    `target_type` VARCHAR(50) NOT NULL COMMENT '目标类型',
    `target_id` VARCHAR(64) NOT NULL COMMENT '目标ID',
    `old_value` JSON COMMENT '旧值',
    `new_value` JSON COMMENT '新值',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_perm_audit_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限审计日志';

-- 9. 租户审计日志
DROP TABLE IF EXISTS `tenant_audit_log`;
CREATE TABLE `tenant_audit_log` (
    `id` VARCHAR(36) NOT NULL COMMENT '日志ID',
    `tenant_id` VARCHAR(36) NOT NULL COMMENT '租户ID',
    `actor_id` VARCHAR(36) NOT NULL COMMENT '超管ID',
    `action` VARCHAR(50) NOT NULL COMMENT '操作类型',
    `details` TEXT COMMENT '操作详情',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_tenant_audit_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户审计日志';


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 二、管道引擎（3 张）
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- 10. 管道表
DROP TABLE IF EXISTS `pipelines`;
CREATE TABLE `pipelines` (
    `id` VARCHAR(64) NOT NULL COMMENT '管道ID (UUID)',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `name` VARCHAR(255) NOT NULL COMMENT '管道名称',
    `description` TEXT COMMENT '管道描述',
    `type` VARCHAR(32) NOT NULL DEFAULT 'aggregation' COMMENT '管道类型：aggregation',
    `active_version` INT NOT NULL DEFAULT 1 COMMENT '当前活动版本号',
    `status` VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT '状态：draft/active/error',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_pipelines_tenant_id` (`tenant_id`),
    KEY `idx_pipelines_type` (`type`),
    KEY `idx_pipelines_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管道表';

-- 11. 管道版本表
DROP TABLE IF EXISTS `pipeline_versions`;
CREATE TABLE `pipeline_versions` (
    `id` VARCHAR(64) NOT NULL COMMENT '版本ID (UUID)',
    `pipeline_id` VARCHAR(64) NOT NULL COMMENT '关联管道ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID（冗余）',
    `version_number` INT NOT NULL COMMENT '版本号（per-pipeline 自增）',
    `change_log` TEXT COMMENT '变更说明',
    `config_snapshot` JSON NOT NULL COMMENT '管道配置完整快照 JSON',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_pipeline_version` (`pipeline_id`, `version_number`),
    KEY `idx_pv_pipeline_id` (`pipeline_id`),
    KEY `idx_pv_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管道版本表';

-- 12. 复合节点表
DROP TABLE IF EXISTS `compound_nodes`;
CREATE TABLE `compound_nodes` (
    `id` VARCHAR(64) NOT NULL COMMENT '复合节点ID (UUID)',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `owner_id` VARCHAR(64) NOT NULL COMMENT '创建者用户ID',
    `name` VARCHAR(255) NOT NULL COMMENT '复合节点名称',
    `description` TEXT COMMENT '描述',
    `config_snapshot` JSON NOT NULL COMMENT '配置 JSON（含 expanded_nodes/internal_edges/exposed_ports）',
    `is_shared` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否共享',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_cn_tenant_id` (`tenant_id`),
    KEY `idx_cn_owner_id` (`owner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='复合节点表';


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 三、知识库管理（4 张）
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- 13. 知识库表
DROP TABLE IF EXISTS `knowledge_bases`;
CREATE TABLE `knowledge_bases` (
    `id` VARCHAR(24) NOT NULL COMMENT '知识库ID（雪花ID）',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `name` VARCHAR(255) NOT NULL COMMENT '知识库名称',
    `description` TEXT COMMENT '描述',
    `vector_backend` VARCHAR(20) NOT NULL DEFAULT 'chroma' COMMENT '向量后端：chroma/es/milvus',
    `chunk_strategy` JSON COMMENT '分块策略配置',
    `embedding_config` JSON COMMENT 'Embedding 配置',
    `visibility` VARCHAR(20) NOT NULL DEFAULT 'public' COMMENT '可见性：public/role_scoped/private',
    `visible_roles` JSON COMMENT '可见角色列表（role_scoped 时生效）',
    `owner_id` VARCHAR(64) NOT NULL COMMENT '创建者ID',
    `status` VARCHAR(20) NOT NULL DEFAULT 'ready' COMMENT '状态：ready/rebuilding/indexing/error',
    `document_count` INT NOT NULL DEFAULT 0 COMMENT '文档数量',
    `chunk_count` INT NOT NULL DEFAULT 0 COMMENT '分块数量',
    `storage_size_bytes` BIGINT NOT NULL DEFAULT 0 COMMENT '存储大小（字节）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_kb_tenant_id` (`tenant_id`),
    KEY `idx_kb_status` (`status`),
    KEY `idx_kb_owner_id` (`owner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库表';

-- 14. 知识库文档表
DROP TABLE IF EXISTS `kb_documents`;
CREATE TABLE `kb_documents` (
    `id` VARCHAR(24) NOT NULL COMMENT '文档ID（雪花ID）',
    `kb_id` VARCHAR(24) NOT NULL COMMENT '知识库ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `filename` VARCHAR(500) NOT NULL COMMENT '文件名',
    `file_type` VARCHAR(20) NOT NULL COMMENT '文件类型：pdf/txt/markdown/html/epub',
    `file_size` INT NOT NULL COMMENT '文件大小（字节）',
    `page_count` INT DEFAULT NULL COMMENT '页数',
    `md5_hash` VARCHAR(32) NOT NULL COMMENT '文件 MD5',
    `parse_status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '解析状态：pending/parsing/parsed/error',
    `error_message` TEXT COMMENT '错误信息',
    `text_content` MEDIUMTEXT COMMENT '提取的文本内容',
    `metadata` JSON COMMENT '文档元数据',
    `access_level` VARCHAR(20) NOT NULL DEFAULT 'inherit' COMMENT '权限级别：inherit/restricted',
    `doc_acl` JSON COMMENT '文档 ACL 角色列表',
    `owner_id` VARCHAR(64) NOT NULL COMMENT '上传者ID',
    `chunk_count` INT NOT NULL DEFAULT 0 COMMENT '分块数量',
    `uploaded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_doc_kb_id` (`kb_id`),
    KEY `idx_doc_tenant_id` (`tenant_id`),
    KEY `idx_doc_md5` (`md5_hash`),
    KEY `idx_doc_parse_status` (`parse_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档表';

-- 15. 知识库分块表
DROP TABLE IF EXISTS `kb_chunks`;
CREATE TABLE `kb_chunks` (
    `id` VARCHAR(24) NOT NULL COMMENT '分块ID（雪花ID）',
    `kb_id` VARCHAR(24) NOT NULL COMMENT '知识库ID',
    `doc_id` VARCHAR(24) NOT NULL COMMENT '文档ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `chunk_index` INT NOT NULL COMMENT '分块序号',
    `content` MEDIUMTEXT NOT NULL COMMENT '分块内容',
    `token_count` INT DEFAULT NULL COMMENT 'Token 数量',
    `metadata` JSON COMMENT '分块元数据',
    `vector_id` VARCHAR(100) DEFAULT NULL COMMENT '向量存储中的 ID',
    PRIMARY KEY (`id`),
    KEY `idx_chunk_kb_id` (`kb_id`),
    KEY `idx_chunk_doc_id` (`doc_id`),
    KEY `idx_chunk_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库分块表';

-- 16. 知识库重建任务表
DROP TABLE IF EXISTS `kb_rebuild_tasks`;
CREATE TABLE `kb_rebuild_tasks` (
    `id` VARCHAR(24) NOT NULL COMMENT '任务ID',
    `kb_id` VARCHAR(24) NOT NULL COMMENT '知识库ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `trigger` VARCHAR(30) NOT NULL COMMENT '触发原因：chunk_change/embedding_change/backend_migration',
    `status` VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT '状态：running/completed/failed',
    `progress_pct` TINYINT NOT NULL DEFAULT 0 COMMENT '进度百分比',
    `progress_message` VARCHAR(500) DEFAULT NULL COMMENT '进度消息',
    `started_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `completed_at` DATETIME DEFAULT NULL,
    `error_message` TEXT,
    PRIMARY KEY (`id`),
    KEY `idx_rebuild_kb_id` (`kb_id`),
    KEY `idx_rebuild_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库重建任务表';


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 四、RAG 评估（11 张）
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- 17. 测试用例表
DROP TABLE IF EXISTS `test_cases`;
CREATE TABLE `test_cases` (
    `id` VARCHAR(64) NOT NULL COMMENT '用例ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `query` TEXT NOT NULL COMMENT '查询文本',
    `description` VARCHAR(500) DEFAULT NULL COMMENT '用例描述',
    `expected_knowledge_ids` JSON COMMENT '期望命中的知识片段 ID 列表',
    `expected_keywords` JSON COMMENT '期望关键词',
    `answer_points_summary` TEXT COMMENT '答案要点摘要',
    `difficulty_level` VARCHAR(20) DEFAULT 'medium' COMMENT '难度：easy/medium/hard',
    `professional_terms` JSON COMMENT '专业术语列表',
    `relevance_scores` JSON COMMENT '相关性分数 {"doc_id": 0.9, ...}',
    `relevant_domains` JSON COMMENT '期望激活的域列表（跨域指标 ground truth）',
    `expected_conflicts` JSON COMMENT '期望检测到的冲突',
    `source` VARCHAR(20) DEFAULT 'manual' COMMENT '来源：manual/import/draft',
    `source_draft_id` VARCHAR(64) DEFAULT NULL COMMENT '来源草稿ID',
    `version` INT NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_tc_tenant_id` (`tenant_id`),
    KEY `idx_tc_difficulty` (`difficulty_level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试用例表';

-- 18. 测试集表
DROP TABLE IF EXISTS `test_sets`;
CREATE TABLE `test_sets` (
    `id` VARCHAR(64) NOT NULL COMMENT '测试集ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `name` VARCHAR(255) NOT NULL COMMENT '测试集名称',
    `description` TEXT COMMENT '描述',
    `source_type` VARCHAR(20) DEFAULT 'manual' COMMENT '来源：manual/import/search_history',
    `case_ids` JSON COMMENT '关联的用例 ID 列表（有序）',
    `visibility` VARCHAR(20) DEFAULT 'public' COMMENT '可见性：public/role_scoped/private',
    `owner_id` VARCHAR(64) NOT NULL COMMENT '创建者ID',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_ts_tenant_id` (`tenant_id`),
    KEY `idx_ts_owner_id` (`owner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试集表';

-- 19. 测试集用例关联表
DROP TABLE IF EXISTS `test_set_cases`;
CREATE TABLE `test_set_cases` (
    `set_id` VARCHAR(64) NOT NULL COMMENT '测试集ID',
    `case_id` VARCHAR(64) NOT NULL COMMENT '用例ID',
    `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序序号',
    PRIMARY KEY (`set_id`, `case_id`),
    KEY `idx_tsc_case_id` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试集用例关联表';

-- 20. 测试运行表
DROP TABLE IF EXISTS `test_runs`;
CREATE TABLE `test_runs` (
    `id` VARCHAR(64) NOT NULL COMMENT '运行ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `name` VARCHAR(255) DEFAULT NULL COMMENT '运行名称',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态：pending/running/completed/failed/cancelled',
    `pipeline_id` VARCHAR(64) NOT NULL COMMENT '被评估的管道ID',
    `pipeline_version` INT NOT NULL COMMENT '管道版本',
    `test_set_ids` JSON COMMENT '测试集ID列表',
    `snapshot_id` VARCHAR(64) DEFAULT NULL COMMENT '知识库快照ID',
    `config_version_id` VARCHAR(64) DEFAULT NULL COMMENT '评估配置版本ID',
    `task_id` VARCHAR(64) DEFAULT NULL COMMENT '异步任务ID',
    `total_test_cases` INT NOT NULL DEFAULT 0,
    `passed_test_cases` INT NOT NULL DEFAULT 0,
    `overall_score` DECIMAL(5,4) DEFAULT NULL,
    `l1_metrics_json` JSON COMMENT 'L1 指标',
    `l2_metrics_json` JSON COMMENT 'L2 指标',
    `l3_metrics_json` JSON COMMENT 'L3 指标',
    `cross_domain_metrics_json` JSON COMMENT '跨域指标',
    `diagnosis_json` JSON COMMENT '诊断结果',
    `domain_results_json` JSON COMMENT '域结果详情',
    `started_at` DATETIME DEFAULT NULL,
    `completed_at` DATETIME DEFAULT NULL,
    `run_as_user_id` VARCHAR(64) DEFAULT NULL COMMENT '以哪个用户身份运行',
    `simulated_role_id` VARCHAR(64) DEFAULT NULL COMMENT '模拟的角色ID',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_tr_tenant_id` (`tenant_id`),
    KEY `idx_tr_pipeline_id` (`pipeline_id`),
    KEY `idx_tr_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试运行表';

-- 21. 测试运行结果表
DROP TABLE IF EXISTS `test_run_results`;
CREATE TABLE `test_run_results` (
    `id` VARCHAR(64) NOT NULL COMMENT '结果ID',
    `run_id` VARCHAR(64) NOT NULL COMMENT '运行ID',
    `test_case_id` VARCHAR(64) NOT NULL COMMENT '用例ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `query` TEXT NOT NULL,
    `retrieved_doc_ids` JSON,
    `retrieved_contexts` JSON,
    `expected_knowledge_ids` JSON,
    `actual_knowledge_ids` JSON,
    `precision` DECIMAL(5,4) DEFAULT NULL,
    `recall` DECIMAL(5,4) DEFAULT NULL,
    `f1` DECIMAL(5,4) DEFAULT NULL,
    `mrr` DECIMAL(5,4) DEFAULT NULL,
    `ndcg` DECIMAL(5,4) DEFAULT NULL,
    `actual_answer` TEXT,
    `domain_results_json` JSON,
    `l1_metrics_json` JSON,
    `l2_metrics_json` JSON,
    `diagnosis_json` JSON,
    `passed` TINYINT(1) DEFAULT NULL,
    `error_message` TEXT,
    `execution_time_ms` INT DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_rr_run_id` (`run_id`),
    KEY `idx_rr_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试运行结果表';

-- 22. 评估报告表
DROP TABLE IF EXISTS `eval_reports`;
CREATE TABLE `eval_reports` (
    `id` VARCHAR(64) NOT NULL COMMENT '报告ID',
    `run_id` VARCHAR(64) NOT NULL COMMENT '运行ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `overall_score` DECIMAL(5,4) DEFAULT NULL,
    `l1_score` DECIMAL(5,4) DEFAULT NULL,
    `l2_score` DECIMAL(5,4) DEFAULT NULL,
    `l3_score` DECIMAL(5,4) DEFAULT NULL,
    `cross_domain_score` DECIMAL(5,4) DEFAULT NULL,
    `metrics_json` JSON,
    `diagnosis_json` JSON,
    `bad_cases_json` JSON,
    `suggestions_json` JSON,
    `cross_domain_json` JSON,
    `markdown_content` MEDIUMTEXT,
    `status` VARCHAR(20) NOT NULL DEFAULT 'processing' COMMENT '状态：processing/completed/superseded',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_er_run_id` (`run_id`),
    KEY `idx_er_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评估报告表';

-- 23. 知识库快照表
DROP TABLE IF EXISTS `knowledge_snapshots`;
CREATE TABLE `knowledge_snapshots` (
    `id` VARCHAR(64) NOT NULL COMMENT '快照ID',
    `kb_id` VARCHAR(24) NOT NULL COMMENT '知识库ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `name` VARCHAR(255) DEFAULT NULL COMMENT '快照名称',
    `vector_store_path` VARCHAR(500) DEFAULT NULL,
    `vector_backend_type` VARCHAR(20) DEFAULT NULL,
    `document_count` INT DEFAULT 0,
    `chunk_count` INT DEFAULT 0,
    `doc_ids_json` JSON COMMENT '文档ID列表',
    `chunk_strategy_json` JSON,
    `embedding_config_json` JSON,
    `config_snapshot` JSON,
    `status` VARCHAR(20) DEFAULT 'active' COMMENT '状态：active/invalid/expired',
    `expires_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_ks_kb_id` (`kb_id`),
    KEY `idx_ks_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库快照表';

-- 24. 调优建议表
DROP TABLE IF EXISTS `tuning_suggestions`;
CREATE TABLE `tuning_suggestions` (
    `id` VARCHAR(64) NOT NULL COMMENT '建议ID',
    `run_id` VARCHAR(64) NOT NULL COMMENT '运行ID',
    `report_id` VARCHAR(64) DEFAULT NULL COMMENT '报告ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `category` VARCHAR(30) NOT NULL COMMENT '分类：retrieval/generation/system/permission',
    `severity` VARCHAR(20) NOT NULL COMMENT '严重性：critical/warning/info',
    `title` VARCHAR(255) NOT NULL,
    `description` TEXT,
    `current_value` VARCHAR(100) DEFAULT NULL,
    `suggested_value` VARCHAR(100) DEFAULT NULL,
    `expected_impact` TEXT,
    `source` VARCHAR(20) DEFAULT 'auto' COMMENT '来源：auto/manual',
    `priority` INT DEFAULT 5,
    `safe_range` VARCHAR(100) DEFAULT NULL,
    `conflict_with` JSON COMMENT '冲突的建议ID列表',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态：pending/adopted/rejected/ignored',
    `applied_config_version_id` VARCHAR(64) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_ts_run_id` (`run_id`),
    KEY `idx_ts_tenant_id` (`tenant_id`),
    KEY `idx_ts_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='调优建议表';

-- 25. 评估配置版本表
DROP TABLE IF EXISTS `eval_config_versions`;
CREATE TABLE `eval_config_versions` (
    `id` VARCHAR(64) NOT NULL COMMENT '配置版本ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `version_number` INT NOT NULL COMMENT '版本号',
    `version_label` VARCHAR(100) DEFAULT NULL,
    `config_snapshot` JSON NOT NULL COMMENT '配置快照',
    `change_summary` TEXT,
    `change_set_id` VARCHAR(64) DEFAULT NULL,
    `created_by` VARCHAR(64) NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_ecv_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评估配置版本表';

-- 26. 评估配置变更集表
DROP TABLE IF EXISTS `eval_config_change_sets`;
CREATE TABLE `eval_config_change_sets` (
    `id` VARCHAR(64) NOT NULL COMMENT '变更集ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `change_set_label` VARCHAR(255) DEFAULT NULL,
    `config_version_id` VARCHAR(64) NOT NULL,
    `previous_version_id` VARCHAR(64) DEFAULT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'committed' COMMENT '状态：committed/rolled_back',
    `rollback_reason` TEXT,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_eccs_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评估配置变更集表';

-- 27. 测试用例草稿表
DROP TABLE IF EXISTS `test_case_drafts`;
CREATE TABLE `test_case_drafts` (
    `id` VARCHAR(64) NOT NULL COMMENT '草稿ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `query` TEXT NOT NULL,
    `description` VARCHAR(500) DEFAULT NULL,
    `difficulty_level` VARCHAR(20) DEFAULT 'medium',
    `expected_knowledge_ids` JSON,
    `expected_keywords` JSON,
    `answer_points` TEXT,
    `professional_terms` JSON,
    `source_document_id` VARCHAR(64) DEFAULT NULL,
    `faithfulness_score` DECIMAL(5,4) DEFAULT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态：pending/approved/rejected/imported',
    `version` INT NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_draft_tenant_id` (`tenant_id`),
    KEY `idx_draft_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试用例草稿表';


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 五、搜索与发布（1 张）
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- 28. 发布端点表
DROP TABLE IF EXISTS `published_endpoints`;
CREATE TABLE `published_endpoints` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `endpoint_id` VARCHAR(64) NOT NULL COMMENT '端点ID (UUID)',
    `pipeline_id` VARCHAR(64) NOT NULL COMMENT '管道ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `url_path` VARCHAR(200) NOT NULL COMMENT 'URL 路径（全局唯一）',
    `bound_version` INT NOT NULL COMMENT '绑定的管道版本',
    `http_method` VARCHAR(10) NOT NULL DEFAULT 'POST',
    `auth_type` VARCHAR(20) NOT NULL DEFAULT 'jwt' COMMENT '认证类型：jwt/api_key/none',
    `rate_limit` INT NOT NULL DEFAULT 0 COMMENT 'QPS 限制（0=不限）',
    `enabled` TINYINT(1) NOT NULL DEFAULT 1,
    `allowed_params` JSON COMMENT '允许的 API 参数白名单',
    `response_format` VARCHAR(20) NOT NULL DEFAULT 'json' COMMENT '响应格式：json/sse/custom',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_pe_endpoint_id` (`endpoint_id`),
    UNIQUE KEY `uk_pe_url_path` (`url_path`),
    KEY `idx_pe_pipeline_id` (`pipeline_id`),
    KEY `idx_pe_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='发布端点表';


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 六、基础设施表（复用 backend/ 已有表，新增字段）
-- 注意：以下表假设 backend/ 已有基础结构，此处仅列出
-- rag-platform 需要的完整 DDL。实际部署时按需调整。
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- 29. 追踪 Span 表
DROP TABLE IF EXISTS `trace_spans`;
CREATE TABLE `trace_spans` (
    `id` VARCHAR(64) NOT NULL COMMENT 'Span ID',
    `trace_id` VARCHAR(64) NOT NULL COMMENT 'Trace ID',
    `parent_span_id` VARCHAR(64) DEFAULT NULL COMMENT '父 Span ID',
    `tenant_id` VARCHAR(64) DEFAULT NULL,
    `operation_name` VARCHAR(255) NOT NULL,
    `start_time` DATETIME(3) NOT NULL,
    `end_time` DATETIME(3) DEFAULT NULL,
    `duration_ms` INT DEFAULT NULL,
    `status` VARCHAR(20) DEFAULT 'ok',
    `error_message` TEXT,
    `attributes` JSON COMMENT 'Span 属性',
    `pipeline_id` VARCHAR(64) DEFAULT NULL COMMENT '管道ID',
    `pipeline_version` INT DEFAULT NULL COMMENT '管道版本',
    `domain_id` VARCHAR(64) DEFAULT NULL COMMENT '域ID',
    `degraded` TINYINT(1) DEFAULT 0 COMMENT '是否降级',
    `degradation_strategy` VARCHAR(30) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_ts_trace_id` (`trace_id`),
    KEY `idx_ts_tenant_id` (`tenant_id`),
    KEY `idx_ts_pipeline_id` (`pipeline_id`),
    KEY `idx_ts_start_time` (`start_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='追踪 Span 表';

-- 30. 配置表
DROP TABLE IF EXISTS `configs`;
CREATE TABLE `configs` (
    `id` VARCHAR(64) NOT NULL COMMENT '配置ID',
    `tenant_id` VARCHAR(64) DEFAULT NULL COMMENT '租户ID（NULL=全局配置）',
    `config_key` VARCHAR(255) NOT NULL COMMENT '配置键',
    `config_value` TEXT COMMENT '配置值',
    `value_type` VARCHAR(20) NOT NULL DEFAULT 'string' COMMENT '值类型：string/number/boolean/json',
    `description` VARCHAR(500) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_config_key_tenant` (`config_key`, `tenant_id`),
    KEY `idx_config_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置表';

-- 31. 提示词表
DROP TABLE IF EXISTS `prompts`;
CREATE TABLE `prompts` (
    `id` VARCHAR(64) NOT NULL COMMENT '提示词ID',
    `tenant_id` VARCHAR(64) DEFAULT NULL COMMENT '租户ID（NULL=全局提示词）',
    `prompt_key` VARCHAR(255) NOT NULL COMMENT '提示词键',
    `prompt_template` MEDIUMTEXT NOT NULL COMMENT '提示词模板',
    `version` INT NOT NULL DEFAULT 1,
    `description` VARCHAR(500) DEFAULT NULL,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_prompt_key_tenant` (`prompt_key`, `tenant_id`),
    KEY `idx_prompt_tenant_id` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示词表';


-- ============================================================
-- 完成：31 张表全部创建
-- ============================================================
