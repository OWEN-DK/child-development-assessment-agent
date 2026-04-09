import React from 'react';
import { ConfigFieldMetadata } from '../../api/config/types';
import { useConfigStore } from '../../store/configStore';
import { Switch, InputNumber, Input, Tooltip, message, Button, Space } from 'antd';
import { QuestionCircleOutlined, WarningOutlined, PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import styles from './DynamicConfigForm.module.scss';

interface DynamicConfigFormProps {
  fields: ConfigFieldMetadata[];
  category?: string;
}

export const DynamicConfigForm: React.FC<DynamicConfigFormProps> = ({
  fields,
  category,
}) => {
  const { draftChanges, updateDraft } = useConfigStore();

  const filteredFields = category
    ? fields.filter((f) => f.category === category)
    : fields;

  const renderField = (field: ConfigFieldMetadata) => {
    const currentValue =
      draftChanges[field.key] ?? field.current_value;

    return (
      <div key={field.key} className={styles.configItem}>
        <div className={styles.configHeader}>
          <span className={styles.configLabel}>{field.key}</span>
          <Tooltip title={field.description || '暂无描述'}>
            <QuestionCircleOutlined className={styles.helpIcon} />
          </Tooltip>
          {field.requires_restart && (
            <Tooltip title="修改后需重启服务">
              <WarningOutlined className={styles.warningIcon} />
            </Tooltip>
          )}
        </div>

        <div className={styles.configControl}>
          {renderControl(field, currentValue, updateDraft)}
        </div>

        <div className={styles.configMeta}>
          <span>默认值: {String(field.default_value)}</span>
          {!field.hot_reloadable && (
            <span className={styles.coldUpdate}>冷更新</span>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className={styles.configForm}>
      {filteredFields.map(renderField)}
    </div>
  );
};

function renderControl(
  field: ConfigFieldMetadata,
  value: any,
  onChange: (key: string, value: any) => void
) {
  // Handle dictionary/object types
  if (field.type === 'dict' || field.type === 'Dict') {
    const dictValue = typeof value === 'object' && value !== null && !Array.isArray(value) ? value : {};
    
    // Check if all values are primitive types (string, number, boolean)
    const isSimpleDict = Object.values(dictValue).every(val => 
      typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean'
    );
    
    if (isSimpleDict) {
      return (
        <div className={styles.dictEditor}>
          {Object.entries(dictValue).map(([key, val], index) => (
            <Space key={index} style={{ display: 'flex', marginBottom: 8, width: '100%' }}>
              <Input
                value={key}
                placeholder="键名"
                onChange={(e) => {
                  const newDict = { ...dictValue };
                  const oldKey = Object.keys(dictValue)[index];
                  const newKey = e.target.value;
                  if (newKey && newKey !== oldKey) {
                    delete newDict[oldKey];
                    newDict[newKey] = val;
                    onChange(field.key, newDict);
                  }
                }}
                style={{ width: '35%' }}
              />
              <Input
                value={String(val)}
                placeholder="值"
                onChange={(e) => {
                  const newDict = { ...dictValue };
                  const currentKey = Object.keys(dictValue)[index];
                  let newValue: any = e.target.value;
                  // Try to convert to number
                  if (!isNaN(Number(newValue)) && newValue.trim() !== '') {
                    newValue = Number(newValue);
                  } else if (newValue.toLowerCase() === 'true') {
                    newValue = true;
                  } else if (newValue.toLowerCase() === 'false') {
                    newValue = false;
                  }
                  newDict[currentKey] = newValue;
                  onChange(field.key, newDict);
                }}
                style={{ flex: 1 }}
              />
              <MinusCircleOutlined
                onClick={() => {
                  const newDict = { ...dictValue };
                  const currentKey = Object.keys(dictValue)[index];
                  delete newDict[currentKey];
                  onChange(field.key, newDict);
                }}
                style={{ color: '#ff4d4f', fontSize: 18 }}
              />
            </Space>
          ))}
          <Button
            type="dashed"
            onClick={() => {
              onChange(field.key, { ...dictValue, 'new_key': '' });
            }}
            icon={<PlusOutlined />}
            style={{ width: '100%' }}
          >
            添加键值对
          </Button>
        </div>
      );
    }
    
    // Fallback to JSON editor for complex objects
    return (
      <Input.TextArea
        value={JSON.stringify(value, null, 2)}
        onChange={(e) => {
          try {
            const parsedValue = JSON.parse(e.target.value);
            onChange(field.key, parsedValue);
          } catch (err) {
            message.error('JSON格式不正确，请检查');
          }
        }}
        rows={6}
        style={{ width: '100%', fontFamily: 'monospace' }}
      />
    );
  }

  // Handle string list/array types with dynamic add/remove editor
  if (field.type === 'list' || field.type === 'List') {
    const listValue = Array.isArray(value) ? value : [];
    
    // Check if all items are strings
    const isStringList = listValue.every(item => typeof item === 'string');
    
    if (isStringList) {
      return (
        <div className={styles.listEditor}>
          {listValue.map((item, index) => (
            <Space key={index} style={{ display: 'flex', marginBottom: 8, width: '100%' }}>
              <Input
                value={item}
                onChange={(e) => {
                  const newList = [...listValue];
                  newList[index] = e.target.value;
                  onChange(field.key, newList);
                }}
                style={{ flex: 1 }}
              />
              <MinusCircleOutlined
                onClick={() => {
                  const newList = listValue.filter((_, i) => i !== index);
                  onChange(field.key, newList);
                }}
                style={{ color: '#ff4d4f', fontSize: 18 }}
              />
            </Space>
          ))}
          <Button
            type="dashed"
            onClick={() => {
              onChange(field.key, [...listValue, '']);
            }}
            icon={<PlusOutlined />}
            style={{ width: '100%' }}
          >
            添加项
          </Button>
        </div>
      );
    }
    
    // Fallback to JSON editor for non-string lists
    return (
      <Input.TextArea
        value={JSON.stringify(value, null, 2)}
        onChange={(e) => {
          try {
            const parsedValue = JSON.parse(e.target.value);
            onChange(field.key, parsedValue);
          } catch (err) {
            message.error('JSON格式不正确，请检查');
          }
        }}
        rows={6}
        style={{ width: '100%', fontFamily: 'monospace' }}
      />
    );
  }

  switch (field.type) {
    case 'bool':
      return (
        <Switch
          checked={!!value}
          onChange={(checked) => onChange(field.key, checked)}
        />
      );
    case 'float':
      return (
        <InputNumber
          value={value}
          onChange={(val) => onChange(field.key, val)}
          step={0.05}
          style={{ width: '100%' }}
        />
      );
    case 'int':
      return (
        <InputNumber
          value={value}
          onChange={(val) => onChange(field.key, val)}
          step={1}
          style={{ width: '100%' }}
        />
      );
    case 'str':
      return (
        <Input
          value={value}
          onChange={(e) => onChange(field.key, e.target.value)}
        />
      );
    default:
      // Try to handle complex types as JSON
      if (typeof value === 'object' && value !== null) {
        return (
          <Input.TextArea
            value={JSON.stringify(value, null, 2)}
            onChange={(e) => {
              try {
                const parsedValue = JSON.parse(e.target.value);
                onChange(field.key, parsedValue);
              } catch (err) {
                message.error('JSON格式不正确，请检查');
              }
            }}
            rows={4}
            style={{ width: '100%', fontFamily: 'monospace' }}
          />
        );
      }
      return (
        <Input
          value={String(value ?? '')}
          onChange={(e) => onChange(field.key, e.target.value)}
        />
      );
  }
}
