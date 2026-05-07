"""元数据处理器门面类

协调所有子服务，保持对外 API 完全兼容。
"""

from typing import Callable, Dict, List, Optional

from llama_index.core.schema import Document, Node

from src.config import settings
from src.core.metadata.chunk_chapter import split_chapters_into_chunks as _split_chapters
from src.core.metadata.chunk_hierarchical import hierarchical_chunking as _hierarchical_chunk
from src.core.metadata.chunk_page import split_pages_into_chunks as _split_pages
from src.core.metadata.metadata_extraction import MetadataExtractionService


class MetadataProcessor:
    """元数据处理工具类，统一处理节点的元数据提取

    门面类，协调分块器管理、元数据提取、节点清理等子服务。
    """

    def __init__(self, concurrency: Optional[int] = None):
        self.concurrency = concurrency or settings.rag_metadata_extraction_concurrency
        self._extraction_service = MetadataExtractionService(
            concurrency=self.concurrency
        )

    async def process_nodes(
        self,
        nodes: List[Node],
        file_hash: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
        total_chunks: Optional[int] = None,
        use_hierarchical: bool = True,
        doc_level_metadata: Optional[dict] = None,
    ) -> List[Node]:
        """批量处理节点，提取元数据

        支持三种策略：
        1. 分层提取（推荐）：文档级元数据 + 关键块单独提取
        2. 规则优先：默认规则提取，质量低时 LLM 兜底
        3. 全量 LLM：每个块都调用 LLM（不推荐用于大量分块）

        Args:
            nodes: 待处理的节点列表
            file_hash: 文档的哈希值，用于关联
            progress_callback: 进度回调函数
            total_chunks: 总块数，用于进度计算
            use_hierarchical: 是否使用分层提取策略
            doc_level_metadata: 文档级元数据（如果已预先提取）

        Returns:
            处理后的节点列表
        """
        if total_chunks is None:
            total_chunks = len(nodes)

        if use_hierarchical and total_chunks > 100:
            logger.info(
                f"Using hierarchical metadata extraction for {total_chunks} chunks"
            )
            return await self._extraction_service.process_hierarchical(
                nodes, file_hash, progress_callback, total_chunks, doc_level_metadata
            )
        else:
            logger.info(f"Using standard metadata extraction for {total_chunks} chunks")
            return await self._extraction_service.process_standard(
                nodes, file_hash, progress_callback, total_chunks
            )

    @staticmethod
    def split_chapters_into_chunks(
        documents: List[Document],
        chunk_target_size: int = 1024,
        file_hash: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ) -> List[Node]:
        """将章节级文档拆分为更小的块

        委托给 chunk_chapter 模块处理。
        """
        return _split_chapters(documents, chunk_target_size, file_hash, progress_callback)

    @staticmethod
    def split_pages_into_chunks(
        documents: List[Document],
        chunk_size: int = 1536,
        chunk_overlap: int = 200,
        file_hash: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ) -> List[Node]:
        """将页级文档拆分为更小的块

        委托给 chunk_page 模块处理。
        """
        return _split_pages(documents, chunk_size, chunk_overlap, file_hash, progress_callback)

    @staticmethod
    def hierarchical_chunking(
        documents: List[Document],
        parent_chunk_size: int = 1500,
        child_chunk_size: int = 400,
        file_hash: Optional[str] = None,
    ) -> List[Node]:
        """父子块关联分块策略

        委托给 chunk_hierarchical 模块处理。
        """
        return _hierarchical_chunk(
            documents, parent_chunk_size, child_chunk_size, file_hash
        )


from src.utils.logger import logger
