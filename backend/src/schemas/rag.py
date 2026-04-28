"""RAG 知识库模块模型

包含 RAG 相关的 Pydantic 模型：
- DocumentMetadata: 文档元数据
- DocumentRecord: 文档记录
- DocumentStore: 文档存储
- SynonymExpansionResult: 同义词扩展结果
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """文档元数据"""

    title: str
    category: str = "Uncategorized"
    total_pages: int = 0
    chapter_count: Optional[int] = None


class DocumentRecord(BaseModel):
    """文档记录"""

    id: str = ""
    file_hash: str
    file_name: str
    file_type: str = ""
    upload_date: datetime = Field(default_factory=datetime.now)
    ref_doc_ids: List[str] = Field(default_factory=list)
    metadata: DocumentMetadata
    status: str = "indexed"
    progress: float = 0.0


class DocumentStore(BaseModel):
    """文档存储"""

    docs: Dict[str, DocumentRecord] = Field(default_factory=dict)


class SynonymExpansionResult(BaseModel):
    """同义词扩展结果"""

    synonyms: List[str] = Field(default_factory=list)
