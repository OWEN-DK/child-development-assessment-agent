from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class DocumentMetadata(BaseModel):
    title: str
    category: str = "Uncategorized"
    total_pages: int = 0
    chapter_count: Optional[int] = None  # 章节数，有结构的文档（EPUB/带书签PDF）才有


class DocumentRecord(BaseModel):
    file_hash: str
    file_name: str
    upload_date: datetime = Field(default_factory=datetime.now)
    ref_doc_ids: List[str] = Field(
        default_factory=list
    )  # 对应 LlamaIndex 的 ref_doc_id
    metadata: DocumentMetadata
    status: str = "indexed"  # pending/processing/indexed/failed
    progress: float = 0.0  # 处理进度 0-100


class DocumentStore(BaseModel):
    docs: Dict[str, DocumentRecord] = Field(default_factory=dict)  # Key: file_hash
