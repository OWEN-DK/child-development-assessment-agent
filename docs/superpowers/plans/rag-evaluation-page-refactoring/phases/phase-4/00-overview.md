# Phase 4: 6 层校验引擎 — 总览

> **需求来源**: spec 文档 `05-validation-layers.md`
> **需求点数量**: 17 个
> **优先级**: P1

## 目标

实现 6 层校验引擎，支持异步/并行/降级执行，总体超时 5 分钟。

## 需求点清单

### 编排器 (1 个)

| # | 需求点 | 实施文件 | 说明 |
|---|--------|---------|------|
| 1 | ValidationOrchestrator 编排器 | `01-validation-orchestrator.md` | 协调 6 层校验，支持异步/并行/降级执行 |

### Layer 1-2: 快速规则 (2 个)

| # | 需求点 | 实施文件 | 校验数 | 延迟 |
|---|--------|---------|--------|------|
| 2 | Layer 1: 规则引擎 | `02-layer1-rule-engine.md` | 8 条规则（P@5/R@5/F1/MRR/短查询/跨领域/PageIndex/参数安全范围） | <50ms |
| 3 | Layer 2: 历史对比 | `03-layer2-history-comparison.md` | 2 条规则（配置变更关联/相似问题匹配） | <100ms |

### Layer 3: LLM 诊断 (1 个)

| # | 需求点 | 实施文件 | 说明 |
|---|--------|---------|------|
| 4 | Layer 3: LLM 诊断 | `04-layer3-llm-diagnosis.md` | Bad Case 语义分析，7 种失败类型 + 8 种根因，降级策略 |

### Layer 4: 数据质量 (3 个)

| # | 需求点 | 实施文件 | 校验 | 延迟 |
|---|--------|---------|------|------|
| 5 | Layer 4a: Golden 覆盖度 | `05-layer4a-golden-coverage.md` | 书籍/章节/领域覆盖率 | <500ms |
| 6 | Layer 4b: 分块质量评分 | `06-layer4b-chunk-quality.md` | 信息密度/结构化/切分合理性 | <500ms |
| 7 | Layer 4c: 文档时效性 | `07-layer4c-document-staleness.md` | 按文档类型分类的过期标记 | <500ms |

### Layer 5: 检索链路 (3 个)

| # | 需求点 | 实施文件 | 校验 | 延迟 |
|---|--------|---------|------|------|
| 8 | Layer 5a: Embedding 质量 | `08-layer5a-embedding-quality.md` | 同义对相似度 + silhouette + 异常检测 | <1s |
| 9 | Layer 5b: 意图识别准确率 | `09-layer5b-intent-accuracy.md` | 整体准确率 + 低置信度查询 | <1s |
| 10 | Layer 5c: 错误模式分组 | `10-layer5c-error-patterns.md` | 多维交叉分组 + 修复方案映射 | <1s |

### Layer 6: 验证保障 (4 个)

| # | 需求点 | 实施文件 | 校验 | 延迟 |
|---|--------|---------|------|------|
| 11 | Layer 6a: 回归检测 | `11-layer6a-regression-detection.md` | 指标退化标记 | 5-30s |
| 12 | Layer 6b: 交叉验证 | `12-layer6b-cross-validation.md` | 各组指标一致性 | 5-30s |
| 13 | Layer 6c: 成本效果分析 | `13-layer6c-cost-effectiveness.md` | 成本效果比 = 指标提升 / 额外成本 | 5-30s |
| 14 | Layer 6d: A/B 影子测试 | `14-layer6d-ab-shadow-test.md` | 分层抽样 + 配对 t-test + p-value | 5-30s |

### 策略 (2 个)

| # | 需求点 | 实施文件 | 说明 |
|---|--------|---------|------|
| 15 | 超时与降级策略 | `15-timeout-degradation-strategy.md` | 总体 5 分钟超时，单层层超时，降级标记 |
| 16 | 并发限制（最多 3 个） | `16-concurrency-limit.md` | 队列上限 10，超出返回 503 |
| 17 | Layer 6 手动触发 API | `17-layer6-manual-trigger-api.md` | 独立端点触发，SSE 推送结果 |

## 验收标准

- [ ] 6 层校验引擎全部实现（13 种校验）
- [ ] 校验总耗时 < 5 分钟
- [ ] 单层层超时正确标记
- [ ] 降级策略正确执行
- [ ] 并发限制正确（最多 3 个并行）
- [ ] 校验结果正确写入 TestReport.validation_results (JSON)

## 执行策略

```
执行顺序（严格按 spec 定义）：
  Layer 1/2/3/4/5 全部并行启动（互不依赖，同时执行）
  Layer 6: 用户手动触发，不阻塞报告生成

spec 数据流原文（05-validation-layers.md 6.1 节）：
  - Layer 1-2-3 并行执行（Layer 3 从 TestRun 结果获取 Bad Case，与 Layer 1-2 并行）
  - Layer 4-5 并行执行（与 Layer 1-2-3 并行，互不阻塞）
  - Layer 6 默认不执行，用户手动触发

注意：Layer 1~5 是**全并行**关系，不存在 Phase A → Phase B 的串行依赖。
      编排器应使用 asyncio.gather() 或 asyncio.create_task() 同时启动所有 Layer。

超时策略说明：
- 总体超时：rag_validation_timeout_total（默认 300s），从配置中心读取
- Layer 4 的超时（30s）是**每个子层独立超时 30s**，不是三个子层共享 30s
- Layer 5 的超时（30s）同理，每个子层独立超时
- 即 Layer 4a/4b/4c 各自最多跑 30s，Layer 5a/5b/5c 各自最多跑 30s
- 由于全并行执行，总耗时取决于最慢的 Layer，而非各层耗时之和
- 编排器中 _run_layer() 对每个子层独立调用 asyncio.wait_for()，是独立超时

并发限制说明：
- "最多 3 个并行" 指的是 report 级别的并发（同时最多 3 个 TestReport 在校验）
- 单个 TestReport 内部的 Layer 子层并行不受此限制
- Semaphore 控制的是 report 级别，不是 layer 级别
- 队列上限 10，超出返回 503

DB Session 安全说明：
- 编排器接收 session_factory（而非单个 session），每个 layer 通过 factory 创建独立 session
- 避免并行协程共享同一 AsyncSession 导致 SQLAlchemy 异步冲突
- _create_report 也使用独立 session + async with session.begin() 管理事务（CLAUDE.md 要求）
```

---

**文档索引**: 
- 上一节: [Phase 3 总览](../phase-3/00-overview.md)
- 下一节: 
  - [01-validation-orchestrator.md](./01-validation-orchestrator.md) — 需求点 1
  - [02-layer1-rule-engine.md](./02-layer1-rule-engine.md) — 需求点 2
  - [03-layer2-history-comparison.md](./03-layer2-history-comparison.md) — 需求点 3
  - [04-layer3-llm-diagnosis.md](./04-layer3-llm-diagnosis.md) — 需求点 4
  - [05-layer4a-golden-coverage.md](./05-layer4a-golden-coverage.md) — 需求点 5
  - [06-layer4b-chunk-quality.md](./06-layer4b-chunk-quality.md) — 需求点 6
  - [07-layer4c-document-staleness.md](./07-layer4c-document-staleness.md) — 需求点 7
  - [08-layer5a-embedding-quality.md](./08-layer5a-embedding-quality.md) — 需求点 8
  - [09-layer5b-intent-accuracy.md](./09-layer5b-intent-accuracy.md) — 需求点 9
  - [10-layer5c-error-patterns.md](./10-layer5c-error-patterns.md) — 需求点 10
  - [11-layer6a-regression-detection.md](./11-layer6a-regression-detection.md) — 需求点 11
  - [12-layer6b-cross-validation.md](./12-layer6b-cross-validation.md) — 需求点 12
  - [13-layer6c-cost-effectiveness.md](./13-layer6c-cost-effectiveness.md) — 需求点 13
  - [14-layer6d-ab-shadow-test.md](./14-layer6d-ab-shadow-test.md) — 需求点 14
  - [15-timeout-degradation-strategy.md](./15-timeout-degradation-strategy.md) — 需求点 15
  - [16-concurrency-limit.md](./16-concurrency-limit.md) — 需求点 16
  - [17-layer6-manual-trigger-api.md](./17-layer6-manual-trigger-api.md) — 需求点 17
