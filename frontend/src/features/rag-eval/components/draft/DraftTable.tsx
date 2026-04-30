import { Table, Space, Button, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { EyeOutlined, CheckOutlined, CloseOutlined, DeleteOutlined } from '@ant-design/icons';
import type { TestCaseDraft } from '@entities/rag-eval';
import { StatusBadge } from '../common/StatusBadge';
import { formatPercent, formatTimestamp } from '@entities/rag-eval';
import { PAGE_SIZE_OPTIONS } from '@shared/lib/constants';

const { Text } = Typography;

interface PaginationState {
  current: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number, pageSize: number) => void;
}

interface DraftTableProps {
  drafts: TestCaseDraft[];
  loading?: boolean;
  pagination: PaginationState;
  onView: (draft: TestCaseDraft) => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onDelete: (id: string) => void;
  selectedRowKeys?: string[];
  onSelectChange?: (keys: string[]) => void;
}

export function DraftTable({
  drafts,
  loading,
  pagination,
  onView,
  onApprove,
  onReject,
  onDelete,
  selectedRowKeys,
  onSelectChange,
}: DraftTableProps) {
  const columns: ColumnsType<TestCaseDraft> = [
    { title: '查询', dataIndex: 'query', width: 220, ellipsis: true },
    {
      title: '忠实度',
      dataIndex: 'faithfulness_score',
      width: 100,
      render: (v: number | null) =>
        v != null ? <Text type={v >= 0.7 ? 'success' : v >= 0.5 ? 'warning' : 'danger'}>{formatPercent(v, 1)}</Text> : '-',
    },
    { title: '状态', dataIndex: 'status', width: 90, render: (s) => <StatusBadge status={s} type="draft" /> },
    { title: '更新时间', dataIndex: 'updated_at', width: 140, render: (t: string) => <Text style={{ fontSize: 12 }}>{formatTimestamp(t)}</Text> },
    {
      title: '操作', width: 180, key: 'actions',
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="查看详情"><Button size="small" icon={<EyeOutlined />} onClick={() => onView(record)} /></Tooltip>
          {record.status !== 'approved' && record.status !== 'rejected' && (
            <>
              <Tooltip title="通过"><Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => onApprove(record.id)} /></Tooltip>
              <Tooltip title="驳回"><Button size="small" danger icon={<CloseOutlined />} onClick={() => onReject(record.id)} /></Tooltip>
            </>
          )}
          <Tooltip title="删除"><Button size="small" danger icon={<DeleteOutlined />} onClick={() => onDelete(record.id)} /></Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <Table
      rowKey="id"
      columns={columns}
      dataSource={drafts}
      loading={loading}
      size="small"
      rowSelection={onSelectChange ? { selectedRowKeys, onChange: (keys) => onSelectChange(keys as string[]) } : undefined}
      pagination={{
        current: pagination.current,
        pageSize: pagination.pageSize,
        total: pagination.total,
        showSizeChanger: true,
        pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
        onChange: pagination.onPageChange,
        onShowSizeChange: pagination.onPageChange,
        showTotal: (total) => `共 ${total} 条`,
      }}
      scroll={{ x: 900 }}
    />
  );
}
