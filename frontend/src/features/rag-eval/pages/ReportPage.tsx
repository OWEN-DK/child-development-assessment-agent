import { useState, useCallback } from 'react';
import {
  Space, Button, Typography, Select, Spin, Alert, Empty, Row, Col, Card, Divider, message,
} from 'antd';
import { FileMarkdownOutlined, FileTextOutlined, FileExcelOutlined } from '@ant-design/icons';
import type { TestDomain } from '@entities/rag-eval';
import { useReports, useReport, useExportReport } from '../hooks/useReports';
import { useRunMetrics, useRunDiagnosis } from '../hooks/useMetrics';
import { ScoringDashboard } from '../components/metrics/ScoringDashboard';
import { DiagnosisPanel } from '../components/diagnosis/DiagnosisPanel';
import { ReportHeader } from '../components/report/ReportHeader';
import { BadCaseTable } from '../components/report/BadCaseTable';
import { SuggestionPanel } from '../components/tuning/SuggestionPanel';
import { useTuningSuggestions, useAdoptSuggestion, useRejectSuggestion, useIgnoreSuggestion } from '../hooks/useTuning';

const { Title } = Typography;

const MOCK_BAD_CASES: Array<{ query: string; domain: TestDomain; age: number; precision: number; recall: number; error_message: string | null }> = [];

export function ReportPage() {
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);

  const { data: reportsData, isLoading: reportsLoading, isError: reportsError } = useReports();
  const { data: report, isLoading: reportLoading } = useReport(selectedReportId || '');
  const { data: metrics } = useRunMetrics(selectedReportId || '');
  const { data: diagnosis } = useRunDiagnosis(selectedReportId || '');
  const { data: suggestionsData = [] } = useTuningSuggestions(selectedReportId || '');

  const adoptMutation = useAdoptSuggestion();
  const rejectMutation = useRejectSuggestion();
  const ignoreMutation = useIgnoreSuggestion();
  const exportMutation = useExportReport();

  const reports = reportsData?.items || [];
  const runId = report?.run_id || selectedReportId || '';

  const handleExport = useCallback((format: 'json' | 'csv' | 'pdf') => {
    if (!selectedReportId) return;
    exportMutation.mutate({ reportId: selectedReportId, format });
    message.success('导出已开始');
  }, [selectedReportId, exportMutation]);

  const handleAdopt = useCallback(async (id: string) => {
    await adoptMutation.mutateAsync({ suggestionId: id, runId });
    message.success('已采纳');
  }, [adoptMutation, runId]);

  const handleRejectSuggestion = useCallback(async (id: string) => {
    await rejectMutation.mutateAsync({ suggestionId: id, runId });
    message.success('已驳回');
  }, [rejectMutation, runId]);

  const handleIgnoreSuggestion = useCallback(async (id: string) => {
    await ignoreMutation.mutateAsync({ suggestionId: id, runId });
    message.success('已忽略');
  }, [ignoreMutation, runId]);

  if (reportsError) return <Alert type="error" message="加载报告列表失败" showIcon />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>评估报告</Title>
        <Space>
          <Select placeholder="选择报告" value={selectedReportId} onChange={setSelectedReportId} loading={reportsLoading} style={{ minWidth: 240 }}
            showSearch filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
            options={reports.map((r) => ({ value: r.id, label: `${r.run_name} (${(r.overall_score * 100).toFixed(0)}%)` }))}
            notFoundContent={reportsLoading ? <Spin size="small" /> : <Empty description="暂无报告" />} allowClear />
          <Button icon={<FileMarkdownOutlined />} onClick={() => handleExport('pdf')} disabled={!selectedReportId}>Markdown</Button>
          <Button icon={<FileTextOutlined />} onClick={() => handleExport('json')} disabled={!selectedReportId}>JSON</Button>
          <Button icon={<FileExcelOutlined />} onClick={() => handleExport('csv')} disabled={!selectedReportId}>CSV</Button>
        </Space>
      </div>

      {!selectedReportId ? (
        <Empty description="请选择一个报告查看" style={{ padding: 60 }} />
      ) : reportLoading ? (
        <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" tip="加载报告中..." /></div>
      ) : !report ? (
        <Alert type="warning" message="未找到该报告" showIcon />
      ) : (
        <div>
          <ReportHeader report={report} />
          <Divider />
          {metrics ? <ScoringDashboard metrics={metrics} /> : <Card size="small" style={{ marginBottom: 16 }}><Alert type="info" message="暂无指标数据" /></Card>}
          <Divider />
          {diagnosis ? <DiagnosisPanel diagnosis={diagnosis} /> : <Card size="small" style={{ marginBottom: 16 }}><Alert type="info" message="暂无诊断数据" /></Card>}
          <Divider />
          <Row gutter={16}>
            <Col xs={24} lg={12}>
              <Title level={5}>Bad Cases</Title>
              <BadCaseTable cases={MOCK_BAD_CASES} />
            </Col>
            <Col xs={24} lg={12}>
              <Title level={5}>调优建议</Title>
              <SuggestionPanel suggestions={suggestionsData as Parameters<typeof SuggestionPanel>[0]['suggestions']}
                onAdopt={handleAdopt} onReject={handleRejectSuggestion} onIgnore={handleIgnoreSuggestion} />
            </Col>
          </Row>
        </div>
      )}
    </div>
  );
}
