# 等待所有用例结果聚合 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 等待所有用例结果聚合

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Modify: `backend/src/service/rag_test_manager.py`
- Modify: `backend/src/controller/rag_test_controller.py`
- Test: `backend/src/service/rag_test_manager.py`

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

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.2` 节
> **所属 Phase**: Phase 0
> **根因**: `complete_test_run` 可能在所有用例完成前读取数据，导致聚合指标不准确

---

## 需求定义

当前批量测试完成后，`_aggregate_results` 方法可能在所有用例结果还未完全写入时就计算指标，导致报告中的统计数据（如通过率、平均分数）与实际执行情况不一致。

**修复要求**：
1. 测试完成后必须等待所有用例结果聚合完毕再计算指标
2. 聚合逻辑必须基于实际执行的用例结果，而非查询数据库（可能有延迟）
3. 错误用例和成功用例分别统计

---

## 验收标准

- [ ] 报告指标与用例执行结果一致
- [ ] 通过率 = 成功用例数 / 总用例数
- [ ] 错误用例在报告中明确列出

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/service/rag_test_manager.py` | 修改 | 完善 `_aggregate_results` 方法 |
| `backend/src/controller/rag_test_controller.py` | 检查 | 确认聚合时机正确 |

---

## 实现方案

### 后端实现

**步骤 1：完善 `_aggregate_results` 方法**

```python
# backend/src/service/rag_test_manager.py

from typing import Optional
from datetime import datetime

class RagTestManager:
    async def _aggregate_results(
        self,
        run_id: str,
        results: list[dict],
        errors: list[dict],
        total: int,
    ) -> dict:
        """聚合测试结果
        
        基于实际执行的 results 和 errors 列表计算指标，
        不依赖数据库查询，确保数据一致性。
        
        参数:
            run_id: 测试运行 ID
            results: 成功用例的结果列表
            errors: 失败用例的错误信息列表
            total: 总用例数
            
        返回:
            聚合指标
        """
        completed = len(results)
        failed = len(errors)
        passed = sum(1 for r in results if r.get('status') == 'passed')
        
        # 计算平均分（仅基于有分数的用例）
        scores = [r.get('score') for r in results if r.get('score') is not None]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # 计算通过率
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        # 构建聚合结果
        aggregation = {
            "run_id": run_id,
            "total": total,
            "completed": completed,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(pass_rate, 2),
            "avg_score": round(avg_score, 2),
            "errors": errors,
            "completed_at": datetime.now().isoformat(),
        }
        
        # 保存聚合结果到数据库
        await self._save_aggregation(run_id, aggregation)
        
        return aggregation
    
    async def _save_aggregation(self, run_id: str, aggregation: dict):
        """保存聚合结果到数据库
        
        参数:
            run_id: 测试运行 ID
            aggregation: 聚合指标
        """
        # 使用 SQLAlchemy 异步会话保存
        from src.core.database import get_async_session
        from src.models.rag_eval.test_run import RagEvalTestRun
        
        async with get_async_session() as session:
            async with session.begin():
                run = await session.get(RagEvalTestRun, run_id)
                if run:
                    run.status = 'completed'
                    run.total_cases = aggregation['total']
                    run.completed_cases = aggregation['completed']
                    run.passed_cases = aggregation['passed']
                    run.failed_cases = aggregation['failed']
                    run.pass_rate = aggregation['pass_rate']
                    run.avg_score = aggregation['avg_score']
                    run.completed_at = aggregation['completed_at']
                # async with session.begin() 块结束时自动 commit
```

**步骤 2：确保 `execute_batch` 正确调用聚合**

在 `execute_batch` 方法中，确保在所有用例执行完毕后才调用聚合：

```python
async def execute_batch(self, run_id: str, concurrency: int = 5, ...):
    # ... 执行所有用例 ...
    
    # 等待所有用例完成
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 分类结果
    results = []
    errors = []
    for i, raw in enumerate(raw_results):
        if isinstance(raw, Exception):
            errors.append({
                "case_id": test_cases[i].get('id'),
                "error": str(raw),
            })
        elif raw is not None:
            results.append(raw)
        # raw is None 的情况已在 execute_with_semaphore 中处理
    
    # 此时所有用例都已完成，可以安全聚合
    aggregation = await self._aggregate_results(run_id, results, errors, total)
    
    return aggregation
```

**步骤 3：处理 SSE 事件时序问题**

确保 SSE 事件的发送顺序正确：

```
1. batch_start
2. case_start (每个用例)
3. case_complete / case_error (每个用例)
4. progress (每个用例完成后)
5. batch_complete (所有用例完成后，包含聚合结果)
```

`batch_complete` 事件必须在 `_aggregate_results` 完成后发送，确保前端收到的聚合数据是最终的。

---

## 测试方案

### 单元测试

```python
# backend/tests/test_result_aggregation.py

import pytest
from unittest.mock import AsyncMock, patch

class TestResultAggregation:
    @pytest.mark.asyncio
    async def test_aggregate_all_passed(self):
        """测试全部用例通过时的聚合"""
        manager = RagTestManager()
        
        results = [
            {"status": "passed", "score": 0.9},
            {"status": "passed", "score": 0.8},
            {"status": "passed", "score": 0.95},
        ]
        errors = []
        
        with patch.object(manager, '_save_aggregation', new_callable=AsyncMock):
            aggregation = await manager._aggregate_results("run-1", results, errors, 3)
        
        assert aggregation["total"] == 3
        assert aggregation["completed"] == 3
        assert aggregation["passed"] == 3
        assert aggregation["failed"] == 0
        assert aggregation["pass_rate"] == 100.0
        assert abs(aggregation["avg_score"] - 0.883) < 0.01
    
    @pytest.mark.asyncio
    async def test_aggregate_with_failures(self):
        """测试包含失败用例时的聚合"""
        manager = RagTestManager()
        
        results = [
            {"status": "passed", "score": 0.9},
            {"status": "failed", "score": 0.3},
        ]
        errors = [
            {"case_id": "case-3", "error": "Connection timeout"},
        ]
        
        with patch.object(manager, '_save_aggregation', new_callable=AsyncMock):
            aggregation = await manager._aggregate_results("run-1", results, errors, 3)
        
        assert aggregation["total"] == 3
        assert aggregation["completed"] == 2
        assert aggregation["passed"] == 1
        assert aggregation["failed"] == 1
        assert aggregation["pass_rate"] == 33.33
        assert len(aggregation["errors"]) == 1
    
    @pytest.mark.asyncio
    async def test_aggregate_empty_results(self):
        """测试空结果时的聚合"""
        manager = RagTestManager()
        
        with patch.object(manager, '_save_aggregation', new_callable=AsyncMock):
            aggregation = await manager._aggregate_results("run-1", [], [], 0)
        
        assert aggregation["total"] == 0
        assert aggregation["pass_rate"] == 0
        assert aggregation["avg_score"] == 0
    
    @pytest.mark.asyncio
    async def test_aggregation_waits_for_all(self):
        """测试聚合等待所有用例完成"""
        manager = RagTestManager()
        
        results = []
        errors = []
        
        async def slow_execute(idx):
            await asyncio.sleep(0.1 * idx)
            if idx % 3 == 0:
                errors.append({"case_id": f"case-{idx}", "error": "error"})
            else:
                results.append({"status": "passed", "score": 0.8})
        
        # 模拟 10 个用例并发执行
        # idx % 3 == 0 的有：0, 3, 6, 9（共 4 个错误）
        # 其余：1, 2, 4, 5, 7, 8（共 6 个成功）
        await asyncio.gather(*[slow_execute(i) for i in range(10)])
        
        # 聚合时应该有完整的结果
        with patch.object(manager, '_save_aggregation', new_callable=AsyncMock):
            aggregation = await manager._aggregate_results("run-1", results, errors, 10)
        
        assert aggregation["completed"] == 10
        assert aggregation["passed"] == 6
        assert aggregation["failed"] == 4
```

### 手动测试

1. 创建一个包含 10 个用例的测试集
2. 执行批量测试
3. 测试完成后检查报告中的指标：
   - 总数 = 10
   - 完成数 = 10
   - 通过率与实际情况一致
4. 人为制造 1-2 个用例失败，确认错误用例在报告中列出

---

## 注意事项

1. **不依赖数据库查询**：聚合基于内存中的 `results` 和 `errors` 列表，而非查询数据库。数据库写入是异步的，可能有延迟。
2. **分数计算**：平均分仅基于有 `score` 字段的用例。如果某些用例没有分数（如执行失败），不计入平均分。
3. **四舍五入**：百分比和平均分保留两位小数，避免浮点数精度问题。
4. **错误分类**：`failed` 包含两种情况：用例执行返回 `status: failed` 和用例抛出异常。两者都在 `errors` 列表中记录。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
