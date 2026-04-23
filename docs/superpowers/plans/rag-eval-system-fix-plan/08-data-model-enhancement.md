# 08 - 数据模型增强模块
**优先级**：🟡 P1
**工作量**：20h（2.5 人天）
**依赖**：无
---
## 一、需求背景
现有数据模型缺少需求文档要求的报告、调优建议、意图标注三个核心模型，无法支撑 6 层校验引擎和调优功能的落地。

## 二、核心设计原则

### 2.1 遵循 CLAUDE.md 强制规范

| 规范 | 要求 | 本方案执行 |
|------|------|------------|
| 实体类位置 | Pydantic Schema 必须在 `schemas/` 目录 | ✅ SQLAlchemy ORM 在 `models/`，Pydantic Schema 在 `schemas/rag_eval.py` |
| 外键约束 | 采用弱关联，无外键约束 | ✅ 删除所有 `ForeignKey()`，改用普通 `Column()` + 注释说明逻辑关联 |
| 索引优化 | 高频查询字段必须加索引 | ✅ 补充 `test_run_id`、`report_id`、`query`、`status` 等索引 |
| 类长度限制 | 单类不超过 500 行 | ✅ 每个模型 < 100 行，Schema < 150 行 |

---

## 三、实施内容

### 3.1 新增 TestReport 模型

**文件路径**：`backend/src/models/rag_eval/test_report.py`

```python
"""测试报告模型 - 存储 6 层校验结果和调优建议"""

from sqlalchemy import Column, String, JSON, Float, DateTime, Index
from datetime import datetime
import uuid
from src.models.base import Base


class TestReport(Base):
    """测试报告表（与 rag_test_runs 弱关联）"""
    
    __tablename__ = "rag_test_reports"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="报告 ID (UUID)")
    test_run_id = Column(String(36), nullable=False, comment="测试运行 ID (逻辑关联 rag_test_runs.id)")
    
    # 6 层校验结果
    validation_results = Column(JSON, nullable=False, comment="6 层校验结果 JSON: {layer1: {...}, layer2: {...}, ...}")
    
    # 调优建议
    tuning_suggestions = Column(JSON, nullable=False, comment="调优建议列表: [{type, reason, current_value, suggested_value, impact_analysis, priority}, ...]")
    
    # 综合评分
    overall_score = Column(Float, nullable=False, comment="综合评分 0-100")
    
    # 元数据
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment="生成时间")
    
    # 索引（高频查询字段）
    __table_args__ = (
        Index('idx_test_run_id', 'test_run_id'),  # 按测试运行查询报告
        Index('idx_generated_at', 'generated_at'),  # 按时间范围查询
    )
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(36) | UUID 字符串（MySQL 5.7 兼容性更好） |
| `test_run_id` | String(36) | 逻辑关联，无外键约束 |
| `validation_results` | JSON | 6 层校验结果，结构见下方 |
| `tuning_suggestions` | JSON | 调优建议列表，结构见下方 |
| `overall_score` | Float | 综合评分 0-100 |
| `generated_at` | DateTime | 自动生成时间 |

**validation_results JSON 结构**：
```json
{
  "layer1_rules": {
    "status": "pass",
    "metrics": {"precision_at_5": 0.85, "recall_at_5": 0.72, "f1": 0.78},
    "suggestions": []
  },
  "layer2_history": {
    "status": "warning",
    "regression_detected": true,
    "diff": {"precision_at_5": -0.05},
    "suggestions": [...]
  },
  // ... layer3-6
}
```

**tuning_suggestions JSON 结构**：
```json
[
  {
    "type": "config",
    "reason": "BM25 权重偏低，导致关键词匹配不足",
    "current_value": {"bm25": 0.3, "vector": 0.7},
    "suggested_value": {"bm25": 0.5, "vector": 0.5},
    "impact_analysis": {
      "scope": "影响所有 factual 类型查询",
      "expected_improvement": "precision@5 预计提升 5-8%",
      "risk": "可能降低 conceptual 查询的语义相关性"
    },
    "priority": "high"
  }
]
```

---

### 3.2 新增 TuningSuggestionRecord 模型

**文件路径**：`backend/src/models/rag_eval/tuning_suggestion.py`

```python
"""调优建议记录模型 - 跟踪建议的采纳和执行情况"""

from sqlalchemy import Column, String, JSON, Text, DateTime, Index
from datetime import datetime
import uuid
from src.models.base import Base


class TuningSuggestionRecord(Base):
    """调优建议记录表（与 rag_test_reports 弱关联）"""
    
    __tablename__ = "rag_tuning_suggestions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="建议 ID (UUID)")
    report_id = Column(String(36), nullable=False, comment="报告 ID (逻辑关联 rag_test_reports.id)")
    
    # 建议内容
    suggestion_type = Column(String(50), nullable=False, comment="建议类型: config/prompt/data")
    current_value = Column(JSON, nullable=False, comment="当前值")
    suggested_value = Column(JSON, nullable=False, comment="建议值")
    reason = Column(Text, nullable=False, comment="建议原因")
    impact_analysis = Column(JSON, nullable=False, comment="影响分析: {scope, expected_improvement, risk}")
    
    # 状态跟踪
    status = Column(String(20), nullable=False, default="pending", comment="状态: pending/applied/ignored")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment="创建时间")
    applied_at = Column(DateTime, nullable=True, comment="采纳时间")
    applied_by = Column(String(100), nullable=True, comment="操作人")
    
    # 索引（高频查询字段）
    __table_args__ = (
        Index('idx_report_id', 'report_id'),  # 按报告查询建议
        Index('idx_status', 'status'),  # 按状态筛选
        Index('idx_suggestion_type', 'suggestion_type'),  # 按类型筛选
        Index('idx_created_at', 'created_at'),  # 按时间范围查询
    )
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(36) | UUID 字符串 |
| `report_id` | String(36) | 逻辑关联，无外键约束 |
| `suggestion_type` | String(50) | config（配置）/ prompt（提示词）/ data（数据） |
| `status` | String(20) | pending（待处理）/ applied（已采纳）/ ignored（已忽略） |
| `applied_by` | String(100) | 操作人用户名或邮箱 |

---

### 3.3 新增 IntentAnnotation 模型

**文件路径**：`backend/src/models/rag_eval/intent_annotation.py`

```python
"""意图标注模型 - 用于 Layer 5 检索链路校验的基准数据"""

from sqlalchemy import Column, String, JSON, Float, DateTime, Index
from datetime import datetime
import uuid
from src.models.base import Base


class IntentAnnotation(Base):
    """意图标注表（独立表，无外键关联）"""
    
    __tablename__ = "rag_intent_annotations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="标注 ID (UUID)")
    query = Column(String(500), nullable=False, comment="用户查询文本")
    intent = Column(String(100), nullable=False, comment="查询意图分类: factual/conceptual/procedural/comparative")
    expected_results = Column(JSON, nullable=False, comment="预期检索结果 ID 列表: [doc_id1, doc_id2, ...]")
    confidence = Column(Float, nullable=True, comment="标注置信度 0-1")
    annotated_by = Column(String(100), nullable=True, comment="标注人")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment="创建时间")
    
    # 索引（高频查询字段）
    __table_args__ = (
        Index('idx_query', 'query', prefix_length=100),  # 按查询文本前缀搜索
        Index('idx_intent', 'intent'),  # 按意图分类筛选
        Index('idx_confidence', 'confidence'),  # 按置信度筛选高质量标注
        Index('idx_annotated_by', 'annotated_by'),  # 按标注人查询
    )
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | String(500) | 用户查询文本 |
| `intent` | String(100) | 意图分类：factual（事实）/ conceptual（概念）/ procedural（流程）/ comparative（对比） |
| `expected_results` | JSON | 预期检索结果文档 ID 列表 |
| `confidence` | Float | 标注置信度 0-1（用于过滤低质量标注） |

**意图分类体系**：

| 意图类型 | 示例查询 | 检索策略 |
|----------|----------|----------|
| factual | "3 岁儿童大肌肉发展标准是什么？" | BM25 权重高（关键词匹配） |
| conceptual | "大肌肉和精细肌肉的区别？" | Vector 权重高（语义理解） |
| procedural | "如何设计感统训练计划？" | 混合检索 |
| comparative | "PEP-3 和 Griffiths 哪个更适合？" | 混合检索 + 重排序 |

---

### 3.4 新增 AuditLog 模型（补充）

**文件路径**：`backend/src/models/rag_eval/audit_log.py`

```python
"""审计日志模型 - 记录所有配置和提示词变更操作"""

from sqlalchemy import Column, String, JSON, Text, DateTime, Index
from datetime import datetime
import uuid
from src.models.base import Base


class AuditLog(Base):
    """审计日志表（独立表，无外键关联）"""
    
    __tablename__ = "rag_audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="日志 ID (UUID)")
    operator = Column(String(100), nullable=False, comment="操作人")
    action = Column(String(50), nullable=False, comment="操作类型: create/update/delete/rollback/apply")
    target_type = Column(String(50), nullable=False, comment="目标类型: config/prompt/test_set/test_case")
    target_id = Column(String(36), nullable=False, comment="目标 ID")
    
    # 变更内容
    before_value = Column(JSON, nullable=True, comment="变更前值")
    after_value = Column(JSON, nullable=False, comment="变更后值")
    diff_summary = Column(Text, nullable=True, comment="变更摘要（人类可读）")
    
    # 元数据
    ip_address = Column(String(45), nullable=True, comment="操作 IP")
    user_agent = Column(String(500), nullable=True, comment="用户代理")
    from datetime import datetime, timezone
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment="创建时间")
    
    # 索引（高频查询字段）
    __table_args__ = (
        Index('idx_operator', 'operator'),  # 按操作人查询
        Index('idx_action', 'action'),  # 按操作类型筛选
        Index('idx_target_type', 'target_type'),  # 按目标类型筛选
        Index('idx_target_id', 'target_id'),  # 按目标 ID 查询变更历史
        Index('idx_created_at', 'created_at'),  # 按时间范围查询
    )
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | String(50) | create（创建）/ update（更新）/ delete（删除）/ rollback（回滚）/ apply（采纳） |
| `target_type` | String(50) | config（配置）/ prompt（提示词）/ test_set（测试集）/ test_case（用例） |
| `before_value` | JSON | 变更前值（创建操作为 null） |
| `after_value` | JSON | 变更后值 |
| `diff_summary` | Text | 人类可读的变更摘要（如"BM25 权重从 0.3 改为 0.5"） |

---

### 3.5 Pydantic Schema 定义

**文件路径**：`backend/src/schemas/rag_eval.py`

**新增 AuditLog Schema**：

```python
# ========== AuditLog Schema ==========

class AuditLogCreate(BaseModel):
    """创建审计日志请求"""
    operator: str = Field(..., max_length=100, description="操作人")
    action: str = Field(..., max_length=50, description="操作类型")
    target_type: str = Field(..., max_length=50, description="目标类型")
    target_id: str = Field(..., description="目标 ID")
    before_value: Optional[Dict[str, Any]] = Field(None, description="变更前值")
    after_value: Dict[str, Any] = Field(..., description="变更后值")
    diff_summary: Optional[str] = Field(None, description="变更摘要")
    ip_address: Optional[str] = Field(None, max_length=45, description="操作 IP")
    user_agent: Optional[str] = Field(None, max_length=500, description="用户代理")


class AuditLogResponse(BaseModel):
    """审计日志响应"""
    id: str
    operator: str
    action: str
    target_type: str
    target_id: str
    before_value: Optional[Dict[str, Any]] = None
    after_value: Dict[str, Any]
    diff_summary: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogQueryParams(BaseModel):
    """审计日志查询参数"""
    operator: Optional[str] = Field(None, description="操作人筛选")
    action: Optional[str] = Field(None, description="操作类型筛选")
    target_type: Optional[str] = Field(None, description="目标类型筛选")
    target_id: Optional[str] = Field(None, description="目标 ID 筛选")
    from_date: Optional[datetime] = Field(None, description="开始时间")
    to_date: Optional[datetime] = Field(None, description="结束时间")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
```

**更新章节编号**：原 3.5 DDL 脚本更新 → 3.6，原 3.6 API 接口设计 → 3.7，原 3.7 验收标准 → 3.8

**文件路径**：`backend/src/schemas/rag_eval.py`

```python
"""RAG 评估相关 Pydantic Schema（实体类统一在 schemas/ 目录）"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ========== TestReport Schema ==========

class ValidationLayerResult(BaseModel):
    """单层校验结果"""
    status: str = Field(..., description="校验状态: pass/warning/fail")
    metrics: Optional[Dict[str, Any]] = Field(None, description="指标数据")
    suggestions: List["TuningSuggestionItem"] = Field(default_factory=list, description="调优建议")


class TuningSuggestionItem(BaseModel):
    """单个调优建议"""
    type: str = Field(..., description="建议类型: config/prompt/data")
    reason: str = Field(..., description="建议原因")
    current_value: Any = Field(..., description="当前值")
    suggested_value: Any = Field(..., description="建议值")
    impact_analysis: Dict[str, str] = Field(..., description="影响分析: {scope, expected_improvement, risk}")
    priority: str = Field(..., description="优先级: high/medium/low")


class TestReportCreate(BaseModel):
    """创建测试报告请求"""
    test_run_id: str = Field(..., description="测试运行 ID")
    validation_results: Dict[str, Any] = Field(..., description="6 层校验结果")
    tuning_suggestions: List[TuningSuggestionItem] = Field(..., description="调优建议列表")
    overall_score: float = Field(..., ge=0, le=100, description="综合评分 0-100")


class TestReportResponse(BaseModel):
    """测试报告响应"""
    id: str
    test_run_id: str
    validation_results: Dict[str, Any]
    tuning_suggestions: List[TuningSuggestionItem]
    overall_score: float
    generated_at: datetime
    
    class Config:
        from_attributes = True


# ========== TuningSuggestionRecord Schema ==========

class TuningSuggestionRecordCreate(BaseModel):
    """创建调优建议记录请求"""
    report_id: str = Field(..., description="报告 ID")
    suggestion_type: str = Field(..., description="建议类型: config/prompt/data")
    current_value: Any = Field(..., description="当前值")
    suggested_value: Any = Field(..., description="建议值")
    reason: str = Field(..., description="建议原因")
    impact_analysis: Dict[str, str] = Field(..., description="影响分析")


class TuningSuggestionRecordUpdate(BaseModel):
    """更新调优建议记录请求"""
    status: str = Field(..., description="新状态: pending/applied/ignored")
    applied_by: Optional[str] = Field(None, description="操作人")


class TuningSuggestionRecordResponse(BaseModel):
    """调优建议记录响应"""
    id: str
    report_id: str
    suggestion_type: str
    current_value: Any
    suggested_value: Any
    reason: str
    impact_analysis: Dict[str, str]
    status: str
    created_at: datetime
    applied_at: Optional[datetime] = None
    applied_by: Optional[str] = None
    
    class Config:
        from_attributes = True


# ========== IntentAnnotation Schema ==========

class IntentAnnotationCreate(BaseModel):
    """创建意图标注请求"""
    query: str = Field(..., max_length=500, description="用户查询文本")
    intent: str = Field(..., description="意图分类: factual/conceptual/procedural/comparative")
    expected_results: List[str] = Field(..., description="预期检索结果 ID 列表")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="标注置信度 0-1")
    annotated_by: Optional[str] = Field(None, description="标注人")


class IntentAnnotationResponse(BaseModel):
    """意图标注响应"""
    id: str
    query: str
    intent: str
    expected_results: List[str]
    confidence: Optional[float] = None
    annotated_by: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# 更新前向引用
ValidationLayerResult.model_rebuild()
```

**Schema 设计规范**：

| 规范 | 说明 |
|------|------|
| 命名 | `{ModelName}{Action}`（如 `TestReportCreate`、`TestReportResponse`） |
| 字段校验 | 使用 `Field()` 添加约束（`ge`、`le`、`max_length`） |
| 类型提示 | 所有字段都有类型注解，可选字段用 `Optional` |
| ORM 模式 | Response 类添加 `from_attributes = True` 支持 SQLAlchemy 转换 |
| 前向引用 | 使用 `model_rebuild()` 处理循环引用 |

---

### 3.5 DDL 脚本更新

**文件路径**：`.ai/full_init_script_mysql57.sql`

**新增建表语句（追加到文件末尾）**：

```sql
-- ============================================================
-- RAG 评估系统增强表（2026-04-18 新增）
-- ============================================================

-- 测试报告表
CREATE TABLE IF NOT EXISTS `rag_test_reports` (
    `id` VARCHAR(36) NOT NULL COMMENT '报告 ID (UUID)',
    `test_run_id` VARCHAR(36) NOT NULL COMMENT '测试运行 ID (逻辑关联 rag_test_runs.id)',
    `validation_results` JSON NOT NULL COMMENT '6 层校验结果 JSON',
    `tuning_suggestions` JSON NOT NULL COMMENT '调优建议列表 JSON',
    `overall_score` FLOAT NOT NULL COMMENT '综合评分 0-100',
    `generated_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '生成时间',
    PRIMARY KEY (`id`),
    INDEX `idx_test_run_id` (`test_run_id`),
    INDEX `idx_generated_at` (`generated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试报告表';

-- 调优建议记录表
CREATE TABLE IF NOT EXISTS `rag_tuning_suggestions` (
    `id` VARCHAR(36) NOT NULL COMMENT '建议 ID (UUID)',
    `report_id` VARCHAR(36) NOT NULL COMMENT '报告 ID (逻辑关联 rag_test_reports.id)',
    `suggestion_type` VARCHAR(50) NOT NULL COMMENT '建议类型: config/prompt/data',
    `current_value` JSON NOT NULL COMMENT '当前值',
    `suggested_value` JSON NOT NULL COMMENT '建议值',
    `reason` TEXT NOT NULL COMMENT '建议原因',
    `impact_analysis` JSON NOT NULL COMMENT '影响分析',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态: pending/applied/ignored',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `applied_at` DATETIME DEFAULT NULL COMMENT '采纳时间',
    `applied_by` VARCHAR(100) DEFAULT NULL COMMENT '操作人',
    PRIMARY KEY (`id`),
    INDEX `idx_report_id` (`report_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_suggestion_type` (`suggestion_type`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调优建议记录表';

-- 意图标注表
CREATE TABLE IF NOT EXISTS `rag_intent_annotations` (
    `id` VARCHAR(36) NOT NULL COMMENT '标注 ID (UUID)',
    `query` VARCHAR(500) NOT NULL COMMENT '用户查询文本',
    `intent` VARCHAR(100) NOT NULL COMMENT '意图分类: factual/conceptual/procedural/comparative',
    `expected_results` JSON NOT NULL COMMENT '预期检索结果 ID 列表',
    `confidence` FLOAT DEFAULT NULL COMMENT '标注置信度 0-1',
    `annotated_by` VARCHAR(100) DEFAULT NULL COMMENT '标注人',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_query` (`query`(100)),
    INDEX `idx_intent` (`intent`),
    INDEX `idx_confidence` (`confidence`),
    INDEX `idx_annotated_by` (`annotated_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='意图标注表';

-- 审计日志表
CREATE TABLE IF NOT EXISTS `rag_audit_logs` (
    `id` VARCHAR(36) NOT NULL COMMENT '日志 ID (UUID)',
    `operator` VARCHAR(100) NOT NULL COMMENT '操作人',
    `action` VARCHAR(50) NOT NULL COMMENT '操作类型: create/update/delete/rollback/apply',
    `target_type` VARCHAR(50) NOT NULL COMMENT '目标类型: config/prompt/test_set/test_case',
    `target_id` VARCHAR(36) NOT NULL COMMENT '目标 ID',
    `before_value` JSON DEFAULT NULL COMMENT '变更前值',
    `after_value` JSON NOT NULL COMMENT '变更后值',
    `diff_summary` TEXT DEFAULT NULL COMMENT '变更摘要',
    `ip_address` VARCHAR(45) DEFAULT NULL COMMENT '操作 IP',
    `user_agent` VARCHAR(500) DEFAULT NULL COMMENT '用户代理',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_operator` (`operator`),
    INDEX `idx_action` (`action`),
    INDEX `idx_target_type` (`target_type`),
    INDEX `idx_target_id` (`target_id`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审计日志表';
```

**DDL 设计规范**：

| 规范 | 说明 |
|------|------|
| 引擎 | InnoDB（支持事务和行级锁） |
| 字符集 | utf8mb4（支持 emoji 和特殊字符） |
| 主键 | VARCHAR(36) UUID（MySQL 5.7 兼容性） |
| 外键 | **无外键约束**（采用弱关联，应用层保证数据一致性） |
| 索引 | 高频查询字段全部添加索引 |
| 注释 | 所有字段都有 COMMENT |
| 默认值 | `created_at` 使用 `CURRENT_TIMESTAMP` |

---

## 四、API 接口设计（概要）

### 4.1 TestReport API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/reports` | 创建测试报告（校验引擎自动调用） |
| GET | `/api/v1/reports/{id}` | 获取报告详情 |
| GET | `/api/v1/reports?test_run_id=xxx` | 按测试运行查询报告 |
| GET | `/api/v1/reports?from=xxx&to=xxx` | 按时间范围查询报告列表 |

### 4.2 TuningSuggestion API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/suggestions?report_id=xxx` | 获取报告的调优建议列表 |
| PATCH | `/api/v1/suggestions/{id}` | 更新建议状态（采纳/忽略） |
| GET | `/api/v1/suggestions/stats` | 获取建议统计（各状态数量） |

### 4.3 IntentAnnotation API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/intent-annotations` | 创建意图标注 |
| GET | `/api/v1/intent-annotations` | 查询标注列表（支持 intent 筛选） |
| DELETE | `/api/v1/intent-annotations/{id}` | 删除标注 |
| POST | `/api/v1/intent-annotations/batch` | 批量导入标注 |

---

## 五、验收标准

- [ ] 三个数据模型 CRUD 接口正常
- [ ] 所有字段符合需求文档定义
- [ ] Pydantic Schema 完整，类型校验正确
- [ ] DDL 脚本可正常执行建表
- [ ] **无外键约束**（遵循弱关联原则）
- [ ] 高频查询字段已添加索引
- [ ] UUID 使用 String(36) 存储（MySQL 5.7 兼容）
- [ ] 所有字段都有注释说明

---
**注意**：遵循零迁移原则，直接修改 DDL 脚本，不生成迁移脚本
