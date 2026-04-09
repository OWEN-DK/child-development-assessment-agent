import React from 'react';
import { Card, Row, Col, Table, Tag, Empty } from 'antd';
import type { TestRun } from '@/api/rag-test/types';

interface EvaluationReportProps {
  testRuns: TestRun[];
  latestRun: TestRun | null;
}

export const EvaluationReport: React.FC<EvaluationReportProps> = ({ latestRun }) => {
  if (!latestRun) {
    return (
      <Empty
        description="暂无测试运行记录"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  const metricsColumns = [
    {
      title: '指标',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '值',
      dataIndex: 'value',
      key: 'value',
      render: (value: number) => value.toFixed(4),
    },
    {
      title: '状态',
      dataIndex: 'passed',
      key: 'passed',
      render: (passed: boolean) => (
        <Tag color={passed ? 'success' : 'error'}>
          {passed ? '合格' : '不合格'}
        </Tag>
      ),
    },
  ];

  const metricsData = [
    {
      key: 'precision',
      name: 'Precision',
      value: latestRun.overall_precision,
      passed: latestRun.overall_precision >= 0.85,
    },
    {
      key: 'recall',
      name: 'Recall',
      value: latestRun.overall_recall,
      passed: latestRun.overall_recall >= 0.90,
    },
    {
      key: 'f1',
      name: 'F1-Score',
      value: latestRun.overall_f1,
      passed: latestRun.overall_f1 >= 0.70,
    },
    {
      key: 'mrr',
      name: 'MRR',
      value: latestRun.overall_mrr,
      passed: latestRun.overall_mrr >= 0.70,
    },
  ];

  const resultsColumns = [
    {
      title: '测试用例ID',
      dataIndex: 'test_case_id',
      key: 'test_case_id',
      width: 150,
    },
    {
      title: '查询',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
    },
    {
      title: 'Precision',
      dataIndex: 'precision',
      key: 'precision',
      width: 100,
      render: (v: number) => v.toFixed(3),
    },
    {
      title: 'Recall',
      dataIndex: 'recall',
      key: 'recall',
      width: 100,
      render: (v: number) => v.toFixed(3),
    },
    {
      title: 'F1',
      dataIndex: 'f1_score',
      key: 'f1_score',
      width: 100,
      render: (v: number) => v.toFixed(3),
    },
    {
      title: 'MRR',
      dataIndex: 'mrr',
      key: 'mrr',
      width: 100,
      render: (v: number) => v.toFixed(3),
    },
    {
      title: '耗时(ms)',
      dataIndex: 'execution_time_ms',
      key: 'execution_time_ms',
      width: 100,
    },
  ];

  return (
    <div>
      <Card title="测试运行信息" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <p><strong>运行ID:</strong> {latestRun.id}</p>
          </Col>
          <Col span={6}>
            <p><strong>名称:</strong> {latestRun.name}</p>
          </Col>
          <Col span={6}>
            <p><strong>状态:</strong> <Tag color={latestRun.status === 'completed' ? 'success' : 'processing'}>{latestRun.status}</Tag></p>
          </Col>
          <Col span={6}>
            <p><strong>完成时间:</strong> {latestRun.completed_at ? new Date(latestRun.completed_at).toLocaleString() : '-'}</p>
          </Col>
        </Row>
      </Card>

      <Card title="核心指标" style={{ marginBottom: 16 }}>
        <Table
          columns={metricsColumns}
          dataSource={metricsData}
          pagination={false}
          size="small"
        />
      </Card>

      <Card title="详细测试结果">
        <Table
          columns={resultsColumns}
          dataSource={latestRun.test_results || []}
          rowKey="test_case_id"
          pagination={{ pageSize: 10, showSizeChanger: true }}
          size="small"
        />
      </Card>
    </div>
  );
};
