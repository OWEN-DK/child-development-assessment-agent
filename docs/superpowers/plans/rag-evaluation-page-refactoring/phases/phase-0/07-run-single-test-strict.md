# runSingleTest 严格单用例 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** runSingleTest 严格单用例

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
> **根因**: 代码 Bug：`_caseId` 参数被忽略，实际运行了所有测试

---

## 需求定义

当前后端 `execute_test_case` 方法（或类似名称）中存在 Bug：即使前端传入了 `caseId` 参数，后端仍然执行了所有测试用例，而不是只执行指定的那一个。

**修复要求**：
1. 单个用例测试必须严格只运行该用例
2. 传入 `caseId` 后，仅执行对应用例
3. 返回结果只包含该用例的执行结果

---

## 验收标准

- [ ] 传入 caseId 后，仅执行对应用例
- [ ] 返回结果只包含该用例的执行数据
- [ ] 不传入 caseId 时行为不变（批量测试不受影响）

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/service/rag_test_manager.py` | 修改 | 修复 `execute_test_case` 中的 caseId 过滤逻辑 |
| `backend/src/controller/rag_test_controller.py` | 检查 | 确认单用例测试端点正确传递 caseId |

---

## 实现方案

### 后端实现

**步骤 1：定位并修复 `execute_test_case` 方法**

找到 `rag_test_manager.py` 中的 `execute_test_case` 方法（约第 201 行），检查 caseId 过滤逻辑：

```python
# backend/src/service/rag_test_manager.py

async def execute_test_case(self, run_id: str, case_id: str) -> dict:
    """执行单个测试用例
    
    参数:
        run_id: 测试运行 ID
        case_id: 测试用例 ID
        
    返回:
        单个用例的执行结果
    """
    # 获取该 run 关联的测试集
    run = await self._get_test_run(run_id)
    if not run:
        raise ValueError(f"Test run {run_id} not found")
    
    # 获取测试集关联的所有用例
    test_cases = await self._get_test_cases_for_run(run_id)
    
    # 修复：严格过滤 case_id（统一使用 ORM 属性访问）
    target_case = None
    for tc in test_cases:
        # tc 为 ORM 模型实例，使用属性访问
        if str(tc.id) == str(case_id):
            target_case = tc
            break
    
    if not target_case:
        raise ValueError(f"Test case {case_id} not found in run {run_id}")
    
    # 只执行目标用例
    result = await self._execute_single_test_case(target_case)
    
    return result
```

**步骤 2：检查 `_execute_single_test_case` 实现**

确保 `_execute_single_test_case` 不会触发其他用例的执行：

```python
async def _execute_single_test_case(self, test_case: dict) -> dict:
    """执行单个测试用例的核心逻辑
    
    参数:
        test_case: 测试用例数据
        
    返回:
        执行结果
    """
    from src.api.sse import SSEPublisher
    
    # 推送开始事件
    run_id = test_case.get('run_id')
    case_id = test_case.get('id')
    
    await SSEPublisher.publish(f"test_run:{run_id}", {
        "type": "case_start",
        "case_id": case_id,
        "query": test_case.get('query'),
    })
    
    try:
        # 执行检索
        results = await self._retrieve_for_test_case(test_case)
        
        # 评估结果
        evaluation = self._evaluate_results(test_case, results)
        
        # 保存结果
        await self._save_test_result(run_id, case_id, evaluation)
        
        # 推送完成事件
        await SSEPublisher.publish(f"test_run:{run_id}", {
            "type": "case_complete",
            "case_id": case_id,
            "status": evaluation.get('status', 'passed'),
            "result": evaluation,
        })
        
        return evaluation
    except Exception as e:
        # 推送错误事件
        await SSEPublisher.publish(f"test_run:{run_id}", {
            "type": "case_error",
            "case_id": case_id,
            "error": str(e),
        })
        raise
```

**步骤 3：修复 `execute_batch` 中的 caseId 误用（如存在）**

如果 `execute_batch` 方法中也有 caseId 参数但被忽略，确保正确处理：

```python
async def execute_batch(
    self,
    run_id: str,
    concurrency: int = 5,
    case_id: str | None = None,  # 新增：可选的 caseId 过滤
    progress_callback=None,
) -> dict:
    """执行批量测试
    
    参数:
        run_id: 测试运行 ID
        concurrency: 并发数
        case_id: 如果指定，只执行该用例（单用例模式）
        progress_callback: 进度回调
        
    返回:
        聚合结果
    """
    test_cases = await self._get_test_cases_for_run(run_id)
    
    # 如果指定了 case_id，只执行该用例（统一使用 ORM 属性访问）
    if case_id:
        test_cases = [tc for tc in test_cases if str(tc.id) == str(case_id)]
        if not test_cases:
            raise ValueError(f"Test case {case_id} not found")
    
    # 使用本地并发控制（需求点 9）
    semaphore = asyncio.Semaphore(concurrency)
    
    async def execute_with_semaphore(tc):
        async with semaphore:
            return await self._execute_single_test_case(tc)
    
    # 使用 return_exceptions=True 防止单个失败影响全局
    results = await asyncio.gather(
        *[execute_with_semaphore(tc) for tc in test_cases],
        return_exceptions=True,
    )
    
    # 聚合结果（需求点 10）
    return await self._aggregate_results(run_id, results, test_cases)
```

**步骤 4：修复 RetrievalService 实例化 Bug（附带修复）**

当前 `execute_test_case` 中直接 `RetrievalService()` 无参数调用会报错。改为使用 DI 容器或全局单例：

```python
# 修改前
retrieval_service = RetrievalService()  # TypeError!

# 修改后：使用全局单例
from src.service.rag_service import rag_service

# 或使用 DI 容器
from src.core.di_container import injector
retrieval_service = injector.get(IRetrievalService)
```

---

## 测试方案

### 单元测试

```python
# backend/tests/test_single_case_execution.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

class TestSingleCaseExecution:
    @pytest.mark.asyncio
    async def test_execute_single_case(self):
        """测试只执行单个用例"""
        manager = RagTestManager()
        
        # Mock 数据
        mock_run = {"id": "run-1", "test_set_id": "ts-1"}
        mock_cases = [
            {"id": "case-1", "query": "query 1", "run_id": "run-1"},
            {"id": "case-2", "query": "query 2", "run_id": "run-1"},
        ]
        
        with patch.object(manager, '_get_test_run', return_value=mock_run):
            with patch.object(manager, '_get_test_cases_for_run', return_value=mock_cases):
                with patch.object(manager, '_execute_single_test_case', return_value={"status": "passed"}) as mock_exec:
                    result = await manager.execute_test_case("run-1", "case-1")
                    
                    # 验证只执行了 case-1
                    mock_exec.assert_called_once()
                    call_args = mock_exec.call_args[0][0]
                    assert call_args["id"] == "case-1"
    
    @pytest.mark.asyncio
    async def test_execute_single_case_not_found(self):
        """测试用例不存在时抛出异常"""
        manager = RagTestManager()
        
        mock_cases = [{"id": "case-1", "query": "query 1"}]
        
        with patch.object(manager, '_get_test_cases_for_run', return_value=mock_cases):
            with pytest.raises(ValueError, match="not found"):
                await manager.execute_test_case("run-1", "case-999")
    
    @pytest.mark.asyncio
    async def test_execute_batch_with_case_id_filter(self):
        """测试批量测试中 case_id 过滤"""
        manager = RagTestManager()
        
        mock_cases = [
            {"id": "case-1", "query": "query 1"},
            {"id": "case-2", "query": "query 2"},
            {"id": "case-3", "query": "query 3"},
        ]
        
        with patch.object(manager, '_get_test_cases_for_run', return_value=mock_cases):
            with patch.object(manager, '_execute_single_test_case', return_value={"status": "passed"}) as mock_exec:
                await manager.execute_batch("run-1", concurrency=1, case_id="case-2")
                
                # 验证只执行了 case-2
                mock_exec.assert_called_once()
                call_args = mock_exec.call_args[0][0]
                assert call_args["id"] == "case-2"
```

### 手动测试

1. 创建一个包含 3 个用例的测试集
2. 调用单用例测试 API，传入 `caseId` 为第 2 个用例
3. 检查后端日志，确认只执行了第 2 个用例
4. 检查返回结果，确认只包含第 2 个用例的数据

---

## 注意事项

1. **ID 匹配**：用例 ID 可能是 UUID 字符串或整数，比较时需确保类型一致。
2. **SSE 事件**：单用例测试也应推送 SSE 事件，前端据此更新 UI。
3. **RetrievalService Bug**：当前 `RetrievalService()` 无参数调用是 Critical Bug，必须同步修复（见步骤 4）。
4. **兼容性**：如果前端旧版代码仍调用旧端点，需确认旧端点是否也需要修复。Phase 0 不写兼容代码，直接修复。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
