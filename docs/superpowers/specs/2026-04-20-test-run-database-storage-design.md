# 测试运行数据库存储设计

## 概述

将 RAG 测试系统的所有持久化逻辑从文件系统完全迁移到 MySQL 数据库，消除文件存储依赖，支持多实例部署和数据共享。

## 问题分析

### 当前问题

1. **数据不可见**：测试完成后，运行历史和报告无法通过数据库查询
2. **多实例不兼容**：文件存储无法在多实例部署中共享数据
3. **代码有 bug**：`TestRunStorage` 使用 `model_dump_json()` 序列化 SQLAlchemy 模型（该方法仅适用于 Pydantic 模型）
4. **违反项目规范**：项目明确要求"所有逻辑都保存进数据库，而不是文件"

### 根本原因

- `TestBatchRunner.run_all_tests()` 创建 TestRun 后调用 `_save_test_run()` 写入 JSON 文件
- `TestRunStorage` 类完全基于文件系统实现
- Controller 层通过 `rag_test_manager.list_test_runs()` 从文件读取数据

### 已有基础设施

数据库模型和 Repository 已存在且可用：
- `models/test_case.py`: `TestRun`, `TestRunResult` 模型
- `repository/test_case_repository.py`: `TestRunRepository`, `TestRunResultRepository`
- `test_executor.py`: 已正确保存 `TestRunResult` 到数据库
- `test_run_creator.py`: 已正确保存 `TestRun` 到数据库

---

## 设计方案

### 架构变更

```
当前架构（错误）:
  TestBatchRunner → TestRunStorage → JSON 文件
  Controller → RagTestFacade → TestRunStorage → JSON 文件

目标架构（正确）:
  TestBatchRunner → TestRunRepository → MySQL
  Controller → RagTestFacade → TestRunRepository → MySQL
```

---

### 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/src/service/rag_test/test_run/test_batch_runner.py` | 重写 | 删除文件操作，改为直接调用 Repository |
| `backend/src/service/rag_test/test_run/test_run_storage.py` | 删除 | 功能合并到 Repository，不再需要 |
| `backend/src/service/rag_test/test_run/__init__.py` | 修改 | 删除 TestRunStorage 导出 |
| `backend/src/service/rag_test/test_run_service.py` | 修改 | 删除 `storage` 依赖，改为调用 Repository，添加 `test_results` 关联查询 |
| `backend/src/service/rag_test/test_run/test_result_analyzer.py` | 修改 | 删除 `_list_test_runs_from_files()`，改为数据库查询 |
| `backend/src/service/rag_test/facade.py` | 修改 | 删除 `test_runs_dir`，删除重复的 `compare_test_runs`，更新删除逻辑 |
| `backend/src/controller/rag_test_controller.py` | 修改 | 添加 await，添加序列化器，添加 `test_results` 转换逻辑 |

---

### 详细改动

#### 1. `test_batch_runner.py` - 核心修改

**删除：**
- `self.test_runs_dir` 初始化
- `_save_test_run()` 方法
- `_get_last_test_run()` 方法
- `_list_test_runs_from_files()` 方法

**修改 `run_all_tests()` 方法：**

```python
# 当前（错误）：
test_run = TestRun(id=run_id, ...)
# ... 执行测试 ...
test_run.test_results = test_results  # TestRun 模型没有这个字段！
self._save_test_run(test_run)  # 写入文件

# 改为：
async def run_all_tests(self, run_test_case_fn, name: str = "", description: str = "", limit: int = 10) -> TestRun:
    # 1. 获取测试用例和配置
    test_cases = await test_case_service.list()
    current_version = config_manager.get_active_version()
    config_snapshot = config_manager.get_full_config()
    
    # 2. 从数据库获取上一次运行
    previous_run = await self._get_last_test_run_from_db()
    
    # 3. 创建 TestRun 对象
    run_id = str(uuid.uuid4())
    test_run = TestRun(
        id=run_id,
        name=name or f"Test Run {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        description=description,
        total_test_cases=len(test_cases),
        status=TestRunStatus.PENDING,
        config_version_id=current_version,
        config_snapshot=config_snapshot,
        previous_config_version_id=previous_run.config_version_id if previous_run else None,
    )
    
    # 4. 立即保存到数据库
    async with self.db_session_factory() as session:
        session.add(test_run)
        await session.commit()
    
    # 5. 创建任务状态并更新为 running
    await test_run_task_adapter.create(...)
    await test_run_task_adapter.update(run_id, {"status": TaskStatus.RUNNING, ...})
    
    test_run.status = TestRunStatus.RUNNING
    
    # 6. 执行测试用例（改为调用 execute_test_case 以保存到数据库）
    # 注意：run_test_case_fn 应该是 execute_test_case 而非 run_test_case
    # execute_test_case 返回 TestRunResult（ORM）并保存到数据库
    # run_test_case 返回 TestResult（Pydantic）不保存到数据库
    passed_count = 0
    total_precision = 0.0
    total_recall = 0.0
    total_f1 = 0.0
    total_mrr = 0.0
    total_ndcg = 0.0
    
    for i, test_case in enumerate(test_cases):
        try:
            # 调用 execute_test_case 而非 run_test_case
            result = await run_test_case_fn(run_id, test_case)
            
            # 累加指标
            total_precision += result.precision or 0.0
            total_recall += result.recall or 0.0
            total_f1 += result.f1 or 0.0
            total_mrr += result.mrr or 0.0
            total_ndcg += result.ndcg or 0.0
            
            if result.passed:
                passed_count += 1
            
            # 更新进度
            progress = ((i + 1) / len(test_cases)) * 100
            await test_run_task_adapter.update(
                run_id,
                {
                    "progress": progress,
                    "message": f"已执行 {i + 1}/{len(test_cases)} 个用例",
                }
            )
        except Exception as e:
            logger.error(f"Failed to run test case {test_case.id}: {e}")
            continue
    
    # 7. 更新聚合指标（通过 complete_test_run）
    await self.complete_test_run(run_id)
    
    return test_run

async def _get_last_test_run_from_db(self) -> Optional[TestRun]:
    """从数据库获取最后一个测试运行"""
    async with self.db_session_factory() as session:
        stmt = select(TestRun).order_by(desc(TestRun.created_at)).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
```

**关键修改点：**
1. **删除 `test_run.test_results = test_results`** - TestRun ORM 模型没有这个字段
2. **改为调用 `execute_test_case()` 而非 `run_test_case()`** - 前者保存结果到数据库，后者不保存
3. **删除 `self._save_test_run(test_run)`** - 改为在步骤4立即保存，步骤7更新聚合指标

**修改 `execute_batch()` 方法：**

当前代码已经正确保存 TestRunResult 到数据库，无需修改。

---

#### 2. `test_run_storage.py` - 删除

**原因：** 功能完全由 `TestRunRepository` 替代，不需要中间层。

**替代方案：**
- `save_test_run()` → `TestRunRepository.create()`
- `list_test_runs()` → `TestRunRepository.get_latest_runs()`
- `get_test_run()` → `TestRunRepository.get_by_id()`
- `get_last_test_run()` → `TestRunRepository.get_latest_runs(limit=1)[0]`

---

#### 3. `test_run/__init__.py` - 修改

**当前：**
```python
from .test_batch_runner import TestBatchRunner
from .test_executor import TestExecutor
from .test_result_analyzer import TestResultAnalyzer
from .test_run_creator import TestRunCreator
from .test_run_storage import TestRunStorage

__all__ = [
    "TestBatchRunner",
    "TestExecutor",
    "TestResultAnalyzer",
    "TestRunCreator",
    "TestRunStorage",
]
```

**改为：**
```python
from .test_batch_runner import TestBatchRunner
from .test_executor import TestExecutor
from .test_result_analyzer import TestResultAnalyzer
from .test_run_creator import TestRunCreator

__all__ = [
    "TestBatchRunner",
    "TestExecutor",
    "TestResultAnalyzer",
    "TestRunCreator",
]
```

---

#### 4. `test_run_service.py` - 修改

**删除：**
- `self.storage = TestRunStorage()`
- `save_test_run()` 方法

**新增：**
```python
from src.repository.test_case_repository import TestRunRepository

class TestRunService:
    def __init__(self):
        self.creator = TestRunCreator()
        self.executor = TestExecutor()
        self.batch_runner = TestBatchRunner()
        self.analyzer = TestResultAnalyzer()
        self.repo = TestRunRepository(db_session_factory)  # 替代 storage
    
    async def list_test_runs(self) -> List[TestRun]:
        """获取测试运行列表（返回 ORM 对象）"""
        return await self.repo.get_latest_runs(limit=50)
    
    async def get_test_run(self, run_id: str) -> Optional[dict]:
        """获取测试运行详情（包含 test_results 关联查询，返回字典）"""
        async with self.db_session_factory() as session:
            # 获取 TestRun
            stmt = select(TestRun).where(TestRun.id == run_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one_or_none()
            
            if not test_run:
                return None
            
            # 关联查询 TestRunResult
            stmt = select(TestRunResult).where(TestRunResult.run_id == run_id)
            result = await session.execute(stmt)
            test_results = result.scalars().all()
            
            # 转换为字典并添加 test_results
            return {
                'id': test_run.id,
                'name': test_run.name,
                'description': test_run.description,
                'overall_precision': float(test_run.overall_precision) if test_run.overall_precision else 0.0,
                'overall_recall': float(test_run.overall_recall) if test_run.overall_recall else 0.0,
                'overall_f1': float(test_run.overall_f1) if test_run.overall_f1 else 0.0,
                'overall_mrr': float(test_run.overall_mrr) if test_run.overall_mrr else 0.0,
                'overall_ndcg': float(test_run.overall_ndcg) if test_run.overall_ndcg else 0.0,
                'total_test_cases': test_run.total_test_cases,
                'passed_test_cases': test_run.passed_test_cases,
                'status': test_run.status.value if hasattr(test_run.status, 'value') else test_run.status,
                'created_at': test_run.created_at.isoformat() if test_run.created_at else None,
                'completed_at': test_run.completed_at.isoformat() if test_run.completed_at else None,
                'snapshot_id': test_run.snapshot_id,
                'config_version_id': test_run.config_version_id,
                'previous_config_version_id': test_run.previous_config_version_id,
                'config_snapshot': test_run.config_snapshot,
                'test_results': [
                    {
                        'id': r.id,
                        'test_case_id': r.test_case_id,
                        'query': r.query,
                        'precision': float(r.precision) if r.precision else 0.0,
                        'recall': float(r.recall) if r.recall else 0.0,
                        'f1': float(r.f1) if r.f1 else 0.0,
                        'mrr': float(r.mrr) if r.mrr else 0.0,
                        'ndcg': float(r.ndcg) if r.ndcg else 0.0,
                        'passed': r.passed,
                        'matched_count': r.matched_count,
                        'expected_count': r.expected_count,
                        'actual_count': r.actual_count,
                        'execution_time_ms': r.execution_time_ms,
                        'error_message': r.error_message,
                    }
                    for r in test_results
                ]
            }
    
    async def get_last_test_run(self) -> Optional[TestRun]:
        runs = await self.repo.get_latest_runs(limit=1)
        return runs[0] if runs else None
```

**返回类型说明：**
- `list_test_runs()` 返回 `List[TestRun]`（ORM 对象列表）- Controller 层使用序列化器转换
- `get_test_run()` 返回 `Optional[dict]`（字典）- 已包含关联查询的 `test_results`，无需额外序列化

---

#### 5. `test_result_analyzer.py` - 修改

**删除：**
- `_list_test_runs_from_files()` 方法

**修改 `compare_config_versions()` 方法：**

```python
async def compare_config_versions(self, version_id1: str, version_id2: str) -> Dict:
    """比较两个配置版本的测试表现"""
    async with self.db_session_factory() as session:
        stmt = select(TestRun).where(
            TestRun.config_version_id.in_([version_id1, version_id2])
        )
        result = await session.execute(stmt)
        runs = result.scalars().all()
        
        runs_for_v1 = [r for r in runs if r.config_version_id == version_id1]
        runs_for_v2 = [r for r in runs if r.config_version_id == version_id2]
        
        if not runs_for_v1:
            raise ValueError(f"No test runs found for config version {version_id1}")
        if not runs_for_v2:
            raise ValueError(f"No test runs found for config version {version_id2}")
        
        # ... 计算平均值和差异 ...
```

---

#### 6. `facade.py` - 修改

**删除：**
- `self.test_runs_dir = f"{STORAGE_DIR}/test_runs"`
- `os.makedirs(self.test_runs_dir, exist_ok=True)`
- **第343-344行：同步版本的 `compare_test_runs()` 方法**（与第157行异步版本重复，且内部调用异步方法会导致错误）

**修改 `batch_delete_test_runs()` 方法：**

```python
async def batch_delete_test_runs(self, run_ids: List[str]) -> int:
    from src.repository import TestRunRepository
    
    repo = TestRunRepository(self.db_session_factory)
    deleted_count = 0
    for run_id in run_ids:
        if await repo.delete(run_id):
            deleted_count += 1
            # 删除文件目录的代码已删除
            logger.info(f"Test run deleted: {run_id}")
    return deleted_count
```

**修改 `compare_test_runs()` 调用：**

Controller 中第311行调用的是同步版本，需要改为调用异步版本并添加 `await`：

```python
# 当前（错误）：
comparison = rag_test_manager.compare_test_runs(run_id1, run_id2)

# 改为：
comparison = await rag_test_manager.compare_test_runs(run_id1, run_id2)
```

---

#### 7. `rag_test_controller.py` - 修改

**新增序列化器：**

```python
serialize_test_run = create_serializer(
    object,
    {
        "id": None,
        "name": None,
        "description": None,
        "overall_precision": safe_float,
        "overall_recall": safe_float,
        "overall_f1": safe_float,
        "overall_mrr": safe_float,
        "overall_ndcg": safe_float,
        "total_test_cases": None,
        "passed_test_cases": None,
        "status": safe_enum_value,
        "created_at": safe_isoformat,
        "completed_at": safe_isoformat,
        "snapshot_id": None,
        "config_version_id": None,
        "previous_config_version_id": None,
        "config_snapshot": None,
    }
)
```

**修改 `list_test_runs()` 端点：**

```python
@router.get("/runs")
async def list_test_runs():
    """列出所有测试运行"""
    runs = await rag_test_manager.list_test_runs()  # 添加 await，返回 ORM 对象列表
    result = [serialize_test_run(run) for run in runs]  # 序列化 ORM 对象
    return APIResponse.success(data=result)
```

**修改 `get_test_run()` 端点：**

```python
@router.get("/runs/{run_id}")
async def get_test_run(run_id: str):
    """获取单个测试运行结果"""
    run = await rag_test_manager.get_test_run(run_id)  # 添加 await，返回字典（已包含 test_results）
    if not run:
        raise TestRunNotFoundException(run_id=run_id)
    return APIResponse.success(data=run)  # 已是字典，无需序列化
```

**修改 `compare_test_runs()` 端点：**

```python
@router.get("/compare")
async def compare_test_runs(run_id1: str, run_id2: str):
    """比较两个测试运行的结果"""
    try:
        comparison = await rag_test_manager.compare_test_runs(run_id1, run_id2)  # 添加 await
        return APIResponse.success(data={"comparison": comparison})
    except ValueError as e:
        raise InvalidParamsException(message=str(e))
```

**返回类型说明：**
- `list_test_runs()` - 返回 ORM 对象列表，Controller 使用 `serialize_test_run` 序列化
- `get_test_run()` - 返回字典（已包含 `test_results`），Controller 直接返回

---

### 数据流设计

```
执行测试流程:
  1. Controller.run_tests() → Facade.create_test_run() → TestRunCreator.create_test_run()
     → 保存 TestRun 到数据库 ✅
  
  2. Facade.execute_batch() → TestBatchRunner.execute_batch()
     → TestExecutor.execute_test_case()
     → 保存 TestRunResult 到数据库 ✅
  
  3. TestBatchRunner.complete_test_run()
     → 更新 TestRun 聚合指标到数据库 ✅

查询测试运行:
  Controller.list_test_runs() → Facade.list_test_runs()
    → TestRunService.list_test_runs()
    → TestRunRepository.get_latest_runs()
    → 从数据库查询 ✅
```

---

### 关键改动点

#### 1. 逐步保存策略

**当前逻辑（有问题）：**
```python
# 创建 TestRun → 执行所有测试 → 一次性保存到文件
```

**改进后：**
```python
# 1. 创建 TestRun 并立即保存到数据库
# 2. 每个 TestRunResult 执行后立即保存到数据库（已实现）
# 3. 完成后更新 TestRun 聚合指标
```

**好处：** 系统崩溃时不会丢失所有数据。

---

#### 2. 异步一致性

**问题：** `TestRunStorage` 的方法是同步的，但 Repository 是异步的。

**解决方案：** 
- 删除 `TestRunStorage` 类
- `TestRunService` 直接调用异步 Repository
- Controller 层添加 `await`

---

#### 3. 数据模型统一

**问题：** `test_run_storage.py` 使用 `model_dump_json()` 序列化 SQLAlchemy 模型（这是 Pydantic 方法）。

**解决方案：** 
- 统一使用 SQLAlchemy 模型
- 删除所有 Pydantic 序列化代码
- Repository 直接返回 ORM 对象

---

## 验收标准

### 功能验收

1. ✅ 测试完成后，`test_runs` 表有对应记录
2. ✅ 测试完成后，`test_run_results` 表有对应结果记录
3. ✅ `GET /rag/test/runs` 返回数据库中的测试运行列表
4. ✅ `GET /rag/test/runs/{run_id}` 返回数据库中的测试运行详情
5. ✅ 删除测试运行时，只删除数据库记录（不操作文件）

### 代码验收

1. ✅ 删除 `test_run_storage.py` 文件
2. ✅ 删除所有 `test_runs_dir` 相关代码
3. ✅ 删除所有 `os.path`, `open()`, `json.load()` 等文件操作
4. ✅ 所有 Repository 调用使用异步方法
5. ✅ Controller 端点正确使用 `await`
6. ✅ `test_run/__init__.py` 不再导出 TestRunStorage
7. ✅ `facade.py` 只有一个异步版本的 `compare_test_runs()`
8. ✅ `get_test_run()` 返回包含 `test_results` 的字典
9. ✅ `list_test_runs()` 返回 ORM 对象列表，Controller 使用序列化器转换
10. ✅ `run_all_tests()` 删除 `test_run.test_results = test_results` 行
11. ✅ `run_all_tests()` 调用 `execute_test_case()` 而非 `run_test_case()`

### 数据验收

1. ✅ `test_runs` 表包含所有必要字段（name, status, total_test_cases, passed_test_cases, 聚合指标等）
2. ✅ `test_run_results` 表包含所有测试结果（precision, recall, f1, mrr, ndcg 等）
3. ✅ 外键关系正确（`test_run_results.run_id` → `test_runs.id`）

---

## 风险评估

### 低风险

- **Repository 已存在**：`TestRunRepository` 和 `TestRunResultRepository` 已实现且可用
- **模型已定义**：`TestRun` 和 `TestRunResult` 模型已正确定义
- **部分已实现**：`TestExecutor` 和 `TestRunCreator` 已正确使用数据库

### 中风险

- **异步改造**：需要同步方法改为异步，可能影响调用链
- **Controller 修改**：需要添加 `await`，可能遗漏
- **前端依赖**：前端期望 `test_results` 字段，需要关联查询
- **方法重复**：`facade.py` 有两个 `compare_test_runs()` 方法，可能调用错误的版本

### 高风险

- **序列化错误**：直接返回 ORM 对象会导致 JSON 序列化失败，必须使用序列化器
- **执行路径混淆**：`run_all_tests()` 调用 `run_test_case()` 不会保存结果到数据库，必须改为调用 `execute_test_case()`
- **字段不存在**：`TestRun` ORM 模型没有 `test_results` 字段，设置该属性不会保存到数据库

### 缓解措施

1. 修改后运行类型检查：`cd backend && python -m py_compile src/service/rag_test/*.py`
2. 测试所有相关 API 端点
3. 检查数据库记录是否正确创建

---

## 实施步骤

1. 修改 `test_batch_runner.py` - 删除文件操作，改为数据库
2. 删除 `test_run_storage.py` 文件
3. 修改 `test_run/__init__.py` - 删除 TestRunStorage 导出
4. 修改 `test_run_service.py` - 删除 storage，改为 repository，添加 test_results 关联查询
5. 修改 `test_result_analyzer.py` - 删除文件查询
6. 修改 `facade.py` - 删除目录初始化，删除重复的 compare_test_runs
7. 修改 `rag_test_controller.py` - 添加 await，添加序列化器
8. 运行测试验证

---

## 后续优化（可选）

1. **报告内容存储**：将 Markdown 报告内容存储到数据库的 JSON 字段，而不是文件路径
2. **分页查询**：为 `list_test_runs()` 添加分页支持
3. **索引优化**：为高频查询字段添加数据库索引
