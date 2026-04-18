import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc

from src.models.prompt import PromptVersion
from src.service.cache_service import cache_service
from src.utils.logger import logger
from src.utils.serializers import create_serializer, safe_isoformat


_serialize_prompt_version_list = create_serializer(
    PromptVersion,
    {
        "id": None,
        "version": None,
        "description": None,
        "created_by": None,
        "created_at": safe_isoformat,
        "variables": None,
        "tags": None,
    }
)

_serialize_prompt_version_detail = create_serializer(
    PromptVersion,
    {
        "id": None,
        "prompt_key": None,
        "version": None,
        "content": None,
        "description": None,
        "created_by": None,
        "created_at": safe_isoformat,
        "variables": None,
        "tags": None,
        "fallback": None,
    }
)


class PromptStorage:
    def __init__(self):
        self._version_repo = None

    def _get_repo(self):
        if self._version_repo is None:
            from src.core.database import async_session_factory
            from src.repository import PromptVersionRepository
            self._version_repo = PromptVersionRepository(async_session_factory)
        return self._version_repo

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
        version_repo = self._get_repo()
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        existing = await version_repo.get_one_by_filter(prompt_key=prompt_key, content_hash=content_hash)
        if existing:
            logger.info(f"提示词内容未变化，返回现有版本：{existing.version}")
            return existing.version
        latest = await version_repo.get_latest_version(prompt_key)
        if latest:
            version_parts = latest.version.split(".")
            version_parts[-1] = str(int(version_parts[-1]) + 1)
            new_version = ".".join(version_parts)
        else:
            new_version = "1.0.0"
        prompt_version = await version_repo.create({
            "id": f"{prompt_key}_{new_version}",
            "prompt_key": prompt_key,
            "version": new_version,
            "content": content,
            "content_hash": content_hash,
            "description": description,
            "created_by": created_by,
            "variables": variables,
            "tags": tags,
            "fallback": fallback,
        })
        await cache_service.invalidate_tag(f"prompt:{prompt_key}")
        logger.info(f"提示词新版本已创建：{prompt_key} v{new_version}")
        return new_version

    async def get_prompt_version(self, prompt_key: str, version: Optional[str] = None) -> Optional[PromptVersion]:
        version_repo = self._get_repo()
        if version:
            versions = await version_repo.get_by_filter(skip=0, limit=1, prompt_key=prompt_key, version=version)
            return versions[0] if versions else None
        return await version_repo.get_latest_version(prompt_key)

    async def list_versions(self, prompt_key: str) -> list[dict]:
        version_repo = self._get_repo()
        versions_orm = await version_repo.get_versions_by_key(prompt_key)
        return [_serialize_prompt_version_list(v) for v in versions_orm]

    async def get_version_detail(self, prompt_key: str, version: str) -> Optional[dict]:
        version_repo = self._get_repo()
        versions = await version_repo.get_by_filter(skip=0, limit=1, prompt_key=prompt_key, version=version)
        pv = versions[0] if versions else None
        if not pv:
            return None
        return _serialize_prompt_version_detail(pv)

    async def get_versions_for_compare(self, prompt_key: str, version_1: str, version_2: str) -> tuple:
        version_repo = self._get_repo()
        versions = await version_repo.get_by_filter(prompt_key=prompt_key)
        version_map = {v.version: v for v in versions if v.version in [version_1, version_2]}
        if len(version_map) != 2:
            raise ValueError("版本未找到")
        return version_map[version_1], version_map[version_2]

    def _get_fallback_prompt(self, prompt_key: str) -> str:
        from src.core.prompts_fallback import (
            ASSESSMENT_SYSTEM_PROMPT, CATEGORY_INFERENCE_PROMPT,
            INTENSITY_INFERENCE_PROMPT, METADATA_EXTRACTION_PROMPT,
            QUERY_REWRITE_PROMPT, REPORTING_SYSTEM_PROMPT,
            SCORING_SYSTEM_PROMPT, SYNONYM_EXPANSION_PROMPT,
            TEST_CASE_DRAFT_GENERATION_PROMPT, VALIDATION_SYSTEM_PROMPT)
        fallbacks = {
            "rag_query_rewrite": QUERY_REWRITE_PROMPT, "synonym_expansion": SYNONYM_EXPANSION_PROMPT,
            "metadata_extraction": METADATA_EXTRACTION_PROMPT, "test_case_generation": TEST_CASE_DRAFT_GENERATION_PROMPT,
            "validation": VALIDATION_SYSTEM_PROMPT, "intensity_inference": INTENSITY_INFERENCE_PROMPT,
            "category_inference": CATEGORY_INFERENCE_PROMPT, "child_assessment": ASSESSMENT_SYSTEM_PROMPT,
            "assessment_system": ASSESSMENT_SYSTEM_PROMPT, "scoring": SCORING_SYSTEM_PROMPT,
            "scoring_system": SCORING_SYSTEM_PROMPT, "report_generation": REPORTING_SYSTEM_PROMPT,
            "reporting_system": REPORTING_SYSTEM_PROMPT,
        }
        return fallbacks.get(prompt_key, "You are a helpful assistant.")
