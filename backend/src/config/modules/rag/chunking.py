"""RAG 分块配置：基础分块、长章节分块、语义分块"""

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()


class RagChunkingSettings(BaseSettings):
    """RAG 分块配置"""

    # 基础分块
    rag_chunk_size: int = Field(
        default=1024,
        validation_alias="RAG_CHUNK_SIZE",
        description="默认分块大小（字符）",
    )
    rag_chunk_overlap: int = Field(
        default=200,
        validation_alias="RAG_CHUNK_OVERLAP",
        description="分块重叠大小（字符）",
    )
    rag_pdf_chunk_size: int = Field(
        default=1536,
        validation_alias="RAG_PDF_CHUNK_SIZE",
        description="PDF 分块大小（字符）",
    )
    rag_epub_chunk_target_size: int = Field(
        default=1024,
        validation_alias="RAG_EPUB_CHUNK_TARGET_SIZE",
        description="EPUB 分块目标大小（字符）",
    )

    # 长章节分块
    semantic_splitter_chapter_max_size: int = Field(
        default=3000,
        validation_alias="SEMANTIC_SPLITTER_CHAPTER_MAX_SIZE",
        description="长章节最大大小",
    )
    semantic_splitter_chapter_split_threshold: int = Field(
        default=50,
        validation_alias="SEMANTIC_SPLITTER_CHAPTER_SPLIT_THRESHOLD",
        description="长章节分割阈值",
    )

    # 语义分块设置
    semantic_splitter_buffer_size: int = Field(
        5,
        validation_alias="SEMANTIC_SPLITTER_BUFFER_SIZE",
        description="语义分块时比较的前后段落数",
    )
    semantic_splitter_breakpoint_threshold: int = Field(
        90,
        validation_alias="SEMANTIC_SPLITTER_BREAKPOINT_THRESHOLD",
        description="语义分块相似度阈值（百分比），低于此值则分割",
    )
    semantic_splitter_chapter_buffer_size: int = Field(
        3,
        validation_alias="SEMANTIC_SPLITTER_CHAPTER_BUFFER_SIZE",
        description="长章节语义分块时比较的前后段落数",
    )
    semantic_splitter_chapter_breakpoint_threshold: int = Field(
        75,
        validation_alias="SEMANTIC_SPLITTER_CHAPTER_BREAKPOINT_THRESHOLD",
        description="长章节语义分块相似度阈值（百分比），低于此值则分割",
    )
    semantic_splitter_separators: List[str] = Field(
        default_factory=lambda: [
            "\n## ",
            "\n### ",
            "\n#### ",  # 标题边界
            "\n\n",  # 段落边界
            "\n",  # 换行边界
            "。",
            "！",
            "？",  # 中文句子结束
            ". ",
            "! ",
            "? ",  # 英文句子结束
        ],
        description="语义分块优先使用的分隔符列表，按优先级排序",
    )

    # 英文分块优化配置
    rag_chunking_english_buffer_size: int = Field(
        default=8,
        validation_alias="RAG_CHUNKING_ENGLISH_BUFFER_SIZE",
        description="英文内容分块 buffer 大小",
    )
    rag_chunking_english_breakpoint_threshold: int = Field(
        default=92,
        validation_alias="RAG_CHUNKING_ENGLISH_BREAKPOINT_THRESHOLD",
        description="英文内容分块 breakpoint 阈值",
    )
    rag_chunking_english_size_multiplier: float = Field(
        default=1.3,
        validation_alias="RAG_CHUNKING_ENGLISH_SIZE_MULTIPLIER",
        description="英文内容分块大小倍率",
    )

    # 语言检测配置
    rag_chunking_language_detection_threshold: float = Field(
        default=0.7,
        validation_alias="RAG_CHUNKING_LANGUAGE_DETECTION_THRESHOLD",
        description="语言检测英文占比阈值",
    )

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
