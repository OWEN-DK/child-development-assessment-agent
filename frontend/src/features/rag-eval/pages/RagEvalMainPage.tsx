/**
 * RAG 评估主布局页
 * 路由: /rag-eval
 * Tab 聚合式布局，URL 与 Tab 状态同步
 *
 * 工作流约束：
 * 草稿管理 → 测试用例 → 测试集管理 → 运行历史 → 评估报告
 * 禁止绕过：测试集不能直接创建用例，所有数据必须先经过草稿审核
 */

import { useEffect, useState } from 'react';
import { Tabs } from 'antd';
import { useSearchParams } from 'react-router-dom';
import DraftManagementPage from './DraftManagementPage';
import TestCaseManagementPage from './TestCaseManagementPage';
import TestSetListPage from './TestSetListPage';
import RunListPage from './RunListPage';
import ReportListPage from './ReportListPage';

type TabKey = 'drafts' | 'cases' | 'test-sets' | 'runs' | 'reports';

const TAB_ITEMS: { key: TabKey; label: string }[] = [
  { key: 'drafts', label: '草稿管理' },
  { key: 'cases', label: '测试用例' },
  { key: 'test-sets', label: '测试集管理' },
  { key: 'runs', label: '运行历史' },
  { key: 'reports', label: '评估报告' },
];

export default function RagEvalMainPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<TabKey>('drafts');

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab && ['drafts', 'cases', 'test-sets', 'runs', 'reports'].includes(tab)) {
      setActiveTab(tab as TabKey);
    }
  }, [searchParams]);

  const handleTabChange = (key: string) => {
    setActiveTab(key as TabKey);
    setSearchParams({ tab: key });
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'drafts':
        return <DraftManagementPage />;
      case 'cases':
        return <TestCaseManagementPage />;
      case 'test-sets':
        return <TestSetListPage />;
      case 'runs':
        return <RunListPage />;
      case 'reports':
        return <ReportListPage />;
      default:
        return <DraftManagementPage />;
    }
  };

  return (
    <div style={{ padding: '24px' }}>
      <Tabs
        activeKey={activeTab}
        onChange={handleTabChange}
        items={TAB_ITEMS}
        destroyInactiveTabPane
        size="large"
        type="card"
      />
      <div style={{ marginTop: 16 }}>
        {renderTabContent()}
      </div>
    </div>
  );
}
