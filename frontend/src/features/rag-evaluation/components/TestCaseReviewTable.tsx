import React, { useState } from 'react';
import { Table, Button, Space, Tag, Popconfirm, message, Modal, Form, Input, Select, InputNumber } from 'antd';
import { CheckOutlined, CloseOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import type { TestCaseDraft } from '@/api/rag-test/types';
import { reviewDraft, updateDraft, importDrafts } from '@/api/rag-test';

const { TextArea } = Input;

interface TestCaseReviewTableProps {
  drafts: TestCaseDraft[];
  loading: boolean;
  onRefresh: () => void;
  onDelete?: (draftId: string) => void;
  onBatchDelete?: (draftIds: string[]) => void;
}

const TestCaseReviewTable: React.FC<TestCaseReviewTableProps> = ({ drafts, loading, onRefresh, onDelete, onBatchDelete }) => {
  const [editingDraft, setEditingDraft] = useState<TestCaseDraft | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [form] = Form.useForm();

  console.log('[TestCaseReviewTable] 接收到草稿数据:', drafts.length, '条');
  console.log('[TestCaseReviewTable] 草稿数据详情:', drafts);

  const handleReview = async (draftId: string, action: 'reviewed' | 'rejected') => {
    try {
      await reviewDraft(draftId, action);
      message.success(action === 'reviewed' ? '已通过' : '已拒绝');
      onRefresh();
    } catch {
      message.error('审核失败');
    }
  };

  const handleEdit = (record: TestCaseDraft) => {
    setEditingDraft(record);
    // 使用 setTimeout 确保 Modal 渲染后，并且 form 绑定完成后再设置值
    setTimeout(() => {
      form.setFieldsValue({
        query: record.query,
        age: record.age,
        domain: record.domain,
        description: record.description,
        expected_knowledge_ids: record.expected_knowledge_ids || [],
        expected_keywords: record.expected_keywords || [],
        answer_points: Array.isArray(record.answer_points) ? record.answer_points.join('\n') : '',
        professional_terms: Array.isArray(record.professional_terms) ? record.professional_terms.join('\n') : '',
        age_requirement: record.age_requirement,
      });
    }, 0);
    setEditModalOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingDraft) return;
    try {
      const values = await form.validateFields();
      const updates = {
        ...values,
        expected_knowledge_ids: values.expected_knowledge_ids || [],
        expected_keywords: values.expected_keywords || [],
        answer_points: values.answer_points ? values.answer_points.split('\n').filter(Boolean) : [],
        professional_terms: values.professional_terms ? values.professional_terms.split('\n').filter(Boolean) : [],
      };
      await updateDraft(editingDraft.id, updates);
      message.success('保存成功');
      setEditModalOpen(false);
      onRefresh();
    } catch {
      message.error('保存失败');
    }
  };

  const handleBatchImport = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要导入的草稿');
      return;
    }
    try {
      const result = await importDrafts(selectedRowKeys as string[]);
      message.success(`成功导入 ${result.imported_count} 条`);
      setSelectedRowKeys([]);
      onRefresh();
    } catch {
      message.error('导入失败');
    }
  };

  const statusMap: Record<string, { color: string; text: string }> = {
    draft: { color: 'default', text: '草稿' },
    reviewed: { color: 'success', text: '已通过' },
    rejected: { color: 'error', text: '已拒绝' },
    imported: { color: 'processing', text: '已导入' },
  };

  const columns = [
    { title: '查询', dataIndex: 'query', key: 'query', ellipsis: true, width: 250 },
    { title: '年龄', dataIndex: 'age', key: 'age', width: 80 },
    {
      title: '领域',
      dataIndex: 'domain',
      key: 'domain',
      width: 120,
      render: (domain: string) => domain ? <Tag color="blue">{domain}</Tag> : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const s = statusMap[status] || { color: 'default', text: status };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: TestCaseDraft) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          {record.status === 'draft' && (
            <>
              <Popconfirm title="通过此草稿？" onConfirm={() => handleReview(record.id, 'reviewed')}>
                <Button type="link" size="small" icon={<CheckOutlined />} style={{ color: '#52c41a' }}>
                  通过
                </Button>
              </Popconfirm>
              <Popconfirm title="确定删除此草稿？" onConfirm={() => onDelete?.(record.id)}>
                <Button type="link" size="small" icon={<DeleteOutlined />} danger>
                  删除
                </Button>
              </Popconfirm>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Button type="primary" onClick={handleBatchImport} disabled={selectedRowKeys.length === 0}>
            批量导入选中 ({selectedRowKeys.length})
          </Button>
          {selectedRowKeys.length > 0 && (
            <Popconfirm
              title={`确定删除选中的 ${selectedRowKeys.length} 个草稿？`}
              onConfirm={() => {
                onBatchDelete?.(selectedRowKeys as string[]);
                setSelectedRowKeys([]);
              }}
              okText="确定"
              cancelText="取消"
            >
              <Button danger icon={<DeleteOutlined />}>
                批量删除 ({selectedRowKeys.length})
              </Button>
            </Popconfirm>
          )}
        </Space>
      </div>

      <Table
        dataSource={drafts}
        columns={columns}
        rowKey="id"
        loading={loading}
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys),
          getCheckboxProps: (record: TestCaseDraft) => ({
            disabled: record.status !== 'draft',
          }),
        }}
        pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
        size="small"
        bordered
      />

      <Modal
        title="编辑草稿"
        open={editModalOpen}
        onOk={handleSaveEdit}
        onCancel={() => setEditModalOpen(false)}
        width={700}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="query" label="查询" rules={[{ required: true, message: '请输入查询内容' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="age" label="年龄" rules={[{ required: true, message: '请输入年龄' }]}>
            <InputNumber min={0} max={18} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="domain" label="领域">
            <Select
              options={[
                { label: '粗大动作', value: '粗大动作' },
                { label: '精细动作', value: '精细动作' },
                { label: '语言发展', value: '语言发展' },
                { label: '认知能力', value: '认知能力' },
                { label: '社交情感', value: '社交情感' },
                { label: '感觉统合', value: '感觉统合' },
              ]}
              allowClear
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="expected_knowledge_ids" label="预期知识ID">
            <Select mode="tags" placeholder="输入预期知识ID" />
          </Form.Item>
          <Form.Item name="expected_keywords" label="预期关键词">
            <Select mode="tags" placeholder="输入预期关键词" />
          </Form.Item>
          <Form.Item name="answer_points" label="答题要点（每行一个）">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="professional_terms" label="专业术语（每行一个）">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="age_requirement" label="年龄要求">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default TestCaseReviewTable;
