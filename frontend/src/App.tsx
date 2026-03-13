import { ConfigProvider, App as AntdApp } from 'antd';
import { PageContainer, ProLayout } from '@ant-design/pro-components';
import { Outlet, useLocation, Link } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';

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
            contentWidth="Fixed"
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
              { path: '/', name: '首页' },
              { path: '/knowledge-base', name: '知识库' },
              { path: '/knowledge-search', name: '内容搜索' },
              { path: '/rag-test', name: '回撤测试' },
              // { path: '/history', name: '历史记录' },
            ]}
            menuItemRender={(item, dom) => (
              <Link to={item.path || '/'} key={item.path}>
                {dom}
              </Link>
            )}
          >
            <PageContainer
              subTitle="基于 AI 的个性化发展评估与训练计划分析"
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
