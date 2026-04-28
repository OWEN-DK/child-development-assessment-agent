import uuid
from typing import Callable, List, Optional

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import Node

from src.config import settings
from src.core.interfaces import IIndexManager
from src.service.index_manager.index_operations import IndexOperations
from src.service.index_manager.storage_manager import StorageManager


class IndexManagerService(IIndexManager):
    def __init__(self):
        self.storage_manager = StorageManager()
        self.index_operations = IndexOperations(self.storage_manager)
        self.index_id = str(uuid.uuid4())
        self.index_version = self.index_id
        import hashlib
        import json
        config_str = json.dumps(settings.rag_config, sort_keys=True)
        self.config_fingerprint = hashlib.md5(config_str.encode()).hexdigest()

    def insert_nodes(self, nodes: list[Node], progress_callback: Callable[[str, float, str], None] = None):
        return self.index_operations.insert_nodes(nodes, progress_callback)

    def delete_document(self, file_name: str) -> bool:
        return self.index_operations.delete_document(file_name)

    def get_index(self) -> Optional[VectorStoreIndex]:
        return self.storage_manager.get_index()

    def is_index_available(self) -> bool:
        return self.storage_manager.is_index_available()

    def get_corpus_size(self) -> int:
        return self.storage_manager.get_corpus_size()

    def get_document_chunks(self, file_hash: str, page: int = 1, page_size: int = 20) -> dict:
        return self.index_operations.get_document_chunks(file_hash, page, page_size)

    def get_chunk_detail(self, chunk_id: str) -> Optional[dict]:
        return self.index_operations.get_chunk_detail(chunk_id)

    def get_all_chunks_by_file_hash(self, file_hash: str) -> List[dict]:
        return self.index_operations.get_all_chunks_by_file_hash(file_hash)

    def __del__(self):
        self.storage_manager.shutdown()
