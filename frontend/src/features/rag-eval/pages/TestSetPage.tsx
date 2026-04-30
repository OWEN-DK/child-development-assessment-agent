import { useState, useCallback } from 'react';
import {
  Space, Button, Card, Modal, message, Typography, Spin, Alert, Form, Input, Row, Col, Empty, Tag, Popconfirm,
} from 'antd';
import { PlusOutlined, DeleteOutlined, ExportOutlined, EditOutlined, SwapOutlined } from '@ant-design/icons';
import type { TestSet } from '@entities/rag-eval';
import { useTestSets, useCreateTestSet, useUpdateTestSet, useDeleteTestSet, useExportTestSet } from '../hooks/useTestSets';
import { CaseTransferModal } from '../components/test-set/CaseTransferModal';
import { formatTimestamp } from '@entities/rag-eval';

const { Title, Text, Paragraph } = Typography;

export function TestSetPage() {
  const { data, isLoading, isError } = useTestSets();
  const createMutation = useCreateTestSet();
  const updateMutation = useUpdateTestSet();
  const deleteMutation = useDeleteTestSet();
  const exportMutation = useExportTestSet();

  const [modalOpen, setModalOpen] = useState(false);
  const [editingSet, setEditingSet] = useState<TestSet | null>(null);
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferSetId, setTransferSetId] = useState<string | null>(null);
  const [form] = Form.useForm<{ name: string; description?: string }>();

  const testSets = data || [];

  const handleCreate = useCallback(() => {
    setEditingSet(null);
    form.resetFields();
    setModalOpen(true);
  }, [form]);

  const handleEdit = useCallback((set: TestSet) => {
    setEditingSet(set);
    form.setFieldsValue({ name: set.name, description: set.description || undefined });
    setModalOpen(true);
  }, [form]);

  const handleSubmit = useCallback(async () => {
    const values = await form.validateFields();
    if (editingSet) {
      await updateMutation.mutateAsync({ id: editingSet.id, data: values });
      message.success('已更新');
    } else {
      await createMutation.mutateAsync(values);
      message.success('已创建');
    }
    setModalOpen(false);
    form.resetFields();
  }, [editingSet, form, createMutation, updateMutation]);

  const handleDelete = useCallback((id: string) => {
    Modal.confirm({
      title: '确认删除', content: '删除后不可恢复',
      onOk: async () => { await deleteMutation.mutateAsync(id); message.success('已删除'); },
    });
  }, [deleteMutation]);

  const handleExport = useCallback(async (id: string) => {
    await exportMutation.mutateAsync(id);
    message.success('导出已开始');
  }, [exportMutation]);

  const handleOpenTransfer = useCallback((id: string) => {
    setTransferSetId(id);
    setTransferOpen(true);
  }, []);

  if (isError) return <Alert type="error" message="加载测试集失败" showIcon />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>测试集管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建测试集</Button>
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
      ) : testSets.length === 0 ? (
        <Empty description="暂无测试集" />
      ) : (
        <Row gutter={[16, 16]}>
          {testSets.map((set: TestSet) => (
            <Col key={set.id} xs={24} sm={12} lg={8}>
              <Card hoverable size="small"
                actions={[
                  <EditOutlined key="edit" onClick={() => handleEdit(set)} />,
                  <SwapOutlined key="transfer" onClick={() => handleOpenTransfer(set.id)} />,
                  <ExportOutlined key="export" onClick={() => handleExport(set.id)} />,
                  <Popconfirm key="delete" title="确认删除？" onConfirm={() => handleDelete(set.id)}><DeleteOutlined style={{ color: '#ff4d4f' }} /></Popconfirm>,
                ]}>
                <Card.Meta
                  title={<Text strong>{set.name}</Text>}
                  description={
                    <div>
                      {set.description && <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 8 }}>{set.description}</Paragraph>}
                      <Space wrap size={[4, 4]}>
                        <Tag color="blue">{set.case_count} 个用例</Tag>
                      </Space>
                      <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 8 }}>{formatTimestamp(set.updated_at)}</Text>
                    </div>
                  }
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal title={editingSet ? '编辑测试集' : '新建测试集'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)}
        confirmLoading={createMutation.isPending || updateMutation.isPending}>
        <Form form={form} layout="vertical" size="small">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input placeholder="测试集名称" /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={3} placeholder="测试集描述（可选）" /></Form.Item>
        </Form>
      </Modal>

      <CaseTransferModal
        open={transferOpen}
        setId={transferSetId!}
        onClose={() => setTransferOpen(false)}
      />
    </div>
  );
}
