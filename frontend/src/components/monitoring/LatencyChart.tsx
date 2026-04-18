import React from 'react';
import { Card, Statistic, Row, Col } from 'antd';
import { Column } from '@ant-design/charts';
import { useQuery } from '@tanstack/react-query';
import { tracingApi } from '@/api/tracing';

interface LatencyChartProps {
  startTime?: string;
  endTime?: string;
}

export const LatencyChart: React.FC<LatencyChartProps> = ({ startTime, endTime }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['latencyDistribution', startTime, endTime],
    queryFn: () => tracingApi.getLatencyDistribution(startTime, endTime),
  });

  const chartData = data
    ? [
        { metric: 'P50', value: data.p50 },
        { metric: 'P95', value: data.p95 },
        { metric: 'P99', value: data.p99 },
        { metric: '平均', value: Math.round(data.avg) },
        { metric: '最小', value: data.min },
        { metric: '最大', value: data.max },
      ]
    : [];

  const config = {
    data: chartData,
    xField: 'metric',
    yField: 'value',
    label: {
      position: 'top' as const,
      content: (datum: any) => `${datum.value}ms`,
    },
    yAxis: {
      title: { text: '延迟 (ms)' },
    },
    xAxis: {
      title: { text: '指标' },
    },
    color: (datum: any) => {
      const colors: Record<string, string> = {
        P50: '#5B8FF9',
        P95: '#F6BD16',
        P99: '#E86452',
        平均: '#6DC8EC',
        最小: '#5AD8A6',
        最大: '#FF9845',
      };
      return colors[datum.metric] || '#5B8FF9';
    },
  };

  return (
    <Card title="延迟分布" loading={isLoading}>
      {data && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={8}>
              <Statistic title="P50 延迟" value={data.p50} suffix="ms" />
            </Col>
            <Col span={8}>
              <Statistic title="P95 延迟" value={data.p95} suffix="ms" />
            </Col>
            <Col span={8}>
              <Statistic title="P99 延迟" value={data.p99} suffix="ms" />
            </Col>
          </Row>
          <Column {...config} />
        </>
      )}
    </Card>
  );
};
