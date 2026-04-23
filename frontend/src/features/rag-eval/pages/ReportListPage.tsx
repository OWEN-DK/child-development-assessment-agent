/**
 * 评估报告列表页
 * 路由: /rag-eval (Tab: 评估报告)
 *
 * 展示测试运行报告列表，支持筛选和查看详情
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table,
  Tag,
  Button,
  Space,
  Select,
  DatePicker,
  Typography,
  Spin,
  Popconfirm,
} from 'antd';
import { notification } from '@shared/lib/notification';
import {
  EyeOutlined,
  FileTextOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { getTestRuns, getTestSets, batchDeleteTestRuns } from '@/api/rag-test';
import type { TestRun, TestSet } from '@/api/rag-test';

const { Title } = Typography;
const { RangePicker } = DatePicker;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待运行', color: 'default' },
  running: { label: '运行中', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
  cancelled: { label: '已取消', color: 'default' },
};

export default function ReportListPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>();
  const [testSetFilter, setTestSetFilter] = useState<string>();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [runsData, setsData] = await Promise.all([
        getTestRuns(),
        getTestSets(),
      ]);
      setRuns(runsData);
      setTestSets(setsData);
    } catch {
      notification.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (selectedRowKeys.length === 0) return;
    try {
      await batchDeleteTestRuns(selectedRowKeys as string[]);
      notification.success(`已删除 ${selectedRowKeys.length} 个报告`);
      setSelectedRowKeys([]);
      loadData();
    } catch {
      notification.error('批量删除失败');
    }
  };

  const filteredRuns = runs.filter(r => {
    if (statusFilter && r.status !== statusFilter) return false;
    if (testSetFilter && r.test_set_id !== testSetFilter) return false;
    if (dateRange && r.completed_at) {
      const completed = dayjs(r.completed_at);
      if (completed.isBefore(dateRange[0]) || completed.isAfter(dateRange[1])) return false;
    }
    return true;
  });

  const getTestSetName = (testSetId: string | undefined) => {
    if (!testSetId) return '-';
    const ts = testSets.find(s => s.id === testSetId);
    return ts?.name || '-';
  };

  const columns = [
    {
      title: '运行名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '测试集',
      key: 'test_set',
      width: 150,
      render: (_: unknown, record: TestRun) => getTestSetName(record.test_set_id),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={STATUS_MAP[status]?.color}>{STATUS_MAP[status]?.label || status}</Tag>
      ),
    },
    {
      title: '用例数',
      key: 'cases',
      width: 100,
      render: (_: unknown, record: TestRun) =>
        `${record.passed_test_cases || 0}/${record.total_test_cases || 0}`,
    },
    {
      title: 'F1',
      dataIndex: 'overall_f1',
      key: 'overall_f1',
      width: 80,
      render: (v: number) => v != null ? v.toFixed(2) : '-',
    },
    {
      title: '完成时间',
      dataIndex: 'completed_at',
      key: 'completed_at',
      width: 160,
      render: (val: string) => val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: TestRun) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            disabled={record.status !== 'completed'}
            onClick={() => navigate(`/rag-eval/reports/${record.id}`)}
          >
            查看
          </Button>
          <Button
            type="link"
            size="small"
            icon={<FileTextOutlined />}
            disabled={record.status !== 'completed'}
            onClick={() => navigate(`/rag-eval/reports/${record.id}`)}
          >
            报告
          </Button>
        </Space>
      ),
    },
  ];

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>评估报告</Title>
        {selectedRowKeys.length > 0 && (
          <Popconfirm title={`确认删除 ${selectedRowKeys.length} 个报告？`} onConfirm={handleDelete}>
            <Button danger icon={<DeleteOutlined />}>
              批量删除 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        )}
      </div>

      <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
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
        <Tag>共 {filteredRuns.length} 条</Tag>
      </div>

      <Table
        columns={columns}
        dataSource={filteredRuns}
        rowKey="id"
        rowSelection={{
          selectedRowKeys,
          onChange: keys => setSelectedRowKeys(keys),
        }}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
        locale={{ emptyText: '暂无报告，请先运行测试' }}
      />
    </div>
  );
}
