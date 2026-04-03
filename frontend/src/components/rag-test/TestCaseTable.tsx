import React from 'react';
import { Table, Button, Space, Tag, Popconfirm } from 'antd';
import { EditOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TestCase } from '../../api/rag-test/types';
import { formatDateTime } from '../../utils/formatters';

interface TestCaseTableProps {
  testCases: TestCase[];
  loading: boolean;
  testRunning: boolean;
  onEdit: (record: TestCase) => void;
  onDelete: (id: string) => void;
  onRun: (record: TestCase) => void;
}

export const TestCaseTable: React.FC<TestCaseTableProps> = ({
  testCases,
  loading,
  testRunning,
  onEdit,
  onDelete,
  onRun,
}) => {
  const columns: ColumnsType<TestCase> = [
    {
      title: '查询内容',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
      width: 250,
    },
    {
      title: '年龄',
      dataIndex: 'age',
      key: 'age',
      width: 80,
    },
    {
      title: '预期关键词',
      dataIndex: 'expected_keywords',
      key: 'expected_keywords',
      render: (keywords: string[]) => (
        <Space wrap>
          {keywords.map((kw, idx) => (
            <Tag key={idx}>{kw}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => formatDateTime(date),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => onRun(record)}
            loading={testRunning}
          >
            运行
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => onEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该测试用例吗？"
            onConfirm={() => onDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={testCases}
      rowKey="id"
      loading={loading}
      pagination={{
        pageSize: 10,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条测试用例`,
      }}
    />
  );
};
