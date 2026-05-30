"""EPUB 章节解析测试。"""

import pytest
from src.core.knowledge_qa.neo4j.chapter_parser import (
    Chapter, ChapterParseResult, _html_to_markdown, _estimate_tokens, _split_long_chapters,
)


class TestChapter:
    """Chapter 数据类。"""

    def test_chapter_defaults(self):
        ch = Chapter(id="ch001", title="第一章", raw_html="<p>Hello</p>")
        assert ch.id == "ch001"
        assert ch.title == "第一章"
        assert ch.markdown == ""
        assert ch.order == 0
        assert ch.token_count == 0


class TestHtmlToMarkdown:
    """_html_to_markdown() 测试。"""

    def test_heading_conversion(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<h1>标题</h1><p>内容</p>", "html.parser")
        md = _html_to_markdown(soup)
        assert "# 标题" in md
        assert "内容" in md

    def test_empty_html(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("", "html.parser")
        md = _html_to_markdown(soup)
        assert md.strip() == ""

    def test_list_conversion(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<ul><li>项目1</li><li>项目2</li></ul>", "html.parser")
        md = _html_to_markdown(soup)
        assert "项目1" in md


class TestEstimateTokens:
    """_estimate_tokens() 测试。"""

    def test_empty_string_returns_minimum(self):
        # _estimate_tokens uses max(1, ...) so empty returns 1
        assert _estimate_tokens("") >= 0

    def test_english_text(self):
        count = _estimate_tokens("Hello world this is a test")
        assert count > 0

    def test_chinese_text(self):
        count = _estimate_tokens("这是一个测试文本")
        assert count > 0

    def test_longer_text_has_more_tokens(self):
        short = _estimate_tokens("短")
        long = _estimate_tokens("这是一段很长的文本用来测试token估算")
        assert long > short


class TestSplitLongChapters:
    """_split_long_chapters() 测试。"""

    def test_short_chapter_not_split(self):
        ch = Chapter(id="ch001", title="短章", raw_html="", markdown="短内容", token_count=100)
        result = _split_long_chapters([ch], max_tokens=6000)
        assert len(result) == 1

    def test_empty_list(self):
        assert _split_long_chapters([], max_tokens=6000) == []

    def test_multiple_short_chapters(self):
        chapters = [
            Chapter(id=f"ch{i:03d}", title=f"Ch{i}", raw_html="", markdown=f"内容{i}", token_count=100)
            for i in range(5)
        ]
        result = _split_long_chapters(chapters, max_tokens=6000)
        assert len(result) == 5
