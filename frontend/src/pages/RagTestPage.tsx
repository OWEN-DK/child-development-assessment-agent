import { useState, useEffect } from 'react';
import { 
  Card, Typography, Button, Table, Space, Modal, Form, Input, 
  InputNumber, Tag, Tabs, List, Descriptions,
  Popconfirm, Statistic, Row, Col, App
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined,
  CameraOutlined, RollbackOutlined, BarChartOutlined, HistoryOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';


import {
  TestCase, TestRun, KnowledgeSnapshot,
  getTestCases, createTestCase, updateTestCase, deleteTestCase,
  runAllTests, runSingleTest, getTestRuns,
  createSnapshot, getSnapshots, restoreSnapshot
} from '../api/client';
import styles from './RagTestPage.module.scss';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { TextArea } = Input;

interface TestCaseFormData {
  query: string;
  age: number;
  expected_keywords: string;
  description: string;
}

const RagTestPage = () => {
  const { modal, message } = App.useApp();
  const [activeTab, setActiveTab] = useState('cases');
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [testRuns, setTestRuns] = useState<TestRun[]>([]);
  const [snapshots, setSnapshots] = useState<KnowledgeSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [testRunning, setTestRunning] = useState(false);
  const [caseModalVisible, setCaseModalVisible] = useState(false);
  const [editingCase, setEditingCase] = useState<TestCase | null>(null);
  const [form] = Form.useForm<TestCaseFormData>();

  // 加载数据
  const loadTestCases = async () => {
    try {
      setLoading(true);
      const data = await getTestCases();
      setTestCases(data);
    } catch (e) {
      message.error('加载测试用例失败');
    } finally {
      setLoading(false);
    }
  };

  const loadTestRuns = async () => {
    try {
      setLoading(true);
      const data = await getTestRuns();
      setTestRuns(data);
    } catch (e) {
      message.error('加载测试运行记录失败');
    } finally {
      setLoading(false);
    }
  };

  const loadSnapshots = async () => {
    try {
      setLoading(true);
      const data = await getSnapshots();
      setSnapshots(data);
    } catch (e) {
      message.error('加载快照列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTestCases();
    loadTestRuns();
    loadSnapshots();
  }, []);

  // 测试用例相关操作
  const handleAddCase = () => {
    setEditingCase(null);
    form.resetFields();
    setCaseModalVisible(true);
  };

  const handleEditCase = (record: TestCase) => {
    setEditingCase(record);
    form.setFieldsValue({
      query: record.query,
      age: record.age,
      expected_keywords: record.expected_keywords.join(', '),
      description: record.description
    });
    setCaseModalVisible(true);
  };

  const handleDeleteCase = async (id: string) => {
    try {
      await deleteTestCase(id);
      message.success('删除成功');
      loadTestCases();
    } catch (e: any) {
      message.error(`删除失败: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleCaseModalOk = async () => {
    try {
      const values = await form.validateFields();
      const caseData = {
        query: values.query,
        age: values.age,
        expected_keywords: values.expected_keywords.split(',').map(k => k.trim()).filter(k => k),
        expected_knowledge_ids: [],
        description: values.description
      };

      if (editingCase) {
        await updateTestCase(editingCase.id, caseData);
        message.success('更新成功');
      } else {
        await createTestCase(caseData);
        message.success('创建成功');
      }

      setCaseModalVisible(false);
      loadTestCases();
    } catch (e: any) {
      message.error(`保存失败: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleRunSingleCase = async (record: TestCase) => {
    try {
      setTestRunning(true);
      const result = await runSingleTest(record.id);
      message.success('测试执行完成');
      // 显示结果弹窗
      modal.info({
        title: '测试结果',
        width: 800,
        content: (
          <div>
            <Descriptions bordered size="small" column={2}>
              <Descriptions.Item label="准确率">{(result.result.precision * 100).toFixed(2)}%</Descriptions.Item>
              <Descriptions.Item label="召回率">{(result.result.recall * 100).toFixed(2)}%</Descriptions.Item>
              <Descriptions.Item label="F1分数">{(result.result.f1_score * 100).toFixed(2)}%</Descriptions.Item>
              <Descriptions.Item label="MRR">{result.result.mrr.toFixed(4)}</Descriptions.Item>
              <Descriptions.Item label="执行时间" span={2}>{result.result.execution_time_ms}ms</Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 16 }}>
              <Title level={5}>检索结果</Title>
              <List
                dataSource={result.result.results}
                renderItem={(item) => (
                  <List.Item key={item.knowledge_id}>
                    <List.Item.Meta
                      title={
                        <Space>
                          <Tag color={item.expected ? 'green' : 'red'}>
                            {item.expected ? '预期' : '非预期'}
                          </Tag>
                          <span>排名: {item.rank} | 得分: {item.score.toFixed(4)}</span>
                        </Space>
                      }
                      description={<Paragraph ellipsis={{ rows: 2 }}>{item.content}</Paragraph>}
                    />
                  </List.Item>
                )}
              />
            </div>
          </div>
        )
      });
    } catch (e: any) {
      message.error(`测试执行失败: ${e.response?.data?.detail || e.message}`);
    } finally {
      setTestRunning(false);
    }
  };

  const handleRunAllTests = async () => {
    if (testCases.length === 0) {
      message.warning('请先创建测试用例');
      return;
    }

    try {
      setTestRunning(true);
      await runAllTests({
        name: `手动运行 - ${new Date().toLocaleString()}`,
        limit: 10
      });
      message.success('所有测试执行完成');
      loadTestRuns();
    } catch (e: any) {
      message.error(`测试执行失败: ${e.response?.data?.detail || e.message}`);
    } finally {
      setTestRunning(false);
    }
  };

  // 快照相关操作
  const handleCreateSnapshot = async () => {
    modal.confirm({
      title: '创建快照',
      content: '确定要创建当前知识库的快照吗？快照将保存当前索引和所有文档状态。',
      onOk: async () => {
        try {
          await createSnapshot({
            name: `快照 - ${new Date().toLocaleString()}`,
            description: '手动创建的快照'
          });
          message.success('快照创建成功');
          loadSnapshots();
        } catch (e: any) {
          message.error(`快照创建失败: ${e.response?.data?.detail || e.message}`);
        }
      }
    });
  };

  const handleRestoreSnapshot = async (snapshotId: string) => {
    modal.confirm({
      title: '恢复快照',
      content: '确定要恢复到该快照吗？当前知识库的所有改动将会丢失。',
      okText: '确定恢复',
      okType: 'danger',
      onOk: async () => {
        try {
          await restoreSnapshot(snapshotId);
          message.success('快照恢复已启动，后台处理中...');
          // 刷新状态
          setTimeout(() => {
            loadTestCases();
            loadTestRuns();
            loadSnapshots();
          }, 2000);
        } catch (e: any) {
          message.error(`快照恢复失败: ${e.response?.data?.detail || e.message}`);
        }
      }
    });
  };

  // 表格列定义
  const caseColumns: ColumnsType<TestCase> = [
    {
      title: '查询内容',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
      width: 250,
    },
    {
      title: '年龄',
      dataIndex: 'age',
      key: 'age',
      width: 80,
    },
    {
      title: '预期关键词',
      dataIndex: 'expected_keywords',
      key: 'expected_keywords',
      render: (keywords: string[]) => (
        <Space wrap>
          {keywords.map((kw, idx) => (
            <Tag key={idx}>{kw}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space size="small">
          <Button 
            type="link" 
            size="small" 
            icon={<PlayCircleOutlined />}
            onClick={() => handleRunSingleCase(record)}
            loading={testRunning}
          >
            运行
          </Button>
          <Button 
            type="link" 
            size="small" 
            icon={<EditOutlined />}
            onClick={() => handleEditCase(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该测试用例吗？"
            onConfirm={() => handleDeleteCase(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const runColumns: ColumnsType<TestRun> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const color = status === 'completed' ? 'green' : status === 'running' ? 'blue' : 'red';
        return <Tag color={color}>{status}</Tag>;
      },
    },
    {
      title: '用例总数',
      dataIndex: 'total_test_cases',
      key: 'total_test_cases',
      width: 100,
    },
    {
      title: '通过数',
      dataIndex: 'passed_test_cases',
      key: 'passed_test_cases',
      width: 100,
      render: (passed: number, record: TestRun) => (
        <span>{passed} / {record.total_test_cases}</span>
      ),
    },
    {
      title: '整体准确率',
      key: 'precision',
      width: 120,
      render: (_, record: TestRun) => `${(record.overall_precision * 100).toFixed(1)}%`,
    },
    {
      title: '整体F1',
      key: 'f1',
      width: 100,
      render: (_, record: TestRun) => `${(record.overall_f1 * 100).toFixed(1)}%`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Button 
          type="link" 
          size="small" 
          icon={<BarChartOutlined />}
          onClick={() => {
            modal.info({
              title: '测试运行详情',
              width: 900,
              content: (
                <div>
                  <Row gutter={16} style={{ marginBottom: 24 }}>
                    <Col span={6}>
                      <Statistic title="准确率" value={record.overall_precision * 100} suffix="%" precision={2} />
                    </Col>
                    <Col span={6}>
                      <Statistic title="召回率" value={record.overall_recall * 100} suffix="%" precision={2} />
                    </Col>
                    <Col span={6}>
                      <Statistic title="F1分数" value={record.overall_f1 * 100} suffix="%" precision={2} />
                    </Col>
                    <Col span={6}>
                      <Statistic title="MRR" value={record.overall_mrr} precision={4} />
                    </Col>
                  </Row>
                  <Title level={5}>测试用例详情</Title>
                  <Table
                    dataSource={record.test_results}
                    columns={[
                      { title: '查询', dataIndex: 'query', key: 'query', ellipsis: true },
                      { title: '准确率', dataIndex: 'precision', key: 'precision', render: v => `${(v*100).toFixed(1)}%` },
                      { title: 'F1', dataIndex: 'f1_score', key: 'f1', render: v => `${(v*100).toFixed(1)}%` },
                      { title: '状态', key: 'status', render: (_, r) => (
                        <Tag color={r.f1_score >= 0.7 ? 'green' : 'red'}>
                          {r.f1_score >= 0.7 ? '通过' : '失败'}
                        </Tag>
                      )},
                    ]}
                    rowKey="test_case_id"
                    pagination={false}
                    size="small"
                  />
                </div>
              )
            });
          }}
        >
          详情
        </Button>
      ),
    },
  ];

  const snapshotColumns: ColumnsType<KnowledgeSnapshot> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '文档数量',
      dataIndex: 'document_count',
      key: 'document_count',
      width: 100,
    },
    {
      title: '索引大小',
      dataIndex: 'index_size_bytes',
      key: 'index_size_bytes',
      width: 120,
      render: (bytes: number) => `${(bytes / 1024 / 1024).toFixed(2)} MB`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Popconfirm
          title="确定要恢复到该快照吗？当前数据会被覆盖。"
          onConfirm={() => handleRestoreSnapshot(record.id)}
          okText="确定"
          okType="danger"
          cancelText="取消"
        >
          <Button type="link" size="small" icon={<RollbackOutlined />}>
            恢复
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2}>知识库回撤测试</Title>
            <Text type="secondary">
              通过测试用例验证知识库变更的影响，确保检索质量稳定。支持测试用例管理、版本快照和结果对比。
            </Text>
          </div>

          <Space>
            <Button 
              type="primary" 
              icon={<PlusOutlined />} 
              onClick={handleAddCase}
            >
              新建测试用例
            </Button>
            <Button 
              icon={<PlayCircleOutlined />} 
              onClick={handleRunAllTests}
              loading={testRunning}
              disabled={testCases.length === 0}
            >
              运行所有测试
            </Button>
            <Button 
              icon={<CameraOutlined />} 
              onClick={handleCreateSnapshot}
            >
              创建快照
            </Button>
          </Space>

          <Row gutter={16}>
            <Col span={6}>
              <Statistic 
                title="测试用例总数" 
                value={testCases.length} 
                prefix={<HistoryOutlined />} 
              />
            </Col>
            <Col span={6}>
              <Statistic 
                title="测试运行次数" 
                value={testRuns.length} 
                prefix={<BarChartOutlined />} 
              />
            </Col>
            <Col span={6}>
              <Statistic 
                title="快照数量" 
                value={snapshots.length} 
                prefix={<CameraOutlined />} 
              />
            </Col>
            <Col span={6}>
              <Statistic 
                title="最近通过率" 
                value={testRuns[0] ? (testRuns[0].passed_test_cases / testRuns[0].total_test_cases * 100) : 0} 
                suffix="%"
                precision={1}
                valueStyle={{ color: testRuns[0] && (testRuns[0].passed_test_cases / testRuns[0].total_test_cases >= 0.8) ? '#3f8600' : '#cf1322' }}
              />
            </Col>
          </Row>
        </Space>
      </Card>

      <Card className={styles.contentCard}>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="测试用例管理" key="cases">
            <Table
              columns={caseColumns}
              dataSource={testCases}
              rowKey="id"
              loading={loading}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条测试用例`,
              }}
            />
          </TabPane>
          <TabPane tab="测试运行记录" key="runs">
            <Table
              columns={runColumns}
              dataSource={testRuns}
              rowKey="id"
              loading={loading}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 次测试运行`,
              }}
            />
          </TabPane>
          <TabPane tab="快照管理" key="snapshots">
            <Table
              columns={snapshotColumns}
              dataSource={snapshots}
              rowKey="id"
              loading={loading}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 个快照`,
              }}
            />
          </TabPane>
        </Tabs>
      </Card>

      {/* 测试用例编辑弹窗 */}
      <Modal
        title={editingCase ? '编辑测试用例' : '新建测试用例'}
        open={caseModalVisible}
        onOk={handleCaseModalOk}
        onCancel={() => setCaseModalVisible(false)}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            age: 3,
            expected_keywords: '',
          }}
        >
          <Form.Item
            name="query"
            label="查询内容"
            rules={[{ required: true, message: '请输入查询内容' }]}
          >
            <TextArea 
              rows={3} 
              placeholder="例如：3岁儿童怕高怎么办？"
            />
          </Form.Item>

          <Form.Item
            name="age"
            label="儿童年龄"
            rules={[{ required: true, message: '请输入年龄' }]}
          >
            <InputNumber min={0} max={18} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="expected_keywords"
            label="预期关键词（多个用逗号分隔）"
            rules={[{ required: true, message: '请输入预期关键词' }]}
            help="检索结果中包含这些关键词则认为是相关结果"
          >
            <Input placeholder="例如：前庭觉, 平衡训练, 感统游戏" />
          </Form.Item>

          <Form.Item
            name="description"
            label="描述（可选）"
          >
            <TextArea rows={2} placeholder="测试用例的说明信息" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default RagTestPage;
