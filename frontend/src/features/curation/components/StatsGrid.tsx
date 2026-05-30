import React from 'react';
import styles from './StatsGrid.module.scss';

interface StatItem {
  value: string | number;
  label: string;
  color?: string;
}

interface StatsGridProps {
  items: StatItem[];
  columns?: number;
}

export const StatsGrid: React.FC<StatsGridProps> = ({ items, columns = 4 }) => {
  return (
    <div className={styles.grid} style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
      {items.map((item, i) => (
        <div key={i} className={styles.card}>
          <div className={styles.card__value} style={item.color ? { color: item.color } : undefined}>
            {item.value}
          </div>
          <div className={styles.card__label}>{item.label}</div>
        </div>
      ))}
    </div>
  );
};
