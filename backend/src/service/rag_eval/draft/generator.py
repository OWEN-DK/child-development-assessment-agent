"""DraftGenerator - 从文档分块生成 QA 草稿"""

import asyncio
import json
from typing import Optional

from json_repair import repair_json as _repair

from src.schemas.rag_eval.draft import BookMetadata, DraftCreate, DraftGenerationConfig
from src.schemas.llm import LLMMessage, LLMRequest
from src.config.core.manager import ConfigManager
from src.models.rag_eval.enums import DifficultyLevel, TestDomain
from src.utils.age_stage import calculate_age_stage_label
from src.utils.embedding_helper import EmbeddingHelper
from src.utils.logger import logger


_DOMAIN_LABELS = {
    "gross_motor": "大运动", "fine_motor": "精细动作", "language": "语言",
    "cognitive": "认知", "social_emotional": "社交情绪", "sensory_integration": "感觉统合",
}


class DraftGenerator:
    """从文档分块生成 QA 草稿"""

    def __init__(
        self,
        llm_factory=None,
        config_cache: Optional[ConfigManager] = None,
        embedding_helper: Optional[EmbeddingHelper] = None,
    ):
        self._llm_factory = llm_factory
        self._config = config_cache or ConfigManager()
        self._embedding = embedding_helper

    async def generate(
        self, chunks: list[dict], metadata: BookMetadata, config: DraftGenerationConfig,
    ) -> list[DraftCreate]:
        """从分块生成草稿，对每个 (age_range, domain) 组合生成 QA 对"""
        if not self._llm_factory:
            logger.warning("LLM 不可用，生成跳过")
            return []

        age_ranges = config.custom_age_ranges or metadata.age_ranges or [(0, 6)]
        domains = config.custom_domains or metadata.domains or ["gross_motor"]
        concurrency = self._config.get_config_value("rag.eval.draft.concurrency", 3)
        sem = asyncio.Semaphore(concurrency)

        async def _wrapper(chunk, age_range, domain):
            async with sem:
                try:
                    return await self._generate_for_chunk(chunk, age_range, domain, config)
                except Exception as e:
                    logger.error(f"生成失败 chunk={chunk.get('id')}: {e}")
                    return []

        all_tasks = [
            _wrapper(chunk, ar, d)
            for ar in age_ranges
            for d in domains
            for chunk in chunks
        ]
        if not all_tasks:
            return []

        results = await asyncio.gather(*all_tasks)
        drafts = [d for batch in results for d in batch]
        logger.info(f"草稿生成: {len(drafts)} 个")
        return drafts

    async def _generate_for_chunk(
        self, chunk: dict, age_range: tuple[float, float], domain: str, config: DraftGenerationConfig,
    ) -> list[DraftCreate]:
        """从单个分块调用 LLM 生成 QA 对"""
        content = chunk.get("content", "")
        chunk_id = chunk.get("id", "")
        page = chunk.get("page")
        if not content.strip():
            return []

        mid_age = (age_range[0] + age_range[1]) / 2
        age_label = calculate_age_stage_label(mid_age)
        domain_label = _DOMAIN_LABELS.get(domain, domain)

        prompt = (
            f"生成 {config.min_qa_per_chunk}-{config.max_qa_per_chunk} 个儿童发展评估测试问题。"
            f"年龄: {mid_age}岁({age_label}) 领域: {domain_label}\n"
            f"内容: {content[:2500]}\n"
            f"返回 JSON 数组: [{{'query':'...','description':'...','expected_keywords':['...'],"
            f"'answer_points':['...'],'difficulty_level':'easy'}}]"
        )

        try:
            model = self._config.get_config_value("rag.eval.draft.llm_model", "")
            llm = await self._llm_factory.create("rag_eval", "langchain")
            resp = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model_name=model or "qwen3.5-plus",
                temperature=self._config.get_config_value("rag.eval.draft.temperature", 0.3),
                max_tokens=self._config.get_config_value("rag.eval.draft.max_tokens", 2048),
            ))

            try:
                items = json.loads(resp.content.strip())
            except json.JSONDecodeError:
                items = json.loads(_repair(resp.content.strip()))

            if not isinstance(items, list):
                items = [items]

            return self._build_drafts(items[:config.max_qa_per_chunk], mid_age, age_label, domain, chunk_id, page, content)
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}")
            return []

    def _build_drafts(
        self, items: list[dict], age: float, label: str, domain: str,
        chunk_id: str, page: Optional[int], content: str,
    ) -> list[DraftCreate]:
        """将 LLM 输出解析为 DraftCreate 列表"""
        drafts = []
        for item in items:
            q = item.get("query", "")
            if not q:
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
            try:
                dom = TestDomain(domain)
            except ValueError:
                dom = TestDomain.GROSS_MOTOR

            drafts.append(DraftCreate(
                query=q, age=age, age_stage_label=label, domain=dom,
                description=item.get("description"),
                expected_keywords=kw, answer_points=ap,
                difficulty_level=diff, source_chunk_id=chunk_id,
                source_page=page, source_content_snippet=content[:500],
                generation_params={"chunk_id": chunk_id, "domain": domain},
            ))
        return drafts

    def _calculate_age_stage_label(self, age: float) -> str:
        """委托给通用工具函数"""
        return calculate_age_stage_label(age)
