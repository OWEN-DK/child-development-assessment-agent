# Phase 3.6: 链路详情与分析

> **前置文档:** [05-dashboard.md](./05-phase-3-05-dashboard.md)
> **状态:** ⏳ 完全待实现

## Span 层级树设计

以树形结构展示 Trace 下的所有 Span，支持展开/折叠。

### 层级结构

```
根节点: Trace 基本信息 (名称、用户、时间范围、总成本)
├── 子节点: NodePre Span
│   └── 叶子节点: LLM 调用 Span (query_classification)
├── 子节点: ValidationNode Span
│   └── 叶子节点: LLM 调用 Span (validation)
├── 子节点: AssessmentNode Span
│   └── 叶子节点: LLM 调用 Span (assessment)
├── 子节点: RetrievalNode Span
├── 子节点: ScoringNode Span
└── 子节点: ReportingNode Span
    └── 叶子节点: LLM 调用 Span (reporting)
```

---

## 实施任务

### Task 3.6.1: 实现 TraceDetailDrawer

**Files:**
- Create: `frontend/src/components/monitoring/TraceDetailDrawer.tsx`
- Create: `frontend/src/api/tracing.ts`
- Test: `frontend/src/components/monitoring/__tests__/TraceDetailDrawer.test.tsx`

- [ ] **Step 1: 定义 API 客户端**
```ts
// frontend/src/api/tracing.ts
import request from '../utils/request';
import type { Trace, Span } from '../types/tracing';

export const useTraceApi = () => {
  const fetchTraces = async (params: Record<string, any>) => {
    const { data } = await request.get('/api/v1/monitoring/traces', { params });
    return data;
  };

  const fetchTraceDetail = async (traceId: string): Promise<Trace & { spans: Span[] }> => {
    const { data } = await request.get(`/api/v1/monitoring/traces/${traceId}`);
    return data;
  };

  const fetchSpanDetail = async (traceId: string, spanId: string): Promise<Span> => {
    const { data } = await request.get(`/api/v1/monitoring/traces/${traceId}/spans/${spanId}`);
    return data;
  };

  return { fetchTraces, fetchTraceDetail, fetchSpanDetail };
};
```

- [ ] **Step 2: 定义组件**
```tsx
// frontend/src/components/monitoring/TraceDetailDrawer.tsx
import React, { useEffect, useState } from 'react';
import { Drawer, Descriptions, Spin, Alert } from 'antd';
import SpanTreeView from './SpanTreeView';
import SpanDetailPanel from './SpanDetailPanel';
import { useTraceApi } from '../../api/tracing';
import type { Trace, Span } from '../../types/tracing';

interface TraceDetailDrawerProps {
  traceId: string | null;
  onClose: () => void;
}

const TraceDetailDrawer: React.FC<TraceDetailDrawerProps> = ({ traceId, onClose }) => {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [spans, setSpans] = useState<Span[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);
  const { fetchTraceDetail } = useTraceApi();

  useEffect(() => {
    if (traceId) {
      loadTraceDetail();
    }
  }, [traceId]);

  const loadTraceDetail = async () => {
    if (!traceId) return;
    setLoading(true);
    try {
      const result = await fetchTraceDetail(traceId);
      setTrace(result);
      setSpans(result.spans || []);
    } catch (error) {
      // 错误处理
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer
      title="Trace 详情"
      width={800}
      open={!!traceId}
      onClose={onClose}
    >
      {loading ? (
        <Spin size="large" />
      ) : trace ? (
        <>
          <Descriptions title="基本信息" bordered column={2}>
            <Descriptions.Item label="Trace ID">{trace.trace_id}</Descriptions.Item>
            <Descriptions.Item label="名称">{trace.name}</Descriptions.Item>
            <Descriptions.Item label="用户 ID">{trace.user_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="状态">{trace.status}</Descriptions.Item>
            <Descriptions.Item label="开始时间">{new Date(trace.start_time).toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="结束时间">{trace.end_time ? new Date(trace.end_time).toLocaleString() : '-'}</Descriptions.Item>
            <Descriptions.Item label="总耗时">{trace.total_duration_ms}ms</Descriptions.Item>
            <Descriptions.Item label="总 Token">{trace.total_tokens}</Descriptions.Item>
            <Descriptions.Item label="总成本">{trace.total_cost ? `¥${trace.total_cost}` : '未配置'}</Descriptions.Item>
          </Descriptions>

          <div style={{ marginTop: 16 }}>
            <h4>Span 层级树</h4>
            <SpanTreeView
              spans={spans}
              onSpanClick={setSelectedSpan}
            />
          </div>

          {selectedSpan && (
            <div style={{ marginTop: 16 }}>
              <SpanDetailPanel span={selectedSpan} />
            </div>
          )}
        </>
      ) : (
        <Alert message="Trace 不存在" type="error" />
      )}
    </Drawer>
  );
};

export default TraceDetailDrawer;
```

- [ ] **Step 3: 运行测试验证通过**
Run: `cd frontend && npm run test -- TraceDetailDrawer --watchAll=false`
Expected: PASS

---

### Task 3.6.2: 实现 SpanTreeView

**Files:**
- Create: `frontend/src/components/monitoring/SpanTreeView.tsx`

- [ ] **Step 1: 定义组件**
```tsx
// frontend/src/components/monitoring/SpanTreeView.tsx
import React, { useState } from 'react';
import { Tree, Tag } from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { Span } from '../../types/tracing';

interface SpanTreeViewProps {
  spans: Span[];
  onSpanClick: (span: Span) => void;
}

const SpanTreeView: React.FC<SpanTreeViewProps> = ({ spans, onSpanClick }) => {
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);

  // 构建树形结构
  const buildTree = (spans: Span[]): DataNode[] => {
    const spanMap = new Map<string, Span>();
    const rootNodes: DataNode[] = [];
    const childrenMap = new Map<string, Span[]>();

    spans.forEach(span => {
      spanMap.set(span.span_id, span);
      if (!span.parent_span_id) {
        rootNodes.push(spanToDataNode(span));
      } else {
        if (!childrenMap.has(span.parent_span_id)) {
          childrenMap.set(span.parent_span_id, []);
        }
        childrenMap.get(span.parent_span_id)!.push(span);
      }
    });

    const attachChildren = (node: DataNode) => {
      const children = childrenMap.get(node.key as string);
      if (children) {
        node.children = children.map(child => {
          const childNode = spanToDataNode(child);
          attachChildren(childNode);
          return childNode;
        });
      }
    };

    rootNodes.forEach(attachChildren);
    return rootNodes;
  };

  const spanToDataNode = (span: Span): DataNode => ({
    key: span.span_id,
    title: (
      <div onClick={() => onSpanClick(span)} style={{ cursor: 'pointer' }}>
        <span>{span.name}</span>
        <Tag color="blue" style={{ marginLeft: 8 }}>{span.duration_ms}ms</Tag>
        {span.tokens && <Tag>{span.tokens} tokens</Tag>}
      </div>
    ),
  });

  const treeData = buildTree(spans);

  return (
    <Tree
      treeData={treeData}
      expandedKeys={expandedKeys}
      onExpand={setExpandedKeys}
      defaultExpandAll
    />
  );
};

export default SpanTreeView;
```

- [ ] **Step 2: 运行测试验证通过**
Run: `cd frontend && npm run test -- SpanTreeView --watchAll=false`
Expected: PASS

---

### Task 3.6.3: 实现 SpanDetailPanel

**Files:**
- Create: `frontend/src/components/monitoring/SpanDetailPanel.tsx`

- [ ] **Step 1: 定义组件**
```tsx
// frontend/src/components/monitoring/SpanDetailPanel.tsx
import React, { useState } from 'react';
import { Collapse, Descriptions, Tabs, Typography } from 'antd';
import type { Span } from '../../types/tracing';

const { Text } = Typography;

interface SpanDetailPanelProps {
  span: Span;
}

const SpanDetailPanel: React.FC<SpanDetailPanelProps> = ({ span }) => {
  const [activeTab, setActiveTab] = useState('input');

  return (
    <Collapse defaultActiveKey={['basic']}>
      <Collapse.Panel header="基本信息" key="basic">
        <Descriptions bordered column={2}>
          <Descriptions.Item label="Span ID">{span.span_id}</Descriptions.Item>
          <Descriptions.Item label="父 Span ID">{span.parent_span_id || '-'}</Descriptions.Item>
          <Descriptions.Item label="耗时">{span.duration_ms}ms</Descriptions.Item>
          <Descriptions.Item label="Token">{span.tokens || '-'}</Descriptions.Item>
          <Descriptions.Item label="状态">{span.status}</Descriptions.Item>
          <Descriptions.Item label="首 Token 延迟">{span.completion_start_time_ms ? `${span.completion_start_time_ms}ms` : '-'}</Descriptions.Item>
        </Descriptions>
      </Collapse.Panel>

      <Collapse.Panel header="输入/输出" key="io">
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <Tabs.TabPane tab="输入 (Prompt)" key="input">
            <Text copyable style={{ whiteSpace: 'pre-wrap', display: 'block' }}>
              {JSON.stringify(span.prompt_messages, null, 2)}
            </Text>
          </Tabs.TabPane>
          <Tabs.TabPane tab="输出 (Completion)" key="output">
            <Text copyable style={{ whiteSpace: 'pre-wrap', display: 'block' }}>
              {span.completion_message}
            </Text>
          </Tabs.TabPane>
        </Tabs>
      </Collapse.Panel>

      <Collapse.Panel header="调用参数" key="params">
        <Descriptions bordered column={1}>
          {span.call_parameters && Object.entries(span.call_parameters).map(([key, value]) => (
            <Descriptions.Item key={key} label={key}>{String(value)}</Descriptions.Item>
          ))}
        </Descriptions>
      </Collapse.Panel>

      {span.error && (
        <Collapse.Panel header="错误信息" key="error">
          <Text type="danger">{span.error}</Text>
        </Collapse.Panel>
      )}
    </Collapse>
  );
};

export default SpanDetailPanel;
```

- [ ] **Step 2: 运行测试验证通过**
Run: `cd frontend && npm run test -- SpanDetailPanel --watchAll=false`
Expected: PASS

---

### Task 3.6.4: 实现成本分析面板

**Files:**
- Create: `frontend/src/components/monitoring/CostAnalysisDashboard.tsx`

- [ ] **Step 1: 定义组件**
```tsx
// frontend/src/components/monitoring/CostAnalysisDashboard.tsx
import React, { useEffect, useState } from 'react';
import { Card, Statistic, Row, Col, Table } from 'antd';
import request from '../../utils/request';

interface CostStats {
  total_cost: string;
  total_tokens: number;
  total_calls: number;
  avg_cost_per_call: string;
}

const CostAnalysisDashboard: React.FC = () => {
  const [stats, setStats] = useState<CostStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadCostStats();
  }, []);

  const loadCostStats = async () => {
    setLoading(true);
    try {
      const { data } = await request.get('/api/v1/monitoring/cost');
      setStats(data);
    } finally {
      setLoading(false);
    }
  };

  const modelCostColumns = [
    { title: '模型', dataIndex: 'model', key: 'model' },
    { title: '调用次数', dataIndex: 'calls', key: 'calls' },
    { title: '总 Token', dataIndex: 'tokens', key: 'tokens' },
    { title: '总成本', dataIndex: 'cost', key: 'cost', render: (cost: string) => `¥${cost}` },
  ];

  return (
    <div>
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic title="总成本" value={stats?.total_cost || 0} prefix="¥" loading={loading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="总 Token" value={stats?.total_tokens || 0} loading={loading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="总调用次数" value={stats?.total_calls || 0} loading={loading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="平均成本/次" value={stats?.avg_cost_per_call || 0} prefix="¥" loading={loading} />
          </Card>
        </Col>
      </Row>

      {/* 按模型统计表格 */}
    </div>
  );
};

export default CostAnalysisDashboard;
```

- [ ] **Step 2: 运行测试验证通过**
Run: `cd frontend && npm run test -- CostAnalysisDashboard --watchAll=false`
Expected: PASS

---

## 验收标准

- [ ] TraceDetailDrawer 正确展示 Trace 基本信息
- [ ] SpanTreeView 正确构建树形结构，支持展开/折叠
- [ ] SpanDetailPanel 展示输入、输出、调用参数、错误信息
- [ ] 内容支持 Markdown 渲染和复制
- [ ] CostAnalysisDashboard 正确展示成本统计

---

**上一阶段:** [05-dashboard.md](./05-phase-3-05-dashboard.md)  
**下一阶段:** [07-api-extension.md](./05-phase-3-07-api-extension.md)
