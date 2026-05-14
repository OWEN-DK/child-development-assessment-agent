"""向量存储适配器工厂"""
from typing import Optional

from src.core.knowledge_base.vector_store.base import VectorStoreAdapter
from src.core.knowledge_base.vector_store.chroma import ChromaAdapter
from src.core.knowledge_base.vector_store.elasticsearch import ElasticsearchAdapter
from src.core.knowledge_base.vector_store.milvus import MilvusAdapter
from src.utils.exceptions import ConfigurationError
from src.utils.logger import logger


class VectorStoreAdapterFactory:
    """向量存储适配器工厂"""

    _adapters: dict[str, VectorStoreAdapter] = {}

    @classmethod
    def get_adapter(
        cls,
        backend_type: str,
        es_url: Optional[str] = None,
        milvus_host: Optional[str] = None,
        milvus_port: int = 19530,
        chroma_storage_dir: str = "./app_data/storage/chroma",
    ) -> VectorStoreAdapter:
        """获取向量存储适配器

        Args:
            backend_type: 后端类型（chroma/elasticsearch/milvus）
            es_url: ES 地址（elasticsearch 后端必需）
            milvus_host: Milvus 地址（milvus 后端必需）
            milvus_port: Milvus 端口
            chroma_storage_dir: Chroma 存储目录

        Returns:
            VectorStoreAdapter 实例

        Raises:
            ConfigurationError: 后端未配置
        """
        if backend_type in cls._adapters:
            return cls._adapters[backend_type]

        if backend_type == "chroma":
            adapter = ChromaAdapter(storage_dir=chroma_storage_dir)
        elif backend_type == "elasticsearch":
            if not es_url:
                raise ConfigurationError(message="Elasticsearch 后端需要配置 ES_URL")
            adapter = ElasticsearchAdapter(es_url=es_url)
        elif backend_type == "milvus":
            if not milvus_host:
                raise ConfigurationError(message="Milvus 后端需要配置 MILVUS_HOST")
            adapter = MilvusAdapter(host=milvus_host, port=milvus_port)
        else:
            raise ConfigurationError(message=f"不支持的向量后端: {backend_type}")

        cls._adapters[backend_type] = adapter
        logger.info(f"向量存储适配器初始化: {backend_type}")
        return adapter

    @classmethod
    def reset(cls):
        """重置所有适配器（测试用）"""
        cls._adapters.clear()
