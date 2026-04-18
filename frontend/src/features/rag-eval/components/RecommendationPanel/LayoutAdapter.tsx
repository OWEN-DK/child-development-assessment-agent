/**
 * 响应式布局适配器
 * 屏幕 >= 1440px: 固定侧边栏 (380px)
 * 屏幕 < 1440px: 抽屉模式 (40% 宽度, 最小 480px)
 */

import { useState, useEffect } from 'react';
import { Drawer, Button } from 'antd';
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';

const BREAKPOINT = 1440;

interface LayoutAdapterProps {
  children: React.ReactNode;
  /** 内容区域的触发按钮（抽屉模式下显示） */
  triggerButton?: React.ReactNode;
}

export default function LayoutAdapter({ children, triggerButton }: LayoutAdapterProps) {
  const [isWideScreen, setIsWideScreen] = useState(window.innerWidth >= BREAKPOINT);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [manualOverride, setManualOverride] = useState<'fixed' | 'drawer' | null>(null);

  useEffect(() => {
    const handleResize = () => {
      if (!manualOverride) {
        setIsWideScreen(window.innerWidth >= BREAKPOINT);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [manualOverride]);

  // 确定当前模式
  const useFixed = manualOverride === 'fixed' || (manualOverride === null && isWideScreen);

  // 切换手动覆盖
  const toggleMode = () => {
    if (manualOverride === null) {
      setManualOverride(isWideScreen ? 'drawer' : 'fixed');
    } else {
      setManualOverride(manualOverride === 'fixed' ? 'drawer' : 'fixed');
    }
  };

  // 固定侧边栏模式
  if (useFixed) {
    return (
      <div style={{ position: 'relative' }}>
        <aside
          style={{
            width: 380,
            position: 'fixed',
            right: 0,
            top: 0,
            bottom: 0,
            overflowY: 'auto',
            borderLeft: '1px solid #f0f0f0',
            background: '#fff',
            zIndex: 10,
            padding: '16px',
          }}
        >
          {children}
        </aside>
        {/* 切换按钮 */}
        <Button
          type="text"
          icon={manualOverride === 'fixed' ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={toggleMode}
          style={{
            position: 'fixed',
            right: 388,
            top: 16,
            zIndex: 11,
          }}
          title={manualOverride === 'fixed' ? '切换为抽屉模式' : '切换为固定模式'}
        />
      </div>
    );
  }

  // 抽屉模式
  return (
    <>
      {triggerButton || (
        <Button
          type="primary"
          icon={<MenuUnfoldOutlined />}
          onClick={() => setDrawerOpen(true)}
          style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 11 }}
        >
          打开面板
        </Button>
      )}
      <Drawer
        placement="right"
        width="40%"
        style={{ minWidth: 480 }}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        destroyOnClose={false}
      >
        {children}
      </Drawer>
      {/* 切换按钮 */}
      <Button
        type="text"
        icon={manualOverride === 'drawer' ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
        onClick={toggleMode}
        style={{
          position: 'fixed',
          right: 16,
          top: 16,
          zIndex: 11,
        }}
        title={manualOverride === 'drawer' ? '切换为固定模式' : '切换为抽屉模式'}
      />
    </>
  );
}
