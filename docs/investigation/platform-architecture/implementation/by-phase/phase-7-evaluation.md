# Phase 7：RAG 评估系统改造——实施文档

> **依赖**：Phase 4（搜索 API）完成后启动。PipelineCompiler 已就绪，权限系统（Phase 1）已就绪。
> **产出**：将现有 backend/ 评估体系适配到平台化管道架构，新增跨域评估能力，前端移动至管道工作台内嵌视图。
> **参考规范**：[06-rag-evaluation.md](../../requirements/06-rag-evaluation.md)、[by-module/06-rag-evaluation.md](../by-module/06-rag-evaluation.md)
> **最后更新**：2026-05-14

---

## 1. 阶段目标

将现有 backend/ 的完整 RAG 评估体系（12 项指标 + 6 层诊断 + 草稿系统 + 调优闭环）适配到新平台管道架构，同时新增跨域评估维度：

- **PipelineCompiler 集成**：将 TestCaseExecutor 的检索路径从 `IRetrievalService` 替换为 `PipelineCompiler.execute()`，注入运行者 AuthContext
- **跨域评估指标**：新增 4 项跨域扩展指标（域激活准确率、跨域覆盖率、冲突检测率、端到端延迟 P95）
- **快照多后端适配**：SnapshotManager 从单一 Chroma 文件复制模式改造为支持 3 种向量后端（Chroma/ES/Milvus）的浅拷贝 + 冻结保护模式
- **角色感知评估**：评估运行注入 JWT 权限上下文，同一管道 + 同一测试集 + 不同角色 → 不同评估结果
- **报告跨域章节**：报告新增跨域分析章节（各域贡献度、激活准确率、冲突统计、端到端延迟分布）
- **内联调优 UI**：评估详情页内嵌调优建议卡片，一键采纳 + 自动创建配置版本；"去编辑器中打开"切换到编辑视图并高亮目标节点
- **路由迁移**：评估页面从独立 `/rag-eval/*` 路由段迁移至管道工作台内嵌视图 `/pipelines/:id/evaluate`

---

## 2. 任务清单

### 7.1 后端改造

#### 7.1.1 Schemas 改造

##### `schemas/rag_eval/test_case.py`

- [ ] **`TestCaseCreate` 新增字段**
  - `relevant_domains: list[str] | None = None`——相关域列表（跨域指标的 ground truth），如 `["心血管内科", "内分泌科", "药学"]`
  - `expected_conflicts: list[ExpectedConflict] | None = None`——期望冲突列表，每条含 `statement_a`, `source_a`, `statement_b`, `source_b`
  - 字段验证：`relevant_domains` 非空时，每个元素与管道中定义的 `domain_id` 匹配校验
  - `ExpectedConflict` 内嵌类型：`{ statement_a: str, source_a: str, statement_b: str, source_b: str }`
- [ ] **`TestCaseRead` 新增字段**
  - 同上，分别输出 `relevant_domains` 和 `expected_conflicts`
- [ ] **`TestCaseUpdate` 新增字段**
  - 同上，均为可选更新
- [ ] **`TestCaseImportData` 新增字段**
  - `relevant_domains`、`expected_conflicts`——批量导入时支持

##### `schemas/rag_eval/test_run.py`

- [ ] **`TestRunCreate` 新增字段**
  - `pipeline_id: str`——被评估的管道 ID
  - `pipeline_version: int | None = None`——被评估的管道版本（不传默认最新）
  - `simulated_role: str | None = None`——模拟角色（如 "普通医生"），运行评估时切换到此角色
  - `auto_snapshot: bool = False`——是否自动创建知识库快照
- [ ] **`TestRunRead` 新增字段**
  - `run_as_user_id: str | None`——实际执行者用户 ID
  - `simulated_role_id: str | None`——模拟的角色 ID
  - `pipeline_id: str | None`——被评估的管道 ID
  - `pipeline_version: int | None`——被评估的管道版本号
  - `cross_domain_metrics_json: dict | None`——跨域扩展指标 JSON
- [ ] **`TestRunList` 新增字段**
  - `pipeline_id`、`pipeline_version`——用于评估历史列表展示
- [ ] **`TestRunResultItem` 新增字段**
  - `domain_results_json: dict | None`——各域贡献结果：`{"心血管内科": {"activated": true, "contribution": 0.6}, ...}`

##### `schemas/rag_eval/metrics.py`

- [ ] **`CrossDomainMetrics`（新增类）**
  - `domain_activation_acc: MetricScore`——域激活准确率
  - `cross_domain_coverage: MetricScore`——跨域覆盖率
  - `conflict_detection_rate: MetricScore`——冲突检测率
  - `e2e_latency_p95: MetricScore`——端到端延迟 P95（details 中存储 p50/p95/p99）
- [ ] **`RunMetrics` 新增字段**
  - `cross_domain: CrossDomainMetrics | None = None`——跨域扩展指标
  - `overall_score` 计算逻辑更新：权重配置新增 `cross_domain` 维度（L1=0.4, L2=0.4, L3=0.15, cross_domain=0.05，默认）
- [ ] **`DomainContribution`（新增）**
  - `domain_name: str`、`activation_accuracy: float`、`hit_count: int`、`total_queries: int`、`avg_contribution_score: float`
- [ ] **`E2ELatencyDistribution`（新增）**
  - `p50_ms: int`、`p95_ms: int`、`p99_ms: int`、`avg_ms: int`

##### `schemas/rag_eval/report.py`

- [ ] **`CrossDomainSection`（新增）**
  - `domain_contributions: list[DomainContribution]`——各域贡献度
  - `overall_activation_accuracy: float`——总体域激活准确率
  - `overall_cross_coverage: float`——总体跨域覆盖率
  - `overall_conflict_detection_rate: float`——总体冲突检测率
  - `e2e_latency_distribution: E2ELatencyDistribution`——延迟分布
  - `domain_conflicts: list[CrossDomainConflictSummary]`——跨域冲突统计
- [ ] **`CrossDomainConflictSummary`（新增）**
  - `domain_pair: tuple[str, str]`、`total_conflicts: int`、`detected_conflicts: int`、`detection_rate: float`
- [ ] **`EvalReportData` 新增字段**
  - `cross_domain: CrossDomainSection | None`——跨域分析章节

##### `schemas/rag_eval/tuning.py`

- [ ] **`TuningSuggestion` 改造字段**
  - `conflict_with` 类型从 `str | None` 改为 `list[str] | None`——支持多条冲突建议 ID
  - `current_value` 结构新增 `target_node_id: str | None`、`target_param: str | None`——用于前端定位到管道编辑器对应节点
  - `suggested_value` 结构新增 `target_node_id: str | None`、`target_param: str | None`、`val: Any`
  - `category` 枚举值新增 `permission`——权限相关的调优建议
- [ ] **`ConfigChangeSetRead` 改造**
  - `previous_version_id: str | None`——回滚源版本 ID

##### `schemas/rag_eval/snapshot.py`

- [ ] **`SnapshotCreate` 新增字段**
  - `kb_id: str`——知识库 ID（必填）
  - `description: str = ""`
- [ ] **`SnapshotRead` 新增/改造字段**
  - `kb_id: str`——关联的知识库 ID
  - `vector_backend_type: str`——`chroma` | `elasticsearch` | `milvus`
  - `doc_ids_json: list[str] | None`——冻结文档 ID 列表
  - `chunk_strategy_json: dict | None`——分块策略快照
  - `embedding_config_json: dict | None`——Embedding 配置快照
  - `status: str`——`active` | `expired` | `invalid`
  - `expires_at: datetime | None`——过期时间

#### 7.1.2 执行器改造（executor.py）

##### `service/rag_eval/run/executor.py`

- [ ] **`TestCaseExecutor` 构造函数改造**
  - 新增参数 `pipeline_compiler: PipelineCompiler`——替换原 `retrieval_service`
  - 新增参数 `auth_context_provider`——权限上下文提供者
  - 保留 `test_run_result_repository` 注入
- [ ] **`execute()` 方法签名改造**
  ```python
  async def execute(
      self,
      test_case,
      run_id: str,
      pipeline_config: dict,        # [改造] 替换原 retrieval_fn/generation_fn
      pipeline_version: int,        # [新增]
      auth_context: AuthContext,    # [新增] 权限上下文
      timeout_ms: int | None = None,
  ) -> TestRunResultItem:
  ```
- [ ] **检索调用改造**
  - 原逻辑：`retrieved = await retrieval_fn(test_case.query)`
  - 新逻辑：
  ```python
  result = await self._pipeline_compiler.execute(
      pipeline_config=pipeline_config,
      query=test_case.query,
      search_params={"top_k": 5},
      auth_context=auth_context,
  )
  retrieved_ids = [d["id"] for d in result.get("documents", [])]
  retrieved_contexts = [d["content"] for d in result.get("documents", [])]
  # 提取域贡献结果
  domain_results = result.get("domain_results", {})
  ```
- [ ] **域结果提取**
  - `_extract_domain_results(result) → dict`——从 PipelineCompiler 返回值中提取 `domain_results`
  - 格式：`{"心血管内科": {"activated": true, "contribution": 0.6, "top_chunks": [...]}}`
- [ ] **结果保存改造**
  - `TestRunResultItem` 写入时新增 `domain_results_json` 字段

##### `service/rag_eval/run/batch_runner.py`

- [ ] **`BatchTestRunner` 构造函数改造**
  - 新增参数 `auth_context_provider`——权限上下文提供者
  - 新增参数 `pipeline_compiler`——PipelineCompiler 实例
- [ ] **`execute_run()` 方法改造**
  - 新增步骤：从 `test_run` 读取 `pipeline_id` / `pipeline_version` / `run_as_user_id` / `simulated_role_id`
  - 新增步骤：构造 `AuthContext`（调用 `auth_context_provider.get_context(user_id, simulated_role_id)`）
  - 每个用例执行前注入权限上下文
  - 将 `pipeline_config` 传递给 `TestCaseExecutor.execute()`
- [ ] **并发控制保持**
  - 全局最大并发运行数：2（`rag.eval.run.max_concurrent_runs`）
  - 单运行内最大并发用例数：5（`rag.eval.run.concurrency`）
  - 评估运行走内部执行通道，不经过发布 URL 限流中间件
- [ ] **SSE 进度事件保持**
  - `run_started`、`case_started`、`case_completed`、`case_failed`、`run_completed`
  - 事件中新增 `pipeline_version` 字段（在 `run_started` 中）

##### `service/rag_eval/run/snapshot_manager.py`

- [ ] **`SnapshotManager` 构造函数改造**
  - 新增参数 `vector_backend_registry: VectorBackendRegistry`——向量后端注册表（适配 3 种后端）
  - 保留 `snapshot_repository`、`config_cache`
- [ ] **`create_snapshot()` 方法改造**
  - 新签名：`async def create_snapshot(self, kb_id: str, name: str, description: str = "") -> SnapshotRead`
  - 流程改造：
    1. 调用 `vector_backend_registry.get(kb_id)` 确定后端类型
    2. 获取知识库元数据（文档列表、分块数、当前分块策略、Embedding 配置、桶/索引路径）
    3. **浅拷贝**：仅记录元数据引用，不复制向量数据
    4. **冻结保护**：标记引用文档为"已冻结"（不可删除/重新解析），标记分块不可被索引重建覆盖
    5. 创建快照记录：`kb_id`, `vector_backend_type`, `vector_store_path`, `doc_ids_json`, `chunk_strategy_json`, `embedding_config_json`, `status=active`, `expires_at=now+30days`
- [ ] **`restore_snapshot()` 方法改造**
  - 验证快照状态为 `active`（非 `invalid`/`expired`）
  - 验证后端类型匹配（当前后端 vs 快照后端）
- [ ] **`check_validity()` 方法新增**
  - `async def check_validity(self, snapshot_id: str) -> bool`
  - 逻辑：当前向量后端类型与快照记录的 `vector_backend_type` 是否一致 → 不一致返回 `False`（标记 `invalid`）
- [ ] **`cleanup_expired_snapshots()` 方法新增**
  - 定时任务调用（APScheduler，每天 03:00）
  - 查询 `status=active AND expires_at < now` → 标记为 `expired` → 解冻对应文档

##### `service/rag_eval/run/result_processor.py`

- [ ] **`ResultProcessor` 改造**
  - 新增 `_aggregate_cross_domain_results(results: list[TestRunResultItem]) → dict`——从所有用例结果聚合跨域统计
  - 聚合逻辑：
    - 按域统计激活次数 / 贡献度均值
    - 按域对统计冲突情况
    - 计算端到端延迟分布（P50/P95/P99）

#### 7.1.3 跨域指标计算器

##### `service/rag_eval/metrics/scoring/calculators/cross_domain_calc.py`（新增）

- [ ] **`CrossDomainCalc` 基类**
  - 实现 `IMetricCalculator` 接口
  - `calculate(self, inputs: list[MetricInput]) -> MetricScore`
  - 构造函数注入 `config_cache`，读取阈值配置
- [ ] **`DomainActivationAccCalc`**
  ```python
  class DomainActivationAccCalc(CrossDomainCalc):
      """域激活准确率
      GT: TestCase.relevant_domains
      实际: PipeCompiler 返回的 domain_results 中 activated=True 的域
      公式: |准确激活域 ∩ 期望激活域| / |期望激活域|
      空 relevant_domains → 返回 N/A (value=None)
      """
  ```
- [ ] **`CrossDomainCoverageCalc`**
  ```python
  class CrossDomainCoverageCalc(CrossDomainCalc):
      """跨域覆盖率
      公式: |有结果贡献的域 ∩ 期望激活域| / |期望激活域|
      有结果贡献 = domain_results[domain].contribution > 0
      """
  ```
- [ ] **`ConflictDetectionRateCalc`**
  ```python
  class ConflictDetectionRateCalc(CrossDomainCalc):
      """冲突检测率
      GT: TestCase.expected_conflicts
      实际: 管道 ConflictDetectExecutor 检测到的冲突数
      公式: 检测到的冲突数 / 期望冲突数
      空 expected_conflicts → 返回 N/A
      """
  ```
- [ ] **`E2ELatencyCalc`**
  ```python
  class E2ELatencyCalc(CrossDomainCalc):
      """端到端延迟 P95
      从所有 execution_time_ms 计算 P50/P95/P99
      不设硬阈值（threshold=0, always passed）
      details: {p50: ms, p95: ms, p99: ms, avg: ms}
      """
  ```
- [ ] **指标注册**
  - 在 `MetricRegistry` 中注册 4 个新指标
  - 指标标识：`domain_activation_acc`, `cross_domain_coverage`, `conflict_detection_rate`, `e2e_latency_p95`
  - 阈值配置键：`rag.eval.threshold.{metric_name}`（从 ConfigCache 读取，无配置用 L0 默认值）

##### `service/rag_eval/metrics/scoring/retrieval.py`

- [ ] **`RetrievalScorer` 不直接改动**（L1 5 项无变更）。跨域指标由 `MetricEngineFacade` 并行调度。

##### `service/rag_eval/metrics/facade.py`

- [ ] **`MetricEngineFacade` 改造**
  - 新增 `calculate_cross_domain(results: list[TestRunResultItem]) → CrossDomainMetrics`
  - `calculate_and_diagnose()` 方法中并行增加跨域指标计算步骤
  - 综合得分权重更新：`DEFAULT_WEIGHTS = {"l1": 0.4, "l2": 0.4, "l3": 0.15, "cross_domain": 0.05}`

#### 7.1.4 报告改造

##### `service/rag_eval/report/builder.py`

- [ ] **`ReportBuilder.build()` 方法改造**
  - 从 `test_run.cross_domain_metrics_json` 解析跨域指标
  - 新增 `_build_cross_domain_section(results, cross_domain_metrics)` 方法
  - `EvalReportData` 中填充 `cross_domain` 字段
- [ ] **`_build_cross_domain_section()` 实现**
  - 从所有 `TestRunResultItem.domain_results_json` 聚合：
    - 各域的 `DomainContribution`（激活准确率、命中次数、总查询数、平均贡献度）
  - 从跨域指标提取：
    - `overall_activation_accuracy`, `overall_cross_coverage`, `overall_conflict_detection_rate`
    - `E2ELatencyDistribution`（P50/P95/P99/avg）
  - 从预计冲突 vs 检测冲突统计 `CrossDomainConflictSummary[]`
- [ ] **报告模板更新**
  - Markdown 渲染新增跨域分析章节模板（域贡献度表格 + 冲突统计表格 + 延迟分布表格）

##### `service/rag_eval/report/markdown_renderer.py`

- [ ] **渲染模板新增跨域分析章节**
  - 域贡献度表格：`| 域 | 激活准确率 | 命中次数 | 平均贡献度 |`
  - 冲突统计表格：`| 域对 | 期望冲突 | 检测到冲突 | 检测率 |`
  - 延迟分布：`| P50 | P95 | P99 | 平均 |`

##### `service/rag_eval/report/exporter.py`

- [ ] **Export 支持跨域数据**
  - JSON 导出含 `cross_domain` 字段
  - CSV 导出新增跨域指标摘要行

#### 7.1.5 调优建议改造

##### `service/rag_eval/tuning/advisor.py`

- [ ] **`TuningAdvisor` 新增跨域调优生成**
  - `generate_cross_domain_suggestions(run_id, cross_domain_metrics, domain_contributions) → list[TuningSuggestion]`
  - 触发条件：
    | 类型 | 触发条件 | 建议内容 |
    |------|---------|---------|
    | `domain_activation_miss` | 某域激活准确率 < 0.7 | 建议检查 `activation_rules.keywords` |
    | `cross_domain_imbalance` | 某域贡献度 < 0.3 | 建议调整该域 `domain_weight` |
    | `conflict_undetected` | 冲突检测率 < 0.5 | 建议开启/增强冲突检测节点 |
    | `latency_bottleneck` | e2e P95 > 阈值 | 建议降低 `top_k` 或启用语义缓存 |
- [ ] **建议 `category` 枚举扩展**
  - 新增 `permission`——权限相关（如角色过滤过严导致检索结果少）
- [ ] **`suggested_value` 结构标准化**
  - 每条建议必须包含 `target_node_id` 和 `target_param`，用于前端定位节点

##### `service/rag_eval/tuning/conflict_detector.py`

- [ ] **冲突检测规则（3 种）**
  - **参数直接冲突**：两条建议 `target_node_id` + `target_param` 相同，`suggested_value` 不同
  - **参数间接冲突**：同一节点的不同参数间有约束关系（如 `vector_weight + keyword_weight = 1`）
  - **效果对冲**：一条提升精度、一条提升召回，方向相反可能导致互相抵消
- [ ] **`conflict_with` 字段从单 `str` 改为 `list[str]`**
  - 返回格式：`["tune_003", "tune_007"]`
  - 每条建议可能与其他多条建议冲突

##### `service/rag_eval/tuning/config_changer.py`

- [ ] **`apply_suggestion()` 方法改造**
  - 解析 `suggested_value` 中的 `target_node_id` / `target_param` / `val`
  - 调用 `PipelineCompiler.update_node_config(target_node_id, target_param, val)`
  - 自动创建 `eval_config_versions` 记录（含 `config_snapshot`、`change_summary`）
  - 自动创建 `eval_config_change_sets` 记录（关联版本）
  - 更新 `tuning_suggestions` 状态为 `adopted` + `applied_config_version_id`
- [ ] **`rollback()` 方法改造**
  - 支持通过 `ConfigChanger` 回滚配置版本

#### 7.1.6 编排器改造

##### `service/rag_eval/orchestrator.py`

- [ ] **`RagEvalOrchestrator` 改造**
  - `run_full_evaluation()` 新增：`pipeline_id: str`, `pipeline_version: int | None`, `simulated_role: str | None`
  - `post_run_pipeline()` 流程调整：新增跨域指标计算步骤 + 跨域调优建议生成
- [ ] **新增协调方法**
  ```python
  async def run_pipeline_comparison(
      self, test_set_ids: list[str], pipeline_id: str,
      version_a: int, version_b: int, config_version_id: str = None,
  ) -> dict:
      """同一数据集上对比两个管道版本的指标差异"""
      # → 返回 {"run_id_a": "...", "run_id_b": "..."}

  async def run_cross_role_evaluation(
      self, test_set_ids: list[str], pipeline_id: str,
      roles: list[str],
  ) -> dict:
      """同一管道多个角色模拟评估"""
      # → 返回 {"run_ids": ["...", "..."], "role_comparison": {...}}
  ```

#### 7.1.7 API 端点改造

所有端点基路径保持 `/api/v1/rag/eval`，但前端路由不再使用独立的 `/rag-eval/*`。

- [ ] **运行创建端点调整**
  - `POST /runs` 请求体新增：`pipeline_id`（必填）、`pipeline_version`、`simulated_role`, `auto_snapshot`
  - 响应新增 `pipeline_id`, `pipeline_version`, `run_as_user_id`, `simulated_role_id`
- [ ] **运行查询端点调整**
  - `GET /runs` 查询参数新增 `pipeline_id` 过滤
  - `GET /runs/{id}` 响应新增跨域指标、权限上下文信息
- [ ] **管道对比端点新增**
  - `GET /runs/compare` 查询参数：`run1`, `run2`（已有，无变更）
  - 内部逻辑：增加跨域指标对比
- [ ] **权限过滤**
  - 所有端点增加 tenant_id 过滤（Repository 基类自动注入）
  - 运行创建时校验用户对目标管道/知识库/测试集的权限
- [ ] **运行管理端点补全**
  - `POST /runs/{id}/cancel` — 取消正在执行的测试运行
  - `POST /runs/{id}/evaluate` — 对已完成运行触发后评估（六层诊断）
  - `POST /runs/{id}/execute/{case_id}` — 单用例执行（调试用途）
  - `DELETE /runs/batch` — 批量删除运行记录
- [ ] **报告端点补全**
  - `GET /reports/generation/{task_id}/stream` — SSE 推送报告生成进度
  - `DELETE /reports/batch` — 批量删除报告
- [ ] **趋势与配置端点补全**
  - `GET /trends` — 指标趋势分析（查询参数：metric, start_date, end_date, pipeline_id）
  - `GET /config-versions` — 评估配置版本列表
  - `GET /config-versions/{id}` — 评估配置版本详情
- [ ] **快照端点补全**
  - `GET /snapshots` — 知识库快照列表
  - `GET /snapshots/{id}` — 知识库快照详情

### 7.2 前端改造

#### 7.2.1 评估详情页改造

##### `features/rag-eval/pages/EvalDetailPage.tsx`

- [ ] **页面布局更新**
  - 路径从 `/rag-eval/runs/:runId` 迁移至 `/pipelines/:id/evaluate/:runId`
  - 作为管道工作台评估视图的子页面
  - 顶部信息栏：综合得分 + 通过/总数 + MRR + NDCG + P95 延迟
- [ ] **域贡献区块（新增）**
  - 嵌入 `DomainContribChart` 组件
  - 展示各域激活准确率、贡献度柱状图
  - 低贡献域（激活准确率 < 0.7）红色标注
- [ ] **三层指标区块（保留）**
  - 复用 `ScoringDashboard` + `LayerScoreCard` + `MetricScoreCard`
  - 新增跨域指标卡片区域
- [ ] **六层诊断区块（保留）**
  - 复用 `DiagnosisPanel` + `LayerResultCard` + `IssueList`
  - 注意 L3 可能返回 `skipped` 状态
- [ ] **内联调优区块（新增）**
  - 嵌入 `InlineTuningCard` 组件列表
  - 每条卡片含：
    - 严重程度标识（🔴/🟡/🟢）
    - 目标节点名称 + 当前参数值
    - 建议修改值 + 预期影响
    - `[🔧 去编辑器中打开]` 按钮——跳转到 `/pipelines/:id/edit?highlightNode={target_node_id}`
    - `[采纳此建议]` 按钮——触发采纳 API + 自动创建配置版本
    - `[忽略]` 按钮
  - 冲突警告：同一参数多条建议时显示 `ConflictAlert`
- [ ] **失败用例区块（保留）**
  - 复用 `BadCaseTable`（增加排序、搜索）
  - 展开行显示各域贡献详情
- [ ] **操作按钮**
  - `[导出]`——导出报告（Markdown/JSON/CSV）
  - `[对比]`——选择另一个运行进行并排对比
  - `[重新评估]`——返回评估视图新建评估

#### 7.2.2 新增组件

##### `features/rag-eval/components/DomainContribChart.tsx`（新增）

- [ ] **域贡献度可视化**
  - 水平柱状图：每个域一条（使用 @ant-design/charts Bar）
  - 柱体长度表示整体贡献度（avg_contribution_score）
  - 柱体颜色表示激活准确率（≥ 0.8 绿色，0.6-0.8 黄色，< 0.6 红色）
  - 标签显示域名称 + 准确率值
  - 高度自适应（域数量 × 40px，最少 120px）
  - Props: `{ domainContributions: DomainContribution[] }`

##### `features/rag-eval/components/InlineTuningCard.tsx`（新增）

- [ ] **内联调优建议卡片**
  - 左侧：严重程度色条（critical=红色, warning=黄色, info=蓝色 4px 竖条）
  - 中间：
    - 标题（如 "药学域 BM25 检索 top_k 过小"）
    - 当前状态（如 "top_k=10 → Hit Rate 0.65"）
    - 建议说明（如 "建议: 增大到 20，预期提升 +0.15"）
  - 右侧：
    - `[🔧 去编辑器中打开]` 按钮——跳转编辑视图 + 高亮目标节点
    - `[采纳此建议]` 按钮——主色调，弹出确认对话框
    - `[忽略]` 按钮——次要色调
  - 采纳确认对话框：
    - 标题："确认采纳调优建议"
    - 内容：展示修改详情（节点 → 参数 → 当前值 → 新值）
    - 若存在冲突建议：列出冲突建议摘要，提示"采纳后可能需要手动调整其他参数"
    - 确认后：调用 API → 显示成功通知 → 刷新页面
  - Props: `{ suggestion: TuningSuggestion, conflicts: TuningSuggestion[], onAdopt, onIgnore, onOpenInEditor }`

##### `features/rag-eval/components/ConflictAlert.tsx`（改造）

- [ ] **建议冲突警告**
  - 现有组件保留核心警告展示逻辑
  - 改造：`conflict_with` 从单字符串改为数组 → 展示多个冲突建议
  - 每条冲突建议显示：建议标题 + 冲突原因（直接冲突/间接冲突/效果对冲）
  - 红色边框 + 警告图标
  - Props: `{ conflictingSuggestions: TuningSuggestion[], conflictTypes: string[] }`

#### 7.2.3 API 客户端适配

##### `features/rag-eval/api/` 改造

- [ ] **路由基础路径不变**（`/api/v1/rag/eval`），但请求中增加 `pipeline_id` 参数
- [ ] **运行 API 接口适配**
  - `createRun(data)`——请求体新增 `pipeline_id`, `pipeline_version`, `simulated_role`, `auto_snapshot`
  - `getRuns(params)`——查询参数新增 `pipeline_id`
  - `getRun(id)`——响应解析新增 `cross_domain_metrics_json`, `domain_results_json`
  - `compareRuns(run1, run2)`——响应解析新增跨域指标对比
- [ ] **调优 API 接口适配**
  - `getTuningSuggestions(runId)`——响应解析新增 `target_node_id`, `target_param`
  - `adoptSuggestion(id)`——采纳后解析返回的 `ConfigVersionRead`
  - `rejectSuggestion(id, reason)`——新增驳回原因参数
- [ ] **类型定义更新**
  - `entities/rag-eval/types.ts`——新增跨域相关类型：`DomainContribution`, `CrossDomainSection`, `E2ELatencyDistribution`, `CrossDomainConflictSummary`

#### 7.2.4 "去编辑器中打开"跳转

- [ ] **路由跳转逻辑**
  - 点击 `[🔧 去编辑器中打开]` 按钮时：
    1. 构建目标 URL：`/pipelines/{pipelineId}/edit?highlightNode={target_node_id}`
    2. 使用 React Router 的 `navigate()` 跳转
    3. 传递状态：`{ fromEvalRunId: runId, highlightNode: target_node_id }`
  - 编辑视图 `PipelineCanvas.tsx` 接收 `highlightNode` 参数：
    1. 定位目标节点
    2. 设置 `selectedNodeId`（高亮 + 属性面板打开）
    3. 执行 `fitView({ nodes: [targetNode], duration: 500 })` 平滑滚动
    4. 节点边框增加脉冲动画（2 秒，橙色外发光）
  - 若目标节点不存在（管道已修改）：Toast 提示"目标节点已不存在，请手动查找"
- [ ] **面包屑导航**
  - 从评估详情回到编辑视图后，面包屑显示：`管道列表 > 管道编辑器 > 从评估跳转`

#### 7.2.5 路由迁移

- [ ] **移除独立 `/rag-eval/*` 路由段**
  - 删除旧路由配置
  - 旧 URL 访问返回 404 或重定向（按零迁移原则：直接 404）
- [ ] **嵌入管道工作台评估视图**
  - 评估历史列表：`/pipelines/:id/evaluate`——`PipelineWorkbench` 的 `evaluate` 视图
  - 评估详情：`/pipelines/:id/evaluate/:runId`——嵌套路由
  - 评估新建抽屉：在评估历史列表页内打开（不单独路由）
- [ ] **测试数据页保持不变（独立于评估路由）**
  - 路径：`/knowledge/test-data`
  - 3 选项卡：用例、测试集、草稿（复用已有组件，适配新路由）

---

## 3. 关键实现细节

### 3.1 PipelineCompiler 集成

**改造核心**：`TestCaseExecutor` 从直接调用检索服务改为通过 `PipelineCompiler` 执行完整管道搜索。

**改造前**：
```python
# 直调检索服务
retrieval_fn = lambda query: self._retrieval.retrieve_knowledge(query, limit=5)
retrieved = await retrieval_fn(test_case.query)
```

**改造后**：
```python
# 通过 PipelineCompiler 执行管道
result = await self._pipeline_compiler.execute(
    pipeline_config=pipeline_config,
    query=test_case.query,
    search_params={"top_k": 5},
    auth_context=self._auth_context_provider.get_context(
        user_id=run.run_as_user_id,
        simulated_role_id=run.simulated_role_id,
    ),
)
retrieved_ids = [d["id"] for d in result.get("documents", [])]
retrieved_contexts = [d["content"] for d in result.get("documents", [])]
domain_results = result.get("domain_results", {})  # 新增提取
```

**关键约束**：
- 评估运行不经过限流中间件——走内部执行通道，不计入搜索 QPS 配额
- 同一 PipelineCompiler 实例被评估和生产搜索共享（编译结果无状态，并发安全）
- PipelineCompiler 不可用时抛出 `NodeExecutionError`，由 `TestCaseExecutor` 捕获并记录为 `failure_stage="pipeline_error"`

### 3.2 认证上下文注入

**认证链**：
```
用户发起评估 → POST /runs (含 simulated_role 参数)
    → BatchTestRunner.execute_run()
        → 读取 run.run_as_user_id + run.simulated_role_id
        → auth_context_provider.get_context(user_id, simulated_role_id)
            → 若无 simulated_role：使用用户自身角色
            → 若有 simulated_role：检查用户是否有权限模拟该角色
                → 无权限：返回 AppException(SIMULATED_ROLE_NOT_ALLOWED, 403)
        → 注入到每个 TestCaseExecutor.execute() 调用
```

**角色感知评估的关键行为**：
- 管理员以"普通医生"身份运行评估 → PipelineCompiler 执行时 ACL 过滤器使用"普通医生"的角色权限 → 检索结果受限 → 指标差异
- **这不是 bug，是设计意图**。管道对比功能限制在同一角色视域内（苹果比苹果）

### 3.3 跨域评估指标

**Ground Truth 来源**：
| 指标 | Ground Truth | 来源 |
|------|------------|------|
| 域激活准确率 | `relevant_domains` | 测试用例创建/导入时人工标注 |
| 跨域覆盖率 | `relevant_domains` + 各域实际贡献 | PipelineCompiler 返回的 domain_results |
| 冲突检测率 | `expected_conflicts` | 测试用例中人工标注的已知跨域矛盾 |
| 端到端延迟 P95 | 无需 GT | 纯计算指标，从 execution_time_ms 统计 |

**N/A 处理规则**：
- `relevant_domains` 为空 → 域激活准确率和跨域覆盖率返回 N/A，综合得分分母排除
- `expected_conflicts` 为空 → 冲突检测率返回 N/A（说明：无 ground truth 无法评估）
- 端到端延迟永远有值

**综合得分计算更新**：
```
overall_score = L1 × 0.4 + L2 × 0.4 + L3 × 0.15 + cross_domain × 0.05
其中 cross_domain = avg(各跨域指标通过率), N/A 指标不计入分母
权重可配置 (L2 评估配置版本)
```

### 3.4 内联调优闭环

**操作流程**：
```
评估详情页 [采纳此建议]
    → POST /api/v1/rag/eval/tuning/{id}/adopt
    → ConfigChanger.apply_suggestion()
        → 解析 target_node_id / target_param / val
        → PipelineCompiler.update_node_config()
        → 创建 eval_config_versions 记录 (含完整 config_snapshot + change_summary)
        → 创建 eval_config_change_sets 记录 (关联版本)
        → 更新 tuning_suggestions 状态 (adopted + applied_config_version_id)
    → 前端收到 ConfigVersionRead
    → Toast: "已采纳并创建配置版本 cv_004，可回滚"
    → 按钮变为 [✓ 已采纳] 灰色态
```

**冲突处理**：
- 采纳前检测 `conflict_with`（非空 `list[str]` 时前端展示冲突警告）
- 弹窗确认："该建议与其他 X 条建议冲突，仍要采纳？"
- 不阻止采纳——最终决策权在用户

### 3.5 "去编辑器中打开"跳转

**完整交互流程**：
```
评估详情页 → 点击 [🔧 去编辑器中打开]
    → navigate(`/pipelines/${pipelineId}/edit?from=eval&highlightNode=${targetNodeId}`)
    → PipelineWorkbench 切换到 edit 视图
    → PipelineCanvas 解析 URL 参数
        → 找到 targetNodeId → 设置 selectedNodeId
        → fitView({ nodes: [{ id: targetNodeId }], duration: 500 })
        → 节点添加 CSS class "node-highlight-pulse"（橙色外发光动画，2 秒后自动消失）
        → PropertyPanel 自动展开目标节点的属性编辑表单
        → URL 参数清除（避免刷新后重复高亮）
```

**异常情况**：
- 目标节点已在当前管道中被删除 → Toast "目标节点已不存在，请手动查找对应参数"
- 用户删除节点但未保存 → 节点仍在，正常高亮

### 3.6 快照浅拷贝 + 冻结保护

**存储策略**：
- 快照仅记录 MySQL 行数据（元数据引用），不复制向量数据到磁盘
- 每条快照约 KB 级存储开销
- 不额外消耗向量存储配额

**冻结保护**：
- 快照创建时调用 `DocumentRepository.mark_frozen(doc_ids)`
- 被冻结文档：`DocumentService.delete()` 返回 `AppException(DOCUMENT_FROZEN, 409)`
- 被冻结分块：`RebuildService.rebuild()` 跳过冻结分块（不出错，但记录 warning 日志）
- 快照过期/删除时调用 `DocumentRepository.unmark_frozen(doc_ids)`
- **注意**：冻结的文档/分块仍计入文档数和分块数配额（物理数据仍在）

**快照失效检测**：
- 触发条件：知识库执行了向量后端迁移（Chroma → ES）
- 检测方法：`SnapshotManager.check_validity()` 对比当前后端类型与快照记录
- 失效后：`status=invalid`，评估运行创建时不可选择
- 注意：快照失效不影响数据完整性（旧数据在后端迁移时已被清理，快照本身无物理数据）

---

## 4. 测试策略

### 4.1 单元测试

| 测试目标 | 测试文件 | 覆盖场景 |
|---------|---------|---------|
| PipelineCompiler mock 适配 | `tests/unit/rag_eval/run/test_executor_pipeline.py` | TestCaseExecutor 正确调用 PipelineCompiler.execute()；domain_results 正确提取；异常时回退到错误状态 |
| 权限上下文注入 | `tests/unit/rag_eval/run/test_auth_context.py` | BatchTestRunner 在执行前注入正确 auth_context；无权限模拟角色时抛出 SIMULATED_ROLE_NOT_ALLOWED |
| 域激活准确率计算 | `tests/unit/rag_eval/metrics/test_domain_activation_acc.py` | 全激活(1.0) / 部分激活(0.6) / 全未激活(0.0)；空 relevant_domains → N/A |
| 跨域覆盖率计算 | `tests/unit/rag_eval/metrics/test_cross_domain_coverage.py` | 全覆盖 / 部分覆盖；无贡献域不影响分子 |
| 冲突检测率计算 | `tests/unit/rag_eval/metrics/test_conflict_detection_rate.py` | 全检测 / 部分检测 / 零检测；空 expected_conflicts → N/A |
| 端到端延迟计算 | `tests/unit/rag_eval/metrics/test_e2e_latency.py` | P50/P95/P99 正确计算；单用例/多用例/空用例处理 |
| 冲突检测器 | `tests/unit/rag_eval/tuning/test_conflict_detector.py` | 参数直接冲突（top_k 双重建议）；参数间接冲突（vector_weight + keyword_weight ≠ 1）；效果对冲（提升精度 vs 提升召回）；多冲突 JSON 数组格式 |
| 调优建议跨域生成 | `tests/unit/rag_eval/tuning/test_cross_domain_advisor.py` | domain_activation_miss 触发；cross_domain_imbalance 触发；conflict_undetected 触发；latency_bottleneck 触发 |
| 快照有效性检测 | `tests/unit/rag_eval/snapshot/test_validity.py` | 后端类型匹配 → valid；后端类型不匹配 → invalid；expired 状态验证 |
| 报告跨域章节构建 | `tests/unit/rag_eval/report/test_cross_domain_section.py` | 所有域有贡献 / 部分域有贡献；冲突统计正确；延迟分布正确 |

### 4.2 集成测试

| 测试目标 | 测试文件 | 覆盖场景 |
|---------|---------|---------|
| 完整评估运行 (mock PipelineCompiler) | `tests/integration/rag_eval/test_run_full.py` | 创建 run → execute → post_run_pipeline → 报告生成 → 状态 completed |
| 跨域指标完整链路 | `tests/integration/rag_eval/test_cross_domain_eval.py` | 用例含 relevant_domains / expected_conflicts → 运行 → 跨域指标计算 → 报告跨域章节 |
| 角色感知评估验证 | `tests/integration/rag_eval/test_role_aware_eval.py` | 同一管道 + 同一测试集 + 管理员 vs 普通医生 → 检索结果/指标不同 |
| 管道版本对比评估 | `tests/integration/rag_eval/test_pipeline_comparison.py` | v2 vs v3 同一测试集 → 指标差异正确 → compare 端点返回 metric_deltas |
| 调优采纳全流程 | `tests/integration/rag_eval/test_tuning_adopt.py` | 采纳 → ConfigChanger → 配置版本创建 → 管道配置更新 → 可回滚 |
| 快照创建与恢复 | `tests/integration/rag_eval/test_snapshot.py` | 浅拷贝创建；多后端 mock；冻结保护（删除被拦截）；过期清理；无效快照检测 |
| SSE 进度事件 | `tests/integration/rag_eval/test_run_sse.py` | 完整事件序列（12 种事件类型）；断线重连；心跳；完成后 30 秒关闭 |
| 报告 superseded | `tests/integration/rag_eval/test_report_superseded.py` | 同一 run 生成两次报告 → 旧报告 superseded → 新报告 completed |

### 4.3 关键测试场景（14 个）

| # | 场景 | 类型 | 验证点 |
|---|------|------|--------|
| 1 | **完整评估→报告**：含 10 用例的运行，mock PipelineCompiler 返回预设结果，验证 post_run_pipeline 全链路 | 集成 | 创建→执行→指标计算→诊断→调优→报告→completed |
| 2 | **跨域指标 N/A 处理**：用例无 relevant_domains → 跨域指标 N/A → 综合得分分母排除 | 单元+集成 | cross_domain 返回 None；overall_score 分母不含跨域权重 |
| 3 | **跨域冲突检测**：用例标注 expected_conflicts → 管路检测到部分冲突 → 冲突检测率 ∈ [0,1] | 集成 | ConflictDetectionRateCalc 正确；报告冲突统计展示 |
| 4 | **权限注入验证**：管理员 vs 普通医生同一测试集 → 检索结果不同 → 指标不同 | 集成 | BatchTestRunner 注入正确 auth_context；PipelineCompiler 返回不同结果 |
| 5 | **管道版本对比**：pipeline v2 vs v3 同一测试集 → 指标差异 → metric_deltas | 集成 | compare_runs() 计算正确；跨域指标也参与对比 |
| 6 | **多角色评估**：管理员模拟"普通医生"和"药师"两个角色 → 产生两次运行 → 结果不同 | 集成 | cross_role_evaluation() 正确；角色列展示不同身份 |
| 7 | **并发控制**：同时启动 3 个运行 → 第三个被拒绝（max_concurrent_runs=2） | 单元 | AppException(RUN_LIMIT_EXCEEDED) 抛出 |
| 8 | **快照冻结保护**：创建快照后删文档 → 409 DOCUMENT_FROZEN 拦截 | 集成 | mark_frozen() 生效；delete 被拒绝 |
| 9 | **快照失效检测**：向量后端迁移 → 旧快照 invalid → 评估运行不可选 | 单元 | check_validity() 正确判断 |
| 10 | **调优采纳冲突**：采纳建议后检测到与另一条冲突 → ConflictAlert 展示 → 弹窗确认后仍可采纳 | 单元 | ConflictDetector 返回 conflict_with 列表 |
| 11 | **报告 superseded**：同一 run 两次报告 → 旧 superseded → 新 completed | 集成 | superseded 状态正确；GET /reports 只返回最新 |
| 12 | **坏案 N/A 排除**：空答案 → 各项指标 N/A → L2 分母排除 | 单元+集成 | calculate_all() 跳过 N/A；分母不计入 |
| 13 | **L3 LLM 诊断降级**：LLM 429 → 诊断层 status=skipped → 不阻塞其他层 | 单元 | DiagnosisOrchestrator.run_layer(3) 转 skipped |
| 14 | **去编辑器中打开**：采纳后 target_node_id → 前端跳转 PipelineCanvas 并高亮节点 | 集成 | URL 参数传递正确；节点 fitView + 脉冲动画 |

---

## 5. 验收检查点

### 现有功能保留

| AC | 内容 | 验证方式 |
|----|------|---------|
| AC-6.1 | 全部 12 项三层指标正确计算，阈值校验有效 | 场景 1 + 单元测试 L1/L2/L3 计算器 |
| AC-6.2 | 六层诊断全部执行，每层输出正确的问题列表 | 场景 1 + 单元测试 L1-L6 诊断层 |
| AC-6.3 | 草稿自动生成 → 审核 → 导入为用例完整流程 | 现有测试继承，无需重写 |
| AC-6.4 | 测试集创建、用例关联、导出功能完整 | 现有集成测试继承 |
| AC-6.5 | 评估运行 SSE 进度推送全部事件类型正确触发 | 场景 6（SSE 事件序列） |
| AC-6.6 | 评估运行并发控制：全局 ≤2 运行，单运行 ≤5 并发 | 场景 7 |
| AC-6.7 | 后处理流水线自动触发，指标计算和报告生成成功 | 场景 1 |
| AC-6.8 | 报告导出正确（Markdown/JSON/CSV 三种格式） | 集成测试 ReportExporter |
| AC-6.9 | 调优建议自动生成，采纳/驳回/忽略操作有效 | 场景 10 + 单元测试 TuningEngineFacade |
| AC-6.10 | 采纳建议后自动创建配置版本，回滚可用 | 场景 10 + 集成测试 ConfigChanger.rollback() |
| AC-6.11 | 知识库快照创建/恢复正确冻结知识库状态 | 场景 8（冻结）+ 场景 9（失效） |
| AC-6.12 | 坏案过滤：N/A 用例不计入指标分母 | 场景 12 |
| AC-6.13 | 报告 superseded 状态正确 | 场景 11 |

### 平台化新增

| AC | 内容 | 验证方式 |
|----|------|---------|
| AC-6.14 | 跨域指标（域激活准确率/跨域覆盖率/冲突检测率/延迟）正确计算 | 场景 2 + 场景 3 |
| AC-6.15 | 评估运行注入权限上下文，同一管道不同角色指标不同 | 场景 4 |
| AC-6.16 | 评估数据集按租户隔离、按角色控制可见性 | 集成测试（tenant_id + visibility） |
| AC-6.17 | 管道对比限制在同一角色视域内 | 场景 5 |
| AC-6.18 | 管道版本对比——同一数据集对比两个版本 | 场景 5 |
| AC-6.19 | 报告跨域分析章节正确展示（域贡献度、冲突统计、延迟分布） | 场景 3 + 场景 1 |

### 前端改造

| AC | 内容 | 验证方式 |
|----|------|---------|
| AC-6.20 | 测试数据在 `/knowledge/test-data` 下，三选项卡切换正常 | 前端集成测试（路由 + 组件渲染） |
| AC-6.21 | TestCase 创建表单含 expected_knowledge_ids、difficulty_level、relevant_domains | 前端组件测试 |
| AC-6.22 | JSON 导入增加格式校验和预览 | 前端集成测试 |
| AC-6.23 | CaseTransferModal 分页加载，支持超过 100 条用例 | 前端组件测试 |
| AC-6.24 | 管道评估视图正确展示评估历史（名称/测试集/角色/状态/得分/耗时） | 前端集成测试 |
| AC-6.25 | 新建评估抽屉正确加载测试集列表、管道版本、角色模拟选项 | 前端集成测试 |
| AC-6.26 | 模拟角色评估——管理员以普通医生身份运行，结果反映权限差异 | 场景 4 + 前端集成测试 |
| AC-6.27 | 选中 2 个运行对比 → 并排展示指标差异（绿升红降） | 前端组件测试（RunComparison） |
| AC-6.28 | 评估详情页一页内展示指标/诊断/域分析/内联建议/失败用例 | 前端集成测试 |
| AC-6.29 | 域分析区块展示各域贡献度、激活准确率、冲突统计 | 前端组件测试（DomainContribChart） |
| AC-6.30 | "去编辑器中打开"点击后切换到编辑视图并高亮对应节点 | 前端集成测试（路由跳转 + 节点高亮 + 脉冲动画） |
| AC-6.31 | 内联调优"采纳"后自动修改管道参数 + 创建配置版本 | 场景 10 + 前端集成测试 |
| AC-6.32 | conflict 正确检测多条建议修改同一参数 | 场景 10 |
| AC-6.33 | 提示词页面存根已移除，提示词归入 `/settings/config` | 前端路由测试（旧路由 404） |
| AC-6.34 | TrendChart 正确部署于评估视图和详情概览 | 前端组件测试（TrendChart 渲染 + 数据绑定） |

---

## 6. 风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| PipelineCompiler 性能瓶颈 | 评估大量用例时执行时间过长 | 单运行并发控制（5 并发）；PipelineCompiler 编译结果缓存 |
| 权限上下文注入错误 | 角色模拟评估结果不可靠 | 单元测试覆盖 AuthContext 构造逻辑；集成测试验证角色差异 |
| 跨域指标 ground truth 不足 | 无 relevant_domains 的用例跨域指标全部 N/A | 返回 N/A 并明确标注；从综合得分分母排除；UI 提示需补充标注 |
| 快照冻结与索引重建冲突 | 冻结分块阻挡重建 | 重建时跳过冻结分块并记录 warning；重建完成后通知用户哪些分块被跳过 |
| 旧 `/rag-eval/*` 路由访问 | 用户书签失效 | 按零迁移原则：直接 404；文档说明新 URL 路径 |
| 调优采纳影响生产 | 参数改动立即生效 | 采纳后自动创建配置版本（可回滚）；建议先做评估验证 |
