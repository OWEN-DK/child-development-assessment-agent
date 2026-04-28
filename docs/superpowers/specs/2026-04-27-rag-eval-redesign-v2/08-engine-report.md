# 08 - ReportEngine 详细设计

## 需求

整合双轨评估结果（三层指标 + 六层诊断），生成结构化的评估报告，支持 Markdown 渲染、趋势分析和多格式导出。

## 当前问题

| 问题 | 位置 | 影响 |
|------|------|------|
| 双轨结果分散 | `rag_report_service.py` + `report/` 目录 | 无统一报告视图 |
| 报告无诊断内容 | 只含指标得分 | 缺少具体问题分析 |
| 无趋势分析 | 缺失 | 无法追踪配置变更效果 |
| 导出格式有限 | 仅 JSON | 不支持 PDF/CSV |
| 报告渲染耦合生成 | Markdown 硬编码在 service 中 | 无法切换渲染策略 |

## 引擎架构

```
ReportEngineFacade (report/facade.py, ~100行)
  ├── ReportBuilder (report/builder.py, ~200行)
  ├── MarkdownRenderer (report/markdown_renderer.py, ~100行)
  ├── TrendAnalyzer (report/trend_analyzer.py, ~120行)
  └── ReportExporter (report/exporter.py, ~100行)
```

## 组件设计

### ReportEngineFacade

```python
class ReportEngineFacade:
    """报告引擎门面"""

    def __init__(
        self,
        builder: ReportBuilder,
        markdown_renderer: MarkdownRenderer,
        trend_analyzer: TrendAnalyzer,
        exporter: ReportExporter,
        report_repository: ReportRepository,
        test_run_repository: TestRunRepository,
        config_manager: ConfigManager,
    ): ...

    async def generate_report(self, run_id: str) -> EvalReportRead:
        """生成完整评估报告

        1. 验证 run 存在且 status=completed
        2. builder.build(run_id) → EvalReportData
        3. markdown_renderer.render(report_data) → markdown_content
        4. 保存到 eval_reports
        5. 返回 EvalReportRead
        """

    async def get_report(self, report_id: str) -> EvalReportRead:
        """获取报告"""

    async def list_reports(
        self,
        page: int = 1,
        page_size: int = 20,
        test_set_id: str | None = None,
    ) -> list[EvalReportRead]:
        """列出报告"""

    async def get_trend(
        self,
        metric: str | None = None,
        limit: int = 10,
    ) -> TrendData:
        """获取趋势数据"""

    async def export_report(
        self,
        report_id: str,
        format: str = "markdown",
    ) -> bytes:
        """导出报告

        format: markdown / json / csv / pdf
        """

    async def compare_runs(
        self,
        run_id_1: str,
        run_id_2: str,
    ) -> RunComparison:
        """比较两个运行（委托给 RunEngineFacade.compare_runs 的报告视图）"""
```

### ReportBuilder

```python
class ReportBuilder:
    """整合双轨评估结果，构建报告数据

    核心职责：将 RunMetrics + DiagnosisResult + 坏案 + 调优建议整合为 EvalReportData。
    """

    def __init__(
        self,
        metric_engine: MetricEngineFacade,
        tuning_engine: TuningEngineFacade,
        test_run_repository: TestRunRepository,
        test_run_result_repository: TestRunResultRepository,
        tuning_suggestion_repository: TuningSuggestionRepository,
    ): ...

    async def build(self, run_id: str) -> EvalReportData:
        """构建完整报告数据

        1. 获取 run 基本信息
        2. 获取 RunMetrics（从 test_runs.l1/l2/l3_metrics_json 读取）
        3. 获取 DiagnosisResult（从 test_runs.diagnosis_json 读取）
        4. 收集坏案列表（passed=false 的 results）
        5. 获取调优建议（tuning_suggestions where run_id）
        6. 构建 EvalReportData
        """

    def _build_overall_summary(
        self,
        metrics: RunMetrics,
        diagnosis: DiagnosisResult,
    ) -> OverallSummary:
        """构建总体摘要

        包含：
        - overall_score
        - 各层得分
        - 诊断健康度
        - 关键问题数
        """

    def _build_scoring_dashboard(
        self,
        metrics: RunMetrics,
    ) -> ScoringDashboard:
        """构建三层指标看板数据

        L1: 5 个 MetricScore 卡片
        L2: 3 个 MetricScore 卡片
        L3: 4 个 MetricScore 卡片
        每个卡片显示：value, passed, threshold, 变化趋势（与上次对比）
        """

    def _build_diagnosis_details(
        self,
        diagnosis: DiagnosisResult,
    ) -> list[DiagnosisSection]:
        """构建六层诊断详情

        每层一个 section：
        - layer: 层号
        - name: 层名称
        - status: pass/warn/fail
        - score: 健康度
        - issues: 问题列表（可折叠）
        - suggestions: 修复建议
        """

    def _build_bad_cases_table(
        self,
        bad_cases: list[TestRunResultItem],
    ) -> list[BadCaseEntry]:
        """构建坏案表

        每条包含：query, domain, age, expected vs actual, 具体指标
        """

    def _build_tuning_section(
        self,
        suggestions: list[TuningSuggestion],
    ) -> list[TuningEntry]:
        """构建调优建议区域

        按优先级排序，包含冲突标记
        """
```

**Schema:**

```python
class OverallSummary(BaseModel):
    """报告总体摘要"""
    overall_score: float
    l1_score: float
    l2_score: float
    l3_score: float
    diagnosis_health: float
    total_issues: int
    critical_issues: int
    run_name: str
    total_cases: int
    passed_cases: int
    duration_ms: int | None = None

class MetricCard(BaseModel):
    """指标卡片"""
    name: str
    value: float
    passed: bool
    threshold: float
    details: dict[str, Any] = {}
    delta: float | None = None          # 与上次对比的变化值

class ScoringDashboard(BaseModel):
    """三层指标看板"""
    l1: list[MetricCard]
    l2: list[MetricCard]
    l3: list[MetricCard]

class DiagnosisSection(BaseModel):
    """诊断层 section"""
    layer: int
    name: str
    status: str
    score: float
    issues: list[LayerIssue]
    suggestions: list[str]

class BadCaseEntry(BaseModel):
    """坏案条目"""
    case_id: str
    query: str
    domain: str
    age: float
    expected_keywords: list[str]
    actual_answer: str | None
    precision: float | None
    recall: float | None
    error_message: str | None

class TuningEntry(BaseModel):
    """调优建议条目"""
    suggestion_id: str
    category: str
    severity: str
    title: str
    description: str
    current_value: Any | None
    suggested_value: Any | None
    expected_impact: str | None
    conflict_with: str | None

class EvalReportData(BaseModel):
    """完整报告数据（中间结构，不直接持久化）"""
    summary: OverallSummary
    scoring_dashboard: ScoringDashboard
    diagnosis_details: list[DiagnosisSection]
    bad_cases: list[BadCaseEntry]
    tuning_suggestions: list[TuningEntry]

class EvalReportRead(BaseModel):
    """报告读取 Schema"""
    id: str
    run_id: str
    test_set_id: str | None = None
    config_version_id: str | None = None
    status: str                          # processing/completed/superseded
    summary: OverallSummary
    scoring_dashboard: ScoringDashboard
    diagnosis_details: list[DiagnosisSection]
    bad_cases: list[BadCaseEntry]
    tuning_suggestions: list[TuningEntry]
    markdown_content: str | None = None
    created_at: datetime
```

### MarkdownRenderer

```python
class MarkdownRenderer:
    """将 EvalReportData 渲染为 Markdown"""

    def render(self, data: EvalReportData) -> str:
        """渲染完整 Markdown 报告

        结构：
        1. # 评估报告: {run_name}
           总体得分、通过率、执行时间

        2. ## 📊 三层指标看板
           ### L1 检索质量
           表格：指标名 | 得分 | 阈值 | 状态 | 变化
           ### L2 生成质量（同上）
           ### L3 系统质量（同上）

        3. ## 🔍 六层诊断详情
           <details> 展开/折叠
           ### Layer 1: 规则引擎 ✅/⚠️/❌
           问题列表 + 建议
           ...（每层一个 details）

        4. ## ❌ 坏案分析
           表格：问题 | 领域 | 年龄 | 精确率 | 召回率 | 错误信息

        5. ## 🔧 调优建议
           按优先级排序，标记冲突

        6. ## 📈 趋势摘要
           最近 N 次运行的得分变化
        """

    def _render_metric_table(self, cards: list[MetricCard], title: str) -> str:
        """渲染指标表格"""

    def _render_diagnosis_section(self, section: DiagnosisSection) -> str:
        """渲染诊断层（用 <details> 标签）"""

    def _render_bad_cases_table(self, cases: list[BadCaseEntry]) -> str:
        """渲染坏案表格"""

    def _render_status_emoji(self, status: str) -> str:
        """状态 emoji 映射：pass→✅, warn→⚠️, fail→❌"""
```

### TrendAnalyzer

```python
class TrendAnalyzer:
    """指标趋势分析——按配置版本追踪指标变化"""

    def __init__(
        self,
        report_repository: ReportRepository,
        test_run_repository: TestRunRepository,
        config_version_repository: ConfigVersionRepository,
    ): ...

    async def get_trend(
        self,
        metric: str | None = None,
        limit: int = 10,
    ) -> TrendData:
        """获取趋势数据

        1. 查询最近 limit 个 completed 状态的 run
        2. 按 created_at 排序
        3. 提取每个 run 的指定指标（或所有核心指标）
        4. 构建 TrendData
        """

    async def get_metric_delta_by_config(
        self,
        config_version_id: str,
    ) -> dict[str, float]:
        """按配置版本计算指标变化

        对比使用该配置版本的 run 与前一版本的指标差异。
        """

    async def get_run_delta(self, run_id: str) -> dict[str, float]:
        """计算指定 run 与前一次 run 的指标变化"""
```

**Schema:**

```python
class TrendData(BaseModel):
    """趋势数据"""
    run_ids: list[str]
    timestamps: list[datetime]
    overall_scores: list[float]
    metric_trends: dict[str, list[float]]  # {"context_precision": [0.7, 0.75, ...], ...}
    config_version_ids: list[str | None]   # 每个 run 的配置版本
```

### ReportExporter

```python
class ReportExporter:
    """报告导出为多种格式"""

    async def export_json(self, report: EvalReportRead) -> bytes:
        """导出为 JSON"""

    async def export_csv(self, report: EvalReportRead) -> bytes:
        """导出为 CSV（指标 + 坏案两张表）"""

    async def export_markdown(self, report: EvalReportRead) -> bytes:
        """导出为 Markdown（直接使用 markdown_content）"""

    async def export_pdf(self, report: EvalReportRead) -> bytes:
        """导出为 PDF

        方案：Markdown → HTML（使用 markdown 库）→ PDF（使用 weasyprint 或 pdfkit）
        若 PDF 依赖库不可用，抛 AppException(REPORT_EXPORT_FAILED)
        """
```

## 报告持久化

报告数据以两种形式存储在 `eval_reports` 表中：

| 字段 | 内容 |
|------|------|
| `metrics_json` | 三层指标 `RunMetrics` JSON |
| `diagnosis_json` | 六层诊断 `DiagnosisResult` JSON |
| `bad_cases_json` | 坏案列表 JSON |
| `suggestions_json` | 调优建议列表 JSON |
| `markdown_content` | Markdown 渲染结果（LONGTEXT） |
| `overall_score` | 三层加权综合得分 |
| `l1_score` / `l2_score` / `l3_score` | 各层得分 |

读取时：从 JSON 字段反序列化为对应的 Pydantic 模型，组装为 `EvalReportRead`。

## 报告状态流转

```
processing → completed → superseded
                ↑                │
                │                │（新报告生成时，同 run 的旧报告标记为 superseded）
                └────────────────┘
```

## API 端点

| 端点 | 方法 | 功能 | 响应 |
|------|------|------|------|
| `/rag/eval/reports` | GET | 列出报告 | `APIResponse[list[EvalReportRead]]` |
| `/rag/eval/reports/{id}` | GET | 获取报告 | `APIResponse[EvalReportRead]` |
| `/rag/eval/runs/{id}/report` | POST | 生成报告 | `APIResponse[EvalReportRead]` |
| `/rag/eval/reports/{id}/export` | GET | 导出报告 | `FileResponse` |
| `/rag/eval/trends` | GET | 趋势数据 | `APIResponse[TrendData]` |

## 错误码

| 数字码 | 错误码 | HTTP | 触发场景 |
|--------|--------|------|----------|
| 13006 | `REPORT_NOT_FOUND` | 404 | 报告 ID 不存在 |
| 13022 | `REPORT_EXPORT_FAILED` | 500 | 导出失败（PDF 库不可用等） |
| 13004 | `TEST_RUN_NOT_FOUND` | 404 | run 不存在 |
| 13014 | `METRIC_CALCULATION_FAILED` | 500 | 指标数据缺失 |

## 配置 Key

| Key | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `rag.eval.report.trend_limit` | int | 10 | 趋势分析最大运行数 |
| `rag.eval.report.pdf_enabled` | bool | false | PDF 导出开关 |
| `rag.eval.report.bad_case_limit` | int | 50 | 坏案列表最大条目数 |

## 验收标准

1. `facade.py` ≤ 100 行，`builder.py` ≤ 200 行，`markdown_renderer.py` ≤ 100 行，`trend_analyzer.py` ≤ 120 行，`exporter.py` ≤ 100 行
2. `ReportBuilder.build()` 正确整合双轨数据（`RunMetrics` + `DiagnosisResult`）
3. Markdown 报告包含完整 6 个 section：总览、三层看板、六层诊断、坏案、调优、趋势
4. 六层诊断使用 `<details>` 标签折叠，每层独立展开
5. 三层指标看板以表格形式呈现，包含变化趋势（与上次对比）
6. `TrendAnalyzer.get_trend()` 返回按时间排序的趋势数据
7. `ReportExporter` 支持 JSON/CSV/Markdown 三种格式，PDF 为可选
8. 同一 run 生成新报告时，旧报告标记为 `superseded`
9. 报告的 JSON 字段（`metrics_json`, `diagnosis_json` 等）可正确反序列化
10. `EvalReportRead` 的 `scoring_dashboard` 包含 12 个 MetricCard（L1×5 + L2×3 + L3×4）
11. `ReportEngineFacade` 通过 `RagEvalModule` DI 注入
12. 所有异常使用 `AppException`，无 `HTTPException`
13. Markdown 内容写入 `LONGTEXT` 字段，不截断
