from abc import ABC, abstractmethod
from typing import List, Optional, Callable, Any
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import Node

class IIndexManager(ABC):
    """索引管理服务接口"""
    
    @abstractmethod
    def get_index(self) -> Optional[VectorStoreIndex]:
        pass
    
    @abstractmethod
    def is_index_available(self) -> bool:
        pass
    
    @abstractmethod
    def insert_nodes(self, nodes: list[Node], progress_callback: Callable[[str, float, str], None] = None):
        pass
    
    @abstractmethod
    def delete_document(self, file_name: str) -> bool:
        pass
    
    @abstractmethod
    def get_corpus_size(self) -> int:
        pass
    
    @abstractmethod
    def get_document_chunks(self, file_hash: str) -> List[dict]:
        """获取指定文档的所有分块"""
        pass
    
    @abstractmethod
    def get_chunk_detail(self, chunk_id: str) -> Optional[dict]:
        """获取指定分块的详细信息"""
        pass

class ICacheService(ABC):
    """缓存服务接口"""
    
    @abstractmethod
    def get(self, key: tuple, default: Any = None) -> Any:
        pass
    
    @abstractmethod
    def set(self, key: tuple, value: Any, expire: int = 3600, doc_hashes: list[str] = None):
        pass
    
    @abstractmethod
    def invalidate_by_doc_hash(self, doc_hash: str):
        pass
    
    @abstractmethod
    def clear(self):
        pass

class IRetrievalService(ABC):
    """检索服务接口"""
    
    @abstractmethod
    async def retrieve_knowledge(self, query: str, age: int, limit: int = 3, load_level: str = "l1") -> List[Any]:
        pass
    
    @abstractmethod
    async def search_content(self, query: str, limit: int = 20) -> List[dict]:
        pass
    
    @abstractmethod
    def reload_retrievers(self):
        pass

class IDocumentIngestionService(ABC):
    """文档导入服务接口"""
    
    @abstractmethod
    async def ingest_book(self, file_path: str, original_filename: str = None, progress_callback=None) -> str:
        pass
