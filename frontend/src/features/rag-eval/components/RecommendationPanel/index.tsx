/**
 * 推荐面板入口组件
 */

import ModeSwitcher from './ModeSwitcher';
import RecommendationMode from './RecommendationMode';
import WizardMode from './WizardMode';
import ExpertMode from './ExpertMode';
import LayoutAdapter from './LayoutAdapter';
import ReviewPanel from '../ReviewPanel';
import IgnoredSuggestionsList from '../IgnoredSuggestionsList';
import { useRecommendationPanelStore } from '@/features/rag-eval/stores/recommendationPanelStore';
import { Button, Space } from 'antd';
import { FileTextOutlined, EyeOutlined } from '@ant-design/icons';
import { saveAdoptedAsVersion } from '@/api/rag-eval/tuning';
import type { AdoptedSuggestion } from '../ReviewPanel/types';

interface RecommendationPanelProps {
  reportId: string;
  testSetId: string;
}

export default function RecommendationPanel({ reportId, testSetId }: RecommendationPanelProps) {
  const { mode, adoptedSuggestionsDetails, openReviewPanel, showIgnoredList, toggleIgnoredList, ignoredSuggestionsDetails } = useRecommendationPanelStore();

  const renderMode = () => {
    switch (mode) {
      case 'recommendation':
        return <RecommendationMode reportId={reportId} testSetId={testSetId} />;
      case 'wizard':
        return <WizardMode />;
      case 'expert':
        return <ExpertMode />;
      default:
        return <RecommendationMode reportId={reportId} testSetId={testSetId} />;
    }
  };

  // 保存版本处理函数
  const handleSaveVersion = async (suggestions: AdoptedSuggestion[]) => {
    const requestData = {
      adopted_suggestions: suggestions.map((s) => ({
        id: s.id,
        param_name: s.param_name,
        value: s.custom_value ?? s.suggested_value,
      })),
      description: `基于报告 ${reportId} 的调优建议`,
    };
    await saveAdoptedAsVersion(requestData);
  };

  const panelContent = (
    <div>
      <ModeSwitcher />
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'flex-end' }}>
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={toggleIgnoredList}
        >
          查看已忽略 ({ignoredSuggestionsDetails.length})
        </Button>
        <Button
          type="default"
          icon={<FileTextOutlined />}
          onClick={openReviewPanel}
        >
          审查已采纳项
        </Button>
      </Space>
      {renderMode()}
      {showIgnoredList && (
        <IgnoredSuggestionsList
          testSetId={testSetId}
          reportId={reportId}
        />
      )}
      <ReviewPanel
        adoptedSuggestions={adoptedSuggestionsDetails}
        onSaveVersion={handleSaveVersion}
      />
    </div>
  );

  return <LayoutAdapter>{panelContent}</LayoutAdapter>;
}
