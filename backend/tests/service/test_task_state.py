"""TaskState 模型单元测试"""

import json
import time
from datetime import datetime, timezone

import pytest

from src.schemas.task import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    TaskState,
    TaskStatus,
    TaskSseEvent,
)


class TestTaskStatus:
    """TaskStatus 枚举测试"""

    def test_terminal_states(self):
        """终态集合包含 completed/failed/cancelled"""
        assert TaskStatus.COMPLETED in TERMINAL_STATES
        assert TaskStatus.FAILED in TERMINAL_STATES
        assert TaskStatus.CANCELLED in TERMINAL_STATES
        assert TaskStatus.PENDING not in TERMINAL_STATES
        assert TaskStatus.RUNNING not in TERMINAL_STATES

    def test_active_states(self):
        """活跃状态集合包含 pending/running/retrying"""
        assert TaskStatus.PENDING in ACTIVE_STATES
        assert TaskStatus.RUNNING in ACTIVE_STATES
        assert TaskStatus.RETRYING in ACTIVE_STATES
        assert TaskStatus.COMPLETED not in ACTIVE_STATES
        assert TaskStatus.FAILED not in ACTIVE_STATES


class TestTaskState:
    """TaskState 模型测试"""

    def test_create_initial_state(self):
        """创建初始任务状态（pending）"""
        state = TaskState.create(
            task_id="test-123",
            task_type="upload",
            metadata={"filename": "test.pdf"},
        )

        assert state.task_id == "test-123"
        assert state.task_type == "upload"
        assert state.status == TaskStatus.PENDING
        assert state.progress == 0.0
        assert state.metadata == {"filename": "test.pdf"}
        assert state.created_at > 0
        assert state.started_at is None
        assert state.completed_at is None

    def test_is_terminal_property(self):
        """终态属性判断"""
        for status in TERMINAL_STATES:
            state = TaskState(
                task_id="test",
                task_type="upload",
                status=status,
                created_at=time.time(),
            )
            assert state.is_terminal is True
            assert state.is_active is False

    def test_is_active_property(self):
        """活跃状态属性判断"""
        for status in ACTIVE_STATES:
            state = TaskState(
                task_id="test",
                task_type="upload",
                status=status,
                created_at=time.time(),
            )
            assert state.is_active is True
            assert state.is_terminal is False

    def test_to_redis_hash(self):
        """转换为 Redis Hash 格式"""
        state = TaskState(
            task_id="test-123",
            task_type="upload",
            status=TaskStatus.RUNNING,
            progress=50.0,
            stage="indexing",
            message="索引中",
            created_at=1234567890.0,
            started_at=1234567891.0,
            metadata={"key": "value"},
        )

        hash_data = state.to_redis_hash()

        assert hash_data["task_id"] == "test-123"
        assert hash_data["task_type"] == "upload"
        assert hash_data["status"] == "running"
        assert hash_data["progress"] == "50.0"
        assert hash_data["stage"] == "indexing"
        assert hash_data["message"] == "索引中"
        assert json.loads(hash_data["metadata"]) == {"key": "value"}

    def test_from_redis_hash(self):
        """从 Redis Hash 恢复"""
        hash_data = {
            "task_id": "test-123",
            "task_type": "upload",
            "status": "completed",
            "progress": "100.0",
            "stage": "",
            "message": "完成",
            "error": "",
            "result": json.dumps({"file_count": 10}),
            "created_at": "1234567890.0",
            "started_at": "1234567891.0",
            "completed_at": "1234567900.0",
            "metadata": json.dumps({"filename": "test.pdf"}),
        }

        state = TaskState.from_redis_hash(hash_data, task_type="upload")

        assert state.task_id == "test-123"
        assert state.task_type == "upload"
        assert state.status == TaskStatus.COMPLETED
        assert state.progress == 100.0
        assert state.message == "完成"
        assert state.result == {"file_count": 10}
        assert state.metadata == {"filename": "test.pdf"}

    def test_from_redis_hash_empty_data(self):
        """空数据返回 None"""
        assert TaskState.from_redis_hash({}, "upload") is None
        assert TaskState.from_redis_hash(None, "upload") is None


class TestTaskSseEvent:
    """TaskSseEvent 模型测试"""

    def test_create_progress_event(self):
        """创建进度事件"""
        event = TaskSseEvent.create_progress(
            task_id="test-123",
            task_type="upload",
            status=TaskStatus.RUNNING,
            progress=50.0,
            stage="indexing",
            message="索引中",
        )

        assert event.type == "progress"
        assert event.task_id == "test-123"
        assert event.task_type == "upload"
        assert event.status == TaskStatus.RUNNING
        assert event.progress == 50.0
        assert event.stage == "indexing"
        assert event.message == "索引中"
        assert event.timestamp is not None

    def test_create_complete_event(self):
        """创建完成事件"""
        event = TaskSseEvent.create_complete(
            task_id="test-123",
            task_type="upload",
            result={"file_count": 10},
            message="上传成功",
        )

        assert event.type == "complete"
        assert event.status == TaskStatus.COMPLETED
        assert event.result == {"file_count": 10}
        assert event.message == "上传成功"

    def test_create_error_event(self):
        """创建错误事件"""
        event = TaskSseEvent.create_error(
            task_id="test-123",
            task_type="upload",
            error="文件格式不支持",
            message="上传失败",
        )

        assert event.type == "error"
        assert event.status == TaskStatus.FAILED
        assert event.error == "文件格式不支持"
        assert event.message == "上传失败"

    def test_create_cancelled_event(self):
        """创建取消事件"""
        event = TaskSseEvent.create_cancelled(
            task_id="test-123",
            task_type="upload",
        )

        assert event.type == "complete"  # 取消也使用 complete 类型
        assert event.status == TaskStatus.CANCELLED
        assert event.message == "任务已取消"
