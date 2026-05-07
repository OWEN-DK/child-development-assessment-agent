# 报告生成性能问题诊断与解决方案

## 一、问题诊断

### 1.1 现象

报告生成进度非常慢，用户点击"生成报告"按钮后只能看到按钮 loading 态，没有进度反馈，体验极差。

### 1.2 根因分析（从数据流全链路定位）

报告生成的完整链路：`generateReport API → 指标补算(可选) → ReportBuilder.build → MarkdownRenderer.render → DB 保存`

#### 瓶颈 1：指标补算时 ScoringFacade 逐条串行计算（最大瓶颈）

**文件**: `backend/src/service/rag_eval/metrics/scoring/facade.py:49-53`

```python
# 当前实现：逐条串行
for rd in results:
    all_l1.append(await self._retrieval.score_all(rd))
    all_l2.append(await self._generation.score_all(rd))
    all_l3.append(await self._system.score_all(rd))
```

每个 test case 的 L1/L2/L3 三个 scorer 都是串行 await。**经代码验证，L2 的三个指标全部涉及 LLM 调用**：
- **faithfulness**：1 次 claim 提取 + N 次逐 claim 验证（串行），每条用例 1-10+ 次 LLM 调用
- **answer_relevancy**：1 次问题生成 + 最多 4 次 Embedding（有缓存）
- **groundedness**：最多 30 次逐句判断（串行，有 cap），每条用例 1-30 次 LLM 调用

单次 LLM 调用 1-5s，每条用例 L2 实际耗时 **10-150s**。N=50 时总耗时可达 `50 × 150s = 7500s`（极端情况），典型场景约 `50 × 30s = 1500s`（25 分钟）。**内层串行循环（claim 验证、sentence 判断）也是瓶颈。**

#### 瓶颈 2：六层诊断逐层串行执行

**文件**: `backend/src/service/rag_eval/metrics/diagnosis/orchestrator.py:60-61`

```python
for layer_num in sorted(self._layers.keys()):
    result = await self.run_layer(layer_num, run_id, results, run_data)
```

6 层诊断严格串行。如果每层平均 2-5s（其中 Layer 3 涉及 LLM 调用），总耗时 12-30s。

#### 瓶颈 3：ReportBuilder.build 三条 DB 查询串行

**文件**: `backend/src/service/rag_eval/report/builder.py:45-59`

```python
run = await self._run_repo.get_by_id(run_id)
# ...
bad_cases = self._build_bad_cases(await self._result_repo.get_failed_results_by_run(run_id))
tuning = self._build_tuning(await self._suggestion_repo.get_by_run_id(run_id))
```

3 次 DB 查询串行执行，每次 50-200ms，累计 150-600ms。

#### 瓶颈 4：报告生成为同步 HTTP POST，无异步化

**文件**: `backend/src/controller/rag_eval/report_controller.py:36`

报告生成是一个同步 HTTP POST 请求。后端 `generateReport` 方法阻塞直到全部完成后才返回。如果总耗时超过 30s，可能触发前端 HTTP 超时。

#### 瓶颈 5：前端无进度反馈

**文件**: `frontend/src/features/rag-eval/pages/RunPage.tsx:103-110`

```tsx
const handleGenerateReport = useCallback(async (runId: string) => {
  await generateReportMutation.mutateAsync(runId);
  message.success('报告已生成，可在报告页查看');
}, [generateReportMutation]);
```

用户只能看到按钮 loading 态，没有进度条、没有阶段提示、没有 SSE 连接。

#### 瓶颈 6：post_run_pipeline 前端完全无感知

测试运行完成后，`BatchTestRunner` 触发 `on_complete` 回调执行 `post_run_pipeline`（指标计算 → 报告生成）。但前端 SSE 在收到 `run_completed` 事件后就断开连接了，不会监听后续 pipeline 进度。用户以为运行已完成，但报告还需要额外等待数分钟。

---

## 二、解决方案

### 方案概览

| 优先级 | 措施 | 预期收益 | 改动范围 |
|--------|------|---------|---------|
| P0 | ScoringFacade 并行化 | 指标计算提速 3-10x | 后端 1 个文件 |
| P0 | 诊断层并行化 | 诊断提速 2-4x | 后端 1 个文件 |
| P0 | 报告生成异步化 + SSE 进度推送 | 用户体验质变 | 后端 3 文件 + 前端 3 文件 |
| P1 | ReportBuilder DB 查询并行化 | 提速 200-400ms | 后端 1 个文件 |
| P1 | post_run_pipeline SSE 串联 | 运行→报告一体化进度 | 后端 1 文件 + 前端 1 文件 |
| P2 | PDF 导出异步化 | 避免阻塞事件循环 | 后端 1 个文件 |

---

### P0-1：ScoringFacade 并行化（外层 + 内层）

**涉及文件**：
- `backend/src/service/rag_eval/metrics/scoring/facade.py`（外层并行）
- `backend/src/service/rag_eval/metrics/scoring/calculators/faithfulness_calc.py`（内层并行）
- `backend/src/service/rag_eval/metrics/scoring/calculators/groundedness_calc.py`（内层并行）

#### 外层并行：facade.py

将逐条串行循环改为 `asyncio.gather` 并行，使用 Semaphore 控制并发度：

```python
async def calculate_all(self, results: list[MetricInput]) -> RunMetrics:
    if not results:
        return self._empty()

    sem = asyncio.Semaphore(10)  # DashScope qwen-plus 默认 200 QPS，10 并发安全

    async def _score_one(rd):
        async with sem:
            l1, l2, l3 = await asyncio.gather(
                self._retrieval.score_all(rd),
                self._generation.score_all(rd),
                self._system.score_all(rd),
            )
            return l1, l2, l3

    scored = await asyncio.gather(*[_score_one(rd) for rd in results])
    all_l1 = [s[0] for s in scored]
    all_l2 = [s[1] for s in scored]
    all_l3 = [s[2] for s in scored]

    weights = self._get_weights()
    l1 = self._agg_l1(all_l1)
    l2 = self._agg_l2(all_l2)
    l3 = self._agg_l3(all_l3)
    overall = (weights["l1"] * self._layer_avg(l1) +
               weights["l2"] * self._layer_avg(l2) +
               weights["l3"] * self._layer_avg(l3))
    return RunMetrics(l1=l1, l2=l2, l3=l3, overall_score=round(overall, 4),
                      weights=weights, calculated_at=datetime.now(timezone.utc))
```

#### 内层并行：faithfulness_calc.py

claim 验证循环从串行改为并行：

```python
# 当前：串行逐条验证
for claim in claims:
    verified.append(await self._verify_claim(claim, context))

# 改为：并行验证所有 claims
verified = await asyncio.gather(*[self._verify_claim(c, context) for c in claims])
```

#### 内层并行：groundedness_calc.py

sentence 判断循环从串行改为并行：

```python
# 当前：串行逐句判断
for sent in sentences:
    scores.append(await self._judge_support(sent, context))

# 改为：并行判断所有 sentences（已有 cap=30，不会过度并发）
scores = await asyncio.gather(*[self._judge_support(s, context) for s in sentences])
```

**风险控制**：外层 Semaphore(10) 限制用例级并发。内层 faithfulness 的 claim 数通常 <10，groundedness 已 cap=30，不会导致并发爆炸。三层 scorer 之间已有 `asyncio.gather` 并行（generation.py:24-26），叠加外层 10 并发，最坏情况瞬时 LLM 调用数约 `10 × 30 = 300`，但实际受 Semaphore 和 DashScope 200 QPS 双重限制。

---

### P0-2：六层诊断并行化

**文件**: `backend/src/service/rag_eval/metrics/diagnosis/orchestrator.py`

将逐层串行改为并行（各层之间无依赖关系）：

```python
async def run_all(self, run_id, results, run_data) -> DiagnosisResult:
    """并行执行全部 6 层诊断（各层独立，无依赖）"""

    async def _safe_run(layer_num):
        try:
            return await self.run_layer(layer_num, run_id, results, run_data)
        except Exception as e:
            logger.error(f"诊断层 {layer_num} 执行异常: {e}")
            return LayerResult(
                layer=layer_num, name=f"Layer{layer_num}", status="error",
                score=0.0, total_cases=len(results), affected_cases=0,
                issues=[LayerIssue(severity="critical", category="execution_error",
                                   description=f"层 {layer_num} 执行异常: {str(e)}",
                                   affected_items=[run_id])],
                execution_time_ms=0,
            )

    layer_results = await asyncio.gather(
        *[_safe_run(n) for n in sorted(self._layers.keys())]
    )
    # ... 后续聚合逻辑不变
```

**风险控制**：如果某层诊断依赖前一层结果（当前代码无此依赖），需改为分组并行。当前 6 层互相独立，可安全并行。

---

### P0-3：报告生成异步化 + SSE 进度推送（核心改动）

#### 后端改动

**1. 新增报告生成 SSE 事件定义**

在 `TaskSsePublisher` 中扩展事件类型，支持报告生成阶段推送：

```
report_started     → 开始生成报告
metrics_computing  → 指标计算中
metrics_done       → 指标计算完成
diagnosis_running  → 六层诊断中
diagnosis_done     → 六层诊断完成
building_report    → 构建报告数据
rendering          → 渲染 Markdown
saving             → 保存报告
report_completed   → 报告生成完成
report_failed      → 报告生成失败
```

**2. 修改 report_controller.py：POST 改为异步任务**

```python
@router.post("/reports")
async def generate_report(body: ReportGenerateRequest):
    """异步生成报告，返回 task_id 供前端订阅 SSE"""
    task_id = await report_engine.start_generate_report(body.run_id)
    return APIResponse.success({"task_id": task_id, "run_id": body.run_id})
```

**3. 新增 report_engine.start_generate_report 方法**

在 `ReportEngineFacade` 中新增异步任务入口，通过 `AsyncTaskManager` 启动后台任务，并在每个阶段通过 `SSEPublisher` 推送进度：

```python
async def start_generate_report(self, run_id: str) -> str:
    task_id = generate_id()
    # 启动后台任务
    await AsyncTaskManager.get_instance().start_task(
        task_id=task_id,
        task_type="report_generation",
        coro=self._generate_report_with_progress(run_id, task_id),
    )
    return task_id

async def _generate_report_with_progress(self, run_id: str, task_id: str):
    channel = f"report_generation:{task_id}"
    try:
        await self._sse.publish(channel, {"type": "report_started", "data": {"run_id": run_id}})

        # 阶段 1：指标计算
        await self._sse.publish(channel, {"type": "metrics_computing", "data": {}})
        if not run.l1_metrics_json:
            await self._compute_metrics(run_id, run)
        await self._sse.publish(channel, {"type": "metrics_done", "data": {}})

        # 阶段 2：构建报告
        await self._sse.publish(channel, {"type": "building_report", "data": {}})
        data = await self._b.build(run_id)

        # 阶段 3：渲染
        await self._sse.publish(channel, {"type": "rendering", "data": {}})
        md = self._r.render(data)

        # 阶段 4：保存
        await self._sse.publish(channel, {"type": "saving", "data": {}})
        # ... 保存逻辑 ...

        await self._sse.publish(channel, {"type": "report_completed", "data": {"report_id": rid}})
    except Exception as e:
        await self._sse.publish(channel, {"type": "report_failed", "data": {"error": str(e)}})
```

**4. 新增 SSE 流端点**

在 `report_controller.py` 中新增：

```python
@router.get("/reports/generation/{task_id}/stream")
async def stream_report_generation(task_id: str):
    return EventSourceResponse(sse_publisher.subscribe(f"report_generation:{task_id}"))
```

#### 前端改动

**1. 修改 generateReport API 调用**

```typescript
// api/rag-eval/reports.ts
export async function generateReport(runId: string): Promise<{ task_id: string; run_id: string }> {
  const res = await apiClient.post('/api/v1/rag/eval/reports', { run_id: runId });
  return res.data;
}
```

**2. 新增 useReportGenerationProgress hook**

参考 `useDraftGenerationProgress` 实现，订阅 `/api/v1/rag/eval/reports/generation/{taskId}/stream`：

```typescript
const STAGE_MAP = {
  report_started: { label: '开始生成', progress: 5 },
  metrics_computing: { label: '计算指标', progress: 20 },
  metrics_done: { label: '指标完成', progress: 40 },
  diagnosis_running: { label: '六层诊断', progress: 50 },
  diagnosis_done: { label: '诊断完成', progress: 60 },
  building_report: { label: '构建报告', progress: 75 },
  rendering: { label: '渲染报告', progress: 85 },
  saving: { label: '保存中', progress: 95 },
  report_completed: { label: '完成', progress: 100 },
  report_failed: { label: '失败', progress: 0 },
};
```

**3. 修改 RunPage.tsx 报告生成按钮**

替换同步 mutation 为异步任务 + SSE 进度：

```tsx
const [reportProgress, setReportProgress] = useState<Record<string, number>>({});

const handleGenerateReport = useCallback(async (runId: string) => {
  const { task_id } = await generateReport(runId);
  startReportSSE(task_id, runId, setReportProgress);
}, []);

// 在表格中显示进度
const renderProgress = (record) => {
  const pct = reportProgress[record.id];
  if (pct !== undefined) {
    return <Progress percent={pct} size="small" />;
  }
  // ... 原有逻辑
};
```

---

### P1-1：ReportBuilder DB 查询并行化

**文件**: `backend/src/service/rag_eval/report/builder.py`

```python
async def build(self, run_id: str) -> EvalReportData:
    run = await self._run_repo.get_by_id(run_id)
    if run is None:
        raise TestRunNotFoundException(run_id)

    # 并行查询三个数据源
    failed_results, suggestions = await asyncio.gather(
        self._result_repo.get_failed_results_by_run(run_id),
        self._suggestion_repo.get_by_run_id(run_id),
    )

    l1_json = run.l1_metrics_json or {}
    l2_json = run.l2_metrics_json or {}
    l3_json = run.l3_metrics_json or {}
    diag_json = run.diagnosis_json or {}

    metrics = self._parse_metrics(l1_json, l2_json, l3_json, {
        "overall_score": run.overall_score or 0.0,
        "weights": {"l1": 0.4, "l2": 0.4, "l3": 0.2},
    })
    bad_cases = self._build_bad_cases(failed_results)
    tuning = self._build_tuning(suggestions)

    return EvalReportData(
        summary=self._build_summary(run, metrics, diag_json),
        scoring_dashboard=self._build_dashboard(l1_json, l2_json, l3_json),
        diagnosis_details=self._build_diagnosis(diag_json),
        bad_cases=bad_cases,
        tuning_suggestions=tuning,
    )
```

---

### P1-2：post_run_pipeline SSE 串联

**问题**：测试运行完成后，`post_run_pipeline` 静默执行，前端无感知。

**方案**：复用已有的 `test_run:{run_id}` SSE channel，在 pipeline 各阶段推送事件。

修改 `orchestrator.py` 的 `post_run_pipeline`，接收 `sse_publisher` 和 `channel` 参数，在每个阶段推送进度事件。前端 `RunPage.tsx` 的 SSE 监听在收到 `run_completed` 后不要立即断开，继续监听 `metrics_computing`、`report_completed` 等事件。

---

### P2：PDF 导出异步化

**文件**: `backend/src/service/rag_eval/report/exporter.py`

WeasyPrint 是 CPU-bound 操作，会阻塞 asyncio 事件循环。改用 `asyncio.to_thread` 或 `loop.run_in_executor`：

```python
async def export_pdf(self, report: EvalReportRead) -> bytes:
    import markdown
    from weasyprint import HTML

    markdown_content = report.markdown_content or ""
    html_body = markdown.markdown(markdown_content, extensions=["tables", "fenced_code"])
    html_doc = f"<!DOCTYPE html>..."  # 同前

    # 在线程池中执行 CPU-bound 的 PDF 渲染
    pdf_bytes = await asyncio.get_event_loop().run_in_executor(
        None, lambda: HTML(string=html_doc).write_pdf()
    )
    return pdf_bytes
```

---

## 三、预期效果

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 指标计算耗时（50 用例） | ~25min（L2 LLM 串行为主） | ~1-3min（外层+内层并行，Semaphore=10） |
| 六层诊断耗时 | ~12-30s（串行） | ~3-8s（并行，Semaphore=3） |
| 报告构建 DB 查询 | ~150-600ms（串行） | ~50-200ms（并行） |
| 用户感知等待时间 | 25min+ 无反馈 | 实时进度条，~3-5min |
| 运行完成后报告感知 | 静默等待，无感知 | SSE 推送，一体化进度 |

---

## 四、实施建议

1. **先做 P0-1**（ScoringFacade 外层+内层并行化，收益最大——从 25min 降至 1-3min）
2. **再做 P0-2**（六层诊断并行化，改动小，收益明确）
3. **再做 P0-3**（异步化 + SSE，需要前后端联调）
4. **最后做 P1 和 P2**（锦上添花）
5. 每个 P0 措施独立可验证，可以分 PR 提交
6. **注意**：P0-1 实施时需同步确认 DashScope 实际 QPS 是否满足并发需求，必要时调整 Semaphore 值
