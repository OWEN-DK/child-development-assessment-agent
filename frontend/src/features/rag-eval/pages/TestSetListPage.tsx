/**
 * 测试集列表页
 * 路由: /rag-eval/test-sets
 */

import { useEffect, useState } from 'react';
import {
  Table,
  Button,
  Input,
  Select,
  Tag,
  Space,
  Modal,
  Form,
  Popconfirm,
  message,
  Typography,
  Empty,
} from 'antd';
import { PlusOutlined, SearchOutlined, PlayCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { useTestSetStore, type SourceType } from '../hooks/useTestSetStore';

const { Title } = Typography;

const SOURCE_TYPE_MAP: Record<SourceType, { label: string; color: string }> = {
  BOOK_GENERATED: { label: '书籍生成', color: 'blue' },
  JSON_IMPORTED: { label: 'JSON导入', color: 'green' },
  MANUAL: { label: '手动创建', color: 'orange' },
};

const SOURCE_TYPE_OPTIONS = Object.entries(SOURCE_TYPE_MAP).map(([value, { label }]) => ({
  value,
  label,
}));

interface CreateFormValues {
  name: string;
  description?: string;
  source_type?: SourceType;
}

export default function TestSetListPage() {
  const navigate = useNavigate();
  const {
    testSets,
    loading,
    total,
    page,
    pageSize,
    keyword,
    sourceType,
    fetchTestSets,
    createTestSet: createSet,
    deleteTestSet: deleteSet,
    setPagination,
    setFilters,
  } = useTestSetStore();

  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [form] = Form.useForm<CreateFormValues>();

  useEffect(() => {
    fetchTestSets();
  }, []);

  const handleCreate = async (values: CreateFormValues) => {
    try {
      await createSet(values);
      message.success('创建成功');
      setCreateModalVisible(false);
      form.resetFields();
    } catch {
      message.error('创建失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteSet(id);
      message.success('删除成功');
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: { id: string }) => (
        <Link to={`/rag-eval/test-sets/${record.id}`}>{text}</Link>
      ),
    },
    {
      title: '来源类型',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 120,
      render: (type: SourceType) => (
        <Tag color={SOURCE_TYPE_MAP[type]?.color}>{SOURCE_TYPE_MAP[type]?.label || type}</Tag>
      ),
    },
    {
      title: '用例数',
      dataIndex: 'total_cases',
      key: 'total_cases',
      width: 80,
      sorter: (a: { total_cases: number }, b: { total_cases: number }) => a.total_cases - b.total_cases,
    },
    {
      title: '运行次数',
      dataIndex: 'run_count',
      key: 'run_count',
      width: 80,
    },
    {
      title: '最近运行',
      dataIndex: 'last_run_at',
      key: 'last_run_at',
      width: 160,
      render: (val: string | null) => (val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-'),
      sorter: (a: { last_run_at: string | null }, b: { last_run_at: string | null }) => {
        if (!a.last_run_at) return 1;
        if (!b.last_run_at) return -1;
        return dayjs(a.last_run_at).valueOf() - dayjs(b.last_run_at).valueOf();
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
      sorter: (a: { created_at: string }, b: { created_at: string }) =>
        dayjs(a.created_at).valueOf() - dayjs(b.created_at).valueOf(),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: { id: string; total_cases: number }) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<PlayCircleOutlined />}
            disabled={record.total_cases === 0}
            onClick={() => navigate(`/rag-eval/test-sets/${record.id}`)}
          >
            运行测试
          </Button>
          <Popconfirm
            title="确定删除此测试集？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
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

      <Table
        columns={columns}
        dataSource={testSets}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: ['10', '20', '50'],
          onChange: (p, ps) => setPagination(p, ps),
          showTotal: t => `共 ${t} 条`,
        }}
        locale={{
          emptyText: (
            <Empty
              description="暂无测试集，点击创建开始"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ),
        }}
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
          onFinish={handleCreate}
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
