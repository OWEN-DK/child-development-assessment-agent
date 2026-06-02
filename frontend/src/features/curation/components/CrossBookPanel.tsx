import React, { useState, useEffect, useCallback } from 'react';
import { Button, Card, Checkbox, Tag, Tooltip, Spin, message, Space, Radio } from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  SwapOutlined,
  ThunderboltOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { curationApi } from '../api/curationApi';
import type { CrossBookData } from '../types';

interface CrossBookPanelProps {
  bookId: string;
}

const ENTITY_DECISIONS = [
  { label: '合并', value: 'merge', icon: <CheckOutlined />, color: '#10B981' },
  { label: '独立', value: 'separate', icon: <CloseOutlined />, color: '#F43F5E' },
  { label: '自动', value: 'auto', icon: <ThunderboltOutlined />, color: '#F59E0B' },
  { label: '跳过', value: 'skip', icon: <StopOutlined />, color: '#6B7280' },
];

const RELATION_DECISIONS = [
  { label: '确认', value: 'confirm', icon: <CheckOutlined />, color: '#10B981' },
  { label: '忽略', value: 'ignore', icon: <CloseOutlined />, color: '#F43F5E' },
  { label: '修改', value: 'modify', icon: <SwapOutlined />, color: '#3B82F6' },
  { label: '自动', value: 'auto', icon: <ThunderboltOutlined />, color: '#F59E0B' },
  { label: '跳过', value: 'skip', icon: <StopOutlined />, color: '#6B7280' },
];

const RELATION_TYPE_LABELS: Record<string, string> = {
  CROSS_TREATS: '治疗',
  CROSS_PREVENTS: '预防',
  CROSS_ALLEVIATES: '缓解',
  CROSS_ADDRESSES: '针对',
  CROSS_IMPROVES: '改善',
  CROSS_ENHANCES: '增强',
  CROSS_CAUSES: '导致',
  CROSS_CONTRIBUTES_TO: '促成',
  CROSS_AFFECTS: '影响',
  CROSS_INCREASES_RISK: '增加风险',
  CROSS_OCCURS_AT: '发生于',
  CROSS_SUPPORTED_BY: '被支持',
  CROSS_EXPLAINED_BY: '被解释',
  CROSS_SUPPORTS: '支持',
  CROSS_CONTRADICTS: '矛盾',
  CROSS_EXTENDS: '扩展',
  CROSS_COMPLEMENTS: '补充',
  CROSS_ILLUMINATES: '阐明',
  CROSS_LOCALIZED_IN: '定位于',
  CROSS_INVOLVES: '涉及',
  CROSS_EXPLAINS: '解释',
  CROSS_ASSOCIATED_WITH: '相关',
  CROSS_COMBINES_WITH: '结合',
};

export const CrossBookPanel: React.FC<CrossBookPanelProps> = ({ bookId }) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<CrossBookData | null>(null);
  const [selectedMatches, setSelectedMatches] = useState<number[]>([]);
  const [selectedRelations, setSelectedRelations] = useState<number[]>([]);
  const [activeTab, setActiveTab] = useState<'matches' | 'relations'>('matches');

  const loadCrossBookData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await curationApi.getCrossBookRelations(bookId);
      if (result) {
        setData(result);
        // 默认全选
        setSelectedMatches(result.entity_matches?.map((_: any, i: number) => i) || []);
        setSelectedRelations(result.cross_relations?.map((_: any, i: number) => i) || []);
      }
    } catch (error) {
      console.error('加载跨书数据失败:', error);
    } finally {
      setLoading(false);
    }
  }, [bookId]);

  useEffect(() => {
    loadCrossBookData();
  }, [loadCrossBookData]);

  const handleUpdateDecision = async (
    decisionType: 'entity_match' | 'cross_relation',
    index: number,
    decision: string,
  ) => {
    try {
      await curationApi.updateCrossBookDecision(bookId, decisionType, index, decision);
      // 更新本地状态
      if (data) {
        const newData = { ...data };
        if (decisionType === 'entity_match') {
          newData.entity_matches = [...newData.entity_matches];
          newData.entity_matches[index] = { ...newData.entity_matches[index], reviewer_decision: decision };
        } else {
          newData.cross_relations = [...newData.cross_relations];
          newData.cross_relations[index] = { ...newData.cross_relations[index], reviewer_decision: decision };
        }
        setData(newData);
      }
      message.success('决策已更新');
    } catch (error) {
      message.error('更新失败');
    }
  };

  const handleBatchDecision = async (
    decisionType: 'entity_match' | 'cross_relation',
    decision: string,
  ) => {
    const indices = decisionType === 'entity_match' ? selectedMatches : selectedRelations;
    if (indices.length === 0) {
      message.warning('请先选择要操作的项目');
      return;
    }

    try {
      await curationApi.batchUpdateCrossBookDecisions(bookId, decisionType, indices, decision);
      // 更新本地状态
      if (data) {
        const newData = { ...data };
        if (decisionType === 'entity_match') {
          newData.entity_matches = newData.entity_matches.map((item, i) =>
            indices.includes(i) ? { ...item, reviewer_decision: decision } : item,
          );
        } else {
          newData.cross_relations = newData.cross_relations.map((item, i) =>
            indices.includes(i) ? { ...item, reviewer_decision: decision } : item,
          );
        }
        setData(newData);
      }
      message.success(`已批量更新 ${indices.length} 条决策`);
    } catch (error) {
      message.error('批量更新失败');
    }
  };

  const getSimilarityColor = (sim: number) => {
    if (sim >= 0.9) return '#10B981';
    if (sim >= 0.7) return '#F59E0B';
    return '#6B7280';
  };

  const getConfidenceColor = (conf: number) => {
    if (conf >= 0.85) return '#10B981';
    if (conf >= 0.7) return '#F59E0B';
    return '#6B7280';
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <Spin tip="加载跨书分析数据..." />
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: '#6B7280' }}>
        暂无跨书分析数据
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* 统计信息 */}
      <Card size="small" style={{ background: '#F9FAFB' }}>
        <div style={{ display: 'flex', justifyContent: 'space-around', textAlign: 'center' }}>
          <div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3B82F6' }}>
              {data.stats.total_new_entities}
            </div>
            <div style={{ fontSize: '12px', color: '#6B7280' }}>新书实体</div>
          </div>
          <div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#8B5CF6' }}>
              {data.stats.total_other_entities}
            </div>
            <div style={{ fontSize: '12px', color: '#6B7280' }}>其他书实体</div>
          </div>
          <div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#F59E0B' }}>
              {data.stats.match_candidates}
            </div>
            <div style={{ fontSize: '12px', color: '#6B7280' }}>匹配候选</div>
          </div>
          <div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10B981' }}>
              {data.stats.relation_candidates}
            </div>
            <div style={{ fontSize: '12px', color: '#6B7280' }}>关系候选</div>
          </div>
        </div>
      </Card>

      {/* 标签切换 */}
      <Radio.Group value={activeTab} onChange={(e) => setActiveTab(e.target.value)}>
        <Radio.Button value="matches">
          实体消歧 ({data.entity_matches.length})
        </Radio.Button>
        <Radio.Button value="relations">
          跨书关系 ({data.cross_relations.length})
        </Radio.Button>
      </Radio.Group>

      {/* 实体消歧面板 */}
      {activeTab === 'matches' && (
        <Card
          title="🔍 实体消歧"
          extra={
            <Space>
              <Button
                size="small"
                type="primary"
                onClick={() => handleBatchDecision('entity_match', 'merge')}
                disabled={selectedMatches.length === 0}
              >
                批量合并
              </Button>
              <Button
                size="small"
                onClick={() => handleBatchDecision('entity_match', 'separate')}
                disabled={selectedMatches.length === 0}
              >
                批量独立
              </Button>
              <Button
                size="small"
                onClick={() => handleBatchDecision('entity_match', 'skip')}
                disabled={selectedMatches.length === 0}
              >
                批量跳过
              </Button>
            </Space>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {data.entity_matches.map((match, idx) => (
              <div
                key={idx}
                style={{
                  padding: '12px',
                  border: '1px solid #E5E7EB',
                  borderRadius: '8px',
                  background: match.reviewer_decision !== 'skip' ? '#F0FDF4' : '#fff',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                  <Checkbox
                    checked={selectedMatches.includes(idx)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedMatches([...selectedMatches, idx]);
                      } else {
                        setSelectedMatches(selectedMatches.filter((i) => i !== idx));
                      }
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <Tag color="blue">{match.new_type}</Tag>
                      <span style={{ fontWeight: 500 }}>{match.new_entity}</span>
                      <span style={{ color: '#9CA3AF' }}>↔</span>
                      <Tag color="purple">{match.matched_type}</Tag>
                      <span style={{ fontWeight: 500 }}>{match.matched_entity}</span>
                      <Tag color={match.matched_book_id === data.source_books[0]?.book_id ? 'green' : 'orange'}>
                        {match.matched_book_title || match.matched_book_id}
                      </Tag>
                    </div>
                    <div style={{ fontSize: '12px', color: '#6B7280', marginBottom: '8px' }}>
                      <div>新书: {match.new_desc || '无描述'}</div>
                      <div>已有: {match.matched_desc || '无描述'}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <Tooltip title={`相似度: ${match.similarity.toFixed(3)}`}>
                        <Tag color={getSimilarityColor(match.similarity)}>
                          相似度: {(match.similarity * 100).toFixed(1)}%
                        </Tag>
                      </Tooltip>
                      {match.llm_same !== null && (
                        <Tag color={match.llm_same ? 'green' : 'red'}>
                          LLM: {match.llm_same ? '同一概念' : '不同概念'}
                        </Tag>
                      )}
                      {match.llm_reason && (
                        <Tooltip title={match.llm_reason}>
                          <span style={{ fontSize: '12px', color: '#9CA3AF', cursor: 'help' }}>
                            ℹ️ 判断理由
                          </span>
                        </Tooltip>
                      )}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {ENTITY_DECISIONS.map((d) => (
                      <Tooltip key={d.value} title={d.label}>
                        <Button
                          size="small"
                          type={match.reviewer_decision === d.value ? 'primary' : 'default'}
                          icon={d.icon}
                          onClick={() => handleUpdateDecision('entity_match', idx, d.value)}
                          style={{
                            borderColor: match.reviewer_decision === d.value ? d.color : undefined,
                            background: match.reviewer_decision === d.value ? d.color : undefined,
                          }}
                        />
                      </Tooltip>
                    ))}
                  </div>
                </div>
              </div>
            ))}
            {data.entity_matches.length === 0 && (
              <div style={{ textAlign: 'center', color: '#9CA3AF', padding: '20px' }}>
                暂无实体消歧候选
              </div>
            )}
          </div>
        </Card>
      )}

      {/* 跨书关系面板 */}
      {activeTab === 'relations' && (
        <Card
          title="🌐 跨书关系"
          extra={
            <Space>
              <Button
                size="small"
                type="primary"
                onClick={() => handleBatchDecision('cross_relation', 'confirm')}
                disabled={selectedRelations.length === 0}
              >
                批量确认
              </Button>
              <Button
                size="small"
                onClick={() => handleBatchDecision('cross_relation', 'ignore')}
                disabled={selectedRelations.length === 0}
              >
                批量忽略
              </Button>
              <Button
                size="small"
                onClick={() => handleBatchDecision('cross_relation', 'skip')}
                disabled={selectedRelations.length === 0}
              >
                批量跳过
              </Button>
            </Space>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {data.cross_relations.map((rel, idx) => (
              <div
                key={idx}
                style={{
                  padding: '12px',
                  border: '1px solid #E5E7EB',
                  borderRadius: '8px',
                  background: rel.reviewer_decision !== 'skip' ? '#F0FDF4' : '#fff',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                  <Checkbox
                    checked={selectedRelations.includes(idx)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedRelations([...selectedRelations, idx]);
                      } else {
                        setSelectedRelations(selectedRelations.filter((i) => i !== idx));
                      }
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <Tag color="blue">{rel.source_type}</Tag>
                      <span style={{ fontWeight: 500 }}>{rel.source_entity}</span>
                      <Tag color="orange">{RELATION_TYPE_LABELS[rel.relation_type] || rel.relation_type}</Tag>
                      <span style={{ fontWeight: 500 }}>{rel.target_entity}</span>
                      <Tag color="purple">{rel.target_type}</Tag>
                    </div>
                    <div style={{ fontSize: '12px', color: '#6B7280', marginBottom: '8px' }}>
                      {rel.reason}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <Tooltip title={`置信度: ${rel.confidence.toFixed(3)}`}>
                        <Tag color={getConfidenceColor(rel.confidence)}>
                          置信度: {(rel.confidence * 100).toFixed(1)}%
                        </Tag>
                      </Tooltip>
                      {rel.evidence_summary && (
                        <Tooltip title={rel.evidence_summary}>
                          <span style={{ fontSize: '12px', color: '#9CA3AF', cursor: 'help' }}>
                            ℹ️ 证据摘要
                          </span>
                        </Tooltip>
                      )}
                      <span style={{ fontSize: '12px', color: '#9CA3AF' }}>
                        {rel.source_book} → {rel.target_book}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {RELATION_DECISIONS.map((d) => (
                      <Tooltip key={d.value} title={d.label}>
                        <Button
                          size="small"
                          type={rel.reviewer_decision === d.value ? 'primary' : 'default'}
                          icon={d.icon}
                          onClick={() => handleUpdateDecision('cross_relation', idx, d.value)}
                          style={{
                            borderColor: rel.reviewer_decision === d.value ? d.color : undefined,
                            background: rel.reviewer_decision === d.value ? d.color : undefined,
                          }}
                        />
                      </Tooltip>
                    ))}
                  </div>
                </div>
              </div>
            ))}
            {data.cross_relations.length === 0 && (
              <div style={{ textAlign: 'center', color: '#9CA3AF', padding: '20px' }}>
                暂无跨书关系候选
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
};
