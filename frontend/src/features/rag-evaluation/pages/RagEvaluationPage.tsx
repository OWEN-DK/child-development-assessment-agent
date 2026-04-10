import React, { useEffect, useState } from 'react';
import { Button, Tabs, message, Card, Row, Col, Statistic, Tag, Space, Tooltip } from 'antd';
import {
  PlayCircleOutlined,
  ImportOutlined,
  ExportOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  WarningOutlined,
  UnorderedListOutlined,
  QuestionCircleOutlined,
  BookOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import { useRagEvaluation } from '../hooks/useRagEvaluation';
import { TestCaseTable } from '../components/TestCaseTable';
import { EvaluationReport } from '../components/EvaluationReport';
import { BadCaseList } from '../components/BadCaseList';
import ImportJsonModal from '../components/ImportJsonModal';
import UploadDocumentModal from '../components/UploadDocumentModal';
import TestSetManager from '../components/TestSetManager';
import TestCaseReviewTable from '../components/TestCaseReviewTable';
import { ConfigDiffView } from '../../../components/config/ConfigDiffView';
import { useConfigStore } from '@/store/configStore';
import styles from './RagEvaluationPage.module.scss';
import type { TestRun } from '@/api/rag-test/types';

interface MetricCardProps {
  title: string;
  value: number | string;
  suffix?: string;
  status?: 'success' | 'warning' | 'error' | 'normal';
  threshold?: number;
  description?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, suffix, status = 'normal', threshold, description }) => {
  const isPass = threshold !== undefined && typeof value === 'number' ? value >= threshold : true;
  const tagColor = status === 'success' || isPass ? 'success' : status === 'error' || !isPass ? 'error' : 'warning';

  const titleElement = (
    <span>
      {title}
      {description && (
        <Tooltip title={description}>
          <QuestionCircleOutlined style={{ marginLeft: 4, fontSize: 12, color: '#999' }} />
        </Tooltip>
      )}
    </span>
  );

  return (
    <Card className={styles.metricCard}>
      <Statistic
        title={titleElement}
        value={value}
        suffix={suffix && <span>{suffix}</span>}
        valueStyle={{ color: isPass ? '#3f8600' : '#cf1322' }}
      />
      {threshold !== undefined && (
        <Tag color={tagColor} className={styles.statusTag}>
          {isPass ? '合格' : '不合格'}
        </Tag>
      )}
    </Card>
  );
};

export const RagEvaluationPage: React.FC = () => {
  const {
    testCases,
    testRuns,
    loading,
    loadTestCases,
    loadTestRuns,
    runAllTests,
    drafts,
    loadDrafts,
  } = useRagEvaluation();

  const { configFields, setRunning, setLastResult, loadConfig } = useConfigStore();

  const [activeTab, setActiveTab] = useState('overview');
  const [latestRun, setLatestRun] = useState<TestRun | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  useEffect(() => {
    loadTestCases();
    loadTestRuns();
    loadConfig();
    loadDrafts();
  }, [loadTestCases, loadTestRuns, loadConfig, loadDrafts]);

  useEffect(() => {
    if (testRuns.length > 0) {
      setLatestRun(testRuns[0]);
    }
  }, [testRuns]);

  const handleRunAllTests = async () => {
    try {
      setRunning(true);
      const result = await runAllTests(`Test Run ${new Date().toLocaleString()}`);
      setLastResult(result);
      message.success('测试运行完成');
      await loadTestRuns();
    } catch (err) {
      message.error('测试运行失败');
    } finally {
      setRunning(false);
    }
  };

  const handleImportTestCases = () => {
    setImportModalOpen(true);
  };

  const handleUploadDocument = () => {
    setUploadModalOpen(true);
  };

  const handleImportSuccess = () => {
    loadTestCases();
  };

  const handleUploadSuccess = () => {
    message.success('文档上传成功，可前往草稿审核');
    loadDrafts();
  };

  const handleExportReport = () => {
    message.info('导出报告功能开发中');
  };

  const metrics = latestRun
    ? {
        precision: latestRun.overall_precision,
        recall: latestRun.overall_recall,
        f1: latestRun.overall_f1,
        mrr: latestRun.overall_mrr,
        ndcg: latestRun.overall_ndcg,
        passed: latestRun.passed_test_cases,
        total: latestRun.total_test_cases,
      }
    : {
        precision: 0,
        recall: 0,
        f1: 0,
        mrr: 0,
        ndcg: 0,
        passed: 0,
        total: 0,
      };

  return (
    <div className={styles.container}>
      <div className={styles.leftPanel}>
        <div className={styles.header}>
          <h1 className={styles.title}>RAG 自动化评估</h1>
          <Space className={styles.actions}>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleRunAllTests}
              loading={loading}
            >
              运行所有测试
            </Button>
            <Button icon={<ImportOutlined />} onClick={handleImportTestCases}>
              JSON导入
            </Button>
            <Button icon={<BookOutlined />} onClick={handleUploadDocument}>
              书籍导入
            </Button>
            <Button icon={<ExportOutlined />} onClick={handleExportReport}>
              导出报告
            </Button>
          </Space>
        </div>

        <Row gutter={[16, 16]} className={styles.metricsRow}>
          <Col xs={24} sm={12} md={8} lg={6} xl={3}>
            <MetricCard
              title="Precision@3"
              value={metrics.precision.toFixed(4)}
              threshold={0.85}
              description="前3个检索结果中相关内容的比例，越高说明检索越准确"
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={6} xl={3}>
            <MetricCard
              title="Recall@3"
              value={metrics.recall.toFixed(4)}
              threshold={0.90}
              description="所有相关内容中出现在前3个结果的比例，越高说明召回越全面"
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={6} xl={3}>
            <MetricCard
              title="MRR"
              value={metrics.mrr.toFixed(4)}
              threshold={0.70}
              description="平均倒数排名，衡量相关结果出现位置的靠前程度，越高说明排序越合理"
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={6} xl={3}>
            <MetricCard
              title="NDCG@3"
              value={metrics.ndcg.toFixed(4)}
              threshold={0.80}
              description="归一化折损累积增益，综合衡量检索结果的排序质量"
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={6} xl={3}>
            <MetricCard
              title="F1-Score"
              value={metrics.f1.toFixed(4)}
              threshold={0.70}
              description="精确率和召回率的调和平均值，是检索性能的综合指标"
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={6} xl={3}>
            <MetricCard
              title="通过率"
              value={`${metrics.total > 0 ? ((metrics.passed / metrics.total) * 100).toFixed(1) : 0}%`}
              suffix={`/ ${metrics.total}`}
              description="测试用例中通过的比例，越高说明系统表现越好"
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={6} xl={3}>
            <MetricCard
              title="测试用例数"
              value={testCases.length}
              description="当前系统中总共的测试用例数量"
            />
          </Col>
        </Row>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          className={styles.tabs}
          items={[
            {
              key: 'overview',
              label: (
                <span>
                  <ExperimentOutlined />
                  评估概览
                </span>
              ),
              children: <EvaluationReport testRuns={testRuns} latestRun={latestRun} />,
            },
            {
              key: 'testcases',
              label: (
                <span>
                  <UnorderedListOutlined />
                  测试用例管理
                </span>
              ),
              children: (
                <TestCaseTable
                  testCases={testCases}
                  loading={loading}
                  onRefresh={loadTestCases}
                  onRunSingle={async (_caseId: string) => {
                    try {
                      message.loading('正在运行测试...', 0);
                      await runAllTests();
                      message.destroy();
                      message.success('测试运行完成');
                      await loadTestRuns();
                    } catch (err) {
                      message.destroy();
                      message.error('测试运行失败');
                    }
                  }}
                  onDelete={async (_caseId: string) => {
                    try {
                      message.loading('正在删除...', 0);
                      await loadTestCases();
                      message.destroy();
                      message.success('删除成功');
                    } catch (err) {
                      message.destroy();
                      message.error('删除失败');
                    }
                  }}
                />
              ),
            },
            {
              key: 'report',
              label: (
                <span>
                  <FileTextOutlined />
                  评估报告
                </span>
              ),
              children: <EvaluationReport testRuns={testRuns} latestRun={latestRun} />,
            },
            {
              key: 'badcases',
              label: (
                <span>
                  <WarningOutlined />
                  Bad Case 分析
                </span>
              ),
              children: <BadCaseList testRuns={testRuns} />,
            },
            {
              key: 'drafts',
              label: (
                <span>
                  <BookOutlined />
                  草稿审核
                </span>
              ),
              children: (
                <TestCaseReviewTable
                  drafts={drafts}
                  loading={loading}
                  onRefresh={loadDrafts}
                />
              ),
            },
            {
              key: 'testsets',
              label: (
                <span>
                  <DatabaseOutlined />
                  测试集管理
                </span>
              ),
              children: <TestSetManager testSets={[]} loading={false} onRefresh={() => {}} />,
            },
          ]}
        />

        {/* 配置版本对比 */}
        {latestRun && latestRun.config_version_id && latestRun.previous_config_version_id && latestRun.config_snapshot && (
          <div className={styles.diffSection}>
            <h3>配置版本对比</h3>
            <ConfigDiffView
              version1Snapshot={testRuns[1]?.config_snapshot || {}}
              version2Snapshot={latestRun.config_snapshot}
              configFields={configFields}
            />
          </div>
        )}
      </div>

      <ImportJsonModal
        open={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSuccess={handleImportSuccess}
      />
      <UploadDocumentModal
        open={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
};
