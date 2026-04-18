"""分块器单例管理模块

管理语义分块器的单例和语言检测功能。
"""

from typing import Optional

from llama_index.core.node_parser import SemanticSplitterNodeParser

from src.config import settings
from src.utils.logger import logger

_semantic_splitter: Optional[SemanticSplitterNodeParser] = None
_semantic_splitter_en: Optional[SemanticSplitterNodeParser] = None


def detect_language(text: str) -> str:
    """检测文本主要语言

    Args:
        text: 待检测的文本

    Returns:
        "en" 或 "zh"
    """
    if not text:
        return "zh"

    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    total_chars = sum(1 for c in text if c.isalpha())

    if total_chars == 0:
        return "zh"

    return (
        "en"
        if english_chars / total_chars > settings.rag_chunking_language_detection_threshold
        else "zh"
    )


def get_semantic_splitter(content_text: Optional[str] = None) -> SemanticSplitterNodeParser:
    """获取语义分块器单例

    根据文本语言自动选择中文或英文优化的分块器配置。

    Args:
        content_text: 可选的文本内容，用于检测语言并调整分块策略

    Returns:
        语义分块器实例
    """
    global _semantic_splitter, _semantic_splitter_en

    language = detect_language(content_text) if content_text else "zh"

    if language == "en" and _semantic_splitter_en is not None:
        return _semantic_splitter_en

    if language == "zh" and _semantic_splitter is not None:
        return _semantic_splitter

    from llama_index.core import Settings

    if language == "en":
        buffer_size = max(
            settings.semantic_splitter_buffer_size,
            settings.rag_chunking_english_buffer_size,
        )
        breakpoint_threshold = max(
            settings.semantic_splitter_breakpoint_threshold,
            settings.rag_chunking_english_breakpoint_threshold,
        )
        chunk_size = int(
            settings.rag_epub_chunk_target_size * settings.rag_chunking_english_size_multiplier
        )
        logger.debug(
            f"Using English-optimized semantic splitter: "
            f"buffer={buffer_size}, threshold={breakpoint_threshold}, chunk_size={chunk_size}"
        )

        _semantic_splitter_en = SemanticSplitterNodeParser(
            embed_model=Settings.embed_model,
            buffer_size=buffer_size,
            breakpoint_percentile_threshold=breakpoint_threshold,
            chunk_size=chunk_size,
        )
        return _semantic_splitter_en
    else:
        _semantic_splitter = SemanticSplitterNodeParser(
            embed_model=Settings.embed_model,
            buffer_size=settings.semantic_splitter_buffer_size,
            breakpoint_percentile_threshold=settings.semantic_splitter_breakpoint_threshold,
            chunk_size=settings.rag_epub_chunk_target_size,
        )
        return _semantic_splitter


def get_chapter_splitter(content_text: Optional[str] = None) -> SemanticSplitterNodeParser:
    """获取针对长章节优化的语义分块器

    Args:
        content_text: 可选的文本内容，用于检测语言并调整分块策略

    Returns:
        针对长章节优化的语义分块器实例
    """
    from llama_index.core import Settings

    language = detect_language(content_text) if content_text else "zh"

    if language == "en":
        buffer_size = max(
            settings.semantic_splitter_chapter_buffer_size,
            settings.rag_chunking_english_buffer_size,
        )
        breakpoint_threshold = max(
            settings.semantic_splitter_chapter_breakpoint_threshold,
            settings.rag_chunking_english_breakpoint_threshold,
        )
        chunk_size = int(
            settings.rag_epub_chunk_target_size * settings.rag_chunking_english_size_multiplier
        )
        logger.debug(
            f"Using English-optimized splitter: "
            f"buffer={buffer_size}, threshold={breakpoint_threshold}, chunk_size={chunk_size}"
        )
    else:
        buffer_size = settings.semantic_splitter_chapter_buffer_size
        breakpoint_threshold = settings.semantic_splitter_chapter_breakpoint_threshold
        chunk_size = settings.rag_epub_chunk_target_size

    return SemanticSplitterNodeParser(
        embed_model=Settings.embed_model,
        buffer_size=buffer_size,
        breakpoint_percentile_threshold=breakpoint_threshold,
        chunk_size=chunk_size,
    )
