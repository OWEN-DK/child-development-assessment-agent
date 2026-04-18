import React, { useRef } from 'react';
import { Input, Space, Typography } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { InputRef } from 'antd';
import { useDebounceCallback } from '@shared/hooks/useDebounce';
import { DEBOUNCE_DELAY } from '@shared/lib/constants';

const { Search } = Input;

interface SearchInputProps {
  onSearch: (query: string) => void;
  resultCount?: number;
}

export const SearchInput: React.FC<SearchInputProps> = ({
  onSearch,
  resultCount,
}) => {
  const [query, setQuery] = React.useState('');
  const searchInputRef = useRef<InputRef>(null);

  const debouncedSearch = useDebounceCallback((value: string) => {
    if (value.trim()) {
      onSearch(value);
    }
  }, DEBOUNCE_DELAY);

  const handleSearch = (value: string) => {
    setQuery(value);
    debouncedSearch(value);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    if (value.trim()) {
      debouncedSearch(value);
    } else {
      onSearch('');
    }
  };

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <Search
        ref={searchInputRef}
        placeholder="输入关键词搜索知识库内容..."
        allowClear
        enterButton={<SearchOutlined />}
        size="large"
        onSearch={handleSearch}
        onChange={handleInputChange}
        value={query}
      />

      {query && (
        <Typography.Text type="secondary">
          找到 {resultCount || 0} 条相关结果，关键词: <Typography.Text strong>{query}</Typography.Text>
        </Typography.Text>
      )}
    </Space>
  );
};
