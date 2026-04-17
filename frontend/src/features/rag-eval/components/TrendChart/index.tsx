/**
 * 趋势图表入口组件
 * 负责数据获取和状态管理，组合子组件展示趋势图
 */

import React, { useEffect, useState } from 'react';
import { Card, Select, Space, message } from 'antd';
import { getTrendData } from '@/api/rag-eval/trend';
import type { TrendDataPoint } from './types';
import ChartCanvas from './ChartCanvas';
import MetricLegend from './MetricLegend';
import type { TrendChartProps } from './types';

const METRIC_OPTIONS = [
  { label: 'F1 Score', value: 'f1' },
  { label: 'Precision', value: 'precision' },
  { label: 'Recall', value: 'recall' },
  { label: 'MRR', value: 'mrr' },
  { label: 'NDCG', value: 'ndcg' },
];

const DAYS_OPTIONS = [
  { label: '7 天', value: 7 },
  { label: '30 天', value: 30 },
  { label: '90 天', value: 90 },
  { label: '365 天', value: 365 },
];

const TrendChart: React.FC<TrendChartProps> = ({
  testSetId,
  metric = 'f1',
  days = 30,
  height = 400,
}) => {
  const [data, setData] = useState<TrendDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState(metric);
  const [selectedDays, setSelectedDays] = useState(days);
  const [activeMetrics, setActiveMetrics] = useState<string[]>(['f1', 'precision', 'recall']);

  useEffect(() => {
    fetchData();
  }, [testSetId, selectedMetric, selectedDays]);

  const fetchData = async () => {
    if (!testSetId) return;
    setLoading(true);
    try {
      const response = await getTrendData(testSetId, selectedMetric, selectedDays);
      setData(response.data);
    } catch {
      message.error('获取趋势数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleMetricToggle = (metric: string) => {
    setActiveMetrics((prev) =>
      prev.includes(metric) ? prev.filter((m) => m !== metric) : [...prev, metric]
    );
  };

  return (
    <Card title="趋势追踪" extra={
      <Space>
        <Select
          value={selectedMetric}
          onChange={setSelectedMetric}
          options={METRIC_OPTIONS}
          style={{ width: 120 }}
        />
        <Select
          value={selectedDays}
          onChange={setSelectedDays}
          options={DAYS_OPTIONS}
          style={{ width: 100 }}
        />
      </Space>
    }>
      <MetricLegend
        metrics={['f1', 'precision', 'recall', 'mrr', 'ndcg']}
        activeMetrics={activeMetrics}
        onToggle={handleMetricToggle}
      />
      <ChartCanvas
        data={data}
        metric={selectedMetric}
        loading={loading}
        height={height}
      />
    </Card>
  );
};

export default TrendChart;
