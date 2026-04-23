import { Table, Tag } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import type { TestResult } from '@/api/rag-test';

interface RunDetailTableProps {
  results: TestResult[];
}

export function RunDetailTable({ results }: RunDetailTableProps) {
  const columns = [
    {
      title: '#',
      key: 'index',
      width: 50,
      render: (_: unknown, __: unknown, index: number) => index + 1,
    },
    {
      title: '查询语句',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
    },
    {
      title: '状态',
      key: 'status',
      width: 60,
      render: (_: unknown, record: TestResult) => (
        record.passed
          ? <Tag color="green"><CheckCircleOutlined /></Tag>
          : <Tag color="red"><CloseCircleOutlined /></Tag>
      ),
    },
    {
      title: 'P@1',
      dataIndex: 'precision',
      key: 'precision',
      width: 70,
      render: (val: number) => val.toFixed(2),
    },
    {
      title: 'R@1',
      dataIndex: 'recall',
      key: 'recall',
      width: 70,
      render: (val: number) => val.toFixed(2),
    },
    {
      title: '耗时',
      dataIndex: 'execution_time_ms',
      key: 'execution_time_ms',
      width: 80,
      render: (val: number) => `${val}ms`,
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={results}
      rowKey="test_case_id"
      pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
    />
  );
}