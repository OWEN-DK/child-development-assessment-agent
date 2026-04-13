import React from 'react';
import { Input, InputNumber, Switch, Select, Tooltip } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';
import { ConfigFieldSchema } from './schema';

interface ConfigFieldRendererProps {
  schema: ConfigFieldSchema;
  value?: any;
  onChange?: (value: any) => void;
  disabled?: boolean;
}

export const ConfigFieldRenderer: React.FC<ConfigFieldRendererProps> = ({
  schema,
  value,
  onChange,
  disabled,
}) => {
  const renderField = () => {
    switch (schema.type) {
      case 'boolean':
        return (
          <Switch
            checked={value}
            onChange={onChange}
            checkedChildren="开启"
            unCheckedChildren="关闭"
            disabled={disabled || schema.disabled}
          />
        );
      
      case 'number':
        return (
          <InputNumber
            value={value}
            onChange={onChange}
            min={schema.min}
            max={schema.max}
            step={schema.step || 1}
            disabled={disabled || schema.disabled}
            style={{ width: '100%' }}
          />
        );
      
      case 'string':
        return (
          <Input
            value={value}
            onChange={(e) => onChange?.(e.target.value)}
            placeholder={schema.default?.toString()}
            disabled={disabled || schema.disabled}
            type={schema.key.includes('password') ? 'password' : 'text'}
          />
        );
      
      case 'enum':
        return (
          <Select
            value={value}
            onChange={onChange}
            options={schema.options}
            disabled={disabled || schema.disabled}
            style={{ width: '100%' }}
          />
        );
      
      default:
        return null;
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      {renderField()}
      {schema.description && (
        <Tooltip title={schema.description}>
          <QuestionCircleOutlined style={{ color: '#999' }} />
        </Tooltip>
      )}
    </div>
  );
};