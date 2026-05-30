import React from 'react';
import styles from './EmptyState.module.scss';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, description, action }) => {
  return (
    <div className={styles.empty}>
      <div className={styles.empty__icon}>{icon || '📭'}</div>
      <div className={styles.empty__title}>{title}</div>
      {description && <div className={styles.empty__desc}>{description}</div>}
      {action && <div className={styles.empty__action}>{action}</div>}
    </div>
  );
};
