import { createBrowserRouter, Outlet } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { Spin } from 'antd';
import App from '../app/App';
import { HomePage } from '../features/assessment';
import { KnowledgeBasePage } from '../features/documents';
import { KnowledgeSearchPage } from '../features/knowledge';
import { LLMMonitoringDashboard } from '../features/monitoring';
import BookChunksPage from '../pages/BookChunksPage';
import { SystemConfigPage } from '../pages/SystemConfigPage';
import RagEvalMainPage from '../features/rag-eval/pages/RagEvalMainPage';

// 懒加载 RAG 评估页面
const TestSetDetailPage = lazy(() => import('@/features/rag-eval/pages/TestSetDetailPage'));
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
            element: <RagEvalMainPage />,
          },
          {
            path: 'test-sets/:id',
            element: <TestSetDetailPage />,
          },
          {
            path: 'runs/:id',
            element: <RunDetailPage />,
          },
          {
            path: 'reports/:id',
            element: <ReportPage />,
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
        element: <RagEvalLayout />,
        children: [
          { index: true, element: <PromptListPage /> },
          { path: ':key', element: <PromptEditPage /> },
          { path: ':key/versions', element: <PromptVersionComparisonPage /> },
          { path: ':key/test', element: <PromptTestSandboxPage /> },
        ],
      },
      {
        path: 'monitoring',
        element: <LLMMonitoringDashboard />,
      },
    ],
  },
]);
