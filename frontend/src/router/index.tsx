import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { Spin } from 'antd';
import App from '../App';
import { HomePage } from '../features/assessment';
import { KnowledgeBasePage } from '../features/documents';
import { KnowledgeSearchPage } from '../features/knowledge';
import { PromptManagementPage } from '../features/prompts';
import { LLMMonitoringDashboard } from '../features/monitoring';
import BookChunksPage from '../pages/BookChunksPage';
import { SystemConfigPage } from '../pages/SystemConfigPage';

// 懒加载 RAG 评估页面
const TestSetListPage = lazy(() => import('@/features/rag-eval/pages/TestSetListPage'));
const TestSetDetailPage = lazy(() => import('@/features/rag-eval/pages/TestSetDetailPage'));
const DraftReviewPage = lazy(() => import('@/features/rag-eval/pages/DraftReviewPage'));
const RunListPage = lazy(() => import('@/features/rag-eval/pages/RunListPage'));
const RunDetailPage = lazy(() => import('@/features/rag-eval/pages/RunDetailPage'));
const ReportPage = lazy(() => import('@/features/rag-eval/pages/ReportPage'));
const PromptListPage = lazy(() => import('@/features/rag-eval/pages/PromptListPage'));
const PromptEditPage = lazy(() => import('@/features/rag-eval/pages/PromptEditPage'));
const PromptVersionComparisonPage = lazy(() => import('@/features/rag-eval/pages/PromptVersionComparisonPage'));
const PromptTestSandboxPage = lazy(() => import('@/features/rag-eval/pages/PromptTestSandboxPage'));

// 布局组件
const RagEvalLayout = () => (
  <Suspense fallback={<Spin size="large" style={{ display: 'block', marginTop: 100 }} />}>
    <Outlet />
  </Suspense>
);

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'knowledge-base',
        element: <KnowledgeBasePage />,
      },
      {
        path: 'knowledge-search',
        element: <KnowledgeSearchPage />,
      },
      {
        path: 'rag-eval',
        element: <RagEvalLayout />,
        children: [
          {
            index: true,
            element: <Navigate to="/rag-eval/test-sets" replace />,
          },
          {
            path: 'test-sets',
            children: [
              { index: true, element: <TestSetListPage /> },
              { path: ':id', element: <TestSetDetailPage /> },
              { path: ':id/drafts', element: <DraftReviewPage /> },
            ],
          },
          {
            path: 'runs',
            children: [
              { index: true, element: <RunListPage /> },
              { path: ':id', element: <RunDetailPage /> },
            ],
          },
          {
            path: 'reports/:id',
            element: <ReportPage />,
          },
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
        path: 'book-chunks/:fileHash/:fileName',
        element: <BookChunksPage />,
      },
      {
        path: 'system-config',
        element: <SystemConfigPage />,
      },
      {
        path: 'prompt-management',
        element: <PromptManagementPage />,
      },
      {
        path: 'monitoring',
        element: <LLMMonitoringDashboard />,
      },
    ],
  },
]);
