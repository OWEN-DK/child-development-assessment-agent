import React from 'react';
import { Card, Row, Col, Statistic, Select, Space, Tabs } from 'antd';
import { Line, Pie } from '@ant-design/charts';
import { useQuery } from '@tanstack/react-query';
import { monitoringApi } from '@/api/monitoring';
import {
  TraceFilterBar,
  TraceListView,
  TraceDetailDrawer,
  LatencyChart,
  CostAnalysisDashboard,
} from '@/components/monitoring';

const { Option } = Select;

export const LLMMonitoringDashboard: React.FC = () => {
  const [days, setDays] = React.useState(7);
  const [modelFilter, setModelFilter] = React.useState<string | undefined>();
  const [traceFilters, setTraceFilters] = React.useState<Record<string, any>>({});
  const [selectedTraceId, setSelectedTraceId] = React.useState<string | null>(null);

  // 查询统计数据
  const { data: statistics, isLoading: statsLoading } = useQuery({
    queryKey: ['monitoringStats', days, modelFilter],
    queryFn: () => monitoringApi.getStatistics(days, modelFilter),
  });

  // 查询趋势
  const { data: trend } = useQuery({
    queryKey: ['monitoringTrend', days],
    queryFn: () => monitoringApi.getTrend(days, 'calls'),
  });

  // 查询模型分布
  const { data: modelDistribution } = useQuery({
    queryKey: ['modelDistribution', days],
    queryFn: () => monitoringApi.getModelDistribution(days),
  });

  const lineConfig = {
    data: trend?.trend || [],
    xField: 'hour',
    yField: 'value',
    point: { size: 5, shape: 'circle' },
    label: {
      style: { fill: '#aaa' },
    },
  };

  const rawDistribution = modelDistribution?.distribution || [];
  const totalCount = rawDistribution.reduce((sum: number, d: any) => sum + (d.count || 0), 0);
  const pieData = rawDistribution.map((d: any) => ({
    ...d,
    percentage: totalCount > 0 ? `${((d.count / totalCount) * 100).toFixed(1)}%` : '0%',
  }));

  const pieConfig = {
    data: pieData,
    angleField: 'count',
    colorField: 'model_name',
    radius: 0.8,
    label: {
      text: (d: any) => `${d.model_name} ${d.percentage}`,
      position: 'spider' as const,
      transform: [{ type: 'overlapDodgeY' }],
    },
    legend: {
      color: {
        position: 'right' as const,
      },
    },
  };

  const dashboardContent = (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>LLM 监控仪表板</h1>
        <Space>
          <Select
            value={days}
            onChange={setDays}
            style={{ width: 120 }}
          >
            <Option value={7}>最近7天</Option>
            <Option value={30}>最近30天</Option>
            <Option value={90}>最近90天</Option>
          </Select>
          <Select
            placeholder="选择模型"
            value={modelFilter}
            onChange={setModelFilter}
            style={{ width: 200 }}
            allowClear
          >
            <Option value="qwen-plus">通义千问 Plus</Option>
            <Option value="qwen-vl">通义千问 VL</Option>
            <Option value="bge-reranker-v2-m3">BGE 重排序</Option>
            <Option value="text-embedding-v4">嵌入模型 v4</Option>
          </Select>
        </Space>
      </div>
      
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card loading={statsLoading}>
            <Statistic
              title="总调用次数"
              value={statistics?.total_calls || 0}
              suffix="次"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={statsLoading}>
            <Statistic
              title="成功率"
              value={(1 - (statistics?.error_rate || 0)) * 100}
              precision={2}
              suffix="%"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={statsLoading}>
            <Statistic
              title="总 Token 消耗"
              value={statistics?.total_tokens || 0}
              suffix="个"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={statsLoading}>
            <Statistic
              title="平均耗时"
              value={statistics?.avg_duration_ms || 0}
              precision={0}
              suffix="ms"
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={16}>
          <Card title="调用趋势">
            <Line {...lineConfig} />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="模型使用分布">
            <Pie {...pieConfig} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <LatencyChart />
        </Col>
        <Col span={12}>
          <CostAnalysisDashboard />
        </Col>
      </Row>
    </div>
  );

  const tracesContent = (
    <div style={{ padding: 24 }}>
      <h1 style={{ marginBottom: 16 }}>调用追踪</h1>
      <TraceFilterBar onFilter={setTraceFilters} />
      <TraceListView
        filters={traceFilters}
        onRowClick={setSelectedTraceId}
      />
      <TraceDetailDrawer
        traceId={selectedTraceId}
        onClose={() => setSelectedTraceId(null)}
      />
    </div>
  );

  const items = [
    {
      key: 'dashboard',
      label: '监控仪表板',
      children: dashboardContent,
    },
    {
      key: 'traces',
      label: '调用追踪 (Traces)',
      children: tracesContent,
    },
  ];

  return <Tabs items={items} />;
};