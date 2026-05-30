"""EPUB 章节解析 -- 从 EPUB 提取结构化章节列表。

放置位置: backend/src/core/knowledge_qa/neo4j/chapter_parser.py
依赖: pip install ebooklib beautifulsoup4
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


@dataclass
class Chapter:
    """一个章节的数据结构。"""
    id: str
    title: str
    raw_html: str
    markdown: str = ""
    order: int = 0
    token_count: int = 0


@dataclass
class ChapterParseResult:
    """EPUB 解析结果。"""
    book_id: str
    book_title: str
    chapters: list[Chapter] = field(default_factory=list)
    total_tokens: int = 0


def parse_epub(file_path: str, book_id: str) -> ChapterParseResult:
    """解析 EPUB 文件，返回按章节组织的结构化结果。

    Args:
        file_path: EPUB 文件路径
        book_id: 书籍唯一标识

    Returns:
        ChapterParseResult 包含所有章节
    """
    book = epub.read_epub(file_path)
    title_meta = book.get_metadata("DC", "title")
    book_title = title_meta[0][0] if title_meta else "Unknown"

    result = ChapterParseResult(book_id=book_id, book_title=book_title)
    chapter_idx = 0

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        html = item.get_content().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        heading = soup.find(["h1", "h2", "h3"])
        title = heading.get_text(strip=True) if heading else f"Chapter {chapter_idx + 1}"

        markdown = _html_to_markdown(soup)
        if not markdown.strip():
            continue

        token_count = _estimate_tokens(markdown)

        chapter = Chapter(
            id=f"{book_id}_ch{chapter_idx:03d}",
            title=title,
            raw_html=html,
            markdown=markdown,
            order=chapter_idx,
            token_count=token_count,
        )
        result.chapters.append(chapter)
        result.total_tokens += token_count
        chapter_idx += 1

    # 超长章节拆分
    # 不再拆分超长章节——qwen3.7-max 上下文 128K，完整章节直接传入效果更好

    return result


def _html_to_markdown(soup: BeautifulSoup) -> str:
    """HTML -> 简化 Markdown。"""
    lines = []
    for elem in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        tag = elem.name
        text = elem.get_text(strip=True)
        if not text:
            continue
        if tag.startswith("h"):
            level = int(tag[1])
            lines.append(f"{'#' * level} {text}")
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag == "blockquote":
            lines.append(f"> {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def _estimate_tokens(text: str) -> int:
    """粗略 token 估算（中文约 1.5 char/token）。"""
    return max(1, len(text) * 2 // 3)


def _split_long_chapters(chapters: list[Chapter], max_tokens: int) -> list[Chapter]:
    """[已废弃] 超长章节按段落边界拆分。

    废弃原因：qwen3.7-max 上下文 128K，拆分会破坏跨段落上下文完整性，
    导致概念提取不完整。保留函数供未来需要时参考。
    """
    result = []
    for ch in chapters:
        if ch.token_count <= max_tokens:
            result.append(ch)
            continue

        paragraphs = ch.markdown.split("\n\n")
        current_text = ""
        current_tokens = 0
        part_idx = 0

        for para in paragraphs:
            para_tokens = _estimate_tokens(para)
            if current_tokens + para_tokens > max_tokens and current_text:
                result.append(Chapter(
                    id=f"{ch.id}_p{part_idx}",
                    title=f"{ch.title} (Part {part_idx + 1})",
                    raw_html=ch.raw_html,
                    markdown=current_text.strip(),
                    order=ch.order,
                    token_count=current_tokens,
                ))
                part_idx += 1
                current_text = ""
                current_tokens = 0
            current_text += para + "\n\n"
            current_tokens += para_tokens

        if current_text.strip():
            result.append(Chapter(
                id=f"{ch.id}_p{part_idx}",
                title=f"{ch.title} (Part {part_idx + 1})" if part_idx > 0 else ch.title,
                raw_html=ch.raw_html,
                markdown=current_text.strip(),
                order=ch.order,
                token_count=current_tokens,
            ))

    return result
