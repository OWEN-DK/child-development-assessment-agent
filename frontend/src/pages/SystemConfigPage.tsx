import React, { useEffect, useState, useMemo } from 'react';
import { useConfig } from '../features/config/hooks/useConfig';
import { DynamicConfigForm } from '../components/config/DynamicConfigForm';
import { WizardMode } from '../components/config/WizardMode';
import { ConfigVersionSelector } from '../components/config/ConfigVersionSelector';
import { Sidebar } from '../components/config/Sidebar';
import { TopToolbar } from '../components/config/TopToolbar';
import { MobileNav } from '../components/config/MobileNav';
import { ConfigErrorBoundary } from '../components/config/ConfigErrorBoundary';
import { Modal, Button } from 'antd';
import { notification } from '@shared/lib/notification';
import { getBreakpoint } from '../components/config/constants';
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
    modePreference,
    switchMode,
  } = useConfig();

  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);

  // 监听窗口大小变化
  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    loadConfig();
    loadVersions();
  }, []);

  const breakpoint = getBreakpoint(windowWidth);
  const isMobile = breakpoint === 'mobile';

  const handleSave = async () => {
    Modal.confirm({
      title: '保存配置',
      content: '确定要保存当前配置修改吗？这将生成新的配置版本。',
      onOk: async () => {
        try {
          await saveConfig('Manual update from config page');
          notification.success('配置已保存');
        } catch (error) {
          notification.error('保存失败');
        }
      },
    });
  };

  const handleReset = () => {
    Modal.confirm({
      title: '恢复出厂设置',
      content: '确定要恢复到.env.dev的默认配置吗？此操作将清除所有自定义配置。',
      okText: '确认恢复',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await resetToFactory();
          notification.success('已恢复出厂设置');
        } catch (error) {
          notification.error('恢复失败');
        }
      },
    });
  };

  const handleSearch = (query: string) => {
    console.log('搜索:', query);
  };

  const handleSelectSearch = (key: string) => {
    console.log('选中搜索:', key);
  };

  const changeCount = Object.keys(draftChanges).length;
  const hasChanges = changeCount > 0;

  // 映射 UI 分类 Key 到后端 Category
  const effectiveCategory = useMemo(() => {
    if (selectedCategory === 'all') return undefined;
    // 场景模型 UI Key 映射到后端 models.llm
    if (selectedCategory === 'models.llm.scenes') return 'models.llm';
    // 其他 UI Key 直接作为后端 category（已修正为与后端一致）
    return selectedCategory;
  }, [selectedCategory]);

  const handleSwitchMode = () => {
    switchMode(modePreference === 'expert' ? 'wizard' : 'expert');
  };

  return (
    <ConfigErrorBoundary>
      <div className={styles.container}>
        {/* 侧边栏（桌面端显示，仅专家模式） */}
        {!isMobile && modePreference === 'expert' && (
          <div className={styles.sidebar}>
            <Sidebar
              selectedCategory={selectedCategory}
              onSelectCategory={setSelectedCategory}
            />
            <ConfigVersionSelector />
            
            {/* 模式切换按钮 */}
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #f0f0f0' }}>
              <Button
                type="link"
                onClick={handleSwitchMode}
                style={{ width: '100%' }}
              >
                → 切换到向导模式
              </Button>
            </div>
          </div>
        )}

        {/* 主内容区 */}
        <div className={styles.main}>
          {/* 顶部工具栏（仅专家模式显示） */}
          {modePreference === 'expert' && (
            <TopToolbar
              configFields={configFields.map(f => ({
                key: f.key,
                label: f.key,
                category: f.category,
                description: f.description
              }))}
              onSearch={handleSearch}
              onSelectSearch={handleSelectSearch}
              onSave={handleSave}
              onReset={handleReset}
              isSaving={isSaving}
              hasChanges={hasChanges}
              changeCount={changeCount}
            />
          )}

          {/* 向导模式头部 */}
          {modePreference === 'wizard' && (
            <div style={{
              padding: '12px 16px',
              borderBottom: '1px solid #f0f0f0',
              backgroundColor: '#fff',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <h2 style={{ margin: 0, fontSize: 18 }}>🔧 系统配置 - 向导模式</h2>
              <Button onClick={handleSwitchMode}>
                ← 切换专家模式
              </Button>
            </div>
          )}

          <div className={styles.content}>
            {isLoading && <div className={styles.loading}>加载中...</div>}

            {!isLoading && (
              <>
                {modePreference === 'expert' && (
                  <DynamicConfigForm
                    fields={configFields}
                    category={effectiveCategory}
                  />
                )}
                
                {modePreference === 'wizard' && <WizardMode />}
              </>
            )}
          </div>
        </div>

        {/* 移动端底部导航 */}
        {isMobile && (
          <MobileNav
            selectedCategory={selectedCategory}
            onSelectCategory={setSelectedCategory}
          />
        )}
      </div>
    </ConfigErrorBoundary>
  );
};
