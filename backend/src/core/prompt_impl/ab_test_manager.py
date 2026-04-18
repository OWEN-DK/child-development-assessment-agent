import random
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc

from src.models.prompt import PromptABTest, PromptVersion
from src.utils.logger import logger
from src.utils.serializers import create_serializer, safe_isoformat


_serialize_ab_test = create_serializer(
    PromptABTest,
    {
        "id": None,
        "prompt_key": None,
        "name": None,
        "is_active": None,
        "variant_a_version": None,
        "variant_b_version": None,
        "variant_a_ratio": None,
        "started_at": safe_isoformat,
        "ended_at": safe_isoformat,
        "created_at": safe_isoformat,
    }
)


class ABTestManager:
    def __init__(self):
        self._ab_test_repo = None

    def _get_repo(self):
        if self._ab_test_repo is None:
            from src.core.database import async_session_factory
            from src.repository import PromptABTestRepository
            self._ab_test_repo = PromptABTestRepository(async_session_factory)
        return self._ab_test_repo

    def _get_version_repo(self):
        from src.core.database import async_session_factory
        from src.repository import PromptVersionRepository
        return PromptVersionRepository(async_session_factory)

    async def create_ab_test(
        self,
        prompt_key: str,
        name: str,
        variant_a_version: str,
        variant_b_version: str,
        variant_a_ratio: float = 0.5,
    ) -> str:
        version_repo = self._get_version_repo()
        ab_test_repo = self._get_repo()
        version_a = await version_repo.get_one_by_filter(prompt_key=prompt_key, version=variant_a_version)
        if not version_a:
            raise ValueError(f"版本 {variant_a_version} 不存在")
        version_b = await version_repo.get_one_by_filter(prompt_key=prompt_key, version=variant_b_version)
        if not version_b:
            raise ValueError(f"版本 {variant_b_version} 不存在")
        test_id = str(uuid.uuid4())[:8]
        await ab_test_repo.create({
            "id": test_id, "prompt_key": prompt_key, "name": name, "is_active": True,
            "variant_a_version": variant_a_version, "variant_b_version": variant_b_version,
            "variant_a_ratio": variant_a_ratio, "started_at": datetime.now(),
        })
        logger.info(f"A/B 测试已创建：{test_id}")
        return test_id

    async def list_ab_tests(self, prompt_key: Optional[str] = None) -> list[dict]:
        ab_test_repo = self._get_repo()
        if prompt_key:
            tests = await ab_test_repo.get_by_filter(order_by=desc("created_at"), prompt_key=prompt_key)
        else:
            tests = await ab_test_repo.get_all(order_by=desc("created_at"))
        return [_serialize_ab_test(t) for t in tests]

    async def toggle_ab_test(self, test_id: str, is_active: bool) -> bool:
        ab_test_repo = self._get_repo()
        ab_test = await ab_test_repo.get_by_id(test_id)
        if not ab_test:
            raise ValueError(f"A/B 测试 {test_id} 不存在")
        await ab_test_repo.update(test_id, {"is_active": is_active, "ended_at": datetime.now() if not is_active else ab_test.ended_at})
        logger.info(f"A/B 测试 {test_id} 已{'启用' if is_active else '禁用'}")
        return True

    async def get_ab_test(self, test_id: str):
        ab_test_repo = self._get_repo()
        return await ab_test_repo.get_by_id(test_id)

    async def apply_ab_test(self, prompt_version: PromptVersion, ab_test_id: str) -> str:
        ab_test_repo = self._get_repo()
        ab_test = await ab_test_repo.get_by_id(ab_test_id)
        if not ab_test or not ab_test.is_active:
            return prompt_version.content
        if random.random() < ab_test.variant_a_ratio:
            target_version = ab_test.variant_a_version
        else:
            target_version = ab_test.variant_b_version
        version_repo = self._get_version_repo()
        target_pv = await version_repo.get_one_by_filter(prompt_key=prompt_version.prompt_key, version=target_version)
        if target_pv:
            return target_pv.content
        logger.warning(f"A/B 测试版本 {target_version} 未找到，使用当前版本")
        return prompt_version.content
