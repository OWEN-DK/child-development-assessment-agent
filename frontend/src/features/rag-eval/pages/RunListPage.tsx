/**
 * 运行历史列表页
 * 路由: /rag-eval/runs
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Table,
  Button,
  Tag,
  Popconfirm,
  message,
  Typography,
  Select,
  Progress,
  DatePicker,
} from 'antd';
import { DeleteOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getTestRuns, batchDeleteTestRuns, getTestSets } from '@/api/rag-test';
import type { TestRun, TestSet } from '@/api/rag-test';

const { RangePicker } = DatePicker;

const { Title } = Typography;

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  running: { label: '运行中', color: 'blue', icon: <LoadingOutlined /> },
  completed: { label: '已完成', color: 'green', icon: <CheckCircleOutlined /> },
  failed: { label: '失败', color: 'red', icon: <CloseCircleOutlined /> },
};

export default function RunListPage() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [testSetFilter, setTestSetFilter] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [runsData, setsData] = await Promise.all([getTestRuns(), getTestSets()]);
      setRuns(runsData);
      setTestSets(setsData);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await batchDeleteTestRuns([id]);
      message.success('删除成功');
      loadData();
    } catch {
      message.error('删除失败');
    }
  };

  const getTestSetName = (testSetId?: string) => {
    if (!testSetId) return '-';
    const ts = testSets.find(s => s.id === testSetId);
    return ts?.name || testSetId.slice(0, 8);
  };

  const getTestSetIdFromRun = (run: TestRun): string | undefined => {
    return run.test_set_id;
  };

  const calcDuration = (run: TestRun) => {
    if (!run.completed_at || !run.created_at) return '-';
    const diff = dayjs(run.completed_at).diff(dayjs(run.created_at), 'second');
    return `${diff}s`;
  };

  const filteredRuns = runs.filter(r => {
    if (statusFilter && r.status !== statusFilter) return false;
    if (testSetFilter && getTestSetIdFromRun(r) !== testSetFilter) return false;
    if (dateRange) {
      const runDate = dayjs(r.created_at);
      if (runDate.isBefore(dateRange[0]) || runDate.isAfter(dateRange[1])) return false;
    }
    return true;
  });

  const columns = [
    {
      title: '运行名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: { id: string }) => (
        <Link to={`/rag-eval/runs/${record.id}`}>{text}</Link>
      ),
    },
    {
      title: '测试集',
      key: 'test_set',
      width: 200,
      render: (_: unknown, record: TestRun) => {
        const testSetId = getTestSetIdFromRun(record);
        const name = getTestSetName(testSetId);
        return testSetId ? <Link to={`/rag-eval/test-sets/${testSetId}`}>{name}</Link> : name;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config = STATUS_CONFIG[status] || { label: status, color: 'default', icon: null };
        return <Tag color={config.color} icon={config.icon}>{config.label}</Tag>;
      },
    },
    {
      title: '用例数',
      key: 'cases',
      width: 120,
      render: (_: unknown, record: TestRun) => {
        const total = record.total_test_cases || 0;
        const passed = record.passed_test_cases || 0;
        if (record.status === 'running') {
          return <Progress percent={total > 0 ? Math.round((passed / total) * 100) : 0} size="small" />;
        }
        return `${passed}/${total}`;
      },
    },
    {
      title: '耗时',
      key: 'duration',
      width: 100,
      render: (_: unknown, record: TestRun) => calcDuration(record),
    },
    {
      title: '开始时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: { id: string; status: string }) => (
        <Popconfirm
          title={record.status === 'running' ? '将终止正在运行的测试，确定删除？' : '确定删除此运行记录？'}
          onConfirm={() => handleDelete(record.id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>运行历史</Title>
      </div>

      <div style={{ marginBottom: 16, display: 'flex', gap: 12 }}>
        <Select
          placeholder="状态筛选"
          style={{ width: 120 }}
          value={statusFilter}
          onChange={setStatusFilter}
          allowClear
          options={[
            { label: '运行中', value: 'running' },
            { label: '已完成', value: 'completed' },
            { label: '失败', value: 'failed' },
          ]}
        />
        <Select
          placeholder="测试集筛选"
          style={{ width: 200 }}
          value={testSetFilter}
          onChange={setTestSetFilter}
          allowClear
          options={testSets.map(s => ({ label: s.name, value: s.id }))}
          showSearch
          filterOption={(input, option) =>
            (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
          }
        />
        <RangePicker
          placeholder={['开始日期', '结束日期']}
          value={dateRange}
          onChange={dates => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
        />
      </div>

      <Table
        columns={columns}
        dataSource={filteredRuns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
        locale={{ emptyText: '暂无运行记录，请先在测试集中运行测试' }}
      />
    </div>
  );
}
