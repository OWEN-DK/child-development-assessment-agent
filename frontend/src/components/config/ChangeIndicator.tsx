import React from 'react';
import { Button, Space, Typography } from 'antd';
import { UndoOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface ChangeIndicatorProps {
  originalValue: any;
  newValue: any;
  onUndo: () => void;
}

export const ChangeIndicator: React.FC<ChangeIndicatorProps> = ({
  originalValue,
  newValue,
  onUndo
}) => {
  const formatValue = (val: any): string => {
    if (val === undefined || val === null) return '未设置';
    if (typeof val === 'object') return JSON.stringify(val, null, 2);
    return String(val);
  };

  return (
    <div style={{ marginTop: 8, padding: '8px 12px', background: '#fffbe6', borderRadius: 4, border: '1px solid #ffe58f' }}>
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <div>
          <Text delete type="secondary" style={{ fontSize: 12 }}>
            原值: {formatValue(originalValue)}
          </Text>
        </div>
        <div>
          <Text type="success" style={{ fontSize: 12 }}>
            新值: {formatValue(newValue)}
          </Text>
        </div>
        <Button
          size="small"
          icon={<UndoOutlined />}
          onClick={onUndo}
          style={{ alignSelf: 'flex-start' }}
        >
          撤销
        </Button>
      </Space>
    </div>
  );
};
