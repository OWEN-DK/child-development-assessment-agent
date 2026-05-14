"""重建服务

触发和执行知识库索引重建。
"""
import asyncio
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.knowledge_base.chunking.engine import ChunkingEngine
from src.core.knowledge_base.vector_store.factory import VectorStoreAdapterFactory
from src.repository.knowledge.chunk_repo import ChunkRepository
from src.repository.knowledge.document_repo import DocumentRepository
from src.repository.knowledge.kb_repo import KnowledgeBaseRepository
from src.repository.knowledge.rebuild_repo import RebuildTaskRepository
from src.schemas.knowledge.rebuild import RebuildStatusResponse, RebuildTaskSummary
from src.service.knowledge.sse_publisher import SSEPublisher
from src.utils.logger import logger


class RebuildService:
    """重建服务"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory
        self.kb_repo = KnowledgeBaseRepository(db_session_factory)
        self.doc_repo = DocumentRepository(db_session_factory)
        self.chunk_repo = ChunkRepository(db_session_factory)
        self.rebuild_repo = RebuildTaskRepository(db_session_factory)
        self.chunking_engine = ChunkingEngine()
        self.sse_publisher = SSEPublisher()

    async def trigger_rebuild(
        self, kb_id: str, tenant_id: str, trigger: str
    ) -> str:
        """触发重建任务

        Args:
            kb_id: 知识库 ID
            tenant_id: 租户 ID
            trigger: 触发原因

        Returns:
            任务 ID
        """
        # 检查是否有正在运行的任务
        running = await self.rebuild_repo.get_latest_running(kb_id, tenant_id)
        if running:
            raise ValueError("已有重建任务正在运行")

        # 创建任务
        task_id = str(uuid.uuid4()).replace("-", "")[:24]
        task_data = {
            "id": task_id,
            "kb_id": kb_id,
            "tenant_id": tenant_id,
            "trigger": trigger,
            "status": "running",
        }
        await self.rebuild_repo.create(task_data)

        # 更新知识库状态
        await self.kb_repo.update_status(kb_id, tenant_id, "rebuilding")

        # 异步执行重建
        asyncio.create_task(self._execute_rebuild(task_id, kb_id, tenant_id))

        return task_id

    async def _execute_rebuild(self, task_id: str, kb_id: str, tenant_id: str) -> None:
        """执行重建流水线"""
        try:
            await self._publish_progress(task_id, kb_id, 0, "开始重建")

            # 1. 获取知识库配置
            kb = await self.kb_repo.get_by_id(kb_id, tenant_id)
            if not kb:
                raise ValueError(f"知识库不存在: {kb_id}")

            chunk_config = kb.chunk_strategy or {"type": "fixed_size", "chunk_size": 512, "overlap": 50}

            # 2. 获取所有已解析的文档
            docs = await self.doc_repo.list_by_kb(kb_id, tenant_id, parse_status="parsed")
            if not docs:
                await self._publish_progress(task_id, kb_id, 100, "无已解析文档")
                await self.rebuild_repo.mark_completed(task_id)
                await self.kb_repo.update_status(kb_id, tenant_id, "ready")
                return

            await self._publish_progress(task_id, kb_id, 10, f"共 {len(docs)} 个文档待处理")

            # 3. 删除旧分块
            old_count = await self.chunk_repo.delete_by_kb(kb_id, tenant_id)
            logger.info(f"删除旧分块: {old_count} 个")

            # 4. 重新分块
            total_chunks = 0
            for i, doc in enumerate(docs):
                if not doc.text_content:
                    continue

                chunks = self.chunking_engine.chunk(doc.text_content, chunk_config)
                chunk_records = []
                for j, chunk in enumerate(chunks):
                    chunk_records.append({
                        "id": str(uuid.uuid4()).replace("-", "")[:24],
                        "kb_id": kb_id,
                        "doc_id": doc.id,
                        "tenant_id": tenant_id,
                        "chunk_index": j,
                        "content": chunk.content,
                        "token_count": chunk.token_count,
                        "metadata": chunk.metadata,
                    })

                if chunk_records:
                    await self.chunk_repo.batch_insert(chunk_records)
                    total_chunks += len(chunk_records)

                # 更新文档分块数
                await self.doc_repo.update(doc.id, {"chunk_count": len(chunks)}, tenant_id)

                progress = 10 + int(80 * (i + 1) / len(docs))
                await self._publish_progress(task_id, kb_id, progress, f"已处理 {i + 1}/{len(docs)} 文档")

            # 5. 更新知识库统计
            await self.kb_repo.update(kb_id, {
                "chunk_count": total_chunks,
                "status": "ready",
            }, tenant_id)

            # 6. 完成
            await self.rebuild_repo.mark_completed(task_id)
            await self._publish_progress(task_id, kb_id, 100, f"重建完成，共 {total_chunks} 个分块")

            logger.info(f"重建完成: {task_id}, {total_chunks} 个分块")

        except Exception as e:
            logger.error(f"重建失败: {task_id}, {e}")
            await self.rebuild_repo.mark_failed(task_id, str(e))
            await self.kb_repo.update_status(kb_id, tenant_id, "error")
            await self.sse_publisher.publish(kb_id, {
                "event": "error",
                "task_id": task_id,
                "kb_id": kb_id,
                "error_message": str(e),
            })

    async def _publish_progress(
        self, task_id: str, kb_id: str, progress_pct: int, message: str
    ) -> None:
        """发布进度"""
        await self.rebuild_repo.update_progress(task_id, progress_pct, message)
        await self.sse_publisher.publish(kb_id, {
            "event": "progress",
            "task_id": task_id,
            "kb_id": kb_id,
            "progress_pct": progress_pct,
            "progress_message": message,
            "status": "running",
        })

    async def get_status(self, kb_id: str, tenant_id: str) -> RebuildStatusResponse:
        """获取重建状态"""
        running = await self.rebuild_repo.get_latest_running(kb_id, tenant_id)
        recent = await self.rebuild_repo.get_recent(kb_id, tenant_id, limit=5)

        return RebuildStatusResponse(
            kb_id=kb_id,
            current_task=self._to_summary(running) if running else None,
            recent_tasks=[self._to_summary(t) for t in recent],
        )

    def _to_summary(self, task) -> RebuildTaskSummary:
        return RebuildTaskSummary(
            id=task.id,
            kb_id=task.kb_id,
            trigger=task.trigger,
            status=task.status,
            progress_pct=task.progress_pct,
            progress_message=task.progress_message,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error_message=task.error_message,
        )
