# RAG 评估运行性能优化方案

> 日期: 2026-05-06
> 问题: 点击"开始运行"后进度条推进缓慢

## 问题根因

逐文件验证后确认 6 个瓶颈，按影响排序：

| # | 瓶颈 | 文件:行号 | 影响 |
|---|------|----------|------|
| 1 | SSE 每次发布都 Redis PING | `sse.py:43-48` | 每个 case 多 2-3 次无意义网络往返 |
| 2 | 用例并发数默认 3 | `batch_runner.py:124` | 30 case 需 10 批，每批 3-15s |
| 3 | 用例加载串行 | `facade.py:96-101` | N 个 case 阻塞 API 响应 N×DB查询 |
| 4 | 闭包创建在信号量内 | `batch_runner.py:242-245` | 占用并发槽位 |
| 5 | 后处理流水线串行 | `orchestrator.py:71-113` | 指标计算完成后才开始报告生成 |
| 6 | 每 case 可能 2 次 LLM | `query_router.py:170-255` | 单 case 耗时翻倍 |

---

## 修复 1: Redis 可用性缓存（高影响，低风险）

**文件**: `backend/src/api/sse.py`

**问题**: `_get_redis_availability()` 每次调用都执行 `redis_client.ping()`，而 `_redis_available` 类变量虽然存在但每次都被覆盖。

**方案**: 带 TTL 的缓存，而非每次都 PING。

```python
# === 修改前 (sse.py:31-48) ===

class SSEPublisher:
    _local_subscribers: dict[str, list[asyncio.Queue]] = {}
    _redis_available: Optional[bool] = None

    @classmethod
    async def _check_redis_availability(cls) -> bool:
        """检查 Redis 是否可用"""
        try:
            redis_client = RedisClient.get_client()
            return await redis_client.ping()
        except Exception:
            return False

    @classmethod
    async def _get_redis_availability(cls) -> bool:
        """获取 Redis 可用性状态（每次发布时重新检查）"""
        cls._redis_available = await cls._check_redis_availability()
        if not cls._redis_available:
            logger.warning("Redis 不可用，SSE 将降级到内存队列模式")
        return cls._redis_available


# === 修改后 ===

class SSEPublisher:
    _local_subscribers: dict[str, list[asyncio.Queue]] = {}
    _redis_available: Optional[bool] = None
    _redis_last_check: float = 0.0
    _REDIS_CHECK_INTERVAL: float = 30.0  # 30 秒检查一次

    @classmethod
    async def _check_redis_availability(cls) -> bool:
        """检查 Redis 是否可用"""
        try:
            redis_client = RedisClient.get_client()
            return await redis_client.ping()
        except Exception:
            return False

    @classmethod
    async def _get_redis_availability(cls) -> bool:
        """获取 Redis 可用性状态（带 TTL 缓存，避免每次发布都 PING）"""
        now = asyncio.get_event_loop().time()
        if cls._redis_available is not None and (now - cls._redis_last_check) < cls._REDIS_CHECK_INTERVAL:
            return cls._redis_available
        cls._redis_available = await cls._check_redis_availability()
        cls._redis_last_check = now
        if not cls._redis_available:
            logger.warning("Redis 不可用，SSE 将降级到内存队列模式")
        return cls._redis_available
```

**预期收益**: 每个 case 减少 2-3 次 Redis 往返，30 个 case 减少 ~60-90 次网络调用。

---

## 修复 2: 提升默认并发数（高影响，需评估资源）

**文件**: `backend/src/service/rag_eval/run/batch_runner.py`

**问题**: 默认并发 3，每个 case 3-15 秒，吞吐量受限。

**方案**: 将默认并发从 3 提升到 5-8。LLM 调用是 I/O 密集型，提高并发不会显著增加 CPU 负载。

```python
# === 修改前 (batch_runner.py:124) ===
concurrency = self._config.get_int("rag.eval.run.concurrency", 3)

# === 修改后 ===
concurrency = self._config.get_int("rag.eval.run.concurrency", 5)
```

**注意**: 这个值应该通过数据库配置 `rag.eval.run.concurrency` 动态调整，代码只是改默认值。如果 LLM 提供商有 QPS 限制，需要根据实际测试调整。

**预期收益**: 吞吐量提升 ~67%（3→5），30 case 从 10 批降到 6 批。

---

## 修复 3: 用例并行加载（中影响，低风险）

**文件**: `backend/src/service/rag_eval/run/facade.py`

**问题**: `start_run` 中逐个加载 test case，N 个 case 阻塞 N 次 DB 查询。

**方案**: 用 `asyncio.gather` 并行加载。

```python
# === 修改前 (facade.py:96-101) ===
test_cases = []
for cid in case_ids:
    try:
        test_cases.append(await self._case_engine.get_case(cid))
    except AppException:
        continue

# === 修改后 ===
async def _load_case(cid: str):
    try:
        return await self._case_engine.get_case(cid)
    except AppException:
        return None

loaded = await asyncio.gather(*[_load_case(cid) for cid in case_ids])
test_cases = [c for c in loaded if c is not None]
```

**预期收益**: API 响应时间从 O(N×DB_latency) 降到 O(1×DB_latency)，前端更快连接 SSE。

---

## 修复 4: 闭包创建移到信号量外（低影响，低风险）

**文件**: `backend/src/service/rag_eval/run/batch_runner.py`

**问题**: `build_execution_functions()` 在 `async with sem:` 内调用，占用并发槽位。

**方案**: 在获取信号量前创建闭包。

```python
# === 修改前 (batch_runner.py:231-257) ===
async def _execute_with_semaphore(self, sem, case, run_id, current_running=1):
    async with sem:
        retrieval_fn, generation_fn = None, None
        if self._facade:
            retrieval_fn, generation_fn = self._facade.build_execution_functions()
        base_timeout_ms = 300_000
        timeout_ms = base_timeout_ms * current_running
        return await self._executor.execute(
            test_case=case, run_id=run_id,
            retrieval_fn=retrieval_fn, generation_fn=generation_fn,
            timeout_ms=timeout_ms,
        )

# === 修改后 ===
async def _execute_with_semaphore(self, sem, case, run_id, current_running=1):
    # 闭包创建不涉及 I/O，移到信号量外避免占用并发槽位
    retrieval_fn, generation_fn = None, None
    if self._facade:
        retrieval_fn, generation_fn = self._facade.build_execution_functions()
    async with sem:
        base_timeout_ms = 300_000
        timeout_ms = base_timeout_ms * current_running
        return await self._executor.execute(
            test_case=case, run_id=run_id,
            retrieval_fn=retrieval_fn, generation_fn=generation_fn,
            timeout_ms=timeout_ms,
        )
```

**预期收益**: 微量，但消除了不必要的槽位占用。

---

## 修复 5: 后处理流水线部分并行（中影响，低风险）

**文件**: `backend/src/service/rag_eval/orchestrator.py`

**问题**: 指标计算和报告生成串行，但报告依赖指标结果，所以只能优化"获取结果"和"指标计算"之间的重叠。

**方案**: 这里实际上步骤是有依赖的（报告依赖指标），所以主要优化是让"获取结果"提前开始。当前已经是 `await get_run_results` 后再计算，结构上没有大的并行空间。

真正可优化的是：**指标计算和报告生成使用独立的异步任务，不阻塞主流程**。但这已经是后台任务了，收益有限。

**结论**: 此项收益有限，暂不修改。

---

## 修复 6: 禁用评估场景下的 LLM 查询分类（高影响，需业务确认）

**文件**: `backend/src/service/retrieval/facade.py` + `backend/src/core/query_router.py`

**问题**: 评估时每个 case 的 query 已知，不需要 LLM 做分类。但 `retrieve_knowledge` 每次都调用 `query_router.classify_async`，如果 regex 不匹配就会触发 LLM 调用。

**方案 A（推荐）**: 在评估执行时，通过参数跳过 LLM 分类。

```python
# retrieval/facade.py - retrieve_knowledge 增加 skip_llm_classify 参数
async def retrieve_knowledge(self, query: str, limit: int = 5, skip_llm_classify: bool = False):
    if skip_llm_classify:
        # 直接走默认检索路径，跳过 query_router
        classification = QueryClassification(domain="default", confidence=1.0)
    else:
        classification = await self.query_router.classify_async(query)
    ...
```

```python
# rag_eval/run/facade.py - build_execution_functions 中传递 skip_llm_classify
async def _retrieval(query: str):
    results = await self._retrieval.retrieve_knowledge(query, limit=5, skip_llm_classify=True)
    ...
```

**方案 B（更简单）**: 在评估场景的配置中设置 `query_router_llm_enabled=false`，但这会影响所有检索，不仅仅是评估。

**预期收益**: 每个 case 减少 1-3 秒 LLM 调用，30 个 case 减少 30-90 秒。

---

## 优先级建议

| 优先级 | 修复项 | 改动量 | 收益 | 风险 |
|--------|--------|--------|------|------|
| P0 | 修复 1: Redis 缓存 | 小 | 高 | 低 |
| P0 | 修复 3: 并行加载 | 小 | 中 | 低 |
| P1 | 修复 2: 提升并发 | 1 行 | 高 | 中（需测 LLM QPS） |
| P1 | 修复 4: 闭包外移 | 小 | 低 | 低 |
| P2 | 修复 6: 跳过 LLM 分类 | 中 | 高 | 中（需确认业务） |
| P3 | 修复 5: 后处理并行 | 大 | 低 | 中 |

---

## 实施建议

1. **先做 P0**（修复 1+3），改动小、风险低、立即见效
2. **测试后做 P1**（修复 2+4），提升并发数需要观察 LLM 提供商的 QPS 限制
3. **与业务确认后做 P2**（修复 6），评估场景确实不需要 LLM 分类，但需确认 query_router 的 regex 覆盖率
4. **P3 暂缓**，后处理已经是后台任务，体感影响小
