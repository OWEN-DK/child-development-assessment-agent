import { useEffect, useMemo, useState } from 'react';
import { useCurationStore } from '../stores/curationStore';
import { curationApi } from '../api/curationApi';
import type { EntityItem } from '../types';

const ENTITY_TYPES = ['Problem', 'Solution', 'BrainRegion', 'Exercise', 'Prescription', 'RootCause'];

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

  // ── 跨书匹配数据获取（§08-3） ──
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

  // Parse entities from MD content
  const parsedEntities = useMemo<EntityItem[]>(() => {
    if (!draftContent) return [];
    const lines = draftContent.split('\n');
    const result: EntityItem[] = [];
    let currentType = '';

    for (const line of lines) {
      const typeMatch = line.match(/^##\s+(问题|方案|脑区|运动|处方|根因)/);
      if (typeMatch) {
        const typeMap: Record<string, string> = {
          '问题': 'Problem', '方案': 'Solution', '脑区': 'BrainRegion',
          '运动': 'Exercise', '处方': 'Prescription', '根因': 'RootCause',
        };
        currentType = typeMap[typeMatch[1]] || '';
        continue;
      }
      const entityMatch = line.match(/^###\s+(.+)/);
      if (entityMatch && currentType) {
        result.push({
          name: entityMatch[1].trim(),
          type: currentType,
          confirmed: confirmedEntities.has(entityMatch[1].trim()),
        });
      }
    }
    return result;
  }, [draftContent, confirmedEntities]);

  // Group entities by type
  const groupedEntities = useMemo(() => {
    const groups: Record<string, EntityItem[]> = {};
    for (const type of ENTITY_TYPES) {
      const items = parsedEntities.filter((e) => e.type === type);
      if (items.length > 0) groups[type] = items;
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
