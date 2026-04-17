"""导出服务测试"""

import pytest
import pytest_asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.service import export_service


@pytest.fixture
def mock_redis_client():
    """创建模拟 Redis 客户端"""
    client = AsyncMock()
    client.get = AsyncMock()
    client.set = AsyncMock()
    client.publish = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_create_export_task_returns_task_id(mock_redis_client):
    """测试：创建导出任务返回任务 ID"""
    with patch("src.service.export_service.RedisClient") as mock_redis_class:
        mock_redis_class.get_client.return_value = mock_redis_client

        with patch("src.service.export_service._export_queue") as mock_queue:
            mock_queue.put = AsyncMock()

            task_id = await export_service.create_export_task(
                report_id="test-report-id",
                user_id="test-user",
            )

            assert task_id is not None
            assert len(task_id) == 36  # UUID 格式


@pytest.mark.asyncio
async def test_get_export_status_returns_none_when_not_found(mock_redis_client):
    """测试：任务不存在时返回 None"""
    mock_redis_client.get.return_value = None

    with patch("src.service.export_service.RedisClient") as mock_redis_class:
        mock_redis_class.get_client.return_value = mock_redis_client

        result = await export_service.get_export_status("non-existent-task")

        assert result is None


@pytest.mark.asyncio
async def test_get_export_status_returns_data_when_found(mock_redis_client):
    """测试：任务存在时返回状态数据"""
    task_data = {
        "task_id": "test-task-id",
        "status": "completed",
        "file_path": "/path/to/file.pdf",
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mock_redis_client.get.return_value = json.dumps(task_data)

    with patch("src.service.export_service.RedisClient") as mock_redis_class:
        mock_redis_class.get_client.return_value = mock_redis_client

        result = await export_service.get_export_status("test-task-id")

        assert result is not None
        assert result["status"] == "completed"
        assert result["file_path"] == "/path/to/file.pdf"


@pytest.mark.asyncio
async def test_get_export_file_path_returns_none_when_not_completed(mock_redis_client):
    """测试：任务未完成时返回 None"""
    task_data = {
        "task_id": "test-task-id",
        "status": "pending",
        "file_path": None,
        "error": None,
    }
    mock_redis_client.get.return_value = json.dumps(task_data)

    with patch("src.service.export_service.RedisClient") as mock_redis_class:
        mock_redis_class.get_client.return_value = mock_redis_client

        result = await export_service.get_export_file_path("test-task-id")

        assert result is None


@pytest.mark.asyncio
async def test_get_export_file_path_returns_path_when_completed(mock_redis_client):
    """测试：任务完成时返回文件路径"""
    task_data = {
        "task_id": "test-task-id",
        "status": "completed",
        "file_path": "/path/to/file.pdf",
        "error": None,
    }
    mock_redis_client.get.return_value = json.dumps(task_data)

    with patch("src.service.export_service.RedisClient") as mock_redis_class:
        mock_redis_class.get_client.return_value = mock_redis_client

        result = await export_service.get_export_file_path("test-task-id")

        assert result == "/path/to/file.pdf"
