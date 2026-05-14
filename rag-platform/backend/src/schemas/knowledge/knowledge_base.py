"""知识库相关实体类"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class VectorBackend(str, Enum):
    """向量后端类型"""
    CHROMA = "chroma"
    ELASTICSEARCH = "elasticsearch"
    MILVUS = "milvus"


class KnowledgeBaseStatus(str, Enum):
    """知识库状态"""
    READY = "ready"
    REBUILDING = "rebuilding"
    INDEXING = "indexing"
    ERROR = "error"


class KnowledgeBaseVisibility(str, Enum):
    """知识库可见性"""
    PUBLIC = "public"
    ROLE_SCOPED = "role_scoped"
    PRIVATE = "private"


class ChunkType(str, Enum):
    """分块策略类型"""
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    RECURSIVE = "recursive"


class SimilarityMetric(str, Enum):
    """相似度度量"""
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"


# ── 请求实体 ──────────────────────────────────────────

class ChunkStrategyReq(BaseModel):
    """分块策略请求"""
    type: ChunkType = Field(default=ChunkType.FIXED_SIZE, description="分块策略类型")
    chunk_size: int = Field(default=512, ge=128, le=4096, description="分块大小（字符数）")
    overlap: int = Field(default=50, ge=0, le=500, description="重叠大小（字符数）")
    separator: str = Field(default="\n\n", description="分隔符")
    min_chunk_size: int = Field(default=100, ge=50, description="最小分块大小")
    max_chunk_size: int = Field(default=4096, le=8192, description="最大分块大小")


class EmbeddingConfigReq(BaseModel):
    """Embedding 配置请求"""
    model: str = Field(default="text-embedding-v3", description="Embedding 模型名称")
    provider: str = Field(default="dashscope", description="模型提供商：dashscope/openai/anthropic")
    dimension: int = Field(default=1024, ge=64, le=4096, description="向量维度")
    batch_size: int = Field(default=64, ge=1, le=512, description="批量大小")
    similarity_metric: SimilarityMetric = Field(default=SimilarityMetric.COSINE, description="相似度度量")


class CreateKnowledgeBaseReq(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=255, description="知识库名称")
    description: Optional[str] = Field(default=None, max_length=500, description="描述")
    vector_backend: VectorBackend = Field(default=VectorBackend.CHROMA, description="向量后端")
    chunk_strategy: Optional[ChunkStrategyReq] = Field(default=None, description="分块策略")
    embedding_config: Optional[EmbeddingConfigReq] = Field(default=None, description="Embedding 配置")
    visibility: KnowledgeBaseVisibility = Field(default=KnowledgeBaseVisibility.PUBLIC, description="可见性")
    visible_roles: Optional[list[str]] = Field(default=None, description="可见角色列表")


class UpdateKnowledgeBaseReq(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="知识库名称")
    description: Optional[str] = Field(default=None, max_length=500, description="描述")
    visibility: Optional[KnowledgeBaseVisibility] = Field(default=None, description="可见性")
    visible_roles: Optional[list[str]] = Field(default=None, description="可见角色列表")


class UpdateChunkStrategyReq(BaseModel):
    """更新分块策略请求"""
    chunk_strategy: ChunkStrategyReq = Field(..., description="分块策略")


class UpdateEmbeddingConfigReq(BaseModel):
    """更新 Embedding 配置请求"""
    embedding_config: EmbeddingConfigReq = Field(..., description="Embedding 配置")


class MigrateBackendReq(BaseModel):
    """迁移向量后端请求"""
    target_backend: VectorBackend = Field(..., description="目标向量后端")


# ── 响应实体 ──────────────────────────────────────────

class KnowledgeBaseSummary(BaseModel):
    """知识库摘要"""
    id: str
    name: str
    description: Optional[str] = None
    vector_backend: VectorBackend
    visibility: KnowledgeBaseVisibility
    status: KnowledgeBaseStatus
    document_count: int = 0
    chunk_count: int = 0
    storage_size_bytes: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeBaseDetail(BaseModel):
    """知识库详情"""
    id: str
    tenant_id: str
    name: str
    description: Optional[str] = None
    vector_backend: VectorBackend
    chunk_strategy: Optional[dict[str, Any]] = None
    embedding_config: Optional[dict[str, Any]] = None
    visibility: KnowledgeBaseVisibility
    visible_roles: Optional[list[str]] = None
    owner_id: str
    status: KnowledgeBaseStatus
    document_count: int = 0
    chunk_count: int = 0
    storage_size_bytes: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeBaseList(BaseModel):
    """知识库列表"""
    items: list[KnowledgeBaseSummary]
    total: int


class RebuildTriggeredResponse(BaseModel):
    """重建触发响应"""
    rebuild_task_id: str
    kb_id: str
    trigger: str
    status: str


class PipelineReference(BaseModel):
    """管道引用"""
    pipeline_id: str
    pipeline_name: str
    version_number: int


class KbDeletionConflict(BaseModel):
    """知识库删除冲突"""
    message: str
    pipelines: list[PipelineReference]
