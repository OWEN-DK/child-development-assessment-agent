# Phase 4: RAG 测试框架 MySQL 迁移与分布式执行

> 本文档是 MySQL + Redis 集成重构实施方案的一部分
> 
> **返回索引：** [README.md](./README.md) | [项目概览](./00-overview.md)

---

## Phase 4: RAG 测试框架 MySQL 迁移与分布式执行（周期：3 天）

### 目标
将 RAG 测试框架从 JSON 文件存储迁移到 MySQL，实现基于 Redis 分布式锁的批量测试执行，新增 SSE 实时进度推送功能。

### 架构设计

```
┌─────────────────────────────────────────────────┐
│           前端 (React + SSE)                     │
│    - 测试执行页面                                │
│    - 进度条实时更新                              │
│    - 结果展示                                    │
└─────────────────────────────────────────────────┘
                      ↓ SSE
┌─────────────────────────────────────────────────┐
│         API 层 (FastAPI + SSE)                   │
│    - POST /rag/test/run                          │
│    - GET /rag/test/run/{run_id}/stream          │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│      RAG 测试管理器 (RagTestManager)             │
│    - 测试用例管理 (MySQL)                        │
│    - 批量执行调度                                │
│    - 进度追踪                                    │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│      分布式锁 (Redis Lock)                       │
│    - 防止并发执行                                │
│    - 看门狗续期                                  │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         MySQL 数据库                             │
│    - test_cases                                  │
│    - test_runs                                   │
│    - test_run_results                            │
│    - test_sets                                   │
└─────────────────────────────────────────────────┘
```

---

### Task 4.1: 重写 RAG 测试管理器

**Files:**
- Modify: `backend/src/service/rag_test_manager.py`

- [ ] **Step 1: 重写 RagTestManager 使用 MySQL**

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from datetime import datetime
import uuid
from src.core.database import db_session_factory
from src.models.test_case import (
    TestCase, TestCaseDraft, TestSet, TestSetCase,
    TestRun, TestRunResult, TestDomain, TestRunStatus,
)
from src.core.distributed_lock import DistributedLock
from src.utils.logger import logger

class RagTestManager:
    """RAG 测试管理器（MySQL 存储版本）"""
    
    def __init__(self):
        self.db_session_factory = db_session_factory
    
    async def create_test_run(
        self,
        name: str,
        description: str = None,
        test_case_ids: list[str] = None,
        test_set_id: str = None,
    ) -> str:
        """创建测试运行"""
        async with self.db_session_factory() as session:
            run_id = str(uuid.uuid4())
            
            # 获取测试用例列表
            if test_case_ids:
                stmt = select(TestCase).where(TestCase.id.in_(test_case_ids))
                result = await session.execute(stmt)
                test_cases = result.scalars().all()
            elif test_set_id:
                # 从测试集获取
                stmt = (
                    select(TestCase)
                    .join(TestSetCase)
                    .where(TestSetCase.test_set_id == test_set_id)
                    .options(selectinload(TestSetCase.test_case))
                )
                result = await session.execute(stmt)
                test_cases = result.scalars().all()
            else:
                # 默认所有测试用例
                stmt = select(TestCase)
                result = await session.execute(stmt)
                test_cases = result.scalars().all()
            
            # 创建测试运行
            test_run = TestRun(
                id=run_id,
                name=name,
                description=description,
                total_test_cases=len(test_cases),
                passed_test_cases=0,
                status=TestRunStatus.RUNNING,
            )
            
            session.add(test_run)
            await session.commit()
            
            logger.info(f"测试运行已创建：{run_id}, 共 {len(test_cases)} 个用例")
            return run_id
    
    async def execute_test_case(
        self,
        run_id: str,
        test_case: TestCase,
        progress_callback=None,
    ) -> TestRunResult:
        """执行单个测试用例"""
        async with self.db_session_factory() as session:
            # 执行检索
            from src.service.retrieval_service import RetrievalService
            retrieval_service = RetrievalService()
            
            start_time = datetime.now()
            try:
                results = await retrieval_service.search(
                    query=test_case.query,
                    age=test_case.age,
                    limit=5,
                )
                
                # 计算指标
                matched_count = 0
                actual_knowledge_ids = []
                
                for result in results:
                    actual_knowledge_ids.append(result.id)
                    if test_case.expected_knowledge_ids and result.id in test_case.expected_knowledge_ids:
                        matched_count += 1
                
                expected_count = len(test_case.expected_knowledge_ids) if test_case.expected_knowledge_ids else 0
                actual_count = len(actual_knowledge_ids)
                
                precision = matched_count / actual_count if actual_count > 0 else 0.0
                recall = matched_count / expected_count if expected_count > 0 else 0.0
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
                passed = recall >= 0.8  # 召回率 >= 80% 视为通过
                
                # 创建结果
                test_result = TestRunResult(
                    run_id=run_id,
                    test_case_id=test_case.id,
                    query=test_case.query,
                    precision=precision,
                    recall=recall,
                    f1=f1,
                    passed=passed,
                    matched_count=matched_count,
                    expected_count=expected_count,
                    actual_count=actual_count,
                    expected_knowledge_ids=test_case.expected_knowledge_ids,
                    actual_knowledge_ids=actual_knowledge_ids,
                    execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                )
                
                session.add(test_result)
                await session.commit()
                
                # 进度回调
                if progress_callback:
                    await progress_callback(test_result)
                
                return test_result
                
            except Exception as e:
                logger.error(f"测试用例执行失败：{test_case.id}: {e}")
                
                test_result = TestRunResult(
                    run_id=run_id,
                    test_case_id=test_case.id,
                    query=test_case.query,
                    passed=False,
                    error_message=str(e),
                    execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                )
                
                session.add(test_result)
                await session.commit()
                
                return test_result
    
    async def complete_test_run(self, run_id: str):
        """完成测试运行，计算聚合指标"""
        async with self.db_session_factory() as session:
            # 获取所有结果
            stmt = select(TestRunResult).where(TestRunResult.run_id == run_id)
            result = await session.execute(stmt)
            test_results = result.scalars().all()
            
            # 计算聚合指标
            total = len(test_results)
            passed = sum(1 for r in test_results if r.passed)
            
            avg_precision = sum(r.precision for r in test_results if r.precision is not None) / total if total > 0 else 0.0
            avg_recall = sum(r.recall for r in test_results if r.recall is not None) / total if total > 0 else 0.0
            avg_f1 = sum(r.f1 for r in test_results if r.f1 is not None) / total if total > 0 else 0.0
            
            # 更新测试运行
            stmt = select(TestRun).where(TestRun.id == run_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one()
            
            test_run.status = TestRunStatus.COMPLETED
            test_run.completed_at = datetime.now()
            test_run.passed_test_cases = passed
            test_run.overall_precision = avg_precision
            test_run.overall_recall = avg_recall
            test_run.overall_f1 = avg_f1
            
            await session.commit()
            
            logger.info(f"测试运行已完成：{run_id}, 通过率={passed}/{total}={passed/total:.2%}")
```

---

### Task 4.2: 实现基于 Redis 分布式锁的批量执行

**Files:**
- Modify: `backend/src/service/rag_test_manager.py`

- [ ] **Step 1: 添加批量执行方法**

```python
async def execute_batch(
    self,
    run_id: str,
    test_case_ids: list[str],
    concurrency: int = 5,
) -> list:
    """批量执行测试用例（带分布式锁）"""
    
    lock_name = f"rag:test_run:{run_id}"
    
    async def _execute_with_lock():
        """在分布式锁保护下执行"""
        async with self.db_session_factory() as session:
            # 获取未执行的测试用例
            stmt = (
                select(TestCase)
                .join(TestRunResult, isouter=True)
                .where(
                    and_(
                        TestCase.id.in_(test_case_ids),
                        TestRunResult.run_id.is_(None)  # 未执行的
                    )
                )
            )
            result = await session.execute(stmt)
            test_cases = result.scalars().all()
        
        # 并发执行
        import asyncio
        semaphore = asyncio.Semaphore(concurrency)
        
        async def execute_single(test_case):
            async with semaphore:
                return await self.execute_test_case(run_id, test_case)
        
        tasks = [execute_single(tc) for tc in test_cases]
        results = await asyncio.gather(*tasks)
        
        # 完成运行
        await self.complete_test_run(run_id)
        
        return results
    
    # 使用分布式锁执行
    from src.core.distributed_lock import DistributedLock
    results = await DistributedLock.execute_with_lock(
        lock_name,
        _execute_with_lock,
        timeout=3600,  # 1 小时超时
    )
    
    return results
```

---

### Task 4.3: 实现 SSE 实时进度推送

**Files:**
- Modify: `backend/src/controller/rag_test_controller.py`
- Create: `backend/src/api/sse.py`

- [ ] **Step 1: 创建 SSE 推送工具**

```python
import asyncio
import json
from typing import AsyncGenerator
from fastapi.responses import StreamingResponse
from src.utils.logger import logger

class SSEPublisher:
    """SSE 发布器"""
    
    _subscribers: dict[str, list[asyncio.Queue]] = {}
    
    @classmethod
    async def subscribe(cls, channel: str) -> AsyncGenerator:
        """订阅频道"""
        queue = asyncio.Queue()
        
        if channel not in cls._subscribers:
            cls._subscribers[channel] = []
        
        cls._subscribers[channel].append(queue)
        logger.info(f"SSE 订阅已创建：{channel}")
        
        try:
            while True:
                message = await queue.get()
                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
        finally:
            # 取消订阅
            if channel in cls._subscribers:
                cls._subscribers[channel].remove(queue)
                if not cls._subscribers[channel]:
                    del cls._subscribers[channel]
            logger.info(f"SSE 订阅已取消：{channel}")
    
    @classmethod
    async def publish(cls, channel: str, message: dict):
        """发布消息到频道"""
        if channel not in cls._subscribers:
            return
        
        for queue in cls._subscribers[channel]:
            try:
                await queue.put(message)
            except Exception as e:
                logger.error(f"SSE 消息发布失败：{e}")
    
    @classmethod
    async def publish_progress(cls, run_id: str, progress: dict):
        """发布进度消息"""
        message = {
            "type": "progress",
            "run_id": run_id,
            **progress,
        }
        await cls.publish(f"test_run:{run_id}", message)
    
    @classmethod
    async def publish_result(cls, run_id: str, result: dict):
        """发布结果消息"""
        message = {
            "type": "result",
            "run_id": run_id,
            **result,
        }
        await cls.publish(f"test_run:{run_id}", message)
    
    @classmethod
    async def publish_complete(cls, run_id: str, summary: dict):
        """发布完成消息"""
        message = {
            "type": "complete",
            "run_id": run_id,
            **summary,
        }
        await cls.publish(f"test_run:{run_id}", message)

def sse_response(channel: str) -> StreamingResponse:
    """创建 SSE 响应"""
    return StreamingResponse(
        SSEPublisher.subscribe(channel),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: 更新控制器添加 SSE 端点**

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.service.rag_test_manager import RagTestManager
from src.api.sse import sse_response, SSEPublisher
from src.models.test_case import TestRunStatus

router = APIRouter()

@router.post("/test/run")
async def run_tests(
    name: str,
    test_case_ids: list[str] = None,
    test_set_id: str = None,
    concurrency: int = 5,
):
    """运行测试用例"""
    manager = RagTestManager()
    
    # 创建运行
    run_id = await manager.create_test_run(
        name=name,
        test_case_ids=test_case_ids,
        test_set_id=test_set_id,
    )
    
    # 后台执行
    import asyncio
    asyncio.create_task(
        _execute_with_progress(run_id, concurrency)
    )
    
    return {"run_id": run_id, "status": "started"}

async def _execute_with_progress(run_id: str, concurrency: int):
    """带进度推送的执行"""
    manager = RagTestManager()
    
    try:
        # 获取测试用例
        async with manager.db_session_factory() as session:
            from sqlalchemy import select
            from src.models.test_case import TestCase, TestRun
            
            stmt = select(TestRun).where(TestRun.id == run_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one()
            
            total = test_run.total_test_cases
        
        # 执行
        async def progress_callback(test_result):
            # 推送进度
            await SSEPublisher.publish_progress(
                run_id,
                {
                    "test_case_id": test_result.test_case_id,
                    "passed": test_result.passed,
                    "execution_time_ms": test_result.execution_time_ms,
                }
            )
        
        await manager.execute_batch(run_id, concurrency, progress_callback)
        
        # 推送完成
        await SSEPublisher.publish_complete(
            run_id,
            {
                "status": "completed",
                "total": total,
                "passed": test_run.passed_test_cases,
            }
        )
        
    except Exception as e:
        logger.error(f"测试执行失败：{e}")
        await SSEPublisher.publish(
            f"test_run:{run_id}",
            {
                "type": "error",
                "run_id": run_id,
                "error": str(e),
            }
        )

@router.get("/test/run/{run_id}/stream")
async def test_run_stream(run_id: str) -> StreamingResponse:
    """SSE 进度推送"""
    return sse_response(f"test_run:{run_id}")
```

---

### Task 4.4: 实现测试结果聚合和对比分析

**Files:**
- Modify: `backend/src/service/rag_test_manager.py`

- [ ] **Step 1: 添加结果分析方法**

```python
async def analyze_test_run(self, run_id: str) -> dict:
    """分析测试运行结果"""
    async with self.db_session_factory() as session:
        from sqlalchemy import select
        from src.models.test_case import TestRun, TestRunResult
        
        # 获取运行信息
        stmt = select(TestRun).where(TestRun.id == run_id)
        result = await session.execute(stmt)
        test_run = result.scalar_one()
        
        # 获取结果
        stmt = select(TestRunResult).where(TestRunResult.run_id == run_id)
        result = await session.execute(stmt)
        test_results = result.scalars().all()
        
        # 按领域分析
        domain_stats = {}
        for test_result in test_results:
            test_case = await session.get(TestCase, test_result.test_case_id)
            domain = test_case.domain.value
            
            if domain not in domain_stats:
                domain_stats[domain] = {
                    "total": 0,
                    "passed": 0,
                    "precision_sum": 0.0,
                    "recall_sum": 0.0,
                }
            
            domain_stats[domain]["total"] += 1
            if test_result.passed:
                domain_stats[domain]["passed"] += 1
            if test_result.precision:
                domain_stats[domain]["precision_sum"] += test_result.precision
            if test_result.recall:
                domain_stats[domain]["recall_sum"] += test_result.recall
        
        # 计算平均值
        for domain in domain_stats:
            total = domain_stats[domain]["total"]
            domain_stats[domain]["avg_precision"] = domain_stats[domain]["precision_sum"] / total
            domain_stats[domain]["avg_recall"] = domain_stats[domain]["recall_sum"] / total
            domain_stats[domain]["pass_rate"] = domain_stats[domain]["passed"] / total
        
        return {
            "run_id": run_id,
            "name": test_run.name,
            "status": test_run.status,
            "total": test_run.total_test_cases,
            "passed": test_run.passed_test_cases,
            "overall_precision": test_run.overall_precision,
            "overall_recall": test_run.overall_recall,
            "overall_f1": test_run.overall_f1,
            "domain_stats": domain_stats,
        }

async def compare_test_runs(self, run_id_1: str, run_id_2: str) -> dict:
    """对比两个测试运行"""
    stats_1 = await self.analyze_test_run(run_id_1)
    stats_2 = await self.analyze_test_run(run_id_2)
    
    return {
        "run_1": stats_1,
        "run_2": stats_2,
        "comparison": {
            "precision_diff": stats_2["overall_precision"] - stats_1["overall_precision"],
            "recall_diff": stats_2["overall_recall"] - stats_1["overall_recall"],
            "f1_diff": stats_2["overall_f1"] - stats_1["overall_f1"],
            "pass_rate_diff": (stats_2["passed"] / stats_2["total"]) - (stats_1["passed"] / stats_1["total"]),
        }
    }
```

---

### Task 4.5: 集成 JSON 修复机制

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/src/service/rag_test_manager.py`

- [ ] **Step 1: 安装 json-repair 库**

```toml
# backend/pyproject.toml
[project]
dependencies = [
    # ... 现有依赖 ...
    "json-repair>=0.30.0",
]
```

- [ ] **Step 2: 在测试用例生成中使用**

```python
# backend/src/service/rag_test_manager.py
import json
from json_repair import repair_json
from src.utils.logger import logger

class RagTestManager:
    async def generate_test_case_drafts(self, ...):
        """生成测试用例草稿"""
        # 大模型返回的 JSON 可能不完整
        raw_json = await llm.generate(...)
        
        try:
            # 尝试直接解析
            draft_data = json.loads(raw_json)
        except json.JSONDecodeError:
            # 解析失败，使用 json-repair 修复
            logger.warning(f"JSON 解析失败，尝试修复：{raw_json[:100]}...")
            repaired_json = repair_json(raw_json)
            
            try:
                draft_data = json.loads(repaired_json)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 修复失败：{e}")
                raise ValueError(f"无法解析大模型生成的 JSON: {e}")
        
        # Pydantic 校验
        try:
            draft = TestCaseDraft(**draft_data)
            return draft
        except Exception as e:
            logger.error(f"Pydantic 校验失败：{e}")
            raise
```

- [ ] **Step 3: 验证 JSON 修复逻辑**

测试不完整 JSON 的修复功能，确保能处理：
- 丢失的括号
- 丢失的引号
- 截断的 JSON

---

### Task 4.5: 实现草稿去重器
**Files:**
- Create: `backend/src/service/draft_deduplicator.py`

- [ ] **Step 1: 创建去重服务**
```python
import difflib
from typing import List
from src.models.test_case import TestCaseDraft
from src.utils.logger import logger

class DraftDeduplicator:
    """基于相似度的草稿去重器"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
    
    def deduplicate(self, drafts: List[TestCaseDraft]) -> List[TestCaseDraft]:
        """去除重复草稿"""
        if not drafts:
            return []
        
        unique_drafts = []
        for draft in drafts:
            is_duplicate = False
            for existing in unique_drafts:
                similarity = self._calculate_similarity(draft, existing)
                if similarity > self.similarity_threshold:
                    is_duplicate = True
                    logger.debug(f"草稿 {draft.id} 与 {existing.id} 相似度过高: {similarity:.2f}")
                    break
            
            if not is_duplicate:
                unique_drafts.append(draft)
        
        removed_count = len(drafts) - len(unique_drafts)
        if removed_count > 0:
            logger.info(f"草稿去重完成：{len(drafts)} → {len(unique_drafts)}（移除 {removed_count} 条）")
        
        return unique_drafts
    
    def _calculate_similarity(self, draft1: TestCaseDraft, draft2: TestCaseDraft) -> float:
        """计算两个草稿的相似度"""
        # 基于 query 的文本相似度
        query_sim = difflib.SequenceMatcher(None, draft1.query, draft2.query).ratio()
        
        # 如果领域不同，直接判定不相似
        if draft1.domain != draft2.domain:
            return query_sim * 0.5
        
        # 如果年龄相差超过 6 个月，降低相似度
        age_diff = abs(float(draft1.age) - float(draft2.age))
        age_factor = max(0, 1 - age_diff / 12)
        
        return query_sim * 0.7 + age_factor * 0.3
```

### Task 4.6: 评分异步重算机制
**Files:**
- Modify: `backend/src/controller/rag_test_controller.py`

- [ ] **Step 1: 添加后台重算任务**
```python
from fastapi import BackgroundTasks
from src.service.rag_test_manager import RagTestManager

@router.delete("/runs/{run_id}")
async def delete_test_run(run_id: str, background_tasks: BackgroundTasks):
    """删除测试运行（触发聚合评分重算）"""
    manager = RagTestManager()
    
    # 删除运行
    await manager.delete_run(run_id)
    
    # 异步重算聚合评分
    background_tasks.add_task(manager.recalculate_aggregate_scores)
    
    return {"message": "测试运行已删除，聚合评分将在后台重算"}
```

- [ ] **Step 2: 实现 recalculate_aggregate_scores**
```python
async def recalculate_aggregate_scores(self):
    """全量重新计算聚合评分（放入 BackgroundTasks 异步执行）"""
    async with self.db_session_factory() as session:
        # 获取所有未完成的运行
        stmt = select(TestRun).where(TestRun.status == "completed")
        result = await session.execute(stmt)
        runs = result.scalars().all()
        
        for run in runs:
            # 重新计算该运行的聚合指标
            results_stmt = select(TestRunResult).where(TestRunResult.run_id == run.id)
            results_result = await session.execute(results_stmt)
            results = results_result.scalars().all()
            
            if not results:
                continue
            
            total = len(results)
            passed = sum(1 for r in results if r.passed)
            run.passed_test_cases = passed
            run.overall_precision = sum(r.precision for r in results if r.precision) / total
            run.overall_recall = sum(r.recall for r in results if r.recall) / total
            run.overall_f1 = sum(r.f1 for r in results if r.f1) / total
        
        await session.commit()
        logger.info(f"聚合评分已重算：{len(runs)} 个运行")
```

### Task 4.7: SSEPublisher 改用 Redis Pub/Sub
**Files:**
- Modify: `backend/src/api/sse.py`

- [ ] **Step 1: 重构 SSEPublisher 使用 Redis**
```python
import asyncio
import json
from typing import AsyncGenerator
from fastapi.responses import StreamingResponse
from src.core.redis_client import RedisClient
from src.utils.logger import logger

class SSEPublisher:
    """SSE 发布器（基于 Redis Pub/Sub，支持多实例）"""
    
    _local_subscribers: dict[str, list[asyncio.Queue]] = {}
    
    @classmethod
    async def subscribe(cls, channel: str) -> AsyncGenerator:
        """订阅频道"""
        queue = asyncio.Queue()
        
        if channel not in cls._local_subscribers:
            cls._local_subscribers[channel] = []
        
        cls._local_subscribers[channel].append(queue)
        
        # 启动 Redis 订阅监听
        redis_task = asyncio.create_task(cls._listen_redis(channel, queue))
        
        try:
            while True:
                message = await queue.get()
                if message is None:  # 停止信号
                    break
                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
        finally:
            if channel in cls._local_subscribers:
                cls._local_subscribers[channel].remove(queue)
                if not cls._local_subscribers[channel]:
                    del cls._local_subscribers[channel]
            redis_task.cancel()
            logger.info(f"SSE 订阅已取消：{channel}")
    
    @classmethod
    async def _listen_redis(cls, channel: str, queue: asyncio.Queue):
        """监听 Redis 频道"""
        redis_client = RedisClient.get_client()
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"child-dev:sse:{channel}")
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await queue.put(data)
        finally:
            await pubsub.unsubscribe(f"child-dev:sse:{channel}")
    
    @classmethod
    async def publish(cls, channel: str, message: dict):
        """发布消息到 Redis 频道"""
        redis_client = RedisClient.get_client()
        await redis_client.publish(
            f"child-dev:sse:{channel}",
            json.dumps(message, ensure_ascii=False)
        )
        
        # 同时发送到本地队列（同实例优化）
        if channel in cls._local_subscribers:
            for queue in cls._local_subscribers[channel]:
                await queue.put(message)
    
    @classmethod
    async def publish_progress(cls, run_id: str, progress: dict):
        """发布进度消息"""
        await cls.publish(f"test_run:{run_id}", {
            "type": "progress",
            "run_id": run_id,
            **progress,
        })
    
    @classmethod
    async def publish_complete(cls, run_id: str, summary: dict):
        """发布完成消息"""
        await cls.publish(f"test_run:{run_id}", {
            "type": "complete",
            "run_id": run_id,
            **summary,
        })

def sse_response(channel: str) -> StreamingResponse:
    """创建 SSE 响应"""
    return StreamingResponse(
        SSEPublisher.subscribe(channel),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

### Phase 4 完成验证

- [ ] 运行单元测试，验证 MySQL 存储功能正常
- [ ] 测试分布式锁，确认并发执行安全
- [ ] 验证 SSE 进度推送，前端实时更新正常
- [ ] 检查测试结果聚合和对比分析功能
- [ ] 压力测试：同时执行多个测试运行

---

**返回索引：** [README.md](./README.md)
