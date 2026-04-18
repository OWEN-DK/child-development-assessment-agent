/**
 * 测试集详情页
 * 路由: /rag-eval/test-sets/:id
 */

import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  Descriptions,
  Table,
  Button,
  Input,
  Select,
  Tag,
  Space,
  Popconfirm,
  message,
  Typography,
  Spin,
  Modal,
  Form,
} from 'antd';
import { ArrowLeftOutlined, PlayCircleOutlined, PlusOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getTestSet, getTestCases, addCasesToSet, removeCasesFromSet, runAllTests } from '@/api/rag-test';
import type { TestSet, TestCase } from '@/api/rag-test';

const { Title } = Typography;

const DOMAIN_COLORS: Record<string, string> = {
  MOTOR_DEVELOPMENT: 'blue',
  SENSORY_INTEGRATION: 'green',
  COGNITIVE_DEVELOPMENT: 'orange',
  LANGUAGE_DEVELOPMENT: 'purple',
  SOCIAL_EMOTIONAL: 'cyan',
};

export default function TestSetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [testSet, setTestSet] = useState<TestSet | null>(null);
  const [cases, setCases] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [domainFilter, setDomainFilter] = useState<string | null>(null);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [runModalVisible, setRunModalVisible] = useState(false);
  const [runName, setRunName] = useState('');
  const [availableCases, setAvailableCases] = useState<TestCase[]>([]);
  const [form] = Form.useForm();

  useEffect(() => {
    if (!id) return;
    loadData();
  }, [id]);

  const loadData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [set, allCases] = await Promise.all([getTestSet(id), getTestCases()]);
      setTestSet(set);
      // 通过 test_case_ids 过滤出属于当前测试集的用例
      const caseIds = new Set(set.test_case_ids || []);
      setCases(allCases.filter(c => caseIds.has(c.id)));
      // 可用用例：不在当前测试集中的用例
      setAvailableCases(allCases.filter(c => !caseIds.has(c.id)));
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveCase = async (caseId: string) => {
    if (!id) return;
    try {
      await removeCasesFromSet(id, [caseId]);
      message.success('已移除');
      loadData();
    } catch {
      message.error('移除失败');
    }
  };

  const handleRunTest = async () => {
    if (!id) return;
    try {
      const result = await runAllTests({ name: runName || `${testSet?.name}-运行`, test_set_ids: [id] });
      message.success('测试已启动');
      setRunModalVisible(false);
      navigate(`/rag-eval/runs/${result.run_id}`);
    } catch {
      message.error('启动失败');
    }
  };

  const handleAddCases = async (values: { case_ids: string[] }) => {
    if (!id) return;
    try {
      await addCasesToSet(id, values.case_ids);
      message.success('添加成功');
      setAddModalVisible(false);
      loadData();
    } catch {
      message.error('添加失败');
    }
  };

  const filteredCases = cases.filter(c => {
    if (keyword && !c.query.toLowerCase().includes(keyword.toLowerCase())) return false;
    if (domainFilter && c.domain !== domainFilter) return false;
    return true;
  });

  const domains = [...new Set(cases.map(c => c.domain))];

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!testSet) return <div>测试集不存在</div>;

  const columns = [
    {
      title: '查询语句',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
    },
    {
      title: '年龄',
      dataIndex: 'age',
      key: 'age',
      width: 80,
      render: (age: number) => `${age}月`,
    },
    {
      title: '领域',
      dataIndex: 'domain',
      key: 'domain',
      width: 120,
      render: (domain: string) => (
        <Tag color={DOMAIN_COLORS[domain] || 'default'}>{domain}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: { id: string }) => (
        <Popconfirm
          title="确定移除此用例？"
          onConfirm={() => handleRemoveCase(record.id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Link to="/rag-eval/test-sets">
          <Button type="link" icon={<ArrowLeftOutlined />}>返回</Button>
        </Link>
      </div>

      <Descriptions
        title={<Title level={4} style={{ margin: 0 }}>{testSet.name}</Title>}
        bordered
        column={3}
        extra={
          <Space>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => setRunModalVisible(true)}
              disabled={testSet.test_case_ids?.length === 0}
            >
              运行测试
            </Button>
            <Link to={`/rag-eval/test-sets/${id}/drafts`}>
              <Button>草稿审核</Button>
            </Link>
          </Space>
        }
      >
        <Descriptions.Item label="描述">{testSet.description || '-'}</Descriptions.Item>
        <Descriptions.Item label="来源类型">{testSet.source_type}</Descriptions.Item>
        <Descriptions.Item label="用例数">{testSet.test_case_ids?.length || 0}</Descriptions.Item>
        <Descriptions.Item label="创建时间">{dayjs(testSet.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
      </Descriptions>

      <div style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 16, display: 'flex', gap: 12, justifyContent: 'space-between' }}>
          <Space>
            <Input
              placeholder="搜索查询语句"
              prefix={<SearchOutlined />}
              style={{ width: 240 }}
              value={keyword}
              onChange={e => setKeyword(e.target.value)}
              allowClear
            />
            <Select
              placeholder="领域筛选"
              style={{ width: 160 }}
              value={domainFilter}
              onChange={setDomainFilter}
              allowClear
              options={domains.map(d => ({ label: d, value: d }))}
            />
          </Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddModalVisible(true)}>
            添加用例
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={filteredCases}
          rowKey="id"
          pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
        />
      </div>

      <Modal
        title="运行测试"
        open={runModalVisible}
        onCancel={() => setRunModalVisible(false)}
        onOk={handleRunTest}
      >
        <Form layout="vertical">
          <Form.Item label="运行名称（可选）">
            <Input value={runName} onChange={e => setRunName(e.target.value)} placeholder="留空则使用测试集名称" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="添加用例"
        open={addModalVisible}
        onCancel={() => setAddModalVisible(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleAddCases}>
          <Form.Item name="case_ids" label="选择用例" rules={[{ required: true, message: '请选择用例' }]}>
            <Select
              mode="multiple"
              placeholder="选择要添加的用例"
              options={availableCases.map(c => ({ label: c.query, value: c.id }))}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
