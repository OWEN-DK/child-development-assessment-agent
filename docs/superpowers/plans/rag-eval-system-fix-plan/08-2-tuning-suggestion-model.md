# 08-2 TuningSuggestionRecord 模型详细实现方案
**所属模块**：数据模型增强
**文件路径**：`backend/src/models/rag_eval/tuning_suggestion.py`
---
## 一、ORM模型完整代码
```python
from sqlalchemy import Column, UUID, ForeignKey, JSON, Text, DateTime, Enum, String
from datetime import datetime, timezone
import uuid
from src.models.base import Base
class TuningSuggestionRecord(Base):
    __tablename__ = "rag_tuning_suggestions"
    __table_args__ = {"comment": "RAG调优建议记录表"}
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID (UUID字符串，MySQL 5.7兼容)")
    report_id = Column(String(36), index=True, comment="关联报告ID (逻辑关联，无外键)")
    suggestion_id = Column(String(64), nullable=False, index=True, comment="建议唯一标识")
    type = Column(Enum("config", "prompt", "data", name="suggestion_type"), nullable=False, comment="建议类型")
    level = Column(Enum("high", "medium", "low", name="suggestion_level"), nullable=False, comment="优先级")
    current_value = Column(JSON, nullable=False, comment="当前值")
    suggested_value = Column(JSON, nullable=False, comment="建议值")
    reason = Column(Text, nullable=False, comment="建议原因")
    impact_analysis = Column(JSON, nullable=False, comment="影响分析")
    status = Column(Enum("pending", "applied", "ignored", name="suggestion_status"), default="pending", comment="状态")
    applied_at = Column(DateTime, comment="应用时间")
    applied_by = Column(String(64), comment="操作人")
    ignore_reason = Column(Text, comment="忽略原因")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment="创建时间")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), comment="更新时间")
```
---
## 二、Pydantic Schema定义
**文件路径**：`backend/src/schemas/rag_eval/tuning_suggestion.py`
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict
class TuningSuggestionBase(BaseModel):
    suggestion_id: str = Field(description="建议唯一标识")
    type: str = Field(description="建议类型：config/prompt/data")
    level: str = Field(description="优先级：high/medium/low")
    current_value: Dict = Field(description="当前值")
    suggested_value: Dict = Field(description="建议值")
    reason: str = Field(description="建议原因")
    impact_analysis: Dict = Field(description="影响分析")
class TuningSuggestionCreate(TuningSuggestionBase):
    """创建建议入参"""
    report_id: str
class TuningSuggestionUpdateStatus(BaseModel):
    """更新状态入参"""
    status: str = Field(description="状态：applied/ignored")
    ignore_reason: Optional[str] = Field(description="忽略原因，status=ignored时必填")
class TuningSuggestionResponse(TuningSuggestionBase):
    """建议返回结构"""
    id: str
    report_id: str
    status: str
    applied_at: Optional[datetime]
    applied_by: Optional[str]
    ignore_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
```
---
## 三、API接口实现
**文件路径**：`backend/src/api/rag_eval/suggestion.py`
```python
from fastapi import APIRouter, Depends
from typing import List, Optional
from src.schemas.rag_eval import TuningSuggestionResponse, TuningSuggestionUpdateStatus
from src.service.rag_eval.suggestion_service import SuggestionService
from src.core.exceptions import AppException
from src.utils.response import APIResponse

router = APIRouter(prefix="/suggestions", tags=["RAG调优建议"])

@router.get("/report/{report_id}", description="获取报告下的所有建议")
async def list_suggestions_by_report(
    report_id: str,
    status: Optional[str] = None,
    type: Optional[str] = None,
    service: SuggestionService = Depends()
):
    result = await service.list_suggestions(report_id, status, type)
    return APIResponse.success(result)

@router.get("/{suggestion_id}", description="获取建议详情")
async def get_suggestion(suggestion_id: str, service: SuggestionService = Depends()):
    suggestion = await service.get_suggestion(suggestion_id)
    if not suggestion:
        raise AppException(status_code=404, code=40402, error_code="SUGGESTION_NOT_FOUND", message="建议不存在")
    return APIResponse.success(suggestion)

@router.put("/{suggestion_id}/status", description="更新建议状态（应用/忽略）")
async def update_suggestion_status(
    suggestion_id: str,
    params: TuningSuggestionUpdateStatus,
    service: SuggestionService = Depends()
):
    if params.status == "ignored" and not params.ignore_reason:
        raise AppException(status_code=400, code=40001, error_code="IGNORE_REASON_REQUIRED", message="忽略原因不能为空")
    suggestion = await service.update_status(suggestion_id, params)
    if not suggestion:
        raise AppException(status_code=404, code=40402, error_code="SUGGESTION_NOT_FOUND", message="建议不存在")
    return APIResponse.success(suggestion)

@router.post("/{suggestion_id}/apply", description="应用建议（自动修改配置/提示词）")
async def apply_suggestion(
    suggestion_id: str,
    service: SuggestionService = Depends()
):
    result = await service.apply_suggestion(suggestion_id)
    return APIResponse.success(result, message="应用成功")
```
---
## 四、Service层实现
**文件路径**：`backend/src/service/rag_eval/suggestion_service.py`
```python
from fastapi import Depends
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import desc
from src.models.rag_eval.tuning_suggestion import TuningSuggestionRecord
from src.schemas.rag_eval import TuningSuggestionCreate, TuningSuggestionUpdateStatus
from src.service.config.config_service import ConfigService
from src.service.prompt.prompt_service import PromptService
from src.core.db.session import get_db
from src.core.exceptions import AppException
class SuggestionService:
    def __init__(self, db=Depends(get_db)):
        self.db = db
        self.config_service = ConfigService(db)
        self.prompt_service = PromptService(db)
    async def list_suggestions(self, report_id: str, status: Optional[str], type: Optional[str]) -> List[TuningSuggestionRecord]:
        """分页查询建议列表"""
        query = self.db.query(TuningSuggestionRecord).filter(TuningSuggestionRecord.report_id == report_id)
        if status:
            query = query.filter(TuningSuggestionRecord.status == status)
        if type:
            query = query.filter(TuningSuggestionRecord.type == type)
        return query.order_by(desc(TuningSuggestionRecord.created_at)).all()
    async def get_suggestion(self, suggestion_id: str) -> Optional[TuningSuggestionRecord]:
        """获取建议详情"""
        return self.db.query(TuningSuggestionRecord).filter(TuningSuggestionRecord.id == suggestion_id).first()
    async def create_suggestions(self, report_id: str, suggestions: List[TuningSuggestionCreate]) -> None:
        """批量创建建议（生成报告时调用）"""
        for item in suggestions:
            suggestion = TuningSuggestionRecord(**item.model_dump(), report_id=report_id)
            self.db.add(suggestion)
        self.db.commit()
    async def update_status(self, suggestion_id: str, params: TuningSuggestionUpdateStatus) -> Optional[TuningSuggestionRecord]:
        """更新建议状态"""
        suggestion = await self.get_suggestion(suggestion_id)
        if not suggestion:
            return None
        suggestion.status = params.status
        if params.status == "applied":
            suggestion.applied_at = datetime.now(timezone.utc)
            suggestion.applied_by = "system"  # 后续接入用户体系后修改为实际用户
        if params.status == "ignored":
            suggestion.ignore_reason = params.ignore_reason
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion
    async def apply_suggestion(self, suggestion_id: str) -> dict:
        """应用建议"""
        suggestion = await self.get_suggestion(suggestion_id)
        if not suggestion:
            raise AppException(status_code=404, code=40402, error_code="SUGGESTION_NOT_FOUND", message="建议不存在")
        if suggestion.status != "pending":
            raise AppException(status_code=400, code=40002, error_code="SUGGESTION_NOT_PENDING", message="建议状态不是待处理，无法应用")
        # 按类型应用建议
        result = {}
        if suggestion.type == "config":
            # 应用配置修改
            config_params = suggestion.suggested_value
            result = await self.config_service.batch_update(config_params)
        elif suggestion.type == "prompt":
            # 应用提示词修改
            prompt_params = suggestion.suggested_value
            result = await self.prompt_service.update_prompt(prompt_params["key"], prompt_params)
        elif suggestion.type == "data":
            # 数据类建议无法自动应用，返回提示
            raise AppException(status_code=400, code=40003, error_code="DATA_SUGGESTION_MANUAL_ONLY", message="数据类建议需要手动处理，无法自动应用")
        # 更新状态为已应用
        await self.update_status(suggestion_id, TuningSuggestionUpdateStatus(status="applied"))
        return result
```
---
## 五、DDL语句
**文件路径**：`.ai/full_init_script_mysql57.sql`
```sql
-- RAG调优建议记录表
CREATE TABLE `rag_tuning_suggestions` (
  `id` VARCHAR(36) NOT NULL COMMENT '主键ID (UUID字符串)',
  `report_id` VARCHAR(36) DEFAULT NULL COMMENT '关联报告ID (逻辑关联，无外键)',
  `suggestion_id` VARCHAR(64) NOT NULL COMMENT '建议唯一标识',
  `type` ENUM('config','prompt','data') NOT NULL COMMENT '建议类型',
  `level` ENUM('high','medium','low') NOT NULL COMMENT '优先级',
  `current_value` JSON NOT NULL COMMENT '当前值',
  `suggested_value` JSON NOT NULL COMMENT '建议值',
  `reason` TEXT NOT NULL COMMENT '建议原因',
  `impact_analysis` JSON NOT NULL COMMENT '影响分析',
  `status` ENUM('pending','applied','ignored') NOT NULL DEFAULT 'pending' COMMENT '状态',
  `applied_at` DATETIME DEFAULT NULL COMMENT '应用时间',
  `applied_by` VARCHAR(64) DEFAULT NULL COMMENT '操作人',
  `ignore_reason` TEXT DEFAULT NULL COMMENT '忽略原因',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_report_id` (`report_id`),
  KEY `idx_suggestion_id` (`suggestion_id`),
  KEY `idx_status` (`status`),
  KEY `idx_type` (`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RAG调优建议记录表';
```
---
**验收标准**：
✅ ORM模型枚举字段使用SQLAlchemy Enum类，未使用字符串
✅ 支持批量创建建议，与报告生成流程集成
✅ 应用建议功能可以自动修改配置/提示词，数据类建议提示手动处理
✅ 状态更新包含操作审计信息
✅ DDL枚举定义与ORM一致，无外键约束
