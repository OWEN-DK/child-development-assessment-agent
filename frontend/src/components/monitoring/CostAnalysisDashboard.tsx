import React from 'react';
import { Card, Statistic, Row, Col, Table } from 'antd';
import { Pie } from '@ant-design/charts';
import { useQuery } from '@tanstack/react-query';
import { tracingApi } from '@/api/tracing';

interface CostAnalysisDashboardProps {
  startTime?: string;
  endTime?: string;
}

export const CostAnalysisDashboard: React.FC<CostAnalysisDashboardProps> = ({
  startTime,
  endTime,
}) => {
  const { data, isLoading } = useQuery({
    queryKey: ['costAnalysis', startTime, endTime],
    queryFn: () => tracingApi.getCostAnalysis(startTime, endTime),
  });

  const pieConfig = {
    data: data?.model_stats.map((s: { model: string; cost: number }) => ({
      type: s.model,
      value: s.cost,
    })) || [],
    angleField: 'value',
    colorField: 'type',
    radius: 0.8,
    label: {
      position: 'outside',
      content: (datum: any) => `${datum.type} ¥${datum.value.toFixed(4)}`,
    },
    interactions: [{ type: 'element-active' }],
  };

  const columns = [
    {
      title: '模型',
      dataIndex: 'model',
      key: 'model',
    },
    {
      title: '调用次数',
      dataIndex: 'calls',
      key: 'calls',
      sorter: (a: any, b: any) => a.calls - b.calls,
    },
    {
      title: 'Token 消耗',
      dataIndex: 'tokens',
      key: 'tokens',
      sorter: (a: any, b: any) => a.tokens - b.tokens,
    },
    {
      title: '成本 (¥)',
      dataIndex: 'cost',
      key: 'cost',
      render: (cost: number) => `¥${cost.toFixed(4)}`,
      sorter: (a: any, b: any) => a.cost - b.cost,
    },
  ];

  return (
    <Card title="成本分析" loading={isLoading}>
      {data && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Statistic
                title="总成本"
                value={`¥${data.total_cost}`}
                precision={4}
              />
            </Col>
            <Col span={6}>
              <Statistic title="总调用次数" value={data.total_calls} />
            </Col>
            <Col span={6}>
              <Statistic title="总 Token" value={data.total_tokens} />
            </Col>
            <Col span={6}>
              <Statistic
                title="平均成本/次"
                value={`¥${data.avg_cost_per_call}`}
                precision={4}
              />
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="模型成本分布" size="small">
                <Pie {...pieConfig} />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="模型详情" size="small">
                <Table
                  dataSource={data.model_stats}
                  columns={columns}
                  rowKey="model"
                  pagination={false}
                  size="small"
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </Card>
  );
};
