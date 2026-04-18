import json
import os
import shutil
from datetime import datetime
from typing import List, Optional

from src.config import settings
from src.core.database import db_session_factory
from src.models.test_case import KnowledgeSnapshot
from src.service.document_manager import document_manager
from src.service.rag_service import rag_service
from src.utils.logger import logger

STORAGE_DIR = settings.rag_storage_dir
SNAPSHOTS_DIR = f"{settings.rag_storage_dir}/snapshots"


class SnapshotService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SnapshotService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.snapshots_dir = SNAPSHOTS_DIR
        os.makedirs(self.snapshots_dir, exist_ok=True)
        self._initialized = True

    def create_snapshot(
        self, name: str = "", description: str = ""
    ) -> KnowledgeSnapshot:
        docs = document_manager.list_documents()
        document_hashes = [doc.file_hash for doc in docs]

        index_size = 0
        if os.path.exists(STORAGE_DIR):
            for root, dirs, files in os.walk(STORAGE_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    index_size += os.path.getsize(file_path)

        snapshot = KnowledgeSnapshot(
            name=name or f"Snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=description,
            document_count=len(docs),
            document_hashes=document_hashes,
            index_size_bytes=index_size,
        )

        snapshot_dir = os.path.join(self.snapshots_dir, snapshot.id)
        os.makedirs(snapshot_dir, exist_ok=True)

        index_dir = os.path.join(STORAGE_DIR, "index")
        snapshot_index_dir = os.path.join(snapshot_dir, "index")
        if os.path.exists(index_dir):
            shutil.copytree(index_dir, snapshot_index_dir, dirs_exist_ok=True)

        doc_store_path = os.path.join(STORAGE_DIR, "document_store.json")
        if os.path.exists(doc_store_path):
            shutil.copy2(
                doc_store_path, os.path.join(snapshot_dir, "document_store.json")
            )

        snapshot.storage_path = snapshot_dir

        self._save_snapshot(snapshot)

        logger.info(f"Snapshot created: {snapshot.id}")
        return snapshot

    def _save_snapshot(self, snapshot: KnowledgeSnapshot):
        try:
            file_path = os.path.join(snapshot.storage_path, "snapshot.json")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(snapshot.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")

    def list_snapshots(self) -> List[KnowledgeSnapshot]:
        snapshots = []
        try:
            for snapshot_id in os.listdir(self.snapshots_dir):
                snapshot_dir = os.path.join(self.snapshots_dir, snapshot_id)
                if os.path.isdir(snapshot_dir):
                    meta_path = os.path.join(snapshot_dir, "snapshot.json")
                    if os.path.exists(meta_path):
                        with open(meta_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            snapshots.append(KnowledgeSnapshot(**data))
            snapshots.sort(key=lambda x: x.created_at, reverse=True)
        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")
        return snapshots

    def get_snapshot(self, snapshot_id: str) -> Optional[KnowledgeSnapshot]:
        try:
            snapshot_dir = os.path.join(self.snapshots_dir, snapshot_id)
            meta_path = os.path.join(snapshot_dir, "snapshot.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return KnowledgeSnapshot(**data)
        except Exception as e:
            logger.error(f"Failed to get snapshot {snapshot_id}: {e}")
        return None

    def restore_snapshot(self, snapshot_id: str) -> bool:
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            logger.error(f"Snapshot {snapshot_id} not found")
            return False

        try:
            if rag_service.index_manager.is_index_available():
                rag_service.index_manager.index = None
                if hasattr(rag_service.retrieval_service, "bm25_retriever"):
                    rag_service.retrieval_service.bm25_retriever = None
                if hasattr(rag_service.retrieval_service, "vector_retriever"):
                    rag_service.retrieval_service.vector_retriever = None

            backup_dir = (
                f"{STORAGE_DIR}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            os.makedirs(backup_dir, exist_ok=True)

            current_index_dir = os.path.join(STORAGE_DIR, "index")
            if os.path.exists(current_index_dir):
                shutil.move(current_index_dir, os.path.join(backup_dir, "index"))

            current_doc_store = os.path.join(STORAGE_DIR, "document_store.json")
            if os.path.exists(current_doc_store):
                shutil.move(
                    current_doc_store, os.path.join(backup_dir, "document_store.json")
                )

            snapshot_index_dir = os.path.join(snapshot.storage_path, "index")

            if os.path.exists(snapshot_index_dir):
                shutil.copytree(snapshot_index_dir, current_index_dir)

            snapshot_doc_store = os.path.join(
                snapshot.storage_path, "document_store.json"
            )

            if os.path.exists(snapshot_doc_store):
                shutil.copy2(snapshot_doc_store, current_doc_store)

            document_manager._load_store()

            rag_service.index_manager._initialize_index()

            logger.info(f"Successfully restored snapshot {snapshot_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore snapshot {snapshot_id}: {e}")
            if "backup_dir" in locals() and os.path.exists(backup_dir):
                backup_index = os.path.join(backup_dir, "index")
                if os.path.exists(backup_index):
                    if os.path.exists(current_index_dir):
                        shutil.rmtree(current_index_dir)
                    shutil.move(backup_index, current_index_dir)

                backup_doc = os.path.join(backup_dir, "document_store.json")
                if os.path.exists(backup_doc):
                    if os.path.exists(current_doc_store):
                        os.remove(current_doc_store)
                    shutil.move(backup_doc, current_doc_store)

                rag_service.index_manager._initialize_index()
                document_manager._load_store()
            return False


snapshot_service = SnapshotService()
