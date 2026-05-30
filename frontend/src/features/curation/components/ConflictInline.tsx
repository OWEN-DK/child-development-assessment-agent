import React from 'react';
import styles from './ConflictInline.module.scss';

interface ConflictInlineProps {
  type: 'consensus' | 'complement' | 'conflict';
  title: string;
  description: string;
  bookA?: string;
  bookB?: string;
  onResolve?: (choice: 'keep' | 'adopt' | 'custom') => void;
}

export const ConflictInline: React.FC<ConflictInlineProps> = ({
  type,
  title,
  description,
  bookA,
  bookB,
  onResolve,
}) => {
  return (
    <div className={`${styles.inline} ${styles[`inline--${type}`]}`}>
      <div className={styles.inline__title}>{title}</div>
      <div className={styles.inline__desc}>{description}</div>
      {bookA && bookB && (
        <div className={styles.inline__books}>
          <span>本书: {bookA}</span>
          <span>对方: {bookB}</span>
        </div>
      )}
      {type === 'conflict' && onResolve && (
        <div className={styles.inline__actions}>
          <button onClick={() => onResolve('keep')}>保留本书</button>
          <button onClick={() => onResolve('adopt')}>采用对方</button>
          <button onClick={() => onResolve('custom')}>自定义</button>
        </div>
      )}
    </div>
  );
};
