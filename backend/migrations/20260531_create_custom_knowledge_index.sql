-- 自定义知识 MySQL 辅助索引表
-- Neo4j CustomRule 节点是真相源，此表仅用于快速匹配（关键词/正则/向量）
-- 放置位置: backend/migrations/20260531_create_custom_knowledge_index.sql

CREATE TABLE IF NOT EXISTS custom_knowledge_index (
    rule_id         VARCHAR(32) PRIMARY KEY COMMENT '对应 Neo4j CustomRule.rule_id',
    keywords        JSON DEFAULT NULL COMMENT '精确匹配关键词列表，如 ["ADHD", "注意力缺陷"]',
    trigger_patterns JSON DEFAULT NULL COMMENT '正则触发模式列表，如 ["注意力.{0,5}(不集中|缺陷)"]',
    embedding       JSON DEFAULT NULL COMMENT '语义向量 (DashScope text-embedding-v4, 1536 维)',
    priority        INT NOT NULL DEFAULT 100 COMMENT '优先级（数值越大越优先）',
    enabled         TINYINT(1) NOT NULL DEFAULT 1 COMMENT '启用状态',
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_cki_priority (priority),
    INDEX idx_cki_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='自定义知识 MySQL 辅助索引（Neo4j CustomRule 是真相源）';
