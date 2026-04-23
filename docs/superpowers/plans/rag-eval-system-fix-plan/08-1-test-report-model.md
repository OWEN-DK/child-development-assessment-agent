# 08-1 TestReport 模型详细实现方案
**所属模块**：数据模型增强
**文件路径**：`backend/src/models/rag_eval/test_report.py`
---
## 一、ORM模型完整代码
```python
from sqlalchemy import Column, UUID, ForeignKey, JSON, Float, DateTime, String, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from src.models.base import Base
class TestReport(Base):
    __tablename__ = "rag_test_reports"
    __table_args__ = {"comment": "RAG测试报告表"}
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID (UUID字符串，MySQL 5.7兼容)")
    test_run_id = Column(String(36), nullable=False, index=True, comment="关联测试运行ID (逻辑关联，无外键)")
    overall_score = Column(Float, nullable=False, comment="综合评分0-100")
    layer1_result = Column(JSON, nullable=False, comment="Layer1规则引擎校验结果")
    layer2_result = Column(JSON, nullable=False, comment="Layer2历史对比校验结果")
    layer3_result = Column(JSON, nullable=False, comment="Layer3 LLM诊断结果")
    layer4_result = Column(JSON, nullable=False, comment="Layer4数据质量校验结果")
    layer5_result = Column(JSON, nullable=False, comment="Layer5检索链路校验结果")
    layer6_result = Column(JSON, nullable=False, comment="Layer6验证保障结果")
    tuning_suggestions = Column(JSON, nullable=False, comment="调优建议列表，去重合并后结果")
    status = Column(String(32), nullable=False, default="completed", comment="报告状态：completed/failed")
    error_msg = Column(String(500), comment="错误信息")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment="创建时间")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), comment="更新时间")
    # 关联测试运行（无外键约束，弱关联）
    @property
    def test_run(self):
        from backend.models.rag_eval.test_run import TestRun
        return TestRun.query.get(self.test_run_id)
```
---
## 二、Pydantic Schema定义
**文件路径**：`backend/src/schemas/rag_eval/test_report.py`
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Optional
class TuningSuggestion(BaseModel):
    """调优建议结构"""
    id: str = Field(description="建议唯一ID")
    type: str = Field(description="建议类型：config/prompt/data")
    level: str = Field(description="优先级：high/medium/low")
    current_value: Dict = Field(description="当前值")
    suggested_value: Dict = Field(description="建议值")
    reason: str = Field(description="建议原因")
    impact_analysis: Dict = Field(description="影响分析：{scope: 影响范围, expected_improvement: 预期提升, risk: 风险}")
    layer: str = Field(description="所属校验层：layer1/layer2/layer3/layer4/layer5/layer6")
class TestReportBase(BaseModel):
    test_run_id: str = Field(description="关联测试运行ID")
    overall_score: float = Field(ge=0, le=100, description="综合评分0-100")
    layer1_result: Dict = Field(description="Layer1校验结果")
    layer2_result: Dict = Field(description="Layer2校验结果")
    layer3_result: Dict = Field(description="Layer3校验结果")
    layer4_result: Dict = Field(description="Layer4校验结果")
    layer5_result: Dict = Field(description="Layer5校验结果")
    layer6_result: Dict = Field(description="Layer6校验结果")
    tuning_suggestions: List[TuningSuggestion] = Field(description="调优建议列表")
class TestReportCreate(TestReportBase):
    """创建报告入参"""
    status: Optional[str] = "completed"
    error_msg: Optional[str] = None
class TestReportResponse(TestReportBase):
    """报告返回结构"""
    id: str
    status: str
    error_msg: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
```
---
## 三、API接口实现
**文件路径**：`backend/src/api/rag_eval/report.py`
```python
from fastapi import APIRouter, Depends
from typing import List, Optional
from src.schemas.rag_eval import TestReportResponse, TestReportCreate
from src.service.rag_eval.report_service import ReportService
from src.core.exceptions import AppException
from src.utils.response import APIResponse

router = APIRouter(prefix="/reports", tags=["RAG评估报告"])

@router.get("", description="分页查询报告列表")
async def list_reports(
    test_run_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    service: ReportService = Depends()
):
    result = await service.list_reports(test_run_id, page, page_size)
    return APIResponse.success(result)

@router.get("/{report_id}", description="获取报告详情")
async def get_report(report_id: str, service: ReportService = Depends()):
    report = await service.get_report(report_id)
    if not report:
        raise AppException(status_code=404, code=40401, error_code="REPORT_NOT_FOUND", message="报告不存在")
    return APIResponse.success(report)

@router.post("", description="创建报告（内部调用）")
async def create_report(
    params: TestReportCreate,
    service: ReportService = Depends()
):
    result = await service.create_report(params)
    return APIResponse.success(result)

@router.delete("/{report_id}", description="删除报告")
async def delete_report(report_id: str, service: ReportService = Depends()):
    await service.delete_report(report_id)
    return APIResponse.success(message="删除成功")
```
---
## 四、Service层实现
**文件路径**：`backend/src/service/rag_eval/report_service.py`
```python
from fastapi import Depends
from typing import List, Optional
from sqlalchemy import desc
from src.models.rag_eval.test_report import TestReport
from src.schemas.rag_eval import TestReportCreate
from src.core.db.session import get_db
from src.core.exceptions import AppException
class ReportService:
    def __init__(self, db=Depends(get_db)):
        self.db = db
    async def list_reports(self, test_run_id: Optional[str], page: int, page_size: int) -> List[TestReport]:
        """分页查询报告列表"""
        query = self.db.query(TestReport)
        if test_run_id:
            query = query.filter(TestReport.test_run_id == test_run_id)
        offset = (page - 1) * page_size
        return query.order_by(desc(TestReport.created_at)).offset(offset).limit(page_size).all()
    async def get_report(self, report_id: str) -> Optional[TestReport]:
        """获取报告详情"""
        return self.db.query(TestReport).filter(TestReport.id == report_id).first()
    async def create_report(self, params: TestReportCreate) -> TestReport:
        """创建报告"""
        report = TestReport(**params.model_dump())
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report
    async def delete_report(self, report_id: str) -> None:
        """删除报告"""
        report = await self.get_report(report_id)
        if report:
            self.db.delete(report)
            self.db.commit()
```
---
## 五、DDL语句
**文件路径**：`.ai/full_init_script_mysql57.sql`
```sql
-- RAG测试报告表
CREATE TABLE `rag_test_reports` (
  `id` VARCHAR(36) NOT NULL COMMENT '主键ID (UUID字符串)',
  `test_run_id` VARCHAR(36) NOT NULL COMMENT '关联测试运行ID (逻辑关联，无外键)',
  `overall_score` FLOAT NOT NULL COMMENT '综合评分0-100',
  `layer1_result` JSON NOT NULL COMMENT 'Layer1规则引擎校验结果',
  `layer2_result` JSON NOT NULL COMMENT 'Layer2历史对比校验结果',
  `layer3_result` JSON NOT NULL COMMENT 'Layer3 LLM诊断结果',
  `layer4_result` JSON NOT NULL COMMENT 'Layer4数据质量校验结果',
  `layer5_result` JSON NOT NULL COMMENT 'Layer5检索链路校验结果',
  `layer6_result` JSON NOT NULL COMMENT 'Layer6验证保障结果',
  `tuning_suggestions` JSON NOT NULL COMMENT '调优建议列表',
  `status` VARCHAR(32) NOT NULL DEFAULT 'completed' COMMENT '报告状态',
  `error_msg` VARCHAR(500) DEFAULT NULL COMMENT '错误信息',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_test_run_id` (`test_run_id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RAG测试报告表';
```
---
## 六、集成点
在测试运行完成后的流程中添加报告生成调用：
**文件路径**：`backend/src/service/rag_test/test_run_service.py`
```python
from src.core.rag.validation.engine import ValidationEngine
async def complete_test_run(test_run_id: str):
    # 现有逻辑：聚合测试结果、计算指标...
    
    # 新增：触发6层校验，生成报告
    engine = ValidationEngine()
    await engine.generate_report(test_run_id)
    
    # 现有逻辑：发送完成通知...
```
---
**验收标准**：
✅ ORM模型字段完整，符合需求定义
✅ Pydantic Schema类型校验正确
✅ API接口CRUD功能正常
✅ DDL脚本可正常执行，无外键约束
✅ 集成到测试完成流程，自动生成报告
