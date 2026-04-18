import React from 'react';
import { Card, Tag } from 'antd';
import { ConfigField } from './ConfigField';
import { ChangeIndicator } from './ChangeIndicator';

interface ConfigCardProps {
  field: {
    key: string;
    label: string;
    type: string;
    min?: number;
    max?: number;
    options?: { label: string; value: any }[];
    sensitive?: boolean;
    description?: string;
  };
  value: any;
  originalValue: any;
  isModified: boolean;
  onChange: (value: any) => void;
  onUndo: () => void;
}

export const ConfigCard: React.FC<ConfigCardProps> = ({
  field,
  value,
  originalValue,
  isModified,
  onChange,
  onUndo
}) => {
  return (
    <Card
      size="small"
      style={{
        marginBottom: 12,
        border: isModified ? '2px solid #faad14' : undefined,
        backgroundColor: isModified ? '#fffbe6' : undefined
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div>
          <strong>{field.label}</strong>
          {field.description && (
            <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
              {field.description}
            </div>
          )}
        </div>
        {isModified && <Tag color="orange">已修改</Tag>}
      </div>

      <ConfigField
        field={field}
        value={value}
        onChange={onChange}
      />

      {isModified && (
        <ChangeIndicator
          originalValue={originalValue}
          newValue={value}
          onUndo={onUndo}
        />
      )}
    </Card>
  );
};
