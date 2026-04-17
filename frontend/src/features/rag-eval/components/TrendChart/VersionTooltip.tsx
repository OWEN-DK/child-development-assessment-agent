/**
 * 版本悬浮提示框组件
 * 鼠标悬停时展示版本详情和指标数据
 */

import React from 'react';
import { Tag, Typography } from 'antd';
import dayjs from 'dayjs';
import type { TrendDataPoint } from './types';

const { Text } = Typography;

interface VersionTooltipProps {
  dataPoint: TrendDataPoint;
  metric: string;
}

const VersionTooltip: React.FC<VersionTooltipProps> = ({ dataPoint }) => {
  const { version_label, created_at, run_count, mean, min, max, config_changes } = dataPoint;

  return (
    <div style={{ padding: 8, background: '#fff', border: '1px solid #d9d9d9', borderRadius: 4 }}>
      <div style={{ marginBottom: 4 }}>
        <Text strong>{version_label}</Text>
      </div>
      {created_at && (
        <div style={{ marginBottom: 4, fontSize: 12, color: '#666' }}>
          {dayjs(created_at).format('YYYY-MM-DD HH:mm')}
        </div>
      )}
      <div style={{ marginBottom: 4 }}>
        <Text>运行次数: {run_count}</Text>
      </div>
      <div style={{ marginBottom: 4 }}>
        <Text>均值: {mean.toFixed(3)}</Text>
      </div>
      <div style={{ marginBottom: 4 }}>
        <Text>范围: {min.toFixed(3)} ~ {max.toFixed(3)}</Text>
      </div>
      {config_changes.length > 0 && (
        <div style={{ marginTop: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>变更:</Text>
          <div style={{ marginTop: 2 }}>
            {config_changes.slice(0, 2).map((cs) => (
              <Tag key={cs.change_set_id} color={cs.status === 'committed' ? 'blue' : 'red'} style={{ fontSize: 10 }}>
                {cs.change_set_label}
              </Tag>
            ))}
            {config_changes.length > 2 && (
              <Tag style={{ fontSize: 10 }}>+{config_changes.length - 2}</Tag>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default VersionTooltip;
