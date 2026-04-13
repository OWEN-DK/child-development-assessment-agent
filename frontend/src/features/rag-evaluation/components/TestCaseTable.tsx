import React, { useState } from 'react';
import { Table, Button, Space, Input, Select, Tag, Popconfirm } from 'antd';
import { SearchOutlined, PlayCircleOutlined, EditOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import type { TestCase } from '@/api/rag-test/types';
import { TestCaseModal } from './TestCaseModal';

const { Search } = Input;

interface TestCaseTableProps {
  testCases: TestCase[];
  loading: boolean;
  onRefresh: () => void;
  onRunSingle?: (caseId: string) => void;
  onDelete?: (caseId: string) => void;
  onBatchDelete?: (caseIds: string[]) => void;
}

export const TestCaseTable: React.FC<TestCaseTableProps> = ({
  testCases,
  loading,
  onRefresh,
  onRunSingle,
  onDelete,
  onBatchDelete,
}) => {
  const [searchText, setSearchText] = useState('');
  const [domainFilter, setDomainFilter] = useState<string | undefined>(undefined);
  const [ageFilter, setAgeFilter] = useState<number | undefined>(undefined);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCase, setEditingCase] = useState<TestCase | undefined>(undefined);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  const filteredCases = testCases.filter(tc => {
    const matchesSearch = !searchText || tc.query.toLowerCase().includes(searchText.toLowerCase());
    const matchesDomain = !domainFilter || (tc as any).domain === domainFilter;
    const matchesAge = !ageFilter || tc.age === ageFilter;
    return matchesSearch && matchesDomain && matchesAge;
  });

  const handleEdit = (record: TestCase) => {
    setEditingCase(record);
    setModalVisible(true);
  };

  const handleCreate = () => {
    setEditingCase(undefined);
    setModalVisible(true);
  };

  const handleModalClose = () => {
    setModalVisible(false);
    setEditingCase(undefined);
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 120,
      ellipsis: true,
    },
    {
      title: '查询内容',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
    },
    {
      title: '年龄',
      dataIndex: 'age',
      key: 'age',
      width: 80,
      sorter: (a: TestCase, b: TestCase) => a.age - b.age,
    },
    {
      title: '领域',
      dataIndex: 'domain',
      key: 'domain',
      width: 120,
      render: (domain: string) => domain ? <Tag color="blue">{domain}</Tag> : '-',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: TestCase) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => onRunSingle?.(record.id)}
          >
            运行
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此测试用例？"
            onConfirm={() => onDelete?.(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <Search
          placeholder="搜索查询内容"
          allowClear
          style={{ width: 300 }}
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          prefix={<SearchOutlined />}
        />
        <Select
          placeholder="选择领域"
          allowClear
          style={{ width: 150 }}
          value={domainFilter}
          onChange={setDomainFilter}
          options={[
            { label: '粗大动作', value: '粗大动作' },
            { label: '精细动作', value: '精细动作' },
            { label: '语言发展', value: '语言发展' },
            { label: '认知能力', value: '认知能力' },
            { label: '社交情感', value: '社交情感' },
            { label: '感觉统合', value: '感觉统合' },
          ]}
        />
        <Select
          placeholder="选择年龄"
          allowClear
          style={{ width: 120 }}
          value={ageFilter}
          onChange={setAgeFilter}
          options={Array.from({ length: 13 }, (_, i) => ({
            label: `${i}岁`,
            value: i,
          }))}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          新建测试用例
        </Button>
        {selectedRowKeys.length > 0 && (
          <Popconfirm
            title={`确定删除选中的 ${selectedRowKeys.length} 个测试用例？`}
            onConfirm={() => {
              onBatchDelete?.(selectedRowKeys as string[]);
              setSelectedRowKeys([]);
            }}
            okText="确定"
            cancelText="取消"
          >
            <Button danger icon={<DeleteOutlined />}>
              批量删除 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        )}
      </div>

      <Table
        columns={columns}
        dataSource={filteredCases}
        rowKey="id"
        loading={loading}
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
        scroll={{ x: 1200 }}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: total => `共 ${total} 条` }}
      />

      <TestCaseModal
        visible={modalVisible}
        testCase={editingCase}
        onClose={handleModalClose}
        onSuccess={onRefresh}
      />
    </div>
  );
};
