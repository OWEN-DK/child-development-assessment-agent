import React, { useState, useRef, useEffect } from 'react';
import { Tag, Empty } from 'antd';
import type { ExtractedRelation } from '../types';
import { RELATION_LABELS } from '../hooks/useDraftEditor';
import styles from './RelationshipCards.module.scss';

interface RelationCardProps {
  rel: ExtractedRelation;
  isActive: boolean;
  onEntityClick: (name: string) => void;
}

const RelationCard: React.FC<RelationCardProps> = ({ rel, isActive, onEntityClick }) => {
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const labelInfo = RELATION_LABELS[rel.relationType] || { label: rel.relationType, color: '#A8A29E' };

  useEffect(() => {
    if (isActive && cardRef.current) {
      cardRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      cardRef.current.style.boxShadow = '0 0 0 2px var(--indigo-400)';
      const timer = setTimeout(() => {
        if (cardRef.current) cardRef.current.style.boxShadow = '';
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [isActive]);

  return (
    <div ref={cardRef} className={`${styles.card} ${isActive ? styles['card--active'] : ''}`}>
      {/* 关系头部：来源 → 目标 */}
      <div className={styles.card__header}>
        <span
          className={styles.card__entity}
          onClick={() => onEntityClick(rel.source)}
        >
          {rel.source}
        </span>
        <span className={styles.card__arrow}>
          <span className={styles['card__arrow-line']} style={{ background: labelInfo.color }} />
          <span className={styles['card__arrow-head']} style={{ borderLeftColor: labelInfo.color }} />
        </span>
        <Tag color={labelInfo.color} className={styles.card__tag}>
          {labelInfo.label}
        </Tag>
        <span className={styles['card__arrow-reverse']}>
          <span className={styles['card__arrow-line']} style={{ background: labelInfo.color }} />
          <span className={styles['card__arrow-head']} style={{ borderLeftColor: labelInfo.color }} />
        </span>
        <span
          className={styles.card__entity}
          onClick={() => onEntityClick(rel.target)}
        >
          {rel.target}
        </span>
      </div>

      {/* 证据 */}
      {rel.evidence && (
        <div className={styles.card__evidence}>
          <div className={styles['card__evidence-preview']}>
            💬 {evidenceExpanded ? rel.evidence : rel.evidence.length > 72 ? `${rel.evidence.slice(0, 72)}…` : rel.evidence}
          </div>
          {rel.evidence.length > 72 && (
            <div
              className={styles['card__evidence-toggle']}
              onClick={() => setEvidenceExpanded(!evidenceExpanded)}
            >
              {evidenceExpanded ? '收起' : '展开'}
            </div>
          )}
        </div>
      )}

      {/* 来源段落 */}
      {rel.sourceParas && (
        <div className={styles.card__source}>
          📍 {rel.sourceParas}
        </div>
      )}
    </div>
  );
};

interface RelationshipCardsProps {
  /** 全部关系 */
  allRelations: ExtractedRelation[];
  /** 按大类分组的关系 */
  groupedRelations: Record<string, ExtractedRelation[]>;
  /** 当前选中的实体 (null = 显示全部) */
  activeEntity: string | null;
  /** 是否有选中实体 */
  hasActiveEntity: boolean;
  /** 点击实体名回调 */
  onEntityClick: (name: string) => void;
}

export const RelationshipCards: React.FC<RelationshipCardsProps> = ({
  allRelations,
  groupedRelations,
  activeEntity,
  hasActiveEntity,
  onEntityClick,
}) => {
  if (allRelations.length === 0) {
    return (
      <div className={styles.empty}>
        <Empty description={hasActiveEntity ? '该实体暂无关系' : '未提取到关系数据'} />
      </div>
    );
  }

  const groupEntries = Object.entries(groupedRelations);

  return (
    <div className={styles.container}>
      {/* 头部统计 */}
      <div className={styles.header}>
        <span className={styles.header__title}>
          {hasActiveEntity ? `「${activeEntity}」的关系` : '全部关系'}
        </span>
        <span className={styles.header__count}>
          {allRelations.length} 条关系 · {groupEntries.length} 类
        </span>
      </div>

      {/* 按大类分组展示 */}
      {groupEntries.map(([category, rels]) => (
        <div key={category} className={styles.group}>
          <div className={styles.group__header}>
            {category}
            <span className={styles.group__count}>{rels.length}</span>
          </div>
          {rels.map((rel) => (
            <RelationCard
              key={rel.id}
              rel={rel}
              isActive={false}
              onEntityClick={onEntityClick}
            />
          ))}
        </div>
      ))}
    </div>
  );
};
