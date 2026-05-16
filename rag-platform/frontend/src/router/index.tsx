import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Spin } from 'antd'

// 占位组件
const Dashboard = () => <div>RAG Platform Dashboard</div>
const NotFound = () => <div>404 - 页面不存在</div>

// Phase 5: 管道编辑器（lazy 加载）
const PipelineListPage = lazy(() => import('@/features/pipeline/pages/PipelineListPage'))
const PipelineWorkbench = lazy(() => import('@/features/pipeline/pages/PipelineWorkbench'))

// Phase 6: 知识库管理（lazy 加载）
const KnowledgeListPage = lazy(() => import('@/features/knowledge/pages/KnowledgeListPage'))
const KnowledgeDetailPage = lazy(() => import('@/features/knowledge/pages/KnowledgeDetailPage'))
const TestDataPage = lazy(() => import('@/features/knowledge/pages/TestDataPage'))

// Phase 9: 管理页面（lazy 加载）
const TenantListPage = lazy(() => import('@/features/admin/pages/TenantListPage'))
const UserListPage = lazy(() => import('@/features/admin/pages/UserListPage'))
const RoleListPage = lazy(() => import('@/features/admin/pages/RoleListPage'))

/** 加载占位 */
const Loading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
    <Spin size="large" />
  </div>
)

function AppRouter() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        {/* 首页 */}
        <Route path="/" element={<Dashboard />} />

        {/* Phase 5: 管道管理 */}
        <Route path="/pipelines" element={<PipelineListPage />} />
        <Route path="/pipelines/:id" element={<Navigate to="edit" replace />} />
        <Route path="/pipelines/:id/edit" element={<PipelineWorkbench />} />
        <Route path="/pipelines/:id/evaluate" element={<PipelineWorkbench />} />
        <Route path="/pipelines/:id/publish" element={<PipelineWorkbench />} />

        {/* Phase 6: 知识库管理 */}
        <Route path="/knowledge" element={<KnowledgeListPage />} />
        <Route path="/knowledge/test-data" element={<Navigate to="cases" replace />} />
        <Route path="/knowledge/test-data/cases" element={<TestDataPage />} />
        <Route path="/knowledge/test-data/sets" element={<TestDataPage />} />
        <Route path="/knowledge/test-data/drafts" element={<TestDataPage />} />
        <Route path="/knowledge/:id" element={<KnowledgeDetailPage />} />
        <Route path="/knowledge/:id/documents" element={<KnowledgeDetailPage />} />
        <Route path="/knowledge/:id/chunks" element={<KnowledgeDetailPage />} />
        <Route path="/knowledge/:id/permissions" element={<KnowledgeDetailPage />} />
        <Route path="/knowledge/:id/settings" element={<KnowledgeDetailPage />} />

        {/* Phase 9: 管理页面 */}
        <Route path="/admin/tenants" element={<TenantListPage />} />
        <Route path="/admin/users" element={<UserListPage />} />
        <Route path="/admin/roles" element={<RoleListPage />} />

        {/* 404 */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}

export default AppRouter
