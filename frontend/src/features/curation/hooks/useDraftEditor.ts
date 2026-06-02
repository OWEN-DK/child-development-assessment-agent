import { useEffect, useMemo, useState } from 'react';
import { useCurationStore } from '../stores/curationStore';
import { curationApi } from '../api/curationApi';
import type { EntityItem, ExtractedRelation } from '../types';

export const ENTITY_TYPE_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  Problem: { label: '问题', icon: '📋', color: '#EF4444' },
  Solution: { label: '方案', icon: '✅', color: '#10B981' },
  BrainRegion: { label: '脑区', icon: '🧠', color: '#3B82F6' },
  Exercise: { label: '运动', icon: '🏃', color: '#F59E0B' },
  Prescription: { label: '处方', icon: '💉', color: '#F59E0B' },
  RootCause: { label: '根因', icon: '⚠️', color: '#EC4899' },
  ChildProfile: { label: '儿童画像', icon: '🧒', color: '#0EA5E9' },
  Risk: { label: '风险', icon: '⛔', color: '#F43F5E' },
  CognitiveProcess: { label: '认知过程', icon: '🧩', color: '#14B8A6' },
  Theory: { label: '理论', icon: '📘', color: '#8B5CF6' },
  Mechanism: { label: '机制', icon: '⚙️', color: '#F97316' },
  DevelopmentalStage: { label: '发展阶段', icon: '📈', color: '#06B6D4' },
  Strategy: { label: '策略', icon: '🧭', color: '#84CC16' },
  KeyInsight: { label: '关键洞察', icon: '💡', color: '#EAB308' },
  ResearchFinding: { label: '研究发现', icon: '🔬', color: '#64748B' },
  Person: { label: '人物', icon: '👤', color: '#6366F1' },
  Location: { label: '地点', icon: '📍', color: '#22C55E' },
  Object: { label: '物体/工具', icon: '🧪', color: '#A855F7' },
  AssessmentTool: { label: '评估工具', icon: '🧾', color: '#8B5CF6' },
  Symptom: { label: '症状', icon: '🩺', color: '#F87171' },
  Intervention: { label: '干预', icon: '🧰', color: '#10B981' },
  Diagnosis: { label: '诊断', icon: '🏥', color: '#0EA5E9' },
  Organization: { label: '机构', icon: '🏛️', color: '#4F46E5' },
  Study: { label: '研究/实验', icon: '📑', color: '#0284C7' },
  Neurotransmitter: { label: '神经递质', icon: '🧪', color: '#D946EF' },
  Milestone: { label: '发展里程碑', icon: '🪜', color: '#16A34A' },
  Environment: { label: '环境', icon: '🌿', color: '#22C55E' },
};


/** 关系类型 → 中文标签 + 颜色 */
export const RELATION_LABELS: Record<string, { label: string; color: string }> = {
  // 因果
  CAUSAL_CAUSES: { label: '导致', color: '#DC2626' },
  CAUSAL_LEADS_TO: { label: '导向', color: '#DC2626' },
  CAUSAL_RESULTS_IN: { label: '产生', color: '#DC2626' },
  CAUSAL_CONTRIBUTES_TO: { label: '促成', color: '#EA580C' },
  CAUSAL_TRIGGERS: { label: '触发', color: '#DC2626' },
  // 治疗/干预
  THERAPEUTIC_TREATS: { label: '治疗', color: '#059669' },
  THERAPEUTIC_PREVENTS: { label: '预防', color: '#059669' },
  THERAPEUTIC_ALLEVIATES: { label: '缓解', color: '#059669' },
  THERAPEUTIC_IMPROVES: { label: '改善', color: '#059669' },
  THERAPEUTIC_INHIBITS: { label: '抑制', color: '#7C3AED' },
  THERAPEUTIC_ENHANCES: { label: '增强', color: '#059669' },
  // 结构
  STRUCTURAL_PART_OF: { label: '是…的一部分', color: '#6B7280' },
  STRUCTURAL_CONTAINS: { label: '包含', color: '#6B7280' },
  STRUCTURAL_CONSISTS_OF: { label: '由…组成', color: '#6B7280' },
  STRUCTURAL_BELONGS_TO: { label: '属于', color: '#6B7280' },
  // 功能
  FUNCTIONAL_REGULATES: { label: '调节', color: '#2563EB' },
  FUNCTIONAL_MODULATES: { label: '调制', color: '#2563EB' },
  FUNCTIONAL_PARTICIPATES_IN: { label: '参与', color: '#2563EB' },
  FUNCTIONAL_INVOLVED_IN: { label: '涉及', color: '#2563EB' },
  FUNCTIONAL_PLAYS_ROLE_IN: { label: '在…中发挥作用', color: '#2563EB' },
  FUNCTIONAL_MEDIATES: { label: '介导', color: '#2563EB' },
  FUNCTIONAL_TRANSFORMS: { label: '转化为', color: '#2563EB' },
  // 证据
  EVIDENCE_SUPPORTS: { label: '支持', color: '#0891B2' },
  EVIDENCE_PROVEN_BY: { label: '被…证明', color: '#0891B2' },
  EVIDENCE_BASED_ON: { label: '基于', color: '#0891B2' },
  EVIDENCE_CONTRADICTS: { label: '矛盾', color: '#F43F5E' },
  EVIDENCE_DEMONSTRATES: { label: '演示', color: '#0891B2' },
  // 时间
  TEMPORAL_PRECEDES: { label: '先于', color: '#D97706' },
  TEMPORAL_FOLLOWS: { label: '后于', color: '#D97706' },
  TEMPORAL_DURING: { label: '在…期间', color: '#D97706' },
  TEMPORAL_DEVELOPS_INTO: { label: '发展为', color: '#D97706' },
  // 比较
  COMPARISON_SIMILAR_TO: { label: '类似于', color: '#9333EA' },
  COMPARISON_DIFFERENT_FROM: { label: '不同于', color: '#9333EA' },
  COMPARISON_ALTERNATIVE_TO: { label: '替代', color: '#9333EA' },
  // 属性
  ATTRIBUTE_ASSOCIATED_WITH: { label: '相关', color: '#6B7280' },
  ATTRIBUTE_HAS_PROPERTY: { label: '具有属性', color: '#6B7280' },
  ATTRIBUTE_CHARACTERIZED_BY: { label: '以…为特征', color: '#6B7280' },
  ATTRIBUTE_MEASURED_BY: { label: '通过…测量', color: '#6B7280' },
  // 评估/诊断 (v3)
  ASSESSMENT_ASSESSES: { label: '评估', color: '#8B5CF6' },
  ASSESSMENT_DIAGNOSES: { label: '诊断', color: '#8B5CF6' },
  ASSESSMENT_MEASURES: { label: '测量', color: '#8B5CF6' },
  // 空间/归属 (v3)
  SPATIAL_LOCATED_IN: { label: '位于', color: '#06B6D4' },
  SPATIAL_CONNECTS_TO: { label: '连接', color: '#06B6D4' },
  // 层级/分类 (v3)
  HIERARCHICAL_SUBCLASS_OF: { label: '是…的子类', color: '#F59E0B' },
  HIERARCHICAL_INSTANCE_OF: { label: '是…的实例', color: '#F59E0B' },
  // 发布/创作 (v3)
  AUTHORSHIP_PUBLISHED_BY: { label: '由…发表', color: '#EC4899' },
  AUTHORSHIP_CITED_BY: { label: '被…引用', color: '#EC4899' },
  // 发展里程碑 (v3)
  DEVELOPMENTAL_EMERGES_AT: { label: '出现在…阶段', color: '#84CC16' },
  DEVELOPMENTAL_PREREQUISITE_FOR: { label: '是…的前提', color: '#84CC16' },
  // 兜底
  RELATES_TO: { label: '关联', color: '#A8A29E' },

  // 原有核心关系
  BELONGS_TO: { label: '属于', color: '#6366F1' },
  CAUSES: { label: '导致', color: '#DC2626' },
  SOLVES: { label: '解决', color: '#10B981' },
  PRESCRIBES: { label: '处方', color: '#F59E0B' },
  TARGETS: { label: '针对', color: '#2563EB' },
  AFFECTS: { label: '影响', color: '#EA580C' },
  REQUIRES: { label: '需要', color: '#0EA5E9' },
  CONTAINS_ENTITY: { label: '包含', color: '#6B7280' },
  SAME_AS: { label: '同义实体', color: '#22C55E' },
  OVERRIDES: { label: '覆盖', color: '#F43F5E' },
  ENHANCES: { label: '增强', color: '#10B981' },
  SUPPLEMENTS: { label: '补充', color: '#84CC16' },
  CONSENSUS: { label: '共识', color: '#16A34A' },
  COMPLEMENTS: { label: '互补', color: '#0EA5E9' },
  CONFLICTS: { label: '冲突', color: '#EF4444' },
};

/** 关系大类前缀 → 中文分类标签 */
const RELATION_CATEGORY_MAP: Record<string, string> = {
  CAUSAL: '因果',
  THERAPEUTIC: '干预',
  STRUCTURAL: '结构',
  FUNCTIONAL: '功能',
  EVIDENCE: '证据',
  TEMPORAL: '时间',
  COMPARISON: '比较',
  ATTRIBUTE: '属性',
  ASSESSMENT: '评估诊断',
  SPATIAL: '空间连接',
  HIERARCHICAL: '层级分类',
  AUTHORSHIP: '来源引用',
  DEVELOPMENTAL: '发展阶段',
  CORE: '核心关系',
  CUSTOMRULE: '自定义规则',
  CROSS: '跨书关系',
  BELONGS: '归属',
  CAUSES: '因果',
  SOLVES: '方案',
  PRESCRIBES: '处方',
  TARGETS: '目标',
  AFFECTS: '影响',
  REQUIRES: '依赖',
  CONTAINS: '结构',
  SAME: '同义',
  OVERRIDES: '覆盖',
  ENHANCES: '增强',
  SUPPLEMENTS: '补充',
  CONSENSUS: '共识',
  COMPLEMENTS: '互补',
  CONFLICTS: '冲突',
};

/**
 * Draft editor hook — manages draft content, entity parsing, and confirmations.
 */
export function useDraftEditor(bookId?: string) {
  const {
    currentDraft,
    draftContent,
    draftLoading,
    draftSaving,
    confirmedEntities,
    activeEntity,
    loadDraft,
    setDraftContent,
    saveDraft,
    markReviewed,
    publishToNeo4j,
    setActiveEntity,
    toggleConfirm,
  } = useCurationStore();

  useEffect(() => {
    if (bookId) loadDraft(bookId);
  }, [bookId, loadDraft]);

  // ── 跨书匹配数据获取 ──
  const [crossBookRelations, setCrossBookRelations] = useState<any[]>([]);
  const [crossBookLoading, setCrossBookLoading] = useState(false);
  const isCompareMode = typeof window !== 'undefined' && window.location.pathname.endsWith('/compare');

  useEffect(() => {
    if (isCompareMode && bookId) {
      setCrossBookLoading(true);
      curationApi.getCrossBookPairs([bookId])
        .then((res: any) => setCrossBookRelations(res.relations || []))
        .catch(() => setCrossBookRelations([]))
        .finally(() => setCrossBookLoading(false));
    }
  }, [isCompareMode, bookId]);

  // ── Parse entities from MD content ──
  const parsedEntities = useMemo<EntityItem[]>(() => {
    if (!draftContent) return [];
    const lines = draftContent.split('\n');
    const result: EntityItem[] = [];

    let currentName: string | null = null;
    let currentType = '';

    const flushEntity = () => {
      if (!currentName) return;
      result.push({
        name: currentName,
        type: currentType || 'AutoEntity',
        confirmed: confirmedEntities.has(currentName),
      });
      currentName = null;
      currentType = '';
    };

    for (const line of lines) {
      if (line.startsWith('### ')) {
        flushEntity();
        currentName = cleanEntityDisplayName(line.replace(/^###\s+/, ''));
        currentType = '';
        continue;
      }

      if (currentName) {
        const metaMatch = line.match(
          /^\s*-\s*\*\*(?:entity_type|实体类型)\*\*[：:]\s*([A-Za-z0-9_]+)/,
        );
        if (metaMatch) {
          currentType = metaMatch[1].trim();
        }
      }
    }

    flushEntity();
    return result;
  }, [draftContent, confirmedEntities]);

  // ── Parse relations from MD content ──
  const parsedRelations = useMemo<ExtractedRelation[]>(() => {
    if (!draftContent) return [];
    const lines = draftContent.split('\n');
    const relations: ExtractedRelation[] = [];
    let inClaims = false;
    let currentRel: Partial<ExtractedRelation> | null = null;
    let relIndex = 0;

    for (const line of lines) {
      // 检测「主张」章节开始
      if (/^##\s+主张/.test(line) || /^##\s+关系/.test(line) || /^##\s+Claims/.test(line)) {
        inClaims = true;
        continue;
      }
      // 遇到下一个 ## 章节时退出
      if (inClaims && /^##\s+/.test(line) && !/^##\s+主张/.test(line) && !/^##\s+关系/.test(line)) {
        inClaims = false;
        if (currentRel?.source && currentRel?.target) {
          relations.push(currentRel as ExtractedRelation);
        }
        currentRel = null;
        continue;
      }
      if (!inClaims) continue;

      // 匹配 ### source → target
      const headingMatch = line.match(/^###\s+(.+?)\s*[→>]\s*(.+)/);
      if (headingMatch) {
        // 保存上一条
        if (currentRel?.source && currentRel?.target) {
          relations.push(currentRel as ExtractedRelation);
        }
        currentRel = {
          id: `rel-${relIndex++}`,
          source: headingMatch[1].trim(),
          target: headingMatch[2].trim(),
          relationType: '',
          relationLabel: '',
          evidence: '',
          sourceParas: '',
        };
        continue;
      }

      if (!currentRel) continue;

      // 匹配 **field**: value
      const typeMatch = line.match(/\*\*(?:relation_type|关联类型)\*\*[：:]\s*(.+)/i);
      if (typeMatch) {
        const rawField = typeMatch[1].trim();
        const extractedEnum = rawField.match(/\(([\w_]+)\)\s*$/)?.[1] || rawField;
        currentRel.relationType = extractedEnum;
        const labelInfo = RELATION_LABELS[extractedEnum];
        currentRel.relationLabel = labelInfo?.label || rawField;
        continue;
      }

      const evidenceMatch = line.match(/\*\*evidence\*\*[：:]\s*(.+)/i);
      if (evidenceMatch) {
        currentRel.evidence = evidenceMatch[1].trim();
        continue;
      }

      const sourceMatch = line.match(/\*\*(?:来源|source)\*\*[：:]\s*(.+)/i);
      if (sourceMatch) {
        currentRel.sourceParas = sourceMatch[1].trim();
        continue;
      }
    }

    // 最后一条
    if (currentRel?.source && currentRel?.target) {
      relations.push(currentRel as ExtractedRelation);
    }

    return relations;
  }, [draftContent]);

  // ── 按选中实体过滤的关系 ──
  const activeEntityRelations = useMemo(() => {
    if (!activeEntity) return parsedRelations;
    return parsedRelations.filter(
      (r) => r.source === activeEntity || r.target === activeEntity,
    );
  }, [parsedRelations, activeEntity]);

  // ── 关系按大类分组 ──
  const groupedRelations = useMemo(() => {
    const groups: Record<string, ExtractedRelation[]> = {};
    for (const rel of (activeEntity ? activeEntityRelations : parsedRelations)) {
      const relType = rel.relationType || '';
      const prefix = relType.split('_')[0] || 'OTHER';
      const catLabel = RELATION_CATEGORY_MAP[relType] || RELATION_CATEGORY_MAP[prefix] || '其他';
      if (!groups[catLabel]) groups[catLabel] = [];
      groups[catLabel].push(rel);
    }
    return groups;
  }, [parsedRelations, activeEntityRelations, activeEntity]);

  // Group entities by type
  const groupedEntities = useMemo(() => {
    const groups: Record<string, EntityItem[]> = {};
    for (const entity of parsedEntities) {
      const type = entity.type || 'AutoEntity';
      if (!groups[type]) groups[type] = [];
      groups[type].push(entity);
    }
    return groups;
  }, [parsedEntities]);

  const totalEntities = parsedEntities.length;
  const confirmedCount = parsedEntities.filter((e) => confirmedEntities.has(e.name)).length;

  return {
    draft: currentDraft,
    content: draftContent,
    loading: draftLoading,
    saving: draftSaving,
    entities: parsedEntities,
    groupedEntities,
    confirmedEntities,
    activeEntity,
    totalEntities,
    confirmedCount,
    relations: parsedRelations,
    activeEntityRelations,
    groupedRelations,
    crossBookRelations,
    crossBookLoading,
    setContent: setDraftContent,
    save: saveDraft,
    markReviewed,
    publish: publishToNeo4j,
    setActiveEntity,
    toggleConfirm,
  };
}
const cleanEntityDisplayName = (raw: string) => {
  if (!raw) return raw;
  return raw
    .replace(/\s*\[[^\]]*提取\]\s*/g, ' ')
    .replace(/\s*\[[0-9a-fA-F-]{8,}[^\]]*\]\s*/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
};
