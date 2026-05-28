import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Layout, Typography } from 'antd';
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { QuestionInput } from '../components/QuestionInput';
import { ProgressPanel } from '../components/ProgressPanel';
import { ReportViewer } from '../components/ReportViewer';
import { HistorySidebar } from '../components/HistorySidebar';
import { useKnowledgeQA } from '../hooks/useKnowledgeQA';
import { useHistory } from '../hooks/useHistory';
import { useKnowledgeQAStore } from '../stores/knowledgeQAStore';
import type { KnowledgeQAResponse } from '../types';

const { Content } = Layout;
const { Title } = Typography;

export const KnowledgeQAPage: React.FC = () => {
  const { ask, cancel, status, result } = useKnowledgeQA();
  const store = useKnowledgeQAStore();
  const {
    items,
    loading: historyLoading,
    error: historyError,
    loadDetail,
    refresh: refreshHistory,
  } = useHistory();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [historyResult, setHistoryResult] = useState<KnowledgeQAResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const displayResult = historyResult || result;
  const displayStatus = historyResult ? 'done' : status;
  const isLoading = displayStatus === 'submitting' || displayStatus === 'streaming';
  const isRunning = status === 'submitting' || status === 'streaming';

  // 查看历史记录时禁止提交新任务
  const isViewingHistory = historyResult !== null || loadingDetail;

  // 任务完成时延迟刷新历史（等待 DB 写入）
  const prevStatusRef = useRef(status);
  useEffect(() => {
    if (prevStatusRef.current !== 'done' && status === 'done' && result) {
      // SSE complete 可能早于 DB 写入，延迟 500ms 再刷新
      const timer = setTimeout(() => refreshHistory(), 500);
      return () => clearTimeout(timer);
    }
    prevStatusRef.current = status;
  }, [status, result, refreshHistory]);

  // 当前任务完成时，如果正在查看历史记录，自动切回当前结果
  useEffect(() => {
    if (status === 'done' && result && historyResult) {
      setHistoryResult(null);
    }
  }, [status, result, historyResult]);

  const handleHistorySelect = useCallback(async (taskId: string) => {
    // 点击的是当前正在运行的任务 → 返回实时进度视图
    if (taskId === store.taskId && isRunning) {
      setHistoryResult(null);
      return;
    }
    // 不清空当前结果，避免界面闪烁
    setLoadingDetail(true);
    try {
      const detail = await loadDetail(taskId);
      if (detail) {
        setHistoryResult(detail);
      }
    } catch (err) {
      console.error('Failed to load history detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  }, [loadDetail, store.taskId, isRunning]);

  const handleNewChat = useCallback(() => {
    // 如果正在生成中，取消当前任务
    if (isRunning) {
      cancel();
    }
    setHistoryResult(null);
    store.reset();
  }, [store, isRunning, cancel]);

  // 查看历史时包装 ask，阻止重复提交
  const handleSubmit = useCallback(
    (question: string, bookIds?: string[]) => {
      if (isViewingHistory) return;
      ask(question, bookIds);
    },
    [ask, isViewingHistory],
  );

  return (
    <Layout style={{ minHeight: '100vh', background: '#fff' }}>
      {/* 左侧历史记录侧边栏 */}
      <Layout.Sider
        width={280}
        collapsedWidth={0}
        collapsed={!sidebarOpen}
        trigger={null}
        collapsible
        style={{
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
        }}
      >
        <HistorySidebar
          open={sidebarOpen}
          onSelect={handleHistorySelect}
          onNewChat={handleNewChat}
          activeTaskId={store.taskId}
          activeQuestion={store.currentQuestion}
          loading={historyLoading}
          items={items}
          listError={historyError}
          onRefresh={refreshHistory}
          isRunning={isRunning}
        />
      </Layout.Sider>

      <Content style={{ padding: '24px 32px', position: 'relative' }}>
        {/* 侧边栏切换按钮 */}
        <div
          style={{
            position: 'absolute',
            top: 16,
            left: 16,
            zIndex: 10,
          }}
        >
          <span
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{
              cursor: 'pointer',
              fontSize: 18,
              color: '#999',
              padding: '4px 8px',
              borderRadius: 4,
              transition: 'color 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#333';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#999';
            }}
          >
            {sidebarOpen ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
          </span>
        </div>

        <Title level={2} style={{ textAlign: 'center', marginBottom: 32 }}>
          儿童发展知识问答
        </Title>

        <QuestionInput
          onSubmit={handleSubmit}
          onCancel={cancel}
          onReturn={() => setHistoryResult(null)}
          loading={isLoading || isViewingHistory}
          isViewingHistory={isViewingHistory}
          displayQuestion={
            isViewingHistory
              ? historyResult?.question
              : isRunning
                ? store.currentQuestion || undefined
                : undefined
          }
        />

        {(displayStatus === 'streaming' || displayStatus === 'submitting') && (
          <ProgressPanel />
        )}

        {displayStatus === 'error' && store.error && (
          <div style={{ color: '#ff4d4f', marginTop: 16 }}>{store.error}</div>
        )}

        {displayStatus === 'done' && displayResult && (
          <ReportViewer result={displayResult} />
        )}
      </Content>
    </Layout>
  );
};
