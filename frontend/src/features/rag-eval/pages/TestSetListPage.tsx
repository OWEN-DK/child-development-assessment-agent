/**
 * 测试集列表页
 * 路由: /rag-eval/test-sets
 */

import { Button, Input, Select, Modal, Form, Typography } from 'antd';
import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useTestSetList, type CreateFormValues } from '../hooks/useTestSetList';
import { TestSetListTable } from '../components/TestSetListTable';

const { Title } = Typography;

const SOURCE_TYPE_OPTIONS = [
  { value: 'BOOK_GENERATED', label: '书籍生成' },
  { value: 'JSON_IMPORTED', label: 'JSON导入' },
  { value: 'MANUAL', label: '手动创建' },
];

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
  } = useTestSetList();

  const [form] = Form.useForm<CreateFormValues>();

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

      <div style={{ marginBottom: 16, display: 'flex', gap: 12 }}>
        <Input
          placeholder="按名称搜索"
          prefix={<SearchOutlined />}
          style={{ width: 240 }}
          value={keyword}
          onChange={e => setFilters(e.target.value, sourceType)}
          allowClear
        />
        <Select
          placeholder="来源类型"
          style={{ width: 140 }}
          value={sourceType}
          onChange={val => setFilters(keyword, val)}
          allowClear
          options={SOURCE_TYPE_OPTIONS}
        />
      </div>

      <TestSetListTable
        testSets={testSets}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        setPagination={setPagination}
        onDelete={handleDelete}
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
          <Form.Item name="source_type" label="来源类型">
            <Select options={SOURCE_TYPE_OPTIONS} placeholder="请选择来源类型" allowClear />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}