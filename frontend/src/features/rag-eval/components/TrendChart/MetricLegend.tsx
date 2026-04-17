/**
 * 指标图例组件
 * 可点击切换指标显示/隐藏
 */

import React from 'react';
import { Space, Tag } from 'antd';

const METRIC_COLORS: Record<string, string> = {
  f1: '#1890ff',
  precision: '#52c41a',
  recall: '#faad14',
  mrr: '#722ed1',
  ndcg: '#13c2c2',
};

interface MetricLegendProps {
  metrics: string[];
  activeMetrics: string[];
  onToggle: (metric: string) => void;
}

const MetricLegend: React.FC<MetricLegendProps> = ({ metrics, activeMetrics, onToggle }) => {
  return (
    <Space size="middle" style={{ marginBottom: 16 }}>
      {metrics.map((metric) => (
        <Tag
          key={metric}
          color={METRIC_COLORS[metric] || '#999'}
          style={{
            cursor: 'pointer',
            opacity: activeMetrics.includes(metric) ? 1 : 0.4,
            textTransform: 'uppercase',
          }}
          onClick={() => onToggle(metric)}
        >
          {metric}
        </Tag>
      ))}
    </Space>
  );
};

export default MetricLegend;
