"""配置变更集服务 - 原子保存配置 + 提示词版本

提供事务性的配置变更集保存功能，确保配置版本、变更集和提示词版本的原子性。
"""

from datetime import datetime
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_eval.config_version import RagEvalConfigVersion
from src.models.rag_eval.config_change_set import RagEvalConfigChangeSet
from src.models.rag_eval.config_change_set_prompt import RagEvalConfigChangeSetPrompt
from src.models.rag_eval.prompt_version import RagEvalPromptVersion
from src.models.rag_eval.enums import RagEvalChangeSetStatus
from src.utils.logger import logger


class ConfigChangeSetService:
    """配置变更集服务"""

    async def save_config_change_set(
        self,
        config_data: dict[str, Any],
        prompt_data: list[dict[str, Any]],
        user_id: str,
        session: AsyncSession,
        change_summary: str | None = None,
    ) -> RagEvalConfigChangeSet:
        """原子保存配置变更集

        执行顺序（严格保证）:
          1. async with session.begin() 块结束 → 自动 commit    ← MySQL 事务提交，数据持久化
          2. 发布 Redis Pub/Sub 事件              ← 事务已提交，其他实例一定能读到新数据
          3. 返回前端成功响应

        Args:
            config_data: 完整配置快照
            prompt_data: 提示词变更列表，每项包含 key, version_string, content, summary
            user_id: 操作用户ID
            session: 数据库会话
            change_summary: 变更摘要

        Returns:
            RagEvalConfigChangeSet: 创建的变更集对象

        Raises:
            Exception: 数据库操作失败时抛出异常，事务自动回滚
        """
        # 生成版本号
        version_label = await self.generate_version_label(session)

        # 生成变更摘要（如果未提供）
        if not change_summary:
            change_summary = self.generate_config_summary(config_data)

        async with session.begin():
            # 1. 创建配置版本
            config_version = RagEvalConfigVersion(
                version_number=await self._get_max_config_version_number(session) + 1,
                version_label=version_label,
                config_snapshot=config_data,
                created_by=user_id,
                change_summary=change_summary,
            )
            session.add(config_version)
            await session.flush()  # 获取生成的 id

            # 2. 创建变更集
            change_set_label = await self._generate_change_set_label(session)
            change_set = RagEvalConfigChangeSet(
                change_set_label=change_set_label,
                config_version_id=config_version.id,
                status=RagEvalChangeSetStatus.COMMITTED,
            )
            session.add(change_set)
            await session.flush()

            # 3. 创建提示词版本并关联到变更集
            for prompt_item in prompt_data:
                prompt_version = RagEvalPromptVersion(
                    prompt_key=prompt_item["key"],
                    version_label=prompt_item["version_string"],
                    version_number=await self.next_prompt_version_number(
                        session, prompt_item["key"]
                    ),
                    content=prompt_item["content"],
                    created_by=user_id,
                    change_summary=prompt_item.get("summary"),
                )
                session.add(prompt_version)
                await session.flush()

                # 创建关联记录
                change_set_prompt = RagEvalConfigChangeSetPrompt(
                    change_set_id=change_set.id,
                    prompt_version_id=prompt_version.id,
                )
                session.add(change_set_prompt)

            # session.begin() 块结束 → 自动 commit
            logger.info(
                f"配置变更集已保存: change_set_id={change_set.id}, "
                f"config_version_id={config_version.id}, "
                f"prompt_count={len(prompt_data)}"
            )

        return change_set

    async def generate_version_label(self, session: AsyncSession) -> str:
        """生成下一个语义版本号

        Args:
            session: 数据库会话

        Returns:
            str: 版本号，如 "v4"
        """
        max_number = await self._get_max_config_version_number(session)
        return f"v{max_number + 1}"

    def generate_config_summary(
        self,
        new_config: dict[str, Any],
        old_config: dict[str, Any] | None = None,
    ) -> str:
        """生成人类可读的配置变更摘要

        Args:
            new_config: 新配置快照
            old_config: 旧配置快照（可选）

        Returns:
            str: 变更摘要
        """
        if old_config is None:
            # 无旧配置，视为初始化
            keys = list(new_config.keys())[:5]  # 最多显示5个键
            return (
                f"初始化配置: {', '.join(keys)}{'...' if len(new_config) > 5 else ''}"
            )

        changes = []
        for key, new_value in new_config.items():
            if key not in old_config:
                changes.append(f"新增 {key}={new_value}")
            elif old_config[key] != new_value:
                changes.append(f"{key}: {old_config[key]} → {new_value}")

        if not changes:
            return "配置无变更"

        return "; ".join(changes[:3]) + ("..." if len(changes) > 3 else "")

    async def next_prompt_version_number(
        self, session: AsyncSession, prompt_key: str
    ) -> int:
        """获取指定 prompt_key 的下一个版本号

        Args:
            session: 数据库会话
            prompt_key: 提示词键名

        Returns:
            int: 下一个版本号（从1开始）
        """
        stmt = select(func.max(RagEvalPromptVersion.version_number)).where(
            RagEvalPromptVersion.prompt_key == prompt_key
        )
        result = await session.execute(stmt)
        max_number = result.scalar_one_or_none()
        return (max_number or 0) + 1

    async def _get_max_config_version_number(self, session: AsyncSession) -> int:
        """获取最大配置版本号

        Args:
            session: 数据库会话

        Returns:
            int: 最大版本号，无记录时返回 0
        """
        stmt = select(func.max(RagEvalConfigVersion.version_number))
        result = await session.execute(stmt)
        max_number = result.scalar_one_or_none()
        return max_number or 0

    async def _generate_change_set_label(self, session: AsyncSession) -> str:
        """生成变更集标签

        格式: CS-YYYYMMDD-NNN (如 CS-20260416-001)

        Args:
            session: 数据库会话

        Returns:
            str: 变更集标签
        """
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"CS-{today}-"

        # 查询今天的变更集数量
        stmt = select(func.count(RagEvalConfigChangeSet.id)).where(
            RagEvalConfigChangeSet.change_set_label.like(f"{prefix}%")
        )
        result = await session.execute(stmt)
        count = result.scalar_one_or_none() or 0

        return f"{prefix}{count + 1:03d}"


# 全局服务实例
config_change_set_service = ConfigChangeSetService()
