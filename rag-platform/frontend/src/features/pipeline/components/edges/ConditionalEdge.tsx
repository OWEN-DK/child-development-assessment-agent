/**
 * 条件边
 *
 * 灰色虚线，中间显示条件标签
 */
import { memo } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from '@xyflow/react'
import { Tag } from 'antd'

interface ConditionalEdgeData {
  condition?: {
    field: string
    operator: string
    value: string | number
  }
}

function ConditionalEdge({
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

  const condition = (data as ConditionalEdgeData)?.condition
  const conditionLabel = condition
    ? `${condition.field} ${condition.operator} ${condition.value}`
    : '条件'

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: '#8c8c8c',
          strokeWidth: 2,
          strokeDasharray: '5,5',
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
              background: '#fff',
              border: '1px solid #d9d9d9',
              borderRadius: 4,
              padding: '2px 8px',
              fontSize: 11,
              cursor: 'pointer',
            }}
          >
            {conditionLabel}
          </Tag>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}

export default memo(ConditionalEdge)
