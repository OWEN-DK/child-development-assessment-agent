/**
 * 误差条组件
 * 用于在趋势图中展示指标的最小值和最大值范围
 */

import React from 'react';

interface ErrorBarProps {
  x: number;
  y: number;
  width: number;
  errorHeight: number;
  stroke?: string;
  strokeWidth?: number;
}

const ErrorBar: React.FC<ErrorBarProps> = ({
  x,
  y,
  width,
  errorHeight,
  stroke = '#999',
  strokeWidth = 1,
}) => {
  const topY = y - errorHeight / 2;
  const bottomY = y + errorHeight / 2;
  const capWidth = width / 2;

  return (
    <g>
      {/* 垂直线 */}
      <line
        x1={x}
        y1={topY}
        x2={x}
        y2={bottomY}
        stroke={stroke}
        strokeWidth={strokeWidth}
      />
      {/* 上横线 */}
      <line
        x1={x - capWidth}
        y1={topY}
        x2={x + capWidth}
        y2={topY}
        stroke={stroke}
        strokeWidth={strokeWidth}
      />
      {/* 下横线 */}
      <line
        x1={x - capWidth}
        y1={bottomY}
        x2={x + capWidth}
        y2={bottomY}
        stroke={stroke}
        strokeWidth={strokeWidth}
      />
    </g>
  );
};

export default ErrorBar;
