# 08 - 报告引擎详细设计

## 需求

统一当前分散在 `rag_report_service.py`（491行）和 `report/` 目录（355行）中的报告生成逻辑，消除重复代码。

## 当前问题

1. 双报告服务共存：`rag_report_service.py` 和 `report/report_generator.py` 实现相同功能
2. 7 个指标的手动均值计算重复 2 次（`generate_report` 和 `export_report`）
3. Domain 统计使用不存在的字段（`getattr(result, "domain", "未知")` 导致全部返回"未知"）
4. `report/report_generator.py` 中的 `_calculate_overall_metrics` 有 60 行重复均值代码
5. Markdown 生成逻辑分散

## 引擎架构

```
service/rag_eval/report/
├── __init__.py
├── facade.py                # ReportEngineFacade (~80行)
├── builder.py               # ReportBuilder (~150行)
├── markdown_renderer.py     # MarkdownRenderer (~80行)
├── trend_analyzer.py        # TrendAnalyzer (~100行)
└── exporter.py              # ReportExporter (~80行)
```

## 各组件职责

### ReportEngineFacade（门面）

```python
class ReportEngineFacade:
    def __init__(
        self,
        builder: ReportBuilder,
        trend_analyzer: TrendAnalyzer,
        exporter: ReportExporter,
        report_repo: ReportRepository,
        run_repo: TestRunRepository,
    ):
        self._builder = builder
        self._trend = trend_analyzer
        self._exporter = exporter
        self._report_repo = report_repo
        self._run_repo = run_repo

    async def get_or_create(self, run_id: str) -> ReportRead:
        """获取或生成报告（按需生成）"""

    async def list_reports(self, page: int, page_size: int) -> list[ReportRead]:
        """列出报告"""

    async def get_report(self, report_id: str) -> ReportRead:
        """获取报告详情"""

    async def export(self, report_id: str, format: str) -> bytes:
        """导出报告"""

    async def get_trends(self, metric_name: str | None, limit: int) -> TrendData:
        """获取趋势数据"""

    async def delete_report(self, report_id: str) -> None:
        """删除报告"""
```

### ReportBuilder（报告构建器）

```python
class ReportBuilder:
    def __init__(
        self,
        markdown_renderer: MarkdownRenderer,
        metric_engine: MetricEngineFacade,
        tuning_engine: TuningEngineFacade,
    ):
        self._renderer = markdown_renderer
        self._metrics = metric_engine
        self._tuning = tuning_engine

    async def build(self, run_id: str, run_data: TestRunRead, results: list[TestRunResultItem]) -> ReportData:
        """构建完整报告
        
        1. 计算三层指标汇总
        2. 识别 bad cases
        3. 生成调优建议
        4. 渲染 Markdown
        """

    def _compute_summary(self, results: list[TestRunResultItem]) -> ReportSummary:
        """计算报告摘要（通用指标聚合函数，替代重复的7行手动均值）"""

    def _identify_bad_cases(self, results: list[TestRunResultItem], threshold: float) -> list[TestRunResultItem]:
        """识别 bad cases（指标低于阈值的用例）"""

    def _aggregate_metrics(self, results: list[TestRunResultItem]) -> dict[str, float]:
        """通用指标聚合（替代7行手动均值重复代码）
        
        def _aggregate_metrics(self, results, metric_path):
            values = [get_nested(r, metric_path) for r in results]
            return sum(values) / max(len(values), 1)
        """
```

### MarkdownRenderer（Markdown渲染器）

```python
class MarkdownRenderer:
    def render(self, report_data: ReportData) -> str:
        """渲染完整 Markdown 报告"""

    def _render_header(self, data: ReportData) -> str: ...
    def _render_metrics_summary(self, metrics: RunMetrics) -> str: ...
    def _render_layer_detail(self, layer_name: str, metrics: dict) -> str: ...
    def _render_bad_cases(self, cases: list[TestRunResultItem]) -> str: ...
    def _render_suggestions(self, suggestions: list[TuningSuggestion]) -> str: ...
    def _render_trend_summary(self, trend: TrendData | None) -> str: ...
```

### TrendAnalyzer（趋势分析器）

```python
class TrendAnalyzer:
    def __init__(self, run_repo: TestRunRepository, metric_engine: MetricEngineFacade):
        self._run_repo = run_repo
        self._metrics = metric_engine

    async def analyze(self, metric_name: str | None, limit: int = 20) -> TrendData:
        """获取指标趋势数据
        
        1. 查询最近 N 次运行
        2. 提取指定指标的值
        3. 计算 moving average
        """

    async def get_metric_history(self, metric_name: str, run_ids: list[str]) -> list[float]:
        """获取指定指标在多个运行中的历史值"""
```

### ReportExporter（导出器）

```python
class ReportExporter:
    def export_json(self, report: ReportData) -> bytes: ...
    def export_csv(self, report: ReportData) -> bytes: ...
    async def export_pdf(self, markdown: str) -> bytes: ...
```

## 删除的旧代码

以下文件在重构完成后删除：
- `service/rag_report_service.py`（491行）→ 被 `ReportEngineFacade` 替代
- `service/report/report_generator.py`（242行）→ 被 `ReportBuilder` 替代
- `service/report/markdown_builder.py`（75行）→ 被 `MarkdownRenderer` 替代
- `service/report/report_deleter.py`（38行）→ 被 `ReportEngineFacade.delete_report` 替代

## 报告结构

生成的报告包含以下部分：

```
# RAG 评估报告
## 概览
  - 综合得分: 0.82
  - 测试用例数: 50
  - 通过/失败: 42/8
## L1 检索质量
  - Context Precision: 0.78 ✓
  - Context Recall: 0.72 ✓
  - MRR: 0.65 ✓
  - NDCG: 0.71 ✓
  - Noise Sensitivity: 0.22 ✓
## L2 生成质量
  - Faithfulness: 0.85 ✓
  - Answer Relevancy: 0.79 ✓
  - Groundedness: 0.81 ✓
## L3 系统质量
  - Rule Compliance: 1.00 ✓
  - Regression Score: 0.94 ✓
  - Cost Efficiency: 0.62 ⚠
  - Config Stability: N/A (首次运行)
## Bad Cases
  - #12: "感统训练适合3岁儿童吗" - Context Recall: 0.33
  - #27: "精细运动训练建议" - Faithfulness: 0.50
## 调优建议
  - [CRITICAL] 检索权重建议从 0.5 调整为 0.6
  - [WARNING] 成本效率低于阈值，建议减少重排序 Top-K
```

## 验收标准

1. 双报告服务合并为单一 `ReportEngineFacade`
2. 指标聚合使用通用函数，零手动重复
3. Domain 统计正确关联到 TestCase 的 domain 字段
4. 支持导出 JSON/CSV/PDF 三种格式
5. 趋势分析支持按指标过滤
6. 每个文件 < 160 行
