import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { Spin } from 'antd';
import App from '../app/App';
import { HomePage } from '../features/assessment';
import { KnowledgeBasePage } from '../features/documents';
import { KnowledgeSearchPage } from '../features/knowledge';
import { LLMMonitoringDashboard } from '../features/monitoring';
import BookChunksPage from '../pages/BookChunksPage';
import { SystemConfigPage } from '../pages/SystemConfigPage';
import {
  RagEvalMainPage,
  DraftPage,
  TestCasePage,
  TestSetPage,
  RunPage,
  ReportPage,
  TuningPage,
} from '@features/rag-eval/pages';

// 懒加载提示词管理页面
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
        element: <RagEvalMainPage />,
        children: [
          { index: true, element: <Navigate to="drafts" replace /> },
          { path: 'drafts', element: <DraftPage /> },
          { path: 'cases', element: <TestCasePage /> },
          { path: 'sets', element: <TestSetPage /> },
          { path: 'runs', element: <RunPage /> },
          { path: 'reports', element: <ReportPage /> },
          { path: 'tuning', element: <TuningPage /> },
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
