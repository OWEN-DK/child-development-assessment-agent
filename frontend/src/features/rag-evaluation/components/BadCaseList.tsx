import React, { useState, useMemo } from 'react';
import { Table, Tag, Select, Button, Modal, Descriptions, Empty } from 'antd';
import { EyeOutlined } from '@ant-design/icons';
import type { TestRun, TestResult } from '@/api/rag-test/types';

interface BadCaseListProps {
  testRuns: TestRun[];
}

export const BadCaseList: React.FC<BadCaseListProps> = ({ testRuns }) => {
  const [selectedRun, setSelectedRun] = useState<string | undefined>(
    testRuns.length > 0 ? testRuns[0].id : undefined
  );
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedCase, setSelectedCase] = useState<TestResult | null>(null);

  const currentRun = useMemo(
    () => testRuns.find(run => run.id === selectedRun),
    [testRuns, selectedRun]
  );

  const badCases = useMemo(() => {
    if (!currentRun?.test_results) return [];
    return currentRun.test_results
      .filter(result => result.f1_score < 0.7)
      .map(result => {
        let errorType = '未知';
        if (result.precision < 0.5) {
          errorType = '检索失败';
        } else if (result.mrr < 0.5) {
          errorType = '排序错误';
        }
        return { ...result, errorType };
      });
  }, [currentRun]);

  const handleViewDetail = (record: TestResult) => {
    setSelectedCase(record);
    setDetailVisible(true);
  };

  const columns = [
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
      title: '错误类型',
      dataIndex: 'errorType',
      key: 'errorType',
      width: 120,
      render: (type: string) => {
        const colorMap: Record<string, string> = {
          '检索失败': 'red',
          '排序错误': 'orange',
          '年龄不匹配': 'purple',
          '未知': 'default',
        };
        return <Tag color={colorMap[type] || 'default'}>{type}</Tag>;
      },
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
      title: 'F1-Score',
      dataIndex: 'f1_score',
      key: 'f1_score',
      width: 100,
      render: (v: number) => <Tag color="error">{v.toFixed(3)}</Tag>,
    },
    {
      title: 'MRR',
      dataIndex: 'mrr',
      key: 'mrr',
      width: 100,
      render: (v: number) => v.toFixed(3),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: TestResult) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => handleViewDetail(record)}
        >
          详情
        </Button>
      ),
    },
  ];

  if (testRuns.length === 0) {
    return (
      <Empty
        description="暂无测试运行记录"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <span style={{ marginRight: 8 }}>选择测试运行:</span>
        <Select
          style={{ width: 300 }}
          value={selectedRun}
          onChange={setSelectedRun}
          options={testRuns.map(run => ({
            label: `${run.name} (${new Date(run.created_at).toLocaleString()})`,
            value: run.id,
          }))}
        />
      </div>

      <Table
        columns={columns}
        dataSource={badCases}
        rowKey="test_case_id"
        pagination={{ pageSize: 10, showSizeChanger: true, showTotal: total => `共 ${total} 个Bad Case` }}
        locale={{ emptyText: '暂无Bad Case' }}
      />

      <Modal
        title="Bad Case 详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={700}
      >
        {selectedCase && (
          <Descriptions column={2} bordered>
            <Descriptions.Item label="测试用例ID" span={2}>
              {selectedCase.test_case_id}
            </Descriptions.Item>
            <Descriptions.Item label="查询" span={2}>
              {selectedCase.query}
            </Descriptions.Item>
            <Descriptions.Item label="Precision">
              {selectedCase.precision.toFixed(4)}
            </Descriptions.Item>
            <Descriptions.Item label="Recall">
              {selectedCase.recall.toFixed(4)}
            </Descriptions.Item>
            <Descriptions.Item label="F1-Score">
              {selectedCase.f1_score.toFixed(4)}
            </Descriptions.Item>
            <Descriptions.Item label="MRR">
              {selectedCase.mrr.toFixed(4)}
            </Descriptions.Item>
            <Descriptions.Item label="耗时(ms)">
              {selectedCase.execution_time_ms}
            </Descriptions.Item>
            <Descriptions.Item label="执行时间">
              {new Date(selectedCase.executed_at).toLocaleString()}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};
