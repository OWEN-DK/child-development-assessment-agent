from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.repository.base import BaseRepository
from src.models.prompt import PromptVersion, PromptABTest


class PromptVersionRepository(BaseRepository[PromptVersion]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(PromptVersion, db_session_factory)

    async def get_latest_version(self, prompt_key: str) -> Optional[PromptVersion]:
        """获取指定提示词的最新版本"""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_key == prompt_key)
                .order_by(desc(PromptVersion.created_at))
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_versions_by_key(
        self, prompt_key: str, skip: int = 0, limit: int = 20
    ) -> List[PromptVersion]:
        """获取指定提示词的所有版本"""
        return await self.get_by_filter(
            skip=skip,
            limit=limit,
            order_by=desc(PromptVersion.created_at),
            prompt_key=prompt_key,
        )


class PromptABTestRepository(BaseRepository[PromptABTest]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(PromptABTest, db_session_factory)

    async def get_active_test(self, prompt_key: str) -> Optional[PromptABTest]:
        """获取指定提示词的活跃A/B测试"""
        return await self.get_one_by_filter(prompt_key=prompt_key, is_active=True)

    async def get_all_active_tests(self) -> List[PromptABTest]:
        """获取所有活跃的A/B测试"""
        return await self.get_by_filter(is_active=True)
