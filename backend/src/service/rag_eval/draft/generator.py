"""DraftGenerator - 从文档分块生成 QA 草稿"""

import asyncio
import json
from typing import Awaitable, Callable, Optional

from json_repair import repair_json as _repair

from src.schemas.rag_eval.draft import BookMetadata, DraftCreate, DraftGenerationConfig
from src.schemas.llm import LLMMessage, LLMRequest
from src.config.core.manager import ConfigManager
from src.core.llm.factory import LLMServiceFactoryCompat
from src.models.rag_eval.enums import DifficultyLevel, TestDomain
from src.utils.age_stage import calculate_age_stage_label
from src.utils.embedding_helper import EmbeddingHelper
from src.utils.logger import logger


_DOMAIN_LABELS = {
    "gross_motor": "大运动", "fine_motor": "精细动作", "language": "语言",
    "cognitive": "认知", "social_emotional": "社交情绪", "sensory_integration": "感觉统合",
}


class DraftGenerator:
    """从文档分块生成 QA 草稿——每分块一次 LLM 调用，覆盖所有年龄段和领域组合"""

    def __init__(
        self,
        config_cache: Optional[ConfigManager] = None,
        embedding_helper: Optional[EmbeddingHelper] = None,
    ):
        self._config = config_cache or ConfigManager()
        self._embedding = embedding_helper

    async def generate(
        self, chunks: list[dict], metadata: BookMetadata, config: DraftGenerationConfig,
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
        draft_batch_callback: Optional[Callable[[list[DraftCreate]], Awaitable[None]]] = None,
    ) -> list[DraftCreate]:
        """从分块生成草稿，每个分块一次 LLM 调用覆盖所有 (age_range, domain) 组合"""

        age_ranges = config.custom_age_ranges or metadata.age_ranges or [(0, 6)]
        domains = config.custom_domains or metadata.domains or ["gross_motor"]
        concurrency = self._config.get_config_value("rag.eval.draft.concurrency", 15)
        sem = asyncio.Semaphore(concurrency)

        async def _wrapper(chunk):
            async with sem:
                try:
                    return await self._generate_for_chunk_all_combos(chunk, age_ranges, domains, config)
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

    async def _generate_for_chunk_all_combos(
        self, chunk: dict, age_ranges: list[tuple[float, float]],
        domains: list[str], config: DraftGenerationConfig,
    ) -> list[DraftCreate]:
        """单次 LLM 调用为一个分块生成所有 (年龄段 × 领域) 组合的 QA 问题"""
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

        age_descs = []
        for ar in age_ranges:
            mid = (ar[0] + ar[1]) / 2
            label = calculate_age_stage_label(mid)
            age_descs.append(f"{mid}岁({label})")

        domain_labels = [_DOMAIN_LABELS.get(d, d) for d in domains]

        combos_desc = "\n".join(
            f"  - {ad} × {dl} (domain={d})"
            for ad, (_, _, d) in zip(age_descs, [(None, None, d) for d in domains])
            for ad in age_descs
        ) if len(age_descs) == 1 and len(domain_labels) == 1 else ""

        # Build combo list for the prompt
        combo_lines = []
        for ar in age_ranges:
            mid = (ar[0] + ar[1]) / 2
            label = calculate_age_stage_label(mid)
            for d in domains:
                dl = _DOMAIN_LABELS.get(d, d)
                combo_lines.append(f"  age={mid}, domain=\"{d}\" ({dl})")
        combos_str = "\n".join(combo_lines)

        # Per-combo question count
        q_per_combo = max(1, config.max_qa_per_chunk // max(1, len(age_ranges) * len(domains)))
        q_per_combo = max(1, min(q_per_combo, 2))

        prompt = (
            f"你是一名儿童发展评估专家。以下文档内容适用于多个年龄段和发展领域。\n"
            f"对每个 (年龄段, 领域) 组合生成 {q_per_combo} 个评估问题。\n"
            f"组合列表:\n{combos_str}\n\n"
            f"文档内容: {content[:2500]}\n\n"
            f"返回 JSON 数组，每个元素包含 age, domain, query, description, "
            f"expected_keywords, answer_points, difficulty_level:\n"
            f"[{{\"age\": 1.5, \"domain\": \"gross_motor\", \"query\": \"...\", "
            f"\"description\": \"...\", \"expected_keywords\": [\"...\"], "
            f"\"answer_points\": [\"...\"], \"difficulty_level\": \"easy\"}}]"
        )

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

            return self._build_drafts(items[:config.max_qa_per_chunk * len(age_ranges) * len(domains)],
                                      age_ranges, domains, chunk_id, page, content)
        except Exception as e:
            logger.error(f"LLM 生成失败 chunk={chunk_id}: {e}")
            return []

    def _build_drafts(
        self, items: list[dict], age_ranges: list[tuple[float, float]],
        domains: list[str], chunk_id: str, page: Optional[int], content: str,
    ) -> list[DraftCreate]:
        """将 LLM 输出解析为 DraftCreate 列表，自动匹配年龄标签"""
        drafts = []
        for item in items:
            q = item.get("query", "")
            if not q:
                continue

            age = float(item.get("age", 0))
            domain_str = item.get("domain", "")

            if domain_str not in domains:
                continue

            age_label = calculate_age_stage_label(age)

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
            try:
                dom = TestDomain(domain_str)
            except ValueError:
                dom = TestDomain.GROSS_MOTOR

            drafts.append(DraftCreate(
                query=q, age=age, age_stage_label=age_label, domain=dom,
                description=item.get("description"),
                expected_keywords=kw, answer_points=ap,
                difficulty_level=diff, source_chunk_id=chunk_id,
                source_page=page, source_content_snippet=content[:500],
                generation_params={"chunk_id": chunk_id, "domain": domain_str},
            ))
        return drafts
