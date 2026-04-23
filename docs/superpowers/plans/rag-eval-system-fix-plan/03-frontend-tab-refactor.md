# P2 前端重构：Tab 切换 + 工作流约束

**优先级**: 🟢 功能增强  
**工作量**: 6h  

---

## 一、需求概述

### 1.1 核心目标

将现有分散的 RAG 评估页面重构为 **Tab 聚合式布局**，并实施**严格的工作流约束**：

```
工作流程强制约束：
书籍/JSON 导入 → 草稿审核 → 通过后进入测试用例库 → 测试集管理只能引用已有测试用例

禁止绕过：
❌ 测试集管理不能直接创建测试用例
❌ 测试集管理不能直接导入书籍/JSON
✅ 所有数据必须先经过草稿审核流程
```

### 1.2 现有路由（分散式）

```
/rag-eval/test-sets          → 测试集列表
/rag-eval/test-sets/:id      → 测试集详情
/rag-eval/test-sets/:id/drafts → 草稿审核
/rag-eval/runs               → 运行历史
/rag-eval/reports/:id        → 评估报告
```

**问题**：
- 草稿审核嵌套在测试集详情页，入口深
- 缺少独立的测试用例管理页
- 导入功能分散，无统一入口

---

## 二、新路由设计（Tab 聚合式）

### 2.1 路由结构

```
/rag-eval                    → 主布局（Tab 导航）
  ├── Tab 1: 草稿管理 (/rag-eval?tab=drafts)
  ├── Tab 2: 测试用例 (/rag-eval?tab=cases)
  ├── Tab 3: 测试集 (/rag-eval?tab=test-sets)
  └── Tab 4: 评估报告 (/rag-eval?tab=reports)
```

### 2.2 Tab 与功能映射

| Tab | 路由 | 页面组件 | 核心功能 |
|-----|------|----------|----------|
| **草稿管理** | `?tab=drafts` | `DraftManagementPage` | 书籍/JSON 导入、草稿审核、草稿编辑 |
| **测试用例** | `?tab=cases` | `TestCaseManagementPage` | 用例查看/编辑/删除、批量导出 |
| **测试集** | `?tab=test-sets` | `TestSetManagementPage` | 测试集 CRUD、引用用例、运行测试 |
| **评估报告** | `?tab=reports` | `ReportListPage` | 报告列表、详情、趋势、导出 |

---

## 三、核心页面设计

### 3.1 新建 `RagEvalMainPage.tsx`（主布局）

**文件**：`frontend/src/features/rag-eval/pages/RagEvalMainPage.tsx`

```tsx
import React, { useState, useEffect } from 'react';
import { Tabs } from 'antd';
import { useSearchParams } from 'react-router-dom';
import DraftManagementPage from './DraftManagementPage';
import TestCaseManagementPage from './TestCaseManagementPage';
import TestSetManagementPage from './TestSetManagementPage';
import ReportListPage from './ReportListPage';

const RagEvalMainPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState('drafts');

  // 从 URL 同步 Tab 状态
  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab && ['drafts', 'cases', 'test-sets', 'reports'].includes(tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  const handleTabChange = (key: string) => {
    setActiveTab(key);
    setSearchParams({ tab: key });
  };

  const tabItems = [
    {
      key: 'drafts',
      label: '草稿管理',
      children: <DraftManagementPage />
    },
    {
      key: 'cases',
      label: '测试用例',
      children: <TestCaseManagementPage />
    },
    {
      key: 'test-sets',
      label: '测试集管理',
      children: <TestSetManagementPage />
    },
    {
      key: 'reports',
      label: '评估报告',
      children: <ReportListPage />
    }
  ];

  return (
    <div className="rag-eval-main" style={{ padding: '24px' }}>
      <Tabs
        activeKey={activeTab}
        onChange={handleTabChange}
        items={tabItems}
        destroyInactiveTabPane={true}  // 懒渲染：销毁未激活 Tab，避免同时挂载 4 个页面
        size="large"
        type="card"
      />
    </div>
  );
};

export default RagEvalMainPage;
```

---

### 3.2 页面 1：草稿管理页 (`DraftManagementPage`)

**文件**：`frontend/src/features/rag-eval/pages/DraftManagementPage.tsx`

#### 功能清单

| 功能 | 说明 | API |
|------|------|-----|
| **书籍导入** | PDF/EPUB 上传 → 解析 → 生成草稿 | `POST /api/rag/documents/upload` |
| **JSON 导入** | 上传 JSON 文件 → 预览 → 批量创建草稿 | `POST /api/rag/cases/import/preview` + `POST /api/rag/cases/batch` |
| **草稿列表** | 按领域/年龄/状态筛选 | `GET /api/rag/drafts` |
| **草稿审核** | 单个通过/拒绝、批量操作 | `POST /api/rag/drafts/batch-review` |
| **草稿编辑** | 修改 query、expected_answer、domain 等 | `PUT /api/rag/drafts/:id` |

#### 工作流约束

```
导入书籍/JSON → 生成草稿 → 人工审核 → 通过 → 自动转入测试用例库
```

#### 核心组件结构

```tsx
const DraftManagementPage: React.FC = () => {
  return (
    <div>
      {/* 操作栏 */}
      <Space>
        <UploadBookModal />      {/* 书籍导入 */}
        <ImportJsonModal />      {/* JSON 导入 */}
      </Space>

      {/* 筛选栏 */}
      <FilterBar
        domains={TestDomain}
        ageRanges={AGE_RANGES}
        statuses={['pending', 'approved', 'rejected']}
      />

      {/* 草稿列表 */}
      <DraftTable
        columns={DRAFT_COLUMNS}
        rowSelection={rowSelection}
        onBatchReview={handleBatchReview}
      />

      {/* 批量审核弹窗 */}
      <BatchReviewModal />
    </div>
  );
};
```

---

### 3.3 页面 2：测试用例管理页 (`TestCaseManagementPage`)

**文件**：`frontend/src/features/rag-eval/pages/TestCaseManagementPage.tsx`

#### 功能清单

| 功能 | 说明 | API |
|------|------|-----|
| **用例列表** | 展示所有已通过审核的用例 | `GET /api/rag/cases?status=approved` |
| **用例详情** | 查看/编辑用例 | `GET /api/rag/cases/:id` + `PUT /api/rag/cases/:id` |
| **用例删除** | 软删除，保留历史记录 | `DELETE /api/rag/cases/:id` |
| **批量导出** | JSON/CSV 导出 | `GET /api/rag/cases/export?format=json` |

#### 工作流约束（重点）

```
数据来源：仅能从草稿审核通过自动流入
禁止操作：❌ 新建用例  ❌ 直接导入
允许操作：✅ 查看  ✅ 编辑  ✅ 删除  ✅ 导出
```

#### 核心组件结构

```tsx
const TestCaseManagementPage: React.FC = () => {
  return (
    <div>
      {/* 操作栏 - 无"新建"按钮 */}
      <Space>
        <ExportButton />  {/* 仅导出 */}
      </Space>

      {/* 筛选栏 */}
      <FilterBar
        domains={TestDomain}
        cognitiveDimensions={CognitiveDimension}  {/* 12 种维度 */}
        ageRanges={AGE_RANGES}
      />

      {/* 用例列表 */}
      <TestCaseTable
        columns={CASE_COLUMNS}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      {/* 编辑弹窗 */}
      <EditCaseModal />
    </div>
  );
};
```

**关键**：移除了所有"新建用例"、"导入"按钮。

---

### 3.4 页面 3：测试集管理页 (`TestSetManagementPage`)

**文件**：`frontend/src/features/rag-eval/pages/TestSetManagementPage.tsx`

#### 功能清单

| 功能 | 说明 | API |
|------|------|-----|
| **测试集列表** | 创建/编辑/删除测试集 | `GET /api/rag/test-sets` + `POST /api/rag/test-sets` |
| **测试集详情** | 查看关联的用例列表 | `GET /api/rag/test-sets/:id` |
| **添加用例** | 从已有测试用例库选择 | `POST /api/rag/test-sets/:id/cases` |
| **批量添加** | 从已有用例库批量选择 | `POST /api/rag/test-sets/:id/cases/batch` |
| **运行测试** | 配置并发数 → 启动运行 | `POST /api/rag/test-sets/:id/run` |
| **移除用例** | 从测试集移除，不删除用例本身 | `DELETE /api/rag/test-sets/:id/cases/:caseId` |

#### 工作流约束（重点）

```
数据来源：仅能从测试用例库引用
禁止操作：❌ 创建新用例  ❌ 导入书籍/JSON
允许操作：✅ 创建测试集  ✅ 引用已有用例  ✅ 运行测试  ✅ 查看报告
```

#### 核心组件结构

```tsx
const TestSetManagementPage: React.FC = () => {
  const handleAddCases = () => {
    // 打开用例选择器模态框（仅展示已有用例）
    openCaseSelectorModal({
      mode: 'select-existing',   // 强制模式
      excludeImport: true        // 隐藏导入选项
    });
  };

  return (
    <div>
      {/* 操作栏 */}
      <Space>
        <CreateTestSetButton />
        <Button onClick={handleAddCases}>
          从用例库选择  {/* 注意：不是"新建用例" */}
        </Button>
      </Space>

      {/* 测试集列表 */}
      <TestSetTable
        columns={TEST_SET_COLUMNS}
        onRunTest={handleRunTest}
        onViewReport={handleViewReport}
      />

      {/* 用例选择器模态框 */}
      <CaseSelectorModal
        mode="select-existing"
        filter={{ status: 'approved' }}  {/* 仅显示已通过用例 */}
      />

      {/* 运行测试弹窗 */}
      <RunTestModal />
    </div>
  );
};
```

---

### 3.5 页面 4：评估报告页 (`ReportListPage`)

**文件**：`frontend/src/features/rag-eval/pages/ReportListPage.tsx`

#### 功能清单

| 功能 | 说明 | API |
|------|------|-----|
| **报告列表** | 按测试集/日期/状态筛选 | `GET /api/rag/reports` |
| **报告详情** | 指标总览 + 6 层校验 + 推荐模式面板 | `GET /api/rag/reports/:id` |
| **趋势追踪** | 多版本对比 | `GET /api/rag/reports/trend` |
| **导出** | PDF/CSV/JSON | `GET /api/rag/reports/:id/export?format=pdf` |

#### 核心组件结构

```tsx
const ReportListPage: React.FC = () => {
  return (
    <div>
      {/* 筛选栏 */}
      <FilterBar
        testSets={testSets}
        statuses={['completed', 'failed', 'running']}
        dateRange={dateRange}
      />

      {/* 报告列表 */}
      <ReportTable
        columns={REPORT_COLUMNS}
        onViewDetail={handleViewDetail}
        onExport={handleExport}
      />

      {/* 报告详情弹窗 */}
      <ReportDetailModal />

      {/* 趋势图 */}
      <TrendChart />
    </div>
  );
};
```

---

## 四、工作流强制约束实现

### 4.1 前端层面

#### 约束 1：测试集管理页无法创建用例

```tsx
// TestSetManagementPage.tsx
const TestSetManagementPage = () => {
  // 移除所有"新建用例"按钮
  // 导入按钮仅显示"从用例库选择"
  
  const handleAddCases = () => {
    // 打开用例选择器模态框（仅展示已有用例）
    openCaseSelectorModal({
      mode: 'select-existing',  // 强制模式
      excludeImport: true       // 隐藏导入选项
    });
  };

  return (
    <div>
      {/* 注意：没有 <CreateCaseButton /> */}
      <Button onClick={handleAddCases}>
        从用例库选择
      </Button>
    </div>
  );
};
```

#### 约束 2：用例选择器仅显示已有用例

```tsx
// CaseSelectorModal.tsx
const CaseSelectorModal: React.FC<{ mode: string }> = ({ mode }) => {
  const isSelectExisting = mode === 'select-existing';

  return (
    <Modal>
      <Tabs>
        {isSelectExisting ? (
          <TabPane tab="从用例库选择" key="existing">
            <ExistingCaseList />  {/* 仅显示 status=approved 的用例 */}
          </TabPane>
        ) : (
          <>
            <TabPane tab="从用例库选择" key="existing">
              <ExistingCaseList />
            </TabPane>
            <TabPane tab="导入书籍" key="book">
              <UploadBook />
            </TabPane>
            <TabPane tab="导入 JSON" key="json">
              <ImportJson />
            </TabPane>
          </>
        )}
      </Tabs>
    </Modal>
  );
};
```

---

### 4.2 后端层面

**⚠️ 重要：工作流约束必须前后端双重验证**

#### 约束 1：验证用例状态

**文件**：`backend/src/service/rag_test/facade.py`

```python
class RagTestFacade:
    def add_cases_to_test_set(self, test_set_id: str, case_ids: List[str]):
        """添加用例到测试集（验证状态）"""
        
        # 验证用例是否存在且状态为 approved
        cases = self.case_repository.get_by_ids(case_ids)
        for case in cases:
            if case.status != TestCaseStatus.APPROVED:
                raise AppException(
                    status_code=400,
                    code=13010,
                    error_code="CASE_NOT_APPROVED",
                    message=f"用例 {case.id} 未通过审核，无法添加到测试集"
                )
        
        # 添加到测试集
        self.test_set_repository.add_cases(test_set_id, case_ids)
```

#### 约束 2：禁止直接创建用例

**文件**：`backend/src/controller/rag_test_controller.py`

```python
# 移除或禁用直接创建用例的端点
# @router.post("/cases")  # 已禁用
# async def create_case(request: CreateCaseRequest):
#     ...
```

**替代方案**：仅保留草稿审核通过后自动创建用例的逻辑。

**新增端点**：草稿审核通过时自动创建用例
```python
@router.post("/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str):
    """审核通过草稿，自动创建测试用例"""
    # 1. 验证草稿状态
    # 2. 创建 TestCase（status=APPROVED）
    # 3. 更新草稿状态
    # 4. 返回新用例 ID
```

---

## 五、路由配置修改

### 5.1 修改 `frontend/src/router/index.tsx`

```tsx
// 修改后（Tab 聚合式）
<Route path="/rag-eval" element={<RagEvalMainPage />} />
```

**注意**：直接删除旧路由，不保留重定向。

### 5.2 修改菜单配置

**文件**：`frontend/src/app/App.tsx`（ProLayout 菜单配置）

```tsx
// 修改前
{
  name: 'RAG 评估',
  icon: 'ExperimentOutlined',
  children: [
    { name: '测试集管理', path: '/rag-eval/test-sets' },
    { name: '运行历史', path: '/rag-eval/runs' },
  ]
}

// 修改后
{
  name: 'RAG 评估',
  icon: 'ExperimentOutlined',
  path: '/rag-eval',  // 直接指向主布局
}
```

---

## 六、验收标准

### 6.1 功能验收

- [ ] 四个 Tab 页面可正常切换
- [ ] URL 与 Tab 状态同步（`?tab=drafts` 等）
- [ ] 草稿管理页支持书籍/JSON 导入
- [ ] 测试用例管理页**无法**直接创建用例
- [ ] 测试集管理页**无法**导入书籍/JSON
- [ ] 测试集添加用例仅能从已有用例库选择
- [ ] 草稿审核通过后自动流入测试用例库
- [ ] SSE 进度推送正常（无 30 秒超时）

### 6.2 工作流约束验收

| 操作 | 草稿管理页 | 测试用例页 | 测试集页 |
|------|-----------|-----------|---------|
| 导入书籍 | ✅ 允许 | ❌ 禁止 | ❌ 禁止 |
| 导入 JSON | ✅ 允许 | ❌ 禁止 | ❌ 禁止 |
| 新建用例 | ❌ 禁止（通过导入生成草稿） | ❌ 禁止 | ❌ 禁止 |
| 审核草稿 | ✅ 允许 | ❌ 不适用 | ❌ 不适用 |
| 查看用例 | ✅ 允许（仅查看） | ✅ 允许 | ✅ 允许（仅查看） |
| 编辑用例 | ✅ 允许（草稿状态） | ✅ 允许 | ❌ 禁止 |
| 删除用例 | ✅ 允许（草稿状态） | ✅ 允许（软删除） | ❌ 禁止（仅移除关联） |
| 运行测试 | ❌ 不适用 | ❌ 不适用 | ✅ 允许 |

---

## 七、影响分析

| 影响维度 | 说明 |
|----------|------|
| **破坏性变更** | 旧路由已删除，书签失效 |
| **用户体验** | Tab 切换减少页面跳转，提升操作效率 |
| **风险等级** | 中（需测试工作流约束是否严格） |


