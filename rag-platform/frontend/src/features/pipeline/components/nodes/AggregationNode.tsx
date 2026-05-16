/**
 * 聚合层节点组件
 *
 * 6 种聚合节点共用，支持多个输入 Handle（每个域一个）
 */
import { memo, useCallback, useMemo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Tooltip } from 'antd'
import { usePipelineWorkbenchStore } from '../../stores/pipelineWorkbenchStore'

/** 聚合节点类型中文名称映射 */
const AGGREGATION_NODE_LABELS: Record<string, string> = {
  query_analyzer: '查询分析',
  domain_dispatch: '域分发',
  cross_fusion: '跨域融合',
  cross_dedup: '跨域去重',
  conflict_detect: '冲突检测',
  unified_generate: '统一生成',
}

/** 聚合节点图标映射 */
const AGGREGATION_NODE_ICONS: Record<string, string> = {
  query_analyzer: '🔎',
  domain_dispatch: '📤',
  cross_fusion: '🔀',
  cross_dedup: '🗑️',
  conflict_detect: '⚠️',
  unified_generate: '✨',
}

interface AggregationNodeData {
  type: string
  label: string
}

function AggregationNode({ data, selected }: NodeProps) {
  const { type, label } = data as unknown as AggregationNodeData

  const { selectNode, domains } = usePipelineWorkbenchStore()

  const typeLabel = AGGREGATION_NODE_LABELS[type] || type
  const icon = AGGREGATION_NODE_ICONS[type] || '🔀'
  const color = '#13c2c2'

  // 动态生成输入 Handle（每个域一个）
  const inputHandles = useMemo(() => {
    return domains.map((domain, index) => ({
      id: `domain-${domain.id}`,
      label: domain.name,
      position: (index + 1) / (domains.length + 1),
    }))
  }, [domains])

  // 点击选中
  const handleClick = useCallback(() => {
    selectNode(type)
  }, [type, selectNode])

  return (
    <div
      onClick={handleClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        background: '#fff',
        border: `2px solid ${selected ? color : '#d9d9d9'}`,
        borderRadius: 12,
        padding: '12px 16px',
        minWidth: 180,
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
          borderRadius: '10px 0 0 10px',
        }}
      />

      {/* 节点内容 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 20 }}>{icon}</span>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{label || typeLabel}</div>
          <div style={{ fontSize: 11, color: '#999' }}>聚合节点</div>
        </div>
      </div>

      {/* 域连接点指示器 */}
      {inputHandles.length > 0 && (
        <div
          style={{
            display: 'flex',
            gap: 4,
            flexWrap: 'wrap',
            justifyContent: 'center',
          }}
        >
          {inputHandles.map((handle) => (
            <Tooltip key={handle.id} title={handle.label}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#1890ff',
                }}
              />
            </Tooltip>
          ))}
        </div>
      )}

      {/* 多个输入 Handle（每个域一个） */}
      {inputHandles.map((handle) => (
        <Handle
          key={handle.id}
          type="target"
          id={handle.id}
          position={Position.Top}
          style={{
            background: '#1890ff',
            left: `${handle.position * 100}%`,
          }}
        />
      ))}

      {/* 单个输出 Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: color }}
      />
    </div>
  )
}

export default memo(AggregationNode)
