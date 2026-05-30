import React from 'react';
import { Checkbox, Tag } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import styles from './ChapterRow.module.scss';

interface ChapterRowProps {
  index: number;
  title: string;
  tokenCount: number;
  selected: boolean;
  overThreshold?: boolean;
  onToggle?: (index: number, selected: boolean) => void;
}

export const ChapterRow: React.FC<ChapterRowProps> = ({
  index,
  title,
  tokenCount,
  selected,
  overThreshold,
  onToggle,
}) => {
  return (
    <div className={`${styles.row} ${overThreshold ? styles['row--warn'] : ''}`}>
      <Checkbox
        checked={selected}
        onChange={(e) => onToggle?.(index, e.target.checked)}
      />
      <span className={styles.row__title}>
        第{index + 1}章 {title}
      </span>
      <span className={styles.row__tokens}>~{tokenCount.toLocaleString()} tokens</span>
      {overThreshold && (
        <Tag color="warning" icon={<WarningOutlined />} style={{ fontSize: 11 }}>
          超阈值
        </Tag>
      )}
    </div>
  );
};
