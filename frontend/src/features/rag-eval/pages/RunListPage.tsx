/**
 * 运行历史列表页
 * 路由: /rag-eval/runs
 */

import { useMemo } from 'react';
import { Select, DatePicker, Space, Card, Button } from 'antd';
import { ReloadOutlined, PlayCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useRunManagement } from '../hooks/useRunManagement';
import { RunListTable } from '../components/RunListTable';
import { ProgressList } from '@/components/progress';
import type { RunTask } from '../hooks/useRunManagement';

const { RangePicker } = DatePicker;

export default function RunListPage() {
  const { runs, testSets, loading, runningTasks, filters, actions } = useRunManagement();

  const runProgressConfig = useMemo(() => ({
    title: '运行中的任务',
    getItemKey: (task: RunTask) => task.taskId,
    getItemTitle: (task: RunTask) => task.name || `测试运行 ${task.taskId.slice(0, 8)}`,
    getItemSubtitle: (task: RunTask) => task.totalTestCases ? `共 ${task.totalTestCases} 个用例` : undefined,
    showProgress: true,
    showStage: false,
    onCancel: async (task: RunTask) => {
      actions.handleCancel(task.taskId);
    },
    autoRemoveOnSuccess: true,
    autoRemoveOnCancel: true,
    successKeepSeconds: 3,
    cancelKeepSeconds: 3,
    failedKeepSeconds: 10,
  }), [actions]);

  return (
    <div>
      <Card
        title="运行任务"
        className="mb-4"
        extra={
          <Space>
            <Button
              icon={<PlayCircleOutlined />}
              type="primary"
              onClick={() => actions.handleRunTest()}
            >
              新建运行
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={actions.loadData}
              loading={loading}
              size="small"
            >
              刷新
            </Button>
          </Space>
        }
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <ProgressList<RunTask>
            config={runProgressConfig}
            tasks={runningTasks}
          />
        </Space>
      </Card>

      <Card
        title="运行历史"
        extra={
          <Space>
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
          </Space>
        }
      >
        <RunListTable
          runs={runs}
          testSets={testSets}
          loading={loading}
          onDelete={actions.handleDelete}
        />
      </Card>
    </div>
  );
}
