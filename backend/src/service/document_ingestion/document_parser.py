import hashlib
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from llama_index.core.schema import Document

from src.config import settings
from src.core.parsers import PDFParser, PDFVLParser, get_parser
from src.utils.logger import logger


class DocumentParser:
    @staticmethod
    def get_actual_total_pages(file_path: str) -> Optional[int]:
        if file_path.lower().endswith(".pdf"):
            import fitz
            with fitz.open(file_path) as pdf_doc:
                return len(pdf_doc)
        return None

    @staticmethod
    def parse_document(file_path: str, progress_callback=None) -> list:
        parser_cls = get_parser(file_path)
        documents = parser_cls.parse(file_path, progress_callback=progress_callback)
        return documents, parser_cls

    @staticmethod
    def check_vl_parsing(file_path: str, documents: list, parser_cls) -> list:
        if parser_cls != PDFParser or not documents:
            return documents
        total_pages = documents[0].metadata.get("total_pages", len(documents))
        total_text_length = sum(len(doc.text) for doc in documents)
        avg_text_length = total_text_length / len(documents) if len(documents) > 0 else 0
        extraction_rate = len(documents) / total_pages if total_pages > 0 else 0
        is_scanned_pdf = (
            extraction_rate < settings.rag_ocr_extraction_rate_threshold
            or avg_text_length < settings.rag_ocr_min_avg_length_threshold
        )
        if is_scanned_pdf:
            logger.warning(f"PDF extraction rate low ({extraction_rate:.0%}, avg length {avg_text_length:.0f}). Trying VL parsing...")
            try:
                vl_documents = PDFVLParser.parse(file_path)
                if vl_documents:
                    vl_total_length = sum(len(doc.text) for doc in vl_documents)
                    vl_avg_length = vl_total_length / len(vl_documents) if vl_documents else 0
                    if vl_avg_length > settings.rag_ocr_min_avg_length_threshold or vl_avg_length > avg_text_length * 2:
                        logger.info(f"VL parsing succeeded, extracted {len(vl_documents)} pages, avg length: {vl_avg_length:.0f}")
                        return vl_documents
                    else:
                        logger.warning(f"VL parsing result quality too low, falling back")
                else:
                    logger.warning("VL parsing returned empty results")
            except Exception as e:
                logger.error(f"VL Parsing failed: {str(e)}, falling back")
        logger.info(f"Using extraction results: {len(documents)} pages, avg length: {avg_text_length:.0f}")
        if avg_text_length < 10:
            logger.warning(f"Extraction quality is very low (avg length: {avg_text_length:.0f})")
        return documents

    @staticmethod
    def calculate_chapter_count(file_path: str, documents: list) -> Optional[int]:
        is_epub = file_path.lower().endswith(".epub")
        is_pdf_with_bookmarks = file_path.lower().endswith(".pdf") and documents and "toc_level" in documents[0].metadata
        if is_epub or is_pdf_with_bookmarks:
            return len(documents)
        return None

    @staticmethod
    def clean_documents(documents: list, file_name: str) -> list:
        from src.utils.text_cleaner import clean_document_text
        cleaned_documents = []
        for doc in documents:
            cleaned_text = clean_document_text(doc.text)
            if not cleaned_text:
                logger.debug(f"Skipping empty document from {file_name}, metadata: {doc.metadata}")
                continue
            new_doc = Document(text=cleaned_text, metadata=doc.metadata.copy())
            new_doc.metadata["file_name"] = file_name
            if "page_label" not in new_doc.metadata:
                new_doc.metadata["page_label"] = new_doc.metadata.get("chapter_title", "Unknown")
            cleaned_documents.append(new_doc)
        return cleaned_documents

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
