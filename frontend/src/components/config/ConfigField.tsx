import React from 'react';
import { Input, InputNumber, Switch, Select } from 'antd';
import { PROVIDER_OPTIONS } from './constants';

interface ConfigFieldProps {
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
  onChange: (value: any) => void;
}

export const ConfigField: React.FC<ConfigFieldProps> = ({
  field,
  value,
  onChange
}) => {
  switch (field.type) {
    case 'bool':
      return (
        <Switch
          checked={!!value}
          onChange={(checked) => onChange(checked)}
        />
      );

    case 'int':
      return (
        <InputNumber
          value={value}
          onChange={(val) => onChange(val)}
          min={field.min}
          max={field.max}
          style={{ width: '100%' }}
        />
      );

    case 'float':
      return (
        <InputNumber
          value={value}
          onChange={(val) => onChange(val)}
          min={field.min}
          max={field.max}
          step={0.1}
          style={{ width: '100%' }}
        />
      );

    case 'str':
      // 提供商字段使用下拉框
      if (field.key.includes('provider') && field.options) {
        return (
          <Select
            value={value}
            onChange={onChange}
            options={field.options}
            style={{ width: '100%' }}
          />
        );
      }
      
      // 敏感字段使用密码输入框
      if (field.sensitive || field.key.includes('key') || field.key.includes('secret')) {
        return (
          <Input.Password
            value={value}
            onChange={(e) => onChange(e.target.value)}
            visibilityToggle
          />
        );
      }
      
      return (
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    case 'select':
      return (
        <Select
          value={value}
          onChange={onChange}
          options={field.options || PROVIDER_OPTIONS}
          style={{ width: '100%' }}
        />
      );

    default:
      return (
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
};
