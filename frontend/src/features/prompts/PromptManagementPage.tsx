import React, { useEffect, useState } from 'react';
import {
  Card,
  Select,
  Button,
  Table,
  Modal,
  Form,
  Input,
  Space,
  Tag,
  message,
  Tabs,
  Typography,
  Divider,
  Switch,
  Descriptions,
} from 'antd';
import {
  PlusOutlined,
  DiffOutlined,
  ExperimentOutlined,
  EyeOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { promptsApi } from '../../api/prompts';
import styles from './PromptManagementPage.module.scss';

const { TextArea } = Input;
const { Title, Text } = Typography;

const PROMPT_KEYS = [
  { value: 'rag_query_rewrite', label: '查询重写' },
  { value: 'synonym_expansion', label: '同义词扩展' },
  { value: 'metadata_extraction', label: '元数据提取' },
  { value: 'child_assessment', label: '儿童评估' },
  { value: 'validation', label: '数据校验' },
  { value: 'intensity_inference', label: '强度推断' },
  { value: 'category_inference', label: '类别推断' },
  { value: 'scoring', label: '评分' },
  { value: 'report_generation', label: '报告生成' },
  { value: 'test_case_generation', label: '测试用例生成' },
];

interface Version {
  id: string;
  version: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  variables: string[] | null;
  tags: string[] | null;
}

interface ABTest {
  id: string;
  prompt_key: string;
  name: string;
  is_active: boolean;
  variant_a_version: string;
  variant_b_version: string;
  variant_a_ratio: number;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export const PromptManagementPage: React.FC = () => {
  const [selectedPrompt, setSelectedPrompt] = useState<string>(
    PROMPT_KEYS[0].value
  );
  const [versions, setVersions] = useState<Version[]>([]);
  const [abTests, setAbTests] = useState<ABTest[]>([]);
  const [loading, setLoading] = useState(false);
  const [versionModalVisible, setVersionModalVisible] = useState(false);
  const [compareModalVisible, setCompareModalVisible] = useState(false);
  const [abTestModalVisible, setAbTestModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [_selectedVersion, _setSelectedVersion] = useState<Version | null>(null);
  const [versionDetail, setVersionDetail] = useState<any>(null);
  const [compareData, setCompareData] = useState<any>(null);
  const [compareVersions, setCompareVersions] = useState<string[]>([]);
  const [form] = Form.useForm();
  const [abTestForm] = Form.useForm();
  const [_compareForm] = Form.useForm();

  useEffect(() => {
    loadVersions();
    loadABTests();
  }, [selectedPrompt]);

  const loadVersions = async () => {
    setLoading(true);
    try {
      const data = await promptsApi.listVersions(selectedPrompt);
      setVersions(data);
    } catch (error) {
      message.error('加载版本列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadABTests = async () => {
    try {
      const data = await promptsApi.listABTests(selectedPrompt);
      setAbTests(data);
    } catch (error) {
      message.error('加载 A/B 测试失败');
    }
  };

  const handleCreateVersion = async (values: any) => {
    try {
      await promptsApi.createVersion(selectedPrompt, {
        content: values.content,
        description: values.description,
        created_by: values.created_by,
        variables: values.variables
          ? values.variables.split(',').map((v: string) => v.trim())
          : undefined,
        tags: values.tags
          ? values.tags.split(',').map((v: string) => v.trim())
          : undefined,
        fallback: values.fallback,
      });
      message.success('版本已创建');
      setVersionModalVisible(false);
      form.resetFields();
      loadVersions();
    } catch (error) {
      message.error('创建版本失败');
    }
  };

  const handleViewDetail = async (version: Version) => {
    try {
      const detail = await promptsApi.getVersionDetail(
        selectedPrompt,
        version.version
      );
      setVersionDetail(detail);
      setDetailModalVisible(true);
    } catch (error) {
      message.error('加载版本详情失败');
    }
  };

  const handleCompare = async () => {
    if (compareVersions.length !== 2) {
      message.warning('请选择两个版本进行对比');
      return;
    }
    try {
      const diff = await promptsApi.compareVersions(
        selectedPrompt,
        compareVersions[0],
        compareVersions[1]
      );
      setCompareData(diff);
      setCompareModalVisible(true);
    } catch (error) {
      message.error('对比失败');
    }
  };

  const handleCreateABTest = async (values: any) => {
    try {
      await promptsApi.createABTest({
        name: values.name,
        variant_a_version: values.variant_a_version,
        variant_b_version: values.variant_b_version,
        variant_a_ratio: values.variant_a_ratio / 100,
      });
      message.success('A/B 测试已创建');
      setAbTestModalVisible(false);
      abTestForm.resetFields();
      loadABTests();
    } catch (error) {
      message.error('创建 A/B 测试失败');
    }
  };

  const handleToggleABTest = async (testId: string, isActive: boolean) => {
    try {
      await promptsApi.toggleABTest(testId, isActive);
      message.success(`A/B 测试已${isActive ? '启用' : '禁用'}`);
      loadABTests();
    } catch (error) {
      message.error('切换状态失败');
    }
  };

  const versionColumns: ColumnsType<Version> = [
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 100,
      render: (text) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '创建人',
      dataIndex: 'created_by',
      key: 'created_by',
      width: 100,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text) => new Date(text).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record)}
          >
            查看
          </Button>
        </Space>
      ),
    },
  ];

  const abTestColumns: ColumnsType<ABTest> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '版本 A',
      dataIndex: 'variant_a_version',
      key: 'variant_a_version',
      render: (text) => <Tag color="green">{text}</Tag>,
    },
    {
      title: '版本 B',
      dataIndex: 'variant_b_version',
      key: 'variant_b_version',
      render: (text) => <Tag color="orange">{text}</Tag>,
    },
    {
      title: '流量分配',
      dataIndex: 'variant_a_ratio',
      key: 'variant_a_ratio',
      width: 120,
      render: (ratio) => `${(ratio * 100).toFixed(0)}% : ${((1 - ratio) * 100).toFixed(0)}%`,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (active, record) => (
        <Switch
          checked={active}
          onChange={(checked) => handleToggleABTest(record.id, checked)}
          size="small"
        />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text) => new Date(text).toLocaleString('zh-CN'),
    },
  ];

  const tabItems = [
    {
      key: 'versions',
      label: '版本管理',
      children: (
        <>
          <div className={styles.toolbar}>
            <Space>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setVersionModalVisible(true)}
              >
                新建版本
              </Button>
              <Button
                icon={<DiffOutlined />}
                onClick={() => setCompareVersions([])}
                disabled={versions.length < 2}
              >
                对比版本
              </Button>
            </Space>
          </div>
          {compareVersions.length < 2 && versions.length >= 2 && (
            <Card size="small" className={styles.compareSelect}>
              <Space>
                <Text>选择版本 1:</Text>
                <Select
                  style={{ width: 150 }}
                  placeholder="选择版本"
                  onChange={(v) =>
                    setCompareVersions((prev) => [v, prev[1]].filter(Boolean))
                  }
                  options={versions.map((v) => ({
                    label: v.version,
                    value: v.version,
                  }))}
                />
                <Text>选择版本 2:</Text>
                <Select
                  style={{ width: 150 }}
                  placeholder="选择版本"
                  onChange={(v) =>
                    setCompareVersions((prev) => [prev[0], v].filter(Boolean))
                  }
                  options={versions.map((v) => ({
                    label: v.version,
                    value: v.version,
                  }))}
                />
                <Button type="primary" onClick={handleCompare}>
                  对比
                </Button>
              </Space>
            </Card>
          )}
          <Table
            columns={versionColumns}
            dataSource={versions}
            rowKey="id"
            loading={loading}
            pagination={false}
          />
        </>
      ),
    },
    {
      key: 'abtest',
      label: (
        <span>
          <ExperimentOutlined /> A/B 测试
        </span>
      ),
      children: (
        <>
          <div className={styles.toolbar}>
            <Button
              type="primary"
              icon={<ExperimentOutlined />}
              onClick={() => setAbTestModalVisible(true)}
              disabled={versions.length < 2}
            >
              创建 A/B 测试
            </Button>
          </div>
          <Table
            columns={abTestColumns}
            dataSource={abTests}
            rowKey="id"
            pagination={false}
          />
        </>
      ),
    },
  ];

  return (
    <div className={styles.container}>
      <Title level={3}>提示词管理</Title>

      <Card className={styles.selectorCard}>
        <Space>
          <Text strong>选择提示词:</Text>
          <Select
            style={{ width: 200 }}
            value={selectedPrompt}
            onChange={setSelectedPrompt}
            options={PROMPT_KEYS}
          />
        </Space>
      </Card>

      <Tabs items={tabItems} defaultActiveKey="versions" />

      <Modal
        title="新建版本"
        open={versionModalVisible}
        onCancel={() => setVersionModalVisible(false)}
        footer={null}
        width={700}
      >
        <Form form={form} layout="vertical" onFinish={handleCreateVersion}>
          <Form.Item
            name="content"
            label="提示词内容"
            rules={[{ required: true, message: '请输入提示词内容' }]}
          >
            <TextArea rows={12} placeholder="输入提示词内容..." />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="版本描述" />
          </Form.Item>
          <Form.Item name="created_by" label="创建人">
            <Input placeholder="创建人" />
          </Form.Item>
          <Form.Item name="variables" label="变量列表">
            <Input placeholder="逗号分隔，如: query, age" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Input placeholder="逗号分隔，如: rag, retrieval" />
          </Form.Item>
          <Form.Item name="fallback" label="兜底提示词">
            <TextArea rows={3} placeholder="兜底提示词" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" icon={<SaveOutlined />}>
              创建版本
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="版本详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={800}
      >
        {versionDetail && (
          <>
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="提示词">
                {versionDetail.prompt_key}
              </Descriptions.Item>
              <Descriptions.Item label="版本">
                {versionDetail.version}
              </Descriptions.Item>
              <Descriptions.Item label="创建人">
                {versionDetail.created_by || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {versionDetail.created_at
                  ? new Date(versionDetail.created_at).toLocaleString('zh-CN')
                  : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="描述" span={2}>
                {versionDetail.description || '-'}
              </Descriptions.Item>
              {versionDetail.variables && (
                <Descriptions.Item label="变量" span={2}>
                  {versionDetail.variables.join(', ')}
                </Descriptions.Item>
              )}
              {versionDetail.tags && (
                <Descriptions.Item label="标签" span={2}>
                  {versionDetail.tags.join(', ')}
                </Descriptions.Item>
              )}
            </Descriptions>
            <Divider />
            <Title level={5}>提示词内容</Title>
            <pre className={styles.contentPreview}>
              {versionDetail.content}
            </pre>
          </>
        )}
      </Modal>

      <Modal
        title="版本对比"
        open={compareModalVisible}
        onCancel={() => setCompareModalVisible(false)}
        footer={null}
        width={900}
      >
        {compareData && (
          <>
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="版本 1">
                {compareData.version_1.version}
              </Descriptions.Item>
              <Descriptions.Item label="版本 2">
                {compareData.version_2.version}
              </Descriptions.Item>
              <Descriptions.Item label="字符变化">
                {compareData.diff.added_chars > 0 ? (
                  <Tag color="green">+{compareData.diff.added_chars}</Tag>
                ) : (
                  <Tag color="red">{compareData.diff.added_chars}</Tag>
                )}
              </Descriptions.Item>
            </Descriptions>
            <Divider />
            <div className={styles.diffContainer}>
              <div className={styles.diffColumn}>
                <Title level={5}>版本 {compareData.version_1.version}</Title>
                <pre className={styles.contentPreview}>
                  {compareData.version_1.content}
                </pre>
              </div>
              <div className={styles.diffColumn}>
                <Title level={5}>版本 {compareData.version_2.version}</Title>
                <pre className={styles.contentPreview}>
                  {compareData.version_2.content}
                </pre>
              </div>
            </div>
          </>
        )}
      </Modal>

      <Modal
        title="创建 A/B 测试"
        open={abTestModalVisible}
        onCancel={() => setAbTestModalVisible(false)}
        footer={null}
      >
        <Form
          form={abTestForm}
          layout="vertical"
          onFinish={handleCreateABTest}
        >
          <Form.Item
            name="name"
            label="测试名称"
            rules={[{ required: true, message: '请输入测试名称' }]}
          >
            <Input placeholder="如: 查询重写优化测试" />
          </Form.Item>
          <Form.Item
            name="variant_a_version"
            label="版本 A"
            rules={[{ required: true, message: '请选择版本 A' }]}
          >
            <Select
              placeholder="选择版本 A"
              options={versions.map((v) => ({
                label: v.version,
                value: v.version,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="variant_b_version"
            label="版本 B"
            rules={[{ required: true, message: '请选择版本 B' }]}
          >
            <Select
              placeholder="选择版本 B"
              options={versions.map((v) => ({
                label: v.version,
                value: v.version,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="variant_a_ratio"
            label="版本 A 流量比例 (%)"
            rules={[{ required: true, message: '请输入流量比例' }]}
            initialValue={50}
          >
            <Input type="number" min={0} max={100} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">
              创建测试
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
