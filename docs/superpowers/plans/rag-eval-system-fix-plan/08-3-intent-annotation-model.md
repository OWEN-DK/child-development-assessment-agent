# 08-3 IntentAnnotation 模型详细实现方案
**所属模块**：数据模型增强
**文件路径**：`backend/src/models/rag_eval/intent_annotation.py`
---
## 一、ORM模型完整代码
```python
from sqlalchemy import Column, UUID, String, JSON, Float, DateTime, Text
from datetime import datetime, timezone
import uuid
from src.models.base import Base
class IntentAnnotation(Base):
    __tablename__ = "rag_intent_annotations"
    __table_args__ = {"comment": "RAG查询意图标注表"}
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID (UUID字符串，MySQL 5.7兼容)")
    query = Column(String(500), nullable=False, index=True, comment="用户查询内容")
    intent = Column(String(100), nullable=False, comment="意图分类")
    intent_confidence = Column(Float, comment="模型识别置信度0-1")
    expected_document_ids = Column(JSON, nullable=False, comment="预期匹配的文档ID列表")
    expected_chunk_ids = Column(JSON, comment="预期匹配的片段ID列表")
    expected_answer = Column(Text, comment="预期回答内容")
    quality_score = Column(Float, comment="标注质量评分0-1")
    annotated_by = Column(String(64), comment="标注人")
    source = Column(String(32), default="manual", comment="来源：manual/auto/test")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment="创建时间")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), comment="更新时间")
```
---
## 二、Pydantic Schema定义
**文件路径**：`backend/src/schemas/rag_eval/intent_annotation.py`
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
class IntentAnnotationBase(BaseModel):
    query: str = Field(max_length=500, description="用户查询内容")
    intent: str = Field(max_length=100, description="意图分类")
    intent_confidence: Optional[float] = Field(ge=0, le=1, description="模型识别置信度")
    expected_document_ids: List[str] = Field(description="预期匹配的文档ID列表")
    expected_chunk_ids: Optional[List[str]] = Field(description="预期匹配的片段ID列表")
    expected_answer: Optional[str] = Field(description="预期回答内容")
    quality_score: Optional[float] = Field(ge=0, le=1, description="标注质量评分")
    source: Optional[str] = Field(default="manual", description="来源")
    remark: Optional[str] = Field(description="备注")
class IntentAnnotationCreate(IntentAnnotationBase):
    """创建标注入参"""
    pass
class IntentAnnotationUpdate(IntentAnnotationBase):
    """更新标注入参"""
    query: Optional[str] = None
    intent: Optional[str] = None
    expected_document_ids: Optional[List[str]] = None
class IntentAnnotationResponse(IntentAnnotationBase):
    """标注返回结构"""
    id: str
    annotated_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
```
---
## 三、API接口实现
**文件路径**：`backend/src/api/rag_eval/annotation.py`
```python
from fastapi import APIRouter, Depends
from typing import List, Optional
from src.schemas.rag_eval import IntentAnnotationResponse, IntentAnnotationCreate, IntentAnnotationUpdate
from src.service.rag_eval.annotation_service import AnnotationService
from src.core.exceptions import AppException
from src.utils.response import APIResponse

router = APIRouter(prefix="/intent-annotations", tags=["RAG意图标注"])

@router.get("", description="分页查询标注列表")
async def list_annotations(
    intent: Optional[str] = None,
    query: Optional[str] = None,
    source: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    service: AnnotationService = Depends()
):
    result = await service.list_annotations(intent, query, source, page, page_size)
    return APIResponse.success(result)

@router.get("/{annotation_id}", description="获取标注详情")
async def get_annotation(annotation_id: str, service: AnnotationService = Depends()):
    annotation = await service.get_annotation(annotation_id)
    if not annotation:
        raise AppException(status_code=404, code=40403, error_code="ANNOTATION_NOT_FOUND", message="标注不存在")
    return APIResponse.success(annotation)

@router.post("", description="创建标注")
async def create_annotation(
    params: IntentAnnotationCreate,
    service: AnnotationService = Depends()
):
    result = await service.create_annotation(params)
    return APIResponse.success(result)

@router.put("/{annotation_id}", description="更新标注")
async def update_annotation(
    annotation_id: str,
    params: IntentAnnotationUpdate,
    service: AnnotationService = Depends()
):
    annotation = await service.update_annotation(annotation_id, params)
    if not annotation:
        raise AppException(status_code=404, code=40403, error_code="ANNOTATION_NOT_FOUND", message="标注不存在")
    return APIResponse.success(annotation)

@router.delete("/{annotation_id}", description="删除标注")
async def delete_annotation(annotation_id: str, service: AnnotationService = Depends()):
    await service.delete_annotation(annotation_id)
    return APIResponse.success(message="删除成功")

@router.post("/batch-import", description="批量导入标注")
async def batch_import_annotations(
    annotations: List[IntentAnnotationCreate],
    service: AnnotationService = Depends()
):
    count = await service.batch_import(annotations)
    return APIResponse.success({"count": count}, message=f"导入成功，共导入{count}条数据")
```
---
## 四、Service层实现
**文件路径**：`backend/src/service/rag_eval/annotation_service.py`
```python
from fastapi import Depends
from typing import List, Optional
from sqlalchemy import desc
from src.models.rag_eval.intent_annotation import IntentAnnotation
from src.schemas.rag_eval import IntentAnnotationCreate, IntentAnnotationUpdate
from src.core.db.session import get_db
from src.core.exceptions import AppException
class AnnotationService:
    def __init__(self, db=Depends(get_db)):
        self.db = db
    async def list_annotations(
        self,
        intent: Optional[str],
        query: Optional[str],
        source: Optional[str],
        page: int,
        page_size: int
    ) -> List[IntentAnnotation]:
        """分页查询标注列表"""
        query_obj = self.db.query(IntentAnnotation)
        if intent:
            query_obj = query_obj.filter(IntentAnnotation.intent == intent)
        if query:
            query_obj = query_obj.filter(IntentAnnotation.query.like(f"%{query}%"))
        if source:
            query_obj = query_obj.filter(IntentAnnotation.source == source)
        offset = (page - 1) * page_size
        return query_obj.order_by(desc(IntentAnnotation.created_at)).offset(offset).limit(page_size).all()
    async def get_annotation(self, annotation_id: str) -> Optional[IntentAnnotation]:
        """获取标注详情"""
        return self.db.query(IntentAnnotation).filter(IntentAnnotation.id == annotation_id).first()
    async def create_annotation(self, params: IntentAnnotationCreate) -> IntentAnnotation:
        """创建标注"""
        annotation = IntentAnnotation(**params.model_dump(), annotated_by="system")  # 后续接入用户体系后修改
        self.db.add(annotation)
        self.db.commit()
        self.db.refresh(annotation)
        return annotation
    async def update_annotation(self, annotation_id: str, params: IntentAnnotationUpdate) -> Optional[IntentAnnotation]:
        """更新标注"""
        annotation = await self.get_annotation(annotation_id)
        if not annotation:
            return None
        update_data = params.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(annotation, key, value)
        self.db.commit()
        self.db.refresh(annotation)
        return annotation
    async def delete_annotation(self, annotation_id: str) -> None:
        """删除标注"""
        annotation = await self.get_annotation(annotation_id)
        if annotation:
            self.db.delete(annotation)
            self.db.commit()
    async def batch_import(self, annotations: List[IntentAnnotationCreate]) -> int:
        """批量导入标注"""
        count = 0
        for item in annotations:
            annotation = IntentAnnotation(**item.model_dump(), annotated_by="system")
            self.db.add(annotation)
            count += 1
        self.db.commit()
        return count
    async def get_all_annotations(self) -> List[IntentAnnotation]:
        """获取所有标注（用于Layer5校验）"""
        return self.db.query(IntentAnnotation).all()
```
---
## 五、DDL语句
**文件路径**：`.ai/full_init_script_mysql57.sql`
```sql
-- RAG查询意图标注表
CREATE TABLE `rag_intent_annotations` (
  `id` VARCHAR(36) NOT NULL COMMENT '主键ID (UUID字符串)',
  `query` VARCHAR(500) NOT NULL COMMENT '用户查询内容',
  `intent` VARCHAR(100) NOT NULL COMMENT '意图分类',
  `intent_confidence` FLOAT DEFAULT NULL COMMENT '模型识别置信度0-1',
  `expected_document_ids` JSON NOT NULL COMMENT '预期匹配的文档ID列表',
  `expected_chunk_ids` JSON DEFAULT NULL COMMENT '预期匹配的片段ID列表',
  `expected_answer` TEXT DEFAULT NULL COMMENT '预期回答内容',
  `quality_score` FLOAT DEFAULT NULL COMMENT '标注质量评分0-1',
  `annotated_by` VARCHAR(64) DEFAULT NULL COMMENT '标注人',
  `source` VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT '来源',
  `remark` TEXT DEFAULT NULL COMMENT '备注',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_query` (`query`(100)),
  KEY `idx_intent` (`intent`),
  KEY `idx_source` (`source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RAG查询意图标注表';
```
---
## 六、集成点
在Layer5检索链路校验中调用获取所有标注数据：
**文件路径**：`backend/src/core/rag/validation/layer5_retrieval.py`
```python
from src.service.rag_eval.annotation_service import AnnotationService
class Layer5RetrievalValidator:
    def __init__(self, db):
        self.annotation_service = AnnotationService(db)
    async def validate(self, test_run_id: str):
        annotations = await self.annotation_service.get_all_annotations()
        # 校验逻辑：对比标注数据和实际检索结果
        pass
```
---
**验收标准**：
✅ 支持批量导入标注数据，用于校验检索准确率
✅ 查询接口支持按意图、查询内容、来源筛选
✅ 提供全量查询接口，供校验引擎调用
✅ 字段设计符合意图标注业务需求
✅ DDL无外键约束，符合项目规范
