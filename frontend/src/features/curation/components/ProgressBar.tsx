import React from 'react';
import styles from './ProgressBar.module.scss';

interface ProgressBarProps {
  percent: number;
  color?: 'default' | 'success' | 'danger';
  size?: 'small' | 'default';
  showLabel?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  percent,
  color = 'default',
  size = 'default',
  showLabel = true,
}) => {
  const clamped = Math.min(100, Math.max(0, percent));
  return (
    <div className={styles.wrapper}>
      <div className={`${styles.bar} ${styles[`bar--${size}`]}`}>
        <div
          className={`${styles.bar__fill} ${styles[`bar__fill--${color}`]}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && <span className={styles.label}>{clamped}%</span>}
    </div>
  );
};
