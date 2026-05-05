import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Space, Button, Typography, Alert, message, Table, Modal, Popconfirm,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import type { EvalReport } from '@entities/rag-eval';
import { useReports, useDeleteReport, useBatchDeleteReports } from '../hooks/useReports';
import { formatPercent, formatDuration, formatTimestamp } from '@entities/rag-eval';
import { useState } from 'react';

const { Text } = Typography;

export function ReportPage() {
  const navigate = useNavigate();
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const { data: reportsData, isLoading, isError } = useReports({ page, page_size: pageSize });
  const deleteMutation = useDeleteReport();
  const batchDeleteMutation = useBatchDeleteReports();

  const reports = reportsData?.items || [];
  const total = reportsData?.total || 0;

  const handleDelete = useCallback((id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后不可恢复',
      onOk: async () => {
        await deleteMutation.mutateAsync(id);
        message.success('已删除');
      },
    });
  }, [deleteMutation]);

  const handleBatchDelete = useCallback(async () => {
    if (selectedRowKeys.length === 0) return;
    Modal.confirm({
      title: '批量删除',
      content: `确定要删除选中的 ${selectedRowKeys.length} 个报告吗？`,
      onOk: async () => {
        await batchDeleteMutation.mutateAsync(selectedRowKeys);
        setSelectedRowKeys([]);
        message.success(`已删除 ${selectedRowKeys.length} 个报告`);
      },
    });
  }, [selectedRowKeys, batchDeleteMutation]);

  const columns: ColumnsType<EvalReport> = [
    { title: '运行名称', dataIndex: 'run_name', width: 160, ellipsis: true },
    {
      title: '综合得分', dataIndex: 'overall_score', width: 100,
      render: (s: number) => (
        <Text strong style={{ color: s >= 0.7 ? '#52c41a' : s >= 0.5 ? '#faad14' : '#ff4d4f' }}>
          {formatPercent(s, 1)}
        </Text>
      ),
    },
    {
      title: '通过/总数', width: 100,
      render: (_, r) => <Text>{r.passed_test_cases}/{r.total_test_cases}</Text>,
    },
    {
      title: '耗时', width: 100,
      render: (_, r) => r.duration_seconds ? formatDuration(r.duration_seconds) : '-',
    },
    {
      title: '状态', dataIndex: 'status', width: 90,
      render: (s: string) => (
        <Text type={s === 'completed' ? 'success' : s === 'superseded' ? 'secondary' : 'warning'}>{s}</Text>
      ),
    },
    {
      title: '创建时间', dataIndex: 'created_at', width: 150,
      render: (t: string) => <Text style={{ fontSize: 12 }}>{formatTimestamp(t)}</Text>,
    },
    {
      title: '操作', width: 160,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" type="primary" icon={<EyeOutlined />} onClick={() => navigate(`/rag-eval/reports/${record.id}`)}>查看</Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (isError) return <Alert type="error" message="加载报告列表失败" showIcon />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>评估报告</Typography.Title>
        <Space>
          <Button danger icon={<DeleteOutlined />} disabled={selectedRowKeys.length === 0} onClick={handleBatchDelete} loading={batchDeleteMutation.isPending}>
            批量删除
          </Button>
        </Space>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={reports}
        loading={isLoading}
        size="small"
        rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys as string[]) }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
        scroll={{ x: 800 }}
      />
    </div>
  );
}
