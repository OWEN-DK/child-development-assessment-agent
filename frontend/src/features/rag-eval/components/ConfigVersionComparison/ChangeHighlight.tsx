/**
 * 变更高亮组件
 * 对比新旧值，高亮显示差异部分
 */

import React from 'react';
import { Tag, Typography } from 'antd';

const { Text } = Typography;

interface ChangeHighlightProps {
  keyName: string;
  oldValue: unknown;
  newValue: unknown;
}

const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};

const ChangeHighlight: React.FC<ChangeHighlightProps> = ({ keyName, oldValue, newValue }) => {
  return (
    <div style={{ marginBottom: 8, padding: 8, background: '#fafafa', borderRadius: 4 }}>
      <div style={{ marginBottom: 4 }}>
        <Tag color="blue">{keyName}</Tag>
      </div>
      <div style={{ display: 'flex', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>旧值:</Text>
          <pre style={{ margin: '4px 0 0', fontSize: 12, color: '#ff4d4f', background: '#fff2f0', padding: 4, borderRadius: 2 }}>
            {formatValue(oldValue)}
          </pre>
        </div>
        <div style={{ flex: 1 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>新值:</Text>
          <pre style={{ margin: '4px 0 0', fontSize: 12, color: '#52c41a', background: '#f6ffed', padding: 4, borderRadius: 2 }}>
            {formatValue(newValue)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default ChangeHighlight;
