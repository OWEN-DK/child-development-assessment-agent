/**
 * 通用节点组件
 *
 * 域内 22 种节点共用的通用模板
 */
import { memo, useCallback } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Tooltip } from 'antd'
import { usePipelineWorkbenchStore } from '../../stores/pipelineWorkbenchStore'
import type { NodeCategory } from '@/entities/pipeline/types'

/** 节点分类颜色映射 */
const CATEGORY_COLORS: Record<NodeCategory, string> = {
  query_understanding: '#1890ff',
  retrieval_strategy: '#52c41a',
  security_compliance: '#ff4d4f',
  quality_enhancement: '#722ed1',
  performance_optimization: '#fa8c16',
  answer_synthesis: '#faad14',
  aggregation: '#13c2c2',
}

/** 节点分类图标映射 */
const CATEGORY_ICONS: Record<NodeCategory, string> = {
  query_understanding: '✏️',
  retrieval_strategy: '🔍',
  security_compliance: '🛡️',
  quality_enhancement: '📊',
  performance_optimization: '⚡',
  answer_synthesis: '✨',
  aggregation: '🔀',
}

/** 节点类型中文名称映射 */
const NODE_TYPE_LABELS: Record<string, string> = {
  query_rewrite: '查询改写',
  synonym_expand: '同义词扩展',
  query_decompose: '查询分解',
  term_normalize: '术语标准化',
  intent_classify: '意图分类',
  stopword_filter: '禁用词过滤',
  query_expand: '查询扩展',
  bm25_search: 'BM25 检索',
  vector_search: '向量检索',
  hybrid_search: '混合检索',
  multimodal_search: '多模态检索',
  result_fusion: '结果融合',
  sensitive_filter: '敏感词过滤',
  pii_mask: 'PII 脱敏',
  content_audit: '内容审核',
  rerank: '重排序',
  dedup: '去重',
  hallucination_check: '幻觉检测',
  citation_verify: '引用验证',
  semantic_cache: '语义缓存',
  rate_limiter: '速率限制',
  structured_output: '结构化输出',
}

interface GenericNodeData {
  type: string
  label: string
  category: NodeCategory
  degradation?: {
    strategy: string
  }
}

function GenericNode({ data, selected }: NodeProps) {
  const { type, label, category, degradation } = data as unknown as GenericNodeData

  const { selectNode } = usePipelineWorkbenchStore()

  const color = CATEGORY_COLORS[category] || '#666'
  const icon = CATEGORY_ICONS[category] || '📦'
  const typeLabel = NODE_TYPE_LABELS[type] || type

  // 点击选中
  const handleClick = useCallback(() => {
    selectNode(type)
  }, [type, selectNode])

  return (
    <div
      onClick={handleClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        background: '#fff',
        border: `2px solid ${selected ? color : '#d9d9d9'}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 150,
        transition: 'all 0.2s',
        cursor: 'pointer',
        position: 'relative',
      }}
    >
      {/* 左侧颜色条 */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: 4,
          background: color,
          borderRadius: '6px 0 0 6px',
        }}
      />

      {/* 降级状态指示器 */}
      {degradation && (
        <Tooltip title={`降级策略: ${degradation.strategy}`}>
          <div
            style={{
              position: 'absolute',
              left: -8,
              top: '50%',
              transform: 'translateY(-50%)',
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: degradation.strategy === 'skip' ? '#52c41a' : '#fa8c16',
            }}
          />
        </Tooltip>
      )}

      {/* 节点内容 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <div>
          <div style={{ fontWeight: 500 }}>{label || typeLabel}</div>
          <div style={{ fontSize: 11, color: '#999' }}>{typeLabel}</div>
        </div>
      </div>

      {/* 输入 Handle */}
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: color }}
      />

      {/* 输出 Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: color }}
      />
    </div>
  )
}

export default memo(GenericNode)
