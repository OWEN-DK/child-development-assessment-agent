# 04 - DraftEngine 详细设计

## 需求

从上传的文档（PDF/EPUB/TXT/DOCX）自动生成测试用例草稿，经过忠实度验证和语义去重后，保存到 `test_case_drafts` 表，供人工审核后导入为正式测试用例。

## 当前问题

| 问题 | 位置 | 影响 |
|------|------|------|
| God Class 1157行 | `draft_service.py` | 无法维护，职责不清 |
| 硬编码模型名和参数 | 多处散布 | 模型切换需改代码 |
| 无忠实度校验 | 缺失 | 草稿可能偏离源文档 |
| 去重策略简陋 | 仅文本匹配 | 语义重复草稿通过 |
| 无书籍元数据分析 | 缺失 | 年龄/领域靠人工填 |
| SSE 进度不可靠 | `draft_generator_facade.py` | 断线无法恢复 |

## 引擎架构

```
DraftEngineFacade (facade.py, ~120行)
  ├── BookMetadataAnalyzer (book_analyzer.py, ~120行)
  ├── DraftGenerator (generator.py, ~200行)
  ├── FaithfulnessChecker (faithfulness_checker.py, ~150行)
  └── DraftDeduplicator (deduplicator.py, ~100行)
```

### 流程

```
上传文档 → 解析分块 → BookMetadataAnalyzer → DraftGenerator
         → FaithfulnessChecker → DraftDeduplicator → 保存 → SSE 进度推送
```

## 组件设计

### DraftEngineFacade

```python
class DraftEngineFacade:
    """草稿引擎门面，协调各子组件"""

    def __init__(
        self,
        draft_generator: DraftGenerator,
        faithfulness_checker: FaithfulnessChecker,
        deduplicator: DraftDeduplicator,
        book_analyzer: BookMetadataAnalyzer,
        draft_repository: DraftRepository,
        test_case_repository: TestCaseRepository,
        config_manager: ConfigManager,
        prompt_manager: PromptManager,
        llm_factory: LLMServiceFactory,
        async_task_manager: AsyncTaskManager,
    ): ...

    async def start_generation(
        self,
        source_document_id: str,
        config: DraftGenerationConfig | None = None,
    ) -> str:
        """启动草稿生成任务，返回 task_id

        流程：
        1. 验证文档存在且状态为 ready
        2. 通过 AsyncTaskManager 启动后台任务 _run_generation
        3. 返回 task_id，前端通过 SSE 监听进度
        """

    async def _run_generation(
        self,
        source_document_id: str,
        task_id: str,
        config: DraftGenerationConfig,
    ) -> None:
        """后台执行完整生成流程

        步骤：
        1. SSE: {type: "generation_started", data: {document_id, task_id}}
        2. book_analyzer.analyze(document) → metadata
        3. SSE: {type: "metadata_analyzed", data: metadata}
        4. draft_generator.generate(chunks, metadata, config) → drafts
        5. SSE: {type: "drafts_generated", data: {count: len(drafts)}}
        6. faithfulness_checker.batch_check(drafts) → 带评分的 drafts
        7. deduplicator.deduplicate(drafts) → 去重后的 drafts
        8. 批量保存到 test_case_drafts
        9. SSE: {type: "generation_completed", data: {saved_count, skipped_count}}
        """

    async def get_drafts(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        domain: str | None = None,
        source_document_id: str | None = None,
        batch_id: str | None = None,
    ) -> DraftList:
        """分页查询草稿"""

    async def get_draft(self, draft_id: str) -> DraftRead:
        """获取单个草稿"""

    async def update_draft(self, draft_id: str, update: DraftUpdate) -> DraftRead:
        """更新草稿"""

    async def review_draft(self, draft_id: str, review: DraftReview) -> TestCaseRead:
        """审核草稿 → 创建正式测试用例

        approve: 创建 TestCase，草稿状态改为 reviewed
        reject: 草稿状态改为 rejected
        """

    async def batch_import(self, draft_ids: list[str]) -> list[TestCaseRead]:
        """批量导入已审核草稿为测试用例"""

    async def batch_delete(self, draft_ids: list[str]) -> None:
        """批量删除草稿"""

    async def delete_by_document(self, source_document_id: str) -> int:
        """删除指定文档的所有草稿，返回删除数量"""
```

### BookMetadataAnalyzer

```python
class BookMetadataAnalyzer:
    """从文档中提取年龄范围和领域元数据

    分析文档的标题、目录、章节结构，推断适用的年龄范围和测试领域。
    使用 LLM 辅助分析，结果缓存到 source_documents.content_summary。
    """

    def __init__(
        self,
        llm_factory: LLMServiceFactory,
        config_manager: ConfigManager,
        prompt_manager: PromptManager,
    ): ...

    async def analyze(self, document: SourceDocumentRead) -> BookMetadata:
        """分析文档元数据

        返回：
        - age_ranges: 推断的适用年龄范围列表，如 [(0, 0.5), (0.5, 1)]
        - domains: 推断的测试领域列表，如 ["gross_motor", "language"]
        - difficulty_hint: 推断的难度级别
        - topic_summary: 主题摘要
        """

    def _extract_chunks_by_metadata(
        self,
        chunks: list[DocumentChunk],
        metadata: BookMetadata,
    ) -> list[DocumentChunk]:
        """根据元数据过滤和分组分块"""
```

**Schema:**

```python
class BookMetadata(BaseModel):
    """文档元数据分析结果"""
    age_ranges: list[tuple[float, float]]  # [(min_age, max_age), ...]
    domains: list[str]                      # TestDomain 值列表
    difficulty_hint: str | None = None      # easy/medium/hard
    topic_summary: str = ""
```

### DraftGenerator

```python
class DraftGenerator:
    """从文档分块生成 QA 草稿

    核心流程：
    1. 按年龄×领域组合规划生成任务
    2. 对每个分块调用 LLM 生成 QA 对
    3. 解析 LLM 输出为 DraftCreate 对象
    """

    def __init__(
        self,
        llm_factory: LLMServiceFactory,
        config_manager: ConfigManager,
        prompt_manager: PromptManager,
        embedding_helper: EmbeddingHelper,
    ): ...

    async def generate(
        self,
        chunks: list[DocumentChunk],
        metadata: BookMetadata,
        config: DraftGenerationConfig,
    ) -> list[DraftCreate]:
        """从分块生成草稿

        对每个 (age_range, domain) 组合，从相关分块中生成 QA 草稿。
        使用 PromptManager 获取 rag.eval.draft.generation_prompt 模板。
        每个分块生成 1-3 个 QA 对（取决于配置）。
        """

    async def _generate_for_chunk(
        self,
        chunk: DocumentChunk,
        age_range: tuple[float, float],
        domain: str,
        config: DraftGenerationConfig,
    ) -> list[DraftCreate]:
        """从单个分块生成草稿

        1. 构建 prompt（注入分块内容、年龄、领域）
        2. 调用 LLM
        3. 使用 json-repair 解析输出
        4. 构建 DraftCreate 对象列表
        """

    def _calculate_age_stage_label(self, age: float) -> str:
        """根据年龄计算年龄段标签

        映射规则：
        - 0-0.5岁 → "0-6m"
        - 0.5-1岁 → "6-12m"
        - 1-2岁 → "1-2y"
        - 2-3岁 → "2-3y"
        - 3-4岁 → "3-4y"
        - 4-6岁 → "4-6y"
        - 6+岁 → "6+y"
        """
```

**Schema:**

```python
class DraftGenerationConfig(BaseModel):
    """草稿生成配置"""
    max_qa_per_chunk: int = 3               # 每个分块最大 QA 数
    min_qa_per_chunk: int = 1               # 每个分块最小 QA 数
    custom_age_ranges: list[tuple[float, float]] | None = None  # 覆盖自动检测
    custom_domains: list[str] | None = None # 覆盖自动检测
```

### FaithfulnessChecker

```python
class FaithfulnessChecker:
    """验证草稿忠实度——确保 QA 内容来自源文档而非 LLM 编造

    使用 embedding 相似度 + LLM 辅助双重校验。
    """

    def __init__(
        self,
        llm_factory: LLMServiceFactory,
        embedding_helper: EmbeddingHelper,
        config_manager: ConfigManager,
    ): ...

    async def check(self, draft: DraftCreate, source_content: str) -> float:
        """检查单个草稿的忠实度

        返回 0-1 的忠实度评分。
        方法：
        1. 计算 draft.description 与 source_content 的 embedding 余弦相似度
        2. 若相似度 < 阈值（默认 0.7），调用 LLM 进行深度校验
        3. 综合评分
        """

    async def batch_check(
        self,
        drafts: list[DraftCreate],
    ) -> list[tuple[DraftCreate, float]]:
        """批量校验忠实度

        返回 [(draft, faithfulness_score), ...]
        批量 embedding 计算，减少 API 调用次数。
        """

    def _embedding_faithfulness(
        self,
        draft_description: str,
        source_content: str,
    ) -> float:
        """基于 embedding 的忠实度快速评分"""
```

### DraftDeduplicator

```python
class DraftDeduplicator:
    """语义去重——过滤语义重复的草稿

    对新生成的草稿之间、以及新草稿与已有草稿之间进行语义相似度比较。
    """

    def __init__(
        self,
        embedding_helper: EmbeddingHelper,
        draft_repository: DraftRepository,
        config_manager: ConfigManager,
    ): ...

    async def deduplicate(
        self,
        drafts: list[tuple[DraftCreate, float]],  # (draft, faithfulness_score)
        source_document_id: str | None = None,
    ) -> list[tuple[DraftCreate, float]]:
        """去重

        步骤：
        1. 计算新草稿之间的 embedding
        2. 内部去重：相似度 > similarity_threshold 的保留分数较高的
        3. 加载同文档已有草稿的 embedding
        4. 外部去重：与已有草稿比较，相似度 > threshold 的跳过
        5. 返回去重后的列表
        """

    def _remove_internal_duplicates(
        self,
        items: list[tuple[DraftCreate, float, list[float]]],  # draft, score, embedding
        threshold: float,
    ) -> list[tuple[DraftCreate, float]]:
        """内部去重：保留忠实度分数较高的"""
```

## 配置 Key

| Key | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `rag.eval.draft.concurrency` | int | 3 | LLM 并发调用数 |
| `rag.eval.draft.max_tokens` | int | 2048 | LLM 单次生成最大 token |
| `rag.eval.draft.llm_model` | str | "" | 空字符串表示使用默认模型 |
| `rag.eval.draft.temperature` | float | 0.3 | LLM 温度 |
| `rag.eval.draft.similarity_threshold` | float | 0.85 | 语义去重相似度阈值 |
| `rag.eval.draft.faithfulness_threshold` | float | 0.7 | 忠实度阈值，低于此值标记警告 |

## Prompt Key

| Key | 说明 |
|-----|------|
| `rag.eval.draft.generation_prompt` | 草稿生成主 prompt，变量: `{chunk_content}`, `{age}`, `{domain}`, `{max_qa}` |

**Prompt 模板变量注入（由 PromptManager 处理）：**

```
输入:
- chunk_content: 文档分块内容
- age: 目标年龄（如 "1.5"）
- domain: 测试领域（如 "gross_motor"）
- max_qa: 最大 QA 数（如 3）

输出要求:
- JSON 数组，每个元素包含 query, description, expected_keywords, answer_points, difficulty_level
- 使用 json-repair 作为后备解析器
```

## SSE 事件

| 事件类型 | 数据 | 说明 |
|----------|------|------|
| `generation_started` | `{document_id, task_id}` | 开始生成 |
| `metadata_analyzed` | `{age_ranges, domains, topic_summary}` | 元数据分析完成 |
| `chunk_progress` | `{current, total, chunk_id}` | 分块处理进度 |
| `drafts_generated` | `{count, batch_id}` | 草稿生成完成 |
| `faithfulness_checked` | `{checked_count, low_faithfulness_count}` | 忠实度校验完成 |
| `deduplication_completed` | `{before_count, after_count}` | 去重完成 |
| `generation_completed` | `{saved_count, skipped_count, batch_id}` | 全部完成 |
| `generation_failed` | `{error: str}` | 生成失败 |

所有 SSE 事件遵循统一格式：`{type: str, data: dict}`

## 验收标准

1. `facade.py` ≤ 120 行，`generator.py` ≤ 200 行，`faithfulness_checker.py` ≤ 150 行，`deduplicator.py` ≤ 100 行，`book_analyzer.py` ≤ 120 行
2. 所有 LLM 调用通过 `llm_factory`，模型名从 `rag.eval.draft.llm_model` 读取
3. 所有 prompt 通过 `prompt_manager.get("rag.eval.draft.generation_prompt")` 获取
4. 忠实度评分写入 `test_case_drafts.faithfulness_score`
5. 语义去重使用 embedding 余弦相似度，阈值可配置
6. SSE 事件统一为 `{type, data}` 格式，异常通过 `generation_failed` 事件推送
7. `BookMetadataAnalyzer` 正确推断年龄范围和领域，覆盖 6 个 `TestDomain`
8. `_calculate_age_stage_label` 映射规则完整覆盖 0-12 岁
9. 审核通过（approve）的草稿自动创建 `TestCase`，`source` 字段为 `draft`
10. 无硬编码值，所有参数通过 `ConfigManager` 读取
11. `DraftEngineFacade` 通过 `RagEvalModule` DI 注入，无 `__new__` 单例
12. LLM 输出使用 `json-repair` 后备解析，`List[str]` 字段处理单字符串转换
13. 后台任务异常不抛出未捕获异常（`Task exception was never retrieved`）
14. `DraftGenerationConfig` 支持覆盖自动检测的年龄和领域
