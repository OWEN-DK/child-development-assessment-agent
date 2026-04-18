import React from 'react';
import { Tree } from 'antd';
import { CATEGORY_TREE } from './constants';

interface SidebarProps {
  onSelectCategory: (key: string) => void;
  selectedCategory: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  onSelectCategory,
  selectedCategory
}) => {
  const handleSelect = (selectedKeys: React.Key[]) => {
    if (selectedKeys.length > 0) {
      onSelectCategory(selectedKeys[0] as string);
    }
  };

  return (
    <div style={{ padding: '16px 12px' }}>
      <h3 style={{ marginBottom: 16, fontSize: 16 }}>配置分类</h3>
      <Tree
        treeData={CATEGORY_TREE}
        defaultExpandAll
        selectedKeys={[selectedCategory]}
        onSelect={handleSelect}
        showLine
        style={{ fontSize: 14 }}
      />
    </div>
  );
};
