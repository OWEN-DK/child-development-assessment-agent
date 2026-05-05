import { useState, useCallback, useRef } from 'react';
import {
  Space, Button, Table, Modal, message, Typography, Alert, Row, Col, Select, Form, Input, Progress, Popconfirm, Spin,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, PlayCircleOutlined, DeleteOutlined, FileTextOutlined, StopOutlined } from '@ant-design/icons';
import type { TestRun, TestRunStatus, TestSet } from '@entities/rag-eval';
import { useTestRuns, useCreateRun, useExecuteRun, useCancelRun, useDeleteRun, useBatchDeleteRuns } from '../hooks/useTestRuns';
import { useGenerateReport } from '../hooks/useReports';
import { useTestSets } from '../hooks/useTestSets';
import { createSSEConnection } from '../utils/sse';
import { StatusBadge } from '../components/common/StatusBadge';
import { getRunStatusLabel } from '@entities/rag-eval';
import { formatPercent, formatDuration, formatTimestamp } from '@entities/rag-eval';

const { Title, Text } = Typography;

const TERMINAL_EVENTS = new Set(['run_completed', 'run_failed', 'run_cancelled', 'complete', 'error']);

export function RunPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [form] = Form.useForm<{ name: string; test_set_ids: string[] }>();
  const [sseProgress, setSseProgress] = useState<Record<string, { current: number; total: number }>>({});

  const { data, isLoading, isError, refetch } = useTestRuns({ status: statusFilter });
  const { data: testSetsData } = useTestSets();
  const createMutation = useCreateRun();
  const executeMutation = useExecuteRun();
  const cancelMutation = useCancelRun();
  const deleteMutation = useDeleteRun();
  const batchDeleteMutation = useBatchDeleteRuns();
  const generateReportMutation = useGenerateReport();

  const sseAbortRef = useRef<AbortController | null>(null);
  const progressRef = useRef<Record<string, { current: number; total: number }>>({});

  const testSets = testSetsData || [];

  const startSSE = useCallback((runId: string) => {
    sseAbortRef.current?.abort();
    const controller = new AbortController();
    sseAbortRef.current = controller;

    createSSEConnection(`/api/v1/rag/eval/runs/${runId}/stream`, controller.signal, {
      onOpen: () => {},
      onMessage: (raw: string) => {
        try {
          const event = JSON.parse(raw);
          if (event.type === 'heartbeat') return;
          // 用 run_started 初始化进度（支持重连后恢复 total）
          if (event.type === 'run_started' && event.data) {
            const total = event.data.total_cases ?? 0;
            const prev = progressRef.current[runId];
            progressRef.current[runId] = { current: prev?.current ?? 0, total };
            setSseProgress({ ...progressRef.current });
          }
          // 基于实际完成数追踪进度（case_completed 和 case_failed 都算完成）
          if ((event.type === 'case_completed' || event.type === 'case_failed') && event.data) {
            const completedCount = event.data.completed_count ?? 0;
            const total = event.data.total ?? progressRef.current[runId]?.total ?? 0;
            progressRef.current[runId] = { current: completedCount, total };
            setSseProgress({ ...progressRef.current });
          }
          if (TERMINAL_EVENTS.has(event.type)) {
            delete progressRef.current[runId];
            setSseProgress({ ...progressRef.current });
            refetch();
          }
        } catch {
          // ignore
        }
      },
      onError: () => {
        delete progressRef.current[runId];
        setSseProgress({ ...progressRef.current });
      },
    });
  }, [refetch]);

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
      startSSE(id);
    } else {
      startSSE(id);
    }
  }, [startSSE, executeMutation]);

  const handleGenerateReport = useCallback(async (runId: string) => {
    try {
      await generateReportMutation.mutateAsync(runId);
      message.success('报告已生成，可在报告页查看');
    } catch {
      message.error('报告生成失败');
    }
  }, [generateReportMutation]);

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
      title: '进度', width: 140,
      render: (_, r: TestRun) => {
        const sse = sseProgress[r.id];
        if (sse && sse.total > 0) {
          const pct = Math.round((sse.current / sse.total) * 100);
          return <Progress percent={pct} size="small" format={() => `${sse.current}/${sse.total}`} />;
        }
        const p = (r as any).progress;
        if (p != null) return <Progress percent={Math.round(p)} size="small" />;
        if (r.status === 'running') return <Spin size="small" />;
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
              <Button size="small" icon={<FileTextOutlined />} onClick={() => handleGenerateReport(record.id)} loading={generateReportMutation.isPending}>生成报告</Button>
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
