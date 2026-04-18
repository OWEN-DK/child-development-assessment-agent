import { Table, Button, Tag, Popconfirm, Progress } from 'antd';
import { Link } from 'react-router-dom';
import { DeleteOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import type { TestRun, TestSet } from '@/api/rag-test';

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  running: { label: '运行中', color: 'blue', icon: <LoadingOutlined /> },
  completed: { label: '已完成', color: 'green', icon: <CheckCircleOutlined /> },
  failed: { label: '失败', color: 'red', icon: <CloseCircleOutlined /> },
};

interface RunListTableProps {
  runs: TestRun[];
  testSets: TestSet[];
  loading: boolean;
  onDelete: (id: string) => void;
}

export function RunListTable({ runs, testSets, loading, onDelete }: RunListTableProps) {
  const getTestSetName = (testSetId?: string) => {
    if (!testSetId) return '-';
    const ts = testSets.find(s => s.id === testSetId);
    return ts?.name || testSetId.slice(0, 8);
  };

  const calcDuration = (run: TestRun) => {
    if (!run.completed_at || !run.created_at) return '-';
    const diff = dayjs(run.completed_at).diff(dayjs(run.created_at), 'second');
    return `${diff}s`;
  };

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
        const testSetId = record.test_set_id;
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
          onConfirm={() => onDelete(record.id)}
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
    <Table
      columns={columns}
      dataSource={runs}
      rowKey="id"
      loading={loading}
      pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
      locale={{ emptyText: '暂无运行记录，请先在测试集中运行测试' }}
    />
  );
}