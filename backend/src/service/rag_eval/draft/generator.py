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
        prompt_manager=_default_prompt_manager,
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
            f"仅返回 JSON，不要包含任何解释性文字。"
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
