"""提示词 A/B 测试管理器"""

import random
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, String, desc, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.models.prompt_version import PromptVersion
from src.utils.logger import logger
from src.utils.serializers import create_serializer, safe_isoformat


class PromptABTest(Base):
    __tablename__ = "prompt_ab_tests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    variant_a_version: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_b_version: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_a_ratio: Mapped[float] = mapped_column(Float, default=0.5)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("idx_ab_test_prompt", "prompt_key", "is_active"),)


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
        self._session_factory = None

    def _get_session_factory(self):
        if self._session_factory is None:
            from src.core.database import async_session_factory
            self._session_factory = async_session_factory
        return self._session_factory

    async def create_ab_test(
        self,
        prompt_key: str,
        name: str,
        variant_a_version: str,
        variant_b_version: str,
        variant_a_ratio: float = 0.5,
    ) -> str:
        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            # 验证版本是否存在
            result = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_key == prompt_key,
                    PromptVersion.version_label == variant_a_version,
                )
            )
            if not result.scalar_one_or_none():
                raise ValueError(f"版本 {variant_a_version} 不存在")

            result = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_key == prompt_key,
                    PromptVersion.version_label == variant_b_version,
                )
            )
            if not result.scalar_one_or_none():
                raise ValueError(f"版本 {variant_b_version} 不存在")

            test_id = str(uuid.uuid4())[:8]
            ab_test = PromptABTest(
                id=test_id,
                prompt_key=prompt_key,
                name=name,
                is_active=True,
                variant_a_version=variant_a_version,
                variant_b_version=variant_b_version,
                variant_a_ratio=variant_a_ratio,
                started_at=datetime.now(),
            )
            session.add(ab_test)
            await session.commit()

        logger.info(f"A/B 测试已创建：{test_id}")
        return test_id

    async def list_ab_tests(self, prompt_key: Optional[str] = None) -> list[dict]:
        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            query = select(PromptABTest).order_by(desc(PromptABTest.created_at))
            if prompt_key:
                query = query.where(PromptABTest.prompt_key == prompt_key)
            result = await session.execute(query)
            tests = result.scalars().all()
            return [_serialize_ab_test(t) for t in tests]

    async def toggle_ab_test(self, test_id: str, is_active: bool) -> bool:
        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PromptABTest).where(PromptABTest.id == test_id)
            )
            ab_test = result.scalar_one_or_none()
            if not ab_test:
                raise ValueError(f"A/B 测试 {test_id} 不存在")

            ab_test.is_active = is_active
            if not is_active:
                ab_test.ended_at = datetime.now()
            await session.commit()

        logger.info(f"A/B 测试 {test_id} 已{'启用' if is_active else '禁用'}")
        return True

    async def get_ab_test(self, test_id: str):
        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PromptABTest).where(PromptABTest.id == test_id)
            )
            return result.scalar_one_or_none()

    async def apply_ab_test(self, prompt_version: PromptVersion, ab_test_id: str) -> str:
        session_factory = self._get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PromptABTest).where(PromptABTest.id == ab_test_id)
            )
            ab_test = result.scalar_one_or_none()

            if not ab_test or not ab_test.is_active:
                return prompt_version.content

            if random.random() < ab_test.variant_a_ratio:
                target_version = ab_test.variant_a_version
            else:
                target_version = ab_test.variant_b_version

            result = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_key == prompt_version.prompt_key,
                    PromptVersion.version_label == target_version,
                )
            )
            target_pv = result.scalar_one_or_none()
            if target_pv:
                return target_pv.content

            logger.warning(f"A/B 测试版本 {target_version} 未找到，使用当前版本")
            return prompt_version.content
