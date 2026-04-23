/**
 * 影响分析预览组件
 * 展示配置/提示词变更影响的测试集范围、预期指标提升、风险提示
 */

import { Card, Alert, Table, Tag, Statistic, Row, Col, Spin, Empty } from 'antd';
import { WarningOutlined, CheckCircleOutlined, InfoCircleOutlined } from '@ant-design/icons';

export interface ImpactPreviewData {
  /** 受影响的测试集 */
  affected_test_sets: {
    id: string;
    name: string;
    case_count: number;
  }[];
  /** 预期指标变化 */
  expected_metrics_change: {
    metric: string;
    current_value: number;
    expected_value: number;
    delta: number;
  }[];
  /** 风险提示 */
  risks: {
    level: 'high' | 'medium' | 'low';
    description: string;
    scope: string;
  }[];
  /** 历史相似变更 */
  historical_similar_changes: {
    date: string;
    change_summary: string;
    actual_impact: string;
  }[];
}

interface ImpactPreviewProps {
  data?: ImpactPreviewData | null;
  loading?: boolean;
}

const RISK_CONFIG = {
  high: { color: 'red', icon: <WarningOutlined />, label: '高风险' },
  medium: { color: 'orange', icon: <WarningOutlined />, label: '中风险' },
  low: { color: 'blue', icon: <InfoCircleOutlined />, label: '低风险' },
};

export default function ImpactPreview({ data, loading = false }: ImpactPreviewProps) {
  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />;
  }

  if (!data) {
    return <Empty description="暂无影响分析数据" />;
  }

  const riskColumns = [
    {
      title: '风险等级',
      dataIndex: 'level',
      key: 'level',
      width: 100,
      render: (level: string) => (
        <Tag color={RISK_CONFIG[level as keyof typeof RISK_CONFIG].color}>
          {RISK_CONFIG[level as keyof typeof RISK_CONFIG].icon}
          {RISK_CONFIG[level as keyof typeof RISK_CONFIG].label}
        </Tag>
      ),
    },
    { title: '风险描述', dataIndex: 'description', key: 'description' },
    { title: '影响范围', dataIndex: 'scope', key: 'scope', width: 150 },
  ];

  const metricColumns = [
    { title: '指标', dataIndex: 'metric', key: 'metric', width: 120 },
    {
      title: '当前值',
      dataIndex: 'current_value',
      key: 'current_value',
      width: 100,
      render: (v: number) => v.toFixed(3),
    },
    {
      title: '预期值',
      dataIndex: 'expected_value',
      key: 'expected_value',
      width: 100,
      render: (v: number) => v.toFixed(3),
    },
    {
      title: '变化',
      dataIndex: 'delta',
      key: 'delta',
      width: 100,
      render: (v: number) => (
        <span style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f', fontWeight: 'bold' }}>
          {v >= 0 ? '+' : ''}{(v * 100).toFixed(1)}%
        </span>
      ),
    },
  ];

  const historyColumns = [
    { title: '时间', dataIndex: 'date', key: 'date', width: 120 },
    { title: '变更摘要', dataIndex: 'change_summary', key: 'change_summary' },
    { title: '实际影响', dataIndex: 'actual_impact', key: 'actual_impact' },
  ];

  return (
    <div>
      <Card title="影响分析预览" style={{ marginBottom: 16 }}>
        {/* 风险提示 */}
        {data.risks.length > 0 && (
          <Alert
            message={`${data.risks.length} 个风险提示`}
            description={
              <Table
                columns={riskColumns}
                dataSource={data.risks}
                rowKey="description"
                pagination={false}
                size="small"
              />
            }
            type="warning"
            style={{ marginBottom: 16 }}
          />
        )}

        {/* 预期指标变化 */}
        {data.expected_metrics_change.length > 0 && (
          <Card title="预期指标变化" size="small" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              {data.expected_metrics_change.map((m) => (
                <Col span={8} key={m.metric}>
                  <Statistic
                    title={m.metric}
                    value={m.expected_value}
                    precision={3}
                    valueStyle={{ color: m.delta >= 0 ? '#52c41a' : '#ff4d4f' }}
                    prefix={m.delta >= 0 ? <CheckCircleOutlined /> : <WarningOutlined />}
                    suffix={
                      <span style={{ fontSize: 12, color: '#999' }}>
                        ({m.delta >= 0 ? '+' : ''}{(m.delta * 100).toFixed(1)}%)
                      </span>
                    }
                  />
                </Col>
              ))}
            </Row>
            <Table
              columns={metricColumns}
              dataSource={data.expected_metrics_change}
              rowKey="metric"
              pagination={false}
              size="small"
              style={{ marginTop: 16 }}
            />
          </Card>
        )}

        {/* 受影响测试集 */}
        {data.affected_test_sets.length > 0 && (
          <Card title={`受影响的测试集 (${data.affected_test_sets.length})`} size="small" style={{ marginBottom: 16 }}>
            {data.affected_test_sets.map((ts) => (
              <Tag key={ts.id} style={{ marginBottom: 8, padding: '4px 12px' }}>
                {ts.name} ({ts.case_count} 用例)
              </Tag>
            ))}
          </Card>
        )}

        {/* 历史相似变更 */}
        {data.historical_similar_changes.length > 0 && (
          <Card title="历史相似变更" size="small">
            <Table
              columns={historyColumns}
              dataSource={data.historical_similar_changes}
              rowKey="date"
              pagination={false}
              size="small"
            />
          </Card>
        )}
      </Card>
    </div>
  );
}
