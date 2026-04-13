# Phase 7: 前端全功能集成与测试

> 本文档是 MySQL + Redis 集成重构实施方案的一部分
> 
> **返回索引：** [README.md](./README.md) | [项目概览](./00-overview.md)

---

## Phase 7: 前端全功能集成与测试（周期：3 天）

### 目标
集成所有新增功能页面（系统配置、提示词管理、LLM 监控），进行端到端功能测试，优化性能和用户体验。

### 架构设计

```
┌─────────────────────────────────────────────────┐
│           React 前端应用                          │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ 系统配置页面  │  │ 提示词管理页面 │            │
│  └──────────────┘  └──────────────┘            │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ LLM 监控仪表板 │  │ RAG 测试页面   │            │
│  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────┘
                      ↓ API Calls
┌─────────────────────────────────────────────────┐
│           FastAPI 后端服务                        │
└─────────────────────────────────────────────────┘
```

---

### Task 7.1: 集成系统配置页面

**Files:**
- Create: `frontend/src/features/system-config/ConfigManagementPage.tsx`
- Create: `frontend/src/features/system-config/ConfigForm.tsx`
- Create: `frontend/src/features/system-config/ConfigFieldRenderer.tsx`
- Create: `frontend/src/features/system-config/schema.ts`
- Create: `frontend/src/features/system-config/index.ts`

- [x] **Step 1: 创建配置管理页面组件**
- [x] **Step 2: 实现 Schema 驱动表单渲染器**
- [x] **Step 3: 动态生成表单**
- [x] **Step 4: 修复 API 方法调用适配**

```tsx
// frontend/src/features/system-config/ConfigManagementPage.tsx
import React, { useState } from 'react';
import { ProTable } from '@ant-design/pro-components';
import { Table, Button, Modal, Form, Input, Space, Tag, Typography } from 'antd';
import { useQuery, useMutation } from '@tanstack/react-query';
import { configApi } from '@/api/config';

const { Text } = Typography;

export const ConfigManagementPage: React.FC = () => {
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);

  // 查询配置版本列表
  const { data: versions, refetch } = useQuery({
    queryKey: ['configVersions'],
    queryFn: () => configApi.getVersions(),
  });

  // 创建新版本
  const createMutation = useMutation({
    mutationFn: (data: any) => configApi.createVersion(data),
    onSuccess: () => {
      refetch();
      setModalVisible(false);
    },
  });

  // 回滚
  const rollbackMutation = useMutation({
    mutationFn: (versionId: string) => configApi.rollback(versionId),
    onSuccess: () => {
      refetch();
    },
  });

  const columns = [
    {
      title: '版本 ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '创建者',
      dataIndex: 'created_by',
      key: 'created_by',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button
            size="small"
            onClick={() => handleViewDetail(record.id)}
          >
            查看
          </Button>
          <Button
            size="small"
            danger
            onClick={() => handleRollback(record.id)}
          >
            回滚
          </Button>
        </Space>
      ),
    },
  ];

  const handleViewDetail = (versionId: string) => {
    setSelectedVersion(versionId);
    // 打开详情弹窗
  };

  const handleRollback = (versionId: string) => {
    Modal.confirm({
      title: '确认回滚',
      content: '确定要回滚到此版本吗？',
      onOk: () => rollbackMutation.mutate(versionId),
    });
  };

  return (
    <div>
      <ProTable
        columns={columns}
        dataSource={versions}
        rowKey="id"
        headerTitle="配置版本管理"
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            onClick={() => setModalVisible(true)}
          >
            创建新版本
          </Button>,
        ]}
      />

      <Modal
        title="创建配置版本"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => {
          // 提交表单
        }}
      >
        <Form layout="vertical">
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
```

---

### Task 7.2: 集成提示词管理页面

**Files:**
- Exist: `frontend/src/features/prompts/PromptManagementPage.tsx`

- [x] **Step 1: 创建提示词管理页面** - 已存在且功能完整

```tsx
// frontend/src/features/prompt-management/PromptManagementPage.tsx
import React, { useState } from 'react';
import { ProTable } from '@ant-design/pro-components';
import { Table, Button, Modal, Form, Input, Space, Typography, Diff } from 'antd';
import { useQuery, useMutation } from '@tanstack/react-query';
import { promptApi } from '@/api/prompt';

const { Text } = Typography;

export const PromptManagementPage: React.FC = () => {
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
  const [compareModalVisible, setCompareModalVisible] = useState(false);
  const [compareVersions, setCompareVersions] = useState<[string, string] | null>(null);

  // 查询提示词列表
  const { data: prompts } = useQuery({
    queryKey: ['prompts'],
    queryFn: () => promptApi.getList(),
  });

  // 创建版本
  const createMutation = useMutation({
    mutationFn: ({ promptKey, content, description }: any) =>
      promptApi.createVersion(promptKey, content, description),
    onSuccess: () => {
      setModalVisible(false);
    },
  });

  // 对比版本
  const compareMutation = useMutation({
    mutationFn: ({ promptKey, version1, version2 }: any) =>
      promptApi.compare(promptKey, version1, version2),
    onSuccess: (data) => {
      setCompareVersions([data.version_1, data.version_2]);
      setCompareModalVisible(true);
    },
  });

  const columns = [
    {
      title: '提示词键',
      dataIndex: 'prompt_key',
      key: 'prompt_key',
    },
    {
      title: '最新版本',
      dataIndex: 'latest_version',
      key: 'latest_version',
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button
            size="small"
            onClick={() => handleEdit(record.prompt_key)}
          >
            编辑
          </Button>
          <Button
            size="small"
            onClick={() => handleCompare(record.prompt_key)}
          >
            对比
          </Button>
        </Space>
      ),
    },
  ];

  const handleEdit = (promptKey: string) => {
    setSelectedPrompt(promptKey);
    setModalVisible(true);
  };

  const handleCompare = (promptKey: string) => {
    // 选择两个版本进行对比
    compareMutation.mutate({
      promptKey,
      version1: '1.0.0',
      version2: '1.1.0',
    });
  };

  return (
    <div>
      <ProTable
        columns={columns}
        dataSource={prompts}
        rowKey="prompt_key"
        headerTitle="提示词管理"
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            onClick={() => setModalVisible(true)}
          >
            新建提示词
          </Button>,
        ]}
      />

      <Modal
        title="编辑提示词"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        width={800}
        footer={null}
      >
        <Form layout="vertical">
          <Form.Item label="提示词键" name="prompt_key">
            <Input disabled />
          </Form.Item>
          <Form.Item label="内容" name="content">
            <Input.TextArea rows={10} />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={() => {
              // 提交
            }}>
              保存新版本
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="版本对比"
        open={compareModalVisible}
        onCancel={() => setCompareModalVisible(false)}
        width={1000}
      >
        <Diff
          left={compareVersions?.[0]?.content || ''}
          right={compareVersions?.[1]?.content || ''}
        />
      </Modal>
    </div>
  );
};
```

---

### Task 7.3: 集成 LLM 监控仪表板

**Files:**
- Create: `frontend/src/features/monitoring/LLMMonitoringDashboard.tsx`
- Create: `frontend/src/features/monitoring/index.ts`
- Create: `frontend/src/api/monitoring/index.ts`
- Create: `frontend/src/api/monitoring/types.ts`

- [x] **Step 1: 创建监控仪表板**

```tsx
// frontend/src/features/monitoring/LLMMonitoringDashboard.tsx
import React from 'react';
import { Card, Row, Col, Statistic, Select } from 'antd';
import { Line, Pie } from '@ant-design/charts';
import { useQuery } from '@tanstack/react-query';
import { monitoringApi } from '@/api/monitoring';

const { Option } = Select;

export const LLMMonitoringDashboard: React.FC = () => {
  const [days, setDays] = React.useState(7);
  const [modelFilter, setModelFilter] = React.useState<string | undefined>();

  // 查询统计数据
  const { data: statistics } = useQuery({
    queryKey: ['monitoringStats', days, modelFilter],
    queryFn: () => monitoringApi.getStatistics(days, modelFilter),
  });

  // 查询趋势
  const { data: trend } = useQuery({
    queryKey: ['monitoringTrend', days],
    queryFn: () => monitoringApi.getTrend(days, 'calls'),
  });

  // 查询模型分布
  const { data: modelDistribution } = useQuery({
    queryKey: ['modelDistribution', days],
    queryFn: () => monitoringApi.getModelDistribution(days),
  });

  const lineConfig = {
    data: trend?.trend || [],
    xField: 'hour',
    yField: 'value',
    point: { size: 5, shape: 'circle' },
    label: {
      style: { fill: '#aaa' },
    },
  };

  const pieConfig = {
    data: modelDistribution?.distribution || [],
    angleField: 'count',
    colorField: 'model_name',
    radius: 0.8,
    labels: {
      type: 'outer',
      content: '{name} {percentage}',
    },
  };

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总调用次数"
              value={statistics?.total_calls || 0}
              suffix="次"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="成功率"
              value={(1 - (statistics?.error_rate || 0)) * 100}
              precision={2}
              suffix="%"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="总 Token 消耗"
              value={statistics?.total_tokens || 0}
              suffix="个"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="平均耗时"
              value={statistics?.avg_duration_ms || 0}
              precision={0}
              suffix="ms"
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={16}>
          <Card title="调用趋势">
            <Line {...lineConfig} />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="模型使用分布">
            <Pie {...pieConfig} />
          </Card>
        </Col>
      </Row>
    </div>
  );
};
```

---

### Task 7.4: 端到端功能测试

**Files:**
- Create: `frontend/src/__tests__/e2e/integration.test.tsx`

- [x] **Step 1: 创建端到端测试**

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigManagementPage } from '@/features/system-config/ConfigManagementPage';

const queryClient = new QueryClient();

describe('端到端测试', () => {
  it('配置管理页面完整流程', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ConfigManagementPage />
      </QueryClientProvider>
    );

    // 等待表格加载
    await waitFor(() => {
      expect(screen.getByText('配置版本管理')).toBeInTheDocument();
    });

    // 点击创建按钮
    const createButton = screen.getByText('创建新版本');
    await userEvent.click(createButton);

    // 填写表单
    const descriptionInput = screen.getByLabelText('描述');
    await userEvent.type(descriptionInput, '测试版本');

    // 提交
    const submitButton = screen.getByText('确定');
    await userEvent.click(submitButton);

    // 验证创建成功
    await waitFor(() => {
      expect(screen.getByText('测试版本')).toBeInTheDocument();
    });
  });
});
```

---

### Task 7.5: 实现 Schema 驱动表单渲染器

**Files:**
- Create: `frontend/src/features/system-config/schema.ts`
- Create: `frontend/src/features/system-config/ConfigFieldRenderer.tsx`
- Create: `frontend/src/features/system-config/ConfigForm.tsx`

- [x] **Step 1: 定义配置 Schema**
- [x] **Step 2: 实现动态渲染器**
- [x] **Step 3: 动态生成表单**
- [x] **Step 4: 验证动态表单**

启动前端，确认表单能正确渲染所有配置项：
```bash
cd frontend
npm run dev
```

访问 `http://localhost:3000/system-config`，验证：
- 数据库配置模块正确渲染
- Redis 配置模块正确渲染
- 所有字段类型（boolean、number、string、enum）都能正确显示
- 禁用字段无法编辑

---

### Phase 7 完成验证

- [x] 运行所有前端测试 - 5 tests passed
- [x] 验证所有页面功能正常
- [x] TypeScript 类型检查通过
- [x] 用户体验优化
- [x] 修复 API 方法调用适配
- [x] 修复测试环境 Mock 配置

---

**返回索引：** [README.md](./README.md)
