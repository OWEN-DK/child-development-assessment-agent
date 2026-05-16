/**
 * 管道画布
 *
 * React Flow 画布组件，支持节点拖拽、连线、缩放等交互
 */
import { useCallback, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Node,
  type NodeTypes,
  type EdgeTypes,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { usePipelineWorkbenchStore } from '../../stores/pipelineWorkbenchStore'
import NodePanel from '../NodePanel/NodePanel'
import PropertyPanel from '../PropertyPanel/PropertyPanel'
import DomainContainerNode from '../DomainContainer/DomainContainerNode'
import GenericNode from '../nodes/GenericNode'
import AggregationNode from '../nodes/AggregationNode'
import CompoundNode from '../nodes/CompoundNode'
import DataFlowEdge from '../edges/DataFlowEdge'
import ConditionalEdge from '../edges/ConditionalEdge'
import DegradationEdge from '../edges/DegradationEdge'

// 自定义节点类型映射
const nodeTypes: NodeTypes = {
  domainContainer: DomainContainerNode,
  // 域内节点（使用 GenericNode）
  queryRewrite: GenericNode,
  synonymExpand: GenericNode,
  queryDecompose: GenericNode,
  termNormalize: GenericNode,
  intentClassify: GenericNode,
  stopwordFilter: GenericNode,
  queryExpand: GenericNode,
  bm25Search: GenericNode,
  vectorSearch: GenericNode,
  hybridSearch: GenericNode,
  multimodalSearch: GenericNode,
  resultFusion: GenericNode,
  sensitiveFilter: GenericNode,
  piiMask: GenericNode,
  contentAudit: GenericNode,
  rerank: GenericNode,
  dedup: GenericNode,
  hallucinationCheck: GenericNode,
  citationVerify: GenericNode,
  semanticCache: GenericNode,
  rateLimiter: GenericNode,
  structuredOutput: GenericNode,
  // 聚合节点
  queryAnalyzer: AggregationNode,
  domainDispatch: AggregationNode,
  crossFusion: AggregationNode,
  crossDedup: AggregationNode,
  conflictDetect: AggregationNode,
  unifiedGenerate: AggregationNode,
  // 复合节点
  compound: CompoundNode,
}

// 自定义边类型映射
const edgeTypes: EdgeTypes = {
  dataFlow: DataFlowEdge,
  conditional: ConditionalEdge,
  degradation: DegradationEdge,
}

export default function PipelineCanvas() {
  const {
    domains,
    aggregationNodes,
    edges,
    addNode,
    addEdge: addEdgeToStore,
    selectNode,
    selectDomain,
  } = usePipelineWorkbenchStore()

  // 转换为 React Flow 节点格式
  const flowNodes = useMemo(() => {
    const nodes: Node[] = []

    // 域容器节点
    domains.forEach((domain) => {
      nodes.push({
        id: domain.id,
        type: 'domainContainer',
        position: { x: 0, y: 0 }, // TODO: 从 domain 配置获取位置
        data: {
          ...domain,
          collapsed: domain.collapsed,
        },
      })

      // 域内节点
      domain.nodeIds.forEach((nodeId) => {
        // TODO: 从 store 获取节点配置
        nodes.push({
          id: nodeId,
          type: 'queryRewrite', // TODO: 根据节点类型动态设置
          position: { x: 0, y: 0 }, // TODO: 从节点配置获取位置
          parentId: domain.id,
          extent: 'parent' as const,
          data: {} as Record<string, unknown>,
        })
      })
    })

    // 聚合节点
    aggregationNodes.forEach((node) => {
      nodes.push({
        id: node.id,
        type: node.type,
        position: node.position,
        data: node as unknown as Record<string, unknown>,
      })
    })

    return nodes
  }, [domains, aggregationNodes])

  // 转换为 React Flow 边格式
  const flowEdges = useMemo(() => {
    return edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: edge.type,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
      data: {
        condition: edge.condition,
        degradation: edge.degradation,
      },
    }))
  }, [edges])

  // 使用 React Flow 状态管理
  const [nodes, , onNodesChange] = useNodesState(flowNodes)
  const [edgeList, setEdges, onEdgesChange] = useEdgesState(flowEdges)

  // 连线回调
  const onConnect = useCallback(
    (connection: Connection) => {
      const newEdge = {
        ...connection,
        id: `edge-${Date.now()}`,
        type: 'dataFlow',
      }
      addEdgeToStore(newEdge as any)
      setEdges((eds) => addEdge(newEdge as any, eds))
    },
    [addEdgeToStore, setEdges]
  )

  // 节点点击
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      selectNode(node.id)
    },
    [selectNode]
  )

  // 画布点击（取消选中）
  const onPaneClick = useCallback(() => {
    selectNode(null)
    selectDomain(null)
  }, [selectNode, selectDomain])

  // 拖放处理
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const data = event.dataTransfer.getData('application/json')
      if (!data) return

      try {
        const { nodeType, domainId } = JSON.parse(data)

        // 获取画布坐标
        const position = {
          x: event.clientX,
          y: event.clientY,
        }

        addNode(domainId || null, nodeType, position)
      } catch (error) {
        console.error('拖放解析失败:', error)
      }
    },
    [addNode]
  )

  // 拖拽悬停
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* 左侧节点面板 */}
      <NodePanel />

      {/* 中央画布 */}
      <div style={{ flex: 1, position: 'relative' }}>
        <ReactFlow
          nodes={nodes}
          edges={edgeList}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onDrop={onDrop}
          onDragOver={onDragOver}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          minZoom={0.25}
          maxZoom={2}
          deleteKeyCode="Delete"
          snapToGrid
          snapGrid={[12, 12]}
        >
          <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
          <MiniMap
            nodeStrokeWidth={3}
            zoomable
            pannable
            style={{ height: 120, width: 180 }}
          />
          <Controls showZoom showFitView showInteractive={false} />
        </ReactFlow>

        {/* 添加业务域按钮 */}
        <div
          style={{
            position: 'absolute',
            top: 16,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 10,
          }}
        >
          <button
            onClick={() => {
              // TODO: 打开域创建对话框
              console.log('添加业务域')
            }}
            style={{
              padding: '8px 16px',
              background: '#1890ff',
              color: '#fff',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
            }}
          >
            + 添加业务域
          </button>
        </div>
      </div>

      {/* 右侧属性面板 */}
      <PropertyPanel />
    </div>
  )
}
