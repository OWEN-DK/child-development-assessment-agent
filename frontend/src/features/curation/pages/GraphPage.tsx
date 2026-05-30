import React, { useState } from 'react';
import { Button, Select, Tooltip, Spin, Empty, Input } from 'antd';
import {
  ReloadOutlined,
  SearchOutlined,
  DownloadOutlined,
  ApartmentOutlined,
  EyeOutlined,
  ArrowLeftOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useGraphData } from '../hooks/useGraphData';
import { curationApi } from '../api/curationApi';
import { GraphCanvas } from '../components/GraphCanvas';
import { NodeDetail } from '../components/NodeDetail';
import styles from './GraphPage.module.scss';

const NODE_LABELS: Record<string, string> = {
  Problem: '问题',
  Solution: '方案',
  BrainRegion: '脑区',
  CognitiveProcess: '认知过程',
  Theory: '理论',
  Mechanism: '机制',
  DevelopmentalStage: '发展阶段',
  Strategy: '策略',
  KeyInsight: '核心洞见',
  ResearchFinding: '研究发现',
  Exercise: '运动',
  Prescription: '处方',
  RootCause: '根因',
  Book: '书籍',
  AutoEntity: '自动实体',
  AutoCommunity: '社区',
};

export const GraphPage: React.FC = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const [searchParams] = useSearchParams();
  const compareParam = searchParams.get('compare');
  const compareBookIds = compareParam ? compareParam.split(',') : [];
  const isCompareMode = compareBookIds.length >= 2;
  const navigate = useNavigate();
  const [showLegend, setShowLegend] = useState(true);

  const handleExportCypher = async () => {
    try {
      const res = await curationApi.exportCypher(bookId);
      const blob = new Blob([res.statements.join('\n')], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `knowledge-graph-${bookId || 'all'}.cypher`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // handled silently
    }
  };

  const {
    data,
    loading,
    error,
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
    refresh,
    NODE_COLORS,
  } = useGraphData(bookId);

  return (
    <div className={styles['graph-page']}>
      <div className={styles.toolbar}>
        <div className={styles.toolbar__left}>
          <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/curation')} />
          <span className={styles.toolbar__title}>
            <ApartmentOutlined /> 知识图谱
            {isCompareMode ? ` · 多书对比 (${compareBookIds.length} 本)` : bookId && ` · ${bookId}`}
          </span>
          <Input
            placeholder="搜索节点..."
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 200 }}
            size="small"
            allowClear
          />
          <Select
            placeholder="类型筛选"
            allowClear
            value={typeFilter}
            onChange={setTypeFilter}
            style={{ width: 140 }}
            size="small"
            options={nodeTypes.map((t) => ({ label: t, value: t }))}
          />
        </div>
        <div className={styles.toolbar__right}>
          {isCompareMode && compareBookIds.length > 0 && (
            <Select
              mode="multiple"
              placeholder="按书籍筛选"
              allowClear
              value={compareBookIds}
              style={{ width: 200 }}
              size="small"
              disabled
              options={compareBookIds.map((id: string) => ({ label: id.substring(0, 12) + '...', value: id }))}
            />
          )}
          {conflictCount > 0 && (
            <Tooltip title="聚焦冲突关系">
              <Button
                size="small"
                type={conflictFocus ? 'primary' : 'default'}
                danger={conflictFocus}
                onClick={toggleConflictFocus}
              >
                ⚠️ {conflictCount} 冲突
              </Button>
            </Tooltip>
          )}
          <Tooltip title="显示图例">
            <Button
              size="small"
              icon={<EyeOutlined />}
              type={showLegend ? 'primary' : 'default'}
              onClick={() => setShowLegend(!showLegend)}
            />
          </Tooltip>
          <Button size="small" icon={<DownloadOutlined />} onClick={exportPNG}>
            导出 PNG
          </Button>
          <Button size="small" icon={<CodeOutlined />} onClick={handleExportCypher}>
            导出 Cypher
          </Button>
          <Button size="small" icon={<ReloadOutlined />} onClick={refresh} loading={loading}>
            刷新
          </Button>
        </div>
      </div>

      <div className={styles['canvas-wrapper']}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Spin size="large" />
          </div>
        ) : error ? (
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', gap: 12 }}>
            <Empty description={null} />
            <div style={{ color: '#F43F5E', fontSize: 14 }}>⚠️ {error}</div>
            <div style={{ color: '#8B847C', fontSize: 13 }}>请确认 Neo4j 服务已启动并配置正确</div>
            <Button size="small" icon={<ReloadOutlined />} onClick={refresh}>重试</Button>
          </div>
        ) : elements.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Empty description="暂无知识图谱数据" />
          </div>
        ) : (
          <GraphCanvas elements={elements} onInit={handleCyInit} />
        )}

        {data && (
          <div className={styles['stats-bar']}>
            <span>{data.nodes.length} 节点</span>
            <span>{data.edges.length} 关系</span>
            {conflictCount > 0 && <span style={{ color: '#F43F5E' }}>{conflictCount} 冲突</span>}
            {isCompareMode && <span style={{ color: '#10B981' }}>对比模式: {compareBookIds.join(' vs ')}</span>}
          </div>
        )}

        {showLegend && (
          <div className={styles.legend}>
            <div className={styles.legend__title}>图例</div>
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <div key={type} className={styles.legend__item}>
                <div className={styles.legend__dot} style={{ background: color }} />
                <span>{NODE_LABELS[type] || type}</span>
              </div>
            ))}
            <div className={styles.legend__item}>
              <div className={styles.legend__line} style={{ background: '#A8A29E' }} />
              <span>普通关系</span>
            </div>
            <div className={styles.legend__item}>
              <div className={styles.legend__line} style={{ background: '#10B981' }} />
              <span>共识</span>
            </div>
            <div className={styles.legend__item}>
              <div className={styles.legend__line} style={{ background: '#0EA5E9' }} />
              <span>互补</span>
            </div>
            <div className={styles.legend__item}>
              <div className={`${styles.legend__line} ${styles['legend__line--dashed']}`} />
              <span>冲突</span>
            </div>
          </div>
        )}

        {selectedNode && (
          <NodeDetail
            node={selectedNode}
            edgeCount={data?.edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id).length}
            connectedEdges={data?.edges
              .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
              .map((e) => {
                const isIn = e.target === selectedNode.id;
                const counterId = isIn ? e.source : e.target;
                const counterNode = data?.nodes.find((n) => n.id === counterId);
                return {
                  id: `${e.source}-${e.target}-${e.type}`,
                  source: e.source,
                  target: e.target,
                  type: e.type,
                  label: e.label,
                  counterpartLabel: counterNode?.label || counterId,
                  counterpartType: counterNode?.type || 'Unknown',
                  direction: isIn ? 'in' as const : 'out' as const,
                };
              }) || []
            }
            onClose={() => setSelectedNode(null)}
            onNodeClick={(nodeId) => {
              const node = data?.nodes.find((n) => n.id === nodeId);
              if (node) setSelectedNode(node);
            }}
          />
        )}
      </div>
    </div>
  );
};
