# 06 — RAG 评估系统

> **定位**：测试搜索管道效果的完整评估体系。用户上传测试数据集 → 选择管道版本 → 运行评估 → 获取指标/诊断/报告 → 采纳调优建议 → 再次评估，形成"配置 → 评估 → 调优 → 再评估"闭环。
> **与核心目标的关系**：实现 [核心目标 §五](./core-objectives.md#五rag-评估测试搜索管道效果)，完整继承现有 `backend/` 评估体系并扩展到跨域评估。

---

## 继承/新增边界

本模块是继承代码量最大的模块。下方区分**从 backend/ 继承后仅需适配改造**的部分与**从零新增**的部分。

### 从 backend/ 继承 + 改造

| 继承内容 | 来源 backend/ | 改造点 |
|---------|-------------|--------|
| **12 项三层指标**（L1 5 项 + L2 3 项 + L3 4 项） | `service/rag_eval/metrics/scoring/` | 无改动，直接继承 |
| **六层诊断**（L1 规则→L6 回归检测） | `service/rag_eval/metrics/diagnosis/` | 仅 L3 LLM 诊断的 prompt 需去业务化 |
| **双轨评估架构**（指标+诊断并行） | `service/rag_eval/rag_eval_orchestrator.py` | 适配新的 PipelineCompiler 调用 |
| **草稿系统**（生成→审核→去重→导入） | `service/rag_eval/draft/` | 无改动，直接继承 |
| **测试用例 CRUD** | `controller/rag_eval/test_case_controller.py` | 新增 `relevant_domains`、`expected_conflicts` 字段 |
| **测试集管理** | `controller/rag_eval/test_set_controller.py` | 无改动，直接继承 |
| **评估运行引擎** | `service/rag_eval/run/` | 检索调用从原 RAG 管线替换为 PipelineCompiler |
| **报告生成**（Markdown/JSON/CSV） | `service/rag_eval/report/` | 新增"跨域分析"章节 |
| **调优建议** | `service/rag_eval/tuning/` | 新增跨域调优建议类型 |
| **知识库快照** | `service/rag_eval/snapshot/` | 适配新的向量后端（Chroma/ES/Milvus） |
| **SSE 进度推送** | `service/task_sse_publisher.py` | 新增跨域进度事件 |
| **趋势分析** | `service/rag_eval/trend/` | 无改动，直接继承 |
| **门面模式架构**（7 个 Facade） | `service/rag_eval/` | 保留架构，更新门面内部组件 |

### 从零新增

| 新增内容 | 说明 |
|---------|------|
| **4 项跨域扩展指标** | 域激活准确率、跨域覆盖率、冲突检测率、端到端延迟 P95 |
| **跨域指标计算器** | `metrics/scoring/calculators/cross_domain_calc.py` |
| **评估权限注入** | 评估运行注入 JWT 权限上下文；角色模拟评估 |
| **内联调优 UI** | 评估详情页内嵌调优建议卡片，支持"采纳"和"🔧 去编辑器中打开" |
| **管道版本对比评估** | 同一数据集上对比两个管道版本的指标差异 |
| **域贡献度可视化** | 评估详情页的域贡献度图表 |

### 前端改动

| 类型 | 内容 |
|------|------|
| **继承** | `ScoringDashboard`、`DiagnosisPanel`、`BadCaseTable`、`TrendChart`、`DraftTable`、SSE 进度 Store |
| **改造** | 从独立 `/rag-eval/*` 路由迁移到管道工作台内嵌 + 测试数据页 |
| **新增** | `DomainContribChart`、`InlineTuningCard`、`ConflictAlert` |

---

## 配置层级

| 层级 | 谁配置 | 存储位置 | 示例 |
|------|--------|---------|------|
| **L3: 评估运行参数** | 运行者 | 运行请求体 | 模拟角色、知识库快照选择 |
| **L2: 评估配置版本** | 租户 editor | MySQL `eval_config_versions` | 指标权重、诊断启用/禁用 |
| **L1: 租户覆盖** | 租户 admin | MySQL 全局配置表 | 默认指标阈值、默认权重、并发限制 |
| **L0: 平台默认** | 超管 / 系统内置 | `_DEFAULT_THRESHOLDS` 常量 + `.env` | 所有指标阈值兜底值、L1/L2/L3 权重 = 0.4/0.4/0.2、max_concurrent_runs=2 |

**覆盖规则**：L3 > L2 > L1 > L0。L0 提供所有指标的出厂默认阈值。租户 admin 可在 `/settings/config` 全局修改 L1。editor 创建评估配置版本覆盖 L2。单次运行时的角色模拟为 L3。

**阈值查找链**（以 context_precision 为例）：
```
ConfigCache.get("rag.eval.threshold.context_precision")
  → L2: eval_config_versions (如该运行绑定了配置版本)
    → L1: MySQL 全局配置表 (租户 admin 设置)
      → L0: _DEFAULT_THRESHOLDS["context_precision"] = 0.7
```

---

## 1. 核心评估架构

### 1.1 双轨评估

每次评估运行同时产出两条轨道：

| 轨道 | 目的 | 输出 |
|------|------|------|
| **三层标准化指标** | 横向比较、趋势跟踪 | 12 项量化指标（L1: 5 检索 + L2: 3 生成 + L3: 4 系统） |
| **六层诊断** | 深度调试、根因分析 | 具体问题定位 + 修复建议 |

两条轨道并行执行，互不阻塞。

### 1.2 评估工作流

```
创建测试用例 → 组织测试集 → 创建评估运行（选择管道版本 + 测试集）
                                    │
                                    ▼
                          执行测试（批量检索 + 答案生成）
                          每用例: 检索 → 生成答案 → 保存结果
                          SSE 实时推送进度
                                    │
                                    ▼
                          后处理流水线（自动触发）
                          ├── 双轨评估（并行）
                          │   ├── 计算 12 项指标 → RunMetrics
                          │   └── 执行 6 层诊断 → DiagnosisResult
                          └── 报告生成 → Markdown 渲染 → EvalReport
                                    │
                                    ▼
                          查看报告 → 分析调优建议 → 采纳/驳回/忽略
                          采纳 → 创建新配置版本 → 回滚支持
```

---

## 2. 三层标准化指标（12 项）

### 2.1 L1 — 检索质量（5 项）

| 指标 | 标识 | 阈值 | 说明 |
|------|------|------|------|
| Context Precision | `context_precision` | ≥ 0.7 | 检索结果中相关片段比例的加权平均（受 RAGAS 启发） |
| Context Recall | `context_recall` | ≥ 0.6 | 检索结果命中期盼知识片段的比例（受 RAGAS 启发） |
| Noise Sensitivity | `noise_sensitivity` | ≤ 0.3 | 检索结果中无关片段的比例（越低越好，阈值反转） |
| MRR | `mrr` | ≥ 0.5 | Mean Reciprocal Rank — 第一个相关结果出现位置的倒数均值 |
| NDCG | `ndcg` | ≥ 0.6 | 归一化折损累积增益，考虑排序位置的检索质量 |

### 2.2 L2 — 生成质量（3 项）

| 指标 | 标识 | 阈值 | 说明 |
|------|------|------|------|
| Faithfulness | `faithfulness` | ≥ 0.8 | 答案中被检索上下文支持的声明比例。单次 LLM 调用进行声明提取和验证（受 RAGAS 启发） |
| Answer Relevancy | `answer_relevancy` | ≥ 0.7 | 从答案反向生成问题 → 计算与原始查询的余弦嵌入相似度 |
| Groundedness | `groundedness` | ≥ 0.75 | 答案每句话在检索上下文中的溯源评分均值。单次批量 LLM 调用（受 TruLens 启发） |

### 2.3 L3 — 系统质量（4 项）

| 指标 | 标识 | 阈值 | 说明 |
|------|------|------|------|
| Rule Compliance | `rule_compliance` | = 1.0 | 测试结果满足 6 条格式和业务规则的比例 |
| Regression Score | `regression_score` | ≥ 0.9 | 与历史基线相比的稳定性。min(当前/基线, 基线/当前) 加权平均 |
| Cost Efficiency | `cost_efficiency` | ≥ 0.5 | 质量评分 / (token 成本 × 延迟)，sigmoid 归一化到 [0,1] |
| Config Stability | `config_stability` | ≥ 0.95 | 1 - avg(指标新-指标旧/指标旧)，衡量历史变化幅度 |

### 2.4 跨域扩展指标（新增）

| 指标 | 标识 | 阈值 | 说明 |
|------|------|------|------|
| 域激活准确率 | `domain_activation_acc` | ≥ 0.8 | 查询分析是否正确激活了域 |
| 跨域覆盖率 | `cross_domain_coverage` | ≥ 0.7 | 多域查询中每个应激活的域是否都有结果贡献 |
| 冲突检测率 | `conflict_detection_rate` | ≥ 0.6 | 是否正确检测出跨域矛盾 |
| 端到端延迟 P95 | `e2e_latency_p95` | — | P50/P95/P99 延迟（ms），不设硬阈值，趋势监控 |

**跨域指标的 ground truth 来源**：

| 指标 | Ground Truth 来源 | 计算方式 |
|------|------------------|---------|
| 域激活准确率 | 测试用例的 `relevant_domains` 字段（人工标注的期望激活域列表） | `准确激活数 / 期望激活数`。查询分析节点输出的激活域与 `relevant_domains` 比对 |
| 跨域覆盖率 | 测试用例的 `relevant_domains` + `domain_results` 中各域是否贡献了结果 | `有结果贡献的域数 / 期望激活域数` |
| 冲突检测率 | 测试用例中标注的已知冲突（可选字段 `expected_conflicts`）。若未标注，此指标不计入综合得分 | `检测到的冲突数 / 期望冲突数`。无 ground truth 时返回 N/A |

**不可妥协**：`relevant_domains` 是跨域指标的唯一 ground truth 来源。测试用例创建/导入时必须填写此字段，否则跨域指标返回 N/A 并从综合得分分母中排除。

### 2.5 指标权重与阈值配置

- 默认权重：L1 = 0.4, L2 = 0.4, L3 = 0.2（可配置）
- 所有阈值通过 `ConfigCache` 从全局配置读取（键：`rag.eval.threshold.{metric_name}`）
- 未设置时使用 `_DEFAULT_THRESHOLDS` 兜底

### 2.6 综合得分计算

```
overall_score = L1_score × w1 + L2_score × w2 + L3_score × w3

其中:
  L1_score = avg(各L1指标通过率)
  L2_score = avg(各L2指标通过率)
  L3_score = avg(各L3指标通过率)
```

坏案（空答案/空查询导致 N/A）不计入分母。

---

## 3. 六层诊断

全部并行执行，单层失败不影响其他层。编排器：`DiagnosisOrchestrator`。

| 层 | 名称 | 检查内容 | 阈值 |
|----|------|---------|------|
| L1 | 规则引擎 | 8 项格式规则：查询非空、答案非空、期望知识 ID 存在、指标在 [0,1] 范围、无错误消息、有效执行时间 | 强制检查 |
| L2 | 历史对比 | 与基线运行对比：核心指标退化（>5% 警告，>10% 严重）、新增失败用例 | 退化 >5% 警告 |
| L3 | LLM 诊断 | 仅针对失败用例：使用 LLM 进行偏离分析和幻觉检测。可通过配置禁用 | — |
| L4 | 数据质量 | Golden 用例覆盖率（阈值 80%）、检索分块完整性（<3 块警告）、文档时效性（>90 天未更新警告） | 覆盖率 <80% 警告 |
| L5 | 效果评估 | 嵌入质量（查询与答案余弦相似度 <0.3 警告）、错误模式聚类（全零召回、逼近超时） | 余弦 <0.3 警告 |
| L6 | 回归检测 | 全局指标回归（>5% 警告，>10% 严重）、跨测试集一致性（通过率差异 >30%）、成本效益变化 | >5% 警告 |

**诊断输出**：每层返回 `LayerResult`，包含 `LayerIssue[]`，每条 issue 包含：
- `severity`：critical / warning / info
- `category`：问题分类
- `description`：问题描述
- `affected_cases`：受影响的用例 ID 列表
- `suggestion`：修复建议

**综合健康度**：基于各层问题数量加权计算，0-100 分。

**各层容错策略**：

| 层 | 失败场景 | 行为 |
|----|---------|------|
| L1 规则引擎 | 不会失败（纯规则，无外部依赖） | — |
| L2 历史对比 | 无基线运行可对比 | 跳过该层，返回空 issue 列表，不阻塞其他层 |
| L3 LLM 诊断 | LLM API 超时/限流/返回错误 | 返回 `status: "skipped"`，`error_reason` 记录失败原因（如 `"llm_timeout"` / `"llm_rate_limited"` / `"llm_api_error"`），不阻塞其他层。诊断报告中该层标注"已跳过" |
| L4 数据质量 | 知识库快照不可用 | 跳过快照相关检查，仅执行不依赖快照的检查项 |
| L5 效果评估 | Embedding 模型不可用 | 跳过嵌入质量检查，其余检查项正常执行 |
| L6 回归检测 | 无历史数据 | 跳过该层，返回空 issue 列表 |

**不可妥协**：单层失败绝不阻塞其他层。`DiagnosisOrchestrator` 并发执行 6 层，任一层异常均被捕获并转为 `skipped` 状态。

---

## 4. 测试数据管理

### 4.1 测试用例

```json
{
  "id": "tc_001",
  "query": "高血压合并糖尿病如何用药",
  "description": "跨学科综合用药咨询",
  "expected_knowledge_ids": ["高血压指南.pdf:chunk_12", "糖尿病用药共识.pdf:chunk_5"],
  "expected_keywords": ["ACEI", "二甲双胍", "联合用药"],
  "answer_points_summary": "建议使用ACEI类药物联合二甲双胍...",
  "difficulty_level": "hard",
  "professional_terms": ["ACEI", "ARB", "胰岛素抵抗"],
  "relevance_scores": {"高血压指南.pdf": 0.9, "糖尿病用药共识.pdf": 0.85},
  "relevant_domains": ["心血管内科", "内分泌科", "药学"],
  "expected_conflicts": [
    {"statement_a": "优先使用ACEI类药物", "source_a": "高血压指南.pdf", "statement_b": "肾功能不全禁用ACEI", "source_b": "糖尿病用药共识.pdf"}
  ],
  "source": "manual",
  "version": 1
}
```

### 4.2 测试集

| 属性 | 说明 |
|------|------|
| `name` | 测试集名称 |
| `description` | 用途描述 |
| `source_type` | manual（手动创建）/ import（批量导入）/ search_history（从搜索历史导入） |
| `case_ids` | 关联的用例 ID 列表（有序） |
| `visibility` | 同知识库权限模型（public/role_scoped/private） |

### 4.3 用例导入

- 格式：CSV / JSON
- JSON 格式：`{cases: [{query, expected_answer, relevant_docs, relevant_domains, ...}]}`
- CSV 格式：第一行为列名，支持分隔符自定义
- 导入时自动去重（按 query + expected_knowledge_ids 的 MinHash 去重）

### 4.4 草稿管理（继承现有系统）

评估系统保留完整的草稿工作流：
- 从源文档自动生成测试草稿（LLM 生成 QA 对）
- 草稿审核：FaithfulnessChecker 评估草稿质量
- 草稿去重：MinHash 去重防止生成重复用例
- 审核通过后导入为正式测试用例

---

## 5. 评估运行

### 5.1 创建运行

**输入**：
- `pipeline_id`：被评估的管道
- `pipeline_version`：被评估的管道版本（默认最新）
- `test_set_ids`：测试集列表（支持多个测试集合并运行）
- `snapshot_id`：知识库快照 ID（可选，不传使用当前最新）
- `config_version_id`：评估配置版本（可选）

**行为**：
- 合并多个测试集的所有用例（去重）
- 可选：创建知识库快照（冻结检索目标状态，保证可复现）
- 运行状态 → `pending`

### 5.2 执行运行

由 `BatchTestRunner` 异步批量执行：

1. 遍历所有用例：
   - 调用 PipelineCompiler 执行管道搜索（注入运行者权限上下文）
   - 收集检索结果、各域贡献、生成答案
   - 保存 `TestRunResult`
2. SSE 实时推送进度事件
3. 全部用例完成后 → 自动触发后处理流水线

**并发控制**：
- 全局最大并发运行数：2（`rag.eval.run.max_concurrent_runs`）
- 单运行内最大并发用例数：5（`rag.eval.run.concurrency`）
- 可配置

**与生产搜索的资源隔离**：

| 资源 | 评估运行 | 生产搜索 | 隔离方式 |
|------|---------|---------|---------|
| PipelineCompiler | 共享 | 共享 | 同一实例，评估通过内部调用路径触发 |
| 搜索 QPS 配额 | **不计入** | 计入 | 评估运行走内部执行通道，不经过发布 URL / 通用端点的限流中间件 |
| LLM API 调用 | 共享 | 共享 | 共享 LLM API 的 QPS/Token 配额。评估大量并发调用可能影响生产搜索的 LLM 响应延迟 |
| 向量存储查询 | 共享 | 共享 | 同一 Collection/Index 的查询并发。评估高并发可能增加向量存储负载 |
| 并发控制 | `max_concurrent_runs` × `concurrency` | `max_search_qps` | 独立计数器，互不影响 |

**不可妥协**：评估运行不消耗租户的搜索 QPS 配额，但共享底层 LLM API 和向量存储资源。若评估导致生产搜索性能下降，应调低评估并发参数（`rag.eval.run.concurrency`），而非限制生产搜索。

**SSE 进度事件**：

| 事件 | 数据 |
|------|------|
| `run_started` | `{run_id, total_cases, pipeline_version}` |
| `case_started` | `{case_id, query}` |
| `case_completed` | `{case_id, precision, recall, mrr, passed}` |
| `case_failed` | `{case_id, error_message}` |
| `run_completed` | `{run_id, overall_score, passed_count, failed_count}` |
| `run_cancelled` | `{run_id}` |
| `run_failed` | `{run_id, error_message}` |
| `metrics_computing` | `{run_id}` |
| `metrics_done` | `{run_id, overall_score}` |
| `report_generating` | `{run_id}` |
| `report_completed` | `{run_id, report_id}` |
| `report_failed` | `{run_id, error}` |

**评估 SSE 连接生命周期**：继承公共 SSE 规范（心跳/缓冲/幂等，见 [需求索引](../requirements.md#sse-连接生命周期公共规范)）。评估 SSE 的差异化配置：

| 差异项 | 评估 SSE |
|--------|---------|
| **连接超时** | 最长 10 分钟（评估运行可能持续数分钟）。超时后服务端关闭连接 |
| **缓冲容量** | 最近 200 条事件（评估事件密度高于搜索） |
| **断线重连** | 支持。客户端携带 `Last-Event-ID` 重连，服务端从该事件 ID 后续推 |
| **事件 ID 格式** | `{run_id}:{seq}` |
| **完成后保持** | `run_completed` / `run_failed` 推送后，连接保持 30 秒再关闭，确保客户端收到最终状态 |

### 5.3 后处理流水线

运行完成后自动触发（`on_complete` 回调）：

1. **双轨评估**（并行）：
   - `MetricEngineFacade.calculate_and_diagnose()` 计算全部 12 项指标 + 执行 6 层诊断
2. **报告生成**：
   - `ReportBuilder.build()` 构建报告数据结构
   - `MarkdownRenderer.render()` 渲染 Markdown
   - 保存 `EvalReport`

### 5.4 手动评估触发

若自动后处理失败或需要重新评估：
- `POST /api/v1/rag/eval/runs/{run_id}/evaluate` — 触发双轨评估（异步后台任务）

### 5.5 权限在评估中的作用

- 评估数据集按租户隔离，按角色控制可见性（同知识库权限模型）
- 用户运行评估时，只能选择自己有权限的知识库和管道
- **评估运行自动注入运行者的 JWT 权限上下文**——同一管道用"管理员"和"普通医生"运行，指标可能不同
- 管道对比功能限制在同一角色视域内进行（苹果比苹果）
- 评估结果不可被无权限用户查看

---

## 6. 评估报告

### 6.1 报告结构

| 章节 | 内容 |
|------|------|
| 概要 | 名称、综合得分、通过/失败用例数、总耗时、报告状态 |
| 三层指标看板 | L1/L2/L3 各指标值、阈值、通过/不通过状态、综合得分圆环 |
| 六层诊断 | 每层问题列表（严重性、分类、描述、受影响用例、建议） |
| 坏案列表 | 失败用例详情（查询、各项指标、错误信息） |
| 调优建议 | 基于指标和诊断自动生成的调优建议（严重性、当前值、建议值、预期影响） |
| 跨域分析（新） | 各域贡献度、域激活准确率、跨域冲突统计 |

### 6.2 报告状态

| 状态 | 说明 |
|------|------|
| `processing` | 正在生成中 |
| `completed` | 已完成 |
| `superseded` | 同一运行生成了新报告，旧报告被取代 |

### 6.3 报告导出

| 格式 | 说明 |
|------|------|
| Markdown | 完整报告，含所有指标表格和诊断详情 |
| JSON | 结构化数据，适合程序化消费 |
| CSV | 仅坏案列表和指标摘要 |
| PDF | 可打印的正式报告（可选，需 WeasyPrint — 一期不做） |

### 6.4 趋势分析

- `GET /api/v1/rag/eval/trends` — 按时间序列展示各项指标趋势
- 支持按管道、按测试集过滤
- 前端以折线图展示

---

## 7. 调优闭环

### 7.1 调优建议

由 `TuningAdvisor` 基于指标和诊断自动生成：

| 属性 | 说明 |
|------|------|
| `category` | 建议分类（retrieval/generation/system/permission） |
| `severity` | critical / warning / info |
| `title` | 建议标题 |
| `description` | 问题描述 |
| `current_value` | 当前参数值 |
| `suggested_value` | 建议参数值 |
| `expected_impact` | 预期影响（如 "Hit Rate 预计提升 0.10-0.15"） |
| `source` | auto（自动生成）/ manual（人工添加） |
| `priority` | 1-10 |
| `safe_range` | 安全调整范围 |
| `conflict_with` | 与其他建议的冲突（见下方冲突检测规则） |

**冲突检测规则**（`ConflictDetector`）：

| 冲突类型 | 检测逻辑 | 示例 |
|---------|---------|------|
| **参数直接冲突** | 两条建议的 `target_node_id` + `target_param` 相同，但 `suggested_value` 不同 | 建议 A：BM25 节点 top_k → 20；建议 B：同一 BM25 节点 top_k → 50 |
| **参数间接冲突** | 两条建议修改同一节点的不同参数，但参数间有约束关系 | 建议 A：混合检索 vector_weight → 0.8；建议 B：同节点 keyword_weight → 0.8（两者之和应为 1） |
| **效果对冲** | 两条建议的 `expected_impact` 方向相反（一个提升精度，一个提升召回，可能导致互相抵消） | 建议 A：增大 top_k 提升召回；建议 B：降低 top_k 提升精度 |

**检测时机**：建议生成后立即执行冲突检测。`conflict_with` 字段存储冲突的建议 ID 列表。

**冲突处理**：
- 前端展示冲突警告（红色标注），提示用户选择其一或手动调和
- 采纳冲突建议时弹出确认对话框，列出冲突详情
- 不阻止采纳——最终决策权在用户

```
生成 → pending ─┬→ adopted → 创建新配置版本
                ├→ rejected (记录驳回原因)
                └→ ignored (暂不处理)
```

- **采纳**：自动创建新配置版本（管道或其他配置的变更），记录采纳操作
- **驳回**：记录驳回原因，不影响配置
- **忽略**：暂不处理，保留在待处理列表

### 7.3 配置版本管理

| 操作 | 描述 |
|------|------|
| 查看配置版本列表 | 按时间倒序，显示版本号、标签、变更摘要、创建者 |
| 创建版本 | 采纳调优建议时自动创建，或手动创建 |
| 回滚 | 回滚到指定版本（创建新版本 = 旧版本快照内容） |
| 变更集 | 每个版本关联一组变更记录，记录从哪个版本变更了什么参数 |

---

## 8. 知识库快照

评估运行可选知识库快照——冻结检索目标状态，保证评估可复现。

| 功能 | 描述 |
|------|------|
| **创建快照** | 记录当前知识库的元数据快照（见下方存储策略） |
| **查看快照** | 快照列表，按知识库、时间筛选 |
| **恢复快照** | 将知识库回滚到快照状态（创建新快照先备份当前状态） |
| **快照过期** | 超过保留期（可配置，默认 30 天）自动清理 |

**快照存储策略（浅拷贝 + 冻结保护）**：

| 项目 | 策略 |
|------|------|
| **存储方式** | **浅拷贝**——快照仅记录元数据引用，不复制向量数据。快照记录：向量存储路径、文档 ID 列表、分块数、分块策略 JSON、Embedding 配置 JSON、向量后端类型 |
| **存储开销** | 快照本身仅占 MySQL 行存储（~KB 级），不额外消耗向量存储配额 |
| **冻结保护** | 快照创建时，标记引用的文档和分块为"已冻结"。被冻结的文档不可删除、不可重新解析；被冻结的分块不可被索引重建覆盖。冻结状态持续到快照过期或手动删除 |
| **快照失效** | 若知识库执行了向量后端迁移，引用旧后端路径的快照自动标记为 `invalid`（旧数据已清理），评估运行不可选择已失效的快照 |
| **与配额关系** | 快照不计入知识库存储配额。冻结的文档/分块仍计入文档数和分块数配额（因为物理数据仍在） |

---

## 9. 数据模型

### 9.1 数据库表（继承现有 10 张 + 新增跨域相关）

| 表名 | 关键字段 |
|------|---------|
| `test_cases` | id, query, description, expected_knowledge_ids, expected_keywords, answer_points_summary, difficulty_level, professional_terms, relevance_scores, relevant_domains (JSON), expected_conflicts (JSON), source, source_draft_id, version, tenant_id |
| `test_sets` | id, name, description, source_type, case_ids (JSON), visibility, owner_id, tenant_id, created_at |
| `test_set_cases` | id, set_id, case_id（多对多关联） |
| `test_runs` | id, name, status, pipeline_id, pipeline_version, test_set_ids, snapshot_id, config_version_id, task_id, total_test_cases, passed_test_cases, overall_score, l1/l2/l3_metrics_json, diagnosis_json, started_at, completed_at, tenant_id, run_as_user_id |
| `test_run_results` | id, run_id, test_case_id, query, retrieved_doc_ids, retrieved_contexts, expected_knowledge_ids, actual_knowledge_ids, precision/recall/f1/mrr/ndcg, actual_answer, domain_results_json, l1/l2_metrics_json, diagnosis_json, passed, error_message, execution_time_ms |
| `eval_reports` | id, run_id, overall_score, l1/l2/l3_score, metrics_json, diagnosis_json, bad_cases_json, suggestions_json, markdown_content, status (processing/completed/superseded), created_at |
| `knowledge_snapshots` | id, kb_id, name, vector_store_path, document_count, chunk_count, config_version_id, config_snapshot, created_at |
| `tuning_suggestions` | id, run_id, report_id, category, severity, title, description, current_value, suggested_value, expected_impact, source, priority, safe_range, status (pending/adopted/rejected/ignored), conflict_with, applied_config_version_id |
| `eval_config_versions` | id, version_number, version_label, config_snapshot (JSON), change_summary, created_by |
| `eval_config_change_sets` | id, change_set_label, config_version_id, status (committed/rolled_back), rollback_reason |
| `test_case_drafts` | id, query, description, difficulty_level, expected_knowledge_ids, expected_keywords, answer_points, professional_terms, source_document_id, faithfulness_score, status, version |

### 9.2 关键 Schema（Pydantic）

| 模块 | 关键类 |
|------|--------|
| 指标 | `MetricInput`, `MetricOutput`, `MetricScore`, `Layer1Metrics`, `Layer2Metrics`, `Layer3Metrics`, `RunMetrics` |
| 运行 | `TestRunCreate`, `TestRunRead`, `TestRunList`, `RetrievalMetrics`, `TestRunResultItem`, `RunComparison` |
| 报告 | `OverallSummary`, `MetricCard`, `ScoringDashboard`, `DiagnosisSection`, `BadCaseEntry`, `TuningEntry`, `EvalReportData`, `EvalReportRead`, `TrendData` |
| 诊断 | `LayerIssue`, `LayerResult`, `DiagnosisResult` |
| 调优 | `TuningSuggestion`, `ConflictPair`, `ConfigVersionRead`, `ConfigChangeSetRead` |
| 快照 | `SnapshotCreate`, `SnapshotRead` |
| 用例 | `TestCaseCreate`, `TestCaseRead`, `TestCaseUpdate`, `TestCaseImportData` |
| 测试集 | `TestSetCreate`, `TestSetRead`, `TestSetExport` |
| 草稿 | `DraftCreate`, `DraftRead`, `DraftReview`, `DraftGenerationConfig` |

---

## 10. API 端点

所有端点注册在 `/api/v1/rag/eval` 下。

### 10.1 用例与测试集

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/test-cases` | 列出用例（分页、筛选） |
| `POST` | `/test-cases` | 创建用例 |
| `GET/PUT/DELETE` | `/test-cases/{id}` | 获取/更新/删除用例 |
| `DELETE` | `/test-cases/batch` | 批量删除用例 |
| `POST` | `/test-cases/import` | 批量导入用例 |
| `GET` | `/test-sets` | 列出测试集 |
| `POST` | `/test-sets` | 创建测试集 |
| `GET/PUT/DELETE` | `/test-sets/{id}` | 获取/更新/删除测试集 |
| `POST/DELETE` | `/test-sets/{id}/cases` | 添加/移除用例 |
| `GET` | `/test-sets/{id}/export` | 导出测试集 |

### 10.2 草稿（继承现有系统）

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/drafts` | 草稿列表 |
| `POST` | `/drafts` | 创建草稿 |
| `POST` | `/drafts/generate` | 从文档自动生成草稿 |
| `GET/PUT/DELETE` | `/drafts/{id}` | 获取/更新/删除草稿 |
| `POST` | `/drafts/{id}/review` | 审核草稿 |
| `POST` | `/drafts/{id}/import` | 将草稿导入为正式用例 |

### 10.3 评估运行

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/runs` | 创建运行 |
| `GET` | `/runs` | 列出运行 |
| `GET` | `/runs/{id}` | 获取运行详情 |
| `DELETE` | `/runs/{id}` | 删除运行 |
| `DELETE` | `/runs/batch` | 批量删除 |
| `POST` | `/runs/{id}/execute` | 启动执行 |
| `POST` | `/runs/{id}/cancel` | 取消运行 |
| `POST` | `/runs/{id}/execute/{case_id}` | 执行单个用例 |
| `POST` | `/runs/{id}/evaluate` | 触发双轨评估 |
| `GET` | `/runs/{id}/metrics` | 获取三层指标 |
| `GET` | `/runs/{id}/diagnosis` | 获取六层诊断 |
| `GET` | `/runs/{id}/stream` | SSE 进度流 |
| `GET` | `/runs/compare` | 对比两个运行 |

### 10.4 报告

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/reports` | 报告列表 |
| `POST` | `/reports` | 生成报告（force=true 重新生成） |
| `GET` | `/reports/{id}` | 报告详情 |
| `DELETE` | `/reports/{id}` | 删除报告 |
| `DELETE` | `/reports/batch` | 批量删除 |
| `GET` | `/reports/{id}/export` | 导出报告（markdown/json/csv） |
| `GET` | `/reports/generation/{task_id}/stream` | 报告生成进度 SSE |
| `GET` | `/trends` | 指标趋势数据 |

### 10.5 调优

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/runs/{id}/tuning` | 获取调优建议 |
| `POST` | `/tuning/{id}/adopt` | 采纳建议 |
| `POST` | `/tuning/{id}/reject` | 驳回建议 |
| `POST` | `/tuning/{id}/ignore` | 忽略建议 |
| `GET` | `/config-versions` | 配置版本列表 |
| `POST` | `/config-versions/{id}/rollback` | 回滚配置版本 |

### 10.6 快照

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/snapshots` | 创建知识库快照 |
| `GET` | `/snapshots` | 快照列表 |
| `GET` | `/snapshots/{id}` | 快照详情 |
| `POST` | `/snapshots/{id}/restore` | 恢复快照 |

---

## 11. 服务层架构

继承 backend/ 的门面模式，每个领域一个 Facade：

| 领域 | 门面 | 内部组件 |
|------|------|---------|
| 运行 | `RunEngineFacade` | `TestCaseExecutor`, `BatchTestRunner`, `ResultProcessor`, `SnapshotManager` |
| 指标 | `MetricEngineFacade` | `ScoringFacade`（聚合 L1/L2/L3 评分器），`DiagnosisOrchestrator`（管理 6 个诊断层） |
| 报告 | `ReportEngineFacade` | `ReportBuilder`, `MarkdownRenderer`, `TrendAnalyzer`, `ReportExporter` |
| 调优 | `TuningEngineFacade` | `TuningAdvisor`, `ConflictDetector`, `ConfigChanger` |
| 用例 | `CaseEngineFacade` | `CaseService`, `SetService` |
| 草稿 | `DraftEngineFacade` | `DraftGenerator`, `FaithfulnessChecker`, `DraftDeduplicator`, `BookMetadataAnalyzer` |
| 编排器 | `RagEvalOrchestrator` | 协调全部 6 个门面，管理完整工作流 |

---

## 12. 前端页面

评估不是独立模块，而是管道工作台的一个视图。测试数据是共享资源，放在知识库导航下。

### 12.1 页面位置

| 页面 | 路由 | 定位 |
|------|------|------|
| 测试数据 | `/knowledge/test-data` | 共享资源。3 选项卡：用例 / 测试集 / 草稿 |
| 管道评估视图 | `/pipelines/:id/evaluate` | 管道工作台的"评估"视图。评估历史 + 新建评估 |
| 评估详情 | `/pipelines/:id/evaluate/:runId` | 一次评估的完整结果。指标/诊断/域分析/内联调优 |

不再有独立的 `/rag-eval/*` 路由段。提示词页面移入 `/settings/config`。

### 12.2 测试数据 `/knowledge/test-data`

在知识库导航下，3 选项卡。与 [03-knowledge-base](./03-knowledge-base.md#43-测试数据页-knowledgetest-data) 共享。

**测试用例选项卡**：表格（搜索/来源筛选/难度筛选/分页/批量操作）+ 创建/编辑抽屉（含 `expected_knowledge_ids`、`difficulty_level`）+ JSON 导入（格式校验 + 预览）

**测试集选项卡**：卡片网格 + 用例成员管理（穿梭框，分页加载，修复 100 上限）+ 导出

**草稿选项卡**：表格 + AI 生成表单（选源文档 → 设置 QA 数 → 提交）+ SSE 进度 + 批量审核 + 导入为用例

### 12.3 管道评估视图 `/pipelines/:id/evaluate`

管道工作台的"评估"视图。从编辑视图点击顶部 [评估] 切换。

```
┌─ ← 管道列表  │  综合问诊管道 v3  │  [编辑] [评估] [发布]  ──────────┐
├──────────────────────────────────────────────────────────────────┤
│  评估历史                                            [+ 新建评估]   │
│                                                                  │
│  [对比选中]                                                        │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ ☐│ 名称      │ 测试集   │ 角色    │ 状态 │ 通过  │ 得分 │ 耗时  ││
│  │  │ 基线测试   │ 医学QA集  │ 管理员   │ ✅   │ 42/50│ 0.84│ 2.3s ││
│  │  │ top_k=20 │ 医学QA集  │ 管理员   │ ✅   │ 45/50│ 0.90│ 2.5s ││
│  │  │ 医生视角   │ 医学QA集  │ 普通医生  │ ✅   │ 38/50│ 0.76│ 2.1s ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                  │
│  统计: 12 次运行 │ 最新得分 0.90 │ 对比基线 +0.06                    │
└──────────────────────────────────────────────────────────────────┘

点击 [+ 新建评估] → 侧边滑出抽屉:
  测试集: [☑ 医学综合QA集] [☐ 单域测试集]
  管道版本: [v3 (当前) ▾]
  知识库快照: [使用最新 ▾] 或 [创建新快照...]
  模拟角色: [当前角色: 管理员 ▾] 或 [普通医生 ▾] [药师 ▾]
  
  [启动评估] — 启动后在表格顶部新增一行（SSE 进度条实时更新）
```

**关键设计**：
- "模拟角色"让管理员以其他角色身份运行评估——验证权限是否生效
- 角色列显示该次评估使用的角色身份
- 同一管道 + 同一测试集 + 不同角色 = 不同结果（设计意图，非 bug）
- 点击历史行 → 进入评估详情
- 选中 2 个已完成运行 → "对比选中" → 并排对比面板

### 12.4 评估详情 `/pipelines/:id/evaluate/:runId`

一次评估的完整结果。所有诊断和调优操作在一页内完成。

```
┌─ ← 返回评估  │  基线测试  │  综合问诊 v3  │  角色:管理员  │  得分 0.84  │  [导出] [对比] ─┐
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐                   │
│  │ 综合得分   │ 通过/总数  │ MRR     │ NDCG    │ P95 延迟   │                   │
│  │  0.84    │  42/50   │  0.72   │  0.68   │  2.3s    │                   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘                   │
│                                                                              │
│  ── 域贡献 ─────────────────────────────────────────────────────              │
│  心血管域 ████████████░░░░ 0.88 (激活准确率 1.0)                                │
│  内分泌域 ██████████░░░░░░ 0.82 (激活准确率 0.9)                                │
│  药学域   ████████░░░░░░░░ 0.65 (激活准确率 0.7)  ⚠️ 低                        │
│                                                                              │
│  ── 三层指标 ───────────────────────────────────────────────────              │
│  ┌─ L1 检索质量 ───────────────────────────────────────────────┐             │
│  │  Context Precision: 0.78 ✅ │ Recall: 0.72 ✅ │ MRR: 0.72 ✅ │            │
│  └────────────────────────────────────────────────────────────┘             │
│  [L2 生成质量 ▸]  [L3 系统质量 ▸]                                              │
│                                                                              │
│  ── 诊断 ──────────────────────────────────────────────────────              │
│  [L1 规则引擎: 0 问题] [L2 历史对比: 2 问题 ▸] [L3 LLM诊断: 1 问题 ▸]          │
│  [L4 数据质量: 1 问题 ▸] [L5 效果评估: 3 问题 ▸] [L6 回归检测: 0 问题]          │
│                                                                              │
│  ── 问题节点（可直接操作）────────────────────────────────────────              │
│  🔴 药学域 / BM25检索  │  top_k=10 → Hit Rate 0.65            │              │
│     建议: 增大到 20，预期提升 +0.15                             │              │
│     [🔧 去编辑器中打开]  [采纳此建议]  [忽略]                     │              │
│                                                                              │
│  🟡 心血管域 / 语义缓存  │  cache_key_scope=role_agnostic       │              │
│     建议: 改为 role_aware，防止不同角色缓存污染                   │              │
│     [🔧 去编辑器中打开]  [采纳此建议]  [忽略]                     │              │
│                                                                              │
│  🟡 药学域 / 域激活规则  │  关键词不完整，未触发药学域             │              │
│     建议: activation_rules.keywords 加入"降压药"                 │              │
│     [🔧 去编辑器中打开]  [采纳此建议]  [忽略]                     │              │
│                                                                              │
│  ── 失败用例 (8) ──────────────────────────────────────────────              │
│  [可展开表格: 查询 / 期望答案 / 实际答案 / 各域得分 / 失败原因]                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**关键设计**：
- **内联调优**：诊断直接指向具体节点和参数，"采纳"一点完成，不跳转
- **🔧 去编辑器中打开**：切换到编辑视图并高亮对应节点（核心目标要求的闭环）
- **域贡献**：直接可视化各域差异
- **对比按钮**：选择另一个运行 → 并排指标差异，绿色提升/红色退化

### 12.5 组件保留清单

| 组件 | 保留 | 位置 |
|------|------|------|
| `ScoringDashboard` + `LayerScoreCard` + `MetricScoreCard` | 保留 | 评估详情页 |
| `DiagnosisPanel` + `LayerResultCard` + `IssueList` | 保留 | 评估详情页 |
| `BadCaseTable` | 保留 + 排序/搜索 | 评估详情页 |
| `SuggestionPanel` + `ConflictAlert` | 保留 + 修复冲突检测 | 评估详情页（内联） |
| `TrendChart` | 保留 | 评估视图 + 详情概览 |
| `DraftTable` + `DraftGenerationForm` | 保留 | 测试数据页草稿选项卡 |
| `CaseTransferModal` | 保留 + 分页加载 | 测试数据页测试集选项卡 |
| SSE 进度 Store | 保留 + 合并为 2 个 | `evaluationProgressStore` + `draftGenerationStore` |
| `entities/rag-eval/types.ts` | 保留 + 跨域类型 | 共享 |
| `api/rag-eval/` | 保留 + 适配新路由 | API 层 |

### 12.6 交互流

```
管道编辑器 [评估] → 评估视图（历史+新建）
                      │
                      ├── 新建评估 → 选择测试集/版本/角色 → 启动
                      │                │
                      ▼                ▼
                 评估详情（SSE 进度 → 完成后：指标/诊断/域分析/内联调优）
                      │
                      ├── [采纳] → 直接修改管道参数 → 自动创建配置版本
                      ├── [🔧 去编辑器中打开] → 切换到编辑视图，高亮对应节点
                      └── [重新评估] → 回到评估视图，再次新建
```

---

## 13. 验收标准

### 现有功能保留

- [ ] AC-6.1：全部 12 项三层指标正确计算，阈值校验有效
- [ ] AC-6.2：六层诊断全部执行，每层输出正确的问题列表
- [ ] AC-6.3：草稿自动生成 → 审核 → 导入为用例完整流程可用
- [ ] AC-6.4：测试集创建、用例关联、导出功能完整
- [ ] AC-6.5：评估运行 SSE 进度推送全部事件类型正确触发
- [ ] AC-6.6：评估运行并发控制正确——全局最多 2 个运行，单运行最多 5 个并发用例
- [ ] AC-6.7：后处理流水线自动触发，指标计算和报告生成成功
- [ ] AC-6.8：报告导出正确（Markdown/JSON/CSV 三种格式）
- [ ] AC-6.9：调优建议自动生成，采纳/驳回/忽略操作有效
- [ ] AC-6.10：采纳建议后自动创建配置版本，回滚可用
- [ ] AC-6.11：知识库快照创建/恢复正确冻结知识库状态
- [ ] AC-6.12：坏案过滤正确——N/A 用例不计入指标分母
- [ ] AC-6.13：报告 superseded 状态正确——同一运行生成新报告时旧报告标记为 superseded

### 平台化新增

- [ ] AC-6.14：跨域指标（域激活准确率/跨域覆盖率/冲突检测率/端到端延迟）正确计算
- [ ] AC-6.15：评估运行注入运行者权限上下文，同一管道不同角色运行指标不同
- [ ] AC-6.16：评估数据集按租户隔离、按角色控制可见性
- [ ] AC-6.17：管道对比限制在同一角色视域内
- [ ] AC-6.18：管道版本对比评估——同一数据集上对比两个管道版本/两个配置版本
- [ ] AC-6.19：报告跨域分析章节正确展示各域贡献度、冲突统计

### 前端重新设计

- [ ] AC-6.20：测试数据在 `/knowledge/test-data` 下，三选项卡切换正常，功能完整
- [ ] AC-6.21：TestCase 创建表单包含 expected_knowledge_ids、difficulty_level 字段
- [ ] AC-6.22：JSON 导入增加格式校验和预览
- [ ] AC-6.23：CaseTransferModal 分页加载，支持超过 100 条用例
- [ ] AC-6.24：管道评估视图正确展示该管道的评估历史（名称/测试集/角色/状态/得分/耗时）
- [ ] AC-6.25：新建评估抽屉正确加载测试集列表、管道版本、角色模拟选项
- [ ] AC-6.26：模拟角色评估——管理员以普通医生身份运行，结果正确反映权限差异
- [ ] AC-6.27：选中 2 个运行对比 → 并排展示指标差异（绿升红降）
- [ ] AC-6.28：评估详情页一页内展示指标/诊断/域分析/内联建议/失败用例
- [ ] AC-6.29：域分析区块展示各域贡献度、激活准确率、冲突统计
- [ ] AC-6.30："🔧 去编辑器中打开"点击后切换到编辑视图并高亮对应节点
- [ ] AC-6.31：内联调优"采纳"后自动修改管道参数 + 创建配置版本
- [ ] AC-6.32：conflict 正确检测多条建议修改同一参数
- [ ] AC-6.33：4 个提示词页面存根已移除，提示词归入 `/settings/config`
- [ ] AC-6.34：TrendChart 正确部署——评估视图和详情概览均可使用

---

## 14. 与其他模块的接口

| 被依赖 | 接口 |
|--------|------|
| [01-pipeline-model](./01-pipeline-model-and-engine.md) | 调用 PipelineCompiler 执行评估中的搜索请求 |
| [03-knowledge-base](./03-knowledge-base.md) | 知识库快照创建/恢复 |
| [04-permission](./04-permission-and-multi-tenancy.md) | 数据集权限模型、评估运行权限注入 |
| [07-infrastructure](./07-infrastructure-and-deployment.md) | SSE 推送基础设施、异步任务管理、配置热重载 |
