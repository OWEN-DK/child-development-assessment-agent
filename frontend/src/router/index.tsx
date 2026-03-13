import { createBrowserRouter } from 'react-router-dom';
import App from '../App';
import { HomePage } from '../pages/HomePage';
import KnowledgeBasePage from '../pages/KnowledgeBasePage';
import RagTestPage from '../pages/RagTestPage';
import KnowledgeSearchPage from '../pages/KnowledgeSearchPage';

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
        path: 'rag-test',
        element: <RagTestPage />,
      },
      {
        path: 'knowledge-search',
        element: <KnowledgeSearchPage />,
      },
      // 未来可以添加更多路由，如：
      // { path: 'history', element: <HistoryPage /> },
      // { path: 'profile', element: <ProfilePage /> },
    ],
  },
]);
