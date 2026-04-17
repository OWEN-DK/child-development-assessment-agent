# 儿童发展评估系统 - MySQL + Redis 集成与核心模块重构设计方案

**版本**: 5.0 (MySQL + Redis 深度集成版)
**日期**: 2026-04-12
**状态**: 待执行
**描述**: 本方案在 2026-04-11 整合版基础上，新增 MySQL 数据库和 Redis 缓存加速层集成设计。MySQL 作为唯一数据源持久化所有结构化数据（配置、测试用例、草稿、测试集、文档记录、A/B 测试指标、LLM 调用日志），替代原有的 JSON 文件存储模式。Redis 作为全面加速层，承担分布式缓存、消息队列、分布式锁、会话存储四大角色。向量索引继续使用 Chroma，静态只读数据保持 JSON 文件。

---

## 1. 总体重构架构视图

**⚠️ 核心重构原则：项目未上线，无历史包袱。所有旧代码（如遗留配置、硬编码提示词、旧的流程控制、JSON 文件存储逻辑）不需要做迁移或向前兼容，重构时可直接丢弃或被新架构替换。**

### 1.1 系统架构图

```mermaid
graph TB
    subgraph 前端展示层
        ConfigUI[系统配置页 /system-config<br>动态Schema表单]
        PromptUI[提示词管理页 /prompts<br>版本管理/A/B配置/变量预览]
        LLM监控UI[LLM监控页 /monitor/llm<br>调用统计/效果分析/告警]
        TestUI[RAG 评估与测试页<br>导入/草稿审核/批量执行]
    end
    
    subgraph 核心配置与状态层
        ConfigManager[ConfigManager 配置管理器<br>MySQL持久化/Redis缓存/热更新/版本控制]
        PromptManager[PromptManager 提示词管理器<br>MySQL持久化/变量校验/A/B分发]
        EventBus[EventBus 事件总线<br>内存事件 + Redis Pub/Sub 跨实例传播]
        SessionMgr[SessionManager 会话管理器<br>Redis Hash 存储 LangGraph 中间状态]
    end

    subgraph 监控与分析层
        LLMMonitor[LLM调用监控器<br>MySQL持久化/Redis实时指标/统计收集/效果分析/告警]
    end

    subgraph 数据持久层
        MySQL[(MySQL 5.7<br>12张核心业务表<br>SQLAlchemy 2.0 ORM<br>唯一数据源)]
        Redis[(Redis 7.0<br>缓存/队列/锁/会话<br>全面加速层)]
        Chroma[(Chroma 向量库<br>Client/Server HTTP模式<br>独立微服务节点)]
        JSONFiles[JSON 文件存储<br>规则/静态数据]
    end

    subgraph 模型适配与路由层
        LLMFactory[LLMServiceFactory 工厂<br>9大独立业务场景模型]
        LangChainAdapter[LangChain 适配器]
        LlamaIndexAdapter[LlamaIndex 适配器]
        PipelineOrch[PipelineOrchestrator<br>YAML驱动查询流水线编排]
    end

    subgraph 业务逻辑层
        RAGNodes[RAG 评估与流水线<br>Redis缓存/Rewrite/Filter/Retrieve]
        TestManager[RagTestManager<br>MySQL并发批量测试/Redis分布式锁/多样化生成/评分同步]
        DistLock[分布式锁服务<br>Redis SET NX + TTL]
    end

    ConfigUI --> ConfigManager
    PromptUI --> PromptManager
    TestUI --> TestManager
    
    ConfigManager --> MySQL
    ConfigManager --> Redis
    LLMMonitor --> MySQL
    LLMMonitor --> Redis
    TestManager --> MySQL
    TestManager --> Redis
    SessionMgr --> Redis
    DistLock --> Redis
    
    ConfigManager --触发--> EventBus
    EventBus --内存事件--> LLMFactory
    EventBus --Redis Pub/Sub--> LLMFactory
    
    LLMFactory --> LangChainAdapter
    LLMFactory --> LlamaIndexAdapter
    
    PipelineOrch --> RAGNodes
    TestManager --> PipelineOrch
    
    RAGNodes --> Redis
    RAGNodes --> Chroma
```

### 1.2 核心数据流向图

```mermaid
sequenceDiagram
    participant User as 测试人员
    participant Frontend as 前端 (React)
    participant Config as ConfigManager
    participant Redis as Redis 缓存层
    participant MySQL as MySQL 数据库
    participant LLMFactory as LLM 工厂
    participant Pipeline as PipelineOrchestrator
    participant Backend as 后端核心 (FastAPI)

    User->>Frontend: 在系统配置页修改模型参数
    Frontend->>Config: PUT /api/v1/config (保存新配置)
    Config->>MySQL: INSERT INTO config_versions (创建新版本)
    Config->>MySQL: INSERT INTO config_audit_log (审计日志)
    Config->>Redis: DEL config:cache:* (清除配置缓存)
    Config->>Config: 更新内存缓存
    Config->>LLMFactory: 触发 ModelConfigChangedEvent
    LLMFactory->>LLMFactory: 从缓存中移除对应场景的旧实例

    User->>Frontend: 发起批量测试执行
    Frontend->>Backend: POST /rag/test/run/batch
    Backend->>Redis: SETNX test:lock:{run_id} (获取分布式锁)
    Backend->>MySQL: INSERT INTO test_runs (创建运行记录)
    Backend->>Redis: HSET test:session:{run_id} status=running (会话状态)
    Backend->>Pipeline: 并发触发流水线查询
    Pipeline->>Redis: GET rag:cache:{query_hash} (缓存检查)
    alt 缓存命中
        Redis-->>Pipeline: 返回缓存结果
    else 缓存未命中
        Pipeline->>LLMFactory: 请求获取场景最新 LLM 实例
        LLMFactory->>LLMFactory: 懒加载创建新模型实例
        LLMFactory-->>Pipeline: 返回新模型实例
        Pipeline->>MySQL: INSERT INTO test_run_results (批量写入结果)
        Pipeline->>Redis: SET rag:cache:{query_hash} result (回写缓存)
    end
    Backend->>MySQL: UPDATE test_runs SET status='completed'
    Backend->>Redis: DEL test:lock:{run_id} (释放分布式锁)
    Backend-->>Frontend: SSE 实时推送测试进度
```

### 1.3 数据存储策略

| 数据类型 | 存储方案 | 原因 |
|---------|---------|------|
| 配置版本与审计日志 | MySQL | 需要版本查询、对比、审计追踪 |
| 测试用例/草稿/测试集 | MySQL | 需要多维度查询、过滤、关联 |
| 测试运行与结果 | MySQL | 需要聚合统计、对比分析 |
| 文档记录与源文档 | MySQL | 需要状态查询、进度跟踪 |
| A/B 测试指标 | MySQL | 需要时间序列分析 |
| LLM 调用日志 | MySQL | 需要多维度统计、告警 |
| RAG 查询缓存 | Redis | 高速缓存，TTL 自动过期，防穿透/击穿/雪崩 |
| 配置缓存 | Redis | 加速配置读取，配置变更时自动失效 |
| 分布式锁 | Redis | 测试批量执行、配置热重载原子性更新 |
| 会话状态 | Redis | LangGraph 中间状态、测试运行进度、断点续传 |
| 实时指标 | Redis | LLM 调用实时统计、SSE 进度推送 |
| 消息队列 | Redis Pub/Sub | 配置变更事件、LLM 调用事件跨实例传播 |
| 向量索引 | Chroma | 专用向量检索。独立微服务部署(C/S HTTP模式)，避免多实例脑裂 |
| 提示词模板 | MySQL | 支持前端在线编辑、A/B测试权重动态调整及多实例数据一致性 |
| 业务规则 | JSON 文件 | 只读配置，无需复杂查询 |
| 静态数据 | JSON 文件 | 里程碑数据、词典等 |

### 1.4 MySQL + Redis 协作架构

**核心原则**：
- **MySQL 是唯一数据源**：所有持久化数据最终存储在 MySQL，Redis 数据可随时重建
- **Redis 是全面加速层**：读操作优先走 Redis，未命中再查 MySQL 并回写；写操作先写 MySQL 再异步/同步更新 Redis
- **一致性保证**：配置变更、缓存失效通过 Redis 事件传播，确保多实例数据一致性

**读写策略**：
```
读操作：Redis 缓存 → 命中返回 → 未命中 → MySQL 查询 → 回写 Redis → 返回
写操作：MySQL 写入 → 成功 → 异步/同步更新 Redis → 返回
失效操作：MySQL 更新/删除 → 删除 Redis 缓存 → 发布失效事件
```

**Redis 四大角色**：
1. **分布式缓存**：三级缓存架构（内存 LRU → Redis → 磁盘），RAG 查询缓存、配置缓存、会话缓存
2. **消息队列**：Redis Pub/Sub 替代内存 EventBus，支持配置变更、LLM 调用事件的跨实例传播
3. **分布式锁**：Redis SET NX + TTL 实现，用于测试批量执行、配置热重载原子性更新、防止重复导入
4. **会话存储**：Redis Hash 存储 LangGraph 中间状态、测试运行进度、用户上传任务状态，支持断点续传

---

## 2. MySQL 数据库设计

### 2.1 技术栈

- **数据库**: MySQL 5.7（自建服务器）
- **ORM 框架**: SQLAlchemy 2.0（异步模式）
- **迁移工具**: Alembic
- **异步驱动**: aiomysql
- **连接池**: SQLAlchemy 内置异步连接池（pool_size=10, max_overflow=20）

### 2.2 数据库表结构（12 张表）

#### 2.2.1 配置管理表

**`config_versions`（配置版本表）**
```sql
CREATE TABLE config_versions (
    id VARCHAR(64) PRIMARY KEY COMMENT '版本ID，如 v_20260412_120000',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    created_by VARCHAR(64) DEFAULT NULL COMMENT '创建者',
    description TEXT COMMENT '版本描述',
    config_snapshot JSON NOT NULL COMMENT '完整配置快照',
    parent_version_id VARCHAR(64) DEFAULT NULL COMMENT '父版本ID',
    is_factory_reset TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否为出厂重置',
    
    INDEX idx_created_at (created_at),
    INDEX idx_parent_version (parent_version_id),
    FOREIGN KEY (parent_version_id) REFERENCES config_versions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置版本快照表';
```

**`config_audit_log`（配置审计日志表）**
```sql
CREATE TABLE config_audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    action ENUM('UPDATE', 'ROLLBACK', 'RESET') NOT NULL COMMENT '操作类型',
    from_version VARCHAR(64) DEFAULT NULL COMMENT '原版本ID',
    to_version VARCHAR(64) DEFAULT NULL COMMENT '目标版本ID',
    user VARCHAR(64) DEFAULT NULL COMMENT '操作者',
    
    INDEX idx_timestamp (timestamp),
    INDEX idx_action (action),
    INDEX idx_from_version (from_version),
    INDEX idx_to_version (to_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置变更审计日志表';
```

#### 2.2.2 测试核心表

**`test_cases`（测试用例表）**
```sql
CREATE TABLE test_cases (
    id VARCHAR(64) PRIMARY KEY,
    query TEXT NOT NULL COMMENT '测试问题',
    age DECIMAL(4,1) NOT NULL COMMENT '适用年龄（月）',
    domain ENUM('gross_motor', 'fine_motor', 'language', 'cognitive', 'social_emotional', 'sensory_integration') NOT NULL COMMENT '领域',
    description TEXT COMMENT '用例描述',
    
    -- 查询优化字段（从 JSON 拆分）
    expected_knowledge_count INT NOT NULL DEFAULT 0 COMMENT '期望知识数量',
    answer_points_summary TEXT COMMENT '答题要点摘要（全文检索）',
    min_age_requirement DECIMAL(4,1) DEFAULT NULL COMMENT '最低年龄要求',
    max_age_requirement DECIMAL(4,1) DEFAULT NULL COMMENT '最高年龄要求',
    difficulty_level ENUM('easy', 'medium', 'hard') DEFAULT NULL COMMENT '难度等级',
    
    -- 保留 JSON（用于详情展示）
    expected_knowledge_ids JSON COMMENT '期望知识ID列表',
    expected_keywords JSON COMMENT '期望关键词列表',
    professional_terms JSON COMMENT '专业术语列表',
    relevance_scores JSON COMMENT '详细评分标准',
    
    source_document_id VARCHAR(64) DEFAULT NULL COMMENT '来源文档ID',
    version INT NOT NULL DEFAULT 1 COMMENT '版本号',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_domain (domain),
    INDEX idx_age (age),
    INDEX idx_difficulty (difficulty_level),
    INDEX idx_age_range (min_age_requirement, max_age_requirement),
    INDEX idx_source_doc (source_document_id),
    FULLTEXT idx_query (query) WITH PARSER ngram,
    FULLTEXT idx_answer_points (answer_points_summary) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试用例表';
```

**`test_case_drafts`（测试用例草稿表）**
```sql
CREATE TABLE test_case_drafts (
    id VARCHAR(64) PRIMARY KEY,
    source_document_id VARCHAR(64) NOT NULL COMMENT '来源文档ID',
    query TEXT NOT NULL COMMENT '测试问题',
    age DECIMAL(4,1) NOT NULL COMMENT '适用年龄（月）',
    domain ENUM('gross_motor', 'fine_motor', 'language', 'cognitive', 'social_emotional', 'sensory_integration') NOT NULL COMMENT '领域',
    description TEXT COMMENT '用例描述',
    
    expected_knowledge_ids JSON COMMENT '期望知识ID列表',
    expected_keywords JSON COMMENT '期望关键词列表',
    answer_points JSON COMMENT '答题要点',
    professional_terms JSON COMMENT '专业术语',
    age_requirement JSON COMMENT '年龄要求',
    generation_params JSON COMMENT '生成参数记录',
    
    status ENUM('draft', 'reviewed', 'rejected', 'imported') NOT NULL DEFAULT 'draft' COMMENT '审核状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_status (status),
    INDEX idx_source_doc (source_document_id),
    INDEX idx_domain_status (domain, status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试用例草稿表';
```

**`test_sets`（测试集表）**
```sql
CREATE TABLE test_sets (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL COMMENT '测试集名称',
    description TEXT COMMENT '测试集描述',
    source_type ENUM('manual', 'json_import', 'book_generated', 'mixed') NOT NULL COMMENT '来源类型',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_source_type (source_type),
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试集表';
```

**`test_set_cases`（测试集-用例关联表）**
```sql
CREATE TABLE test_set_cases (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    test_set_id VARCHAR(64) NOT NULL COMMENT '测试集ID',
    test_case_id VARCHAR(64) NOT NULL COMMENT '测试用例ID',
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '添加时间',
    
    UNIQUE KEY uk_set_case (test_set_id, test_case_id),
    INDEX idx_test_set (test_set_id),
    INDEX idx_test_case (test_case_id),
    
    FOREIGN KEY (test_set_id) REFERENCES test_sets(id) ON DELETE CASCADE,
    FOREIGN KEY (test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试集-用例关联表';
```

**`test_runs`（测试运行记录表）**
```sql
CREATE TABLE test_runs (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL COMMENT '运行名称',
    description TEXT COMMENT '运行描述',
    
    -- 聚合指标
    overall_precision DECIMAL(5,4) DEFAULT NULL COMMENT '总体精确率',
    overall_recall DECIMAL(5,4) DEFAULT NULL COMMENT '总体召回率',
    overall_f1 DECIMAL(5,4) DEFAULT NULL COMMENT '总体F1',
    overall_mrr DECIMAL(5,4) DEFAULT NULL COMMENT '平均倒数排名',
    overall_ndcg DECIMAL(5,4) DEFAULT NULL COMMENT 'NDCG指标',
    total_test_cases INT NOT NULL COMMENT '总用例数',
    passed_test_cases INT NOT NULL COMMENT '通过用例数',
    
    status ENUM('running', 'completed', 'failed', 'cancelled') NOT NULL COMMENT '运行状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME DEFAULT NULL COMMENT '完成时间',
    
    snapshot_id VARCHAR(64) DEFAULT NULL COMMENT '关联的知识库快照ID',
    config_version_id VARCHAR(64) DEFAULT NULL COMMENT '测试时使用的配置版本',
    config_snapshot JSON COMMENT '配置快照（用于复现）',
    previous_config_version_id VARCHAR(64) DEFAULT NULL COMMENT '对比的配置版本',
    
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_config_version (config_version_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试运行记录表';
```

**`test_run_results`（测试运行详细结果表）**
```sql
CREATE TABLE test_run_results (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL COMMENT '运行ID',
    test_case_id VARCHAR(64) NOT NULL COMMENT '测试用例ID',
    query TEXT NOT NULL COMMENT '测试问题（冗余字段，便于查询）',
    
    -- 核心指标（独立列，用于聚合统计）
    precision DECIMAL(5,4) DEFAULT NULL COMMENT '精确率',
    recall DECIMAL(5,4) DEFAULT NULL COMMENT '召回率',
    f1 DECIMAL(5,4) DEFAULT NULL COMMENT 'F1分数',
    passed TINYINT(1) DEFAULT NULL COMMENT '是否通过',
    matched_count INT NOT NULL DEFAULT 0 COMMENT '匹配的知识数量',
    expected_count INT NOT NULL DEFAULT 0 COMMENT '期望知识数量',
    actual_count INT NOT NULL DEFAULT 0 COMMENT '实际返回知识数量',
    
    -- 保留 JSON（用于详情展示）
    expected_knowledge_ids JSON COMMENT '期望知识ID列表',
    actual_knowledge_ids JSON COMMENT '实际知识ID列表',
    
    error_message TEXT COMMENT '错误信息',
    execution_time_ms INT DEFAULT NULL COMMENT '执行耗时（毫秒）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_run_case (run_id, test_case_id),
    INDEX idx_run_id (run_id),
    INDEX idx_test_case (test_case_id),
    INDEX idx_passed (passed),
    INDEX idx_matched_count (matched_count),
    INDEX idx_execution_time (execution_time_ms),
    
    FOREIGN KEY (run_id) REFERENCES test_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='测试运行详细结果表';
```

#### 2.2.3 文档管理表

**`source_documents`（源文档表）**
```sql
CREATE TABLE source_documents (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(500) NOT NULL COMMENT '文档标题',
    file_type ENUM('pdf', 'epub', 'txt') NOT NULL COMMENT '文件类型',
    file_path VARCHAR(1000) NOT NULL COMMENT '文件路径',
    file_hash VARCHAR(64) NOT NULL COMMENT '文件MD5/SHA256',
    content_summary TEXT COMMENT '内容摘要',
    
    -- 查询优化字段（从 JSON 拆分）
    page_count INT DEFAULT NULL COMMENT '页数',
    chapter_count INT DEFAULT NULL COMMENT '章节数量',
    quality_score DECIMAL(3,2) DEFAULT NULL COMMENT '质量评分',
    scan_page_ratio DECIMAL(3,2) DEFAULT NULL COMMENT '扫描版页面比例',
    
    -- 保留 JSON（用于详情展示）
    chapter_structure JSON COMMENT '完整章节结构',
    quality_report JSON COMMENT '详细质量报告',
    
    status ENUM('uploaded', 'parsing', 'ready', 'archived') NOT NULL COMMENT '文档状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_file_hash (file_hash),
    INDEX idx_status (status),
    INDEX idx_file_type (file_type),
    INDEX idx_quality_score (quality_score),
    INDEX idx_chapter_count (chapter_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='源文档元数据表';
```

**`document_records`（文档导入记录表）**
```sql
CREATE TABLE document_records (
    id VARCHAR(64) PRIMARY KEY,
    file_hash VARCHAR(64) NOT NULL COMMENT '文件哈希',
    file_name VARCHAR(500) NOT NULL COMMENT '文件名称',
    upload_date DATETIME NOT NULL COMMENT '上传日期',
    
    -- 查询优化字段（从 JSON 拆分）
    total_pages INT DEFAULT NULL COMMENT '总页数',
    indexed_chunks INT NOT NULL DEFAULT 0 COMMENT '已索引块数量',
    category VARCHAR(100) DEFAULT NULL COMMENT '文档分类',
    
    -- 保留 JSON（用于详情展示）
    ref_doc_ids JSON COMMENT '关联文档ID列表',
    metadata JSON COMMENT '完整元数据',
    
    status ENUM('pending', 'processing', 'indexed', 'failed') NOT NULL COMMENT '导入状态',
    progress INT NOT NULL DEFAULT 0 COMMENT '进度 0-100',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_file_hash (file_hash),
    INDEX idx_status (status),
    INDEX idx_upload_date (upload_date),
    INDEX idx_category (category),
    INDEX idx_indexed_chunks (indexed_chunks)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档导入记录表';
```

#### 2.2.4 监控分析表

**`ab_test_metrics`（A/B 测试指标表）**
```sql
CREATE TABLE ab_test_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    test_name VARCHAR(255) NOT NULL COMMENT '测试名称',
    variant_name VARCHAR(255) NOT NULL COMMENT '变体名称（A/B）',
    metric_value DECIMAL(10,4) NOT NULL COMMENT '指标值',
    metric_type VARCHAR(100) NOT NULL COMMENT '指标类型',
    recorded_at DATETIME NOT NULL COMMENT '记录时间',
    
    INDEX idx_test_name (test_name),
    INDEX idx_variant (variant_name),
    INDEX idx_recorded_at (recorded_at),
    INDEX idx_test_variant (test_name, variant_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='A/B测试指标表';
```

**`llm_call_logs`（LLM 调用日志表）**
```sql
CREATE TABLE llm_call_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id VARCHAR(64) NOT NULL COMMENT '请求唯一ID',
    prompt_key VARCHAR(255) DEFAULT NULL COMMENT '提示词标识',
    prompt_version VARCHAR(64) DEFAULT NULL COMMENT '提示词版本',
    scenario VARCHAR(100) DEFAULT NULL COMMENT '业务场景',
    model_name VARCHAR(255) NOT NULL COMMENT '使用的模型',
    
    input_tokens INT DEFAULT NULL COMMENT '输入Token数',
    output_tokens INT DEFAULT NULL COMMENT '输出Token数',
    total_tokens INT DEFAULT NULL COMMENT '总Token数',
    duration_ms INT DEFAULT NULL COMMENT '耗时（毫秒）',
    
    status ENUM('success', 'failed', 'timeout') NOT NULL COMMENT '调用状态',
    error_message TEXT COMMENT '错误信息',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_request_id (request_id),
    INDEX idx_prompt_key (prompt_key),
    INDEX idx_scenario (scenario),
    INDEX idx_model (model_name),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_duration (duration_ms)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='LLM调用日志表';
```

### 2.3 SQLAlchemy 模型设计

#### 2.3.1 数据库连接配置

```python
# backend/src/config/modules/database.py
from pydantic_settings import BaseSettings
from pydantic import Field

class DatabaseSettings(BaseSettings):
    """MySQL 数据库配置"""
    
    db_host: str = Field(default="localhost", validation_alias="MYSQL_HOST")
    db_port: int = Field(default=3306, validation_alias="MYSQL_PORT")
    db_user: str = Field(default="root", validation_alias="MYSQL_USER")
    db_password: str = Field(default="", validation_alias="MYSQL_PASSWORD")
    db_name: str = Field(default="child_development", validation_alias="MYSQL_DATABASE")
    
    pool_size: int = Field(default=10, validation_alias="MYSQL_POOL_SIZE")
    max_overflow: int = Field(default=20, validation_alias="MYSQL_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, validation_alias="MYSQL_POOL_TIMEOUT")
    pool_recycle: int = Field(default=3600, validation_alias="MYSQL_POOL_RECYCLE")
    
    @property
    def async_url(self) -> str:
        """异步数据库连接 URL"""
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )
    
    @property
    def sync_url(self) -> str:
        """同步数据库连接 URL（用于 Alembic 迁移）"""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )
```

#### 2.3.2 数据库引擎初始化

```python
# backend/src/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from src.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.async_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,  # 连接前检测有效性
)

# 创建会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass
```

#### 2.3.3 核心模型示例

```python
# backend/src/models/test_case.py
from sqlalchemy import String, Text, DECIMAL, Enum, Integer, JSON, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from datetime import datetime
from enum import Enum as PyEnum

class TestDomain(PyEnum):
    GROSS_MOTOR = "gross_motor"
    FINE_MOTOR = "fine_motor"
    LANGUAGE = "language"
    COGNITIVE = "cognitive"
    SOCIAL_EMOTIONAL = "social_emotional"
    SENSORY_INTEGRATION = "sensory_integration"

class DifficultyLevel(PyEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class TestCase(Base):
    __tablename__ = "test_cases"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[float] = mapped_column(DECIMAL(4, 1), nullable=False)
    domain: Mapped[TestDomain] = mapped_column(Enum(TestDomain), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # 查询优化字段
    expected_knowledge_count: Mapped[int] = mapped_column(Integer, default=0)
    answer_points_summary: Mapped[str | None] = mapped_column(Text)
    min_age_requirement: Mapped[float | None] = mapped_column(DECIMAL(4, 1))
    max_age_requirement: Mapped[float | None] = mapped_column(DECIMAL(4, 1))
    difficulty_level: Mapped[DifficultyLevel | None] = mapped_column(Enum(DifficultyLevel))
    
    # JSON 字段
    expected_knowledge_ids: Mapped[list | None] = mapped_column(JSON)
    expected_keywords: Mapped[list | None] = mapped_column(JSON)
    professional_terms: Mapped[list | None] = mapped_column(JSON)
    relevance_scores: Mapped[dict | None] = mapped_column(JSON)
    
    source_document_id: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    
    __table_args__ = (
        Index("idx_domain", "domain"),
        Index("idx_age", "age"),
        Index("idx_difficulty", "difficulty_level"),
        Index("idx_age_range", "min_age_requirement", "max_age_requirement"),
        Index("idx_source_doc", "source_document_id"),
    )
```

### 2.4 Alembic 迁移配置

```python
# backend/alembic.ini
[alembic]
script_location = backend/alembic
sqlalchemy.url = mysql+pymysql://root:password@localhost:3306/child_development?charset=utf8mb4

# backend/alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from src.core.database import Base
from src.config import settings

# 导入所有模型，确保 Base.metadata 包含所有表
import src.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
```

### 2.5 JSON 字段使用原则

| 场景 | 存储方式 | 原因 |
|------|---------|------|
| 需要过滤/排序/聚合的字段 | **独立列 + 索引** | 支持高效查询 |
| 需要全文检索的字段 | **独立列 + FULLTEXT 索引** | 支持语义搜索 |
| 仅用于展示/快照的字段 | **JSON 字段** | 保持灵活性，避免频繁 DDL |
| 动态扩展字段 | **JSON 字段** | 字段不固定 |
| 配置快照 | **JSON 字段** | 按版本 ID 整体读取，不查询内部 |
| 关键词/ID 列表 | **JSON + 独立计数字段** | 列表用于展示，计数用于过滤 |

---

## 3. Redis 缓存加速层设计

### 3.1 技术栈

- **数据库**: Redis 7.0+（自建服务器）
- **Python 客户端**: redis.asyncio（异步模式）
- **连接池**: redis.asyncio.ConnectionPool（max_connections=20）
- **序列化**: JSON（配置、缓存）、MessagePack（会话状态，可选）
- **键命名规范**: `child-dev:{module}:{key}` 统一前缀，避免键冲突

### 3.2 Redis 配置模块

```python
# backend/src/config/modules/redis.py
from pydantic_settings import BaseSettings
from pydantic import Field

class RedisSettings(BaseSettings):
    """Redis 缓存加速层配置"""
    
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    redis_password: str = Field(default="", validation_alias="REDIS_PASSWORD")
    
    # 连接池配置
    redis_max_connections: int = Field(default=20, validation_alias="REDIS_MAX_CONNECTIONS")
    redis_socket_timeout: int = Field(default=5, validation_alias="REDIS_SOCKET_TIMEOUT")
    redis_socket_connect_timeout: int = Field(default=3, validation_alias="REDIS_SOCKET_CONNECT_TIMEOUT")
    
    # 缓存配置
    cache_enabled: bool = Field(default=True, validation_alias="REDIS_CACHE_ENABLED")
    cache_default_ttl: int = Field(default=3600, validation_alias="REDIS_CACHE_DEFAULT_TTL")  # 1小时
    cache_max_memory: str = Field(default="256mb", validation_alias="REDIS_CACHE_MAX_MEMORY")
    
    # 分布式锁配置
    lock_timeout: int = Field(default=30, validation_alias="REDIS_LOCK_TIMEOUT")  # 30秒
    lock_retry_interval: float = Field(default=0.1, validation_alias="REDIS_LOCK_RETRY_INTERVAL")
    
    # 会话存储配置
    session_ttl: int = Field(default=86400, validation_alias="REDIS_SESSION_TTL")  # 24小时
    
    # 消息队列配置
    pubsub_enabled: bool = Field(default=True, validation_alias="REDIS_PUBSUB_ENABLED")
    pubsub_channels: list[str] = Field(
        default=["config:changed", "llm:call", "test:progress"],
        validation_alias="REDIS_PUBSUB_CHANNELS"
    )
```

### 3.3 Redis 客户端初始化

```python
# backend/src/core/redis_client.py
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from src.config import settings
from src.utils.logger import logger

class RedisClient:
    """Redis 异步客户端单例"""
    
    _instance: redis.Redis | None = None
    _pool: ConnectionPool | None = None
    
    @classmethod
    def get_client(cls) -> redis.Redis:
        """获取 Redis 客户端实例（懒加载）"""
        if cls._instance is None:
            cls._pool = ConnectionPool.from_url(
                settings.redis_url,
                password=settings.redis_password or None,
                max_connections=settings.redis_max_connections,
                socket_timeout=settings.redis_socket_timeout,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                decode_responses=True,
            )
            cls._instance = redis.Redis(connection_pool=cls._pool)
            logger.info("Redis 客户端已初始化")
        return cls._instance
    
    @classmethod
    async def close(cls):
        """关闭 Redis 连接池"""
        if cls._pool:
            await cls._pool.disconnect()
            logger.info("Redis 连接池已关闭")
```

### 3.4 分布式缓存层（角色一）

**架构**：三级缓存（内存 LRU → Redis → 磁盘 JSON）

**现有 CacheService 改造**：
```python
# backend/src/service/cache_service.py（启用现有 Redis 代码）

class CacheService(ICacheService):
    """生产级统一缓存服务，支持多级缓存、细粒度失效、穿透/击穿/雪崩防护"""
    
    def __init__(self):
        self.enabled = settings.cache_enabled
        # 内存缓存（热点数据）
        self.memory_cache = LRU(maxsize=settings.rag_config["cache"]["max_size"] or 10000)
        # Redis缓存（分布式全量数据）- 启用现有代码
        self.redis_client = self._init_redis_client()
        # 磁盘持久化（降级方案）
        self.disk_cache_enabled = getattr(settings, 'rag_cache_disk_enabled', True)
        self.disk_cache_dir = self._init_disk_cache_dir()
        self.disk_cache = self._load_disk_cache()
        # 互斥锁（防击穿）
        self.locks = {}
        # 文档哈希到缓存键映射（细粒度失效）
        self.doc_hash_map = defaultdict(set)
        # 缓存标签映射
        self.tag_map = defaultdict(set)
        # 默认TTL
        self.default_ttl = settings.rag_config["cache"]["ttl_seconds"]
    
    def _init_redis_client(self):
        """初始化 Redis 客户端连接池（启用现有代码）"""
        redis_url = getattr(settings, "redis_url", None)
        if redis_url:
            try:
                import redis.asyncio as redis
                pool = redis.ConnectionPool.from_url(
                    redis_url, 
                    decode_responses=True, 
                    max_connections=10
                )
                client = redis.Redis(connection_pool=pool)
                logger.info(f"Redis client initialized with URL: {redis_url}")
                return client
            except ImportError:
                logger.warning("redis package not installed, Redis cache disabled.")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize Redis client: {e}")
                return None
        return None
    
    async def get(self, key: str, default: Any = None) -> Any:
        """获取缓存，优先内存，再 Redis，最后磁盘"""
        if not self.enabled:
            return default
            
        # 1. 查内存
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # 2. 查 Redis
        if self.redis_client:
            try:
                redis_value = await self.redis_client.get(key)
                if redis_value:
                    value = json.loads(redis_value)
                    self.memory_cache[key] = value  # 回写内存
                    return value
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        # 3. 查磁盘
        if self.disk_cache_enabled and key in self.disk_cache:
            value = self.disk_cache[key]
            self.memory_cache[key] = value
            return value
        
        return default
    
    async def set(self, key: str, value: Any, expire: int = None, ...):
        """写入缓存，同步到 Redis"""
        if not self.enabled:
            return
            
        expire = expire or self.default_ttl
        # 写入内存
        self.memory_cache.set(key, value, expire=expire)
        # 写入磁盘
        if self.disk_cache_enabled:
            self.disk_cache[key] = value
        # 写入 Redis
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key, 
                    expire, 
                    json.dumps(value, ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
```

**缓存键设计规范**：
```
rag:cache:{query_hash}              # RAG 查询缓存
config:cache:{config_key}           # 配置缓存
test:session:{run_id}               # 测试会话状态
llm:stats:{scenario}:{date}         # LLM 调用实时统计
lock:test:{run_id}                  # 测试执行分布式锁
lock:config:reload                  # 配置热重载分布式锁
```

### 3.5 消息队列/事件总线（角色二）

**架构**：内存 EventBus + Redis Pub/Sub 跨实例传播

```python
# backend/src/core/event_bus.py（增强版）

import redis.asyncio as redis
from src.core.redis_client import RedisClient
from src.config import settings

import weakref
import uuid

class EventBus:
    """事件总线，支持内存事件 + Redis Pub/Sub 跨实例传播"""
    _instance_id: str = str(uuid.uuid4())
    _subscribers: Dict[Type[BaseEvent], List[Any]] = defaultdict(list)
    _redis_subscriber: redis.client.PubSub | None = None
    
    @classmethod
    def subscribe(cls, event_type: Type[BaseEvent], callback: Callable[[Any], None]) -> None:
        """订阅事件（内存，建议使用 weakref 或显式 unsubscribe 防止内存泄漏）"""
        cls._subscribers[event_type].append(callback)
        
    @classmethod
    def unsubscribe(cls, event_type: Type[BaseEvent], callback: Callable[[Any], None]) -> None:
        """显式取消订阅，防止 Controller 等短生命周期对象内存泄漏"""
        if callback in cls._subscribers[event_type]:
            cls._subscribers[event_type].remove(callback)
    
    @classmethod
    def publish(cls, event: BaseEvent) -> None:
        """发布事件（内存 + Redis Pub/Sub）"""
        # 1. 内存事件传播
        event_type = type(event)
        for callback in cls._subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback failed: {e}")
        
        # 2. Redis Pub/Sub 跨实例传播
        if settings.pubsub_enabled:
            try:
                redis_client = RedisClient.get_client()
                payload = {
                    "publisher_id": cls._instance_id,
                    "event_data": event.__dict__
                }
                await redis_client.publish(
                    f"child-dev:events:{event_type.__name__}",
                    json.dumps(payload, ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"Redis Pub/Sub publish failed: {e}")
    
    @classmethod
    async def start_redis_subscriber(cls):
        """启动 Redis Pub/Sub 订阅器（接收其他实例的事件）"""
        if not settings.pubsub_enabled:
            return
        
        redis_client = RedisClient.get_client()
        cls._redis_subscriber = redis_client.pubsub()
        await cls._redis_subscriber.subscribe("child-dev:events:*")
        
        async for message in cls._redis_subscriber.listen():
            if message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    # 过滤自身发送的消息，防止回声死循环
                    if payload.get("publisher_id") == cls._instance_id:
                        continue
                    event_data = payload.get("event_data", {})
                    # 根据事件类型分发到内存回调
                    # ...
                except Exception as e:
                    logger.error(f"Redis Pub/Sub message processing failed: {e}")
```

### 3.6 分布式锁服务（角色三）

```python
# backend/src/core/distributed_lock.py

import asyncio
from src.core.redis_client import RedisClient
from src.config import settings
from src.utils.logger import logger

class DistributedLock:
    """基于 Redis 的分布式锁服务"""
    
    @classmethod
    async def _watchdog(cls, lock, timeout: int, stop_event: asyncio.Event):
        """锁自动续期看门狗"""
        renewal_interval = timeout / 3.0
        while not stop_event.is_set():
            await asyncio.sleep(renewal_interval)
            if not stop_event.is_set():
                try:
                    await lock.extend(timeout)
                except Exception as e:
                    logger.warning(f"分布式锁续期失败: {e}")
                    break

    @classmethod
    async def execute_with_lock(cls, lock_name: str, func, timeout: int = None, *args, **kwargs):
        """使用 redis-py 内置的健壮分布式锁包装器，并带有看门狗续期机制"""
        timeout = timeout or settings.lock_timeout
        redis_client = RedisClient.get_client()
        
        # 依赖内置锁机制，通过唯一 Token 和 Lua 脚本保证释放的安全性，避免误删他人的锁
        lock = redis_client.lock(f"child-dev:lock:{lock_name}", timeout=timeout, blocking_timeout=5)
        try:
            async with lock:
                stop_event = asyncio.Event()
                watchdog_task = asyncio.create_task(cls._watchdog(lock, timeout, stop_event))
                try:
                    return await func(*args, **kwargs)
                finally:
                    stop_event.set()
                    watchdog_task.cancel()
        except redis.exceptions.LockError:
            raise RuntimeError(f"无法获取分布式锁: {lock_name}")
```

**使用场景**：
- 测试批量执行：`lock:test:{run_id}` 防止重复执行
- 配置热重载：`lock:config:reload` 保证原子性更新
- 文档导入：`lock:import:{file_hash}` 防止重复导入

### 3.7 会话存储（角色四）

```python
# backend/src/core/session_manager.py

import json
from src.core.redis_client import RedisClient
from src.config import settings
from src.utils.logger import logger

class SessionManager:
    """基于 Redis 的会话管理器"""
    
    @classmethod
    async def save_session(cls, session_id: str, data: dict, ttl: int = None) -> None:
        """保存会话到 Redis Hash"""
        ttl = ttl or settings.session_ttl
        redis_client = RedisClient.get_client()
        
        # HSET session:{session_id} field value
        pipe = redis_client.pipeline()
        for key, value in data.items():
            pipe.hset(
                f"child-dev:session:{session_id}",
                key,
                json.dumps(value, ensure_ascii=False)
            )
        pipe.expire(f"child-dev:session:{session_id}", ttl)
        await pipe.execute()
    
    @classmethod
    async def load_session(cls, session_id: str) -> dict | None:
        """从 Redis Hash 加载会话"""
        redis_client = RedisClient.get_client()
        session_data = await redis_client.hgetall(f"child-dev:session:{session_id}")
        
        if not session_data:
            return None
        
        return {k: json.loads(v) for k, v in session_data.items()}
    
    @classmethod
    async def delete_session(cls, session_id: str) -> None:
        """删除会话"""
        redis_client = RedisClient.get_client()
        await redis_client.delete(f"child-dev:session:{session_id}")
```

**使用场景**：
- LangGraph 中间状态：`session:agent:{run_id}` 存储 AgentState
- 测试运行进度：`session:test:{run_id}` 存储执行进度、成功/失败数量
- 用户上传任务：`session:upload:{task_id}` 存储导入进度、分块状态

---

## 4. 配置系统重构 (Configuration System)

### 4.1 三层配置目录架构

摒弃原有的 700 行庞大 `settings.py`，采用三层目录架构，配置持久化从 JSON 文件迁移到 MySQL：

```text
backend/src/config/
├── core/                  # 基础设施：manager.py(版本与热更新), repository.py(MySQL), events.py
├── modules/               # 配置模块（支持热更新与环境覆盖）
│   ├── app.py             # 基础应用配置
│   ├── logging.py         # 日志配置
│   ├── paths.py           # 路径配置
│   ├── database.py        # MySQL 数据库配置（新增）
│   ├── redis.py           # Redis 缓存加速层配置（新增）
│   ├── models/            # 模型配置组 (llm.py, embedding.py, ml_scoring.py)
│   └── rag/               # RAG知识库组 (core.py, retrieval.py, chunking.py, vector_store.py, pipeline.py, pageindex.py)
├── rules/                 # 业务规则加载 (rules.py, rules.json)
└── __init__.py            # 多重继承聚合入口，对外导出单例 `settings`
```

### 4.2 配置持久化迁移到 MySQL

**原方案（JSON 文件）**：
```
app_data/data/configs/
├── active_version.json
├── audit_log.jsonl
└── versions/
    └── v_20260412_120000.json
```

**新方案（MySQL）**：
```
MySQL 数据库
├── config_versions 表（配置版本快照）
└── config_audit_log 表（审计日志）
```

**ConfigRepository 改造**：
```python
# backend/src/config/core/repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.config_version import ConfigVersion
from src.models.config_audit_log import ConfigAuditLog

class MySQLConfigRepository:
    """基于 MySQL 的配置仓库 (遵循 UoW 模式，事务由外层统一管理)"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save_version(self, version: ConfigVersion) -> None:
        self.session.add(version)
        await self.session.flush()
    
    async def get_latest_version(self) -> ConfigVersion | None:
        result = await self.session.execute(
            select(ConfigVersion)
            .order_by(ConfigVersion.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_version_by_id(self, version_id: str) -> ConfigVersion | None:
        return await self.session.get(ConfigVersion, version_id)
    
    async def list_versions(self, limit: int = 50) -> list[ConfigVersion]:
        result = await self.session.execute(
            select(ConfigVersion)
            .order_by(ConfigVersion.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def log_action(
        self,
        action: str,
        from_version: str | None,
        to_version: str | None,
        user: str | None = None,
    ) -> None:
        log = ConfigAuditLog(
            action=action,
            from_version=from_version,
            to_version=to_version,
            user=user,
        )
        self.session.add(log)
        await self.session.flush()
```

### 4.3 热更新与原子性更新

1. **监听机制**：`watchdog` 监听 `.env`、`.yaml` 和配置目录，触发 `reload_settings()`。
2. **原子性保证**：使用 Redis 分布式锁（`lock:config:reload`）+ 读写锁机制。重载失败时，保留原有配置实例，避免系统崩溃。
3. **事件驱动**：派发 `ConfigChangedEvent` 和 `ModelConfigChangedEvent` 供订阅方动态调整运行时资源，通过 Redis Pub/Sub 跨实例传播。
4. **MySQL 事务保证**：配置版本创建和审计日志写入在同一事务中，确保数据一致性。
5. **Redis 缓存失效**：配置更新后自动清除 Redis 中的配置缓存（`DEL config:cache:*`），确保下次读取获取最新配置。

### 4.4 统一的独立前端配置页

- 新增路由 `/system-config`，替代原评估页中的右侧边栏 `ConfigTuningPanel`。
- **Schema 驱动表单**：新增 `GET /api/v1/config/schema` 接口，返回所有配置模块的标准 JSON Schema 定义，前端无需硬编码配置项定义，使用 `ConfigFieldRenderer` 动态渲染 Switch、InputNumber、Slider 等 Ant Design 控件。
- 提供"恢复默认"、"应用到所有场景"、"配置版本对比"及批量导出/导入功能。
- **安全校验**：配置保存接口 `PUT /api/v1/config` 增加严格的字段校验，禁止修改系统级只读配置，防止恶意操作。

---

## 5. 全模型支持与独立场景配置 (Unified LLM Support)

### 5.1 9大独立业务场景

模型配置从全局统一更改为**按场景独立配置**。每个场景拥有独立的 `provider`, `model_name`, `temperature`, `max_tokens`, `retry_count`, `timeout`, `api_key`, `base_url`。

| 场景标识 | 用途说明 | 使用框架适配器 |
|---------|----------|--------------|
| `report_generation` | 生成最终用户可读的评估报告 | LlamaIndex |
| `assessment` | 儿童发展状态评估，对标里程碑 | LlamaIndex |
| `validation` | 数据格式校验和智能补全 | LlamaIndex |
| `query_rewrite` | RAG查询语句优化改写 | LangChain |
| `metadata_extraction` | 文档元数据自动提取 | LlamaIndex |
| `vl_parsing` | 扫描版PDF/图片内容识别 | LlamaIndex (IVLMService) |
| `query_classification` | 查询路由分类 | LlamaIndex |
| `ml_scoring` | 大模型评估打分 | LlamaIndex |
| `synonym_expand` | 查询同义词扩展 | LangChain |
| `memory_extraction` | 历史上下文偏好特征提取 | LlamaIndex |

### 5.2 抽象层与工厂注入模式 (DI Container)

1. **统一接口**：定义与框架无关的 `ILLMService`（包含 `agenerate`, `astream`, `dispose`）。
2. **统一消息结构**：在 `backend/src/core/llm/base.py` 中定义标准化的 `Message` 数据结构，屏蔽 LangChain 与 LlamaIndex 底层框架的消息类型差异（`BaseMessage` vs `ChatMessage`），适配器内部负责双向转换。
3. **双框架适配**：实现 `LangChainTongyiLLMService`、`LlamaIndexOpenAILLMService` 等。
4. **工厂注入**：为解决 Injector 单例与热更新的冲突，DI 容器注入的是**工厂函数**（`callable`）而非实例。
   - `LLMServiceFactory.get_for_scene("assessment", "llamaindex")` 每次调用返回最新配置的实例。
5. **资源释放（优雅降级）**：当接收到 `ModelConfigChangedEvent` 时，从工厂缓存中移除对应场景的旧实例引用。为防止 Asyncio 环境下强行依赖 GC 导致 `Unclosed client session` 警告与 Socket 句柄泄漏，应实现延迟显式释放机制：将旧实例移入后台，启动清理协程 `asyncio.create_task(delayed_dispose(old_instance))`，等待 60 秒（确保进行中的旧请求已返回）后显式调用 `await old_instance.dispose()` 释放连接池。
6. **敏感信息安全策略**：所有场景配置中的 `api_key` 字段在持久化存储时使用 AES 对称加密，接口返回时强制脱敏（仅显示前4位与后4位，中间用 `*` 填充，如 `sk-****1234`），防止密钥泄露。

---

## 6. 提示词管理系统 (Prompt Management System)

### 6.1 核心机制

- 废弃硬编码提示词，**全面迁移至 MySQL 数据库**（新增 `prompts` 与 `prompt_versions` 表），以支持多实例架构下的前端在线编辑和动态路由一致性。
- **数据模型**：每个提示词包含key、name、description、version、tags、template、variables、ab_test配置、fallback字段。
- **支持功能**：
  - 完整版本控制与历史版本一键回滚
  - 动态变量校验（`{{variable}}` 占位符解析与类型校验）
  - 内置A/B测试流量分发，支持多版本按权重自动路由
  - MySQL 统一存储配合 Redis 缓存，保障多实例节点间的数据一致性
- **加载机制**：业务代码通过 `PromptManager.get_prompt("PROMPT_KEY", **kwargs)` 统一加载，结合 Redis 缓存加速，内置降级策略（数据库异常时回退到内存默认值）。

### 6.2 前端管理页 (`/prompts`)

- 独立一级菜单。
- 列表页：按业务域、标签筛选提示词，展示基本信息与调用量统计入口
- 编辑器：
  - 支持语法高亮的模板编辑器
  - 变量自动识别与实时校验提示
  - 实时预览面板：输入测试变量，直接查看渲染后的完整提示词
- 详情页：
  - 版本历史对比，支持一键回滚到指定版本
  - A/B测试配置面板，设置不同版本的流量权重
  - 快速跳转到对应的LLM监控统计页面

---

## 7. LLM调用监控系统 (LLM Monitoring System)

### 7.1 核心机制

- 完全独立于提示词管理系统，通过EventBus订阅所有LLM调用事件
- **事件收集**：每次LLM调用自动记录提示词版本、输入输出、耗时、Token消耗、错误信息、请求ID等上下文
- **持久化**：调用日志写入 MySQL `llm_call_logs` 表，支持多维度查询
- **统计分析**：
  - 多维度统计：调用次数、成功率、平均耗时、Token消耗总量与人均消耗
  - 效果分析：A/B测试不同版本的成功率、返回结果质量对比
  - 错误分析：错误类型分布、异常率告警阈值配置
- **可观测性**：内置Prometheus指标输出，支持对接现有监控大盘

### 7.2 前端监控页 (`/monitor/llm`)

- 独立一级菜单。
- 总览仪表盘：全系统LLM调用统计、消耗趋势、错误率概览
- 提示词维度分析：单个提示词的调用统计、不同A/B版本的效果对比
- 场景维度分析：按业务场景（评估/报告生成/查询重写等）统计消耗与质量
- 告警配置：异常率升高、耗时突增、Token消耗超阈值等场景的告警规则配置

---

## 8. RAG 查询流水线编排 (Query Pipeline Orchestration)

### 8.1 YAML 声明式流水线

消除 `retrieval_service.py` 中 600 行的硬编码，改用 `query_pipeline.yaml` 驱动。

```yaml
pipelines:
  simple:  # 事实性/定义性问题，跳过大模型重写
    - name: prompt_injection_guard  # 强制提示词注入检测，拦截恶意输入
    - name: cache_check
    - name: hybrid_retrieval
      params: { bm25_top_k: 10, vector_top_k: 10 }
    - name: rerank
    - name: dedup
    - name: convert_to_knowledge
  complex: # 比较分析/多步骤问题，启用全量增强
    - name: prompt_injection_guard  # 强制提示词注入检测，拦截恶意输入
    - name: cache_check
    - name: query_rewrite
    - name: synonym_expand
    - name: age_filter
    - name: hybrid_retrieval
    - name: rerank
    ...
```

### 8.2 编排器实现 (`PipelineOrchestrator`)

- 基于 `QueryRouter` 对用户查询进行分类（Simple vs Complex）。
- 动态加载 YAML 对应的 `PipelineStep`。
- **失败降级策略**：若某一步骤（如 `query_rewrite` 超时）失败，根据 `RAG_PIPELINE_FAILURE_STRATEGY` 选择 fail_fast、continue_with_warning 或 fallback_to_default（跳过已成功的步骤）。
- **可观测性**：全链路 Prometheus 埋点（`STEP_DURATION`, `STEP_TOTAL`）与详细日志上下文。
- **Bug修复**：整合时修复原设计中的 `synonyms` 变量未定义、`pageindex_wrapper.py` 文件句柄泄漏问题。

---

## 9. RAG 测试框架全链路优化 (RAG Test Framework)

### 9.1 数据模型扩展与导入

- **数据模型**：引入 `SourceDocument`（来源书籍）、`TestCaseDraft`（草稿）、`TestSet`（测试集），重构 `TestCase`，增加领域（domain）、版本号、答题要点等。所有数据持久化到 MySQL。
- **书籍导入工作台**：
  - 上传书籍自动解析并生成 `QualityReport`（评估扫描件比例和完整性）。
  - **多样化生成**：支持自定义生成数量（10-1000）、目标领域和年龄。基于 12 种考核维度和 80+ 角度模板生成高覆盖率、互不相同的草稿。优先选用轻量模型（如 qwen3-omni-flash 等），大幅降低生成费用。
  - **鲁棒性 JSON 解析**：大模型生成复杂嵌套 JSON 时极易截断或丢失尾部括号。在入库前必须强制接入 `json-repair` 进行解析兜底，并在 Pydantic 校验阶段处理单字符串被错误解析为列表的问题，防止 MySQL 批量事务因 JSON 错误而回滚。
  - **去重与重试**：基于相似度的 `DraftDeduplicator`，以及带指数退避的 LLM 重试机制。
- **审核流**：草稿列表支持人工修改、批量通过或拒绝，确认后通过 MySQL 事务原子写入转换为正式 `TestCase` 并加入 `TestSet`。

### 9.2 并发批量执行与进度反馈

- **并发控制**：新增 `POST /rag/test/run/batch`，使用 `asyncio.Semaphore` 控制并发数（1-10）。
- **实时进度推送**：新增 `GET /rag/test/run/{run_id}/progress` SSE 接口，后端主动推送执行进度，替代原有的前端轮询机制，大幅降低服务器压力，提升实时性。`ExecutionProgress` 组件订阅 SSE 事件，实时展示进度条、成功/失败数量及失败原因。
- **执行安全**：支持通过 `run_id/cancel` 取消正在执行的任务。
- **MySQL 批量写入优化**：测试运行结果使用 `INSERT ... ON DUPLICATE KEY UPDATE` 批量写入，减少数据库交互次数。

### 9.3 评分同步机制

- **问题解决**：过去删除报告（TestRun）后，系统的聚合评分不会更新。
- **优化逻辑**：拦截 `DELETE /runs/{run_id}` API，通过 MySQL 外键级联删除 `test_run_results` 后，将 `recalculate_aggregate_scores()` 放入 FastAPI `BackgroundTasks` 中异步全量重新计算（由于单次计算开销小，暂采用全量计算，预留缓存增量计算空间），接口立即返回成功响应，异步计算完成后通过事件通知前端更新大盘指标，避免长耗时阻塞用户操作。

---

## 10. MySQL 连接池优化与性能调优

### 10.1 连接池高级配置

**核心配置参数**：
```python
# backend/src/core/database.py
engine = create_async_engine(
    settings.async_url,
    echo=settings.debug,
    pool_size=10,                    # 基础连接数（根据并发负载调整）
    max_overflow=20,                 # 峰值溢出连接（突发流量缓冲）
    pool_timeout=30,                 # 获取连接超时（秒）
    pool_recycle=1800,               # 连接回收时间（30分钟，避免 MySQL wait_timeout）
    pool_pre_ping=True,              # 连接前检测有效性（防止 stale connection）
    pool_use_lifo=True,              # LIFO 策略（提高连接复用率，减少空闲连接）
    echo_pool="debug",               # 连接池调试日志（生产环境关闭）
)
```

**参数调优指南**：

| 参数 | 低负载场景 | 中等负载场景 | 高负载场景 | 说明 |
|------|-----------|-------------|-----------|------|
| `pool_size` | 5 | 10 | 20-30 | 基础连接数，建议 = (CPU核心数 * 2) + 有效磁盘数 |
| `max_overflow` | 10 | 20 | 40-50 | 峰值缓冲，建议 = pool_size * 2 |
| `pool_timeout` | 30 | 30 | 10-15 | 超时越短，失败越快，避免长时间阻塞 |
| `pool_recycle` | 3600 | 1800 | 900 | 必须 < MySQL `wait_timeout`（默认 28800） |
| `pool_pre_ping` | True | True | True | 生产环境必须开启，检测连接有效性 |

### 10.2 慢查询分析与优化

**慢查询日志配置**：
```python
# backend/src/core/database.py
from sqlalchemy import event
from src.utils.logger import logger

SLOW_QUERY_THRESHOLD_MS = 100  # 慢查询阈值（毫秒）

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """记录 SQL 执行开始时间"""
    conn.info.setdefault("query_start_time", []).append(time.time())

@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """记录 SQL 执行结束时间，检测慢查询"""
    total = time.time() - conn.info["query_start_time"].pop(-1)
    duration_ms = total * 1000
    
    if duration_ms > SLOW_QUERY_THRESHOLD_MS:
        logger.warning(
            f"慢查询检测: {duration_ms:.2f}ms\n"
            f"SQL: {statement}\n"
            f"参数: {parameters}"
        )
```

**索引优化策略**：

| 查询模式 | 优化方案 | 示例 |
|---------|---------|------|
| 等值查询 | 单列索引 | `INDEX idx_domain (domain)` |
| 范围查询 | 联合索引（最左前缀） | `INDEX idx_age_range (min_age_requirement, max_age_requirement)` |
| 全文检索 | FULLTEXT 索引 | `FULLTEXT idx_query (query) WITH PARSER ngram` |
| 排序+分页 | 覆盖索引 | `INDEX idx_created_at (created_at)` |
| 高频查询 | 冗余字段 + 索引 | `expected_knowledge_count` 独立列 |

### 10.3 批量写入优化

**批量插入模式**：
```python
# backend/src/service/rag_test_manager.py
from sqlalchemy.dialects.mysql import insert

async def batch_insert_test_results(self, run_id: str, results: list[dict]):
    """批量写入测试结果（使用 INSERT ... ON DUPLICATE KEY UPDATE）"""
    async with self.session_factory() as session:
        stmt = insert(TestRunResult).values(results)
        stmt = stmt.on_duplicate_key_update(
            precision=stmt.inserted.precision,
            recall=stmt.inserted.recall,
            f1=stmt.inserted.f1,
            passed=stmt.inserted.passed,
            matched_count=stmt.inserted.matched_count,
            execution_time_ms=stmt.inserted.execution_time_ms,
        )
        await session.execute(stmt)
        await session.commit()
```

**性能对比**：

| 写入方式 | 100条数据 | 1000条数据 | 说明 |
|---------|----------|-----------|------|
| 逐条 INSERT | ~500ms | ~5s | 每次事务开销大 |
| 事务批量 INSERT | ~100ms | ~800ms | 单次事务，减少网络往返 |
| INSERT ... ON DUPLICATE KEY | ~80ms | ~600ms | 支持幂等写入，避免重复 |

### 10.4 连接池监控

**连接池状态检查**：
```python
# backend/src/core/database.py
async def get_pool_status() -> dict:
    """获取连接池当前状态"""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalidated": pool.invalidated(),
    }
```

**告警阈值**：
- `checked_out / pool_size > 0.8`：连接池使用率过高，考虑扩容
- `overflow > max_overflow * 0.8`：突发流量频繁，调整 max_overflow
- `invalidated > 10/min`：连接频繁失效，检查网络或 MySQL 配置

---

## 11. Redis 缓存一致性与数据同步

### 11.1 缓存策略模式

**Cache-Aside（旁路缓存）模式**：
```
读操作：
1. 查询 Redis 缓存
2. 命中 → 返回
3. 未命中 → 查询 MySQL → 写入 Redis → 返回

写操作：
1. 更新 MySQL
2. 删除 Redis 缓存（不更新，避免并发问题）
3. 下次读取时自动重建缓存
```

**为什么选择删除而非更新？**
- 删除操作更简单，避免并发更新导致的数据不一致
- 缓存数据可能包含复杂计算结果，重建比更新更安全
- 符合"缓存数据可随时重建"的原则

### 11.2 缓存穿透防护

**问题**：查询不存在的数据，缓存无法命中，每次穿透到 MySQL。

**解决方案**：
```python
# backend/src/service/cache_service.py
class CacheService:
    async def get_with_protection(self, key: str, query_func, ttl: int = None) -> Any:
        """带穿透防护的缓存查询"""
        # 1. 查缓存
        value = await self.get(key)
        if value is not None:
            return value if value != "__NULL__" else None
        
        # 2. 查数据库
        result = await query_func()
        
        # 3. 写入缓存（空值也缓存，短 TTL）
        if result is None:
            await self.set(key, "__NULL__", expire=300)  # 5分钟
        else:
            await self.set(key, result, expire=ttl or self.default_ttl)
        
        return result
```

**布隆过滤器（可选）**：
```python
# 对于大量固定 ID 的查询（如测试用例 ID）
from pybloom_live import BloomFilter

class TestCacheService:
    def __init__(self, capacity: int = 100000):
        """初始化布隆过滤器"""
        self.bloom = BloomFilter(capacity=capacity, error_rate=0.01)
        self._load_existing_ids()
    
    async def might_contain(self, test_case_id: str) -> bool:
        """快速判断 ID 是否可能存在"""
        return test_case_id in self.bloom
    
    def add(self, test_case_id: str):
        """添加 ID 到布隆过滤器"""
        self.bloom.add(test_case_id)
```

### 11.3 缓存击穿防护

**问题**：热点 key 过期瞬间，大量请求同时穿透到 MySQL。

**解决方案：互斥锁 + 逻辑过期**：
```python
# backend/src/service/cache_service.py
import asyncio

class CacheService:
    async def get_with_lock(self, key: str, query_func, ttl: int = None) -> Any:
        """带互斥锁的缓存查询（防击穿）"""
        # 1. 查缓存
        value = await self.get(key)
        if value is not None:
            return value
        
        # 2. 尝试获取分布式锁
        lock_key = f"lock:{key}"
        acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=10)
        
        if acquired:
            try:
                # 3. 获取锁成功，查询数据库
                result = await query_func()
                await self.set(key, result, expire=ttl or self.default_ttl)
                return result
            finally:
                await self.redis_client.delete(lock_key)
        else:
            # 4. 未获取锁，等待后重试
            await asyncio.sleep(0.1)
            return await self.get_with_lock(key, query_func, ttl)
```

**逻辑过期方案**：
```python
class CacheWithLogicalExpiry:
    """带逻辑过期的缓存（热点数据永不过期）"""
    
    async def get(self, key: str, query_func, physical_ttl: int = 86400) -> Any:
        """物理 TTL 很长，逻辑 TTL 控制刷新"""
        cached = await self.redis_client.get(key)
        if cached:
            data = json.loads(cached)
            # 逻辑过期判断
            if time.time() < data.get("logical_expire", 0):
                return data["value"]
            else:
                # 逻辑过期，异步刷新
                asyncio.create_task(self._refresh(key, query_func, physical_ttl))
                return data["value"]
        
        # 缓存不存在，同步加载
        return await self._refresh(key, query_func, physical_ttl)
    
    async def _refresh(self, key: str, query_func, physical_ttl: int) -> Any:
        """刷新缓存"""
        result = await query_func()
        data = {
            "value": result,
            "logical_expire": time.time() + 3600,  # 逻辑过期 1 小时
        }
        await self.redis_client.setex(
            key, physical_ttl, json.dumps(data)
        )
        return result
```

### 11.4 缓存雪崩防护

**问题**：大量缓存 key 同时过期，导致 MySQL 瞬间压力激增。

**解决方案：TTL 随机偏移**：
```python
import random

class CacheService:
    async def set_with_jitter(self, key: str, value: Any, base_ttl: int = None) -> None:
        """带随机偏移的缓存写入（防雪崩）"""
        base_ttl = base_ttl or self.default_ttl
        # 随机偏移 ±20%
        jitter = int(base_ttl * 0.2)
        actual_ttl = base_ttl + random.randint(-jitter, jitter)
        # 确保 TTL > 0
        actual_ttl = max(60, actual_ttl)
        
        await self.set(key, value, expire=actual_ttl)
```

**多级缓存降级**：
```
正常情况：Redis → MySQL
Redis 故障：内存 LRU → MySQL
MySQL 故障：内存 LRU → 返回旧数据/默认值
```

### 11.5 MySQL → Redis 数据同步机制

**同步策略**：

| 场景 | 同步方式 | 说明 |
|------|---------|------|
| 配置变更 | 同步删除 Redis 缓存 | 配置更新后立即删除缓存，下次读取重建 |
| 测试用例 CRUD | 异步更新 Redis | 通过 EventBus 发布事件，异步更新缓存 |
| 测试运行结果 | 不缓存 | 结果数据只写 MySQL，不缓存 |
| LLM 调用统计 | Redis 聚合 → 定时刷 MySQL | 实时统计存 Redis，每 5 分钟刷入 MySQL |

**异步同步实现**：
```python
# backend/src/core/event_bus.py
class EventBus:
    @classmethod
    async def on_test_case_updated(cls, event: TestCaseUpdatedEvent):
        """测试用例更新后，异步更新 Redis 缓存"""
        try:
            redis_client = RedisClient.get_client()
            cache_key = f"child-dev:cache:test_case:{event.test_case_id}"
            # 删除旧缓存
            await redis_client.delete(cache_key)
            logger.info(f"测试用例缓存已失效: {event.test_case_id}")
        except Exception as e:
            logger.error(f"缓存失效失败: {e}")
```

---

## 12. 容错处理与降级方案

### 12.1 MySQL 连接故障处理

**连接断开自动重连**：
```python
# backend/src/core/database.py
from sqlalchemy.exc import OperationalError
import asyncio

async def safe_query(session_factory, query_func, fallback=None, max_retries: int = 2):
    """带重试的安全查询"""
    for attempt in range(max_retries + 1):
        try:
            async with session_factory() as session:
                return await query_func(session)
        except OperationalError as e:
            logger.warning(f"MySQL 连接失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(1 * (attempt + 1))  # 指数退避
            else:
                logger.error("MySQL 重连失败，使用降级方案")
                return fallback
        except Exception as e:
            logger.error(f"查询异常: {e}")
            return fallback
```

**连接池耗尽降级**：
```python
from asyncio import TimeoutError

async def query_with_timeout(session_factory, query_func, timeout: float = 5.0):
    """带超时的查询"""
    try:
        return await asyncio.wait_for(
            query_func(session_factory),
            timeout=timeout
        )
    except TimeoutError:
        logger.warning(f"查询超时 ({timeout}s)，返回降级数据")
        return None
```

### 12.2 Redis 故障降级

**Redis 不可用降级到 MySQL**：
```python
# backend/src/service/cache_service.py
class CacheService:
    async def get_or_fallback(self, key: str, mysql_query_func, fallback=None) -> Any:
        """带降级与熔断的缓存查询"""
        # 1. 尝试 Redis (接入熔断器，Fast-Fail 避免 Socket 超时拖垮吞吐量)
        try:
            if self.redis_client:
                redis_value = await redis_circuit_breaker.execute(self.redis_client.get, key)
                if redis_value:
                    return json.loads(redis_value)
        except CircuitBreakerOpenError:
            logger.warning("Redis 熔断器已打开，快速降级查询 MySQL")
        except (ConnectionError, TimeoutError, redis.RedisError) as e:
            logger.warning(f"Redis 不可用，触发异常并记录熔断: {e}")
        
        # 2. 降级到 MySQL
        try:
            result = await mysql_query_func()
            # 异步回写 Redis（不阻塞）
            asyncio.create_task(self._set_async(key, result))
            return result
        except Exception as e:
            logger.error(f"MySQL 查询也失败: {e}")
            return fallback
    
    async def _set_async(self, key: str, value: Any):
        """异步写入 Redis（不阻塞主流程）"""
        try:
            if self.redis_client:
                await self.redis_client.setex(
                    key, self.default_ttl, json.dumps(value, ensure_ascii=False)
                )
        except Exception:
            pass  # 忽略写入失败
```

### 12.3 熔断器模式

**实现**：
```python
# backend/src/core/circuit_breaker.py
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"       # 正常状态
    OPEN = "open"           # 熔断状态
    HALF_OPEN = "half_open" # 半开状态（试探）

class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0
    
    async def execute(self, func, *args, **kwargs):
        """执行带熔断保护的方法"""
        if self.state == CircuitState.OPEN:
            # 检查是否可以进入半开状态
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info(f"熔断器 {self.name} 进入半开状态")
            else:
                raise CircuitBreakerOpenError(f"熔断器 {self.name} 处于打开状态")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """成功回调"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"熔断器 {self.name} 已打开（失败 {self.failure_count} 次）")

class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass
```

**使用示例**：
```python
# MySQL 熔断器
mysql_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    name="mysql"
)

# Redis 熔断器
redis_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30,
    name="redis"
)

async def query_with_circuit_breaker(session_factory, query_func):
    """带熔断器的查询"""
    return await mysql_circuit_breaker.execute(
        safe_query, session_factory, query_func
    )
```

### 12.4 单例高可用方案

**当前架构**：MySQL 和 Redis 均为单例，无主从复制。

**风险**：
- MySQL 单点故障 → 整个系统不可用
- Redis 单点故障 → 缓存失效，降级到 MySQL

**短期缓解措施**：
1. **MySQL**：
   - 启用 `pool_pre_ping=True` 检测连接有效性
   - 配置自动重连机制（max_retries=2）
   - 定期备份数据（每天凌晨 2 点）

2. **Redis**：
   - 配置 `maxmemory-policy allkeys-lru` 自动淘汰旧数据
   - 缓存数据可随时重建，故障影响可控
   - 降级到内存 LRU + MySQL 直查

**长期规划**（项目上线后）：
- MySQL：主从复制 + 读写分离
- Redis：哨兵模式或集群模式

---

## 13. 性能测试指标与预期

### 13.1 基准测试指标

| 场景 | 重构前 | 重构后预期 | 提升幅度 |
|------|--------|-----------|---------|
| **简单 RAG 查询** | ~4s, 2000 tokens | ~1.5s, 0 token | 延迟降低 60%，Token 降为 0 |
| **缓存命中查询** | ~3s | 50-100ms | 响应时间降幅 95% |
| **Redis 缓存命中** | 内存 LRU，单机有效 | 三级缓存，Redis 命中 5-10ms | 分布式缓存，命中率提升 40% |
| **测试用例查询** | O(n) 内存遍历 | O(log n) 索引查询 | 支持万级数据量 |
| **测试运行对比** | 加载多个 JSON 文件 | SQL 聚合函数 | 性能提升 10 倍以上 |
| **配置版本查询** | 遍历目录解析 JSON | SQL 排序分页 | 秒级降至毫秒级 |
| **批量测试执行** | 无并发控制 | Redis 分布式锁 + SSE | 实时性提升 90% |

### 13.2 MySQL 性能指标

| 指标 | 预期值 | 说明 |
|------|--------|------|
| 单条查询延迟 | < 10ms | 带索引的等值查询 |
| 批量插入（1000 条） | < 1s | 使用事务批量写入 |
| 连接池获取延迟 | < 5ms | 连接池有空闲连接时 |
| 慢查询比例 | < 1% | 超过 100ms 的查询 |
| 连接池使用率 | < 80% | 正常运行时 |

### 13.3 Redis 性能指标

| 指标 | 预期值 | 说明 |
|------|--------|------|
| 缓存命中延迟 | < 5ms | 内存读取 |
| 缓存未命中总延迟 | < 50ms | Redis + MySQL 回源 |
| 缓存命中率 | > 70% | 正常运行时 |
| 分布式锁获取延迟 | < 1ms | SET NX 操作 |
| Pub/Sub 消息延迟 | < 10ms | 跨实例传播 |

### 13.4 缓存命中率预期

| 缓存层级 | 命中率预期 | 说明 |
|---------|-----------|------|
| 内存 LRU | 30-40% | 热点数据 |
| Redis | 60-70% | 全量缓存 |
| 磁盘 | < 5% | 降级方案 |
| 总命中率 | > 85% | 三级缓存合计 |

---

## 14. 详细实施步骤与阶段交付标准

### Phase 0: MySQL + Redis 基础设施搭建（周期：3 天）

- **任务**：
  1. 安装 SQLAlchemy 2.0、Alembic、aiomysql、redis[hiredis] 依赖
  2. 创建 MySQL 数据库配置模块和连接池
  3. 创建 Redis 配置模块和异步客户端
  4. 定义所有 SQLAlchemy 模型（12 张表）
  5. 配置 Alembic 并执行初始迁移
  6. 创建基础仓库类和数据库会话管理
  7. 启用 CacheService 中现有的 Redis 代码
  8. 创建分布式锁服务、会话管理器
  9. 增强 EventBus 支持 Redis Pub/Sub
  10. 实现熔断器模式（CircuitBreaker）
- **交付标准**：
  - MySQL 数据库连接成功，Alembic 迁移成功创建所有表
  - Redis 客户端初始化成功，三级缓存正常工作
  - 分布式锁获取/释放正常
  - 可通过 SQLAlchemy 异步会话执行基本 CRUD 操作
  - `alembic upgrade head` 可完整初始化数据库
  - 熔断器正常工作，故障降级验证通过

### Phase 1: 配置系统 MySQL 迁移 + Redis 缓存（周期：2 天）

- **任务**：
  1. 重写 `ConfigRepository` 为 MySQL 实现
  2. 更新 `ConfigManager` 使用 MySQL 仓库
  3. 配置版本创建和查询使用 MySQL 事务
  4. 配置更新后自动清除 Redis 配置缓存
  5. 删除旧 JSON 配置文件
- **交付标准**：
  - 配置更新成功写入 `config_versions` 表
  - 审计日志成功写入 `config_audit_log` 表
  - 配置版本列表、回滚、对比功能正常
  - 热重载机制正常工作，Redis 缓存自动失效

### Phase 2: 模型层统一与工厂注入（周期：3 天）

- **任务**：定义 `ILLMService`，实现 LangChain 与 LlamaIndex 双框架适配器；构建 `LLMServiceFactory` 并在 DI 容器中完成场景工厂的注入。
- **交付标准**：系统具备热切换 9 大业务场景模型的能力，切换过程中确保旧连接正确关闭 (`dispose`)，无资源泄露。

### Phase 3: RAG 声明式流水线与提示词管理（周期：4 天）

- **任务**：实现 `query_pipeline.yaml` 解析器，重构 `PipelineOrchestrator`；从硬编码中剥离提示词到 `backend/data/prompts`，实现 `PromptManager`。
- **交付标准**：简单查询绕过大模型重写直达检索层（验证延迟达标）；所有模型调用的系统提示词均从 JSON 持久层动态获取并支持渲染。

### Phase 4: RAG 测试框架 MySQL 迁移 + Redis 分布式锁（周期：3 天）

- **任务**：
  1. 重写 `RagTestManager` 使用 SQLAlchemy 异步会话
  2. 测试用例、草稿、测试集 CRUD 迁移到 MySQL
  3. 批量测试执行使用 MySQL 事务批量写入
  4. 使用 Redis 分布式锁防止重复执行
  5. 使用 Redis Hash 存储测试运行进度
  6. 删除旧 JSON 数据文件
- **交付标准**：
  - 测试用例查询使用 SQL 索引优化
  - 批量测试执行成功写入 `test_runs` 和 `test_run_results` 表
  - 分布式锁正常工作，防止并发冲突
  - 删除测试运行后触发聚合评分重算
  - 前端 `ExecutionProgress` 正常显示进度

### Phase 5: LLM 监控系统开发（周期：2 天）

- **任务**：
  1. LLM 调用埋点，发布 LLMCallEvent
  2. LLMMonitor 订阅事件并写入 MySQL
  3. 开发统计分析接口
  4. 实现 Prometheus 指标输出
- **交付标准**：
  - LLM 调用日志成功写入 `llm_call_logs` 表
  - 支持按场景/模型/时间范围查询统计
  - Prometheus 指标正常输出

### Phase 6: 前端重构与最终集成（周期：3 天）

- **任务**：搭建独立的 `/system-config` 与 `/prompts` 管理界面，并在 RAG 测试页接入新的导入、审核与批量执行模态框组件。
- **交付标准**：全链路端到端功能验证通过。测试环境所有 API 兼容且无严重性能问题；新界面的交互体验优于历史版本。

---

## 15. 数据清理计划

### 15.1 可删除的旧文件

完成 MySQL 迁移后，以下文件和目录可以安全删除：

```
app_data/data/configs/              # 配置版本和审计日志（已迁移到 MySQL）
app_data/storage/test_cases.json    # 测试用例（已迁移到 MySQL）
backend/data/prompts/               # 旧提示词模板（已迁移到 MySQL）
app_data/storage/test_sets/         # 测试集（已迁移到 MySQL）
app_data/storage/test_case_drafts/  # 测试用例草稿（已迁移到 MySQL）
app_data/storage/test_runs/         # 测试运行结果（已迁移到 MySQL）
app_data/storage/source_documents/  # 源文档元数据（已迁移到 MySQL）
app_data/storage/document_store.json # 文档记录（已迁移到 MySQL）
app_data/storage/ab_test_metrics.json # A/B 测试指标（已迁移到 MySQL）
app_data/storage/memory_store.json  # 记忆数据（已迁移到 MySQL）
app_data/cache/                     # 磁盘缓存（已由 Redis 替代）
```

### 15.2 保留的文件

```
backend/src/config/rules/rules.json # 业务规则（保持 JSON 文件）
backend/src/data/                   # 静态数据（里程碑、词典等）
app_data/storage/vector_store/      # Chroma 向量索引（如转为C/S模式则可删除本地持久化目录）
```

---

## 16. 风险与缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| MySQL 连接池耗尽 | 请求阻塞 | 配置合理的 pool_size 和 max_overflow，启用 pool_pre_ping 检测，实现熔断器降级 |
| 异步会话未正确关闭 | 连接泄漏 | 使用 `async with` 上下文管理器，确保会话自动关闭 |
| Alembic 迁移冲突 | 数据库结构不一致 | 每次迁移前备份数据库，迁移后验证表结构 |
| JSON 字段查询性能差 | 查询超时 | 遵循 JSON 使用原则，需要查询的字段拆分为独立列 |
| 批量写入性能差 | 测试执行慢 | 使用 `INSERT ... ON DUPLICATE KEY UPDATE` 批量写入 |
| 数据迁移丢失 | 数据丢失 | 项目未上线，无历史数据，无需迁移 |
| Redis 连接断开 | 缓存失效，降级到 MySQL | 连接池自动重连，CacheService 内置降级逻辑（内存 → MySQL 直查） |
| Redis 内存溢出 | 缓存驱逐，性能下降 | 配置 maxmemory 和淘汰策略（allkeys-lru），监控内存使用 |
| 分布式锁死锁 | 测试执行阻塞 | 设置 TTL 自动过期，使用 `execute_with_lock` 包装器确保释放 |
| Redis Pub/Sub 消息丢失 | 事件未传播 | 内存 EventBus 作为兜底，关键事件使用 MySQL 持久化 + 补偿机制 |
| 缓存不一致 | 读取到旧数据 | 配置变更时主动清除 Redis 缓存，使用版本号机制验证一致性 |
| 缓存穿透 | MySQL 压力激增 | 空值缓存 + 布隆过滤器，短 TTL 防护 |
| 缓存击穿 | 热点 key 过期瞬间压力大 | 互斥锁 + 逻辑过期，保证单线程回源 |
| 缓存雪崩 | 大量 key 同时过期 | TTL 随机偏移（±20%），多级缓存降级 |
| MySQL 单点故障 | 系统不可用 | 连接重试 + 熔断器 + 定期备份，上线后规划主从复制 |
| Redis 单点故障 | 缓存失效 | 降级到内存 LRU + MySQL 直查，缓存数据可随时重建 |