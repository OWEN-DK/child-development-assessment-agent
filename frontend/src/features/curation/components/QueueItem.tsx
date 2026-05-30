import React from 'react';
import { Tag } from 'antd';
import {
  ClockCircleOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import type { PendingItem } from '../types';
import styles from './QueueItem.module.scss';

const STATUS_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  pending: { color: 'default', label: '待处理', icon: <ClockCircleOutlined /> },
  processing: { color: 'processing', label: '处理中', icon: <LoadingOutlined spin /> },
  completed: { color: 'success', label: '已提炼', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', label: '失败', icon: <ExclamationCircleOutlined /> },
};

const ENTITY_ICONS: Record<string, string> = {
  Problem: '📋',
  Solution: '✅',
  BrainRegion: '🧠',
  Exercise: '🏃',
  Prescription: '💉',
  RootCause: '⚠️',
};

const ENTITY_COLORS: Record<string, string> = {
  Problem: '#EF4444',
  Solution: '#10B981',
  BrainRegion: '#3B82F6',
  Exercise: '#F59E0B',
  Prescription: '#F59E0B',
  RootCause: '#EC4899',
};

interface QueueItemProps {
  item: PendingItem;
}

export const QueueItem: React.FC<QueueItemProps> = ({ item }) => {
  const statusCfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.pending;
  const entityType = item.entity_type || item.topic || '';
  const entityName = item.entity_name || item.reason || item.topic || '';
  const bookId = item.book_id || (item.source_books && item.source_books[0]) || '';
  const entityColor = ENTITY_COLORS[entityType] || '#78716C';
  const entityIcon = ENTITY_ICONS[entityType] || '📄';

  return (
    <div className={styles.item}>
      <div className={styles.item__info}>
        <div className={styles.item__icon} style={{ background: `${entityColor}15`, color: entityColor }}>
          {entityIcon}
        </div>
        <div>
          <div className={styles.item__name}>{entityName}</div>
          <div className={styles.item__meta}>
            {entityType}{bookId ? ` · ${bookId}` : ''} · {item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : '-'}
          </div>
        </div>
      </div>
      <Tag icon={statusCfg.icon} color={statusCfg.color}>
        {statusCfg.label}
      </Tag>
    </div>
  );
};
