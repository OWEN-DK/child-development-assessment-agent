"""文档解析器

从 backend/src/core/parsers.py 继承，移除业务配置引用。
通过构造函数注入 LLM 配置，支持 PDF/TXT/EPUB 解析。
"""
import os
import re
import tempfile
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from http import HTTPStatus
from typing import Any, Optional

import fitz  # PyMuPDF
from bs4 import BeautifulSoup

from src.utils.logger import logger

warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")


class PDFParseError(Exception):
    """PDF 解析失败异常"""
    pass


class PDFCorruptedError(PDFParseError):
    """PDF 文件损坏异常"""
    pass


class ParserServiceError(PDFParseError):
    """解析服务不可用异常"""
    pass


class PDFParser:
    """PDF 文本提取解析器（PyMuPDF）"""

    @staticmethod
    def parse(file_path: str, progress_callback=None) -> list[dict]:
        """解析 PDF 文件，按书签或页面分割

        Returns:
            [{"text": str, "metadata": dict}, ...]
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        doc = fitz.open(file_path)
        try:
            documents = []
            file_name = os.path.basename(file_path)
            total_pages = len(doc)

            toc = doc.get_toc()
            valid_toc = [item for item in toc if 1 <= item[2] <= total_pages]

            if valid_toc:
                logger.info(f"PDF 有 {len(valid_toc)} 个书签，按书签结构分割")
                processed_toc = []
                level_path = []

                for i, (level, title, start_page) in enumerate(valid_toc):
                    end_page = total_pages
                    for j in range(i + 1, len(valid_toc)):
                        next_level, _, next_start_page = valid_toc[j]
                        if next_level <= level:
                            end_page = next_start_page - 1
                            break
                    end_page = max(start_page, min(end_page, total_pages))

                    while len(level_path) >= level:
                        level_path.pop()
                    level_path.append(title)
                    full_chapter_title = "-".join(level_path)

                    processed_toc.append({
                        "level": level,
                        "title": title,
                        "full_chapter_title": full_chapter_title,
                        "start_page": start_page,
                        "end_page": end_page,
                    })

                for toc_idx, toc_item in enumerate(processed_toc):
                    combined_text = ""
                    for page_num in range(toc_item["start_page"] - 1, toc_item["end_page"]):
                        page = doc[page_num]
                        text = page.get_text()
                        if text.strip():
                            combined_text += text + "\n\n"

                    if len(combined_text.strip()) < 10:
                        continue

                    documents.append({
                        "text": combined_text.strip(),
                        "metadata": {
                            "file_name": file_name,
                            "chapter_title": toc_item["full_chapter_title"],
                            "section_title": toc_item["title"],
                            "page_label": f"{toc_item['start_page']}-{toc_item['end_page']}",
                            "total_pages": total_pages,
                            "toc_level": toc_item["level"],
                        },
                    })

                    if progress_callback:
                        progress_callback(toc_item["end_page"], total_pages)
            else:
                logger.info("PDF 无书签，按页面分割")
                for page_num, page in enumerate(doc):
                    text = page.get_text()
                    if len(text.strip()) < 10:
                        continue

                    documents.append({
                        "text": text,
                        "metadata": {
                            "file_name": file_name,
                            "page_label": str(page_num + 1),
                            "total_pages": total_pages,
                        },
                    })

                    if progress_callback:
                        progress_callback(page_num + 1, total_pages)

            return documents
        finally:
            doc.close()


class EPUBParser:
    """EPUB 解析器"""

    @staticmethod
    def parse(file_path: str, progress_callback=None) -> list[dict]:
        """解析 EPUB 文件"""
        import ebooklib
        from ebooklib import epub

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        book = epub.read_epub(file_path)
        try:
            documents = []
            file_name = os.path.basename(file_path)

            href_item_map = {}
            document_items = []
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    document_items.append(item)
                    href_item_map[item.get_name()] = item

            total_pages = len(document_items)
            toc = book.toc
            processed_toc = []

            if toc:
                logger.info(f"EPUB 有 TOC，按层级结构处理")
                level_path = []
                for node in toc:
                    EPUBParser._traverse_toc(node, 1, level_path, processed_toc)

                for idx, toc_item in enumerate(processed_toc):
                    text = EPUBParser._get_item_content(href_item_map, toc_item["href"])
                    if not text or not text.strip():
                        continue

                    documents.append({
                        "text": text.strip(),
                        "metadata": {
                            "file_name": file_name,
                            "chapter_title": toc_item["full_chapter_title"],
                            "section_title": toc_item["title"],
                            "page_label": toc_item["href"],
                            "toc_level": toc_item["level"],
                            "total_pages": total_pages,
                        },
                    })

                    if progress_callback:
                        progress_callback(idx + 1, len(processed_toc))
            else:
                logger.info("EPUB 无 TOC，按文档项处理")
                for idx, item in enumerate(document_items):
                    content = item.get_content()
                    soup = BeautifulSoup(content, "html.parser")
                    text = soup.get_text(separator="\n")

                    if not text.strip():
                        continue

                    title = ""
                    if soup.h1:
                        title = soup.h1.get_text().strip()
                    elif soup.h2:
                        title = soup.h2.get_text().strip()

                    documents.append({
                        "text": text,
                        "metadata": {
                            "file_name": file_name,
                            "chapter_title": title or item.get_name(),
                            "page_label": item.get_name(),
                            "total_pages": total_pages,
                        },
                    })

                    if progress_callback:
                        progress_callback(idx + 1, len(document_items))

            return documents
        finally:
            if hasattr(book, 'close'):
                book.close()

    @staticmethod
    def _traverse_toc(toc_node, level: int, level_path: list, processed_toc: list):
        """递归遍历 TOC 节点"""
        from ebooklib import epub

        if isinstance(toc_node, epub.Link):
            title = toc_node.title.strip()
            href = toc_node.href.split("#")[0]
            while len(level_path) >= level:
                level_path.pop()
            level_path.append(title)
            processed_toc.append({
                "level": level,
                "title": title,
                "full_chapter_title": "-".join(level_path),
                "href": href,
            })
        elif isinstance(toc_node, tuple) and len(toc_node) == 2:
            link, children = toc_node
            title = link.title.strip()
            href = link.href.split("#")[0]
            while len(level_path) >= level:
                level_path.pop()
            level_path.append(title)
            processed_toc.append({
                "level": level,
                "title": title,
                "full_chapter_title": "-".join(level_path),
                "href": href,
            })
            for child in children:
                EPUBParser._traverse_toc(child, level + 1, level_path, processed_toc)

    @staticmethod
    def _get_item_content(href_item_map: dict, item_href: str) -> Optional[str]:
        """根据 href 获取 item 的文本内容"""
        item = href_item_map.get(item_href)
        if not item:
            return None
        content = item.get_content()
        soup = BeautifulSoup(content, "html.parser")
        return soup.get_text(separator="\n")


class TXTParser:
    """纯文本解析器（自动编码检测）"""

    @staticmethod
    def parse(file_path: str) -> str:
        """读取 TXT 文件内容"""
        encoding = TXTParser._detect_encoding(file_path)
        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            return f.read()

    @staticmethod
    def _detect_encoding(file_path: str) -> str:
        """自动检测文件编码"""
        try:
            import chardet
            with open(file_path, "rb") as f:
                raw = f.read(10000)
            result = chardet.detect(raw)
            return result.get("encoding") or "utf-8"
        except Exception:
            return "utf-8"


def get_parser(file_path: str):
    """根据文件类型获取解析器

    Args:
        file_path: 文件路径或扩展名（如 '.txt'）

    Returns:
        解析器实例
    """
    if file_path.startswith("."):
        ext = file_path.lower()
    else:
        ext = os.path.splitext(file_path)[1].lower()

    parsers = {
        ".pdf": PDFParser,
        ".epub": EPUBParser,
        ".txt": TXTParser,
        ".md": TXTParser,
        ".markdown": TXTParser,
    }

    parser_class = parsers.get(ext)
    if not parser_class:
        raise ValueError(f"不支持的文件格式: {ext}。支持: {', '.join(parsers.keys())}")

    return parser_class()
