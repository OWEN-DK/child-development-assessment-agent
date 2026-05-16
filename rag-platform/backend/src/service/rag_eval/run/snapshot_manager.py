"""知识库快照管理器

创建知识库在评估时刻的浅拷贝快照，冻结关联文档防止被删除/重建覆盖。
支持 3 种向量后端（Chroma/ES/Milvus）的快照创建和有效性检查。
"""
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.knowledge_base.vector_store.factory import VectorStoreAdapterFactory
from src.models.knowledge_base import KnowledgeBase
from src.models.rag_eval.snapshot import KnowledgeSnapshot
from src.repository.knowledge.document_repo import DocumentRepository
from src.repository.knowledge.kb_repo import KnowledgeBaseRepository
from src.repository.rag_eval.snapshot_repo import SnapshotRepository
from src.schemas.rag_eval.snapshot import SnapshotRead
from src.utils.logger import logger

# 快照默认有效期（30 天）
SNAPSHOT_TTL_DAYS = 30


class SnapshotManager:
    """知识库快照管理器

    浅拷贝策略：仅记录元数据引用，不复制向量数据。
    冻结保护：创建快照时标记关联文档为已冻结，防止评估期间数据变更。
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        vector_store_factory: VectorStoreAdapterFactory,
        snapshot_repo: SnapshotRepository,
        kb_repo: KnowledgeBaseRepository,
        doc_repo: DocumentRepository,
    ):
        self._session_factory = session_factory
        self._vector_store_factory = vector_store_factory
        self._snapshot_repo = snapshot_repo
        self._kb_repo = kb_repo
        self._doc_repo = doc_repo

    async def create_snapshot(
        self,
        kb_id: str,
        tenant_id: str,
        name: str = "",
        description: str = "",
    ) -> SnapshotRead:
        """为知识库创建评估快照

        步骤：
        1. 获取知识库元数据（向量后端、文档列表、分块策略、Embedding 配置）
        2. 记录向量存储路径（浅拷贝——不复制向量数据）
        3. 冻结关联文档（防止被删除/重建覆盖）
        4. 创建快照 MySQL 记录

        Returns:
            SnapshotRead
        """
        import uuid

        # 1. 获取知识库信息
        kb = await self._kb_repo.get_by_id(kb_id, tenant_id)
        if not kb:
            raise ValueError(f"知识库不存在: {kb_id}")

        # 2. 获取向量后端信息
        adapter = self._vector_store_factory.get_adapter(kb.vector_backend)
        if adapter is None:
            raise ValueError(f"向量后端不可用: {kb.vector_backend}")

        # 3. 获取文档列表和分块统计
        docs = await self._doc_repo.list_by_kb(
            kb_id=kb_id,
            tenant_id=tenant_id,
            skip=0,
            limit=10000,  # 快照场景：一次性获取全部文档
        )
        doc_ids = [d.id for d in docs]

        # 4. 浅拷贝：仅记录元数据引用，不复制向量数据文件
        vector_store_path = f"storage/{tenant_id}/vectors/{kb_id}"
        snapshot_id = self._generate_snapshot_id()
        expires_at = datetime.utcnow() + timedelta(days=SNAPSHOT_TTL_DAYS)

        # 5. 冻结文档（阻止删除和重新解析）
        if doc_ids:
            await self._doc_repo.mark_frozen(doc_ids, tenant_id)

        # 6. 创建快照记录
        snapshot_data = {
            "id": snapshot_id,
            "kb_id": kb_id,
            "tenant_id": tenant_id,
            "name": name or f"snapshot_{kb_id}_{datetime.utcnow().isoformat()}",
            "vector_store_path": vector_store_path,
            "vector_backend_type": kb.vector_backend,
            "document_count": len(docs),
            "chunk_count": kb.chunk_count,
            "doc_ids_json": doc_ids,
            "chunk_strategy_json": kb.chunk_strategy or {},
            "embedding_config_json": kb.embedding_config or {},
            "config_snapshot": {
                "kb_id": kb.id,
                "chunk_strategy": kb.chunk_strategy,
                "embedding_config": kb.embedding_config,
                "vector_backend": kb.vector_backend,
            },
            "status": "active",
            "expires_at": expires_at,
        }
        snapshot = await self._snapshot_repo.create(snapshot_data)
        logger.info(f"快照创建完成: {snapshot_id}, 冻结 {len(doc_ids)} 个文档")

        return SnapshotRead.model_validate(snapshot)

    async def check_validity(self, snapshot_id: str) -> bool:
        """检查快照是否有效

        判断条件：当前向量后端类型与快照记录一致。
        不一致 → 返回 False 并标记快照为 invalid。
        """
        snapshot = await self._snapshot_repo.get_by_id(snapshot_id)
        if not snapshot:
            return False

        # 已过期或已失效
        if snapshot.status in ("expired", "invalid"):
            return False

        # 检查后端类型匹配
        kb = await self._kb_repo.get_by_id(snapshot.kb_id, snapshot.tenant_id)
        if not kb:
            await self._snapshot_repo.update(snapshot_id, {"status": "invalid"})
            return False

        if kb.vector_backend != snapshot.vector_backend_type:
            await self._snapshot_repo.update(snapshot_id, {"status": "invalid"})
            logger.warning(
                f"快照 {snapshot_id} 失效: 后端类型不匹配 "
                f"(快照={snapshot.vector_backend_type}, 当前={kb.vector_backend})"
            )
            return False

        return True

    async def cleanup_expired_snapshots(self) -> int:
        """清理过期快照

        查询 status=active AND expires_at < now 的快照，
        标记为 expired 并解冻关联文档。
        建议由定时任务（APScheduler）每天调用。

        Returns:
            清理的快照数
        """
        async with self._session_factory() as session:
            from sqlalchemy import select, update

            stmt = select(KnowledgeSnapshot).where(
                KnowledgeSnapshot.status == "active",
                KnowledgeSnapshot.expires_at < datetime.utcnow(),
            )
            result = await session.execute(stmt)
            expired = result.scalars().all()

            count = 0
            for snap in expired:
                snap.status = "expired"
                # 解冻文档
                doc_ids = snap.doc_ids_json or []
                if doc_ids:
                    await self._doc_repo.unmark_frozen(doc_ids, snap.tenant_id)
                count += 1

            await session.commit()
            if count:
                logger.info(f"清理了 {count} 个过期快照")
            return count

    def _generate_snapshot_id(self) -> str:
        import uuid
        return f"snap_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
