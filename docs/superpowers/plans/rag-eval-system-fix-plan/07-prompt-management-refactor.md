# P1 提示词管理页面重构：对齐需求文档

**优先级**: 🟡 重要  
**工作量**: 6h  
**状态**: 方案制定中，待实施  

---

## 一、问题诊断

### 1.1 核心问题清单

| # | 问题 | 严重程度 | 影响范围 |
|---|------|----------|----------|
| 1 | **两套页面并存** | 🔴 高 | 路由混乱，维护成本高 |
| 2 | **A/B 测试未删除** | 🔴 高 | 违反需求文档明确指令 |
| 3 | **路由参数用 `:id` 而非 `:key`** | 🔴 高 | 语义错误，与后端 API 不一致 |
| 4 | **缺少独立子页面路由** | 🔴 高 | 无法通过 URL 直接访问编辑/版本/沙箱页 |
| 5 | **API 端点路径不匹配** | 🔴 高 | 前后端 API 契约不一致，调用会 404 |
| 6 | **列表页功能缺失** | 🟡 中 | 缺少状态筛选、版本号列、测试沙箱入口 |
| 7 | **编辑页布局不符** | 🟡 中 | 非左右分栏，无变量实时提取，无保存前校验 |
| 8 | **版本页功能缺失** | 🟡 中 | 无回滚功能，无 diff 可视化 |
| 9 | **沙箱页功能缺失** | 🟡 中 | 无对比模式，无历史记录 |
| 10 | **硬编码 Prompt 列表** | 🟡 中 | `PromptManagementPage` 使用常量数组，非 API 动态获取 |

### 1.2 详细分析

#### 问题 1：两套页面并存

**现状**：
- `/rag-eval/prompts/*`：4 个页面（列表、编辑、版本对比、测试沙箱），功能接近需求
- `/prompt-management`：1 个页面（旧 A/B 测试管理页面），功能与需求不符

**根因**：
- 历史演进过程中未清理旧页面
- 需求文档更新后未同步重构路由

**影响**：
- 用户入口混乱，不知道使用哪个页面
- 维护双倍代码成本
- 路由命名不符合需求文档规范

---

#### 问题 2：A/B 测试未删除

**现状**：
- `PromptManagementPage.tsx` 包含完整 A/B 测试功能（Tab、表单、API 调用）
- 需求文档明确要求删除所有 A/B 测试相关端点和 UI

**根因**：
- 需求变更未执行彻底
- 旧代码未清理

**影响**：
- 违反需求文档
- 增加系统复杂度
- 用户困惑

---

#### 问题 3：路由参数用 `:id` 而非 `:key`

**现状**：
- 路由定义：`/rag-eval/prompts/:id`、`:id/versions`、`:id/test`
- 需求文档：`/prompt-management/:key`、`:key/versions`、`:key/sandbox`

**根因**：
- 开发时使用数据库自增 ID 作为路由参数
- 需求文档要求使用 Prompt Key（字符串标识符）作为路由参数

**影响**：
- 语义错误（Key 才是业务标识符）
- 与后端 API 路径不一致（后端使用 `:key`）
- URL 不友好（数字 ID 不如 Key 直观）

---

#### 问题 4：缺少独立子页面路由

**现状**：
- `/prompt-management` 仅注册了单页 `PromptManagementPage`
- 无 `/:key`、`/:key/versions`、`/:key/sandbox` 子路由

**根因**：
- 旧页面使用 Modal/Tab 切换，未拆分为独立路由

**影响**：
- 无法通过 URL 直接访问编辑/版本/沙箱页
- 浏览器前进/后退按钮失效
- 无法分享特定页面链接

---

#### 问题 5：API 端点路径不匹配

**现状**：
- 前端 API 客户端：`/rag/prompts`、`/rag/prompts/${key}`、`/rag/prompts/test`、`/rag/prompts/${key}/analyze`
- 需求文档：`/api/v1/prompts/metadata/*`、`/api/v1/prompts/:key/versions/*`、`/api/v1/prompts/:key/test`、`/api/v1/prompts/:key/impact`

**根因**：
- 前后端 API 契约未对齐
- 旧 API 路径未更新

**影响**：
- 调用会 404
- 数据无法正确加载/保存

---

## 二、修复方案

### 2.1 核心决策

**以 `/rag-eval/prompts/*` 四页面为基础重构**，原因：
1. 功能更接近需求（已有列表/编辑/版本/沙箱）
2. 删除 `/prompt-management` 单页（旧 A/B 测试页面）
3. 路由改为 `/prompt-management/*`（符合需求文档）

### 2.2 实施步骤

#### Step 1：删除旧页面和 A/B 测试代码

**文件**：
- `frontend/src/features/prompts/PromptManagementPage.tsx`（删除）
- `frontend/src/features/prompts/` 目录（删除）
- `frontend/src/api/rag-eval/prompts.ts` 中 A/B 测试相关 API（删除）

**操作**：
```bash
rm -rf frontend/src/features/prompts/
```

**代码清理**：
- 删除 `abTests`、`handleCreateABTest`、`handleToggleABTest`、`abTestColumns`、`abTestModalVisible` 等变量和函数
- 删除 A/B 测试 Tab 和 Modal

---

#### Step 2：迁移路由至 `/prompt-management/*`

**文件**：`frontend/src/router/index.tsx`

**修改前**：
```tsx
{
  path: 'rag-eval',
  children: [
    {
      path: 'prompts',
      children: [
        { index: true, element: <PromptListPage /> },
        { path: ':id', element: <PromptEditPage /> },
        { path: ':id/versions', element: <PromptVersionComparisonPage /> },
        { path: ':id/test', element: <PromptTestSandboxPage /> },
      ],
    },
  ],
},
{
  path: 'prompt-management',
  element: <PromptManagementPage />, // 旧页面，已删除
},
```

**修改后**：
```tsx
{
  path: 'prompt-management',
  children: [
    { index: true, element: <PromptListPage /> },
    { path: ':key', element: <PromptEditPage /> },
    { path: ':key/versions', element: <PromptVersionComparisonPage /> },
    { path: ':key/sandbox', element: <PromptTestSandboxPage /> },
  ],
},
```

**注意**：
- 路由前缀从 `/rag-eval/prompts` 改为 `/prompt-management`
- 路由参数从 `:id` 改为 `:key`
- 直接删除旧路由，不保留重定向

---

#### Step 3：修改页面路由参数 `:id` → `:key`

**文件**：
- `frontend/src/features/rag-eval/pages/PromptListPage.tsx`
- `frontend/src/features/rag-eval/pages/PromptEditPage.tsx`
- `frontend/src/features/rag-eval/pages/PromptVersionComparisonPage.tsx`
- `frontend/src/features/rag-eval/pages/PromptTestSandboxPage.tsx`

**修改内容**：
```tsx
// 修改前
const { id } = useParams();
const prompt = await api.get(`/rag/prompts/${id}`);

// 修改后
const { key } = useParams();
const prompt = await api.get(`/api/v1/prompts/metadata/${key}`);
```

**影响范围**：
- 所有 `useParams()` 调用
- 所有 API 请求路径
- 所有路由跳转（`navigate`、`Link`）

---

#### Step 4：修正 API 端点路径

**文件**：`frontend/src/api/rag-eval/prompts.ts`

**修改前**：
```typescript
export const getPrompt = (key: string) => api.get(`/rag/prompts/${key}`);
export const updatePrompt = (key: string, data: any) => api.put(`/rag/prompts/${key}`, data);
export const getVersions = (key: string) => api.get(`/rag/prompts/${key}/versions`);
export const testPrompt = (data: any) => api.post(`/rag/prompts/test`, data);
export const analyzeImpact = (key: string) => api.get(`/rag/prompts/${key}/analyze`);
```

**修改后**：
```typescript
export const getPromptMetadata = (key: string) => api.get(`/api/v1/prompts/metadata/${key}`);
export const updatePromptMetadata = (key: string, data: any) => api.put(`/api/v1/prompts/metadata/${key}`, data);
export const getVersions = (key: string) => api.get(`/api/v1/prompts/${key}/versions`);
export const createVersion = (key: string, data: any) => api.post(`/api/v1/prompts/${key}/versions`, data);
export const compareVersions = (key: string, v1: string, v2: string) => api.get(`/api/v1/prompts/${key}/versions/compare`, { params: { v1, v2 } });
export const rollbackVersion = (key: string, version: string) => api.post(`/api/v1/prompts/${key}/versions/rollback`, { version });
export const testPrompt = (key: string, data: any) => api.post(`/api/v1/prompts/${key}/test`, data);
export const getImpact = (key: string) => api.get(`/api/v1/prompts/${key}/impact`);
export const scanImpact = (key: string) => api.post(`/api/v1/prompts/${key}/scan`);
```

**注意**：
- 删除 A/B 测试相关 API
- 新增元数据 API、版本 API、测试沙箱 API、影响分析 API
- 路径与需求文档一致

---

#### Step 5：列表页增强

**文件**：`frontend/src/features/rag-eval/pages/PromptListPage.tsx`

**新增功能**：
1. **状态筛选**：全部/已启用/已禁用/未引用
2. **版本号列**：显示当前版本号 + 最后修改时间
3. **测试沙箱入口**：操作按钮组新增"测试沙箱"按钮
4. **状态展示**：三色状态（绿=启用且被引用，黄=启用未引用，红=禁用）

**表格列定义**：
```tsx
const columns = [
  { title: '状态', dataIndex: 'status', render: (status) => <StatusTag status={status} /> },
  { title: '中文名称', dataIndex: 'name_zh' },
  { title: 'Prompt Key', dataIndex: 'key' },
  { title: '分类', dataIndex: 'category' },
  { title: '版本', dataIndex: 'current_version', render: (v) => `${v.label} (${v.updated_at})` },
  { title: '操作', render: (_, record) => (
    <Space>
      <Button onClick={() => navigate(`/prompt-management/${record.key}`)}>编辑</Button>
      <Button onClick={() => navigate(`/prompt-management/${record.key}/versions`)}>版本</Button>
      <Button onClick={() => navigate(`/prompt-management/${record.key}/sandbox`)}>沙箱</Button>
    </Space>
  )},
];
```

---

#### Step 6：编辑页重构（左右分栏 + 变量实时提取 + 保存前校验）

**文件**：`frontend/src/features/rag-eval/pages/PromptEditPage.tsx`

**布局修改**：
```tsx
<Row gutter={16}>
  <Col span={16}>
    {/* 左侧：编辑器 */}
    <Card title="提示词内容">
      <Editor value={content} onChange={handleChange} />
    </Card>
  </Col>
  <Col span={8}>
    {/* 右侧：变量面板 + 影响分析 */}
    <Card title="变量列表">
      <VariableList variables={extractedVariables} onInsert={handleInsert} />
    </Card>
    <Card title="影响分析">
      <ImpactAnalysis impact={impactData} />
    </Card>
  </Col>
</Row>
```

**新增功能**：
1. **变量实时提取**：监听编辑器内容变化，实时提取 `{variable}` 格式变量
2. **变量插入**：点击变量可插入到编辑器光标处
3. **保存前校验**：
   - 变量缺失：声明了但未在内容中使用
   - 变量多余：内容中使用了但未声明
   - 类型不匹配：变量类型与 schema 定义不符
   - 弹窗警告，允许强制保存

**校验逻辑**：
```typescript
const validateBeforeSave = () => {
  const declaredVars = metadata.variables_schema.map(v => v.name);
  const usedVars = extractVariablesFromContent(content);
  
  const missing = declaredVars.filter(v => !usedVars.includes(v));
  const extra = usedVars.filter(v => !declaredVars.includes(v));
  
  if (missing.length > 0 || extra.length > 0) {
    Modal.warning({
      title: '变量校验警告',
      content: `缺失变量：${missing.join(', ')}\n多余变量：${extra.join(', ')}`,
      onOk: handleForceSave,
    });
    return false;
  }
  return true;
};
```

---

#### Step 7：版本页增强（回滚功能 + diff 可视化）

**文件**：`frontend/src/features/rag-eval/pages/PromptVersionComparisonPage.tsx`

**新增功能**：
1. **版本回滚**：版本列表底部操作区新增"回滚到此版本"按钮
2. **Diff 可视化**：左右分栏高亮差异，底部展示变更摘要

**回滚逻辑**：
```typescript
const handleRollback = async (version: string) => {
  await api.rollbackVersion(key, version);
  message.success('回滚成功');
  navigate(`/prompt-management/${key}`);
};
```

**Diff 可视化**：
```tsx
<DiffViewer
  oldValue={versionA.content}
  newValue={versionB.content}
  splitView={true}
/>
<ChangeSummary
  addedVars={addedVariables}
  removedVars={removedVariables}
  changedLines={changedLinesCount}
/>
```

---

#### Step 8：沙箱页增强（对比模式 + 历史记录）

**文件**：`frontend/src/features/rag-eval/pages/PromptTestSandboxPage.tsx`

**新增功能**：
1. **对比模式**：支持开启新旧版本输出对比
2. **历史记录**：展示历史测试记录列表

**对比模式**：
```tsx
<Switch
  checked={comparisonMode}
  onChange={setComparisonMode}
  checkedChildren="对比模式"
  unCheckedChildren="单次测试"
/>

{comparisonMode ? (
  <Row gutter={16}>
    <Col span={12}><OutputPanel output={oldVersionOutput} label="旧版本" /></Col>
    <Col span={12}><OutputPanel output={newVersionOutput} label="新版本" /></Col>
  </Row>
) : (
  <OutputPanel output={currentOutput} />
)}
```

**历史记录**：
```tsx
<Card title="测试历史">
  <List
    dataSource={history}
    renderItem={item => (
      <List.Item>
        <List.Item.Meta
          title={item.created_at}
          description={`变量：${JSON.stringify(item.variables)}`}
        />
        <Button onClick={() => loadHistory(item)}>加载</Button>
      </List.Item>
    )}
  />
</Card>
```

---

## 三、验收标准

### 3.1 路由与页面验收

- [ ] 删除 `/prompt-management` 旧单页（A/B 测试页面）
- [ ] 删除 `/rag-eval/prompts/*` 路由
- [ ] 新增 `/prompt-management/*` 路由（列表、编辑、版本、沙箱）
- [ ] 路由参数使用 `:key` 而非 `:id`
- [ ] 可通过 URL 直接访问编辑/版本/沙箱页

### 3.2 功能验收

- [ ] 删除所有 A/B 测试相关代码和 UI
- [ ] API 端点路径与需求文档一致
- [ ] 列表页支持状态筛选（全部/已启用/已禁用/未引用）
- [ ] 列表页显示版本号 + 最后修改时间
- [ ] 列表页操作按钮包含"测试沙箱"入口
- [ ] 状态展示三色（绿/黄/红）
- [ ] 编辑页为左右分栏布局
- [ ] 编辑页支持变量实时提取
- [ ] 编辑页支持变量插入
- [ ] 编辑页保存前校验（变量缺失/多余/类型不匹配）
- [ ] 版本页支持回滚功能
- [ ] 版本页支持 diff 可视化
- [ ] 沙箱页支持对比模式
- [ ] 沙箱页展示历史测试记录

### 3.3 数据验收

- [ ] 列表数据从 API 动态获取（非硬编码）
- [ ] 提示词元数据包含 `name_zh`、`category`、`current_version` 等字段
- [ ] 版本列表包含 `version_label`、`created_at`、`change_log` 等字段

---

## 四、风险分析

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 路由迁移导致书签失效 | 中 | 项目未上线，无历史兼容问题 |
| API 路径变更导致后端 404 | 高 | 与后端同步确认 API 端点已实现 |
| 变量实时提取性能问题 | 低 | 使用防抖（debounce）优化提取频率 |
| Diff 可视化库体积大 | 低 | 按需加载 diff 库，或使用轻量级实现 |

---

## 五、实施顺序

| 阶段 | 任务 | 工作量 | 优先级 |
|------|------|--------|--------|
| **阶段 1** | 删除旧页面和 A/B 测试代码 | 1h | 🔴 P0 |
| **阶段 2** | 迁移路由 + 修改 `:id` → `:key` | 1h | 🔴 P0 |
| **阶段 3** | 修正 API 端点路径 | 1h | 🔴 P0 |
| **阶段 4** | 列表页增强 | 1h | 🟡 P1 |
| **阶段 5** | 编辑页重构 | 1.5h | 🟡 P1 |
| **阶段 6** | 版本页增强 | 0.5h | 🟡 P1 |
| **阶段 7** | 沙箱页增强 | 0.5h | 🟡 P1 |

**总工作量**：约 **6.5 小时**

---

**方案制定完成，等待实施指令**。
