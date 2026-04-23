/**
 * 评估报告页
 * 路由: /rag-eval/reports/:id (id 为 run_id)
 */

import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Button,
  Space,
  Typography,
  Tabs,
  Empty,
  Spin,
} from 'antd';
import { notification } from '@shared/lib/notification';
import {
  ArrowLeftOutlined,
  FilePdfOutlined,
  FileExcelOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { getTestRun, getTestSet } from '@/api/rag-test';
import type { TestRun } from '@/api/rag-test';
import ValidationResult from '@/features/rag-eval/components/ValidationResult';
import RecommendationPanel from '@/features/rag-eval/components/RecommendationPanel';
import TrendChart from '@/features/rag-eval/components/TrendChart';
import RollbackConfirmDialog from '@/features/rag-eval/components/RollbackConfirmDialog';
import { exportCasesToCSV, exportReportToJSON } from '@/features/rag-eval/utils/export';
import { createExportTask, downloadExport } from '@/api/rag-eval/export';
import { rollbackToVersion } from '@/api/rag-eval/config';
import { useSSE } from '@shared/hooks/useSSE';

const { Title } = Typography;

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<TestRun | null>(null);
  const [testSetName, setTestSetName] = useState('');
  const [loading, setLoading] = useState(true);

  // 导出相关状态
  const [exporting, setExporting] = useState(false);

  // 导出 SSE
  const { connect: connectExportSse, disconnect: disconnectExportSse } = useSSE({
    url: '/api/sse/exports?user_id=anonymous',
    enabled: false,
    onMessage: async (eventType, event: any) => {
      if (eventType === 'export_ready') {
        try {
          await downloadExport(event.export_id);
          notification.success('PDF 下载已开始');
        } catch (err) {
          notification.error('下载导出文件失败');
        } finally {
          setExporting(false);
          disconnectExportSse();
        }
      } else if (eventType === 'export_failed') {
        notification.error(`PDF 导出失败: ${event.error || '未知错误'}`);
        setExporting(false);
        disconnectExportSse();
      }
    }
  });

  // 回滚相关状态
  const [rollbackVisible, setRollbackVisible] = useState(false);
  const [rollbackLoading, setRollbackLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    loadData();
  }, [id]);

  const loadData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const runData = await getTestRun(id);
      setRun(runData);
      if (runData.test_set_id) {
        try {
          const testSet = await getTestSet(runData.test_set_id);
          setTestSetName(testSet.name);
        } catch {
          // 忽略测试集获取失败
        }
      }
    } catch {
      notification.error('加载报告失败');
    } finally {
      setLoading(false);
    }
  };

  // 导出 PDF（异步）
  const handleExportPDF = async () => {
    if (!id) return;
    setExporting(true);
    try {
      connectExportSse();
      await createExportTask(id);
      notification.success('PDF 导出任务已提交，请稍后查看下载状态');
    } catch {
      notification.error('创建 PDF 导出任务失败');
      setExporting(false);
      disconnectExportSse();
    }
  };

  // 导出 CSV
  const handleExportCSV = async () => {
    if (!id) return;
    try {
      await exportCasesToCSV(id, `rag_eval_results_${id.slice(0, 8)}`);
    } catch {
      notification.error('导出 CSV 失败');
    }
  };

  // 导出 JSON
  const handleExportJSON = async () => {
    if (!id) return;
    try {
      await exportReportToJSON(id, `rag_eval_report_${id.slice(0, 8)}`);
    } catch {
      notification.error('导出 JSON 失败');
    }
  };

  // 回滚操作
  const handleRollback = async (reason: string) => {
    if (!run?.config_version_id) return;
    setRollbackLoading(true);
    try {
      await rollbackToVersion(run.config_version_id, reason);
      notification.success('配置回滚成功');
      setRollbackVisible(false);
    } catch {
      notification.error('配置回滚失败');
    } finally {
      setRollbackLoading(false);
    }
  };

  // 从运行数据提取指标
  const metrics = run ? {
    precision_at_1: run.overall_precision || 0,
    recall_at_5: run.overall_recall || 0,
    mrr: run.overall_mrr || 0,
    ndcg_at_5: run.overall_ndcg || 0,
    hit_rate_at_5: run.total_test_cases ? ((run.passed_test_cases || 0) / run.total_test_cases) : 0,
    total_cases: run.total_test_cases || 0,
    passed_cases: run.passed_test_cases || 0,
  } : null;

  const tabItems = [
    {
      key: 'metrics',
      label: '指标总览',
      children: metrics ? (
        <Row gutter={16}>
          <Col span={16}>
            <Card title="核心指标">
              <Row gutter={[16, 16]}>
                <Col span={8}><Statistic title="P@1" value={metrics.precision_at_1} precision={2} /></Col>
                <Col span={8}><Statistic title="R@5" value={metrics.recall_at_5} precision={2} /></Col>
                <Col span={8}><Statistic title="MRR" value={metrics.mrr} precision={2} /></Col>
                <Col span={8}><Statistic title="NDCG@5" value={metrics.ndcg_at_5} precision={2} /></Col>
                <Col span={8}><Statistic title="通过率" value={metrics.hit_rate_at_5 * 100} precision={1} suffix="%" /></Col>
                <Col span={8}><Statistic title="用例" value={`${metrics.passed_cases}/${metrics.total_cases}`} /></Col>
              </Row>
            </Card>
          </Col>
          <Col span={8}>
            <Card title="运行信息">
              <p>测试集：{testSetName || '-'}</p>
              <p>状态：{run?.status}</p>
              <p>完成时间：{run?.completed_at ? dayjs(run.completed_at).format('YYYY-MM-DD HH:mm') : '-'}</p>
            </Card>
          </Col>
        </Row>
      ) : <Empty description="运行未完成，暂无指标" />,
    },
    {
      key: 'validation',
      label: '6层校验',
      children: <ValidationResult runId={id!} />,
    },
    {
      key: 'suggestions',
      label: '调优建议',
      children: run?.test_set_id ? (
        <RecommendationPanel reportId={id!} testSetId={run.test_set_id} />
      ) : (
        <Empty description="无法获取测试集信息" />
      ),
    },
    {
      key: 'trend',
      label: '趋势追踪',
      children: run?.test_set_id ? (
        <TrendChart testSetId={run.test_set_id} />
      ) : (
        <Empty description="需要多次运行后展示趋势" />
      ),
    },
    {
      key: 'badcases',
      label: 'Bad Case',
      children: run?.test_results ? (
        <Table
          columns={[
            { title: '查询', dataIndex: 'query', key: 'query', ellipsis: true },
            { title: 'F1', key: 'f1', width: 80, render: (_: unknown, r: { f1_score?: number }) => (r.f1_score || 0).toFixed(2) },
            { title: '耗时', key: 'time', width: 80, render: (_: unknown, r: { execution_time_ms?: number }) => `${r.execution_time_ms || 0}ms` },
          ]}
          dataSource={run.test_results.filter(r => (r.f1_score || 0) < 0.7) as unknown as Record<string, unknown>[]}
          rowKey="test_case_id"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: '暂无 Bad Case' }}
        />
      ) : <Empty description="暂无数据" />,
    },
  ];

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!run) return <div>报告不存在</div>;

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Link to="/rag-eval?tab=runs">
          <Button type="link" icon={<ArrowLeftOutlined />}>返回</Button>
        </Link>
        <Space>
          <Button
            icon={<FilePdfOutlined />}
            onClick={handleExportPDF}
            loading={exporting}
          >
            导出 PDF
          </Button>
          <Button icon={<FileExcelOutlined />} onClick={handleExportCSV}>
            导出 CSV
          </Button>
          <Button icon={<CodeOutlined />} onClick={handleExportJSON}>
            导出 JSON
          </Button>
          {run.config_version_id && (
            <Button danger onClick={() => setRollbackVisible(true)}>
              回滚配置
            </Button>
          )}
        </Space>
      </div>

      <Title level={4}>评估报告 - {run.name}</Title>

      {/* 调优建议 Tab 使用 LayoutAdapter，需要给主内容区留出右侧空间 */}
      <div style={{ marginRight: 380 }}>
        <Tabs items={tabItems} />
      </div>

      {/* 回滚确认对话框 */}
      <RollbackConfirmDialog
        visible={rollbackVisible}
        targetVersion={run.config_version_id ? {
          id: run.config_version_id,
          version_label: '当前版本',
          version_number: 0,
          created_at: null,
        } : null}
        onConfirm={handleRollback}
        onCancel={() => setRollbackVisible(false)}
        loading={rollbackLoading}
      />
    </div>
  );
}
