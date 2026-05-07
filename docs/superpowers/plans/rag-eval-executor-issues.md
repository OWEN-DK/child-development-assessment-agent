# RAG 评估执行器问题诊断报告

> 日期: 2026-05-06
> 触发: 测试用例 tc_5616a88fc2ed 执行超时 (30000ms)

## 问题总览

| # | 严重度 | 问题 | 文件 |
|---|--------|------|------|
| 1 | **P0** | executor 层 30s 超时与 RAG 流水线不匹配 | executor.py:64-67 |
| 2 | **P0** | `execute_single` 未传递 retrieval/generation 函数 | facade.py:103-108 |
| 3 | **P1** | 无答案也标记 `passed = True` | executor.py:61-68 |
| 4 | **P1** | 空 ID 污染检索指标 | executor.py:60 |
| 5 | **P2** | `_get_config_int` 重复定义 | executor.py:173, batch_runner.py:265 |
| 6 | **P2** | `age`/`domain` 参数透传但未使用 | batch_runner.py:199 |
| 7 | **P1** | `age`/`domain` 弃用残留未清理（42 个文件） | 见下方详细清单 |

---

## 问题 1: executor 层 30s 超时与 RAG 流水线不匹配

**位置**: [executor.py:64-67](backend/src/service/rag_eval/run/executor.py#L64-L67)

**现状**:

```python
await asyncio.wait_for(
    _retrieve_and_generate(),
    timeout=timeout_ms / 1000.0,  # 30s
)
```

检索 + 生成串行执行，共享一个 30s 超时窗口。但 RAG 流水线内部每步都可能调用 LLM：

| 阶段 | 可能耗时 |
|------|---------|
| 查询分类 (LLM) | 2-5s |
| 查询拆解 (LLM, 复杂查询) | 2-5s |
| 同义词扩展 (LLM) | 2-5s |
| BM25 + 向量检索 | 1-3s |
| 重排序 (LLM) | 2-5s |
| 答案生成 (LLM) | 5-15s |
| **总计** | **14-38s** |

RAG 流水线自身已有步骤级超时保护（orchestrator.py:131-152），LLM 适配器也有独立超时。外层 30s 是多余的粗暴限制。

**建议**: 去掉 `asyncio.wait_for`，改为仅保留极宽松的安全网（如 300s）防止协程泄漏，或直接移除由子系统自行管理超时。

---

## 问题 2: `execute_single` 未传递 retrieval/generation 函数

**位置**: [facade.py:103-108](backend/src/service/rag_eval/run/facade.py#L103-L108)

**现状**:

```python
async def execute_single(self, run_id: str, case_id: str) -> TestRunResultItem:
    case = await self._case_engine.get_case(case_id)
    if not case:
        raise TestCaseNotFoundException(case_id)
    return await self._executor.execute(test_case=case, run_id=run_id)
    # ❌ 没有传 retrieval_fn 和 generation_fn
```

executor 收到的 `retrieval_fn=None`, `generation_fn=None`，跳过检索和生成，直接标记 `passed = True` 并写入空结果。

**根因**: retrieval/generation 函数的构建逻辑在 `BatchTestRunner._execute_with_semaphore()` 中（闭包），`RunEngineFacade` 没有独立的构建路径。

**建议**: 将 retrieval/generation 函数的构建逻辑提取为 `RunEngineFacade` 的方法，`execute_single` 和 `batch_runner` 共用。

---

## 问题 3: 无答案也标记 `passed = True`

**位置**: [executor.py:61-68](backend/src/service/rag_eval/run/executor.py#L61-L68)

**现状**:

```python
if generation_fn and retrieved_ids:
    actual_answer = await generation_fn(test_case.query, retrieved_ids)
# ...
passed = True  # 无论 actual_answer 是否为 None
```

当 `generation_fn` 返回 `None`（如检索结果无内容、上下文为空）时，`actual_answer` 为空但仍标记 `passed = True`。

**建议**: `passed` 判定应要求 `actual_answer is not None`。

---

## 问题 4: 空 ID 污染检索指标

**位置**: [executor.py:60](backend/src/service/rag_eval/run/executor.py#L60)

**现状**:

```python
retrieved_ids = [
    (d.get("id", "") if isinstance(d, dict) else getattr(d, "id", "") or "")
    for d in (retrieved or [])
]
```

当 `id` 为空字符串或 `None` 时，仍加入 `retrieved_ids`。后果：
- `actual_count` 虚高
- `precision` 被稀释
- `mrr`/`ndcg`/`hit_rate` 计算失真

**建议**: 过滤掉空 ID：`[x for x in retrieved_ids if x]`。

---

## 问题 5: `_get_config_int` 重复定义

**位置**:
- [executor.py:173-181](backend/src/service/rag_eval/run/executor.py#L173-L181)
- [batch_runner.py:265-272](backend/src/service/rag_eval/run/batch_runner.py#L265-L272)

两个类各写了一遍完全相同的 `_get_config_int`（batch_runner 还多一个 `_get_config_str`）。

**建议**: 提取到 `ConfigCache` 或共用 mixin。

---

## 问题 6: `age`/`domain` 参数透传但未使用

**位置**: [batch_runner.py:199](backend/src/service/rag_eval/run/batch_runner.py#L199)

**现状**:

```python
async def _retrieval(query, age, domain):
    results = await self._retrieval.retrieve_knowledge(query, limit=5)
    # age、domain 未被使用
```

executor 调用 `retrieval_fn(test_case.query, test_case.age, test_case.domain)`，闭包接收但未转发。属于死参数（项目已移除 age/domain 过滤）。

**建议**: 清理 executor 调用签名和闭包参数。

---

## 问题 7: `age`/`domain` 弃用残留未清理

commit 8b39530c 移除了 age/domain 过滤系统，但代码中仍有大量残留。以下按是否属于 RAG 评估模块分为两类。

### 7a. RAG 评估模块内的残留（需清理）

这些直接属于 rag_eval 模块，与已移除的过滤系统耦合。**关键事实：这些字段从未被实际赋值。** 草稿提升为测试用例时 `age=None, domain=None` 硬编码（[draft/facade.py:277](backend/src/service/rag_eval/draft/facade.py#L277)），手动创建和 JSON 导入均为 `Optional` 无默认值。数据库中这些字段全部为 NULL。

**数据库模型** — [test_case.py](backend/src/models/rag_eval/test_case.py)

| 行号 | 字段 | 说明 |
|------|------|------|
| 17-19 | `age: DECIMAL(4,1)` | 测试用例年龄字段 |
| 20-22 | `age_stage_label: String(20)` | 年龄段标签 |
| 23-28 | `domain: Enum(TestDomain)` | 测试领域枚举 |
| 39-41 | `min_age_requirement: DECIMAL(4,1)` | 最小年龄要求 |
| 42-44 | `max_age_requirement: DECIMAL(4,1)` | 最大年龄要求 |

**枚举定义** — [enums.py](backend/src/models/rag_eval/enums.py):4-11 — `TestDomain` 枚举仍完整存在

**Pydantic Schemas**

| 文件 | 行号 | 字段 |
|------|------|------|
| [schemas/rag_eval/test_case.py](backend/src/schemas/rag_eval/test_case.py) | 15-16 | `TestCaseCreate.age`, `TestCaseCreate.domain` |
| 同上 | 47-48 | `TestCaseUpdate.age`, `TestCaseUpdate.domain` |
| 同上 | 69-70 | `TestCaseImportItem.age`, `TestCaseImportItem.domain` |
| [schemas/rag_eval/report.py](backend/src/schemas/rag_eval/report.py) | 62-63 | `BadCaseEntry.domain`, `BadCaseEntry.age` |

**控制器** — [case_controller.py](backend/src/controller/rag_eval/case_controller.py):43-45 — `list_cases` 仍接受 `domain` 查询参数

**服务层**

| 文件 | 行号 | 残留 |
|------|------|------|
| [case/case_service.py](backend/src/service/rag_eval/case/case_service.py) | 42, 63-65 | 创建/更新时计算 `age_stage_label` |
| 同上 | 87, 94-95 | `list_cases` 的 `domain` 过滤 |
| 同上 | 131-148 | 导入时校验 `domain` 枚举、计算 `age_stage_label` |
| [case/facade.py](backend/src/service/rag_eval/case/facade.py) | 49, 53 | `list_cases` 透传 `domain` |
| [draft/facade.py](backend/src/service/rag_eval/draft/facade.py) | 277 | 提升用例时 `age=None, domain=None` |
| [draft_deduplicator.py](backend/src/service/draft_deduplicator.py) | 50, 54 | 去重逻辑使用 `domain` 和 `age` |
| [report/builder.py](backend/src/service/rag_eval/report/builder.py) | 152, 161 | 报告构建读取 `domain`/`age` |
| [report/exporter.py](backend/src/service/rag_eval/report/exporter.py) | 49, 54-55 | CSV 导出包含"领域""年龄"列 |
| [report/markdown_renderer.py](backend/src/service/rag_eval/report/markdown_renderer.py) | 80-81 | Markdown 报告包含 age/domain 列 |
| [run/executor.py](backend/src/service/rag_eval/run/executor.py) | 59 | 调用 `retrieval_fn(test_case.query, test_case.age, test_case.domain)` |
| [run/batch_runner.py](backend/src/service/rag_eval/run/batch_runner.py) | 199 | 闭包接收 `age, domain` 但未使用 |
| [metrics/scoring/calculators/precision_recall.py](backend/src/service/rag_eval/metrics/scoring/calculators/precision_recall.py) | 143, 175 | 注释引用 domain/age 规则 |

**工具函数** — [utils/age_stage.py](backend/src/utils/age_stage.py):7-37 — `calculate_age_stage_label()` 整个文件

**序列化** — [utils/serializers.py](backend/src/utils/serializers.py):162-163 — `age: float`, `domain: safe_enum_value`

**Prompt 初始化**

| 文件 | 行号 | 残留 |
|------|------|------|
| [core/prompt_impl/initializer.py](backend/src/core/prompt_impl/initializer.py) | 69, 78, 105, 114 | prompt 变量含 `domain`, `age_stage_label`, `age` |
| [scripts/init_prompts.py](backend/scripts/init_prompts.py) | 28, 49, 63, 70 | 同上 |

**模块导出** — `TestDomain` 仍在以下 `__init__.py` 中导出：
- [models/rag_eval/__init__.py](backend/src/models/rag_eval/__init__.py):6,28
- [models/__init__.py](backend/src/models/__init__.py):13,33
- [schemas/rag_eval/__init__.py](backend/src/schemas/rag_eval/__init__.py):7,84

**前端**

| 文件 | 行号 | 残留 |
|------|------|------|
| [entities/rag-eval/types.ts](frontend/src/entities/rag-eval/types.ts) | 70, 72, 88, 142, 238-239, 362 | `age`/`domain` 类型定义 |
| [entities/rag-eval/enums.ts](frontend/src/entities/rag-eval/enums.ts) | 4-10 | `TestDomain` 类型 |
| [entities/rag-eval/constants.ts](frontend/src/entities/rag-eval/constants.ts) | 12-29, 97-124 | `DOMAIN_MAP`, `DOMAIN_COLORS`, `AGE_STAGES`, `getAgeStage` |
| [entities/rag-eval/mappers.ts](frontend/src/entities/rag-eval/mappers.ts) | 18-36 | `formatDomain`, `formatAge`, `formatAgeRange` |
| [api/rag-eval/cases.ts](frontend/src/api/rag-eval/cases.ts) | 12, 30, 39 | API 参数含 `domain`/`age` |
| [features/rag-eval/hooks/useTestCases.ts](frontend/src/features/rag-eval/hooks/useTestCases.ts) | 7, 38 | hook 参数含 `domain`/`age` |
| [features/rag-eval/components/common/DomainTag.tsx](frontend/src/features/rag-eval/components/common/DomainTag.tsx) | 6, 9-10 | `DomainTag` 组件 |
| [features/rag-eval/components/report/BadCaseTable.tsx](frontend/src/features/rag-eval/components/report/BadCaseTable.tsx) | 11-12, 28-36 | 列定义含 domain/age |
| [features/rag-eval/components/test-set/CaseTransferModal.tsx](frontend/src/features/rag-eval/components/test-set/CaseTransferModal.tsx) | 20, 36, 88 | 穿梭框含 domain |
| [features/rag-eval/pages/TestCasePage.tsx](frontend/src/features/rag-eval/pages/TestCasePage.tsx) | 26, 58, 88, 120, 137-138 | 筛选/表单含 domain/age |
| [features/rag-eval/pages/ReportDetailPage.tsx](frontend/src/features/rag-eval/pages/ReportDetailPage.tsx) | 70-71 | 映射 domain/age |
| [entities/rag-eval/index.ts](frontend/src/entities/rag-eval/index.ts) | 2, 48-49 | 导出 `TestDomain`, `DOMAIN_MAP`, `DOMAIN_COLORS` |

### 7b. 评估模块（assessment）— 活跃业务，保留

`ChildProfile.age` 是评估流程的必填输入（`Field(...)` 无默认值），在 LangGraph 主工作流 5 个节点中被实际读取：

| 节点 | 文件:行号 | 用途 |
|------|----------|------|
| AssessmentNode | [assessment.py:49,54](backend/src/core/nodes/assessment.py#L49) | 查年龄里程碑、写入 LLM prompt |
| ValidationNode | [validation.py:72,140](backend/src/core/nodes/validation.py#L72) | 传入 LLM 做强度/类别推断 |
| ScoringNode | [scoring.py:179,194,225](backend/src/core/nodes/scoring.py#L179) | 年龄适配性评分（占 AHP 30% 权重） |
| ReportingNode | [reporting.py:305](backend/src/core/nodes/reporting.py#L305) | 写入最终报告 |
| QwenScorer | [qwen_scorer.py:37](backend/src/core/ml/qwen_scorer.py#L37) | 传入 ML 评分器 |

这些是评估业务的核心逻辑（"这个运动计划对 3 岁孩子是否安全"），和 RAG 检索过滤的 age/domain 是完全不同的语义。**保留，不清理。**

相关保留项：
- [schemas/assessment.py:45](backend/src/schemas/assessment.py#L45) — `ChildProfile.age` 必填字段
- [config/rules/rules.json:33](backend/src/config/rules/rules.json#L33) — `weight_age: 0.3`
- [config/rules/rules.py:91-98](backend/src/config/rules/rules.py#L91) — `age_milestones` 配置
- [core/prompts_fallback.py](backend/src/core/prompts_fallback.py) — prompt 模板中的 `{age}` 变量
- [frontend/src/entities/assessment/types.ts:15](frontend/src/entities/assessment/types.ts#L15) — `ChildProfile.age`
- [frontend/src/components/assessment/AssessmentForm.tsx:54](frontend/src/components/assessment/AssessmentForm.tsx#L54) — 表单字段
- [frontend/src/shared/lib/validators.ts:45](frontend/src/shared/lib/validators.ts#L45) — `validateAge`

### 7c. 评估模块内的死代码（需清理）

以下两个类在生产代码中**无任何调用**，仅被测试/诊断脚本引用：

| 文件 | 说明 |
|------|------|
| [core/child_development_engine.py](backend/src/core/child_development_engine.py) (全文 172 行) | `ChildDevelopmentRuleEngine` — 年龄适配度计算、内容过滤、推荐生成。ScoringNode 中的年龄逻辑是自行实现的，不依赖此类 |
| [core/rag/boundary_handler.py](backend/src/core/rag/boundary_handler.py):122-184 | `get_development_stage` / `map_age到_stage_range` — 发展阶段映射。无生产调用，且方法名含中文字符 |

此外，`BookChunksPage.tsx:117` 中的 `target_age_min`/`target_age_max` 是文档元数据展示，与过滤系统无关，保留。

---

## 修复方案概要

| 问题 | 改动范围 | 方案 |
|------|---------|------|
| #1 超时 | executor.py | 移除 `asyncio.wait_for`，保留 300s 安全网或完全移除 |
| #2 execute_single | facade.py + batch_runner.py | 提取 retrieval/generation 构建逻辑到 facade，两处共用 |
| #3 passed 判定 | executor.py | 增加 `actual_answer is not None` 条件 |
| #4 空 ID | executor.py | 过滤空值 |
| #5 重复方法 | executor.py + batch_runner.py | 提取到 ConfigCache 或工具类 |
| #6 死参数 | executor.py + batch_runner.py | 清理签名 |
| #7 age/domain 残留 | 后端 25 文件 + 前端 17 文件 | RAG 评估模块内全部移除；评估模块（assessment）保留 |
