import { ConfigProvider, App as AntdApp } from 'antd';
import { PageContainer, ProLayout } from '@ant-design/pro-components';
import { Outlet, useLocation, Link } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '../lib/queryClient';
import {
  ExperimentOutlined,
  AuditOutlined,
  BookOutlined,
  ApartmentOutlined,
  ClockCircleOutlined,
  LinkOutlined,
} from '@ant-design/icons';

function App() {
  const location = useLocation();

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider>
        <AntdApp>
          <ProLayout
            title="儿童发展评估助手"
            layout="top"
            navTheme="light"
            contentWidth="Fluid"
            fixedHeader
            token={{
              header: {
                colorBgHeader: '#fff',
              },
            }}
            location={{
              pathname: location.pathname,
            }}
            menuDataRender={() => [
              { path: '/', name: '知识问答' },
              { path: '/knowledge-base', name: '知识库' },
              { path: '/knowledge-search', name: '内容搜索' },
              { path: '/rag-eval', name: 'RAG 评估', icon: <ExperimentOutlined /> },
              { path: '/prompt-management', name: '提示词管理' },
              { path: '/monitoring', name: 'LLM监控' },
              {
                path: '/curation',
                name: '知识管理',
                icon: <AuditOutlined />,
                children: [
                  { path: '/curation/books', name: '📚 书籍管理', icon: <BookOutlined /> },
                  { path: '/curation/bind', name: '🔗 绑定书籍', icon: <LinkOutlined /> },
                  { path: '/curation/graph', name: '🕸️ 知识图谱', icon: <ApartmentOutlined /> },
                  { path: '/curation/pending', name: '⏱️ 待提炼队列', icon: <ClockCircleOutlined /> },
                ],
              },
              { path: '/system-config', name: '系统配置' },
            ]}
            menuItemRender={(item, dom) => (
              <Link to={item.path || '/'} key={item.path}>
                {dom}
              </Link>
            )}
          >
            <PageContainer
              subTitle="基于知识库的智能问答与运动方案推荐"
            >
              <Outlet />
            </PageContainer>
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'rgba(0, 0, 0, 0.45)' }}>
               Child Development Assessment Agent ©{new Date().getFullYear()} Created with Ant Design & ProComponents
            </div>
          </ProLayout>
        </AntdApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

export default App;
