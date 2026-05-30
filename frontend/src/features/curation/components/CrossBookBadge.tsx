import React from 'react';
import { Tag } from 'antd';
import {
  CheckCircleOutlined,
  LinkOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import styles from './CrossBookBadge.module.scss';

interface CrossBookBadgeProps {
  type: 'consensus' | 'complement' | 'conflict';
  label?: string;
  bookName?: string;
  confirmed?: boolean;
  onConfirm?: () => void;
  onIgnore?: () => void;
}

const TYPE_CONFIG = {
  consensus: { color: '#10B981', icon: <CheckCircleOutlined />, label: '观点一致' },
  complement: { color: '#0EA5E9', icon: <LinkOutlined />, label: '观点互补' },
  conflict: { color: '#F43F5E', icon: <ExclamationCircleOutlined />, label: '观点冲突' },
};

export const CrossBookBadge: React.FC<CrossBookBadgeProps> = ({
  type,
  label,
  bookName,
  confirmed,
  onConfirm,
  onIgnore,
}) => {
  const cfg = TYPE_CONFIG[type];
  return (
    <div className={`${styles.badge} ${styles[`badge--${type}`]}`}>
      <div className={styles.badge__header}>
        <span style={{ color: cfg.color }}>{cfg.icon}</span>
        <span className={styles.badge__label}>{label || cfg.label}</span>
        {confirmed && <Tag color="success" style={{ marginLeft: 'auto', fontSize: 11 }}>已确认</Tag>}
      </div>
      {bookName && <div className={styles.badge__book}>{bookName}</div>}
      {type === 'conflict' && onConfirm && onIgnore && (
        <div className={styles.badge__actions}>
          <button className={styles.badge__btn} onClick={onConfirm}>保留本书</button>
          <button className={styles.badge__btn} onClick={onIgnore}>忽略</button>
        </div>
      )}
    </div>
  );
};
