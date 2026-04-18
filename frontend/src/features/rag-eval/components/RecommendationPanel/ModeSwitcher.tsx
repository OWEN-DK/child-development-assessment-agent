/**
 * 模式切换器
 */

import { Tabs } from 'antd';
import type { RecommendationMode } from './types';
import { useRecommendationPanelStore } from '@/store/recommendationPanelStore';

const MODE_TABS = [
  { key: 'recommendation', label: '智能推荐' },
  { key: 'wizard', label: '向导模式' },
  { key: 'expert', label: '专家模式' },
];

export default function ModeSwitcher() {
  const { mode, setMode } = useRecommendationPanelStore();

  return (
    <Tabs
      activeKey={mode}
      onChange={(key) => setMode(key as RecommendationMode)}
      items={MODE_TABS}
      size="small"
      style={{ marginBottom: 16 }}
    />
  );
}
