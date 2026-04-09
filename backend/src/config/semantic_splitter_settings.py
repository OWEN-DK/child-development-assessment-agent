from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List

class SemanticSplitterSettings(BaseSettings):
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
            "\n## ", "\n### ", "\n#### ",  # 标题边界
            "\n\n",                        # 段落边界
            "\n",                          # 换行边界
            "。", "！", "？",              # 中文句子结束
            ". ", "! ", "? "               # 英文句子结束
        ],
        description="语义分块优先使用的分隔符列表，按优先级排序"
    )
