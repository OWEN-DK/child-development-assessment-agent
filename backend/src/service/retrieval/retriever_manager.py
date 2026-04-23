import logging
import os
import warnings
from typing import Optional

import jieba
from llama_index.core.retrievers import BaseRetriever
from llama_index.retrievers.bm25 import BM25Retriever

from src.config import BASE_DIR, settings
from src.core.reranker import CrossEncoderReranker
from src.service.cache_service import CacheService
from src.service.index_manager_service import IndexManagerService
from src.utils.logger import logger

# 抑制 llama_index BM25 tokenizer 弃用警告（该库使用 logger.warning 而非 warnings.warn）
logging.getLogger("llama_index.retrievers.bm25.base").setLevel(logging.ERROR)


class RetrieverManager:
    """检索器管理服务，负责初始化和重载检索器"""

    _ever_initialized = False

    def __init__(self, index_manager: IndexManagerService, cache_service: CacheService):
        self.index_manager = index_manager
        self.cache_service = cache_service
        self.bm25_retriever: Optional[BaseRetriever] = None
        self.vector_retriever: Optional[BaseRetriever] = None
        self.bm25_weight = 0.5
        self.vector_weight = 0.5
        self.merge_mode = "OR"

        # 初始化 Cross-Encoder 重排序器
        self.reranker = CrossEncoderReranker(
            model_name=settings.rag_reranker_model,
            initial_k=settings.rag_reranker_initial_k,
            final_k=settings.rag_reranker_final_k,
        )

        # 加载 jieba 自定义词典
        custom_dict_path = os.path.join(
            BASE_DIR, "src", "data", "jieba_custom_dict.txt"
        )
        if os.path.exists(custom_dict_path):
            jieba.load_userdict(custom_dict_path)
            if not RetrieverManager._ever_initialized:
                logger.info(f"Loaded jieba custom dictionary from {custom_dict_path}")

        self.dashscope_available = bool(settings.dashscope_api_key)
        self._initialize_retrievers()

    def _initialize_retrievers(self) -> None:
        """初始化BM25和向量检索器"""
        index = self.index_manager.get_index()
        if not index:
            return

        rag_config = settings.rag_config["hybrid_retrieval"]
        corpus_size = self.index_manager.get_corpus_size()

        if corpus_size == 0:
            logger.warning("Index is empty. Skipping retriever initialization.")
            self.bm25_retriever = None
            self.vector_retriever = None
            return

        # 动态调整top_k
        bm25_top_k = min(rag_config["bm25_top_k"], max(1, corpus_size))
        vector_top_k = min(rag_config["vector_top_k"], max(1, corpus_size))

        # 初始化向量检索器（优先初始化，作为回退）
        try:
            self.vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)
            if not RetrieverManager._ever_initialized:
                logger.info(f"Vector retriever initialized: top_k={vector_top_k}")
        except Exception as e:
            logger.error(f"Failed to initialize vector retriever: {e}")
            self.vector_retriever = None
            return

        # 检查 docstore 是否有内容（BM25 需要 docstore，而不仅仅是向量存储）
        has_docstore_docs = False
        if hasattr(index, "docstore") and index.docstore:
            has_docstore_docs = len(index.docstore.docs) > 0
            if not RetrieverManager._ever_initialized:
                logger.info(f"Docstore contains {len(index.docstore.docs)} documents")

        if not has_docstore_docs:
            logger.warning(
                "Docstore is empty. BM25 retriever cannot be initialized. Using vector-only retrieval."
            )
            self.bm25_retriever = None
            return

        # 初始化BM25检索器（使用jieba分词）
        try:
            self.bm25_retriever = BM25Retriever.from_defaults(
                index=index, similarity_top_k=bm25_top_k, tokenizer=jieba.lcut
            )
            if not RetrieverManager._ever_initialized:
                logger.info(f"BM25 retriever initialized: top_k={bm25_top_k}")
        except Exception as e:
            logger.error(
                f"Failed to initialize BM25 retriever: {e}. Falling back to vector-only retrieval."
            )
            self.bm25_retriever = None
            return

        # 设置混合检索权重
        self.bm25_weight = rag_config["bm25_weight"]
        self.vector_weight = rag_config["vector_weight"]
        self.merge_mode = rag_config["merge_mode"]
        if not RetrieverManager._ever_initialized:
            RetrieverManager._ever_initialized = True
            logger.info(
                f"Hybrid retrieval enabled: BM25 weight={self.bm25_weight}, Vector weight={self.vector_weight}"
            )

    def reload_retrievers(self) -> None:
        """重新加载检索器（索引更新后调用）"""
        self._initialize_retrievers()
        self.cache_service.clear()
        logger.info("Retrievers reloaded")
