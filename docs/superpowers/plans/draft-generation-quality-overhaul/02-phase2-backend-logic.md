# 阶段 2：后端核心逻辑重构（含 PromptManager 接入）

> 前置：阶段 1 完成。
>
> **关键变更：** PromptManager 接入与 generator 重写合并为 Task 4，一步到位。避免同一文件连续两次大改。

---

### Task 4: 重写 DraftGenerator — 移除笛卡尔积 + 接入 PromptManager

**Files:**
- Rewrite: `backend/src/service/rag_eval/draft/generator.py`
- Modify: `backend/src/core/prompts_fallback.py`
- Modify: `backend/src/core/prompt_impl/initializer.py`

**核心变更：**
1. 移除 `_DOMAIN_LABELS` 常量
2. 移除 `import calculate_age_stage_label`
3. `generate()` 方法签名移除 `metadata` 参数，只保留 `chunks` + `config`
4. `_generate_for_chunk_all_combos` 重写为 `_generate_for_chunk`
5. `_build_drafts` 简化——不再处理 age/domain
6. **接入 PromptManager**：构造函数注入 prompt_manager，`_generate_for_chunk` 通过 PromptManager 加载 prompt 模板，不可用时退回 `_build_fallback_prompt`
7. **新建 prompt 模板**：在 `prompts_fallback.py` 注册 `DRAFT_GENERATION_RAG_PROMPT`，在 `initializer.py` 注册到数据库

- [ ] **Step 1: 在 prompts_fallback.py 中新增 RAG 测试 prompt**

```python
DRAFT_GENERATION_RAG_PROMPT = """\
你是 RAG 系统测试用例设计师。以下是一段文档原文。
请从中提取 {max_qa} 个可直接回答的测试问题。

## 生成约束（强制，不可违反）

1. **忠实性铁律**：生成的 query 必须能从原文直接找到答案
2. **禁止编造**：不允许引入原文未提及的任何概念、数据、理论或术语
3. **答案来源**：answer_points 中的每条必须是原文关键短语或其直接改写
4. **关键词来源**：expected_keywords 中的每个关键词必须出现在原文中
5. **语言一致**：输出语言与原文保持一致

## 如果原文内容不足以生成问题

如果原文过短或无实质内容，返回空数组 []。
不要强行从不相关内容中编造问题。

## 文档原文

{chunk_content}

## 返回格式

必须返回严格的 JSON 数组：
[{{"query": "基于原文可回答的问题", "description": "测试意图描述",
   "expected_keywords": ["原文中的关键词"], "answer_points": ["从原文提取的答案要点"],
   "difficulty_level": "easy|medium|hard"}}]

仅返回 JSON，不要包含任何解释性文字。
"""
```

- [ ] **Step 2: 在 initializer.py 中注册新 prompt**

```python
{
    "key": "draft_generation_rag",
    "content": DRAFT_GENERATION_RAG_PROMPT,
    "name_zh": "RAG 草稿生成",
    "purpose": "从文档分块中生成忠实于原文的 RAG 测试 QA 对",
    "category": "test_case_generation",
    "variables": ["max_qa", "chunk_content"],
    "tags": ["rag_eval", "draft", "chunk_grounded"],
},
```

- [ ] **Step 3: 重写整个 generator.py**

```python
"""DraftGenerator - 从文档分块生成忠实于原文的 QA 草稿"""

import asyncio
import json
from typing import Awaitable, Callable, Optional

from json_repair import repair_json as _repair

from src.schemas.rag_eval.draft import DraftCreate, DraftGenerationConfig
from src.schemas.llm import LLMMessage, LLMRequest
from src.config.core.manager import ConfigManager
from src.core.llm.factory import LLMServiceFactoryCompat
from src.models.rag_eval.enums import DifficultyLevel
from src.utils.embedding_helper import EmbeddingHelper
from src.utils.logger import logger
from src.core.prompt_impl.facade import prompt_manager as _default_prompt_manager


class DraftGenerator:
    """从文档分块生成 QA 草稿——每分块一次 LLM 调用，生成忠实于原文的问答对"""

    def __init__(
        self,
        config_cache: Optional[ConfigManager] = None,
        embedding_helper: Optional[EmbeddingHelper] = None,
        prompt_manager=_default_prompt_manager,  # PromptManager 模块单例
    ):
        self._config = config_cache or ConfigManager()
        self._embedding = embedding_helper
        self._prompt_manager = prompt_manager

    async def generate(
        self, chunks: list[dict], config: DraftGenerationConfig,
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
        draft_batch_callback: Optional[Callable[[list[DraftCreate]], Awaitable[None]]] = None,
    ) -> list[DraftCreate]:
        """从分块生成草稿，每个分块独立生成 N 个 QA 对"""

        concurrency = self._config.get_config_value("rag.eval.draft.concurrency", 15)
        sem = asyncio.Semaphore(concurrency)

        async def _wrapper(chunk):
            async with sem:
                try:
                    return await self._generate_for_chunk(chunk, config)
                except Exception as e:
                    logger.error(f"生成失败 chunk={chunk.get('id')}: {e}")
                    return []

        all_coros = [_wrapper(c) for c in chunks]
        total = len(all_coros)
        if total == 0:
            return []

        drafts = []
        completed = 0
        for coro in asyncio.as_completed(all_coros):
            batch = await coro
            drafts.extend(batch)
            completed += 1
            if draft_batch_callback and batch:
                await draft_batch_callback(batch)
            if progress_callback:
                await progress_callback(completed, total)

        logger.info(f"草稿生成: {len(drafts)} 个 (来自 {total} 个分块)")
        return drafts

    def _build_prompt(self, max_qa: int, content: str) -> str:
        """构建 fallback prompt（PromptManager 不可用时使用）"""
        return (
            f"你是一名 RAG 系统测试用例设计师。以下是一段文档原文。\n"
            f"请从中提取 {max_qa} 个可直接回答的测试问题。\n\n"
            f"## 生成约束（强制）\n"
            f"1. **忠实性铁律**：query 必须能从原文直接找到答案\n"
            f"2. **禁止编造**：不允许引入原文未提及的概念、数据或术语\n"
            f"3. **答案来源**：answer_points 中每条必须是原文关键短语或其直接改写\n"
            f"4. **关键词来源**：expected_keywords 中每个词必须出现在原文中\n"
            f"5. **语言一致**：输出语言与原文保持一致\n\n"
            f"## 如果原文内容不足以生成问题\n"
            f"如果原文过短或无实质内容，返回空数组 []。不要强行编造。\n\n"
            f"## 文档原文\n{content}\n\n"
            f"## 返回格式\n"
            f"返回 JSON 数组，每个元素：\n"
            f'[{{"query": "基于原文可回答的问题", '
            f'"description": "测试意图描述", '
            f'"expected_keywords": ["原文中的关键词"], '
            f'"answer_points": ["从原文提取的答案要点"], '
            f'"difficulty_level": "easy|medium|hard"}}]\n\n'
            f"仅返回 JSON，不要包含解释性文字。"
        )

    async def _generate_for_chunk(
        self, chunk: dict, config: DraftGenerationConfig,
    ) -> list[DraftCreate]:
        """单次 LLM 调用为一个分块生成 QA 对，忠实于原文"""
        content = chunk.get("content", "")
        chunk_id = chunk.get("id", "")

        page_raw = chunk.get("page")
        page = None
        if page_raw is not None:
            try:
                page = int(page_raw)
            except (ValueError, TypeError):
                page = None

        if not content.strip():
            return []

        max_qa = config.max_qa_per_chunk
        max_content_length = self._config.get_config_value(
            "rag.eval.draft.max_chunk_content_length", 2500,
        )

        # 优先使用 PromptManager，不可用时退回 fallback
        prompt = None
        if self._prompt_manager:
            try:
                prompt = await self._prompt_manager.get_prompt(
                    "draft_generation_rag",
                    variables={"max_qa": max_qa, "chunk_content": content[:max_content_length]},
                )
            except Exception as e:
                logger.warning(f"PromptManager 加载失败，使用 fallback: {e}")

        if not prompt:
            prompt = self._build_prompt(max_qa, content[:max_content_length])

        try:
            model = self._config.get_config_value("rag.eval.draft.llm_model", "") or "qwen-plus"
            temperature = self._config.get_config_value("rag.eval.draft.temperature", 0.3)
            max_tokens = self._config.get_config_value("rag.eval.draft.max_tokens", 2048)
            llm = LLMServiceFactoryCompat.create(
                model_name=model, temperature=temperature, max_tokens=max_tokens,
            )
            resp = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model_name=model,
                temperature=temperature,
                max_tokens=max_tokens,
            ))

            try:
                items = json.loads(resp.content.strip())
            except json.JSONDecodeError:
                items = json.loads(_repair(resp.content.strip()))

            if not isinstance(items, list):
                items = [items]

            return self._build_drafts(items[:max_qa], chunk_id, page, content)
        except Exception as e:
            logger.error(f"LLM 生成失败 chunk={chunk_id}: {e}")
            return []

    def _build_drafts(
        self, items: list[dict], chunk_id: str, page: Optional[int], content: str,
    ) -> list[DraftCreate]:
        """将 LLM 输出解析为 DraftCreate 列表"""
        drafts = []
        for item in items:
            q = item.get("query", "")
            if not q:
                continue
            if item.get("skip"):
                continue

            kw = item.get("expected_keywords", [])
            if isinstance(kw, str):
                kw = [kw]
            ap = item.get("answer_points", [])
            if isinstance(ap, str):
                ap = [ap]

            try:
                diff = DifficultyLevel(item.get("difficulty_level", "easy"))
            except ValueError:
                diff = DifficultyLevel.EASY

            drafts.append(DraftCreate(
                query=q,
                description=item.get("description"),
                expected_keywords=kw, answer_points=ap,
                difficulty_level=diff, source_chunk_id=chunk_id,
                source_page=page, source_content_snippet=content[:500],
                generation_params={"chunk_id": chunk_id},
            ))
        return drafts
```

- [ ] **Step 4: 验证无编译错误**

Run: `cd backend && uv run python -c "from src.service.rag_eval.draft.generator import DraftGenerator; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add backend/src/service/rag_eval/draft/generator.py backend/src/core/prompts_fallback.py backend/src/core/prompt_impl/initializer.py
git commit -m "refactor: DraftGenerator 移除 age/domain 笛卡尔积 + 接入 PromptManager，一步到位"
```

---

### Task 5: 简化 BookMetadataAnalyzer — 仅提取 topic_summary

**Files:**
- Modify: `backend/src/service/rag_eval/draft/book_analyzer.py`

- [ ] **Step 1: 重写 book_analyzer.py**

```python
"""BookMetadataAnalyzer - 从文档中提取主题摘要"""

import json

from json_repair import repair_json

from src.schemas.rag_eval.draft import BookMetadata
from src.schemas.llm import LLMMessage, LLMRequest
from src.config.core.manager import ConfigManager
from src.core.llm.factory import LLMServiceFactoryCompat
from src.utils.logger import logger


_SUMMARY_PROMPT = """分析以下文档，用一句话概括其核心主题。返回 JSON:
{{"topic_summary": "..."}}
文档标题: {title} | 类型: {file_type}
内容摘要: {content_summary}"""


class BookMetadataAnalyzer:
    """从文档中提取 topic_summary，用于辅助生成 prompt 上下文"""

    def __init__(self, config_cache: ConfigManager | None = None):
        self._config = config_cache or ConfigManager()

    async def analyze(
        self, title: str, file_type: str, content_summary: str,
    ) -> BookMetadata:
        """提取文档主题摘要"""
        try:
            prompt = _SUMMARY_PROMPT.format(
                title=title, file_type=file_type,
                content_summary=content_summary or "（无摘要）",
            )
            model = self._config.get_config_value("rag.eval.draft.llm_model", "") or "qwen-plus"
            llm = LLMServiceFactoryCompat.create(
                model_name=model, temperature=0.1, max_tokens=256,
            )
            resp = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model_name=model, temperature=0.1, max_tokens=256,
            ))

            try:
                data = json.loads(resp.content.strip())
            except json.JSONDecodeError:
                data = json.loads(repair_json(resp.content.strip()))

            return BookMetadata(
                topic_summary=data.get("topic_summary", ""),
            )
        except Exception as e:
            logger.warning(f"元数据提取失败: {e}")
            return BookMetadata()
```

> **注意：** `analyze()` 签名从 `(document: SourceDocumentRead)` 改为 `(title, file_type, content_summary)`，facade 调用点需同步修改。

- [ ] **Step 2: 验证无编译错误**

Run: `cd backend && uv run python -c "from src.service.rag_eval.draft.book_analyzer import BookMetadataAnalyzer; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/src/service/rag_eval/draft/book_analyzer.py
git commit -m "refactor: BookMetadataAnalyzer 简化为仅提取 topic_summary"
```

---

### Task 6: 重写 FaithfulnessChecker — 改对比对象为 answer_points vs source

**Files:**
- Modify: `backend/src/service/rag_eval/draft/faithfulness_checker.py`

**核心变更：** embedding 对比从 `(description vs source)` 改为 `(answer_points 拼接 vs source)`。

- [ ] **Step 1: 修改 check 方法 — 使用 answer_points 构建对比文本**

```python
async def check(self, draft: DraftCreate, source_content: str) -> float:
    """评估草稿忠实度——比较 answer_points 与原文的语义相似度"""
    if not source_content:
        return 0.5

    answer_points = draft.answer_points or []
    if answer_points:
        compare_text = "。".join(str(p) for p in answer_points)
    else:
        compare_text = draft.description or ""
    compare_text = compare_text[:500]

    if not compare_text.strip():
        return 0.5

    score = await self._embedding_faithfulness_async(compare_text, source_content[:1500])

    if score < 0.6:
        llm_score = await self._llm_faithfulness_check(compare_text, source_content[:1500])
        if llm_score is not None:
            return max(score, llm_score)

    return score
```

- [ ] **Step 2: 修改 LLM check prompt — 明确比较"答案要点"与"原文"**

```python
async def _llm_faithfulness_check(self, answer_text: str, source_content: str) -> float:
    """使用 LLM 评估答案要点是否忠实于原文"""
    prompt = (
        f"评估以下「答案要点」是否忠实于「原文」。\n"
        f"返回 JSON: {{\"faithfulness_score\": 0.85, \"reason\": \"...\"}}\n"
        f"评分标准：\n"
        f"- 1.0 = 答案要点完全来自原文\n"
        f"- 0.5 = 部分要点可在原文找到\n"
        f"- 0.0 = 答案要点与原文无关\n\n"
        f"原文：{source_content[:1500]}\n\n"
        f"答案要点：{answer_text[:800]}"
    )
    # ... 后续 LLM 调用逻辑不变
```

- [ ] **Step 3: 验证无编译错误**

Run: `cd backend && uv run python -c "from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/src/service/rag_eval/draft/faithfulness_checker.py
git commit -m "fix: FaithfulnessChecker 改用 answer_points vs source 对比，修复评分偏低问题"
```

---

### Task 7: 重写 DraftEngineFacade — 适配简化后的生成器

**Files:**
- Modify: `backend/src/service/rag_eval/draft/facade.py`

**核心变更：**
1. `_run_generation` 中移除 age_ranges/domains 参数传递
2. `_tc_dict` 中 age/domain 设为 None（test_cases 已允许 NULL）
3. `get_drafts` 移除 domain 筛选参数
4. SSE 事件中移除 age_ranges/domains 字段
5. `analyze` 调用改为传 `title, file_type, content_summary`
6. **确认 `generate()` 返回值与 `draft_batch_callback` 的关系**：facade 当前忽略 `generate()` 返回值，完全依赖 callback 收集草稿。新实现保持这一行为不变。

- [ ] **Step 1: 修改 `_run_generation` — generate 签名适配**

```python
# 原：drafts = await self._gen.generate(chunks, meta, config, ...)
# 改：drafts = await self._gen.generate(chunks, config, ...)
```

移除所有 `age_ranges`、`domains` 变量的构建和传递。

- [ ] **Step 2: 修改 metadata 分析调用**

```python
# 原：meta = await self._analyzer.analyze(doc)
# 改：
meta = await self._analyzer.analyze(
    title=doc.title or "",
    file_type=doc.file_type or "",
    content_summary=getattr(doc, "content_summary", None) or "",
)
```

- [ ] **Step 3: 修改 `_tc_dict` — age/domain 设为 None，签名新增 source_document_id 参数**

```python
@staticmethod
def _tc_dict(o, draft_id, source_document_id) -> dict:
    return dict(
        id=generate_prefixed_id("tc"), query=o.query,
        age=None, age_stage_label="", domain=None,
        description=o.description,
        expected_knowledge_ids=o.expected_knowledge_ids or [],
        expected_keywords=o.expected_keywords or [],
        answer_points_summary=(o.description or "")[:500],
        difficulty_level=o.difficulty_level,
        professional_terms=o.professional_terms or [],
        source="draft", source_draft_id=draft_id,
        source_document_id=source_document_id, version=1,
    )
```

**调用点同步更新（共 2 处）：**

> `o` 来自 `await self._draft_repo.get_by_id(...)` 返回的 ORM 对象，`source_document_id` 是 ORM 列，可直接访问。

```python
# 第 201 行 — 单条提升（o 是 TestCaseDraft ORM 对象）
tc = await self._tc_repo.create(self._tc_dict(o, draft_id, o.source_document_id))

# 第 212 行 — 批量提升（o 是 TestCaseDraft ORM 对象）
tc = await self._tc_repo.get_by_source_draft(did) or await self._tc_repo.create(
    self._tc_dict(o, did, o.source_document_id))
```

- [ ] **Step 4: 修改 `get_drafts` — 移除 domain 筛选**

```python
async def get_drafts(self, page: int = 1, page_size: int = 20,
                     status: Optional[str] = None,
                     source_document_id: Optional[str] = None) -> dict:
```

- [ ] **Step 5: 更新 SSE 事件契约 — 移除 age_ranges/domains**

新的 SSE 事件 schema：

```python
# metadata_analyzed 事件
await self._publish_event(task_id, "metadata_analyzed", {
    "topic_summary": metadata.topic_summary,
})

# chunk_progress 事件（不变）
await self._publish_event(task_id, "chunk_progress", {
    "completed": completed, "total": total,
})

# complete 事件
await self._publish_event(task_id, "complete", {
    "batch_id": batch_id, "total_drafts": len(all_drafts),
})

# error 事件（不变）
await self._publish_event(task_id, "error", {
    "message": str(e),
})
```

> **前端对照：** `useDraftGenerationProgress.ts` 已按上述事件结构实现（progress / complete / error 类型），需确认新后端事件字段与前端 hook 一致。

- [ ] **Step 6: 修改 save 逻辑 — 移除 age/domain 字段**

持久化草稿时不再传 age/age_stage_label/domain。

- [ ] **Step 7: 验证无编译错误**

Run: `cd backend && uv run python -c "from src.service.rag_eval.draft.facade import DraftEngineFacade; print('OK')"`

- [ ] **Step 8: Commit**

```bash
git add backend/src/service/rag_eval/draft/facade.py
git commit -m "refactor: DraftEngineFacade 适配简化后的生成器，移除 age/domain 参数传递"
```

---

### Task 8: 修改 DraftController — 移除 domain 查询参数

**Files:**
- Modify: `backend/src/controller/rag_eval/draft_controller.py`

- [ ] **Step 1: 移除 GET /drafts 的 domain 查询参数**

```python
@router.get("/drafts")
async def list_drafts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    ...  # 移除 domain 参数
):
```

- [ ] **Step 2: 验证无编译错误**

- [ ] **Step 3: Commit**

```bash
git add backend/src/controller/rag_eval/draft_controller.py
git commit -m "refactor: DraftController 移除 domain 查询参数"
```
