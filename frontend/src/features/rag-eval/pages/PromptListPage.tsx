/**
 * 提示词列表页
 * 路由: /prompt-management
 */

import React, { useEffect, useState } from 'react';
import { Table, Tag, Input, Select, Button, Space, Typography, Card } from 'antd';
import { SearchOutlined, EditOutlined, UnorderedListOutlined, ExperimentOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getPromptList, PromptMetadata } from '@/api/rag-eval/prompts';

const { Title } = Typography;
const { Search } = Input;

const CATEGORY_MAP: Record<string, { label: string; color: string }> = {
  rag_retrieval: { label: 'RAG 检索', color: 'blue' },
  rag_generation: { label: 'RAG 生成', color: 'cyan' },
  assessment: { label: '评估', color: 'green' },
  scoring: { label: '评分', color: 'orange' },
  reporting: { label: '报告', color: 'purple' },
  test_case_generation: { label: '测试用例生成', color: 'magenta' },
};

const PromptListPage: React.FC = () => {
  const navigate = useNavigate();
  const [prompts, setPrompts] = useState<PromptMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();

  const fetchPrompts = async (category?: string) => {
    setLoading(true);
    try {
      const data = await getPromptList(category);
      setPrompts(data.items);
    } catch (error) {
      console.error('获取提示词列表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrompts(categoryFilter);
  }, [categoryFilter]);

  const filteredPrompts = prompts.filter(
    (p) =>
      p.name_zh.toLowerCase().includes(searchText.toLowerCase()) ||
      p.prompt_key.toLowerCase().includes(searchText.toLowerCase()) ||
      p.purpose.toLowerCase().includes(searchText.toLowerCase())
  );

  const columns = [
    {
      title: '中文名称',
      dataIndex: 'name_zh',
      key: 'name_zh',
      render: (text: string, record: PromptMetadata) => (
        <a onClick={() => navigate(`/prompt-management/${record.prompt_key}`)}>{text}</a>
      ),
    },
    {
      title: '标识',
      dataIndex: 'prompt_key',
      key: 'prompt_key',
      render: (text: string) => <code>{text}</code>,
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      render: (category: string) => {
        const info = CATEGORY_MAP[category] || { label: category, color: 'default' };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: '用途说明',
      dataIndex: 'purpose',
      key: 'purpose',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'red'}>{active ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: PromptMetadata) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => navigate(`/prompt-management/${record.prompt_key}`)}
          >
            编辑
          </Button>
          <Button
            type="link"
            icon={<UnorderedListOutlined />}
            onClick={() => navigate(`/prompt-management/${record.prompt_key}/versions`)}
          >
            版本
          </Button>
          <Button
            type="link"
            icon={<ExperimentOutlined />}
            onClick={() => navigate(`/prompt-management/${record.prompt_key}/test`)}
          >
            沙箱
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>提示词管理</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space style={{ marginBottom: 16 }}>
          <Search
            placeholder="搜索提示词名称、标识或用途"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 300 }}
            allowClear
          />
          <Select
            placeholder="筛选分类"
            style={{ width: 150 }}
            allowClear
            value={categoryFilter}
            onChange={(val) => setCategoryFilter(val)}
            options={Object.entries(CATEGORY_MAP).map(([key, val]) => ({
              label: val.label,
              value: key,
            }))}
          />
        </Space>

        <Table
          columns={columns}
          dataSource={filteredPrompts}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
};

export default PromptListPage;
