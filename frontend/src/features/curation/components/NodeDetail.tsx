import React from 'react';
import { Tag, Button, Divider } from 'antd';
import { CloseOutlined, LinkOutlined } from '@ant-design/icons';
import type { KGNode } from '../types';
import styles from './NodeDetail.module.scss';

const NODE_COLORS: Record<string, string> = {
  Problem: '#EF4444',
  Solution: '#10B981',
  BrainRegion: '#3B82F6',
  CognitiveProcess: '#14B8A6',
  Theory: '#8B5CF6',
  Mechanism: '#F97316',
  DevelopmentalStage: '#06B6D4',
  Strategy: '#84CC16',
  KeyInsight: '#EAB308',
  ResearchFinding: '#64748B',
  Exercise: '#F59E0B',
  Prescription: '#F59E0B',
  RootCause: '#EC4899',
  Book: '#6366F1',
  AutoEntity: '#8B5CF6',
  AutoCommunity: '#06B6D4',
};

const RELATION_LABELS: Record<string, string> = {
  RELATES_TO: '相关',
  CONSENSUS: '共识',
  COMPLEMENTS: '互补',
  CONFLICTS: '⚠️ 冲突',
  CONTAINS_ENTITY: '包含',
  PRESCRIBES: '处方',
  改善: '改善',
  导致: '导致',
  抑制: '抑制',
  促进: '促进',
  包含: '包含',
  属于: '属于',
  相关: '相关',
  替代: '替代',
};

interface ConnectedEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label?: string;
  counterpartLabel: string;
  counterpartType: string;
  direction: 'in' | 'out';
}

interface NodeDetailProps {
  node: KGNode;
  edgeCount?: number;
  connectedEdges?: ConnectedEdge[];
  onClose: () => void;
  onViewSource?: () => void;
  onNodeClick?: (nodeId: string) => void;
}

export const NodeDetail: React.FC<NodeDetailProps> = ({
  node,
  edgeCount,
  connectedEdges = [],
  onClose,
  onViewSource,
  onNodeClick,
}) => {
  const color = NODE_COLORS[node.type] || '#78716C';

  return (
    <div className={styles.detail}>
      <div className={styles.detail__header}>
        <div>
          <div className={styles.detail__name}>{node.label}</div>
          <Tag color={color}>{node.type}</Tag>
          {node.confirmed === false && <Tag color="orange">待审核</Tag>}
        </div>
        <Button type="text" icon={<CloseOutlined />} size="small" onClick={onClose} />
      </div>

      {node.description && (
        <div className={styles.detail__desc}>{node.description}</div>
      )}

      <div className={styles.detail__meta}>
        <div>ID: {node.id}</div>
        {node.book_id && <div>来源: {node.book_id}</div>}
        {node.severity && <div>严重度: <Tag color={node.severity === 'high' ? 'red' : node.severity === 'medium' ? 'orange' : 'green'}>{node.severity}</Tag></div>}
        {node.category && <div>类别: {node.category}</div>}
        {node.key_figures && <div>代表人物: {node.key_figures}</div>}
        {node.mechanism_detail && <div>机制: {node.mechanism_detail}</div>}
        {node.brain_regions && node.brain_regions.length > 0 && (
          <div>关联脑区: {node.brain_regions.join(', ')}</div>
        )}
        {node.evidence && <div>证据: {node.evidence}</div>}
        {edgeCount !== undefined && <div>关联: {edgeCount} 条关系</div>}
      </div>

      {/* 关系列表 */}
      {connectedEdges.length > 0 && (
        <>
          <Divider style={{ margin: '8px 0' }} />
          <div className={styles.detail__relations}>
            <div className={styles.detail__relations_title}>
              <LinkOutlined /> 关联关系 ({connectedEdges.length})
            </div>
            <div className={styles.detail__relations_list}>
              {connectedEdges.map((edge) => (
                <div
                  key={edge.id}
                  className={styles.detail__relation_item}
                  onClick={() => onNodeClick?.(edge.direction === 'in' ? edge.source : edge.target)}
                >
                  <span
                    className={styles.detail__relation_arrow}
                    style={{ color: edge.type === 'CONFLICTS' ? '#F43F5E' : '#78716C' }}
                  >
                    {edge.direction === 'in' ? '←' : '→'}
                  </span>
                  <Tag
                    color={edge.type === 'CONFLICTS' ? 'red' : edge.type === 'CONSENSUS' ? 'green' : 'default'}
                    style={{ fontSize: 11 }}
                  >
                    {RELATION_LABELS[edge.type] || edge.label || edge.type}
                  </Tag>
                  <span className={styles.detail__relation_node}>
                    {edge.counterpartLabel}
                  </span>
                  <Tag
                    color={NODE_COLORS[edge.counterpartType] || 'default'}
                    style={{ fontSize: 10 }}
                  >
                    {edge.counterpartType}
                  </Tag>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {connectedEdges.length === 0 && (
        <div style={{ marginTop: 8, color: '#A8A29E', fontSize: 12 }}>暂无关联关系</div>
      )}

      {onViewSource && (
        <Button size="small" block style={{ marginTop: 8 }} onClick={onViewSource}>
          查看 MD 原文
        </Button>
      )}
    </div>
  );
};
