import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import {
  Space, Button, Table, Modal, message, Typography, Alert, Row, Col, Select, Form, Input, Progress, Popconfirm, Spin,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, PlayCircleOutlined, DeleteOutlined, StopOutlined, EyeOutlined } from '@ant-design/icons';
import type { TestRun, TestRunStatus, TestSet } from '@entities/rag-eval';
import { useTestRuns, useCreateRun, useExecuteRun, useCancelRun, useDeleteRun, useBatchDeleteRuns } from '../hooks/useTestRuns';
import { useTestSets } from '../hooks/useTestSets';
import { useRunProgressStore } from '../stores/runProgressStore';
import { StatusBadge } from '../components/common/StatusBadge';
import { getRunStatusLabel } from '@entities/rag-eval';
import { formatPercent, formatDuration, formatTimestamp } from '@entities/rag-eval';
const { Title, Text } = Typography;

export function RunPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [form] = Form.useForm<{ name: string; test_set_ids: string[] }>();

  const queryClient = useQueryClient();

  // 从 Zustand store 读取进度状态
  const sseProgress = useRunProgressStore(s => s.sseProgress);
  const reportProgressMap = useRunProgressStore(s => s.reportProgress);
  const reportIdMap = useRunProgressStore(s => s.reportIdMap);
  const storeStartSSE = useRunProgressStore(s => s.startSSE);
  const storeOnMount = useRunProgressStore(s => s.onMount);
  const storeOnUnmount = useRunProgressStore(s => s.onUnmount);

  const { data, isLoading, isError, refetch } = useTestRuns({ status: statusFilter });
  const { data: testSetsData } = useTestSets();
  const createMutation = useCreateRun();
  const executeMutation = useExecuteRun();
  const cancelMutation = useCancelRun();
  const deleteMutation = useDeleteRun();
  const batchDeleteMutation = useBatchDeleteRuns();

  const testSets = testSetsData || [];

  const startSSE = useCallback((runId: string) => {
    storeStartSSE(runId, () => {
      refetch();
      queryClient.invalidateQueries({ queryKey: ['rag-eval', 'reports'] });
    });
  }, [storeStartSSE, refetch, queryClient]);

  // 挂载/卸载：重连活跃 run 的 SSE
  useEffect(() => {
    storeOnMount(() => {
      refetch();
      queryClient.invalidateQueries({ queryKey: ['rag-eval', 'reports'] });
    });
    return storeOnUnmount;
  }, [storeOnMount, storeOnUnmount, refetch, queryClient]);

  const handleCreate = useCallback(async () => {
    const values = await form.validateFields();
    await createMutation.mutateAsync({
      name: values.name,
      test_set_ids: values.test_set_ids,
    });
    setCreateModalOpen(false);
    form.resetFields();
    message.success('运行已创建');
    refetch();
  }, [form, createMutation, refetch]);

  const handleStartEvaluation = useCallback(async (id: string, status?: string) => {
    if (status === 'completed' || status === 'pending') {
      await executeMutation.mutateAsync(id);
      await refetch();
      startSSE(id);
    } else {
      message.info('正在连接进度...');
      startSSE(id);
    }
  }, [startSSE, executeMutation, refetch]);

  const handleDelete = useCallback((id: string) => {
    Modal.confirm({
      title: '确认删除', content: '删除后不可恢复',
      onOk: async () => { await deleteMutation.mutateAsync(id); message.success('已删除'); },
    });
  }, [deleteMutation]);

  const handleCancel = useCallback((id: string) => {
    Modal.confirm({
      title: '确认取消', content: '取消后已完成的用例结果会保留，未执行的用例将跳过',
      onOk: async () => { await cancelMutation.mutateAsync(id); message.success('已取消'); },
    });
  }, [cancelMutation]);

  const handleBatchDelete = useCallback(async () => {
    if (selectedRowKeys.length === 0) return;
    Modal.confirm({
      title: '批量删除', content: `确定要删除选中的 ${selectedRowKeys.length} 个运行吗？`,
      onOk: async () => { await batchDeleteMutation.mutateAsync(selectedRowKeys); setSelectedRowKeys([]); message.success(`已删除 ${selectedRowKeys.length} 个运行`); },
    });
  }, [selectedRowKeys, batchDeleteMutation]);

  const runs = data?.items || [];

  const columns: ColumnsType<TestRun> = [
    { title: '名称', dataIndex: 'name', width: 160, ellipsis: true },
    { title: '状态', dataIndex: 'status', width: 90, render: (s: TestRunStatus) => <StatusBadge status={s} /> },
    {
      title: '进度', width: 160,
      render: (_, r: TestRun) => {
        const sse = sseProgress[r.id];
        if (sse && sse.total > 0) {
          const pct = Math.round((sse.current / sse.total) * 100);
          return <Progress percent={pct} size="small" format={() => `${sse.current}/${sse.total}`} />;
        }
        const p = r.progress;
        if (p != null) return <Progress percent={Math.round(p)} size="small" />;
        if (r.status === 'running') return <Spin size="small" />;
        const rp = reportProgressMap[r.id];
        if (rp) return <Progress percent={rp.percent} size="small" format={() => rp.label} />;
        return <Text type="secondary">-</Text>;
      },
    },
    { title: '通过/总数', width: 100, render: (_, r) => <Text>{r.passed_test_cases}/{r.total_test_cases}</Text> },
    { title: '综合得分', dataIndex: 'overall_score', width: 100,
      render: (s: number | null) => s != null ? <Text strong style={{ color: s >= 0.7 ? '#52c41a' : s >= 0.5 ? '#faad14' : '#ff4d4f' }}>{formatPercent(s, 1)}</Text> : '-',
    },
    { title: '耗时', width: 100,
      render: (_, r) => {
        if (!r.started_at) return '-';
        const start = new Date(r.started_at).getTime();
        const end = r.completed_at ? new Date(r.completed_at).getTime() : Date.now();
        return formatDuration((end - start) / 1000);
      },
    },
    { title: '创建时间', dataIndex: 'created_at', width: 140, render: (t: string) => <Text style={{ fontSize: 12 }}>{formatTimestamp(t)}</Text> },
    {
      title: '操作', width: 180,
      render: (_, record) => (
        <Space size="small">
          {record.status === 'pending' && (
            <Button size="small" type="primary" icon={<PlayCircleOutlined />} onClick={() => handleStartEvaluation(record.id, record.status)} loading={executeMutation.isPending}>执行</Button>
          )}
          {record.status === 'running' && (
            <>
              <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleStartEvaluation(record.id, record.status)}>查看进度</Button>
              <Popconfirm title="确认取消运行？" onConfirm={() => handleCancel(record.id)}>
                <Button size="small" danger icon={<StopOutlined />} loading={cancelMutation.isPending}>取消</Button>
              </Popconfirm>
            </>
          )}
          {record.status === 'completed' && (
            <>
              <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleStartEvaluation(record.id, record.status)}>重新评估</Button>
              {reportIdMap[record.id] && (
                <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => navigate(`/rag-eval/reports/${reportIdMap[record.id]}`)}>查看报告</Button>
              )}
            </>
          )}
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>运行管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>新建运行</Button>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={4}>
          <Select placeholder="状态筛选" allowClear value={statusFilter} onChange={setStatusFilter}
            options={(['pending', 'running', 'completed', 'failed', 'cancelled'] as const).map((s) => ({ value: s, label: getRunStatusLabel(s as TestRunStatus) }))}
            style={{ width: '100%' }} />
        </Col>
        <Col xs={12} sm={4}>
          <Button danger icon={<DeleteOutlined />} disabled={selectedRowKeys.length === 0} onClick={handleBatchDelete} loading={batchDeleteMutation.isPending}>批量删除</Button>
        </Col>
      </Row>

      {isError && <Alert type="error" message="加载运行列表失败" showIcon style={{ marginBottom: 16 }} />}

      <Table rowKey="id" columns={columns} dataSource={runs} loading={isLoading} size="small"
        rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys as string[]) }}
        pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ x: 1000 }} />

      <Modal title="新建运行" open={createModalOpen} onOk={handleCreate} onCancel={() => setCreateModalOpen(false)} confirmLoading={createMutation.isPending}>
        <Form form={form} layout="vertical" size="small">
          <Form.Item name="name" label="运行名称" rules={[{ required: true }]}><Input placeholder="输入运行名称" /></Form.Item>
          <Form.Item name="test_set_ids" label="选择测试集" rules={[{ required: true }]}>
            <Select mode="multiple" placeholder="选择测试集" options={testSets.map((s: TestSet) => ({ value: s.id, label: s.name }))} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
