import { createBrowserRouter } from 'react-router-dom';
import App from '../App';
import { HomePage } from '../pages/HomePage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      // 未来可以添加更多路由，如：
      // { path: 'history', element: <HistoryPage /> },
      // { path: 'profile', element: <ProfilePage /> },
    ],
  },
]);
