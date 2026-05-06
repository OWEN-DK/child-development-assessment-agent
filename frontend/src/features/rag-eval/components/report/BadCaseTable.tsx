import { Table, Typography, Empty } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { formatPercent } from '@entities/rag-eval';

const { Text } = Typography;

interface BadCase {
  query: string;
  precision: number;
  recall: number;
  error_message: string | null;
}

interface BadCaseTableProps {
  cases: BadCase[];
  loading?: boolean;
}

export function BadCaseTable({ cases, loading }: BadCaseTableProps) {
  const columns: ColumnsType<BadCase> = [
    { title: '查询', dataIndex: 'query', width: 200, ellipsis: true },
    {
      title: '精确率',
      dataIndex: 'precision',
      width: 80,
      render: (v: number) => (
        <Text type={v < 0.5 ? 'danger' : 'success'}>{formatPercent(v, 1)}</Text>
      ),
    },
    {
      title: '召回率',
      dataIndex: 'recall',
      width: 80,
      render: (v: number) => (
        <Text type={v < 0.5 ? 'danger' : 'success'}>{formatPercent(v, 1)}</Text>
      ),
    },
    {
      title: '错误信息',
      dataIndex: 'error_message',
      width: 200,
      ellipsis: true,
      render: (msg: string | null) => msg ? <Text type="danger">{msg}</Text> : '-',
    },
  ];

  return (
    <Table
      rowKey="query"
      columns={columns}
      dataSource={cases}
      loading={loading}
      size="small"
      pagination={{ pageSize: 10, showSizeChanger: false }}
      locale={{ emptyText: <Empty description="无失败用例" /> }}
    />
  );
}
