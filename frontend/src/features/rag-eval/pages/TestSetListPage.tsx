/**
 * 测试集列表页
 * 路由: /rag-eval/test-sets
 */

import { Button, Input, Modal, Form, Typography, Popconfirm } from 'antd';
import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { useTestSetList, type CreateFormValues } from '../hooks/useTestSetList';
import { TestSetListTable } from '../components/TestSetListTable';

const { Title } = Typography;

export default function TestSetListPage() {
  const {
    testSets,
    loading,
    total,
    page,
    pageSize,
    keyword,
    sourceType,
    createModalVisible,
    setCreateModalVisible,
    setPagination,
    setFilters,
    handleCreate,
    handleDelete,
    handleBatchDelete,
  } = useTestSetList();

  const [form] = Form.useForm<CreateFormValues>();
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  const onFinish = (values: CreateFormValues) => {
    handleCreate(values, () => form.resetFields());
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>测试集管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>
          创建测试集
        </Button>
      </div>

      <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
        <Input
          placeholder="按名称搜索"
          prefix={<SearchOutlined />}
          style={{ width: 240 }}
          value={keyword}
          onChange={e => setFilters(e.target.value, sourceType)}
          allowClear
        />
        {selectedRowKeys.length > 0 && (
          <Popconfirm title={`确认删除 ${selectedRowKeys.length} 个测试集？`} onConfirm={() => handleBatchDelete(selectedRowKeys as string[])}>
            <Button danger>
              批量删除 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        )}
      </div>

      <TestSetListTable
        testSets={testSets}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        setPagination={setPagination}
        onDelete={handleDelete}
        selectedRowKeys={selectedRowKeys}
        onSelectChange={setSelectedRowKeys}
      />

      <Modal
        title="创建测试集"
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        onOk={() => form.submit()}
      >
        <Form<CreateFormValues>
          form={form}
          layout="vertical"
          onFinish={onFinish}
        >
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入测试集名称' }]}
          >
            <Input placeholder="请输入名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="请输入描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}