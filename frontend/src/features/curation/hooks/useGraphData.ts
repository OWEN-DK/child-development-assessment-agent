import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import type { Core } from 'cytoscape';
import { useCurationStore } from '../stores/curationStore';
import type { KGNode } from '../types';

const NODE_COLORS: Record<string, string> = {
  Problem: '#EF4444',
  Solution: '#10B981',
  BrainRegion: '#3B82F6',
  Exercise: '#F59E0B',
  Prescription: '#F59E0B',
  RootCause: '#EC4899',
  Book: '#6366F1',
  AutoEntity: '#8B5CF6',
  AutoCommunity: '#06B6D4',
  CognitiveProcess: '#14B8A6',
  Theory: '#8B5CF6',
  Mechanism: '#F97316',
  DevelopmentalStage: '#06B6D4',
  Strategy: '#84CC16',
  KeyInsight: '#EAB308',
  ResearchFinding: '#64748B',
};

const EDGE_COLORS: Record<string, string> = {
  RELATES_TO: '#A8A29E',
  CONSENSUS: '#10B981',
  COMPLEMENTS: '#0EA5E9',
  CONFLICTS: '#F43F5E',
  CONTAINS_ENTITY: '#6366F1',
  改善: '#10B981',
  导致: '#EF4444',
  抑制: '#F97316',
  促进: '#3B82F6',
  包含: '#8B5CF6',
  属于: '#6366F1',
  相关: '#A8A29E',
  替代: '#F59E0B',
  PRESCRIBES: '#F59E0B',
};

/**
 * Knowledge graph data hook — manages graph data, filtering, and Cytoscape interaction.
 */
export function useGraphData(bookId?: string) {
  const { kgData, kgLoading, kgError, loadGraph } = useCurationStore();
  const cyRef = useRef<Core | null>(null);
  const [searchText, setSearchText] = useState('');
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [selectedNode, setSelectedNode] = useState<KGNode | null>(null);
  const [conflictFocus, setConflictFocus] = useState(false);

  useEffect(() => {
    loadGraph(bookId);
  }, [bookId, loadGraph]);

  const nodeTypes = useMemo(
    () => (kgData ? [...new Set(kgData.nodes.map((n) => n.type))] : []),
    [kgData],
  );

  const conflictCount = useMemo(
    () => kgData?.edges.filter((e) => e.type === 'CONFLICTS').length || 0,
    [kgData],
  );

  // Build Cytoscape elements
  const elements = useMemo(() => {
    if (!kgData) return [];
    const els: any[] = [];
    const filteredNodes = kgData.nodes.filter((n) => {
      const matchSearch = !searchText || n.label.includes(searchText) || n.description?.includes(searchText);
      const matchType = !typeFilter || n.type === typeFilter;
      return matchSearch && matchType;
    });
    const nodeIds = new Set(filteredNodes.map((n) => n.id));

    for (const node of filteredNodes) {
      const color = NODE_COLORS[node.type] || '#78716C';
      const isConflict = kgData.edges.some(
        (e) => (e.source === node.id || e.target === node.id) && e.type === 'CONFLICTS',
      );
      els.push({
        data: {
          id: node.id,
          label: node.label,
          type: node.type,
          color,
          borderColor: isConflict ? '#F43F5E' : color,
          degree: kgData.edges.filter((e) => e.source === node.id || e.target === node.id).length,
          description: node.description,
        },
        classes: isConflict ? 'conflict' : '',
      });
    }

    for (const edge of kgData.edges) {
      if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
        const color = EDGE_COLORS[edge.type] || '#A8A29E';
        const edgeLabel = edge.label || edge.type;
        els.push({
          data: {
            id: `${edge.source}-${edge.target}-${edge.type}`,
            source: edge.source,
            target: edge.target,
            type: edge.type,
            label: edgeLabel,
            color,
            lineStyle: edge.type === 'CONFLICTS' ? 'dashed' : 'solid',
            weight: edge.weight || 1,
          },
          classes: edge.type === 'CONFLICTS' ? 'conflict-edge' : '',
        });
      }
    }
    return els;
  }, [kgData, searchText, typeFilter]);

  const handleCyInit = useCallback(
    (cy: Core) => {
      cyRef.current = cy;
      cy.on('tap', 'node', (evt: any) => {
        const nodeData = evt.target.data();
        const kgNode = kgData?.nodes.find((n) => n.id === nodeData.id);
        if (kgNode) setSelectedNode(kgNode);
      });
      cy.on('tap', (evt: any) => {
        if (evt.target === cy) setSelectedNode(null);
      });
    },
    [kgData],
  );

  const toggleConflictFocus = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const next = !conflictFocus;
    setConflictFocus(next);
    if (next) {
      cy.elements().forEach((ele: any) => {
        if (ele.hasClass('conflict') || ele.hasClass('conflict-edge')) ele.removeClass('faded');
        else ele.addClass('faded');
      });
    } else {
      cy.elements().removeClass('faded');
    }
  }, [conflictFocus]);

  const exportPNG = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const png = cy.png({ bg: 'white', full: true, scale: 2 });
    const a = document.createElement('a');
    a.href = png;
    a.download = `knowledge-graph-${bookId || 'all'}.png`;
    a.click();
  }, [bookId]);

  return {
    data: kgData,
    loading: kgLoading,
    error: kgError,
    elements,
    nodeTypes,
    conflictCount,
    searchText,
    setSearchText,
    typeFilter,
    setTypeFilter,
    selectedNode,
    setSelectedNode,
    conflictFocus,
    toggleConflictFocus,
    handleCyInit,
    exportPNG,
    refresh: () => loadGraph(bookId),
    NODE_COLORS,
    EDGE_COLORS,
  };
}
