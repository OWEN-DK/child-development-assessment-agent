"""元数据处理模块

提供元数据提取、节点清理、关键块识别和多种分块策略。
"""

from src.core.metadata.chunk_chapter import split_chapters_into_chunks
from src.core.metadata.chunk_hierarchical import hierarchical_chunking
from src.core.metadata.chunk_page import split_pages_into_chunks
from src.core.metadata.key_chunk_identifier import identify_key_chunks
from src.core.metadata.metadata_extraction import MetadataExtractionService
from src.core.metadata.node_cleaner import clean_node_content
from src.core.metadata.splitter_manager import (
    detect_language,
    get_chapter_splitter,
    get_semantic_splitter,
)

__all__ = [
    "split_chapters_into_chunks",
    "split_pages_into_chunks",
    "hierarchical_chunking",
    "identify_key_chunks",
    "clean_node_content",
    "MetadataExtractionService",
    "detect_language",
    "get_semantic_splitter",
    "get_chapter_splitter",
]
