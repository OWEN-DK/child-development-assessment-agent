import React, { useEffect, useState, useMemo, useRef } from 'react';
import { Input, AutoComplete } from 'antd';

interface SearchBoxProps {
  configFields: Array<{
    key: string;
    label: string;
    category: string;
    description?: string;
  }>;
  onSearch: (query: string) => void;
  onSelect: (key: string) => void;
}

export const SearchBox: React.FC<SearchBoxProps> = ({
  configFields,
  onSearch,
  onSelect
}) => {
  const [localQuery, setLocalQuery] = useState('');
  const inputRef = useRef<any>(null);

  // ⌘K 快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // 使用 useMemo 缓存搜索结果，提升性能
  const options = useMemo(() => {
    if (!localQuery.trim()) return [];

    const query = localQuery.toLowerCase();
    return configFields
      .filter(f =>
        f.label.toLowerCase().includes(query) ||
        f.description?.toLowerCase().includes(query) ||
        f.category.toLowerCase().includes(query) ||
        f.key.toLowerCase().includes(query)
      )
      .slice(0, 10)
      .map(f => ({
        label: (
          <div>
            <div>{f.label}</div>
            <div style={{ fontSize: 12, color: '#999' }}>{f.category}</div>
          </div>
        ),
        value: f.key,
      }));
  }, [localQuery, configFields]);

  const handleChange = (value: string) => {
    setLocalQuery(value);
    onSearch(value);
  };

  const handleSelect = (value: string) => {
    onSelect(value);
  };

  return (
    <AutoComplete
      options={options}
      style={{ width: 300 }}
      onSelect={handleSelect}
    >
      <Input.Search
        ref={inputRef}
        placeholder="搜索配置... (⌘K)"
        value={localQuery}
        onChange={(e) => handleChange(e.target.value)}
        allowClear
      />
    </AutoComplete>
  );
};
