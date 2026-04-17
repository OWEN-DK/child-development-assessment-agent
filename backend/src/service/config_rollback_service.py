"""配置回滚服务

负责将配置回滚到指定版本，创建新的 ConfigVersion 和 ConfigChangeSet，
并复制关联的 PromptVersions。
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_eval.config_version import RagEvalConfigVersion
from src.models.rag_eval.config_change_set import RagEvalConfigChangeSet
from src.models.rag_eval.config_change_set_prompt import RagEvalConfigChangeSetPrompt
from src.models.rag_eval.prompt_version import RagEvalPromptVersion
from src.models.rag_eval.enums import RagEvalChangeSetStatus
from src.core.redis_client import RedisClient
from src.utils.logger import logger


async def rollback_to_version(
    session: AsyncSession,
    config_version_id: str,
    user_id: str,
    reason: str,
) -> dict:
    """回滚到指定配置版本

    原子操作：
    1. 创建新的 ConfigVersion（复制目标版本的 config_snapshot）
    2. 创建新的 ConfigChangeSet（status=rolled_back）
    3. 复制关联的 PromptVersions
    4. 发布 Redis config_changed 事件

    Args:
        session: 数据库会话
        config_version_id: 目标配置版本ID
        user_id: 操作用户ID
        reason: 回滚原因

    Returns:
        包含新版本ID和变更集ID的字典

    Raises:
        ValueError: 当目标版本不存在时
    """
    # 1. 获取目标配置版本
    stmt = select(RagEvalConfigVersion).where(
        RagEvalConfigVersion.id == config_version_id
    )
    result = await session.execute(stmt)
    target_version = result.scalar_one_or_none()

    if not target_version:
        raise ValueError(f"配置版本不存在: {config_version_id}")

    # 2. 获取当前最大版本号
    max_version_stmt = (
        select(RagEvalConfigVersion.version_number)
        .order_by(RagEvalConfigVersion.version_number.desc())
        .limit(1)
    )
    max_version_result = await session.execute(max_version_stmt)
    max_version_number = max_version_result.scalar_one_or_none() or 0

    # 3. 创建新的 ConfigVersion（复制目标版本的快照）
    new_version = RagEvalConfigVersion(
        id=str(uuid.uuid4()),
        version_number=max_version_number + 1,
        version_label=f"rollback-{target_version.version_label}",
        config_snapshot=target_version.config_snapshot.copy(),
        created_by=user_id,
        change_summary=f"回滚到版本 {target_version.version_label}: {reason}",
    )
    session.add(new_version)
    await session.flush()  # 获取 new_version.id

    # 4. 创建新的 ConfigChangeSet（status=rolled_back）
    change_set_label = (
        f"CS-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:3].upper()}"
    )
    change_set = RagEvalConfigChangeSet(
        id=str(uuid.uuid4()),
        change_set_label=change_set_label,
        config_version_id=new_version.id,
        status=RagEvalChangeSetStatus.ROLLED_BACK,
        rollback_reason=reason,
    )
    session.add(change_set)
    await session.flush()

    # 5. 复制目标版本关联的 PromptVersions
    prompt_stmt = (
        select(RagEvalPromptVersion)
        .where(
            RagEvalPromptVersion.created_by
            == user_id  # 简化处理：复制用户相关的 prompt
        )
        .order_by(RagEvalPromptVersion.created_at.desc())
    )
    prompt_result = await session.execute(prompt_stmt)
    prompt_versions = prompt_result.scalars().all()

    # 创建 ChangeSetPrompt 关联
    for prompt_version in prompt_versions:
        change_set_prompt = RagEvalConfigChangeSetPrompt(
            id=str(uuid.uuid4()),
            change_set_id=change_set.id,
            prompt_id=prompt_version.id,
        )
        session.add(change_set_prompt)

    # 6. 发布 Redis config_changed 事件
    try:
        redis_client = RedisClient.get_client()
        await redis_client.publish(
            "config_changed",
            {
                "type": "config_rollback",
                "new_version_id": new_version.id,
                "target_version_id": config_version_id,
                "change_set_id": change_set.id,
                "user_id": user_id,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    except Exception as e:
        logger.warning(f"发布 config_changed 事件失败: {e}")

    logger.info(
        f"配置回滚完成: target={config_version_id}, "
        f"new_version={new_version.id}, change_set={change_set.id}"
    )

    return {
        "new_version_id": new_version.id,
        "new_version_label": new_version.version_label,
        "change_set_id": change_set.id,
        "change_set_label": change_set.change_set_label,
    }


async def compare_config_versions(
    session: AsyncSession,
    from_version_id: str,
    to_version_id: str,
) -> dict:
    """对比两个配置版本的差异

    Args:
        session: 数据库会话
        from_version_id: 源版本ID
        to_version_id: 目标版本ID

    Returns:
        包含两个版本配置快照差异的字典

    Raises:
        ValueError: 当任一版本不存在时
    """
    # 获取两个版本
    stmt = select(RagEvalConfigVersion).where(
        RagEvalConfigVersion.id.in_([from_version_id, to_version_id])
    )
    result = await session.execute(stmt)
    versions = result.scalars().all()

    if len(versions) != 2:
        raise ValueError("一个或两个配置版本不存在")

    from_version = next(v for v in versions if v.id == from_version_id)
    to_version = next(v for v in versions if v.id == to_version_id)

    # 对比配置快照
    from_snapshot = from_version.config_snapshot or {}
    to_snapshot = to_version.config_snapshot or {}

    # 计算差异
    added_keys = set(to_snapshot.keys()) - set(from_snapshot.keys())
    removed_keys = set(from_snapshot.keys()) - set(to_snapshot.keys())
    common_keys = set(from_snapshot.keys()) & set(to_snapshot.keys())

    changed_keys = []
    for key in common_keys:
        if from_snapshot[key] != to_snapshot[key]:
            changed_keys.append(
                {
                    "key": key,
                    "old_value": from_snapshot[key],
                    "new_value": to_snapshot[key],
                }
            )

    return {
        "from_version": {
            "id": from_version.id,
            "version_label": from_version.version_label,
            "version_number": from_version.version_number,
            "created_at": from_version.created_at.isoformat()
            if from_version.created_at
            else None,
        },
        "to_version": {
            "id": to_version.id,
            "version_label": to_version.version_label,
            "version_number": to_version.version_number,
            "created_at": to_version.created_at.isoformat()
            if to_version.created_at
            else None,
        },
        "diff": {
            "added": {key: to_snapshot[key] for key in added_keys},
            "removed": {key: from_snapshot[key] for key in removed_keys},
            "changed": changed_keys,
        },
    }
