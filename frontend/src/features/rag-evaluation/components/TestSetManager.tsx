import React, { useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, message, Popconfirm, Tag } from 'antd';
import { PlusOutlined, DeleteOutlined, ExportOutlined, EditOutlined } from '@ant-design/icons';
import type { TestSet } from '@/api/rag-test/types';
import { createTestSet, updateTestSet, deleteTestSet, exportTestSet } from '@/api/rag-test';

interface TestSetManagerProps {
  testSets: TestSet[];
  loading: boolean;
  onRefresh: () => void;
}

const TestSetManager: React.FC<TestSetManagerProps> = ({ testSets, loading, onRefresh }) => {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editingSet, setEditingSet] = useState<TestSet | null>(null);
  const [form] = Form.useForm();

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await createTestSet(values);
      message.success('创建成功');
      setCreateModalOpen(false);
      form.resetFields();
      onRefresh();
    } catch {
      message.error('创建失败');
    }
  };

  const handleEdit = (record: TestSet) => {
    setEditingSet(record);
    setTimeout(() => {
      form.setFieldsValue({ name: record.name, description: record.description });
    }, 0);
    setCreateModalOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingSet) return;
    try {
      const values = await form.validateFields();
      await updateTestSet(editingSet.id, values);
      message.success('更新成功');
      setCreateModalOpen(false);
      setEditingSet(null);
      form.resetFields();
      onRefresh();
    } catch {
      message.error('更新失败');
    }
  };

  const handleDelete = async (setId: string) => {
    try {
      await deleteTestSet(setId);
      message.success('删除成功');
      onRefresh();
    } catch {
      message.error('删除失败');
    }
  };

  const handleExport = async (setId: string) => {
    try {
      const cases = await exportTestSet(setId);
      const blob = new Blob([JSON.stringify(cases, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `test_set_${setId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch {
      message.error('导出失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 120,
      render: (type: string) => {
        const map: Record<string, { color: string; text: string }> = {
          manual: { color: 'blue', text: '手动创建' },
          json_import: { color: 'green', text: 'JSON导入' },
          book_generated: { color: 'orange', text: '书籍生成' },
          mixed: { color: 'purple', text: '混合' },
        };
        const s = map[type] || { color: 'default', text: type };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '用例数',
      key: 'case_count',
      width: 100,
      render: (_: any, record: TestSet) => record.test_case_ids.length,
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: TestSet) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Button type="link" size="small" icon={<ExportOutlined />} onClick={() => handleExport(record.id)}>
            导出
          </Button>
          <Popconfirm title="确定删除此测试集？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingSet(null); form.resetFields(); setCreateModalOpen(true); }}>
          新建测试集
        </Button>
      </div>

      <Table
        dataSource={testSets}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
      />

      <Modal
        title={editingSet ? '编辑测试集' : '新建测试集'}
        open={createModalOpen}
        onOk={editingSet ? handleSaveEdit : handleCreate}
        onCancel={() => { setCreateModalOpen(false); setEditingSet(null); form.resetFields(); }}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default TestSetManager;
