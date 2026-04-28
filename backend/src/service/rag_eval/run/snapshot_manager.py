"""知识库快照管理"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.core.config.cache import ConfigCache
from src.repository.rag_eval.snapshot_repository import SnapshotRepository
from src.schemas.rag_eval.snapshot import SnapshotRead
from src.utils.exceptions import (
    AppException,
)
from src.utils.id_generator import generate_id
from src.utils.logger import logger


class SnapshotManager:
    """知识库快照管理

    通过文件系统复制实现向量库快照的创建与恢复。
    """

    def __init__(
        self,
        snapshot_repository: SnapshotRepository,
        config_cache: ConfigCache | None = None,
    ):
        self._snapshot_repo = snapshot_repository
        self._config = config_cache or ConfigCache.get_instance()

    async def create_snapshot(
        self,
        name: str | None = None,
        description: str = "",
    ) -> SnapshotRead:
        """创建快照

        1. 确定索引工作目录和 document_store 路径
        2. 复制到快照存储路径
        3. 持久化到 knowledge_snapshots 表
        """
        snapshot_id = generate_id()
        snapshot_dir = self._get_snapshot_dir(snapshot_id)
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # 获取当前向量库路径
        work_dir = self._get_work_dir()
        index_src = work_dir / "index"
        docstore_src = work_dir / "document_store.json"

        document_count = 0
        chunk_count = 0

        if index_src.exists():
            shutil.copytree(index_src, snapshot_dir / "index", dirs_exist_ok=True)
            chunk_count = self._count_index_entries(snapshot_dir / "index")

        if docstore_src.exists():
            shutil.copy2(docstore_src, snapshot_dir / "document_store.json")
            try:
                import json
                doc_data = json.loads(docstore_src.read_text())
                document_count = len(doc_data.get("docstore/data", {})) if isinstance(doc_data, dict) else 0
            except Exception:
                pass

        snapshot_name = name or f"snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        orm_obj = await self._snapshot_repo.create({
            "id": snapshot_id,
            "name": snapshot_name,
            "description": description,
            "vector_store_path": str(snapshot_dir),
            "document_count": document_count,
            "chunk_count": chunk_count,
        })

        from src.utils.orm_mapper import OrmMapper
        return OrmMapper.to_read(orm_obj, SnapshotRead)

    async def restore_snapshot(self, snapshot_id: str) -> None:
        """恢复快照

        1. 验证 snapshot 存在
        2. 备份当前索引
        3. 复制快照文件到工作目录
        """
        orm_obj = await self._snapshot_repo.get_by_id(snapshot_id)
        if not orm_obj:
            raise AppException(
                status_code=404,
                code=13005,
                message="快照不存在",
                error_code="SNAPSHOT_NOT_FOUND",
            )

        snapshot_path = Path(orm_obj.vector_store_path)
        if not snapshot_path.exists():
            raise AppException(
                status_code=500,
                code=13010,
                message="快照文件缺失，恢复失败",
                error_code="SNAPSHOT_RESTORE_FAILED",
            )

        work_dir = self._get_work_dir()
        backup_dir = work_dir.parent / f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        try:
            # 备份当前索引
            index_path = work_dir / "index"
            docstore_path = work_dir / "document_store.json"
            backup_dir.mkdir(parents=True, exist_ok=True)

            if index_path.exists():
                shutil.copytree(index_path, backup_dir / "index", dirs_exist_ok=True)
            if docstore_path.exists():
                shutil.copy2(docstore_path, backup_dir / "document_store.json")

            # 清理工作目录
            if index_path.exists():
                shutil.rmtree(index_path)
            if docstore_path.exists():
                docstore_path.unlink()

            # 恢复快照
            snap_index = snapshot_path / "index"
            snap_docstore = snapshot_path / "document_store.json"
            if snap_index.exists():
                shutil.copytree(snap_index, index_path, dirs_exist_ok=True)
            if snap_docstore.exists():
                shutil.copy2(snap_docstore, docstore_path)

            logger.info(f"快照[{snapshot_id}] 恢复成功")
        except Exception as e:
            logger.error(f"快照恢复失败: {e}")
            # 尝试从备份恢复
            if backup_dir.exists() and (backup_dir / "index").exists():
                if index_path.exists():
                    shutil.rmtree(index_path)
                shutil.copytree(backup_dir / "index", index_path, dirs_exist_ok=True)
                if (backup_dir / "document_store.json").exists():
                    shutil.copy2(backup_dir / "document_store.json", docstore_path)
            raise AppException(
                status_code=500,
                code=13010,
                message=f"快照恢复失败: {e}",
                error_code="SNAPSHOT_RESTORE_FAILED",
            )
        finally:
            # 清理备份
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)

    async def list_snapshots(self) -> list[SnapshotRead]:
        """列出所有快照"""
        from src.utils.orm_mapper import OrmMapper
        orm_list = await self._snapshot_repo.get_all(limit=1000)
        return OrmMapper.to_read_list(orm_list, SnapshotRead)

    async def get_snapshot(self, snapshot_id: str) -> SnapshotRead:
        """获取快照详情，不存在抛异常"""
        from src.utils.orm_mapper import OrmMapper
        orm_obj = await self._snapshot_repo.get_by_id(snapshot_id)
        if not orm_obj:
            raise AppException(
                status_code=404,
                code=13005,
                message="快照不存在",
                error_code="SNAPSHOT_NOT_FOUND",
            )
        return OrmMapper.to_read(orm_obj, SnapshotRead)

    def _get_work_dir(self) -> Path:
        """获取 RAG 索引工作目录"""
        base = Path(__file__).resolve().parent.parent.parent.parent.parent
        return base / "storage" / "rag_eval"

    def _get_snapshot_dir(self, snapshot_id: str) -> Path:
        """获取快照存储目录"""
        base = Path(__file__).resolve().parent.parent.parent.parent.parent
        return base / "storage" / "snapshots" / snapshot_id

    def _count_index_entries(self, index_dir: Path) -> int:
        """估算索引条目数"""
        try:
            return len(list(index_dir.rglob("*")))
        except Exception:
            return 0
