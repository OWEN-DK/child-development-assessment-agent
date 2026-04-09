import React, { useEffect, useState } from 'react';
import { useConfigStore } from '../store/configStore';
import { DynamicConfigForm } from '../components/config/DynamicConfigForm';
import { ConfigVersionSelector } from '../components/config/ConfigVersionSelector';
import { Button, message, Modal, Space } from 'antd';
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

  const categories = [
    'all',
    ...new Set(configFields.map((f) => f.category)),
  ];

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
        <ul className={styles.categoryList}>
          {categories.map((cat) => (
            <li
              key={cat}
              className={selectedCategory === cat ? styles.active : ''}
              onClick={() => setSelectedCategory(cat)}
            >
              {cat === 'all' ? '全部配置' : cat}
            </li>
          ))}
        </ul>

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
