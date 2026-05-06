import { useState, useCallback } from 'react';
import {
  Space, Button, Select, Input, Modal, message, Table, Typography, Alert, Row, Col, Form, Upload, Tag, Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, DeleteOutlined, ImportOutlined, EditOutlined } from '@ant-design/icons';
import type { TestCase, TestCaseSource } from '@entities/rag-eval';
import { useTestCases, useCreateTestCase, useUpdateTestCase, useDeleteTestCase, useBatchDeleteTestCases, useImportTestCases } from '../hooks/useTestCases';
import { formatTimestamp } from '@entities/rag-eval';

const { Title, Text } = Typography;

export function TestCasePage() {
  const [sourceFilter, setSourceFilter] = useState<string | undefined>();
  const [searchText, setSearchText] = useState('');
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingCase, setEditingCase] = useState<TestCase | null>(null);
  const [form] = Form.useForm<Partial<TestCase>>();

  const { data, isLoading, isError } = useTestCases({
    source: sourceFilter,
    search: searchText || undefined,
  });

  const createMutation = useCreateTestCase();
  const updateMutation = useUpdateTestCase();
  const deleteMutation = useDeleteTestCase();
  const batchDeleteMutation = useBatchDeleteTestCases();
  const importMutation = useImportTestCases();

  const testCases = data?.items || [];

  const handleCreate = useCallback(() => {
    setEditingCase(null);
    form.resetFields();
    setEditModalOpen(true);
  }, [form]);

  const handleEdit = useCallback((record: TestCase) => {
    setEditingCase(record);
    form.setFieldsValue(record);
    setEditModalOpen(true);
  }, [form]);

  const handleSubmit = useCallback(async () => {
    const values = await form.validateFields();
    if (editingCase) {
      await updateMutation.mutateAsync({ id: editingCase.id, data: values });
      message.success('已更新');
    } else {
      await createMutation.mutateAsync(values as Pick<TestCase, 'query' | 'expected_knowledge_ids' | 'expected_keywords' | 'difficulty_level'> & Partial<Pick<TestCase, 'description' | 'answer_points_summary'>>);
      message.success('已创建');
    }
    setEditModalOpen(false);
    form.resetFields();
  }, [editingCase, form, createMutation, updateMutation]);

  const handleDelete = useCallback((id: string) => {
    Modal.confirm({
      title: '确认删除', content: '删除后不可恢复',
      onOk: async () => { await deleteMutation.mutateAsync(id); message.success('已删除'); },
    });
  }, [deleteMutation]);

  const handleBatchDelete = useCallback(async () => {
    if (selectedRowKeys.length === 0) return;
    Modal.confirm({
      title: '批量删除', content: `确定要删除选中的 ${selectedRowKeys.length} 个用例吗？`,
      onOk: async () => { await batchDeleteMutation.mutateAsync(selectedRowKeys); setSelectedRowKeys([]); message.success(`已删除 ${selectedRowKeys.length} 个用例`); },
    });
  }, [selectedRowKeys, batchDeleteMutation]);

  const handleImport = useCallback(async (file: File) => {
    await importMutation.mutateAsync({ file });
    message.success('导入成功');
    return false;
  }, [importMutation]);

  const columns: ColumnsType<TestCase> = [
    { title: '查询', dataIndex: 'query', width: 200, ellipsis: true },
    { title: '来源', dataIndex: 'source', width: 90,
      render: (s: TestCaseSource) => {
        const map: Record<string, { label: string; color: string }> = { manual: { label: '手动', color: 'blue' }, draft: { label: '草稿', color: 'green' }, import: { label: '导入', color: 'purple' } };
        return <Tag color={map[s]?.color}>{map[s]?.label || s}</Tag>;
      },
    },
    { title: '更新时间', dataIndex: 'updated_at', width: 140, render: (t: string) => <Text style={{ fontSize: 12 }}>{formatTimestamp(t)}</Text> },
    {
      title: '操作', width: 120,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="编辑"><Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} /></Tooltip>
          <Tooltip title="删除"><Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)} /></Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>测试用例管理</Title>
        <Space>
          <Upload accept=".json" showUploadList={false} beforeUpload={handleImport}><Button icon={<ImportOutlined />}>导入 JSON</Button></Upload>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建用例</Button>
        </Space>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={6}><Input.Search placeholder="搜索查询..." allowClear onSearch={setSearchText} style={{ width: '100%' }} /></Col>
        <Col xs={8} sm={4}><Select placeholder="来源" allowClear value={sourceFilter} onChange={setSourceFilter} options={[{ value: 'manual', label: '手动创建' }, { value: 'draft', label: '草稿导入' }, { value: 'import', label: '文件导入' }]} style={{ width: '100%' }} /></Col>
        <Col xs={24} sm={6}><Button danger icon={<DeleteOutlined />} disabled={selectedRowKeys.length === 0} onClick={handleBatchDelete} loading={batchDeleteMutation.isPending}>批量删除</Button></Col>
      </Row>

      {isError && <Alert type="error" message="加载测试用例失败" showIcon style={{ marginBottom: 16 }} />}

      <Table rowKey="id" columns={columns} dataSource={testCases} loading={isLoading} size="small"
        rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys as string[]) }}
        pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ x: 800 }} />

      <Modal title={editingCase ? '编辑用例' : '新建用例'} open={editModalOpen} onOk={handleSubmit} onCancel={() => setEditModalOpen(false)}
        confirmLoading={createMutation.isPending || updateMutation.isPending} width={640}>
        <Form form={form} layout="vertical" size="small">
          <Form.Item name="query" label="查询" rules={[{ required: true }]}><Input.TextArea rows={2} placeholder="输入测试查询..." /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="expected_keywords" label="预期关键词"><Select mode="tags" placeholder="输入关键词后回车" /></Form.Item>
          <Form.Item name="answer_points_summary" label="答案要点"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
