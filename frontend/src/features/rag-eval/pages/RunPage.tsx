import { useState, useCallback } from 'react';
import {
  Space, Button, Table, Modal, message, Typography, Alert, Row, Col, Select, Form, Input, Progress, Popconfirm,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, PlayCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import type { TestRun, TestRunStatus, TestSet } from '@entities/rag-eval';
import { useTestRuns, useCreateRun, useDeleteRun, useBatchDeleteRuns } from '../hooks/useTestRuns';
import { useTriggerEvaluation } from '../hooks/useMetrics';
import { useTestSets } from '../hooks/useTestSets';
import { useSSEProgress } from '../hooks/useSSEProgress';
import { StatusBadge } from '../components/common/StatusBadge';
import { getRunStatusLabel } from '@entities/rag-eval';
import { formatPercent, formatDuration, formatTimestamp } from '@entities/rag-eval';

const { Title, Text } = Typography;

export function RunPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [progressModalOpen, setProgressModalOpen] = useState(false);
  const [sseUrl, setSseUrl] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [form] = Form.useForm<{ name: string; test_set_ids: string[] }>();

  const { data, isLoading, isError, refetch } = useTestRuns({ status: statusFilter });
  const { data: testSetsData } = useTestSets();
  const createMutation = useCreateRun();
  const triggerEvalMutation = useTriggerEvaluation();
  const deleteMutation = useDeleteRun();
  const batchDeleteMutation = useBatchDeleteRuns();

  const { events: sseEvents, status: sseStatus } = useSSEProgress(sseUrl);

  const testSets = testSetsData?.items || [];

  const handleCreate = useCallback(async () => {
    const values = await form.validateFields();
    await createMutation.mutateAsync({
      name: values.name,
      testSetId: values.test_set_ids[0],
    });
    setCreateModalOpen(false);
    form.resetFields();
    message.success('运行已创建');
    refetch();
  }, [form, createMutation, refetch]);

  const handleStartEvaluation = useCallback(async (id: string) => {
    await triggerEvalMutation.mutateAsync(id);
    setActiveRunId(id);
    setSseUrl(`/rag/eval/runs/${id}/stream`);
    setProgressModalOpen(true);
  }, [triggerEvalMutation]);

  const handleDelete = useCallback((id: string) => {
    Modal.confirm({
      title: '确认删除', content: '删除后不可恢复',
      onOk: async () => { await deleteMutation.mutateAsync(id); message.success('已删除'); },
    });
  }, [deleteMutation]);

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
    { title: '进度', dataIndex: 'progress', width: 120, render: (p: number) => <Progress percent={Math.round(p)} size="small" /> },
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
          {(record.status === 'pending' || record.status === 'completed') && (
            <Button size="small" type="primary" icon={<PlayCircleOutlined />} onClick={() => handleStartEvaluation(record.id)}>评估</Button>
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

      <Modal title={`运行进度 ${activeRunId || ''}`} open={progressModalOpen} onCancel={() => { setProgressModalOpen(false); setSseUrl(null); refetch(); }} footer={null} width={500}>
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          {sseStatus === 'connecting' && <Typography.Text>连接中...</Typography.Text>}
          {sseStatus === 'connected' && <Typography.Text>运行中... ({sseEvents.length} 条事件)</Typography.Text>}
          {sseStatus === 'done' && <Alert type="success" message="运行已完成" showIcon />}
          {sseStatus === 'error' && <Alert type="error" message="连接异常" showIcon />}
        </div>
        {sseEvents.length > 0 && (
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            {sseEvents.map((event, i) => (
              <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                <Text code style={{ fontSize: 11 }}>{event.type}</Text>
                {event.type === 'progress' && event.data && (
                  <Progress percent={Math.round((event.data.progress as number) || 0)} size="small" />
                )}
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
