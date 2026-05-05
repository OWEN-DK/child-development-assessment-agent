import { useParams, useNavigate } from 'react-router-dom';
import {
  Space, Button, Typography, Alert, Row, Col, Card, Divider, Spin, message, Descriptions,
} from 'antd';
import { FileMarkdownOutlined, FileTextOutlined, FileExcelOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import type {
  MetricCard, LayerMetrics, RunMetrics,
  DiagnosisSection, DiagnosisResult, LayerResult, BadCaseEntry, TuningEntry, ScoringDashboardData,
} from '@entities/rag-eval';
import { useReport, useExportReport } from '../hooks/useReports';
import { ScoringDashboard } from '../components/metrics/ScoringDashboard';
import { DiagnosisPanel } from '../components/diagnosis/DiagnosisPanel';
import { BadCaseTable } from '../components/report/BadCaseTable';
import { SuggestionPanel } from '../components/tuning/SuggestionPanel';
import { formatPercent, formatDuration, formatTimestamp } from '@entities/rag-eval';

const { Title, Text } = Typography;

/** MetricCard[] → LayerMetrics ({ [name]: MetricScore }) */
function cardsToLayerMetrics(cards: MetricCard[]): LayerMetrics {
  const result: LayerMetrics = {};
  for (const c of cards) {
    result[c.name] = { value: c.value, passed: c.passed, threshold: c.threshold, details: c.details };
  }
  return result;
}

/** ScoringDashboardData → RunMetrics */
function dashboardToRunMetrics(dashboard: ScoringDashboardData, overallScore: number): RunMetrics {
  return {
    l1: cardsToLayerMetrics(dashboard.l1),
    l2: cardsToLayerMetrics(dashboard.l2),
    l3: cardsToLayerMetrics(dashboard.l3),
    overall_score: overallScore,
  };
}

/** DiagnosisSection[] → DiagnosisResult */
function sectionsToDiagnosis(sections: DiagnosisSection[], overallHealth: number, totalIssues: number, criticalIssues: number): DiagnosisResult {
  const toLayerResult = (s: DiagnosisSection): LayerResult => ({
    layer: s.layer,
    name: s.name,
    status: s.status as LayerResult['status'],
    score: s.score,
    issues: s.issues,
    details: {},
  });
  const empty: LayerResult = { layer: 0, name: '', status: 'skip', score: 0, issues: [], details: {} };
  const byLayer: Record<number, LayerResult> = {};
  for (const s of sections) {
    byLayer[s.layer] = toLayerResult(s);
  }
  return {
    layer1: byLayer[1] || { ...empty, layer: 1 },
    layer2: byLayer[2] || { ...empty, layer: 2 },
    layer3: byLayer[3] || { ...empty, layer: 3 },
    layer4: byLayer[4] || { ...empty, layer: 4 },
    layer5: byLayer[5] || { ...empty, layer: 5 },
    layer6: byLayer[6] || { ...empty, layer: 6 },
    overall_health: overallHealth,
    total_issues: totalIssues,
    critical_issues: criticalIssues,
  };
}

/** BadCaseEntry → BadCaseTable 期望的格式 */
function mapBadCases(cases: BadCaseEntry[]) {
  return cases.map((c) => ({
    query: c.query,
    domain: (c.domain || '') as any,
    age: c.age ?? 0,
    precision: c.precision ?? 0,
    recall: c.recall ?? 0,
    error_message: c.error_message ?? null,
  }));
}

/** TuningEntry → SuggestionPanel 期望的 TuningSuggestion 格式 */
function mapTuningSuggestions(entries: TuningEntry[]) {
  return entries.map((t) => ({
    id: t.suggestion_id,
    run_id: '',
    category: t.category,
    severity: t.severity as any,
    title: t.title,
    description: t.description,
    current_value: t.current_value ?? '',
    suggested_value: t.suggested_value ?? '',
    config_key: '',
    status: 'pending' as any,
    conflict_ids: t.conflict_with ? [t.conflict_with] : [],
    created_at: '',
  }));
}

export function ReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const navigate = useNavigate();
  const { data: report, isLoading, isError } = useReport(reportId || '');
  const exportMutation = useExportReport();

  const handleExport = (format: 'json' | 'csv' | 'pdf') => {
    if (!reportId) return;
    exportMutation.mutate({ reportId, format });
  };

  if (isLoading) {
    return <Spin size="large" style={{ display: 'block', marginTop: 100 }} />;
  }

  if (isError || !report) {
    return (
      <div>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/rag-eval/reports')} style={{ marginBottom: 16 }}>
          返回列表
        </Button>
        <Alert type="error" message="加载报告失败" showIcon />
      </div>
    );
  }

  const metrics = dashboardToRunMetrics(report.scoring_dashboard, report.overall_score);
  const diagnosis = sectionsToDiagnosis(
    report.diagnosis_details,
    report.summary.diagnosis_health,
    report.summary.total_issues,
    report.summary.critical_issues,
  );
  const badCases = mapBadCases(report.bad_cases);
  const suggestions = mapTuningSuggestions(report.tuning_suggestions);

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/rag-eval/reports')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          报告详情：{report.run_name}
        </Title>
        <Space>
          <Button icon={<FileMarkdownOutlined />} onClick={() => handleExport('pdf')}>PDF</Button>
          <Button icon={<FileTextOutlined />} onClick={() => handleExport('json')}>JSON</Button>
          <Button icon={<FileExcelOutlined />} onClick={() => handleExport('csv')}>CSV</Button>
        </Space>
      </div>

      {/* 概要信息 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions size="small" column={4}>
          <Descriptions.Item label="综合得分">
            <Text strong style={{ fontSize: 18, color: report.overall_score >= 0.7 ? '#52c41a' : report.overall_score >= 0.5 ? '#faad14' : '#ff4d4f' }}>
              {formatPercent(report.overall_score, 1)}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="通过/总数">{report.passed_test_cases} / {report.total_test_cases}</Descriptions.Item>
          <Descriptions.Item label="耗时">{report.duration_seconds ? formatDuration(report.duration_seconds) : '-'}</Descriptions.Item>
          <Descriptions.Item label="生成时间">{formatTimestamp(report.created_at)}</Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 三层指标看板 */}
      <Divider />
      <ScoringDashboard metrics={metrics} />

      {/* 六层诊断 */}
      <Divider />
      <DiagnosisPanel diagnosis={diagnosis} />

      {/* 坏案 + 调优建议 */}
      <Divider />
      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Title level={5}>Bad Cases</Title>
          <BadCaseTable cases={badCases as any} />
        </Col>
        <Col xs={24} lg={12}>
          <Title level={5}>调优建议</Title>
          <SuggestionPanel
            suggestions={suggestions as any}
            onAdopt={() => message.info('请在报告页操作')}
            onReject={() => message.info('请在报告页操作')}
            onIgnore={() => message.info('请在报告页操作')}
          />
        </Col>
      </Row>
    </div>
  );
}
