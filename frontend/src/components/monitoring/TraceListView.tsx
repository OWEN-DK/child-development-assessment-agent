import React, { useState } from 'react';
import { Table, Tag, Space, Button, Tooltip } from 'antd';
import { CopyOutlined, EyeOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { tracingApi } from '@/api/tracing';
import type { Trace } from '@/types/tracing';

interface TraceListViewProps {
  filters?: Record<string, any>;
  onRowClick?: (traceId: string) => void;
}

const statusColorMap: Record<string, string> = {
  success: 'green',
  failed: 'red',
  partial: 'orange',
};

export const TraceListView: React.FC<TraceListViewProps> = ({ filters, onRowClick }) => {
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  const { data, isLoading } = useQuery({
    queryKey: ['traces', pagination.current, pagination.pageSize, filters],
    queryFn: () =>
      tracingApi.getTraces(pagination.current, pagination.pageSize, filters),
  });

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      sorter: true,
      render: (date: string) => new Date(date).toLocaleString(),
      width: 180,
    },
    {
      title: '场景/名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
    },
    {
      title: '模型',
      dataIndex: 'metadata',
      key: 'model',
      render: (metadata: Record<string, any>) => metadata?.model || '-',
      width: 150,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={statusColorMap[status] || 'default'}>{status}</Tag>
      ),
      width: 100,
    },
    {
      title: 'Token',
      dataIndex: 'total_tokens',
      key: 'total_tokens',
      sorter: true,
      width: 100,
    },
    {
      title: '延迟',
      dataIndex: 'total_duration_ms',
      key: 'total_duration_ms',
      sorter: true,
      render: (ms: number) => `${ms}ms`,
      width: 100,
    },
    {
      title: '成本',
      dataIndex: 'total_cost',
      key: 'total_cost',
      render: (cost: string) => (cost ? `¥${cost}` : '未配置'),
      width: 100,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: Trace) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => onRowClick?.(record.trace_id)}
            />
          </Tooltip>
          <Tooltip title="复制 Trace ID">
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={() => navigator.clipboard.writeText(record.trace_id)}
            />
          </Tooltip>
        </Space>
      ),
      width: 100,
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={data?.items || []}
      rowKey="trace_id"
      loading={isLoading}
      pagination={{
        current: pagination.current,
        pageSize: pagination.pageSize,
        total: data?.total || 0,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条`,
      }}
      onChange={(pag) =>
        setPagination((prev) => ({ ...prev, current: pag.current || 1 }))
      }
    />
  );
};
