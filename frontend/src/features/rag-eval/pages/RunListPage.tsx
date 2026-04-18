/**
 * 运行历史列表页
 * 路由: /rag-eval/runs
 */

import { Typography, Select, DatePicker } from 'antd';
import dayjs from 'dayjs';
import { useRunList } from '../hooks/useRunList';
import { RunListTable } from '../components/RunListTable';

const { RangePicker } = DatePicker;
const { Title } = Typography;

export default function RunListPage() {
  const { runs, testSets, loading, filters, actions } = useRunList();

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>运行历史</Title>
      </div>

      <div style={{ marginBottom: 16, display: 'flex', gap: 12 }}>
        <Select
          placeholder="状态筛选"
          style={{ width: 120 }}
          value={filters.statusFilter}
          onChange={filters.setStatusFilter}
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
          value={filters.testSetFilter}
          onChange={filters.setTestSetFilter}
          allowClear
          options={testSets.map(s => ({ label: s.name, value: s.id }))}
          showSearch
          filterOption={(input, option) =>
            (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
          }
        />
        <RangePicker
          placeholder={['开始日期', '结束日期']}
          value={filters.dateRange}
          onChange={dates => filters.setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
        />
      </div>

      <RunListTable
        runs={runs}
        testSets={testSets}
        loading={loading}
        onDelete={actions.handleDelete}
      />
    </div>
  );
}