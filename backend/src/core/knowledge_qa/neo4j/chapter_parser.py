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

    对于整本书内容打包在单个 HTML 文档中的 EPUB（如"学习如何学习"），
    会按内部的 <h1>/<h2> 标题自动拆分为多个章节。

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

        # 检测 item 内是否有多个 h1 标题，需要按标题拆分
        sub_chapters = _split_by_headings(soup, html, book_id, chapter_idx)
        if sub_chapters is not None:
            for ch in sub_chapters:
                if not ch.markdown.strip():
                    continue
                ch.order = chapter_idx
                ch.token_count = _estimate_tokens(ch.markdown)
                result.chapters.append(ch)
                result.total_tokens += ch.token_count
                chapter_idx += 1
            continue

        # 常规逻辑：一个 item = 一个章节
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

    return result


def _split_by_headings(
    soup: BeautifulSoup, raw_html: str, book_id: str, start_idx: int
) -> list[Chapter] | None:
    """当单个 HTML 文档内包含多个 h1 标题时，按标题拆分为子章节。

    Returns:
        拆分后的 Chapter 列表，如果不需拆分则返回 None。
    """
    h1_tags = soup.find_all("h1")
    if len(h1_tags) <= 1:
        return None

    chapters: list[Chapter] = []
    for i, h1 in enumerate(h1_tags):
        # 收集该标题之后、下一个 h1 之前的所有兄弟元素内容
        elems = _collect_until_next_heading(h1)
        markdown = _elems_to_markdown(elems)
        title = h1.get_text(strip=True)
        # 前置标题内容（如"名言"等）归入第一个章节
        if i == 0 and not markdown.strip():
            continue

        chapters.append(Chapter(
            id=f"{book_id}_ch{(start_idx + len(chapters)):03d}",
            title=title,
            raw_html=raw_html,
            markdown=markdown,
        ))

    return chapters if chapters else None


def _collect_until_next_heading(h1_tag) -> list:
    """从 h1 标签开始，收集其后的兄弟元素直到下一个 h1 为止。"""
    elems = []
    for sibling in h1_tag.next_siblings:
        if sibling.name == "h1":
            break
        if hasattr(sibling, "name") and sibling.name in (
            "h1", "h2", "h3", "h4", "p", "li", "blockquote",
        ):
            elems.append(sibling)
        elif hasattr(sibling, "find_all"):
            # 嵌套容器（如 <div>），提取内部内容元素
            for child in sibling.find_all(
                ["h2", "h3", "h4", "p", "li", "blockquote"]
            ):
                elems.append(child)
    return elems


def _elems_to_markdown(elems: list) -> str:
    """将一组 HTML 元素转换为简化 Markdown。"""
    lines = []
    for elem in elems:
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


class ChapterParser:
    """通过 file_hash 查询数据库获取 EPUB 文件路径并解析章节。"""

    async def parse_by_hash(self, file_hash: str) -> ChapterParseResult:
        """根据 file_hash 解析对应的 EPUB 文件。

        Args:
            file_hash: 源文件的哈希标识

        Returns:
            ChapterParseResult 包含所有章节

        Raises:
            FileNotFoundError: 找不到对应的文档记录或文件路径
        """
        from src.core.database import async_session_factory
        from src.models.document import SourceDocument
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(SourceDocument).where(SourceDocument.file_hash == file_hash)
            )
            doc = result.scalar_one_or_none()

        if not doc:
            raise FileNotFoundError(f"未找到 file_hash={file_hash} 对应的文档记录")

        file_path = doc.file_path
        book_id = doc.id or file_hash

        return parse_epub(file_path, book_id)
