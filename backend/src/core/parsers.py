import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from typing import List, Optional, Tuple, Dict, Any
import os
import re
import warnings
import tempfile
from http import HTTPStatus
import dashscope
from concurrent.futures import ThreadPoolExecutor, as_completed
from llama_index.core.schema import Document
from src.config import settings
from src.utils.logger import logger


class PDFParseError(Exception):
    """PDF解析失败异常"""
    pass


class PDFCorruptedError(PDFParseError):
    """PDF文件损坏异常"""
    pass


class ParserServiceError(PDFParseError):
    """解析服务不可用异常"""
    pass


class ParserType:
    """解析器类型枚举"""
    TEXT = "text"      # 传统文本提取
    OCR = "ocr"        # OCR解析（TBD，当前使用VL作为OCR替代）
    VLM = "vlm"        # VLM解析

# Suppress ebooklib warnings
warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")


class PDFParser:
    @staticmethod
    def parse(file_path: str, progress_callback=None) -> List[Document]:
        """
        Parse PDF file using PyMuPDF.
        If PDF has bookmarks (TOC), split by bookmarks first, otherwise split by page.
        Returns a list of Documents.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        doc = fitz.open(file_path)
        documents = []
        file_name = os.path.basename(file_path)
        total_pages = len(doc)

        # 首先尝试获取PDF书签（目录）
        toc = doc.get_toc()
        # 过滤无效的TOC条目（页码不在有效范围内）
        valid_toc = [item for item in toc if 1 <= item[2] <= total_pages]

        if valid_toc:
            logger.info(
                f"PDF has {len(valid_toc)} bookmarks, splitting by bookmark structure"
            )

            # 处理TOC，为每个书签计算结束页码并构建完整层级标题
            processed_toc = []
            # 记录各级别的父标题路径，用于拼接完整标题
            level_path = []

            for i, (level, title, start_page) in enumerate(valid_toc):
                # 查找下一个同级或更高级别的书签，作为当前书签的结束边界
                end_page = total_pages
                for j in range(i + 1, len(valid_toc)):
                    next_level, _, next_start_page = valid_toc[j]
                    if next_level <= level:
                        end_page = next_start_page - 1
                        break

                # 确保结束页码不小于开始页码且不超过总页数
                end_page = max(start_page, min(end_page, total_pages))

                # 构建完整层级标题路径
                # 先截断到当前层级的父级
                while len(level_path) >= level:
                    level_path.pop()
                # 添加当前标题到路径
                level_path.append(title)
                # 拼接完整标题
                full_chapter_title = "-".join(level_path)

                processed_toc.append(
                    {
                        "level": level,
                        "title": title,
                        "full_chapter_title": full_chapter_title,
                        "start_page": start_page,
                        "end_page": end_page,
                    }
                )

            # 按书签分割文档
            for toc_idx, toc_item in enumerate(processed_toc):
                # 合并当前书签范围内的所有页面文本
                combined_text = ""
                for page_num in range(toc_item["start_page"] - 1, toc_item["end_page"]):
                    page = doc[page_num]
                    text = page.get_text()
                    if text.strip():
                        combined_text += text + "\n\n"

                if len(combined_text.strip()) < 10:
                    continue

                metadata = {
                    "file_name": file_name,
                    "chapter_title": toc_item["full_chapter_title"],  # 完整层级标题
                    "section_title": toc_item["title"],  # 当前小节标题
                    "page_label": f"{toc_item['start_page']}-{toc_item['end_page']}",
                    "total_pages": total_pages,
                    "toc_level": toc_item["level"],
                    "start_page": toc_item["start_page"],
                    "end_page": toc_item["end_page"],
                }

                documents.append(
                    Document(text=combined_text.strip(), metadata=metadata)
                )

                # 报告进度
                if progress_callback:
                    current_page = toc_item["end_page"]
                    progress_callback(current_page, total_pages)

            logger.info(f"Split PDF into {len(documents)} sections based on bookmarks")
        else:
            # 没有书签，按原有逻辑逐页分割
            logger.info("PDF has no bookmarks, splitting by page")
            for page_num, page in enumerate(doc):
                text = page.get_text()
                # 降低过滤阈值，保留更多内容，即使是少量文本
                if len(text.strip()) < 10:
                    continue

                metadata = {
                    "file_name": file_name,
                    "page_label": str(page_num + 1),
                    "total_pages": total_pages,
                }

                documents.append(Document(text=text, metadata=metadata))

                # 报告进度
                if progress_callback:
                    progress_callback(page_num + 1, total_pages)

        doc.close()
        return documents


class PDFVLParser:
    @staticmethod
    def _parse_single_page(args: Tuple[fitz.Page, int, int, str]) -> Optional[Document]:
        """
        解析单个PDF页面，用于多线程并行处理
        """
        page, page_num, total_pages, file_name = args
        # Render page to image
        # Matrix(1.0, 1.0) 最快速度，满足OCR基础需求
        mat = fitz.Matrix(1.0, 1.0)
        pix = page.get_pixmap(matrix=mat)

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
            pix.save(tmp_img.name)
            tmp_img_path = tmp_img.name

        try:
            # Call Qwen-VL
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": f"file://{tmp_img_path}"},
                        {
                            "text": "请提取这张图片中的所有文字内容，保持原有的段落结构。只输出提取的文字，不要输出任何其他解释或描述。"
                        },
                    ],
                }
            ]

            response = dashscope.MultiModalConversation.call(
                model=settings.model_vl_parsing,
                messages=messages,
                api_key=settings.dashscope_api_key,
            )

            text = ""
            if response.status_code == HTTPStatus.OK:
                if response.output and response.output.choices:
                    content_list = response.output.choices[0].message.content
                    # content can be a list or string depending on model version, usually list for multimodal
                    if isinstance(content_list, list):
                        text = "".join(
                            [item["text"] for item in content_list if "text" in item]
                        )
                    elif isinstance(content_list, str):
                        text = content_list
            else:
                logger.error(
                    f"VL Parsing failed for page {page_num}: {response.message}"
                )

            if not text.strip():
                logger.warning(f"Page {page_num} yielded empty text via VL.")
                return None

            metadata = {
                "file_name": file_name,
                "page_label": str(page_num + 1),
                "total_pages": total_pages,
                "parsing_method": "qwen-vl",
            }

            logger.info(f"Parsed page {page_num + 1}/{total_pages} via VL.")
            return Document(text=text, metadata=metadata)

        except Exception as e:
            logger.error(f"Error parsing page {page_num} with VL: {e}")
            return None
        finally:
            if os.path.exists(tmp_img_path):
                os.remove(tmp_img_path)

    @staticmethod
    def parse(file_path: str, max_workers: int = None, progress_callback=None) -> List[Document]:
        """
        Parse PDF file using Qwen-VL for OCR/understanding (for scanned PDFs).
        使用多线程并行解析，大幅提升速度。
        Returns a list of Documents, one per page.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not settings.dashscope_api_key:
            raise ValueError("DashScope API Key is required for VL parsing.")

        doc = fitz.open(file_path)
        file_name = os.path.basename(file_path)
        total_pages = len(doc)
        documents = []

        # 如果没有指定线程数，使用配置文件中的值
        if max_workers is None:
            max_workers = settings.rag_vl_max_workers

        logger.info(
            f"Starting VL parsing for {file_name} with {total_pages} pages using {settings.model_vl_parsing}, {max_workers} threads"
        )

        # 准备页面参数列表
        page_args = [
            (doc[page_num], page_num, total_pages, file_name)
            for page_num in range(total_pages)
        ]

        # 多线程并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(PDFVLParser._parse_single_page, args)
                for args in page_args
            ]

            completed = 0
            for future in as_completed(futures):
                result = future.result()
                if result:
                    documents.append(result)
                
                completed += 1
                # 报告进度
                if progress_callback:
                    progress_callback(completed, total_pages)

        doc.close()

        # 按页码排序，保证输出顺序正确
        documents.sort(key=lambda x: int(x.metadata["page_label"]))
        logger.info(f"VL parsing completed, {len(documents)} pages parsed successfully")

        return documents


class EPUBParser:
    @staticmethod
    def _get_item_content(book, item_href: str) -> Optional[str]:
        """根据href获取item的文本内容"""
        for item in book.get_items():
            if (
                item.get_type() == ebooklib.ITEM_DOCUMENT
                and item.get_name() == item_href
            ):
                content = item.get_content()
                soup = BeautifulSoup(content, "html.parser")
                return soup.get_text(separator="\n")
        return None

    @staticmethod
    def _traverse_toc(
        toc_node,
        level: int,
        level_path: list,
        processed_toc: list,
        book,
        total_pages: int,
    ):
        """递归遍历TOC节点，构建层级结构"""
        if isinstance(toc_node, epub.Link):
            # 叶子节点（章节链接）
            title = toc_node.title.strip()
            href = toc_node.href.split("#")[0]  # 去除锚点部分

            # 构建完整层级标题
            while len(level_path) >= level:
                level_path.pop()
            level_path.append(title)
            full_chapter_title = "-".join(level_path)

            processed_toc.append(
                {
                    "level": level,
                    "title": title,
                    "full_chapter_title": full_chapter_title,
                    "href": href,
                }
            )
        elif isinstance(toc_node, tuple) and len(toc_node) == 2:
            # 父节点（包含子节点的章节）: (Link, [children])
            link, children = toc_node
            title = link.title.strip()
            href = link.href.split("#")[0]

            # 构建完整层级标题
            while len(level_path) >= level:
                level_path.pop()
            level_path.append(title)
            full_chapter_title = "-".join(level_path)

            processed_toc.append(
                {
                    "level": level,
                    "title": title,
                    "full_chapter_title": full_chapter_title,
                    "href": href,
                }
            )

            # 递归处理子节点
            for child in children:
                EPUBParser._traverse_toc(
                    child, level + 1, level_path, processed_toc, book, total_pages
                )

    @staticmethod
    def parse(file_path: str, progress_callback=None) -> List[Document]:
        """
        Parse EPUB file using EbookLib.
        If EPUB has TOC, split by TOC hierarchy with full path titles, otherwise split by document item.
        Returns a list of Documents.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        book = epub.read_epub(file_path)
        documents = []
        file_name = os.path.basename(file_path)
        total_pages = len(
            [
                item
                for item in book.get_items()
                if item.get_type() == ebooklib.ITEM_DOCUMENT
            ]
        )

        # 首先尝试获取EPUB的TOC
        toc = book.toc
        processed_toc = []

        if toc:
            logger.info(f"EPUB has TOC, processing with hierarchical structure")
            level_path = []
            # 递归遍历TOC构建层级结构
            for node in toc:
                EPUBParser._traverse_toc(
                    node, 1, level_path, processed_toc, book, total_pages
                )

            # 为每个TOC条目获取内容并创建Document
            for idx, toc_item in enumerate(processed_toc):
                text = EPUBParser._get_item_content(book, toc_item["href"])
                if not text or not text.strip():
                    continue

                metadata = {
                    "file_name": file_name,
                    "chapter_title": toc_item["full_chapter_title"],  # 完整层级标题
                    "section_title": toc_item["title"],  # 当前小节标题
                    "page_label": toc_item["href"],
                    "toc_level": toc_item["level"],
                    "total_pages": total_pages,
                }

                documents.append(Document(text=text.strip(), metadata=metadata))
                
                # 报告进度
                if progress_callback:
                    progress_callback(idx + 1, len(processed_toc))

            logger.info(f"Processed {len(documents)} chapters from EPUB TOC")
        else:
            # 没有TOC，按原有逻辑处理每个document item
            logger.info("EPUB has no TOC, processing by document items")
            document_items = [item for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT]
            
            for idx, item in enumerate(document_items):
                content = item.get_content()
                soup = BeautifulSoup(content, "html.parser")
                text = soup.get_text(separator="\n")

                if not text.strip():
                    continue

                # Try to extract chapter title
                title = ""
                if soup.h1:
                    title = soup.h1.get_text().strip()
                elif soup.h2:
                    title = soup.h2.get_text().strip()
                elif soup.title:
                    title = soup.title.get_text().strip()

                metadata = {
                    "file_name": file_name,
                    "chapter_title": title if title else item.get_name(),
                    "page_label": item.get_name(),
                    "total_pages": total_pages,
                }

                documents.append(Document(text=text, metadata=metadata))
                
                # 报告进度
                if progress_callback:
                    progress_callback(idx + 1, len(document_items))

        return documents


class PDFParserV2:
    """
    改进的PDF解析器，支持三级降级机制：
    1. 优先使用VLM解析（保留格式、图片内容理解）
    2. VLM失败时使用OCR解析（当前使用VL作为OCR替代）
    3. OCR失败时使用传统文本提取
    """
    
    def __init__(
        self, 
        fallback_order: List[str] = None, 
        min_content_length: int = 100,
        max_workers: int = None
    ):
        """
        初始化PDF解析器
        :param fallback_order: 降级顺序，默认是 [ParserType.VLM, ParserType.TEXT]
        :param min_content_length: 最小有效内容长度，低于此长度视为解析失败
        :param max_workers: 最大并行解析线程数
        """
        self.fallback_order = fallback_order or [ParserType.VLM, ParserType.TEXT]
        self.min_content_length = min_content_length
        self.max_workers = max_workers or settings.rag_vl_max_workers
        
        # 解析器映射
        self.parsers = {
            ParserType.VLM: self._parse_with_vlm,
            ParserType.TEXT: self._parse_with_text
        }
    
    def _clean_content(self, content: str) -> str:
        """清理解析内容，去除多余空白和特殊字符"""
        if not content:
            return ""
        # 去除多余空白字符
        content = re.sub(r"\s+", " ", content)
        # 去除不可见字符
        content = re.sub(r"[\x00-\x1F\x7F]", "", content)
        return content.strip()
    
    def _is_content_valid(self, documents: List[Document]) -> bool:
        """校验解析内容是否有效"""
        if not documents:
            return False
        
        total_length = sum(len(doc.text) for doc in documents)
        avg_length = total_length / len(documents) if documents else 0
        
        # 平均内容长度过短
        if avg_length < self.min_content_length:
            return False
        
        # 检查乱码比例（可配置）
        sample_text = " ".join([doc.text[:100] for doc in documents[:10]])
        if not sample_text:
            return False
            
        non_ascii_ratio = sum(1 for c in sample_text if ord(c) > 127) / len(sample_text)
        if non_ascii_ratio > 0.8 and not any("\u4e00" <= c <= "\u9fff" for c in sample_text):
            # 非ASCII字符比例过高且没有中文字符，可能是乱码
            return False
            
        return True
    
    def _parse_with_text(self, file_path: str, progress_callback=None) -> List[Document]:
        """使用传统文本提取解析PDF"""
        try:
            return PDFParser.parse(file_path, progress_callback=progress_callback)
        except Exception as e:
            if "corrupted" in str(e).lower() or "invalid pdf" in str(e).lower():
                raise PDFCorruptedError(f"PDF file corrupted: {e}") from e
            raise PDFParseError(f"Text extraction failed: {e}") from e
    
    def _parse_with_vlm(self, file_path: str, progress_callback=None) -> List[Document]:
        """使用VLM解析PDF"""
        if not settings.dashscope_api_key:
            raise ParserServiceError("DashScope API Key is required for VLM parsing.")
            
        try:
            return PDFVLParser.parse(file_path, max_workers=self.max_workers, progress_callback=progress_callback)
        except (TimeoutError, ConnectionError) as e:
            raise ParserServiceError(f"VLM service unavailable: {e}") from e
        except Exception as e:
            if "corrupted" in str(e).lower() or "invalid pdf" in str(e).lower():
                raise PDFCorruptedError(f"PDF file corrupted: {e}") from e
            raise PDFParseError(f"VLM parse failed: {e}") from e
    
    def parse(self, file_path: str, progress_callback=None) -> List[Document]:
        """
        三级降级解析PDF
        :param file_path: PDF文件路径
        :param progress_callback: 进度回调函数，接收(current_page, total_pages)参数
        :return: 解析后的文档列表
        :raises PDFParseError: 所有解析方式都失败时抛出
        :raises PDFCorruptedError: PDF文件本身损坏时抛出
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        if not file_path.lower().endswith(".pdf"):
            raise ValueError(f"File is not a PDF: {file_path}")
        
        last_error = None
        file_name = os.path.basename(file_path)
        
        for parser_type in self.fallback_order:
            parser_func = self.parsers.get(parser_type)
            if not parser_func:
                logger.warning(f"Unknown parser type: {parser_type}, skipping")
                continue
            
            try:
                logger.info(f"Parsing PDF {file_name} with {parser_type} parser")
                
                documents = parser_func(file_path, progress_callback=progress_callback)
                
                # 校验解析结果质量
                if self._is_content_valid(documents):
                    total_length = sum(len(doc.text) for doc in documents)
                    avg_length = total_length / len(documents) if documents else 0
                    logger.info(f"PDF parsed successfully with {parser_type} parser, "
                              f"{len(documents)} pages, avg content length: {avg_length:.0f}")
                    return documents
                else:
                    logger.warning(f"{parser_type} parser returned invalid content, falling back")
            
            except PDFCorruptedError as e:
                # PDF本身损坏，直接抛出，不需要继续降级
                logger.error(f"PDF file {file_name} is corrupted: {e}")
                raise
            except ParserServiceError as e:
                # 解析服务不可用，记录错误继续降级
                logger.warning(f"{parser_type} service unavailable: {e}, falling back")
                last_error = e
            except Exception as e:
                logger.warning(f"{parser_type} parse failed: {e}, falling back")
                last_error = e
        
        # 所有解析方式都失败
        error_msg = f"All PDF parsers failed for {file_name}"
        if last_error:
            error_msg += f": {last_error}"
        
        logger.error(error_msg)
        raise PDFParseError(error_msg)


def get_parser(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return PDFParserV2()
    elif ext == ".epub":
        return EPUBParser
    else:
        raise ValueError(f"Unsupported file format: {ext}")
