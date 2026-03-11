import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from typing import List, Optional
import os
import warnings
from llama_index.core.schema import Document

# Suppress ebooklib warnings
warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")

class PDFParser:
    @staticmethod
    def parse(file_path: str) -> List[Document]:
        """
        Parse PDF file using PyMuPDF.
        Returns a list of Documents, one per page.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        doc = fitz.open(file_path)
        documents = []
        
        file_name = os.path.basename(file_path)
        
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if not text.strip():
                continue
                
            metadata = {
                "file_name": file_name,
                "page_label": str(page_num + 1),
                "total_pages": len(doc)
            }
            
            documents.append(Document(text=text, metadata=metadata))
            
        doc.close()
        return documents

class EPUBParser:
    @staticmethod
    def parse(file_path: str) -> List[Document]:
        """
        Parse EPUB file using EbookLib.
        Returns a list of Documents, one per chapter/item.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        book = epub.read_epub(file_path)
        documents = []
        file_name = os.path.basename(file_path)
        
        # Iterate through items
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                content = item.get_content()
                soup = BeautifulSoup(content, 'html.parser')
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
                    "page_label": item.get_name()
                }
                
                documents.append(Document(text=text, metadata=metadata))
                
        return documents

def get_parser(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return PDFParser
    elif ext == ".epub":
        return EPUBParser
    else:
        raise ValueError(f"Unsupported file format: {ext}")
