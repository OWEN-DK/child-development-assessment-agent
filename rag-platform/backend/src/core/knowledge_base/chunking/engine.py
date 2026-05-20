"""分块引擎门面

根据策略配置选择分块策略，执行分块并应用约束。
"""
from typing import Any

from src.utils.exceptions import InvalidParamsException

from src.core.knowledge_base.chunking.strategies import (
    BaseChunkingStrategy,
    Chunk,
    FixedSizeChunking,
    HeadingChunking,
    ParagraphChunking,
    RecursiveChunking,
    SemanticChunking,
    _estimate_tokens,
)


class ChunkingEngine:
    """分块引擎门面"""

    def __init__(self):
        self._strategies: dict[str, BaseChunkingStrategy] = {
            "fixed_size": FixedSizeChunking(),
            "semantic": SemanticChunking(),
            "paragraph": ParagraphChunking(),
            "heading": HeadingChunking(),
            "recursive": RecursiveChunking(),
        }

    def chunk(self, text: str, strategy_config: dict[str, Any]) -> list[Chunk]:
        """执行分块

        Args:
            text: 输入文本
            strategy_config: 分块策略配置（必须包含 "type" 字段）

        Returns:
            分块结果列表
        """
        strategy_type = strategy_config.get("type", "fixed_size")
        strategy = self._strategies.get(strategy_type)
        if not strategy:
            raise InvalidParamsException(message=f"不支持的分块策略: {strategy_type}")

        chunks = strategy.chunk(text, strategy_config)
        return self._apply_constraints(chunks, strategy_config)

    def preview(
        self, text: str, strategy_config: dict[str, Any], limit: int = 10
    ) -> dict[str, Any]:
        """分块预览

        Args:
            text: 输入文本
            strategy_config: 分块策略配置
            limit: 返回的分块数量

        Returns:
            {"total_chunks": int, "preview": [Chunk, ...]}
        """
        chunks = self.chunk(text, strategy_config)
        return {
            "total_chunks": len(chunks),
            "preview": chunks[:limit],
        }

    def _apply_constraints(
        self, chunks: list[Chunk], config: dict[str, Any]
    ) -> list[Chunk]:
        """应用分块约束（min/max chunk_size）"""
        min_size = config.get("min_chunk_size", 100)
        max_size = config.get("max_chunk_size", 4096)

        result = []
        merged = None

        for chunk in chunks:
            if len(chunk.content) < min_size:
                # 太短，合并到下一个
                if merged:
                    merged.content += " " + chunk.content
                    merged.token_count = _estimate_tokens(merged.content)
                else:
                    merged = chunk
            else:
                if merged:
                    # 之前的短块与当前块合并
                    chunk.content = merged.content + " " + chunk.content
                    chunk.token_count = _estimate_tokens(chunk.content)
                    merged = None

                # 截断过长的块
                if len(chunk.content) > max_size:
                    chunk.content = chunk.content[:max_size]
                    chunk.token_count = _estimate_tokens(chunk.content)

                result.append(chunk)

        # 处理最后的短块
        if merged and result:
            last = result[-1]
            last.content += " " + merged.content
            last.token_count = _estimate_tokens(last.content)
        elif merged:
            result.append(merged)

        return result
