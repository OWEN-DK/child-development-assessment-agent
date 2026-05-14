import { lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'

// 占位组件（Phase 5/6/9 替换为真实页面）
const Dashboard = () => <div>RAG Platform Dashboard</div>
const NotFound = () => <div>404 - 页面不存在</div>

// Phase 5: 管道编辑器（lazy 加载）
// const PipelineListPage = lazy(() => import('@/features/pipeline/pages/PipelineListPage'))
// const PipelineWorkbench = lazy(() => import('@/features/pipeline/pages/PipelineWorkbench'))

// Phase 6: 知识库管理（lazy 加载）
// const KnowledgeBaseListPage = lazy(() => import('@/features/knowledgeBase/pages/KnowledgeBaseListPage'))
// const KnowledgeBaseDetailPage = lazy(() => import('@/features/knowledgeBase/pages/KnowledgeBaseDetailPage'))

// Phase 9: 超管页面（lazy 加载）
// const TenantListPage = lazy(() => import('@/features/admin/pages/TenantListPage'))

function AppRouter() {
  return (
    <Routes>
      {/* 首页 */}
      <Route path="/" element={<Dashboard />} />

      {/* Phase 5: 管道管理 */}
      {/* <Route path="/pipelines" element={<PipelineListPage />} /> */}
      {/* <Route path="/pipelines/:id/*" element={<PipelineWorkbench />} /> */}

      {/* Phase 6: 知识库管理 */}
      {/* <Route path="/knowledge" element={<KnowledgeBaseListPage />} /> */}
      {/* <Route path="/knowledge/:id" element={<KnowledgeBaseDetailPage />} /> */}

      {/* Phase 9: 超管页面 */}
      {/* <Route path="/admin/tenants" element={<TenantListPage />} /> */}

      {/* 404 */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

export default AppRouter
