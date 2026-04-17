/**
 * 趋势图表画布组件
 * 基于 SVG 实现，支持误差条和悬浮提示
 */

import React from 'react';
import { Empty, Spin } from 'antd';
import type { TrendDataPoint } from './types';

const METRIC_COLORS: Record<string, string> = {
  f1: '#1890ff',
  precision: '#52c41a',
  recall: '#faad14',
  mrr: '#722ed1',
  ndcg: '#13c2c2',
};

interface ChartCanvasProps {
  data: TrendDataPoint[];
  metric: string;
  loading: boolean;
  height?: number;
}

const ChartCanvas: React.FC<ChartCanvasProps> = ({ data, metric, loading, height = 400 }) => {
  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />;
  }

  if (!data || data.length === 0) {
    return <Empty description="暂无趋势数据" />;
  }

  // 计算图表尺寸
  const width = 800;
  const padding = { top: 20, right: 30, left: 50, bottom: 40 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // 计算数据范围
  const values = data.map(d => d.mean);
  const minVal = Math.min(...values, 0);
  const maxVal = Math.max(...values, 1);
  const range = maxVal - minVal || 1;

  // 坐标映射函数
  const xScale = (index: number) => padding.left + (index / Math.max(data.length - 1, 1)) * chartWidth;
  const yScale = (value: number) => padding.top + chartHeight - ((value - minVal) / range) * chartHeight;

  // 生成路径
  const pathData = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(d.mean)}`).join(' ');

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <svg width={width} height={height} style={{ display: 'block', margin: '0 auto' }}>
        {/* 网格线 */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = padding.top + chartHeight * (1 - ratio);
          return (
            <g key={ratio}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#eee" />
              <text x={padding.left - 5} y={y + 4} textAnchor="end" fontSize={10} fill="#999">
                {(minVal + range * ratio).toFixed(2)}
              </text>
            </g>
          );
        })}

        {/* 误差条（min-max 范围） */}
        {data.map((d, i) => {
          const x = xScale(i);
          const yMin = yScale(d.min);
          const yMax = yScale(d.max);
          return (
            <g key={`error-${i}`}>
              <line x1={x} y1={yMin} x2={x} y2={yMax} stroke={METRIC_COLORS[metric] || '#1890ff'} strokeWidth={1} strokeOpacity={0.5} />
              <line x1={x - 5} y1={yMin} x2={x + 5} y2={yMin} stroke={METRIC_COLORS[metric] || '#1890ff'} strokeWidth={1} strokeOpacity={0.5} />
              <line x1={x - 5} y1={yMax} x2={x + 5} y2={yMax} stroke={METRIC_COLORS[metric] || '#1890ff'} strokeWidth={1} strokeOpacity={0.5} />
            </g>
          );
        })}

        {/* 趋势线 */}
        <path d={pathData} fill="none" stroke={METRIC_COLORS[metric] || '#1890ff'} strokeWidth={2} />

        {/* 数据点 */}
        {data.map((d, i) => (
          <g key={`point-${i}`}>
            <circle cx={xScale(i)} cy={yScale(d.mean)} r={4} fill={METRIC_COLORS[metric] || '#1890ff'} />
            <text x={xScale(i)} y={yScale(d.mean) - 10} textAnchor="middle" fontSize={10} fill="#666">
              {d.version_label}
            </text>
          </g>
        ))}

        {/* X 轴标签 */}
        <text x={width / 2} y={height - 5} textAnchor="middle" fontSize={12} fill="#666">
          配置版本
        </text>

        {/* Y 轴标签 */}
        <text x={15} y={height / 2} textAnchor="middle" fontSize={12} fill="#666" transform={`rotate(-90, 15, ${height / 2})`}>
          {metric.toUpperCase()}
        </text>
      </svg>
    </div>
  );
};

export default ChartCanvas;
