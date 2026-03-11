from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class DocumentMetadata(BaseModel):
    title: str
    category: str = "Uncategorized"
    total_pages: int = 0

class DocumentRecord(BaseModel):
    file_hash: str
    file_name: str
    upload_date: datetime = Field(default_factory=datetime.now)
    ref_doc_ids: List[str] = Field(default_factory=list) # 对应 LlamaIndex 的 ref_doc_id
    metadata: DocumentMetadata
    status: str = "indexed"

class DocumentStore(BaseModel):
    docs: Dict[str, DocumentRecord] = Field(default_factory=dict) # Key: file_hash
