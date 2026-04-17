# 07 - Layer 4c: 文档时效性 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 07 - Layer 4c: 文档时效性

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer4c_staleness.py`
- Test: `backend/tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.4.3 校验 4c: 文档时效性检查` 节
> **所属 Phase**: Phase 4

## 需求定义

检查源文档内容是否过期。按文档类型分类的时效阈值：政策法规 3 年、学术研究 10 年、经典理论不检查、实操方法 5 年。

## 验收标准

- [ ] 文档类型识别正确
- [ ] 过期比例 > 20% 时警告
- [ ] 政策法规类 > 5 年前严重警告
- [ ] 未标注类型默认学术研究类

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer4c_staleness.py` | 新增 | Layer 4c 实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer4c_staleness.py
import logging
from datetime import datetime, timedelta, UTC
from typing import Any
from collections import defaultdict

logger = logging.getLogger(__name__)

STALENESS_THRESHOLDS = {
    "政策法规/指南": 3,
    "学术研究/实证": 10,
    "经典理论": None,
    "实操方法/训练方案": 5,
}

class Layer4cDocumentStaleness:
    """Layer 4c: 文档时效性检查"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行时效性检查"""
        source_documents = self.test_run.source_documents or []
        
        if not source_documents:
            return {"status": "skipped", "data": {"reason": "缺少源文档数据"}}
        
        now = datetime.now(UTC).replace(tzinfo=None)
        stale_count = 0
        stale_docs = []
        by_type = defaultdict(lambda: {"total": 0, "stale": 0})
        
        for doc in source_documents:
            doc_type = doc.get("document_type", "学术研究/实证")
            upload_date = doc.get("upload_date")
            
            if not upload_date:
                continue
            
            by_type[doc_type]["total"] += 1
            
            threshold_years = STALENESS_THRESHOLDS.get(doc_type)
            if threshold_years is None:
                continue  # 经典理论不检查
            
            if isinstance(upload_date, str):
                upload_date = datetime.fromisoformat(upload_date.replace("Z", "+00:00")).replace(tzinfo=None)
            
            age_years = (now - upload_date).days / 365.25
            
            if age_years > threshold_years:
                stale_count += 1
                by_type[doc_type]["stale"] += 1
                stale_docs.append({
                    "doc_id": doc.get("id"),
                    "title": doc.get("title", ""),
                    "doc_type": doc_type,
                    "upload_date": upload_date.isoformat(),
                    "age_years": round(age_years, 1),
                    "threshold_years": threshold_years,
                })
        
        total = sum(v["total"] for v in by_type.values())
        stale_ratio = stale_count / total if total > 0 else 0
        
        warnings = []
        if stale_ratio > 0.20:
            warnings.append({"level": "warning", "message": f"过期文档过多 ({stale_ratio:.1%} > 20%)"})
        
        for doc in stale_docs:
            if doc["doc_type"] == "政策法规/指南" and doc["age_years"] > 5:
                warnings.append({
                    "level": "critical",
                    "message": f"严重过期文档: {doc['title']} ({doc['age_years']} 年 > 5 年)",
                })
        
        return {
            "status": "completed",
            "data": {
                "stale_count": stale_count,
                "stale_ratio": stale_ratio,
                "stale_docs": stale_docs[:10],
                "by_type": dict(by_type),
                "warnings": warnings,
            },
        }
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_stale_policy_document():
    """政策法规类 > 5 年严重警告"""
    ...

@pytest.mark.asyncio
async def test_default_document_type():
    """未标注类型默认学术研究类"""
    ...
```

## 注意事项

- 日期解析需处理 ISO 格式和 datetime 对象
- 经典理论类型不检查时效性
