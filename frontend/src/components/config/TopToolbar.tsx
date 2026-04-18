import React from 'react';
import { Button, Space } from 'antd';
import { SearchBox } from './SearchBox';

interface TopToolbarProps {
  configFields: Array<{
    key: string;
    label: string;
    category: string;
    description?: string;
  }>;
  onSearch: (query: string) => void;
  onSelectSearch: (key: string) => void;
  onSave: () => void;
  onReset: () => void;
  isSaving: boolean;
  hasChanges: boolean;
  changeCount: number;
}

export const TopToolbar: React.FC<TopToolbarProps> = ({
  configFields,
  onSearch,
  onSelectSearch,
  onSave,
  onReset,
  isSaving,
  hasChanges,
  changeCount
}) => {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '12px 16px',
      borderBottom: '1px solid #f0f0f0',
      backgroundColor: '#fff'
    }}>
      <SearchBox
        configFields={configFields}
        onSearch={onSearch}
        onSelect={onSelectSearch}
      />

      <Space>
        <Button
          danger
          onClick={onReset}
        >
          恢复出厂设置
        </Button>
        <Button
          type="primary"
          onClick={onSave}
          loading={isSaving}
          disabled={!hasChanges}
        >
          保存配置 {hasChanges ? `(${changeCount} 项修改)` : ''}
        </Button>
      </Space>
    </div>
  );
};
