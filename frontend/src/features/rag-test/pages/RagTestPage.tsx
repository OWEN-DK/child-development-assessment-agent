import React, { useState } from 'react';
import { Card, Typography, Button, Space, Tabs, Statistic, Row, Col, Form, App, List, Tag, Descriptions } from 'antd';
import {
  PlusOutlined, PlayCircleOutlined, CameraOutlined,
  BarChartOutlined, HistoryOutlined
} from '@ant-design/icons';
import { useRagTest } from '../hooks/useRagTest';
import { TestCaseTable } from '../../../components/rag-test/TestCaseTable';
import { TestRunTable } from '../../../components/rag-test/TestRunTable';
import { SnapshotTable } from '../../../components/rag-test/SnapshotTable';
import { TestCaseModal } from '../../../components/rag-test/TestCaseModal';
import { useModal } from '../../../hooks/useModal';
import type { TestCase } from '../../../api/rag-test/types';
import styles from './RagTestPage.module.scss';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;

interface TestCaseFormData {
  query: string;
  age: number;
  expected_keywords: string;
  description: string;
}

const RagTestPage: React.FC = () => {
  const { modal, message } = App.useApp();
  const [activeTab, setActiveTab] = useState('cases');
  const [form] = Form.useForm<TestCaseFormData>();

  const {
    testCases,
    testRuns,
    snapshots,
    loading,
    testRunning,
    handleAddCase,
    handleUpdateCase,
    handleDeleteCase,
    handleRunSingleCase: runSingleCaseFromHook,
    handleRunAllTests: runAllTestsFromHook,
    handleCreateSnapshot,
    handleRestoreSnapshot,
  } = useRagTest();

  const caseModal = useModal<TestCase>();

  const handleRunAllTests = async () => {
    if (testCases.length === 0) {
      message.warning('请先创建测试用例');
      return;
    }

    try {
      await runAllTestsFromHook();
      message.success('所有测试执行完成');
    } catch (e: any) {
      message.error(`测试执行失败: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleEditCase = (record: TestCase) => {
    form.setFieldsValue({
      query: record.query,
      age: record.age,
      expected_keywords: record.expected_keywords.join(', '),
      description: record.description
    });
    caseModal.open(record);
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

      if (caseModal.data) {
        await handleUpdateCase(caseModal.data.id, caseData);
        message.success('更新成功');
      } else {
        await handleAddCase(caseData);
        message.success('创建成功');
      }

      caseModal.close();
      form.resetFields();
    } catch (e: any) {
      message.error(`保存失败: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleRunSingleCaseFromTable = async (record: TestCase) => {
    try {
      const result = await runSingleCaseFromHook(record.id);
      message.success('测试执行完成');
      modal.info({
        title: '测试结果',
        width: 800,
        content: (
          <div>
            <Descriptions bordered size="small" column={2}>
              <Descriptions.Item label="准确率">{(result.precision * 100).toFixed(2)}%</Descriptions.Item>
              <Descriptions.Item label="召回率">{(result.recall * 100).toFixed(2)}%</Descriptions.Item>
              <Descriptions.Item label="F1分数">{(result.f1_score * 100).toFixed(2)}%</Descriptions.Item>
              <Descriptions.Item label="MRR">{result.mrr.toFixed(4)}</Descriptions.Item>
              <Descriptions.Item label="执行时间" span={2}>{result.execution_time_ms}ms</Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 16 }}>
              <Title level={5}>检索结果</Title>
              <List
                dataSource={result.results}
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
    }
  };

  const handleCreateSnapshotWithConfirm = async () => {
    modal.confirm({
      title: '创建快照',
      content: '确定要创建当前知识库的快照吗？快照将保存当前索引和所有文档状态。',
      onOk: async () => {
        try {
          await handleCreateSnapshot();
          message.success('快照创建成功');
        } catch (e: any) {
          message.error(`快照创建失败: ${e.response?.data?.detail || e.message}`);
        }
      }
    });
  };

  const handleRestoreSnapshotWithConfirm = async (snapshotId: string) => {
    modal.confirm({
      title: '恢复快照',
      content: '确定要恢复到该快照吗？当前知识库的所有改动将会丢失。',
      okText: '确定恢复',
      okType: 'danger',
      onOk: async () => {
        try {
          await handleRestoreSnapshot(snapshotId);
          message.success('快照恢复已启动，后台处理中...');
        } catch (e: any) {
          message.error(`快照恢复失败: ${e.response?.data?.detail || e.message}`);
        }
      }
    });
  };

  const latestRun = testRuns[0];
  const passRate = latestRun
    ? (latestRun.passed_test_cases / latestRun.total_test_cases * 100)
    : 0;

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2}>知识库回撤测试</Title>
            <Text type="secondary">
              通过测试用例验证知识库变更的影响，确保检索质量稳定。
            </Text>
          </div>

          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                form.resetFields();
                caseModal.open();
              }}
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
              onClick={handleCreateSnapshotWithConfirm}
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
                value={passRate}
                suffix="%"
                precision={1}
                valueStyle={{ color: passRate >= 80 ? '#3f8600' : '#cf1322' }}
              />
            </Col>
          </Row>
        </Space>
      </Card>

      <Card className={styles.contentCard}>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="测试用例管理" key="cases">
            <TestCaseTable
              testCases={testCases}
              loading={loading}
              testRunning={testRunning}
              onEdit={handleEditCase}
              onDelete={handleDeleteCase}
              onRun={handleRunSingleCaseFromTable}
            />
          </TabPane>
          <TabPane tab="测试运行记录" key="runs">
            <TestRunTable
              testRuns={testRuns}
              loading={loading}
            />
          </TabPane>
          <TabPane tab="快照管理" key="snapshots">
            <SnapshotTable
              snapshots={snapshots}
              loading={loading}
              onRestore={handleRestoreSnapshotWithConfirm}
            />
          </TabPane>
        </Tabs>
      </Card>

      <TestCaseModal
        visible={caseModal.isOpen}
        editingCase={caseModal.data}
        form={form}
        onOk={handleCaseModalOk}
        onCancel={caseModal.close}
      />
    </div>
  );
};

export default RagTestPage;
