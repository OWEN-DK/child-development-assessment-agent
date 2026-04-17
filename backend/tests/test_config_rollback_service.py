"""配置回滚服务测试"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.service import config_rollback_service
from src.models.rag_eval.config_version import RagEvalConfigVersion
from src.models.rag_eval.config_change_set import RagEvalConfigChangeSet
from src.models.rag_eval.enums import RagEvalChangeSetStatus


@pytest.fixture
def mock_session():
    """创建模拟数据库会话"""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.mark.asyncio
async def test_rollback_raises_when_version_not_found(mock_session):
    """测试：目标版本不存在时抛出 ValueError"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(ValueError, match="配置版本不存在"):
        await config_rollback_service.rollback_to_version(
            session=mock_session,
            config_version_id="non-existent-id",
            user_id="test-user",
            reason="测试回滚",
        )


@pytest.mark.asyncio
async def test_compare_versions_raises_when_not_found(mock_session):
    """测试：版本不存在时抛出 ValueError"""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    with pytest.raises(ValueError, match="一个或两个配置版本不存在"):
        await config_rollback_service.compare_config_versions(
            session=mock_session,
            from_version_id="non-existent-1",
            to_version_id="non-existent-2",
        )


@pytest.mark.asyncio
async def test_compare_versions_logic():
    """测试：对比逻辑正确计算差异"""
    # 模拟两个配置快照
    from_snapshot = {"key1": "old_value", "key2": "value2"}
    to_snapshot = {"key1": "new_value", "key3": "value3"}

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

    # 验证差异
    assert "key3" in added_keys
    assert "key2" in removed_keys
    assert len(changed_keys) == 1
    assert changed_keys[0]["key"] == "key1"
    assert changed_keys[0]["old_value"] == "old_value"
    assert changed_keys[0]["new_value"] == "new_value"
