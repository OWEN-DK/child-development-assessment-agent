# Phase 2A.3: 前端UI增强

> **前置文档:** [Overview](./02-phase-2a-00-overview.md) | [测试用例生成优化](./02-phase-2a-04-test-case-generation.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 1人天

### 🟡 2.5 前端UI修复与增强（⏳ 完全待实现，1人天）
> UX 要求：操作路径不超过 3 步，批量操作响应时间 < 2s

#### Task 2.5.0: 定义 RAG 测试 API 客户端
**Files:**
- Create: `src/api/rag-test.ts`

- [ ] 实现全量 API 客户端方法：
```typescript
// src/api/rag-test.ts
import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1/rag/test' })

export const ragTestApi = {
  // 测试集管理
  getTestSets: (params: { page: number; limit: number; status?: string }) => api.get('/test-sets', { params }),
  createTestSet: (data: { name: string; description?: string }) => api.post('/test-sets', data),
  updateTestSet: (id: number, data: Partial<TestSet>) => api.put(`/test-sets/${id}`, data),
  deleteTestSet: (id: number) => api.delete(`/test-sets/${id}`),
  getTestSetMetricsHistory: (id: number) => api.get(`/test-sets/${id}/metrics-history`),
  
  // 测试集-用例关联管理
  getTestSetCases: (id: number, params: { page: number; limit: number }) => api.get(`/test-sets/${id}/cases`, { params }),
  addCasesToTestSet: (id: number, data: { case_ids: number[] }) => api.post(`/test-sets/${id}/cases`, data),
  removeCaseFromTestSet: (testSetId: number, caseId: number) => api.delete(`/test-sets/${testSetId}/cases/${caseId}`),
  getCaseTestSets: (caseId: number) => api.get(`/cases/${caseId}/test-sets`),  // 反向查询：用例属于哪些测试集
  
  // 测试执行
  runTest: (data: { test_set_ids: number[]; custom_case_ids?: number[] }) => api.post('/run', data),
  getTestRun: (id: number) => api.get(`/runs/${id}`),
  getTestRunResults: (runId: number) => api.get(`/runs/${runId}/results`),
  
  // 报告管理
  getReport: (runId: number) => api.get(`/reports/${runId}`),
  exportReport: (runId: number, format: 'markdown' | 'pdf' | 'json') => api.get(`/reports/${runId}/export`, { params: { format } }),
  deleteReport: (runId: number) => api.delete(`/reports/${runId}`),
  
  // 测试用例管理
  getTestCases: (params: { page: number; limit: number; domain?: string }) => api.get('/cases', { params }),
  createTestCase: (data: { query: string; domain: string; age_min?: number; age_max?: number; expected_keywords?: string[]; description?: string }) => api.post('/cases', data),
  generateDrafts: (data: { document_id: number; count: number; age_min: number; age_max: number }) => api.post('/cases/drafts/generate', data),
  reviewDraft: (id: number, action: 'approve' | 'reject') => api.post(`/cases/drafts/${id}/review`, { action }),
  approveDraftToCase: (id: number) => api.post(`/cases/drafts/${id}/approve-to-case`),
}
```

> **后端需要新增对应的API接口（src/controller/rag_test_controller.py）**:
> ```python
> # 测试集管理
> @router.get("/test-sets")
> async def list_test_sets(page: int = 1, limit: int = 10, status: str = None): ...
> @router.post("/test-sets")
> async def create_test_set(data: TestSetCreate): ...
> @router.put("/test-sets/{id}")
> async def update_test_set(id: int, data: TestSetUpdate): ...
> @router.delete("/test-sets/{id}")
> async def delete_test_set(id: int): ...
> @router.get("/test-sets/{id}/metrics-history")
> async def get_test_set_metrics_history(id: int): ...
> 
> # 测试集-用例关联管理
> @router.get("/test-sets/{id}/cases")
> async def list_test_set_cases(id: int, page: int = 1, limit: int = 20): ...
> @router.post("/test-sets/{id}/cases")
> async def add_cases_to_test_set(id: int, data: LinkCasesRequest): ...  # data: {case_ids: List[int]}
> @router.delete("/test-sets/{test_set_id}/cases/{case_id}")
> async def remove_case_from_test_set(test_set_id: int, case_id: int): ...
> @router.get("/cases/{case_id}/test-sets")
> async def get_case_test_sets(case_id: int): ...  # 反向查询：用例属于哪些测试集
> 
> # 测试运行管理
> @router.get("/runs/{id}")
> async def get_test_run(id: int): ...
> @router.get("/runs/{run_id}/results")
> async def get_test_run_results(run_id: int): ...
> 
> # 报告管理
> @router.get("/reports/{run_id}")
> async def get_report(run_id: int): ...
> @router.get("/reports/{run_id}/export")
> async def export_report(run_id: int, format: ReportExportFormat): ...
> @router.delete("/reports/{run_id}")
> async def delete_report(run_id: int): ...
> 
> # 测试用例管理
> @router.get("/cases")
> async def list_test_cases(page: int = 1, limit: int = 10, domain: str = None): ...
> @router.post("/cases")
> async def create_test_case(data: TestCaseCreate): ...  # 手动创建测试用例
> @router.post("/cases/drafts/generate")
> async def generate_drafts(data: DraftGenerateRequest): ...
> @router.post("/cases/drafts/{id}/review")
> async def review_draft(id: int, action: str): ...
> @router.post("/cases/drafts/{id}/approve-to-case")
> async def approve_draft_to_case(id: int): ...
> ```

> **TestSet模型新增status字段（src/models/rag.py）**:
> ```python
> class TestSetStatus(str, enum.Enum):
>     DRAFT = "draft"
>     READY = "ready"
>     RUNNING = "running"
>     ARCHIVED = "archived"
> 
> class TestSet(Base):
>     __tablename__ = "test_sets"
>     ...
>     status = Column(SAEnum(TestSetStatus), nullable=False, default=TestSetStatus.DRAFT, comment="测试集状态")
> ```

---

#### Task 2.5.1: 修复TestSetManager数据流
**Files:**
- Modify: `src/features/rag-test/components/TestSetManager.tsx`
- Test: `src/features/rag-test/components/__tests__/TestSetManager.test.tsx`

- [ ] 接通全量API：`getTestSets` / `createTestSet` / `updateTestSet` / `deleteTestSet`
- [ ] 实现列表分页、搜索、按状态筛选功能
- [ ] 新增测试集状态标签（草稿/就绪/运行中/已删除）
- [ ] 支持直接从列表页跳转执行测试集

---

#### Task 2.5.2: 实现CasePicker组件
**Files:**
- Create: `src/features/rag-test/components/CasePicker.tsx`
- Test: `src/features/rag-test/components/__tests__/CasePicker.test.tsx`

- [ ] 双库选择：支持从正式用例库和草稿库选择用例
  - **正式用例库**: 调用 `getTestCases` 获取已审核用例，选中后调用 `addCasesToTestSet` 直接关联
  - **草稿库**: 调用草稿接口获取待审核草稿，选中后调用 `approveDraftToCase` 转正再关联
- [ ] 批量操作：全选/反选/按领域筛选/按年龄区间筛选
- [ ] 跨页选择：选择状态在分页切换时保持
- [ ] 草稿自动转正：选中的草稿在确认后自动转为正式用例并关联到当前测试集
- [ ] **反向查询**：查看某个测试案例属于哪些测试集
  - 新增 API: `GET /api/v1/rag/test/cases/{id}/test-sets`
  - 前端展示：用例详情面板中增加"所属测试集"列表
  - 支持点击跳转到对应测试集详情页

---

#### Task 2.5.3: 增强测试集详情页
**Files:**
- Modify: `src/features/rag-test/pages/TestSetDetailPage.tsx`
- Test: `src/features/rag-test/pages/__tests__/TestSetDetailPage.test.tsx`

- [ ] 展示已关联的用例列表，支持分页、搜索、排序
- [ ] 支持单个/批量移除用例，二次确认防止误删（调用 `removeCaseFromTestSet`）
- [ ] 新增测试集执行入口，直接跳转测试执行页面
- [ ] 展示历史执行记录与MRR/NDCG/Precision/Recall指标趋势图（使用ECharts）
- [ ] **新增"添加用例"按钮**，弹出 CasePicker 组件，支持四种添加途径：
  1. **从正式用例库选择**: 浏览已有用例，勾选后调用 `addCasesToTestSet` 关联
  2. **从草稿库选择**: 浏览待审核草稿，勾选后调用 `approveDraftToCase` 转正并关联
  3. **手动创建**: 打开表单对话框，填写后调用 `createTestCase` + `addCasesToTestSet` 创建并关联
  4. **文档导入生成**: 跳转到文档导入页面，生成草稿后审核归入当前测试集
- [ ] **手动创建测试案例表单**:
  - 表单字段：query (必填), domain (下拉选择六大领域), age_min (数字), age_max (数字), expected_keywords (标签输入), description (文本域)
  - 提交后自动关联到当前测试集

---

**上一阶段：** [测试用例生成优化](./02-phase-2a-04-test-case-generation.md)  
**返回 Overview:** [Overview](./02-phase-2a-00-overview.md)
