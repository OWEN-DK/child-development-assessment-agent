"""提示词存储层 - 基于新统一表结构"""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc

from src.models.prompt_metadata import PromptMetadata
from src.models.prompt_version import PromptVersion
from src.service.cache_service import cache_service
from src.utils.logger import logger
from src.utils.exceptions import ResourceNotFoundException
from src.utils.serializers import create_serializer, safe_isoformat


_serialize_prompt_version_list = create_serializer(
    PromptVersion,
    {
        "id": None,
        "prompt_key": None,
        "version_label": None,
        "version_number": None,
        "created_by": None,
        "created_at": safe_isoformat,
        "variables_extracted": None,
        "change_summary": None,
    }
)

_serialize_prompt_version_detail = create_serializer(
    PromptVersion,
    {
        "id": None,
        "prompt_key": None,
        "version_label": None,
        "version_number": None,
        "content": None,
        "content_hash": None,
        "variables_extracted": None,
        "change_impact": None,
        "change_summary": None,
        "tags": None,
        "fallback": None,
        "created_by": None,
        "created_at": safe_isoformat,
    }
)


class PromptStorage:
    def __init__(self):
        self._session_factory = None

    def _get_session_factory(self):
        if self._session_factory is None:
            from src.core.database import async_session_factory
            self._session_factory = async_session_factory
        return self._session_factory

    async def create_prompt_version(
        self,
        prompt_key: str,
        content: str,
        description: Optional[str] = None,
        created_by: Optional[str] = None,
        variables: Optional[list] = None,
        tags: Optional[list] = None,
        fallback: Optional[str] = None,
    ) -> str:
        if variables:
            from src.core.prompt.validator import PromptValidator
            result = PromptValidator.validate_variables(prompt_key, content, variables)
            if not result.is_valid:
                logger.warning(f"提示词 '{prompt_key}' 占位符不匹配: missing={result.missing}, extra={result.extra}")

        session_factory = self._get_session_factory()
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        async with session_factory() as session:
            # 检查内容是否已存在
            from sqlalchemy import select
            existing = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_key == prompt_key,
                    PromptVersion.content_hash == content_hash,
                )
            )
            existing = existing.scalar_one_or_none()
            if existing:
                logger.info(f"提示词内容未变化，返回现有版本：{existing.version_label}")
                return existing.version_label

            # 获取最新版本号
            latest = await session.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_key == prompt_key)
                .order_by(desc(PromptVersion.version_number))
                .limit(1)
            )
            latest = latest.scalar_one_or_none()

            next_version_number = (latest.version_number + 1) if latest else 1
            version_label = f"v{next_version_number}"

            new_version = PromptVersion(
                id=f"{prompt_key}_{version_label}",
                prompt_key=prompt_key,
                version_label=version_label,
                version_number=next_version_number,
                content=content,
                content_hash=content_hash,
                variables_extracted=variables,
                change_summary=description,
                created_by=created_by,
                tags=tags,
                fallback=fallback,
            )
            session.add(new_version)
            await session.commit()

        await cache_service.invalidate_tag(f"prompt:{prompt_key}")
        logger.info(f"提示词新版本已创建：{prompt_key} {version_label}")
        return version_label

    async def get_prompt_version(self, prompt_key: str, version: Optional[str] = None) -> Optional[PromptVersion]:
        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            if version:
                result = await session.execute(
                    select(PromptVersion).where(
                        PromptVersion.prompt_key == prompt_key,
                        PromptVersion.version_label == version,
                    )
                )
                return result.scalar_one_or_none()
            result = await session.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_key == prompt_key)
                .order_by(desc(PromptVersion.version_number))
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def list_versions(self, prompt_key: str) -> list[dict]:
        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_key == prompt_key)
                .order_by(desc(PromptVersion.version_number))
            )
            versions = result.scalars().all()
            return [_serialize_prompt_version_list(v) for v in versions]

    async def get_version_detail(self, prompt_key: str, version: str) -> Optional[dict]:
        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_key == prompt_key,
                    PromptVersion.version_label == version,
                )
            )
            pv = result.scalar_one_or_none()
            if not pv:
                return None
            return _serialize_prompt_version_detail(pv)

    async def get_versions_for_compare(self, prompt_key: str, version_1: str, version_2: str) -> tuple:
        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_key == prompt_key,
                    PromptVersion.version_label.in_([version_1, version_2]),
                )
            )
            versions = result.scalars().all()
            version_map = {v.version_label: v for v in versions if v.version_label in [version_1, version_2]}
            if len(version_map) != 2:
                raise ResourceNotFoundException(message="提示词版本未找到")
            return version_map[version_1], version_map[version_2]

    async def get_or_create_metadata(
        self,
        prompt_key: str,
        name_zh: str,
        purpose: str,
        category: str,
        subcategory: Optional[str] = None,
        is_system: bool = False,
        created_by: Optional[str] = None,
    ) -> PromptMetadata:
        """获取或创建提示词元数据"""
        from src.models.prompt_enums import PromptCategory

        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PromptMetadata).where(PromptMetadata.prompt_key == prompt_key)
            )
            metadata = result.scalar_one_or_none()

            if not metadata:
                metadata = PromptMetadata(
                    prompt_key=prompt_key,
                    name_zh=name_zh,
                    purpose=purpose,
                    category=PromptCategory(category),
                    subcategory=subcategory,
                    is_system=is_system,
                    created_by=created_by,
                )
                session.add(metadata)
                await session.commit()
                await session.refresh(metadata)

            return metadata

    def _get_fallback_prompt(self, prompt_key: str) -> str:
        from src.core.prompts_fallback import (
            ASSESSMENT_SYSTEM_PROMPT, CATEGORY_INFERENCE_PROMPT,
            DRAFT_GENERATION_RAG_PROMPT, INTENSITY_INFERENCE_PROMPT,
            LAYER3_DEVIATION_ANALYSIS_PROMPT, LAYER3_HALLUCINATION_DETECTION_PROMPT,
            METADATA_EXTRACTION_PROMPT, QUERY_REWRITE_PROMPT,
            RAG_EVAL_METRIC_ANSWER_RELEVANCY_GENERATE_PROMPT,
            RAG_EVAL_METRIC_FAITHFULNESS_BATCH_VERIFY_PROMPT,
            RAG_EVAL_METRIC_FAITHFULNESS_EXTRACT_CLAIMS_PROMPT,
            RAG_EVAL_METRIC_FAITHFULNESS_VERIFY_CLAIM_PROMPT,
            RAG_EVAL_METRIC_GROUNDEDNESS_BATCH_PROMPT,
            RAG_EVAL_METRIC_GROUNDEDNESS_PROMPT,
            RAG_QUERY_TEMPLATE, REPORTING_SYSTEM_PROMPT, SCORING_SYSTEM_PROMPT,
            SYNONYM_EXPANSION_PROMPT, TEST_CASE_DRAFT_GENERATION_PROMPT,
            TEST_CASE_GENERATION_CHUNK_GROUNDED_PROMPT, VALIDATION_SYSTEM_PROMPT)
        fallbacks = {
            "rag_query_rewrite": QUERY_REWRITE_PROMPT, "synonym_expansion": SYNONYM_EXPANSION_PROMPT,
            "rag_query_template": RAG_QUERY_TEMPLATE,
            "metadata_extraction": METADATA_EXTRACTION_PROMPT, "test_case_generation": TEST_CASE_DRAFT_GENERATION_PROMPT,
            "test_case_generation_chunk_grounded": TEST_CASE_GENERATION_CHUNK_GROUNDED_PROMPT,
            "validation": VALIDATION_SYSTEM_PROMPT, "intensity_inference": INTENSITY_INFERENCE_PROMPT,
            "category_inference": CATEGORY_INFERENCE_PROMPT, "child_assessment": ASSESSMENT_SYSTEM_PROMPT,
            "assessment_system": ASSESSMENT_SYSTEM_PROMPT, "scoring": SCORING_SYSTEM_PROMPT,
            "scoring_system": SCORING_SYSTEM_PROMPT, "report_generation": REPORTING_SYSTEM_PROMPT,
            "reporting_system": REPORTING_SYSTEM_PROMPT, "draft_generation_rag": DRAFT_GENERATION_RAG_PROMPT,
            "rag.eval.diagnosis.layer3.deviation_analysis": LAYER3_DEVIATION_ANALYSIS_PROMPT,
            "rag.eval.diagnosis.layer3.hallucination_detection": LAYER3_HALLUCINATION_DETECTION_PROMPT,
            "rag.eval.metric.groundedness": RAG_EVAL_METRIC_GROUNDEDNESS_PROMPT,
            "rag.eval.metric.groundedness_batch": RAG_EVAL_METRIC_GROUNDEDNESS_BATCH_PROMPT,
            "rag.eval.metric.faithfulness_extract_claims": RAG_EVAL_METRIC_FAITHFULNESS_EXTRACT_CLAIMS_PROMPT,
            "rag.eval.metric.faithfulness_verify_claim": RAG_EVAL_METRIC_FAITHFULNESS_VERIFY_CLAIM_PROMPT,
            "rag.eval.metric.faithfulness_batch_verify": RAG_EVAL_METRIC_FAITHFULNESS_BATCH_VERIFY_PROMPT,
            "rag.eval.metric.answer_relevancy_generate": RAG_EVAL_METRIC_ANSWER_RELEVANCY_GENERATE_PROMPT,
        }
        return fallbacks.get(prompt_key, "You are a helpful assistant.")
