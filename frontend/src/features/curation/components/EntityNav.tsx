import React, { useState } from 'react';
import { Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { EntityItem } from '../types';
import styles from './EntityNav.module.scss';

const TYPE_LABELS: Record<string, string> = {
  Problem: '📋 问题',
  Solution: '✅ 方案',
  BrainRegion: '🧠 脑区',
  Exercise: '🏃 运动',
  Prescription: '💉 处方',
  RootCause: '⚠️ 根因',
};

interface EntityNavProps {
  entities: EntityItem[];
  groupedEntities: Record<string, EntityItem[]>;
  confirmedEntities: Set<string>;
  activeEntity: string | null;
  confirmedCount: number;
  totalEntities: number;
  onSelect: (name: string) => void;
  onToggleConfirm: (name: string) => void;
}

export const EntityNav: React.FC<EntityNavProps> = ({
  groupedEntities,
  confirmedEntities,
  activeEntity,
  confirmedCount,
  totalEntities,
  onSelect,
  onToggleConfirm,
}) => {
  const [search, setSearch] = useState('');
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(Object.keys(groupedEntities)),
  );

  const toggleGroup = (type: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const filtered: Record<string, EntityItem[]> = search
    ? Object.fromEntries(
        Object.entries(groupedEntities)
          .map(([type, items]) => [
            type,
            items.filter((e) => e.name.toLowerCase().includes(search.toLowerCase())),
          ])
          .filter(([, items]) => items.length > 0),
      )
    : groupedEntities;

  return (
    <div className={styles.nav}>
      <div className={styles.nav__header}>
        <span className={styles.nav__title}>实体导航</span>
        <span className={styles.nav__count}>{confirmedCount}/{totalEntities}</span>
      </div>
      <Input
        placeholder="搜索实体..."
        size="small"
        prefix={<SearchOutlined />}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        allowClear
        className={styles.nav__search}
      />
      {Object.entries(filtered).map(([type, items]) => (
        <div key={type} className={styles.group}>
          <div className={styles.group__header} onClick={() => toggleGroup(type)}>
            <span className={`${styles.group__arrow} ${expandedGroups.has(type) ? styles['group__arrow--expanded'] : ''}`}>
              ▶
            </span>
            <span>{TYPE_LABELS[type] || type}</span>
            <span className={styles.group__count}>{items.length}</span>
          </div>
          {expandedGroups.has(type) &&
            items.map((entity) => (
              <div
                key={entity.name}
                className={`${styles.item} ${activeEntity === entity.name ? styles['item--active'] : ''}`}
                onClick={() => onSelect(entity.name)}
              >
                <div
                  className={`${styles.item__check} ${confirmedEntities.has(entity.name) ? styles['item__check--confirmed'] : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleConfirm(entity.name);
                  }}
                >
                  {confirmedEntities.has(entity.name) && '✓'}
                </div>
                <span className={styles.item__name}>{entity.name}</span>
              </div>
            ))}
        </div>
      ))}
    </div>
  );
};
