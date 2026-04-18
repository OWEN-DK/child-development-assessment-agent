import re
from typing import Any, Dict, Optional

from src.core.prompt_impl.ab_test_manager import ABTestManager
from src.core.prompt_impl.prompt_storage import PromptStorage
from src.service.cache_service import cache_service
from src.utils.logger import logger


class PromptManager:
    def __init__(self):
        self.cache = cache_service
        self.prompt_storage = PromptStorage()
        self.ab_test_manager = ABTestManager()

    async def get_prompt(
        self,
        prompt_key: str,
        version: Optional[str] = None,
        ab_test_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        cache_key = f"prompt:{prompt_key}:{version or 'latest'}:{ab_test_id or 'default'}"
        try:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug(f"提示词缓存命中：{cache_key}")
                return self._render_template(cached, variables) if variables else cached
            prompt_version = await self.prompt_storage.get_prompt_version(prompt_key, version)
            if not prompt_version:
                logger.warning(f"提示词未找到：{prompt_key}")
                fallback = self.prompt_storage._get_fallback_prompt(prompt_key)
                return self._render_template(fallback, variables) if variables else fallback
            if ab_test_id:
                prompt_content = await self.ab_test_manager.apply_ab_test(prompt_version, ab_test_id)
            else:
                prompt_content = prompt_version.content
            await self.cache.set_with_jitter(cache_key, prompt_content, base_ttl=3600, tags=["prompt", prompt_key])
            return self._render_template(prompt_content, variables) if variables else prompt_content
        except Exception as e:
            logger.error(f"获取提示词失败：{prompt_key}, 错误：{e}, 降级到 fallback")
            fallback = self.prompt_storage._get_fallback_prompt(prompt_key)
            return self._render_template(fallback, variables) if variables else fallback

    def _render_template(self, template: str, variables: Optional[Dict[str, Any]] = None) -> str:
        if not variables:
            return template
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"提示词渲染失败，缺少变量 {e}，返回原始模板")
            return template
        except Exception as e:
            logger.error(f"提示词渲染异常：{e}，返回原始模板")
            return template

    async def create_prompt_version(
        self, prompt_key: str, content: str, description: Optional[str] = None,
        created_by: Optional[str] = None, variables: Optional[list] = None,
        tags: Optional[list] = None, fallback: Optional[str] = None,
    ) -> str:
        return await self.prompt_storage.create_prompt_version(
            prompt_key, content, description, created_by, variables, tags, fallback
        )

    async def list_versions(self, prompt_key: str) -> list[dict]:
        versions = await self.prompt_storage.list_versions(prompt_key)
        if not versions:
            default_content = self.prompt_storage._get_fallback_prompt(prompt_key)
            if default_content != "You are a helpful assistant.":
                await self.create_prompt_version(
                    prompt_key=prompt_key, content=default_content, description="系统默认版本",
                    created_by="system", variables=[], tags=["default"], fallback=default_content,
                )
                versions = await self.prompt_storage.list_versions(prompt_key)
        return versions

    async def get_version_detail(self, prompt_key: str, version: str) -> Optional[dict]:
        return await self.prompt_storage.get_version_detail(prompt_key, version)

    async def compare_versions(self, prompt_key: str, version_1: str, version_2: str) -> dict:
        v1, v2 = await self.prompt_storage.get_versions_for_compare(prompt_key, version_1, version_2)
        return {
            "version_1": {"version": version_1, "content": v1.content, "created_at": v1.created_at.isoformat() if v1.created_at else None, "description": v1.description},
            "version_2": {"version": version_2, "content": v2.content, "created_at": v2.created_at.isoformat() if v2.created_at else None, "description": v2.description},
            "diff": {"added_chars": len(v2.content) - len(v1.content), "version_1_length": len(v1.content), "version_2_length": len(v2.content)},
        }

    async def create_ab_test(self, prompt_key: str, name: str, variant_a_version: str, variant_b_version: str, variant_a_ratio: float = 0.5) -> str:
        return await self.ab_test_manager.create_ab_test(prompt_key, name, variant_a_version, variant_b_version, variant_a_ratio)

    async def list_ab_tests(self, prompt_key: Optional[str] = None) -> list[dict]:
        return await self.ab_test_manager.list_ab_tests(prompt_key)

    async def toggle_ab_test(self, test_id: str, is_active: bool) -> bool:
        return await self.ab_test_manager.toggle_ab_test(test_id, is_active)


prompt_manager = PromptManager()
