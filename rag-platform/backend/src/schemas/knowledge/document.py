"""文档相关实体类"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ParseStatus(str, Enum):
    """解析状态"""
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    ERROR = "error"


class DocAccessLevel(str, Enum):
    """文档权限级别"""
    INHERIT = "inherit"
    RESTRICTED = "restricted"


# ── 请求实体 ──────────────────────────────────────────

class UpdateDocAclReq(BaseModel):
    """更新文档 ACL 请求"""
    access_level: DocAccessLevel = Field(..., description="权限级别")
    doc_acl: Optional[list[str]] = Field(default=None, description="文档 ACL 角色列表（restricted 时必填）")


# ── 响应实体 ──────────────────────────────────────────

class DocumentSummary(BaseModel):
    """文档摘要"""
    id: str
    kb_id: str
    filename: str
    file_type: str
    file_size: int
    page_count: Optional[int] = None
    md5_hash: str
    parse_status: ParseStatus
    error_message: Optional[str] = None
    access_level: DocAccessLevel = DocAccessLevel.INHERIT
    owner_id: str
    chunk_count: int = 0
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ChunkPreviewItem(BaseModel):
    """分块预览项"""
    chunk_index: int
    content: str
    char_count: int
    token_estimate: int


class DocumentDetail(BaseModel):
    """文档详情"""
    id: str
    kb_id: str
    tenant_id: str
    filename: str
    file_type: str
    file_size: int
    page_count: Optional[int] = None
    md5_hash: str
    parse_status: ParseStatus
    error_message: Optional[str] = None
    text_content: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    access_level: DocAccessLevel = DocAccessLevel.INHERIT
    doc_acl: Optional[list[str]] = None
    owner_id: str
    chunk_count: int = 0
    uploaded_at: datetime
    chunk_preview: list[ChunkPreviewItem] = Field(default_factory=list, description="前 10 块预览")

    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    """文档列表"""
    items: list[DocumentSummary]
    total: int


class BatchUploadResult(BaseModel):
    """批量上传结果"""
    created: list[DocumentSummary] = Field(default_factory=list, description="新创建的文档")
    duplicates: list[DocumentSummary] = Field(default_factory=list, description="重复的文档（MD5 匹配）")
    errors: list[dict[str, str]] = Field(default_factory=list, description="上传失败的文件")
    total_uploaded: int = 0
    total_duplicates: int = 0
    total_errors: int = 0
