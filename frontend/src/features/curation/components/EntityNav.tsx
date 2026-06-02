import React, { useMemo, useState } from 'react';
import { Input, Tooltip } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { EntityItem } from '../types';
import { ENTITY_TYPE_LABELS } from '../hooks/useDraftEditor';
import styles from './EntityNav.module.scss';

const ENTITY_TYPE_FALLBACK_COLOR = '#78716C';

const getEntityLabel = (type: string) => {
  const meta = ENTITY_TYPE_LABELS[type];
  return meta ? `${meta.icon} ${meta.label}` : `🧩 ${type}`;
};

const getEntityColor = (type: string) => ENTITY_TYPE_LABELS[type]?.color || ENTITY_TYPE_FALLBACK_COLOR;

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
  const defaultExpanded = useMemo(() => {
    return new Set(
      Object.entries(groupedEntities)
        .sort((a, b) => b[1].length - a[1].length)
        .slice(0, 12)
        .map(([type]) => type),
    );
  }, [groupedEntities]);

  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(defaultExpanded);

  const filtered: Record<string, EntityItem[]> = useMemo(
    () =>
      search
        ? Object.fromEntries(
            Object.entries(groupedEntities)
              .map(([type, items]) => [
                type,
                items.filter((e) => e.name.toLowerCase().includes(search.toLowerCase())),
              ])
              .filter(([, items]) => items.length > 0),
          )
        : groupedEntities,
    [groupedEntities, search],
  );

  const toggleGroup = (type: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

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
            <span className={styles.group__title}>{getEntityLabel(type)}</span>
            <span className={styles.group__badge} style={{ background: getEntityColor(type) }}>{items.length}</span>
          </div>
          {expandedGroups.has(type) && (
            <div className={styles.group__grid}>
              {items.map((entity, entityIdx) => (
                <button
                  key={`${entity.name}-${entity.type}-${entityIdx}`}
                  type="button"
                  className={`${styles.item} ${activeEntity === entity.name ? styles['item--active'] : ''}`}
                  onClick={() => onSelect(entity.name)}
                >
                  <span
                    role="checkbox"
                    aria-checked={confirmedEntities.has(entity.name)}
                    className={`${styles.item__check} ${confirmedEntities.has(entity.name) ? styles['item__check--confirmed'] : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleConfirm(entity.name);
                    }}
                  >
                    {confirmedEntities.has(entity.name) && '✓'}
                  </span>
                  <Tooltip title={entity.name.length > 18 ? entity.name : undefined}>
                    <span className={styles.item__name}>{entity.name}</span>
                  </Tooltip>
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
