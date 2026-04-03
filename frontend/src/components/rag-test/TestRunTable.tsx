import React from 'react';
import { Table, Tag, Button, Modal, Row, Col, Statistic, Typography } from 'antd';
import { BarChartOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TestRun } from '../../api/rag-test/types';
import { formatDateTime, formatPercentage } from '../../utils/formatters';

interface TestRunTableProps {
  testRuns: TestRun[];
  loading: boolean;
}

export const TestRunTable: React.FC<TestRunTableProps> = ({
  testRuns,
  loading,
}) => {
  const columns: ColumnsType<TestRun> = [
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
      render: (_, record: TestRun) => formatPercentage(record.overall_precision),
    },
    {
      title: '整体F1',
      key: 'f1',
      width: 100,
      render: (_, record: TestRun) => formatPercentage(record.overall_f1),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => formatDateTime(date),
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
            Modal.info({
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
                  <Typography.Title level={5}>测试用例详情</Typography.Title>
                  <Table
                    dataSource={record.test_results}
                    columns={[
                      { title: '查询', dataIndex: 'query', key: 'query', ellipsis: true },
                      { title: '准确率', dataIndex: 'precision', key: 'precision', render: (v: number) => formatPercentage(v) },
                      { title: 'F1', dataIndex: 'f1_score', key: 'f1', render: (v: number) => formatPercentage(v) },
                      { title: '状态', key: 'status', render: (_: unknown, r: any) => (
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

  return (
    <Table
      columns={columns}
      dataSource={testRuns}
      rowKey="id"
      loading={loading}
      pagination={{
        pageSize: 10,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 次测试运行`,
      }}
    />
  );
};
