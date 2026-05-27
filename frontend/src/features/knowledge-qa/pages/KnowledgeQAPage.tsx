import React from 'react';
import { Layout, Typography } from 'antd';
import { QuestionInput } from '../components/QuestionInput';
import { ProgressPanel } from '../components/ProgressPanel';
import { ReportViewer } from '../components/ReportViewer';
import { useKnowledgeQA } from '../hooks/useKnowledgeQA';
import { useKnowledgeQAStore } from '../stores/knowledgeQAStore';

const { Content } = Layout;
const { Title } = Typography;

export const KnowledgeQAPage: React.FC = () => {
  const { ask, status, result } = useKnowledgeQA();
  const store = useKnowledgeQAStore();

  return (
    <Layout style={{ minHeight: '100vh', background: '#fff' }}>
      <Content style={{ padding: '40px 32px' }}>
        <Title level={2} style={{ textAlign: 'center', marginBottom: 32 }}>
          儿童发展知识问答
        </Title>

        <QuestionInput
          onSubmit={ask}
          loading={status === 'submitting' || status === 'streaming'}
        />

        {(status === 'streaming' || status === 'submitting') && <ProgressPanel />}

        {status === 'error' && store.error && (
          <div style={{ color: '#ff4d4f', marginTop: 16 }}>{store.error}</div>
        )}

        {status === 'done' && result && (
          <ReportViewer result={result} />
        )}
      </Content>
    </Layout>
  );
};
