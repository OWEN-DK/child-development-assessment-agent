import { Space, Typography, Descriptions } from 'antd';
import type { EvalReport } from '@entities/rag-eval';
import { StatusBadge } from '../common/StatusBadge';
import { formatDuration, formatTimestamp } from '@entities/rag-eval';

const { Title } = Typography;

interface ReportHeaderProps {
  report: EvalReport;
}

export function ReportHeader({ report }: ReportHeaderProps) {
  return (
    <div>
      <Space align="center" style={{ marginBottom: 8 }}>
        <Title level={3} style={{ margin: 0 }}>{report.run_name}</Title>
        <StatusBadge status={report.status} />
      </Space>
      <Descriptions size="small" column={4}>
        <Descriptions.Item label="综合得分">
          <Typography.Text strong style={{ fontSize: 18, color: report.overall_score >= 0.7 ? '#52c41a' : report.overall_score >= 0.5 ? '#faad14' : '#ff4d4f' }}>
            {(report.overall_score * 100).toFixed(1)}%
          </Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label="通过/总数">{report.passed_test_cases} / {report.total_test_cases}</Descriptions.Item>
        <Descriptions.Item label="耗时">{formatDuration(report.duration_seconds)}</Descriptions.Item>
        <Descriptions.Item label="生成时间">{formatTimestamp(report.created_at)}</Descriptions.Item>
      </Descriptions>
    </div>
  );
}
