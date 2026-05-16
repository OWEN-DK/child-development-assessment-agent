/**
 * 降级边
 *
 * 橙色虚线，中间显示降级策略标签
 */
import { memo } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from '@xyflow/react'
import { Tag } from 'antd'

interface DegradationEdgeData {
  degradation?: {
    strategy: string
    fallbackNodeId?: string
  }
}

/** 降级策略中文映射 */
const STRATEGY_LABELS: Record<string, string> = {
  skip: '跳过',
  use_cache: '使用缓存',
  fallback_node: '回退节点',
  abort: '中止',
}

function DegradationEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  style = {},
  markerEnd,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  const degradation = (data as DegradationEdgeData)?.degradation
  const strategy = degradation?.strategy || 'skip'
  const strategyLabel = STRATEGY_LABELS[strategy] || strategy
  const label = degradation?.fallbackNodeId
    ? `降级: ${strategyLabel} → ${degradation.fallbackNodeId}`
    : `降级: ${strategyLabel}`

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: '#fa8c16',
          strokeWidth: 2,
          strokeDasharray: '8,4',
          ...style,
        }}
      />

      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
        >
          <Tag
            style={{
              background: '#fff7e6',
              border: '1px solid #fa8c16',
              borderRadius: 4,
              padding: '2px 8px',
              fontSize: 11,
              color: '#fa8c16',
              cursor: 'pointer',
            }}
          >
            {label}
          </Tag>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}

export default memo(DegradationEdge)
