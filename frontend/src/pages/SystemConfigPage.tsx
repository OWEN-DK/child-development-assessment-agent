import React, { useEffect, useState, useMemo } from 'react';
import { useConfigStore } from '../store/configStore';
import { DynamicConfigForm } from '../components/config/DynamicConfigForm';
import { ConfigVersionSelector } from '../components/config/ConfigVersionSelector';
import { Button, message, Modal, Space, Tree } from 'antd';
import type { TreeProps } from 'antd';
import styles from './SystemConfigPage.module.scss';

export const SystemConfigPage: React.FC = () => {
  const {
    configFields,
    draftChanges,
    isLoading,
    isSaving,
    loadConfig,
    loadVersions,
    saveConfig,
    resetToFactory,
  } = useConfigStore();

  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  useEffect(() => {
    loadConfig();
    loadVersions();
  }, []);

  // 配置分类映射 - 适配新的配置层级结构
  const categoryMapping: Record<string, string> = {
    'app': '📦 应用设置',
    'logging': '日志配置',
    'paths': '路径配置',
    'models': '🤖 AI模型',
    'llm': 'LLM模型',
    'embedding': 'Embedding模型',
    'ml_scoring': 'ML评分模型',
    'rag': '📚 RAG知识库',
    'core': '核心设置',
    'retrieval': '检索配置',
    'chunking': '分块配置',
    'vector_store': '向量存储',
    'pageindex': 'PageIndex索引',
    'pipeline': '导入流水线',
    'rules': '⚙️ 业务规则',
    'validation': '校验规则',
    'assessment': '评估规则',
    'scoring': '评分规则',
    'preprocessing': '预处理规则',
    'metadata': '元数据规则',
    'other': '其他配置'
  };

  // Build tree data for sidebar
  const treeData = useMemo<any[]>(() => {
    const root: any[] = [
      {
        title: '全部配置',
        key: 'all',
        isLeaf: true,
      }
    ];

    // Group categories by main category
    const categoryGroups = configFields.reduce((groups, field) => {
      const fullCategory = field.category || 'other';
      const [mainCategory, subCategory] = fullCategory.split('.', 2);
      
      if (!groups[mainCategory]) {
        groups[mainCategory] = new Set();
      }
      
      if (subCategory) {
        groups[mainCategory].add(subCategory);
      }
      
      return groups;
    }, {} as Record<string, Set<string>>);

    // 预设的分类顺序，按照我们新的层级结构排序
    const categoryOrder = ['app', 'models', 'rag', 'rules', 'other'];
    
    // Build tree nodes
    categoryOrder.forEach(mainCategory => {
      if (!categoryGroups[mainCategory]) return;
      
      const subCategories = categoryGroups[mainCategory];
      const mainTitle = categoryMapping[mainCategory] || mainCategory;
      
      if (subCategories.size === 0) {
        root.push({
          title: mainTitle,
          key: mainCategory,
          isLeaf: true,
        });
      } else {
        // 子分类排序
        const subCategoryOrder: Record<string, number> = {
          // 应用设置子分类
          'app': 1, 'logging': 2, 'paths': 3,
          // AI模型子分类
          'llm': 1, 'embedding': 2, 'ml_scoring': 3,
          // RAG子分类
          'core': 1, 'retrieval': 2, 'chunking': 3, 'vector_store': 4, 'pageindex': 5, 'pipeline': 6,
          // 业务规则子分类
          'validation': 1, 'assessment': 2, 'scoring': 3, 'preprocessing': 4, 'metadata':5
        };
        
        const children = Array.from(subCategories)
          .sort((a, b) => (subCategoryOrder[a] || 99) - (subCategoryOrder[b] || 99))
          .map(subCategory => {
            const subTitle = categoryMapping[subCategory] || subCategory;
            return {
              title: subTitle,
              key: `${mainCategory}.${subCategory}`,
              isLeaf: true,
            };
          });
        
        root.push({
          title: mainTitle,
          key: mainCategory,
          children: children as any,
          isLeaf: false,
        });
      }
    });

    return root;
  }, [configFields]);

  const handleTreeSelect: TreeProps['onSelect'] = (selectedKeys) => {
    if (selectedKeys.length > 0) {
      setSelectedCategory(selectedKeys[0] as string);
    }
  };

  const handleSave = async () => {
    Modal.confirm({
      title: '保存配置',
      content: '确定要保存当前配置修改吗？这将生成新的配置版本。',
      onOk: async () => {
        try {
          await saveConfig('Manual update from config page');
          message.success('配置已保存');
        } catch (error) {
          message.error('保存失败');
        }
      },
    });
  };

  const handleReset = () => {
    Modal.confirm({
      title: '恢复出厂设置',
      content: '确定要恢复到.env.dev的默认配置吗？',
      onOk: async () => {
        try {
          await resetToFactory();
          message.success('已恢复出厂设置');
        } catch (error) {
          message.error('恢复失败');
        }
      },
    });
  };

  return (
    <div className={styles.container}>
      <div className={styles.sidebar}>
        <h2>配置分类</h2>
        <Tree
          treeData={treeData}
          defaultExpandAll
          selectedKeys={[selectedCategory]}
          onSelect={handleTreeSelect}
          className={styles.categoryTree}
          showLine
        />

        <ConfigVersionSelector />
      </div>

      <div className={styles.main}>
        <div className={styles.header}>
          <h1>系统全局配置</h1>
          <Space>
            <Button onClick={handleReset} danger>
              恢复出厂设置
            </Button>
            <Button
              type="primary"
              onClick={handleSave}
              loading={isSaving}
              disabled={Object.keys(draftChanges).length === 0}
            >
              保存配置 ({Object.keys(draftChanges).length} 项修改)
            </Button>
          </Space>
        </div>

        {isLoading && <div className={styles.loading}>加载中...</div>}

        <DynamicConfigForm
          fields={configFields}
          category={selectedCategory === 'all' ? undefined : selectedCategory}
        />
      </div>
    </div>
  );
};
