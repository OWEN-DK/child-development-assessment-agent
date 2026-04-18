import hashlib
import random
import re
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import desc

from src.models.prompt import PromptVersion, PromptABTest
from src.service.cache_service import cache_service
from src.utils.logger import logger


class PromptManager:
    """提示词管理器（MySQL 存储 + Redis 缓存）"""

    def __init__(self):
        self.cache = cache_service
        self._version_repo = None
        self._ab_test_repo = None

    def _get_repos(self):
        """懒加载Repository实例"""
        if self._version_repo is None:
            from src.core.database import async_session_factory
            from src.repository import PromptVersionRepository, PromptABTestRepository

            self._version_repo = PromptVersionRepository(async_session_factory)
            self._ab_test_repo = PromptABTestRepository(async_session_factory)
        return self._version_repo, self._ab_test_repo

    async def get_prompt(
        self,
        prompt_key: str,
        version: Optional[str] = None,
        ab_test_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """获取提示词并渲染占位符"""
        cache_key = (
            f"prompt:{prompt_key}:{version or 'latest'}:{ab_test_id or 'default'}"
        )

        try:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug(f"提示词缓存命中：{cache_key}")
                return self._render_template(cached, variables) if variables else cached

            version_repo, ab_test_repo = self._get_repos()

            if version:
                versions = await version_repo.get_by_filter(
                    skip=0, limit=1, prompt_key=prompt_key, version=version
                )
                prompt_version = versions[0] if versions else None
            else:
                prompt_version = await version_repo.get_latest_version(prompt_key)

            if not prompt_version:
                logger.warning(f"提示词未找到：{prompt_key}")
                fallback = self._get_fallback_prompt(prompt_key)
                return (
                    self._render_template(fallback, variables)
                    if variables
                    else fallback
                )

            if ab_test_id:
                prompt_content = await self._apply_ab_test(prompt_version, ab_test_id)
            else:
                prompt_content = prompt_version.content

            await self.cache.set_with_jitter(
                cache_key,
                prompt_content,
                base_ttl=3600,
                tags=["prompt", prompt_key],
            )

            return (
                self._render_template(prompt_content, variables)
                if variables
                else prompt_content
            )
        except Exception as e:
            # 数据库或缓存不可用时降级到 fallback
            logger.error(f"获取提示词失败：{prompt_key}, 错误：{e}, 降级到 fallback")
            fallback = self._get_fallback_prompt(prompt_key)
            return self._render_template(fallback, variables) if variables else fallback

    def _render_template(
        self, template: str, variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """渲染提示词模板中的占位符

        Args:
            template: 提示词模板字符串
            variables: 变量字典，如 {"child_age": 3, "issues": "..."}

        Returns:
            渲染后的提示词字符串
        """
        if not variables:
            return template

        try:
            # 使用 str.format() 渲染占位符
            # 对于 JSON 模板中的 {{}}，需要先转义
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"提示词渲染失败，缺少变量 {e}，返回原始模板")
            return template
        except Exception as e:
            logger.error(f"提示词渲染异常：{e}，返回原始模板")
            return template

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
        """创建新版本"""
        # 校验占位符一致性
        if variables:
            from src.core.prompt.validator import PromptValidator

            result = PromptValidator.validate_variables(prompt_key, content, variables)
            if not result.is_valid:
                logger.warning(
                    f"提示词 '{prompt_key}' 占位符不匹配: "
                    f"missing={result.missing}, extra={result.extra}"
                )
                # 注意：这里不抛出异常，仅警告，允许保存（兼容旧数据）

        version_repo, _ = self._get_repos()
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        existing = await version_repo.get_one_by_filter(
            prompt_key=prompt_key, content_hash=content_hash
        )

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

        prompt_version = await version_repo.create(
            {
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
            }
        )

        await self.cache.invalidate_tag(f"prompt:{prompt_key}")

        logger.info(f"提示词新版本已创建：{prompt_key} v{new_version}")
        return new_version

    async def list_versions(self, prompt_key: str) -> list[dict]:
        """列出所有版本，如果没有版本则自动创建默认版本"""
        version_repo, _ = self._get_repos()
        versions_orm = await version_repo.get_versions_by_key(prompt_key)

        versions = [
            {
                "id": v.id,
                "version": v.version,
                "description": v.description,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "variables": v.variables,
                "tags": v.tags,
            }
            for v in versions_orm
        ]

        if not versions:
            default_content = self._get_fallback_prompt(prompt_key)
            if default_content != "You are a helpful assistant.":
                await self.create_prompt_version(
                    prompt_key=prompt_key,
                    content=default_content,
                    description="系统默认版本",
                    created_by="system",
                    variables=[],
                    tags=["default"],
                    fallback=default_content,
                )
                versions_orm = await version_repo.get_versions_by_key(prompt_key)
                versions = [
                    {
                        "id": v.id,
                        "version": v.version,
                        "description": v.description,
                        "created_by": v.created_by,
                        "created_at": v.created_at.isoformat()
                        if v.created_at
                        else None,
                        "variables": v.variables,
                        "tags": v.tags,
                    }
                    for v in versions_orm
                ]

        return versions

    async def get_version_detail(self, prompt_key: str, version: str) -> Optional[dict]:
        """获取版本详情"""
        version_repo, _ = self._get_repos()
        versions = await version_repo.get_by_filter(
            skip=0, limit=1, prompt_key=prompt_key, version=version
        )
        pv = versions[0] if versions else None

        if not pv:
            return None

        return {
            "id": pv.id,
            "prompt_key": pv.prompt_key,
            "version": pv.version,
            "content": pv.content,
            "description": pv.description,
            "created_by": pv.created_by,
            "created_at": pv.created_at.isoformat() if pv.created_at else None,
            "variables": pv.variables,
            "tags": pv.tags,
            "fallback": pv.fallback,
        }

    async def compare_versions(
        self,
        prompt_key: str,
        version_1: str,
        version_2: str,
    ) -> dict:
        """对比两个版本"""
        version_repo, _ = self._get_repos()
        versions = await version_repo.get_by_filter(
            prompt_key=prompt_key,
        )
        version_map = {
            v.version: v for v in versions if v.version in [version_1, version_2]
        }

        if len(version_map) != 2:
            raise ValueError("版本未找到")

        v1 = version_map[version_1]
        v2 = version_map[version_2]

        return {
            "version_1": {
                "version": version_1,
                "content": v1.content,
                "created_at": v1.created_at.isoformat() if v1.created_at else None,
                "description": v1.description,
            },
            "version_2": {
                "version": version_2,
                "content": v2.content,
                "created_at": v2.created_at.isoformat() if v2.created_at else None,
                "description": v2.description,
            },
            "diff": {
                "added_chars": len(v2.content) - len(v1.content),
                "version_1_length": len(v1.content),
                "version_2_length": len(v2.content),
            },
        }

    async def create_ab_test(
        self,
        prompt_key: str,
        name: str,
        variant_a_version: str,
        variant_b_version: str,
        variant_a_ratio: float = 0.5,
    ) -> str:
        """创建 A/B 测试"""
        import uuid

        version_repo, ab_test_repo = self._get_repos()

        version_a = await version_repo.get_one_by_filter(
            prompt_key=prompt_key, version=variant_a_version
        )
        if not version_a:
            raise ValueError(f"版本 {variant_a_version} 不存在")

        version_b = await version_repo.get_one_by_filter(
            prompt_key=prompt_key, version=variant_b_version
        )
        if not version_b:
            raise ValueError(f"版本 {variant_b_version} 不存在")

        test_id = str(uuid.uuid4())[:8]

        await ab_test_repo.create(
            {
                "id": test_id,
                "prompt_key": prompt_key,
                "name": name,
                "is_active": True,
                "variant_a_version": variant_a_version,
                "variant_b_version": variant_b_version,
                "variant_a_ratio": variant_a_ratio,
                "started_at": datetime.now(),
            }
        )

        logger.info(f"A/B 测试已创建：{test_id}")
        return test_id

    async def list_ab_tests(self, prompt_key: Optional[str] = None) -> list[dict]:
        """列出 A/B 测试"""
        _, ab_test_repo = self._get_repos()

        if prompt_key:
            tests = await ab_test_repo.get_by_filter(
                order_by=desc("created_at"), prompt_key=prompt_key
            )
        else:
            tests = await ab_test_repo.get_all(order_by=desc("created_at"))

        return [
            {
                "id": t.id,
                "prompt_key": t.prompt_key,
                "name": t.name,
                "is_active": t.is_active,
                "variant_a_version": t.variant_a_version,
                "variant_b_version": t.variant_b_version,
                "variant_a_ratio": t.variant_a_ratio,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "ended_at": t.ended_at.isoformat() if t.ended_at else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tests
        ]

    async def toggle_ab_test(self, test_id: str, is_active: bool) -> bool:
        """启用/禁用 A/B 测试"""
        _, ab_test_repo = self._get_repos()
        ab_test = await ab_test_repo.get_by_id(test_id)

        if not ab_test:
            raise ValueError(f"A/B 测试 {test_id} 不存在")

        await ab_test_repo.update(
            test_id,
            {
                "is_active": is_active,
                "ended_at": datetime.now() if not is_active else ab_test.ended_at,
            },
        )

        logger.info(f"A/B 测试 {test_id} 已{'启用' if is_active else '禁用'}")
        return True

    def _get_fallback_prompt(self, prompt_key: str) -> str:
        """获取兜底提示词（从 prompts_fallback.py 读取）"""
        from src.core.prompts_fallback import (
            QUERY_REWRITE_PROMPT,
            SYNONYM_EXPANSION_PROMPT,
            METADATA_EXTRACTION_PROMPT,
            TEST_CASE_DRAFT_GENERATION_PROMPT,
            VALIDATION_SYSTEM_PROMPT,
            INTENSITY_INFERENCE_PROMPT,
            CATEGORY_INFERENCE_PROMPT,
            ASSESSMENT_SYSTEM_PROMPT,
            SCORING_SYSTEM_PROMPT,
            REPORTING_SYSTEM_PROMPT,
        )

        fallbacks = {
            "rag_query_rewrite": QUERY_REWRITE_PROMPT,
            "synonym_expansion": SYNONYM_EXPANSION_PROMPT,
            "metadata_extraction": METADATA_EXTRACTION_PROMPT,
            "test_case_generation": TEST_CASE_DRAFT_GENERATION_PROMPT,
            "validation": VALIDATION_SYSTEM_PROMPT,
            "intensity_inference": INTENSITY_INFERENCE_PROMPT,
            "category_inference": CATEGORY_INFERENCE_PROMPT,
            "child_assessment": ASSESSMENT_SYSTEM_PROMPT,
            "assessment_system": ASSESSMENT_SYSTEM_PROMPT,
            "scoring": SCORING_SYSTEM_PROMPT,
            "scoring_system": SCORING_SYSTEM_PROMPT,
            "report_generation": REPORTING_SYSTEM_PROMPT,
            "reporting_system": REPORTING_SYSTEM_PROMPT,
        }
        return fallbacks.get(prompt_key, "You are a helpful assistant.")

    async def _apply_ab_test(
        self,
        prompt_version: PromptVersion,
        ab_test_id: str,
    ) -> str:
        """应用 A/B 测试分流"""
        _, ab_test_repo = self._get_repos()
        ab_test = await ab_test_repo.get_by_id(ab_test_id)

        if not ab_test or not ab_test.is_active:
            return prompt_version.content

        if random.random() < ab_test.variant_a_ratio:
            target_version = ab_test.variant_a_version
        else:
            target_version = ab_test.variant_b_version

        version_repo, _ = self._get_repos()
        target_pv = await version_repo.get_one_by_filter(
            prompt_key=prompt_version.prompt_key, version=target_version
        )

        if target_pv:
            return target_pv.content

        logger.warning(f"A/B 测试版本 {target_version} 未找到，使用当前版本")
        return prompt_version.content


prompt_manager = PromptManager()
