# 02 - 核心数据模型

> **本文档包含**: 全部 18 个数据模型定义、状态枚举、状态机
>
> **零兼容原则**: 本文档定义的数据模型为全新设计，不保留旧字段、不写迁移脚本、不做双版本并行。
>
> **ID 策略**: 所有表主键统一使用 UUID (CHAR(36))，不使用自增 INT。原因：
> - 分布式友好，无需协调 ID 生成器
> - 前端可预生成 ID，支持离线操作
> - 避免暴露业务量信息
> - 关联表/中间表同样使用 UUID

---

## 3.4 核心数据模型

> **Document 表说明**: Document 是现有表（书籍导入时创建），非本重构需求新建。本方案中仅作为弱引用关联（无外键约束）。
>
> **Document 表关键字段** (现有表，供参考):
> - `id (UUID)`: 主键
> - `title (VARCHAR(255))`: 文档标题
> - `file_path (VARCHAR(500))`: 文件存储路径
> - `file_type (ENUM: pdf / epub / txt)`: 文件类型
> - `chapter_count (INT)`: 章节数
> - `document_type (VARCHAR(64))`: 文档类型（政策法规/学术研究/经典理论/实操方法），用于 Layer 4c 时效性检查
> - `upload_date (DATETIME)`: 上传时间
> - `created_at, updated_at`

```python
class TestSet(Base):
    """测试集 - 测试用例的集合"""
    id (UUID)                                # 主键，CHAR(36)
    name (VARCHAR(255))
    description (TEXT, 可选)
    source_type (ENUM: book_generated / json_imported / manual)
    source_document_id (UUID, 弱引用 → Document.id, 可选)
    created_at, updated_at
    # total_cases 通过 COUNT(test_set_cases) 实时计算，不存储冗余字段
    # 删除级联规则:
    # - TestSetCase: 级联删除 (测试集删除时，关联关系自动清理)
    # - TestCase: 不级联 (用例可能被其他测试集复用，仅删除关联关系)
    # - TestRun: 级联删除 (测试集删除时，关联的运行记录自动清理)
    # - TestReport: 级联删除 (随 TestRun 级联删除)
    # - TestCaseDraft: 级联删除 (来自该测试集书籍的草稿自动清理)
    # - IgnoredSuggestion: 级联删除 (忽略记录自动清理)

class TestSetCase(Base):
    """测试集-用例关联表 - 支持用例被多个测试集复用"""
    id (UUID)                                # 主键
    test_set_id (UUID, 弱引用 → TestSet.id)
    case_id (UUID, 弱引用 → TestCase.id)
    added_at (DATETIME)
    added_by (VARCHAR(36))                   # 添加用例的用户 ID
    # 唯一约束: UNIQUE(test_set_id, case_id)

class TestCase(Base):
    """测试用例 - 单个测试条目"""
    id (UUID)                                # 主键
    query (TEXT)
    age_months (INT, 可选)
    domain (ENUM: TestDomain)
    expected_document_ids (JSON, 可选)       # Golden Dataset: 期望命中的文档 ID 列表，格式: ["uuid-1", "uuid-2", ...]
    expected_key_points (JSON, 可选)         # 期望知识点列表，格式: ["知识点 1", "知识点 2", ...]
    source_draft_id (UUID, 弱引用 → TestCaseDraft.id, 可选)
    created_at
    # 注意: 不再包含 test_set_id，用例通过 TestSetCase 中间表与测试集关联

class PromptMetadata(Base):
    """提示词元数据 - 提示词级别的静态信息（一个 prompt_key 只有一份）"""
    id (UUID)                                # 主键
    prompt_key (VARCHAR(255))                # 唯一标识，唯一索引
    name_zh (VARCHAR(255))                   # 中文名称
    purpose (TEXT)                           # 用途说明
    category (VARCHAR(64))                   # 分类: rag_retrieval/rag_generation/assessment/scoring/reporting/test_case_generation
    subcategory (VARCHAR(64), 可选)           # 子分类
    variables_schema (JSON, 可选)             # 变量声明 schema（含类型、必填、默认值、说明）
    code_references (JSON, 可选)              # 代码引用位置（文件路径、行号、函数名）
    config_dependencies (JSON, 可选)          # 配置参数依赖（参数名、分类、说明）
    is_active (bool, default=True)           # 是否启用
    is_system (bool, default=False)          # 是否系统内置（系统内置不可删除）
    created_by (VARCHAR(36), 可选)            # 创建人
    updated_by (VARCHAR(36), 可选)            # 更新人
    created_at, updated_at
    # 唯一约束: UNIQUE(prompt_key)
    # 索引: INDEX(category, is_active) 支持按分类筛选启用的提示词

class PromptVersion(Base):
    """提示词版本 - 记录某时刻的提示词内容"""
    id (UUID)                                # 主键
    prompt_key (VARCHAR(255))                # 如 query_rewrite, query_routing
    version_label (VARCHAR(64))              # 展示用版本号，如 "v3", "v4-new-constraint"
    version_number (INT)                     # 该 prompt_key 下的自增序号，仅用于排序
    # version_number 生成: SELECT COALESCE(MAX(version_number), 0) + 1 WHERE prompt_key = ? FOR UPDATE（使用行锁保证并发安全）
    content (TEXT)                           # 提示词完整内容
    variables_extracted (JSON, 可选)          # 自动从 content 中提取的变量列表，保存时自动更新，格式: ["query", "age", ...]
    change_impact (JSON, 可选)               # 变更影响分析，保存时自动计算，格式: {"variables_added": [], "variables_removed": [], "config_dependencies_changed": false, "affected_code_files": []}
    created_at, created_by (VARCHAR(36)), change_summary
    # 唯一约束: UNIQUE(prompt_key, version_label)

class ConfigVersion(Base):
    """配置版本 - 记录某时刻的完整 RAG 配置快照"""
    id (UUID)                                # 主键
    version_number (INT)                     # 自增序号，用于排序和生成 version_label，由系统自动维护
    version_label (VARCHAR(32))              # 展示用语义版本号，如 "v2.3"，根据 version_number 自动生成
    config_snapshot (JSON)                   # 完整配置快照，包含所有 RAG 参数
    created_at, created_by (VARCHAR(36)), change_summary
    # 注意: 不将参数拆为独立列，避免新增参数时 ALTER TABLE
    # config_snapshot 示例: {"bm25_top_k": 10, "vector_top_k": 10, "fusion_threshold": 0.25, ...}
    # version_label 生成规则: 查询最大 version_number N，新标签为 "v{N+1}.0"；小修订时 version_number 不变，version_label 通过 "v{N}.{revision}" 格式递增 revision（如 v2.1 → v2.2）
    # 注意: version_label 是配置版本号，用于展示和趋势图；change_set_label 是变更集编号，用于审计追踪，两者用途不同
    # 注意: version_number 是数字排序字段，解决 version_label 字符串排序不准确的问题；仅在大版本变更时递增，小修订时保持不变

class ConfigChangeSet(Base):
    """配置变更集 - 原子保存配置+提示词的整体版本"""
    id (UUID)                                # 主键
    change_set_label (VARCHAR(32))           # 展示用标签，格式 "CS-20260416-001"，用于审计追踪
    config_version_id (UUID, 弱引用 → ConfigVersion.id)
    created_at, status (ENUM: committed / rolled_back)
    rollback_reason (VARCHAR(500), 可选)
    # 注意: prompt_version_ids 不再存为 JSON 数组，改用 ConfigChangeSetPrompt 关联表
    # 注意: change_set_label 是变更集编号 (审计用)，version_label 是配置版本号 (展示用)，两者独立编号

class ConfigChangeSetPrompt(Base):
    """配置变更集-提示词版本关联表 - 一个变更集可包含多个提示词版本变更"""
    id (UUID)                                # 主键
    change_set_id (UUID, 弱引用 → ConfigChangeSet.id)
    prompt_version_id (UUID, 弱引用 → PromptVersion.id)
    # 唯一约束: UNIQUE(change_set_id, prompt_version_id)
    # 索引: INDEX(prompt_version_id) 支持反向查询"哪些变更集包含某提示词版本"

class TestReport(Base):
    """评估报告 - 每次运行生成一份报告"""
    id (UUID)                                # 主键
    run_id (UUID, 弱引用 → TestRun.id, 可选)      # 常规报告关联 TestRun；A/B 对比报告为 NULL，通过 ab_test_id 关联
    test_set_id (UUID, 弱引用 → TestSet.id)
    config_version_id (UUID, 弱引用 → ConfigVersion.id)
    status (ENUM: processing / completed / superseded)  # 报告状态，与状态机一致（无 pending，创建即 processing）
    prompt_version_snapshot (JSON)           # {prompt_key: {version_label, content, changed_at}, ...} 存储完整内容快照，确保可回溯
    overall_score, precision, recall, f1, mrr, ndcg
    validation_results (JSON)                # 统一存储 6 层校验结果: [{layer: 1, status, data, duration_ms}, ...]
    tuning_suggestion_summary (JSON)         # 调优建议摘要: {config: {total: 3, by_priority: {high: 1, medium: 2}, by_source: {rule_engine: 2, llm: 1}}, prompt: {total: 2, by_priority: {high: 1, medium: 1}}}，用于报告列表快速展示，详细建议存 TuningSuggestionRecord 和 PromptSuggestionRecord 表
    created_by (VARCHAR(36), 可选)            # 生成报告的用户 ID（系统自动生成为 "system"）
    created_at
    # 注意: TestReport 单向弱引用 → TestRun，TestRun 不持有 report_id，避免循环依赖
    # 注意: 不再使用 layer1_results ~ layer6_results 六列，改为单列 JSON 数组，新增校验层无需 ALTER TABLE
    # 注意: prompt_version_snapshot 存储完整内容而非仅引用，防止提示词被修改后无法回溯

    # validation_results 中每层的 status 字段枚举值:
    # - "completed": 校验正常完成
    # - "degraded": 校验降级执行（如 LLM API 异常时跳过，使用降级策略）
    # - "timeout": 校验超时（超过单层层超时上限被取消）
    # - "cancelled": 校验被用户手动取消
    # - "skipped": 校验被跳过（如 TestRun 失败时未执行的层，或 Layer 6 默认不执行）

    # TestReport 创建条件规则:
    # 1. TestRun.status = completed: 必须生成完整报告（包含所有 6 层校验结果）
    # 2. TestRun.status = failed: 生成部分报告（仅包含已完成的校验层，未完成的层标记 status="skipped"，data 中记录失败原因）
    # 3. TestRun.status = cancelled: 生成部分报告（仅包含已完成的用例结果和已执行的校验层，标注"运行已取消"）
    # 4. TestRun.status = pending/running: 不生成报告
    # 5. 部分报告与完整报告使用同一 TestReport 表，通过 validation_results 中各层的 status 字段区分

class TuningSuggestionRecord(Base):
    """调优建议记录 - 配置参数调优建议"""
    id (UUID)                                # 主键
    report_id (UUID, 弱引用 → TestReport.id)
    param_name (VARCHAR(128))
    current_value (JSON), suggested_value (JSON)
    action (VARCHAR(36)), reason (TEXT), expected_effect (JSON), priority (VARCHAR(32))
    # expected_effect 格式: {"metric": "P@5", "current": 0.53, "predicted_range": [0.65, 0.72], "risk": "可能引入更多噪声文档", "historical_reference": "v2.1 改过类似，P@5+0.08"}
    source (ENUM: rule_engine / history / llm, 可选)
    safe_range (JSON), applied (bool), applied_config_version_id (UUID, 可选)
    # 注意: 忽略状态由独立表 IgnoredSuggestion 管理，不在此表存储，避免跨报告查询效率问题
    # 注意: 本表仅存储配置参数调优建议 (如 bm25_top_k, fusion_threshold 等)

class PromptSuggestionRecord(Base):
    """提示词优化建议 - 提示词内容修改建议"""
    id (UUID)                                # 主键
    report_id (UUID, 弱引用 → TestReport.id)
    prompt_key (VARCHAR(128))
    current_version_id (UUID, 可选), suggested_version_id (UUID, 可选)
    reason (TEXT), expected_effect (JSON), priority (VARCHAR(32)), source (ENUM: rule_engine / history / llm, 可选)
    suggestion_type (ENUM: add_constraint / rewrite / parameter_tweak, 可选)
    applied (bool), applied_version_id (UUID, 可选)
    # 注意: 忽略状态由独立表 IgnoredSuggestion 管理，不在此表存储
    # 注意: 本表仅存储提示词优化建议 (如 query_rewrite prompt 修改)，与 TuningSuggestionRecord 职责分离

class TestRun(Base):
    """测试执行记录"""
    id (UUID)                                # 主键
    name (VARCHAR(255))
    status (ENUM: pending / running / completed / failed / cancelled)
    test_set_id (UUID, 弱引用 → TestSet.id)
    config_version_id (UUID, 弱引用 → ConfigVersion.id)
    created_by (VARCHAR(36), 可选)           # 触发运行的用户 ID
    overall_precision, overall_recall, overall_f1, overall_mrr, overall_ndcg
    total_test_cases, passed_test_cases, failed_at_case_id (UUID, 可选)
    ab_test_id (UUID, 可选)                  # A/B 测试组 ID，关联同一 A/B 测试的两次运行
    ab_test_side (ENUM: A / B, 可选)         # 标识本次运行是配置 A 还是配置 B
    # 注意: 不持有 report_id，通过 TestReport.run_id 反向查询
    created_at, completed_at
    # completed_at 语义: 仅在 status=completed 时填写（失败/取消时为 NULL）

class TestRunResult(Base):
    """单次用例执行结果 - 存储每个用例的详细执行数据"""
    id (UUID)                                # 主键
    run_id (UUID, 弱引用 → TestRun.id)           # 关联运行记录
    case_id (UUID, 弱引用 → TestCase.id)         # 关联用例
    query (TEXT)                             # 查询文本快照
    hit_at_1, hit_at_3, hit_at_5             # 命中检测 (0 或 1)
    matched_doc_ids (JSON)                   # 实际命中的文档 ID 列表: ["uuid-1", ...]
    matched_doc_scores (JSON)                # 命中文档的分数列表: [0.85, 0.72, ...]
    status (ENUM: passed / failed)           # 用例执行状态
    duration_ms (INT, 可选)                  # 单用例执行耗时 (毫秒)
    created_at
    # 索引: INDEX(run_id) 支持按运行查询所有用例结果
    # 索引: INDEX(run_id, status) 支持按运行+状态筛选 (Bad Case 查询)
    # 用途: 断线重连时从数据库恢复进度（Redis 无数据时的降级方案）；运行详情页展示用例明细

class TestCaseDraft(Base):
    """测试用例草稿 - 书籍导入后生成的待审核用例"""
    id (UUID)                                # 主键
    source_document_id (UUID, 弱引用 → Document.id)
    query (TEXT), age_months (INT, 可选), domain (ENUM: TestDomain)
    expected_key_points (JSON, 可选)
    status (ENUM: draft / reviewed / rejected / imported)
    reviewed_by (VARCHAR(36), 可选), reviewed_at (DATETIME, 可选), created_at
    # 级联规则: Document 删除时，应用层删除关联的草稿（文档不存在，草稿无意义）

class IntentAnnotation(Base):
    """意图人工标注 - Layer 5b 意图识别准确率校验的数据来源"""
    id (UUID)                                # 主键
    case_id (UUID, 弱引用 → TestCase.id)
    intent_type (VARCHAR(64))                # 如: factual_query, how_to, comparison, definition
    annotated_by (VARCHAR(36)), annotated_at
    # 唯一约束: UNIQUE(case_id) 每个用例最多一条人工标注

class QueryIntentLog(Base):
    """查询意图自动分类日志 - Layer 5b 意图识别的数据来源"""
    id (UUID)                                # 主键
    run_id (UUID, 弱引用 → TestRun.id)           # 关联运行记录
    case_id (UUID, 弱引用 → TestCase.id, 可选)   # 关联用例
    query (TEXT)                             # 查询文本
    predicted_intent (VARCHAR(64))           # LLM 自动分类的意图
    confidence (FLOAT, 可选)                 # 置信度 (0.0-1.0)
    created_at
    # 索引: INDEX(run_id) 支持按运行查询所有意图分类结果
    # 用途: Layer 5b 读取此表获取"查询分析结果"，与 IntentAnnotation 对比计算准确率

class IgnoredSuggestion(Base):
    """忽略建议记录 - 独立表，支持高效跨报告查询"""
    id (UUID)                                # 主键
    test_set_id (UUID, 弱引用 → TestSet.id)      # 绑定测试集
    report_id (UUID, 弱引用 → TestReport.id, 可选)  # report 级别时填写
    param_name (VARCHAR(255))                # 参数名或 prompt_key
    suggestion_type (ENUM: config / prompt)  # 配置建议或提示词建议
    ignore_scope (ENUM: report / test_set)   # 忽略范围
    ignored_by (VARCHAR(36))                 # 操作用户
    ignored_at (DATETIME)                    # 忽略时间
    ignore_reason (VARCHAR(500), 可选)       # 忽略原因
    restored (bool, default=False)           # 是否已恢复
    restored_at (DATETIME, 可选)             # 恢复时间
    # 索引: INDEX(test_set_id, ignore_scope, restored) 支持快速查询活跃忽略记录
    # 索引: INDEX(report_id) report 删除时应用层清理忽略记录
    # 注意: 无外键约束，级联删除由应用层逻辑处理

class SynonymQueryPair(Base):
    """同义查询对 - Layer 5a Embedding 质量校验的数据来源"""
    id (UUID)                                # 主键
    query_a (TEXT)                           # 查询 A
    query_b (TEXT)                           # 查询 B
    domain (VARCHAR(64))                     # 发展领域
    created_by (VARCHAR(36))                 # 创建者
    created_at (DATETIME)                    # 创建时间
    source (ENUM: builtin / auto_extracted / manual)  # 数据来源
    active (bool, default=True)              # 是否启用
    # 索引: INDEX(domain, active) 支持按领域查询启用的同义对
    # 用途: Layer 5a 读取此表获取同义查询对，计算 embedding 余弦相似度
```

**TestRun 状态枚举**:

| 状态 | 说明 | 触发时机 |
|------|------|---------|
| `pending` | 等待执行 | 创建 TestRun 后 |
| `running` | 正在执行 | SSE `run_started` 事件触发 |
| `completed` | 执行完成 | 所有用例执行完毕 |
| `failed` | 执行失败 | 异常中断，记录 `failed_at_case_id` (UUID) |
| `cancelled` | 用户取消 | 用户主动取消运行 |

**TestCaseDraft 状态机**:

```
┌───────┐   通过    ┌─────────┐   归入    ┌─────────┐
│ draft ├──────────►│ reviewed├──────────►│ imported│
└───┬───┘           └─────────┘           └─────────┘
    │ 拒绝               │ 取消归入
    ▼                    ▼
┌──────────┐        ┌───────┐
│ rejected │        │ draft │ (重新编辑后)
└──────────┘        └───────┘
```

**状态转换说明**:
- `draft → reviewed`: 用户点击"通过"，草稿进入待归入状态
- `reviewed → imported`: 用户选择测试集并确认，**系统复制草稿数据到 TestCase 表**，草稿状态标记为 imported
- `imported` 后，TestCaseDraft 保留作为历史记录，TestCase 为独立副本，两者数据解耦
- 如需回滚：删除对应 TestCase，将 TestCaseDraft 状态重置为 `reviewed`

---

## 3.5 索引定义

> **所有索引均为业务查询性能优化必需，实施时必须创建。**

| 表名 | 索引名称 | 索引字段 | 类型 | 用途 |
|------|---------|---------|------|------|
| TestSet | idx_created_at | created_at | 普通索引 | 测试集列表按时间排序 |
| TestSet | idx_source_doc | source_document_id | 普通索引 | 按源文档筛选测试集 |
| TestSetCase | idx_case_id | case_id | 普通索引 | 反向查询"用例被哪些测试集复用" |
| TestSetCase | idx_test_set_id | test_set_id | 普通索引 | 按测试集查询关联用例 |
| TestCase | idx_domain_age | domain, age_months | 复合索引 | 按领域/年龄筛选用例 |
| TestCase | idx_source_draft | source_draft_id | 普通索引 | 按来源草稿查询用例 |
| ConfigVersion | idx_created_at | created_at | 普通索引 | 趋势图按时间查询配置版本 |
| PromptMetadata | uk_prompt_key | prompt_key | 唯一索引 | 提示词key唯一约束 |
| PromptMetadata | idx_category_active | category, is_active | 复合索引 | 按分类筛选启用的提示词 |
| PromptVersion | idx_key_created | prompt_key, created_at | 复合索引 | 版本列表查询（按 key 分组，按时间排序） |
| ConfigChangeSet | idx_status | status | 普通索引 | 查询活跃变更集（status='committed'） |
| ConfigChangeSet | idx_config_version_id | config_version_id | 普通索引 | 查询某配置版本的变更集 |
| TestReport | idx_testset_created | test_set_id, created_at | 复合索引 | 报告列表查询（按测试集筛选，按时间排序） |
| TestRun | idx_testset_status_created | test_set_id, status, created_at | 复合索引 | 运行历史筛选（按测试集+状态过滤，按时间排序） |
| TestCaseDraft | idx_doc_status | source_document_id, status | 复合索引 | 草稿审核列表（按文档筛选待审核草稿） |
| TuningSuggestionRecord | idx_report_applied | report_id, applied | 复合索引 | 推荐面板查询（按报告筛选，过滤已应用） |
| TuningSuggestionRecord | idx_applied_config | applied_config_version_id | 普通索引 | 查询采纳建议关联的配置版本 |
| PromptSuggestionRecord | idx_report_applied | report_id, applied | 复合索引 | 推荐面板查询（按报告筛选，过滤已应用） |
| PromptSuggestionRecord | idx_current_version | current_version_id | 普通索引 | 反向查询"哪些建议引用当前版本" |
| PromptSuggestionRecord | idx_suggested_version | suggested_version_id | 普通索引 | 反向查询"哪些建议引用建议版本" |
| PromptSuggestionRecord | idx_applied_version | applied_version_id | 普通索引 | 反向查询"哪些建议引用采纳版本" |
| IntentAnnotation | idx_case_id | case_id | 唯一索引 | 每个用例最多一条标注（UNIQUE 约束） |
| IgnoredSuggestion | idx_testset_scope_restored | test_set_id, ignore_scope, restored | 复合索引 | 推荐面板查询活跃忽略记录 |
| TestReport | idx_run_id | run_id | 普通索引 | 通过 run_id 反向查询报告 |
| TestReport | idx_config_version_id | config_version_id | 普通索引 | 查询某配置版本的所有报告 |
| TestRun | idx_config_version_id | config_version_id | 普通索引 | 查询某配置版本的所有运行 |
| ConfigChangeSetPrompt | idx_prompt_version_id | prompt_version_id | 普通索引 | 反向查询"哪些变更集包含某提示词版本" |
| IgnoredSuggestion | idx_report_id | report_id | 普通索引 | report 删除时应用层清理忽略记录 |
| QueryIntentLog | idx_run_id | run_id | 普通索引 | Layer 5b 按运行查询所有意图分类结果 |
| QueryIntentLog | idx_case_id | case_id | 普通索引 | 按用例查询意图标注 |
| TestRunResult | idx_run_id | run_id | 普通索引 | 按运行查询所有用例结果 |
| TestRunResult | idx_run_status | run_id, status | 复合索引 | 按运行+状态筛选 Bad Case |
| TestRunResult | idx_case_id | case_id | 普通索引 | 按用例查询执行结果 |
| SynonymQueryPair | idx_domain_active | domain, active | 复合索引 | 按领域查询启用的同义对 |

**TestReport 状态机**:

```
┌───────────┐    校验中     ┌───────────┐
│processing ├──────────────►│processing │
│(创建即开始)│               │(校验执行中)│
└───────────┘               └─────┬─────┘
                                  │ 所有校验完成
                                  ▼
                            ┌───────────┐
                            │ completed │
                            └─────┬─────┘
                                  │ 应用建议 + 复测
                                  ▼
                            ┌───────────┐
                            │superseded │ (被新报告替代)
                            └───────────┘
```

**状态说明**:
- TestReport 在 TestRun 完成后立即创建，初始状态为 `processing`（无 `pending` 状态）
- `processing`: 校验引擎正在执行 6 层校验
- `completed`: 所有校验完成，报告可展示
- `superseded`: 用户应用建议并复测后，旧报告标记为被替代

---

**文档索引**: 
- 上一节: [01-phase-0-bug-fixes.md](./01-phase-0-bug-fixes.md) — Phase 0 核心工作流修复
- 下一节: [03-sse-workflow.md](./03-sse-workflow.md) — SSE 事件与工作流
