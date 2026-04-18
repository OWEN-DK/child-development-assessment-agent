import React from 'react';
import { Tabs } from 'antd';
import { CATEGORY_TREE } from './constants';

interface MobileNavProps {
  selectedCategory: string;
  onSelectCategory: (key: string) => void;
}

// 图标映射
const CATEGORY_ICONS: Record<string, string> = {
  credentials: '🔑',
  ai_models: '🤖',
  rag: '📚',
  rules: '⚙️',
  system: '📦'
};

export const MobileNav: React.FC<MobileNavProps> = ({
  selectedCategory,
  onSelectCategory
}) => {
  // 仅显示顶级分类
  const topCategories = CATEGORY_TREE.filter(c => !c.key.includes('.'));

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 1000,
      backgroundColor: '#fff',
      boxShadow: '0 -2px 8px rgba(0, 0, 0, 0.1)'
    }}>
      <Tabs
        activeKey={selectedCategory}
        onChange={onSelectCategory}
        items={topCategories.map(cat => ({
          key: cat.key,
          label: (
            <span>
              {CATEGORY_ICONS[cat.key] || '📋'} {cat.title.replace(/[^\u4e00-\u9fa5]/g, '')}
            </span>
          )
        }))}
        size="small"
        style={{ marginBottom: 0 }}
      />
    </div>
  );
};
