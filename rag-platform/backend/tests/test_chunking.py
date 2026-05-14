"""分块引擎单元测试"""
import pytest

from src.core.knowledge_base.chunking.strategies import (
    Chunk,
    FixedSizeChunking,
    ParagraphChunking,
    RecursiveChunking,
    SemanticChunking,
    HeadingChunking,
    _estimate_tokens,
)
from src.core.knowledge_base.chunking.engine import ChunkingEngine


class TestEstimateTokens:
    """Token 估算测试"""

    def test_chinese_text(self):
        """中文文本估算"""
        tokens = _estimate_tokens("你好世界")
        assert tokens == int(4 * 1.5)  # 6

    def test_english_text(self):
        """英文文本估算"""
        tokens = _estimate_tokens("hello world")
        assert tokens == int(11 * 1.3)  # 14

    def test_mixed_text(self):
        """混合文本估算"""
        tokens = _estimate_tokens("hello 你好")
        # 6 英文字符 * 1.3 + 2 中文字符 * 1.5
        expected = int(6 * 1.3 + 2 * 1.5)
        assert tokens == expected


class TestFixedSizeChunking:
    """固定大小分块测试"""

    def test_basic_chunking(self):
        """基本分块"""
        strategy = FixedSizeChunking()
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        chunks = strategy.chunk(text, {"chunk_size": 20, "overlap": 5})

        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.content
            assert chunk.token_count > 0

    def test_overlap_preserved(self):
        """重叠区域保留"""
        strategy = FixedSizeChunking()
        text = "A" * 100 + "\n\n" + "B" * 100
        chunks = strategy.chunk(text, {"chunk_size": 80, "overlap": 20})

        if len(chunks) >= 2:
            # 第二个块的开头应包含第一个块末尾的 overlap
            assert chunks[1].content.startswith("A" * 20) or "A" in chunks[1].content[:30]


class TestParagraphChunking:
    """段落分块测试"""

    def test_split_by_paragraph(self):
        """按段落分割"""
        strategy = ParagraphChunking()
        text = "段落一。\n\n段落二。\n\n段落三。"
        chunks = strategy.chunk(text, {"min_sentences_per_chunk": 1, "max_chunk_size": 1000})

        assert len(chunks) >= 1

    def test_short_paragraph_merge(self):
        """短段落合并"""
        strategy = ParagraphChunking()
        text = "短。\n\n这是一个较长的段落，包含足够的内容。"
        chunks = strategy.chunk(text, {"min_sentences_per_chunk": 2, "max_chunk_size": 1000})

        # 短段落应被合并
        assert len(chunks) <= 2


class TestHeadingChunking:
    """标题分块测试"""

    def test_split_by_heading(self):
        """按标题分割"""
        strategy = HeadingChunking()
        text = "# 第一章\n内容一\n\n## 1.1 节\n内容二\n\n# 第二章\n内容三"
        chunks = strategy.chunk(text, {"heading_levels": [1, 2], "max_chunk_size": 1000})

        assert len(chunks) >= 2
        # 检查 heading_path 元数据
        for chunk in chunks:
            assert "heading_path" in chunk.metadata


class TestRecursiveChunking:
    """递归分块测试"""

    def test_respects_max_size(self):
        """遵守最大分块大小"""
        strategy = RecursiveChunking()
        text = "A" * 2000
        chunks = strategy.chunk(text, {
            "separator_priority_list": ["\n\n", "\n", " "],
            "max_chunk_size": 500,
            "min_chunk_size": 50,
        })

        for chunk in chunks:
            assert len(chunk.content) <= 600  # 允许一定误差


class TestChunkingEngine:
    """分块引擎门面测试"""

    def test_select_strategy(self):
        """根据配置选择策略"""
        engine = ChunkingEngine()

        # fixed_size
        chunks = engine.chunk("测试文本。" * 100, {"type": "fixed_size", "chunk_size": 200})
        assert len(chunks) >= 1

    def test_preview(self):
        """预览功能"""
        engine = ChunkingEngine()
        result = engine.preview(
            "测试文本。" * 100,
            {"type": "fixed_size", "chunk_size": 200},
            limit=3,
        )

        assert "total_chunks" in result
        assert "preview" in result
        assert len(result["preview"]) <= 3

    def test_invalid_strategy(self):
        """无效策略抛出异常"""
        engine = ChunkingEngine()
        with pytest.raises(ValueError, match="不支持的分块策略"):
            engine.chunk("text", {"type": "invalid_strategy"})
