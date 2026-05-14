"""知识库服务门面

协调 KB CRUD、文档管理、索引重建、后端迁移。
"""
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.knowledge_base.bm25_index import BM25IndexManager
from src.core.knowledge_base.vector_store.factory import VectorStoreAdapterFactory
from src.models.knowledge_base import KnowledgeBase
from src.repository.knowledge.chunk_repo import ChunkRepository
from src.repository.knowledge.document_repo import DocumentRepository
from src.repository.knowledge.kb_repo import KnowledgeBaseRepository
from src.repository.knowledge.rebuild_repo import RebuildTaskRepository
from src.schemas.knowledge.knowledge_base import (
    CreateKnowledgeBaseReq,
    KnowledgeBaseDetail,
    KnowledgeBaseList,
    KnowledgeBaseSummary,
    UpdateChunkStrategyReq,
    UpdateEmbeddingConfigReq,
    UpdateKnowledgeBaseReq,
    VectorBackend,
)
from src.utils.logger import logger


class KnowledgeBaseService:
    """知识库服务门面"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory
        self.kb_repo = KnowledgeBaseRepository(db_session_factory)
        self.doc_repo = DocumentRepository(db_session_factory)
        self.chunk_repo = ChunkRepository(db_session_factory)
        self.rebuild_repo = RebuildTaskRepository(db_session_factory)
        self.bm25_manager = BM25IndexManager()

    async def create(
        self, data: CreateKnowledgeBaseReq, tenant_id: str, user_id: str
    ) -> KnowledgeBaseDetail:
        """创建知识库

        同时创建 MySQL 记录 + 向量存储 Collection + BM25 索引（如需）
        失败时自动回滚已创建的资源。
        """
        kb_id = self._generate_id()
        collection_created = False

        try:
            # 1. 创建向量存储 Collection
            adapter = VectorStoreAdapterFactory.get_adapter(
                data.vector_backend.value,
                es_url=self._get_es_url(),
                milvus_host=self._get_milvus_host(),
            )
            dimension = data.embedding_config.dimension if data.embedding_config else 1024
            await adapter.create_collection(kb_id, tenant_id, dimension)
            collection_created = True

            # 2. Chroma/Milvus 后端需要创建 BM25 索引目录
            if data.vector_backend != VectorBackend.ELASTICSEARCH:
                await self.bm25_manager.rebuild(kb_id, tenant_id, [])

            # 3. 创建 MySQL 记录
            kb_data = {
                "id": kb_id,
                "tenant_id": tenant_id,
                "name": data.name,
                "description": data.description,
                "vector_backend": data.vector_backend.value,
                "chunk_strategy": data.chunk_strategy.model_dump() if data.chunk_strategy else None,
                "embedding_config": data.embedding_config.model_dump() if data.embedding_config else None,
                "visibility": data.visibility.value,
                "visible_roles": data.visible_roles,
                "owner_id": user_id,
                "status": "ready",
            }
            kb = await self.kb_repo.create(kb_data)

            logger.info(f"知识库创建成功: {kb_id} ({data.name})")
            return self._to_detail(kb)

        except Exception as e:
            logger.error(f"知识库创建失败: {kb_id}, {e}")

            # 回滚：清理已创建的资源
            if collection_created:
                try:
                    adapter = VectorStoreAdapterFactory.get_adapter(
                        data.vector_backend.value,
                        es_url=self._get_es_url(),
                        milvus_host=self._get_milvus_host(),
                    )
                    await adapter.delete_collection(kb_id, tenant_id)
                    logger.info(f"回滚：向量 Collection 已删除: {kb_id}")
                except Exception as rollback_error:
                    logger.error(f"回滚失败: {rollback_error}")

            if data.vector_backend != VectorBackend.ELASTICSEARCH:
                try:
                    await self.bm25_manager.delete_index(kb_id, tenant_id)
                    logger.info(f"回滚：BM25 索引已删除: {kb_id}")
                except Exception as rollback_error:
                    logger.error(f"回滚失败: {rollback_error}")

            raise

    async def list(
        self,
        tenant_id: str,
        keyword: Optional[str] = None,
        vector_backend: Optional[str] = None,
        status: Optional[str] = None,
        visibility: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> KnowledgeBaseList:
        """列出知识库"""
        items = await self.kb_repo.search(
            tenant_id=tenant_id,
            keyword=keyword,
            vector_backend=vector_backend,
            status=status,
            visibility=visibility,
            skip=skip,
            limit=limit,
        )
        total = await self.kb_repo.count_by_tenant(tenant_id)
        return KnowledgeBaseList(
            items=[self._to_summary(kb) for kb in items],
            total=total,
        )

    async def get_detail(self, kb_id: str, tenant_id: str) -> KnowledgeBaseDetail:
        """获取知识库详情"""
        kb = await self.kb_repo.get_by_id(kb_id, tenant_id)
        if not kb:
            raise ValueError(f"知识库不存在: {kb_id}")
        return self._to_detail(kb)

    async def update(
        self, kb_id: str, data: UpdateKnowledgeBaseReq, tenant_id: str
    ) -> KnowledgeBaseDetail:
        """更新知识库"""
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get_detail(kb_id, tenant_id)

        # 枚举转字符串
        if "visibility" in update_data and update_data["visibility"]:
            update_data["visibility"] = update_data["visibility"].value

        await self.kb_repo.update(kb_id, update_data, tenant_id)
        return await self.get_detail(kb_id, tenant_id)

    async def delete(self, kb_id: str, tenant_id: str, force: bool = False) -> None:
        """删除知识库

        级联删除：文档 → 分块 → 向量 → BM25 → 重建任务
        """
        # 检查管道引用（force=False 时）
        if not force:
            references = await self._check_pipeline_references(kb_id, tenant_id)
            if references:
                raise ValueError(
                    f"知识库被 {len(references)} 个管道引用，无法删除。"
                    f"使用 force=true 强制删除。"
                )

        # 删除向量存储
        kb = await self.kb_repo.get_by_id(kb_id, tenant_id)
        if kb:
            adapter = VectorStoreAdapterFactory.get_adapter(
                kb.vector_backend,
                es_url=self._get_es_url(),
                milvus_host=self._get_milvus_host(),
            )
            await adapter.delete_collection(kb_id, tenant_id)

        # 删除 BM25 索引
        await self.bm25_manager.delete_index(kb_id, tenant_id)

        # 删除分块
        await self.chunk_repo.delete_by_kb(kb_id, tenant_id)

        # 删除文档（TODO: 级联删除文件）

        # 删除知识库记录
        await self.kb_repo.delete(kb_id, tenant_id)

        logger.info(f"知识库删除成功: {kb_id}")

    async def update_chunk_strategy(
        self, kb_id: str, data: UpdateChunkStrategyReq, tenant_id: str
    ) -> str:
        """更新分块策略（触发重建）"""
        update_data = {"chunk_strategy": data.chunk_strategy.model_dump()}
        await self.kb_repo.update(kb_id, update_data, tenant_id)

        # 创建重建任务
        task_id = self._generate_id()
        task_data = {
            "id": task_id,
            "kb_id": kb_id,
            "tenant_id": tenant_id,
            "trigger": "chunk_change",
            "status": "running",
        }
        await self.rebuild_repo.create(task_data)

        # TODO: 异步执行重建
        logger.info(f"分块策略更新，重建任务创建: {task_id}")
        return task_id

    async def update_embedding_config(
        self, kb_id: str, data: UpdateEmbeddingConfigReq, tenant_id: str
    ) -> str:
        """更新 Embedding 配置（触发重建）"""
        update_data = {"embedding_config": data.embedding_config.model_dump()}
        await self.kb_repo.update(kb_id, update_data, tenant_id)

        # 创建重建任务
        task_id = self._generate_id()
        task_data = {
            "id": task_id,
            "kb_id": kb_id,
            "tenant_id": tenant_id,
            "trigger": "embedding_change",
            "status": "running",
        }
        await self.rebuild_repo.create(task_data)

        logger.info(f"Embedding 配置更新，重建任务创建: {task_id}")
        return task_id

    async def migrate_backend(
        self, kb_id: str, target_backend: VectorBackend, tenant_id: str
    ) -> dict[str, Any]:
        """迁移向量后端"""
        kb = await self.kb_repo.get_by_id(kb_id, tenant_id)
        if not kb:
            raise ValueError(f"知识库不存在: {kb_id}")

        if kb.vector_backend == target_backend.value:
            raise ValueError("目标后端与当前后端相同")

        # 创建重建任务
        task_id = self._generate_id()
        task_data = {
            "id": task_id,
            "kb_id": kb_id,
            "tenant_id": tenant_id,
            "trigger": "backend_migration",
            "status": "running",
        }
        await self.rebuild_repo.create(task_data)

        # 更新知识库状态
        await self.kb_repo.update_status(kb_id, tenant_id, "rebuilding")

        # TODO: 异步执行迁移

        return {
            "source_backend": kb.vector_backend,
            "target_backend": target_backend.value,
            "rebuild_task_id": task_id,
        }

    async def _check_pipeline_references(self, kb_id: str, tenant_id: str) -> list[dict]:
        """检查知识库是否被管道引用

        Returns:
            引用该知识库的管道列表 [{"pipeline_id": str, "pipeline_name": str}, ...]
        """
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                # 查询 pipeline_versions 中 config_snapshot 引用了该 kb_id 的管道
                stmt = text("""
                    SELECT DISTINCT p.id, p.name
                    FROM pipelines p
                    JOIN pipeline_versions pv ON pv.pipeline_id = p.id
                    WHERE p.tenant_id = :tenant_id
                    AND pv.config_snapshot LIKE :kb_pattern
                """)
                result = await session.execute(stmt, {
                    "tenant_id": tenant_id,
                    "kb_pattern": f"%{kb_id}%",
                })
                rows = result.fetchall()
                return [{"pipeline_id": row[0], "pipeline_name": row[1]} for row in rows]
        except Exception as e:
            logger.warning(f"检查管道引用失败: {e}")
            return []

    def _generate_id(self) -> str:
        """生成唯一 ID"""
        return str(uuid.uuid4()).replace("-", "")[:24]

    def _get_es_url(self) -> Optional[str]:
        """获取 ES URL"""
        import os
        return os.getenv("ES_URL") or None

    def _get_milvus_host(self) -> Optional[str]:
        """获取 Milvus Host"""
        import os
        return os.getenv("MILVUS_HOST") or None

    def _to_summary(self, kb: KnowledgeBase) -> KnowledgeBaseSummary:
        """转换为摘要模型"""
        return KnowledgeBaseSummary(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            vector_backend=kb.vector_backend,
            visibility=kb.visibility,
            status=kb.status,
            document_count=kb.document_count,
            chunk_count=kb.chunk_count,
            storage_size_bytes=kb.storage_size_bytes,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )

    def _to_detail(self, kb: KnowledgeBase) -> KnowledgeBaseDetail:
        """转换为详情模型"""
        return KnowledgeBaseDetail(
            id=kb.id,
            tenant_id=kb.tenant_id,
            name=kb.name,
            description=kb.description,
            vector_backend=kb.vector_backend,
            chunk_strategy=kb.chunk_strategy,
            embedding_config=kb.embedding_config,
            visibility=kb.visibility,
            visible_roles=kb.visible_roles,
            owner_id=kb.owner_id,
            status=kb.status,
            document_count=kb.document_count,
            chunk_count=kb.chunk_count,
            storage_size_bytes=kb.storage_size_bytes,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )
