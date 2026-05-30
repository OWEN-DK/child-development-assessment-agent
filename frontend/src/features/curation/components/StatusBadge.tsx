import React from 'react';
import { Tag } from 'antd';
import styles from './StatusBadge.module.scss';

interface StatusBadgeProps {
  status: 'draft' | 'reviewed' | 'published' | string;
  size?: 'small' | 'default';
}

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  draft: { color: 'default', label: '草稿' },
  reviewed: { color: 'warning', label: '已审核' },
  published: { color: 'success', label: '已入库' },
  generating: { color: 'processing', label: '生成中' },
  failed: { color: 'error', label: '失败' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'default' }) => {
  const cfg = STATUS_MAP[status] || { color: 'default', label: status };
  return (
    <span className={`${styles.badge} ${styles[`badge--${status}`]}`}>
      <span className={styles.badge__dot} />
      <Tag color={cfg.color} style={size === 'small' ? { fontSize: 11, padding: '0 4px' } : undefined}>
        {cfg.label}
      </Tag>
    </span>
  );
};
