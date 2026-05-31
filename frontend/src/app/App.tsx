import { ConfigProvider, App as AntdApp } from 'antd';
import { PageContainer, ProLayout } from '@ant-design/pro-components';
import { Outlet, useLocation, Link } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '../lib/queryClient';
import {
  ExperimentOutlined,
  BookOutlined,
  ApartmentOutlined,
  SettingOutlined,
  EditOutlined,
  FolderOpenOutlined,
  SearchOutlined,
  ThunderboltOutlined,
  DashboardOutlined,
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
              { path: '/', name: '知识问答', icon: <ThunderboltOutlined /> },
              {
                path: '/knowledge-lib',
                name: '知识库',
                icon: <FolderOpenOutlined />,
                children: [
                  { path: '/knowledge-base', name: '文档管理', icon: <FolderOpenOutlined /> },
                  { path: '/knowledge-search', name: '内容搜索', icon: <SearchOutlined /> },
                  { path: '/curation/books', name: '书籍管理', icon: <BookOutlined /> },
                  { path: '/curation/graph', name: '知识图谱', icon: <ApartmentOutlined /> },
                  { path: '/curation/custom-knowledge', name: '自定义知识', icon: <EditOutlined /> },
                ],
              },
              {
                path: '/quality',
                name: '质量保障',
                icon: <ExperimentOutlined />,
                children: [
                  { path: '/rag-eval', name: 'RAG 评估', icon: <ExperimentOutlined /> },
                  { path: '/prompt-management', name: '提示词管理', icon: <EditOutlined /> },
                ],
              },
              {
                path: '/sys',
                name: '系统',
                icon: <SettingOutlined />,
                children: [
                  { path: '/monitoring', name: 'LLM 监控', icon: <DashboardOutlined /> },
                  { path: '/system-config', name: '系统配置', icon: <SettingOutlined /> },
                ],
              },
            ]}
            menuItemRender={(item, dom) => (
              <Link to={item.path || '/'} key={item.path}>
                {dom}
              </Link>
            )}
          >
            <PageContainer
              subTitle={false}
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
