# 09 - Layer 5b: 意图识别准确率 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 09 - Layer 5b: 意图识别准确率

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer5b_intent.py`
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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.5.2 校验 5b: 意图识别准确率` 节
> **所属 Phase**: Phase 4

## 需求定义

检查查询意图分类的准确性。LLM 自动标注 + 人工标注双轨制，5 种意图类型。

## 验收标准

- [ ] 整体准确率 < 80% 时警告（基于人工标注部分）
- [ ] 低置信度查询占比 > 30% 时警告
- [ ] 5 种意图类型分类正确

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer5b_intent.py` | 新增 | Layer 5b 实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer5b_intent.py
import logging
from typing import Any
from collections import defaultdict

logger = logging.getLogger(__name__)

INTENT_TYPES = {
    "factual_query": "事实查询",
    "how_to": "方法指导",
    "comparison": "对比分析",
    "definition": "定义解释",
    "troubleshooting": "问题诊断",
}

class Layer5bIntentAccuracy:
    """Layer 5b: 意图识别准确率"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行意图准确率校验"""
        query_analyses = self.test_run.query_analyses or []
        
        if not query_analyses:
            return {"status": "skipped", "data": {"reason": "缺少查询分析结果"}}
        
        auto_labeled = [qa for qa in query_analyses if qa.get("label_source") == "auto"]
        manual_labeled = [qa for qa in query_analyses if qa.get("label_source") == "manual"]
        
        low_confidence_queries = [
            qa for qa in query_analyses
            if qa.get("confidence", 1.0) < 0.8
        ]
        
        accuracy = None
        if manual_labeled:
            correct = sum(
                1 for qa in manual_labeled
                if qa.get("predicted_intent") == qa.get("manual_intent")
            )
            accuracy = correct / len(manual_labeled)
        
        accuracy_by_type = defaultdict(lambda: {"correct": 0, "total": 0})
        for qa in manual_labeled:
            intent = qa.get("manual_intent") or qa.get("predicted_intent")
            accuracy_by_type[intent]["total"] += 1
            if qa.get("predicted_intent") == qa.get("manual_intent"):
                accuracy_by_type[intent]["correct"] += 1
        
        warnings = []
        if accuracy is not None and accuracy < 0.80:
            warnings.append({
                "level": "warning",
                "message": f"意图识别准确率低 ({accuracy:.1%} < 80%)",
            })
        
        low_confidence_ratio = len(low_confidence_queries) / len(query_analyses) if query_analyses else 0
        if low_confidence_ratio > 0.30:
            warnings.append({
                "level": "warning",
                "message": f"低置信度查询过多 ({low_confidence_ratio:.1%} > 30%)",
            })
        
        return {
            "status": "completed",
            "data": {
                "overall_accuracy": accuracy,
                "accuracy_by_type": {
                    k: v["correct"] / v["total"] if v["total"] > 0 else None
                    for k, v in accuracy_by_type.items()
                },
                "low_confidence_queries": [
                    {"query": qa.get("query"), "confidence": qa.get("confidence")}
                    for qa in low_confidence_queries[:10]
                ],
                "low_confidence_ratio": low_confidence_ratio,
                "warnings": warnings,
            },
        }
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_accuracy_below_threshold():
    """准确率低于 80% 时警告"""
    ...

@pytest.mark.asyncio
async def test_low_confidence_ratio():
    """低置信度查询占比过高时警告"""
    ...
```

## 注意事项

- 准确率基于人工标注部分计算
- 低置信度阈值 0.8
