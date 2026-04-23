import { Table, Button, Tag, Popconfirm } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import type { TestCase } from '@/api/rag-test';

const DOMAIN_MAP: Record<string, string> = {
  gross_motor: '大运动',
  fine_motor: '精细运动',
  language: '语言',
  cognitive: '认知',
  social_emotional: '社交情感',
  sensory_integration: '感觉统合',
};

const DOMAIN_COLORS: Record<string, string> = {
  gross_motor: 'blue',
  fine_motor: 'green',
  language: 'orange',
  cognitive: 'purple',
  social_emotional: 'cyan',
  sensory_integration: 'magenta',
};

const formatAge = (age: number): string => {
  if (!age && age !== 0) return '-';
  const years = Math.floor(age / 12);
  const months = age % 12;
  if (years > 0 && months > 0) return `${years}岁${months}月`;
  if (years > 0) return `${years}岁`;
  return `${months}月`;
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
      width: 100,
      render: (age: number) => formatAge(age),
    },
    {
      title: '领域',
      dataIndex: 'domain',
      key: 'domain',
      width: 120,
      render: (domain: string) => (
        <Tag color={DOMAIN_COLORS[domain] || 'default'}>{DOMAIN_MAP[domain] || domain}</Tag>
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