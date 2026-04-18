/**
 * 审查面板入口组件
 */

import ReviewDrawer from './ReviewDrawer';
import { useRecommendationPanelStore } from '@/features/rag-eval/stores/recommendationPanelStore';
import type { AdoptedSuggestion } from './types';

interface ReviewPanelProps {
  adoptedSuggestions: AdoptedSuggestion[];
  onSaveVersion: (suggestions: AdoptedSuggestion[]) => Promise<void>;
}

export default function ReviewPanel({ adoptedSuggestions, onSaveVersion }: ReviewPanelProps) {
  const { reviewPanelOpen, closeReviewPanel, removeFromAdopted, updateCustomValue } =
    useRecommendationPanelStore();

  const handleRemove = (id: string) => {
    removeFromAdopted(id);
  };

  const handleCustomValueChange = (id: string, value: string) => {
    updateCustomValue(id, value);
  };

  const handleCancelAll = () => {
    // 清空所有已采纳建议
    adoptedSuggestions.forEach((item) => removeFromAdopted(item.id));
  };

  return (
    <>
      <ReviewDrawer
        open={reviewPanelOpen}
        adoptedSuggestions={adoptedSuggestions}
        onClose={closeReviewPanel}
        onRemove={handleRemove}
        onCustomValueChange={handleCustomValueChange}
        onSaveVersion={onSaveVersion}
        onCancelAll={handleCancelAll}
      />
    </>
  );
}
