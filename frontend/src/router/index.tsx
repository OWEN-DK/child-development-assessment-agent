import { createBrowserRouter } from 'react-router-dom';
import App from '../App';
import { HomePage } from '../features/assessment';
import { KnowledgeBasePage } from '../features/documents';
import { RagTestPage } from '../features/rag-test';
import { KnowledgeSearchPage } from '../features/knowledge';
import BookChunksPage from '../pages/BookChunksPage';

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
        path: 'rag-test',
        element: <RagTestPage />,
      },
      {
        path: 'book-chunks/:fileHash/:fileName',
        element: <BookChunksPage />,
      },
    ],
  },
]);
