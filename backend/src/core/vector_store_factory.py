from typing import Dict, Type, Callable
from llama_index.core.vector_stores.types import BasePydanticVectorStore
from src.config.settings import settings
from src.utils.logger import logger

class VectorStoreFactory:
    """向量存储工厂，实现向量库无关性"""
    
    _stores: Dict[str, Callable[[], Type[BasePydanticVectorStore]]] = {
        "chroma": lambda: __import__("llama_index.vector_stores.chroma", fromlist=["ChromaVectorStore"]).ChromaVectorStore,
        "pinecone": lambda: __import__("llama_index.vector_stores.pinecone", fromlist=["PineconeVectorStore"]).PineconeVectorStore,
        "milvus": lambda: __import__("llama_index.vector_stores.milvus", fromlist=["MilvusVectorStore"]).MilvusVectorStore,
        "weaviate": lambda: __import__("llama_index.vector_stores.weaviate", fromlist=["WeaviateVectorStore"]).WeaviateVectorStore,
    }
    
    @staticmethod
    def get_vector_store() -> BasePydanticVectorStore:
        """根据配置获取向量存储实例"""
        store_type = settings.vector_store_type
        store_config = settings.vector_store_config
        
        if store_type not in VectorStoreFactory._stores:
            raise ValueError(f"Unsupported vector store type: {store_type}")
        
        # 验证必填配置项
        required_params = {
            "chroma": ["persist_dir", "collection_name"],
            "pinecone": ["api_key", "environment", "index_name"],
            "milvus": ["host", "port", "collection_name"],
            "weaviate": ["host", "port", "index_name"],
        }
        
        if store_type in required_params:
            missing_params = [param for param in required_params[store_type] if param not in store_config]
            if missing_params:
                raise ValueError(f"Missing required parameters for {store_type} vector store: {', '.join(missing_params)}")
        
        store_class_factory = VectorStoreFactory._stores[store_type]
        store_class = store_class_factory()
        
        # Chroma本地模式特殊处理
        if store_type == "chroma" and "persist_dir" in store_config:
            import chromadb
            from llama_index.vector_stores.chroma import ChromaVectorStore
            
            # 创建本地持久化客户端
            db = chromadb.PersistentClient(path=store_config["persist_dir"])
            collection = db.get_or_create_collection(
                name=store_config["collection_name"],
                metadata={"hnsw:space": "cosine"}
            )
            vector_store = ChromaVectorStore(chroma_collection=collection)
        else:
            vector_store = store_class(**store_config)
        
        logger.info(f"Initialized vector store: {store_type}")
        return vector_store
