# Phase 3.5: 前端追踪视图

> **前置文档:** [04-data-processing.md](./05-phase-3-04-data-processing.md)
> **状态:** ⏳ 完全待实现
> **⚠️ 开发顺序说明**: 本 Task (05) 在实施顺序上早于后端 API (07-api-extension.md)。前端开发时应使用 Mock API 或本地 mock 数据，待后端 API 完成后替换。

## 前端依赖声明

LatencyChart 组件使用 `@antv/g2plot` 图表库。实施前需确认：

```bash
# 检查是否已安装
cd frontend && npm list @antv/g2plot

# 若未安装，执行
npm install @antv/g2plot
```

若项目已有其他图表库 (如 echarts/recharts)，可替换 LatencyChart 的底层实现，保持 API 接口不变。

## 开发顺序建议

```
后端优先路径 (推荐):
  07-api-extension (API 实现) → 05-dashboard (前端视图) → 06-trace-details (详情组件)

并行开发路径 (需 Mock):
  05-dashboard 使用 Mock API → 07-api-extension 完成后替换
  Mock 数据定义在 frontend/src/mocks/tracing.ts
```

## Mock API 示例
```ts
// frontend/src/mocks/tracing.ts
export const mockTraces = [
  {
    trace_id: "mock-trace-001",
    name: "assessment_run",
    user_id: "user-123",
    status: "success",
    total_tokens: 12500,
    total_duration_ms: 3200,
    total_cost: "0.1500",
    created_at: "2026-04-14T10:30:00Z",
    metadata: { model: "qwen3.5-plus" },
  },
];

export const mockSpans = [
  {
    span_id: "span-001",
    parent_span_id: null,
    name: "NodePre",
    duration_ms: 50,
    tokens: null,
    status: "success",
  },
  {
    span_id: "span-002",
    parent_span_id: "span-001",
    name: "llm_call_qwen3.5-plus",
    duration_ms: 1200,
    tokens: 800,
    status: "success",
    prompt_messages: [{ role: "user", content: "test query" }],
    completion_message: "test response",
    call_parameters: { provider: "dashscope", temperature: 0.7 },
  },
];
```

## 前端组件设计

在 `LLMMonitoringDashboard.tsx` 中新增 **"调用追踪 (Traces)"** 标签页。

### 新增组件清单

| 组件 | 文件 | 说明 |
|------|------|------|
| TraceListView | `TraceListView.tsx` | 追踪列表表格，支持排序和筛选 |
| TraceFilterBar | `TraceFilterBar.tsx` | 高级筛选器 |
| TraceDetailDrawer | `TraceDetailDrawer.tsx` | 追踪详情抽屉 |
| SpanTreeView | `SpanTreeView.tsx` | Span 层级树，支持展开/折叠 |
| SpanDetailPanel | `SpanDetailPanel.tsx` | Span 详情面板 |

---

## 实施任务

### Task 3.5.1: 实现 TraceListView

**Files:**
- Create: `frontend/src/components/monitoring/TraceListView.tsx`
- Test: `frontend/src/components/monitoring/__tests__/TraceListView.test.tsx`

- [ ] **Step 1: 定义组件**
```tsx
// frontend/src/components/monitoring/TraceListView.tsx
import React, { useEffect, useState } from 'react';
import { Table, Tag, Space, Button, Tooltip } from 'antd';
import { CopyOutlined, EyeOutlined } from '@ant-design/icons';
import { useTraceApi } from '../../api/tracing';
import type { Trace } from '../../types/tracing';

interface TraceListViewProps {
  filters?: Record<string, any>;
  onRowClick?: (traceId: string) => void;
}

const statusColorMap: Record<string, string> = {
  success: 'green',
  failed: 'red',
  partial: 'orange',
};

const TraceListView: React.FC<TraceListViewProps> = ({ filters, onRowClick }) => {
  const [data, setData] = useState<Trace[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const { fetchTraces } = useTraceApi();

  useEffect(() => {
    loadData();
  }, [filters, pagination.current, pagination.pageSize]);

  const loadData = async () => {
    setLoading(true);
    try {
      const result = await fetchTraces({
        page: pagination.current,
        page_size: pagination.pageSize,
        ...filters,
      });
      setData(result.items);
      setPagination(prev => ({ ...prev, total: result.total }));
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      sorter: true,
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '场景/名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '模型',
      dataIndex: 'metadata',
      key: 'model',
      render: (metadata: Record<string, any>) => metadata?.model || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={statusColorMap[status] || 'default'}>{status}</Tag>
      ),
    },
    {
      title: 'Token',
      dataIndex: 'total_tokens',
      key: 'total_tokens',
      sorter: true,
    },
    {
      title: '延迟',
      dataIndex: 'total_duration_ms',
      key: 'total_duration_ms',
      sorter: true,
      render: (ms: number) => `${ms}ms`,
    },
    {
      title: '成本',
      dataIndex: 'total_cost',
      key: 'total_cost',
      render: (cost: string) => cost ? `¥${cost}` : '未配置',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: Trace) => (
        <Space>
          <Tooltip title="查看详情">
            <Button icon={<EyeOutlined />} onClick={() => onRowClick?.(record.trace_id)} />
          </Tooltip>
          <Tooltip title="复制 Trace ID">
            <Button
              icon={<CopyOutlined />}
              onClick={() => navigator.clipboard.writeText(record.trace_id)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={data}
      rowKey="trace_id"
      loading={loading}
      pagination={pagination}
      onChange={(pag) => setPagination(prev => ({ ...prev, current: pag.current || 1 }))}
    />
  );
};

export default TraceListView;
```

- [ ] **Step 2: 运行测试验证通过**
Run: `cd frontend && npm run test -- TraceListView --watchAll=false`
Expected: PASS

---

### Task 3.5.2: 实现 TraceFilterBar

**Files:**
- Create: `frontend/src/components/monitoring/TraceFilterBar.tsx`

- [ ] **Step 1: 定义组件**
```tsx
// frontend/src/components/monitoring/TraceFilterBar.tsx
import React, { useState } from 'react';
import { Form, Select, DatePicker, Input, Button, Space } from 'antd';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';

const { RangePicker } = DatePicker;

interface TraceFilterBarProps {
  onFilter: (filters: Record<string, any>) => void;
}

const TraceFilterBar: React.FC<TraceFilterBarProps> = ({ onFilter }) => {
  const [form] = Form.useForm();

  const handleSearch = () => {
    const values = form.getFieldsValue();
    const filters: Record<string, any> = {};
    
    if (values.time_range) {
      filters.start_time = values.time_range[0]?.toISOString();
      filters.end_time = values.time_range[1]?.toISOString();
    }
    if (values.scenes?.length) filters.scenes = values.scenes;
    if (values.models?.length) filters.models = values.models;
    if (values.status) filters.status = values.status;
    if (values.user_id) filters.user_id = values.user_id;
    if (values.trace_id) filters.trace_id = values.trace_id;
    if (values.tags?.length) filters.tags = values.tags;
    
    onFilter(filters);
  };

  const handleReset = () => {
    form.resetFields();
    onFilter({});
  };

  return (
    <Form form={form} layout="inline">
      <Form.Item name="time_range" label="时间范围">
        <RangePicker showTime />
      </Form.Item>
      <Form.Item name="scenes" label="场景">
        <Select mode="multiple" placeholder="选择场景" style={{ width: 200 }}>
          <Select.Option value="assessment">评估</Select.Option>
          <Select.Option value="reporting">报告生成</Select.Option>
          <Select.Option value="retrieval">检索</Select.Option>
          <Select.Option value="test_execution">测试执行</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item name="models" label="模型">
        <Select mode="multiple" placeholder="选择模型" style={{ width: 200 }}>
          <Select.Option value="qwen3.5-plus">qwen3.5-plus</Select.Option>
          <Select.Option value="qwen3.5-turbo">qwen3.5-turbo</Select.Option>
          <Select.Option value="gpt-4o">gpt-4o</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item name="status" label="状态">
        <Select placeholder="选择状态" style={{ width: 120 }} allowClear>
          <Select.Option value="success">成功</Select.Option>
          <Select.Option value="failed">失败</Select.Option>
          <Select.Option value="partial">部分成功</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item name="user_id" label="用户 ID">
        <Input placeholder="搜索用户 ID" style={{ width: 150 }} />
      </Form.Item>
      <Form.Item name="trace_id" label="Trace ID">
        <Input placeholder="精确搜索 Trace ID" style={{ width: 200 }} />
      </Form.Item>
      <Form.Item>
        <Space>
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置
          </Button>
        </Space>
      </Form.Item>
    </Form>
  );
};

export default TraceFilterBar;
```

- [ ] **Step 2: 运行测试验证通过**
Run: `cd frontend && npm run test -- TraceFilterBar --watchAll=false`
Expected: PASS

---

### Task 3.5.3: 集成到 LLMMonitoringDashboard

**Files:**
- Modify: `frontend/src/pages/LLMMonitoringDashboard.tsx`

- [ ] **Step 1: 添加 Traces 标签页**
```tsx
// 在 LLMMonitoringDashboard.tsx 中
import { Tabs } from 'antd';
import TraceListView from '../components/monitoring/TraceListView';
import TraceFilterBar from '../components/monitoring/TraceFilterBar';
import TraceDetailDrawer from '../components/monitoring/TraceDetailDrawer';

const LLMMonitoringDashboard: React.FC = () => {
  const [filters, setFilters] = useState<Record<string, any>>({});
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  const items = [
    // ... 现有标签页 ...
    {
      key: 'traces',
      label: '调用追踪 (Traces)',
      children: (
        <>
          <TraceFilterBar onFilter={setFilters} />
          <div style={{ marginTop: 16 }}>
            <TraceListView
              filters={filters}
              onRowClick={setSelectedTraceId}
            />
          </div>
          <TraceDetailDrawer
            traceId={selectedTraceId}
            onClose={() => setSelectedTraceId(null)}
          />
        </>
      ),
    },
  ];

  return <Tabs items={items} />;
};
```

- [ ] **Step 2: 运行测试验证通过**
Run: `cd frontend && npm run test -- LLMMonitoringDashboard --watchAll=false`
Expected: PASS

---

### Task 3.5.4: 实现 LatencyChart

**Files:**
- Create: `frontend/src/components/monitoring/LatencyChart.tsx`
- Test: `frontend/src/components/monitoring/__tests__/LatencyChart.test.tsx`

- [ ] **Step 1: 定义组件**
```tsx
// frontend/src/components/monitoring/LatencyChart.tsx
import React, { useEffect, useState } from 'react';
import { Card, Spin } from 'antd';
import { Chart } from '@antv/g2plot';
import request from '../../utils/request';

interface LatencyStats {
  p50: number;
  p95: number;
  p99: number;
  avg: number;
  min: number;
  max: number;
}

const LatencyChart: React.FC = () => {
  const [stats, setStats] = useState<LatencyStats | null>(null);
  const [loading, setLoading] = useState(false);
  const chartRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadLatencyStats();
  }, []);

  useEffect(() => {
    if (stats && chartRef.current) {
      renderChart();
    }
  }, [stats]);

  const loadLatencyStats = async () => {
    setLoading(true);
    try {
      const { data } = await request.get('/api/v1/monitoring/latency');
      setStats(data);
    } finally {
      setLoading(false);
    }
  };

  const renderChart = () => {
    if (!chartRef.current || !stats) return;
    
    const chart = new Chart(chartRef.current, { autoFit: true });
    chart.data([
      { metric: 'P50', value: stats.p50 },
      { metric: 'P95', value: stats.p95 },
      { metric: 'P99', value: stats.p99 },
      { metric: 'AVG', value: stats.avg },
      { metric: 'MIN', value: stats.min },
      { metric: 'MAX', value: stats.max },
    ]);
    chart.interval().position('metric*value').color('metric').label('value');
    chart.axis('value', { label: { formatter: '{value}ms' } });
    chart.render();
  };

  return (
    <Card title="延迟分布" loading={loading}>
      <div ref={chartRef} style={{ height: 300 }} />
      {stats && (
        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-around' }}>
          <div>P50: <strong>{stats.p50}ms</strong></div>
          <div>P95: <strong>{stats.p95}ms</strong></div>
          <div>P99: <strong>{stats.p99}ms</strong></div>
        </div>
      )}
    </Card>
  );
};

export default LatencyChart;
```

- [ ] **Step 2: 运行测试验证通过**
Run: `cd frontend && npm run test -- LatencyChart --watchAll=false`
Expected: PASS

---

## 验收标准

- [ ] TraceListView 正确展示追踪列表，支持排序和分页
- [ ] TraceFilterBar 提供完整筛选功能
- [ ] Traces 标签页集成到 LLMMonitoringDashboard
- [ ] 点击行打开 TraceDetailDrawer
- [ ] 复制 Trace ID 功能正常

---

**上一阶段:** [04-data-processing.md](./05-phase-3-04-data-processing.md)  
**下一阶段:** [06-trace-details.md](./05-phase-3-06-trace-details.md)
