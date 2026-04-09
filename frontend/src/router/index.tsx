import { createBrowserRouter } from 'react-router-dom';
import App from '../App';
import { HomePage } from '../features/assessment';
import { KnowledgeBasePage } from '../features/documents';
import { RagEvaluationPage } from '../features/rag-evaluation';
import { KnowledgeSearchPage } from '../features/knowledge';
import BookChunksPage from '../pages/BookChunksPage';
import { SystemConfigPage } from '../pages/SystemConfigPage';

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
        path: 'rag-evaluation',
        element: <RagEvaluationPage />,
      },
      {
        path: 'book-chunks/:fileHash/:fileName',
        element: <BookChunksPage />,
      },
      {
        path: 'system-config',
        element: <SystemConfigPage />,
      },
    ],
  },
]);
