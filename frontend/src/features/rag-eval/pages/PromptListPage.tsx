import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router';
import {
  Table, Select, Input, Tag, Button, Space, Tooltip, Typography, Alert, Row, Col,
} from 'antd';
import {
  EditOutlined, SwapOutlined, ExperimentOutlined, CheckCircleFilled, CloseCircleFilled,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { PromptMetadata, PromptCategory } from '@entities/rag-eval';
import { getPromptCategoryLabel, getPromptCategoryColor, formatTimestamp } from '@entities/rag-eval';
import { PROMPT_CATEGORY_MAP } from '@entities/rag-eval';
import { usePrompts } from '../hooks/usePrompts';

const { Title, Text } = Typography;

const CATEGORY_OPTIONS = Object.entries(PROMPT_CATEGORY_MAP).map(([value, { label }]) => ({
  value,
  label,
}));

export function PromptListPage() {
  const navigate = useNavigate();
  const [categoryFilter, setCategoryFilter] = useState<PromptCategory | undefined>();
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>();
  const [searchText, setSearchText] = useState('');

  const { data, isLoading, isError } = usePrompts({
    category: categoryFilter,
    is_active: activeFilter,
  });

  const filteredItems = useMemo(() => {
    const items = data?.items || [];
    if (!searchText) return items;
    const lower = searchText.toLowerCase();
    return items.filter(
      (item) =>
        item.name_zh.toLowerCase().includes(lower) ||
        item.prompt_key.toLowerCase().includes(lower),
    );
  }, [data?.items, searchText]);

  const handleCategoryChange = useCallback((value: string | undefined) => {
    setCategoryFilter(value as PromptCategory | undefined);
  }, []);

  const handleActiveChange = useCallback((value: string | undefined) => {
    if (value === undefined) {
      setActiveFilter(undefined);
    } else {
      setActiveFilter(value === 'true');
    }
  }, []);

  const columns: ColumnsType<PromptMetadata> = [
    {
      title: '名称',
      dataIndex: 'name_zh',
      width: 200,
      ellipsis: true,
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: 'Key',
      dataIndex: 'prompt_key',
      width: 220,
      ellipsis: true,
      render: (key: string) => <Text code>{key}</Text>,
    },
    {
      title: '分类',
      dataIndex: 'category',
      width: 130,
      render: (category: string) => (
        <Tag color={getPromptCategoryColor(category)}>
          {getPromptCategoryLabel(category)}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: (active: boolean) =>
        active ? (
          <Tag icon={<CheckCircleFilled />} color="success">启用</Tag>
        ) : (
          <Tag icon={<CloseCircleFilled />} color="default">禁用</Tag>
        ),
    },
    {
      title: '系统内置',
      dataIndex: 'is_system',
      width: 90,
      render: (isSystem: boolean) =>
        isSystem ? <Tag color="purple">内置</Tag> : <Tag>自定义</Tag>,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 160,
      render: (ts: string | null) => (ts ? formatTimestamp(ts) : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="编辑">
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => navigate(`/prompt-management/${record.prompt_key}`)}
            />
          </Tooltip>
          <Tooltip title="版本对比">
            <Button
              size="small"
              icon={<SwapOutlined />}
              onClick={() => navigate(`/prompt-management/${record.prompt_key}/versions`)}
            />
          </Tooltip>
          <Tooltip title="测试沙箱">
            <Button
              size="small"
              icon={<ExperimentOutlined />}
              onClick={() => navigate(`/prompt-management/${record.prompt_key}/test`)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ margin: '0 0 16px' }}>提示词管理</Title>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Input.Search
            placeholder="搜索名称或 Key..."
            allowClear
            onSearch={setSearchText}
            style={{ width: '100%' }}
          />
        </Col>
        <Col xs={12} sm={6}>
          <Select
            placeholder="分类筛选"
            allowClear
            value={categoryFilter}
            onChange={handleCategoryChange}
            options={CATEGORY_OPTIONS}
            style={{ width: '100%' }}
          />
        </Col>
        <Col xs={12} sm={6}>
          <Select
            placeholder="状态筛选"
            allowClear
            value={activeFilter === undefined ? undefined : String(activeFilter)}
            onChange={handleActiveChange}
            options={[
              { value: 'true', label: '启用' },
              { value: 'false', label: '禁用' },
            ]}
            style={{ width: '100%' }}
          />
        </Col>
      </Row>

      {isError && <Alert type="error" message="加载提示词列表失败" showIcon style={{ marginBottom: 16 }} />}

      <Table
        rowKey="id"
        columns={columns}
        dataSource={filteredItems}
        loading={isLoading}
        size="small"
        scroll={{ x: 1000 }}
        pagination={{
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
        }}
      />
    </div>
  );
}
