# 阶段 1：数据库与数据模型

> 前置：无。本阶段为整个方案的起点。

---

### Task 1: 修改 DDL — 移除 age/domain 列

**Files:**
- Modify: `.ai/full_init_script_mysql57.sql:144-172` (test_case_drafts 表)
- Modify: `.ai/full_init_script_mysql57.sql:179-203` (test_cases 表)

**test_case_drafts 表变更：**

移除以下列和索引：
- `age DECIMAL(4,1) NOT NULL`
- `age_stage_label VARCHAR(20) NOT NULL DEFAULT ''`
- `domain VARCHAR(32) NOT NULL`
- `INDEX idx_domain (domain)`

- [ ] **Step 1: 修改 test_case_drafts DDL**

将原来的：
```sql
CREATE TABLE `test_case_drafts` (
    `id` VARCHAR(64) PRIMARY KEY,
    `source_document_id` VARCHAR(64),
    `query` TEXT NOT NULL,
    `age` DECIMAL(4,1) NOT NULL COMMENT '年龄（岁，如 1.5）',
    `age_stage_label` VARCHAR(20) NOT NULL DEFAULT '' COMMENT '年龄段标签(0-6m/1-2y等)',
    `domain` VARCHAR(32) NOT NULL,
    ...
    INDEX `idx_domain` (`domain`),
    ...
);
```

改为：
```sql
CREATE TABLE `test_case_drafts` (
    `id` VARCHAR(64) PRIMARY KEY,
    `source_document_id` VARCHAR(64),
    `query` TEXT NOT NULL,
    `description` TEXT,
    `expected_knowledge_ids` JSON,
    `expected_keywords` JSON,
    `answer_points` JSON,
    `professional_terms` JSON,
    `difficulty_level` VARCHAR(16),
    `faithfulness_score` DECIMAL(5,4),
    `source_chunk_id` VARCHAR(64),
    `source_page` INT,
    `source_content_snippet` TEXT,
    `generation_params` JSON,
    `batch_id` VARCHAR(64),
    `draft_index` INT DEFAULT 0,
    `status` VARCHAR(16) NOT NULL DEFAULT 'draft',
    `version` INT NOT NULL DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_source_document_id` (`source_document_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_batch_id` (`batch_id`)
);
```

- [ ] **Step 2: 修改 test_cases 表 DDL — 将 age/domain 改为可 NULL**

```sql
`age` DECIMAL(4,1) DEFAULT NULL COMMENT '年龄（岁），从草稿提升时可留空',
`age_stage_label` VARCHAR(20) NOT NULL DEFAULT '' COMMENT '年龄段标签',
`domain` VARCHAR(32) DEFAULT NULL COMMENT '测试领域，从草稿提升时可留空',
```

- [ ] **Step 3: Commit**

```bash
git add .ai/full_init_script_mysql57.sql
git commit -m "refactor: 移除 test_case_drafts 的 age/domain 列，test_cases 的 age/domain 改为可 NULL"
```

---

### Task 2: 修改后端 Pydantic Schema

**Files:**
- Modify: `backend/src/schemas/rag_eval/draft.py`

- [ ] **Step 1: 修改 DraftCreate — 移除 age/domain/age_stage_label 字段**

> **注意：** `source_document_id` 不属于 `DraftCreate` schema。它由 `DraftEngineFacade` 在 save 阶段作为独立参数传给 `_draft_repo.create()`，不在生成器输出中。不要将此字段加入 DraftCreate。

将 `DraftCreate` 从：

```python
class DraftCreate(BaseModel):
    query: str
    age: float
    age_stage_label: str = ""
    domain: TestDomain
    description: Optional[str] = None
    ...
```

改为：

```python
class DraftCreate(BaseModel):
    query: str
    description: Optional[str] = None
    expected_knowledge_ids: list[str] = Field(default_factory=list)
    expected_keywords: list[str] = Field(default_factory=list)
    answer_points: Optional[list[str]] = None
    professional_terms: list[str] = Field(default_factory=list)
    difficulty_level: Optional[DifficultyLevel] = None
    source_chunk_id: Optional[str] = None
    source_page: Optional[int] = None
    source_content_snippet: Optional[str] = None
    generation_params: Optional[dict] = None
```

- [ ] **Step 2: 修改 DraftUpdate — 移除 age/domain/age_stage_label 可选字段**

`DraftUpdate` 中移除 `age`、`age_stage_label`、`domain` 的 Optional 声明。

- [ ] **Step 3: 修改 DraftGenerationConfig — 移除 custom_age_ranges/custom_domains**

```python
class DraftGenerationConfig(BaseModel):
    max_qa_per_chunk: int = 3
    min_qa_per_chunk: int = 1
```

> **注意：** 不添加 `difficulty_overrides` 等未来字段——YAGNI 原则，需要时再加。

- [ ] **Step 4: 修改 BookMetadata — 移除 age_ranges/domains**

```python
class BookMetadata(BaseModel):
    topic_summary: str = ""
```

- [ ] **Step 5: 修改 DraftRead — 移除 age/domain/age_stage_label**

`DraftRead` 继承 `DraftCreate`，移除字段后自动生效。确认 `DraftRead` 中没有额外声明这三个字段。

- [ ] **Step 6: Commit**

```bash
git add backend/src/schemas/rag_eval/draft.py
git commit -m "refactor: 移除 draft schema 中的 age/domain/age_stage_label 字段"
```

---

### Task 3: 修改后端 ORM Model

**Files:**
- Modify: `backend/src/models/rag_eval/draft.py`
- Modify: `backend/src/models/rag_eval/test_case.py`
- Modify: `backend/src/schemas/rag_eval/test_case.py`

- [ ] **Step 1: 移除 TestCaseDraft 的 age/domain/age_stage_label 列**

全部删除。

- [ ] **Step 2: 修改 test_case.py ORM — age/domain 改为 nullable**

```python
age: Mapped[Optional[float]] = mapped_column(
    DECIMAL(4, 1), nullable=True, comment="年龄（岁），从草稿提升时可留空"
)
domain: Mapped[Optional[TestDomain]] = mapped_column(
    Enum(TestDomain, values_callable=lambda obj: [e.value for e in obj]),
    nullable=True, index=True,
    comment="测试领域，从草稿提升时可留空",
)
```

- [ ] **Step 3: 修改 TestCaseCreate schema — age/domain 改为 Optional**

```python
age: Optional[float] = None
domain: Optional[TestDomain] = None
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/models/rag_eval/draft.py backend/src/models/rag_eval/test_case.py backend/src/schemas/rag_eval/test_case.py
git commit -m "refactor: ORM 和 test_case schema 中 age/domain 改为可空"
```
