import React from 'react';
import { Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

interface LoadingSpinnerProps {
  size?: 'small' | 'default' | 'large';
  tip?: string;
  fullScreen?: boolean;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'large',
  tip = '加载中...',
  fullScreen = false,
}) => {
  const indicator = <LoadingOutlined style={{ fontSize: size === 'large' ? 32 : 24 }} spin />;

  if (fullScreen) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        flexDirection: 'column',
        gap: '16px',
      }}>
        <Spin indicator={indicator} size={size} tip={tip} />
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: '48px 0',
      flexDirection: 'column',
      gap: '16px',
    }}>
      <Spin indicator={indicator} size={size} tip={tip} />
    </div>
  );
};
