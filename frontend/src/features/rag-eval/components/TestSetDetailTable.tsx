import { Table, Button, Tag, Popconfirm } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import type { TestCase } from '@/api/rag-test';

const DOMAIN_COLORS: Record<string, string> = {
  MOTOR_DEVELOPMENT: 'blue',
  SENSORY_INTEGRATION: 'green',
  COGNITIVE_DEVELOPMENT: 'orange',
  LANGUAGE_DEVELOPMENT: 'purple',
  SOCIAL_EMOTIONAL: 'cyan',
};

interface TestSetDetailTableProps {
  cases: TestCase[];
  onRemove: (id: string) => void;
}

export function TestSetDetailTable({ cases, onRemove }: TestSetDetailTableProps) {
  const columns = [
    {
      title: '查询语句',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
    },
    {
      title: '年龄',
      dataIndex: 'age',
      key: 'age',
      width: 80,
      render: (age: number) => `${age}月`,
    },
    {
      title: '领域',
      dataIndex: 'domain',
      key: 'domain',
      width: 120,
      render: (domain: string) => (
        <Tag color={DOMAIN_COLORS[domain] || 'default'}>{domain}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: { id: string }) => (
        <Popconfirm
          title="确定移除此用例？"
          onConfirm={() => onRemove(record.id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={cases}
      rowKey="id"
      pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
    />
  );
}