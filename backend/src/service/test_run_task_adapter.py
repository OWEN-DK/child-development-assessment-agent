"""TestRun 任务状态适配器

负责 test_run 类型的 Redis + MySQL 双写：
- Redis 作为主存储（快速查询 + SSE 推送）
- MySQL TestRun.status 作为持久化兜底
- 中间状态定期同步（stage 变化或进度每增加 10%）
- 终态必须同步到 MySQL
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select

from src.core.database import db_session_factory
from src.models.test_case import TestRun, TestRunStatus
from src.schemas.task import TaskState, TaskStatus
from src.service.task_sse_publisher import TaskSsePublisher
from src.utils.di import get_task_state_service
from src.utils.logger import logger

TASK_TYPE = "test_run"


class TestRunTaskStateAdapter:
    """test_run 类型的 Redis + MySQL 双写适配器

    - Redis 作为主存储（快速查询 + SSE 推送）
    - MySQL TestRun.status 作为持久化兜底
    - 中间状态定期同步（stage 变化或进度每增加 10%）
    """

    # 上次同步到 MySQL 的进度值，用于判断是否需要同步
    _last_synced_progress: dict[str, float] = {}
    # 上次同步的 stage 值
    _last_synced_stage: dict[str, str] = {}

    async def create(self, state: TaskState) -> None:
        """创建任务状态（同时写入 Redis 和 MySQL）

        Args:
            state: 统一任务状态模型
        """
        task_state_service = get_task_state_service()

        # 1. 写入 Redis
        await task_state_service.create(state)

        # 2. 初始化 MySQL 同步记录
        self._last_synced_progress[state.task_id] = state.progress
        self._last_synced_stage[state.task_id] = state.stage or ""

        logger.info(f"TestRun task created: {state.task_id}")

    async def update(self, task_id: str, updates: dict) -> bool:
        """原子更新任务状态（Redis 主写 + MySQL 按需同步）

        Args:
            task_id: 任务 ID
            updates: 需要更新的字段

        Returns:
            是否更新成功
        """
        task_state_service = get_task_state_service()

        # 1. 更新 Redis（含兜底逻辑）
        success = await task_state_service.update(
            task_id=task_id, task_type=TASK_TYPE, updates=updates
        )

        if not success:
            return False

        # 2. 判断是否需要同步到 MySQL
        new_status = updates.get("status")
        new_progress = updates.get("progress")
        new_stage = updates.get("stage")

        should_sync = False

        # 终态必须同步
        if new_status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ):
            should_sync = True

        # stage 变化时同步
        if new_stage and new_stage != self._last_synced_stage.get(task_id):
            should_sync = True
            self._last_synced_stage[task_id] = new_stage

        # 进度每增加 10% 同步一次
        if new_progress is not None:
            last_progress = self._last_synced_progress.get(task_id, 0)
            if new_progress - last_progress >= 10:
                should_sync = True
                self._last_synced_progress[task_id] = new_progress

        if should_sync:
            await self._sync_to_mysql(task_id, updates)

        return success

    async def get(self, task_id: str) -> Optional[TaskState]:
        """获取任务状态（Redis 优先，失败时降级到 MySQL）

        Args:
            task_id: 任务 ID

        Returns:
            任务状态，不存在则返回 None
        """
        task_state_service = get_task_state_service()

        # 1. 优先从 Redis 读取
        state = await task_state_service.get(task_id, TASK_TYPE)
        if state:
            return state

        # 2. Redis 失败时，从 MySQL TestRun 表读取
        return await self._load_from_mysql(task_id)

    async def cancel(self, task_id: str) -> bool:
        """取消任务

        Args:
            task_id: 任务 ID

        Returns:
            是否取消成功
        """
        task_state_service = get_task_state_service()

        # 1. 设置取消信号并更新 Redis
        success = await task_state_service.cancel(task_id, TASK_TYPE)

        if success:
            # 2. 同步到 MySQL
            await self._sync_to_mysql(
                task_id, {"status": TaskStatus.CANCELLED.value}
            )

            # 3. 推送 SSE 取消事件
            await TaskSsePublisher.publish_cancelled(
                task_type=TASK_TYPE, task_id=task_id
            )

        return success

    async def delete(self, task_id: str) -> bool:
        """删除任务状态

        Args:
            task_id: 任务 ID

        Returns:
            是否删除成功
        """
        task_state_service = get_task_state_service()

        # 清理同步记录
        self._last_synced_progress.pop(task_id, None)
        self._last_synced_stage.pop(task_id, None)

        return await task_state_service.delete(task_id, TASK_TYPE)

    async def _sync_to_mysql(self, task_id: str, updates: dict) -> None:
        """同步状态到 MySQL TestRun 表

        Args:
            task_id: 任务 ID
            updates: 更新的字段
        """
        try:
            async with db_session_factory() as session:
                stmt = select(TestRun).where(TestRun.id == task_id)
                result = await session.execute(stmt)
                test_run = result.scalar_one_or_none()

                if not test_run:
                    logger.warning(f"TestRun not found for sync: {task_id}")
                    return

                new_status = updates.get("status")
                if new_status:
                    # 统一 TaskStatus 枚举到 TestRunStatus 枚举的映射
                    status_map = {
                        TaskStatus.PENDING: TestRunStatus.PENDING,
                        TaskStatus.RUNNING: TestRunStatus.RUNNING,
                        TaskStatus.COMPLETED: TestRunStatus.COMPLETED,
                        TaskStatus.FAILED: TestRunStatus.FAILED,
                        TaskStatus.CANCELLED: TestRunStatus.CANCELLED,
                    }
                    if isinstance(new_status, TaskStatus):
                        test_run.status = status_map.get(new_status, TestRunStatus.RUNNING)
                    else:
                        # 兼容字符串状态
                        test_run.status = TestRunStatus(new_status)

                if new_status in (
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                    TaskStatus.CANCELLED,
                ):
                    test_run.completed_at = datetime.utcnow()
                    # 清理同步记录
                    self._last_synced_progress.pop(task_id, None)
                    self._last_synced_stage.pop(task_id, None)

                # 同步进度和阶段信息（存入 config_snapshot）
                if "progress" in updates or "stage" in updates:
                    snapshot = test_run.config_snapshot or {}
                    if "progress" in updates:
                        snapshot["last_progress"] = updates["progress"]
                    if "stage" in updates:
                        snapshot["last_stage"] = updates["stage"]
                    test_run.config_snapshot = snapshot

                await session.commit()
                logger.debug(
                    f"TestRun synced to MySQL: {task_id}, status={new_status}"
                )
        except Exception as e:
            logger.error(f"Failed to sync TestRun to MySQL: {task_id}, error={e}")

    async def _load_from_mysql(self, task_id: str) -> Optional[TaskState]:
        """从 MySQL TestRun 表恢复状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态，不存在则返回 None
        """
        try:
            async with db_session_factory() as session:
                stmt = select(TestRun).where(TestRun.id == task_id)
                result = await session.execute(stmt)
                test_run = result.scalar_one_or_none()

                if not test_run:
                    return None

                snapshot = test_run.config_snapshot or {}

                # TestRunStatus 到 TaskStatus 的映射
                status_map = {
                    TestRunStatus.PENDING: TaskStatus.PENDING,
                    TestRunStatus.RUNNING: TaskStatus.RUNNING,
                    TestRunStatus.COMPLETED: TaskStatus.COMPLETED,
                    TestRunStatus.FAILED: TaskStatus.FAILED,
                    TestRunStatus.CANCELLED: TaskStatus.CANCELLED,
                }

                return TaskState(
                    task_id=test_run.id,
                    task_type=TASK_TYPE,
                    status=status_map.get(test_run.status, TaskStatus.RUNNING),
                    progress=snapshot.get("last_progress", 0.0),
                    stage=snapshot.get("last_stage"),
                    message="测试运行中",
                    created_at=test_run.created_at.timestamp(),
                    started_at=(
                        test_run.started_at.timestamp() if test_run.started_at else None
                    ),
                    completed_at=(
                        test_run.completed_at.timestamp()
                        if test_run.completed_at
                        else None
                    ),
                    metadata=snapshot,
                )
        except Exception as e:
            logger.error(f"Failed to load TestRun from MySQL: {task_id}, error={e}")
            return None

    def cleanup_sync_records(self, task_id: str) -> None:
        """清理同步记录（任务终态后调用）

        Args:
            task_id: 任务 ID
        """
        self._last_synced_progress.pop(task_id, None)
        self._last_synced_stage.pop(task_id, None)


# 单例实例
test_run_task_adapter = TestRunTaskStateAdapter()
