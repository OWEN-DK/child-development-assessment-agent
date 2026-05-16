/**
 * 管道工作台状态管理
 *
 * 管理管道编辑器的核心状态，包括：
 * - 管道基础信息
 * - 编辑视图状态（域、节点、边）
 * - 撤销/重做
 * - 复合节点库
 */
import { create } from 'zustand'
import type {
  PipelineConfig,
  PipelineSnapshot,
  DomainConfig,
  PipelineNode,
  EdgeConfig,
  NodeType,
  CompoundNodeConfig,
  ValidationResult,
  DryRunResult,
} from '@/entities/pipeline/types'
import * as pipelineApi from '@/api/pipeline/pipeline'

// 性能约束常量
const MAX_DOMAINS = 20
const MAX_NODES_PER_DOMAIN = 30
const MAX_TOTAL_NODES = 100
const MAX_UNDO_STACK_SIZE = 50

/** 工作台视图类型 */
export type WorkbenchView = 'edit' | 'evaluate' | 'publish'

/** 管道工作台状态 */
interface PipelineWorkbenchState {
  // 基础状态
  pipelineId: string | null
  pipelineName: string
  pipelineVersion: number
  activeView: WorkbenchView
  isLoading: boolean
  isSaving: boolean
  error: string | null

  // 编辑视图状态
  domains: DomainConfig[]
  aggregationNodes: PipelineNode[]
  edges: EdgeConfig[]
  selectedNodeId: string | null
  selectedDomainId: string | null
  isDirty: boolean

  // 撤销/重做
  undoStack: PipelineSnapshot[]
  redoStack: PipelineSnapshot[]

  // 复合节点库
  compoundNodeLibrary: CompoundNodeConfig[]

  // 操作方法
  switchView: (view: WorkbenchView) => void
  addNode: (domainId: string | null, nodeType: NodeType, position: { x: number; y: number }) => void
  removeNode: (nodeId: string) => void
  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => void
  addEdge: (edge: EdgeConfig) => void
  removeEdge: (edgeId: string) => void
  addDomain: (domainConfig: Omit<DomainConfig, 'id' | 'nodeIds' | 'collapsed'>) => void
  removeDomain: (domainId: string) => void
  updateDomainConfig: (domainId: string, config: Partial<DomainConfig>) => void
  moveNodeToDomain: (nodeId: string, targetDomainId: string) => void
  save: () => Promise<void>
  validate: () => Promise<ValidationResult>
  dryRun: (query: string, params?: Record<string, unknown>) => Promise<DryRunResult>
  loadPipeline: (pipelineId: string) => Promise<void>
  loadCompoundNodeLibrary: () => Promise<void>

  // 撤销/重做
  snapshot: () => void
  undo: () => void
  redo: () => void

  // 选择
  selectNode: (nodeId: string | null) => void
  selectDomain: (domainId: string | null) => void

  // 性能约束检查
  checkDomainLimit: () => boolean
  checkNodeLimit: (domainId: string) => boolean
  checkTotalNodeLimit: () => boolean
  checkCompoundNesting: (compoundId: string) => boolean

  // 内部方法
  _findNode: (nodeId: string) => PipelineNode | null
  _findDomain: (domainId: string) => DomainConfig | null
  _generateId: () => string
}

/** 生成唯一ID */
const generateId = (): string => {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

/** 创建管道快照 */
const createSnapshot = (state: PipelineWorkbenchState): PipelineSnapshot => ({
  domains: JSON.parse(JSON.stringify(state.domains)),
  aggregationNodes: JSON.parse(JSON.stringify(state.aggregationNodes)),
  edges: JSON.parse(JSON.stringify(state.edges)),
  timestamp: Date.now(),
})

export const usePipelineWorkbenchStore = create<PipelineWorkbenchState>((set, get) => ({
  // 初始状态
  pipelineId: null,
  pipelineName: '',
  pipelineVersion: 0,
  activeView: 'edit',
  isLoading: false,
  isSaving: false,
  error: null,

  domains: [],
  aggregationNodes: [],
  edges: [],
  selectedNodeId: null,
  selectedDomainId: null,
  isDirty: false,

  undoStack: [],
  redoStack: [],

  compoundNodeLibrary: [],

  // 切换视图
  switchView: (view) => {
    const state = get()
    if (state.activeView === 'edit' && state.isDirty) {
      // TODO: 弹出确认对话框
      console.warn('有未保存的更改')
    }
    set({ activeView: view })
  },

  // 添加节点
  addNode: (domainId, nodeType, position) => {
    const state = get()

    // 性能约束检查
    if (domainId) {
      if (!state.checkNodeLimit(domainId)) {
        console.error(`单个域最多 ${MAX_NODES_PER_DOMAIN} 个节点`)
        return
      }
    }

    const newNode: PipelineNode = {
      id: state._generateId(),
      type: nodeType,
      label: nodeType, // TODO: 从元数据获取中文名称
      category: 'query_understanding', // TODO: 从元数据获取分类
      config: {},
      position,
      domainId: domainId || undefined,
    }

    state.snapshot()

    if (domainId) {
      const domain = state.domains.find((d) => d.id === domainId)
      if (domain) {
        set({
          domains: state.domains.map((d) =>
            d.id === domainId ? { ...d, nodeIds: [...d.nodeIds, newNode.id] } : d
          ),
          isDirty: true,
        })
      }
    } else {
      set({
        aggregationNodes: [...state.aggregationNodes, newNode],
        isDirty: true,
      })
    }
  },

  // 删除节点
  removeNode: (nodeId) => {
    const state = get()
    state.snapshot()

    // 删除关联的边
    const newEdges = state.edges.filter(
      (e) => e.source !== nodeId && e.target !== nodeId
    )

    // 从域中移除节点
    const newDomains = state.domains.map((d) => ({
      ...d,
      nodeIds: d.nodeIds.filter((id) => id !== nodeId),
    }))

    // 从聚合节点中移除
    const newAggregationNodes = state.aggregationNodes.filter((n) => n.id !== nodeId)

    set({
      domains: newDomains,
      aggregationNodes: newAggregationNodes,
      edges: newEdges,
      selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId,
      isDirty: true,
    })
  },

  // 更新节点配置
  updateNodeConfig: (nodeId, config) => {
    const state = get()
    state.snapshot()

    // 更新聚合节点
    const newAggregationNodes = state.aggregationNodes.map((n) =>
      n.id === nodeId ? { ...n, config: { ...n.config, ...config } } : n
    )

    set({
      aggregationNodes: newAggregationNodes,
      isDirty: true,
    })
  },

  // 添加边
  addEdge: (edge) => {
    const state = get()

    // 检查循环引用
    if (state.edges.some((e) => e.source === edge.target && e.target === edge.source)) {
      console.error('检测到循环引用')
      return
    }

    state.snapshot()

    set({
      edges: [...state.edges, edge],
      isDirty: true,
    })
  },

  // 删除边
  removeEdge: (edgeId) => {
    const state = get()
    state.snapshot()

    set({
      edges: state.edges.filter((e) => e.id !== edgeId),
      isDirty: true,
    })
  },

  // 添加域
  addDomain: (domainConfig) => {
    const state = get()

    if (!state.checkDomainLimit()) {
      console.error(`单管道最多 ${MAX_DOMAINS} 个业务域`)
      return
    }

    state.snapshot()

    const newDomain: DomainConfig = {
      ...domainConfig,
      id: state._generateId(),
      nodeIds: [],
      collapsed: false,
    }

    set({
      domains: [...state.domains, newDomain],
      isDirty: true,
    })
  },

  // 删除域
  removeDomain: (domainId) => {
    const state = get()
    state.snapshot()

    const domain = state.domains.find((d) => d.id === domainId)
    if (!domain) return

    // 删除域内的所有节点
    const nodeIdsToRemove = new Set(domain.nodeIds)
    const newAggregationNodes = state.aggregationNodes.filter(
      (n) => !nodeIdsToRemove.has(n.id)
    )
    const newEdges = state.edges.filter(
      (e) => !nodeIdsToRemove.has(e.source) && !nodeIdsToRemove.has(e.target)
    )

    set({
      domains: state.domains.filter((d) => d.id !== domainId),
      aggregationNodes: newAggregationNodes,
      edges: newEdges,
      selectedDomainId: state.selectedDomainId === domainId ? null : state.selectedDomainId,
      isDirty: true,
    })
  },

  // 更新域配置
  updateDomainConfig: (domainId, config) => {
    const state = get()
    state.snapshot()

    set({
      domains: state.domains.map((d) =>
        d.id === domainId ? { ...d, ...config } : d
      ),
      isDirty: true,
    })
  },

  // 移动节点到域
  moveNodeToDomain: (nodeId, targetDomainId) => {
    const state = get()

    // 检查目标域节点数限制
    if (!state.checkNodeLimit(targetDomainId)) {
      console.error(`目标域最多 ${MAX_NODES_PER_DOMAIN} 个节点`)
      return
    }

    state.snapshot()

    // 从原域移除
    const newDomains = state.domains.map((d) => ({
      ...d,
      nodeIds: d.nodeIds.filter((id) => id !== nodeId),
    }))

    // 添加到目标域
    const targetDomain = newDomains.find((d) => d.id === targetDomainId)
    if (targetDomain) {
      targetDomain.nodeIds.push(nodeId)
    }

    set({
      domains: newDomains,
      isDirty: true,
    })
  },

  // 保存管道
  save: async () => {
    const state = get()
    if (!state.pipelineId) return

    // 总节点数检查
    if (!state.checkTotalNodeLimit()) {
      throw new Error(`总节点数超过 ${MAX_TOTAL_NODES} 个限制`)
    }

    set({ isSaving: true, error: null })

    try {
      const config: PipelineConfig = {
        domains: state.domains,
        aggregationNodes: state.aggregationNodes,
        edges: state.edges,
      }

      const result = await pipelineApi.savePipeline(state.pipelineId, {
        configSnapshot: config,
        version: state.pipelineVersion,
      })

      set({
        pipelineVersion: result.version,
        isDirty: false,
        isSaving: false,
        undoStack: [],
        redoStack: [],
      })
    } catch (error) {
      set({
        isSaving: false,
        error: error instanceof Error ? error.message : '保存失败',
      })
      throw error
    }
  },

  // 校验管道
  validate: async () => {
    const state = get()
    if (!state.pipelineId) {
      return { valid: false, errors: [{ message: '管道未加载', severity: 'error' }] }
    }

    const config: PipelineConfig = {
      domains: state.domains,
      aggregationNodes: state.aggregationNodes,
      edges: state.edges,
    }

    return pipelineApi.validatePipeline(state.pipelineId, config)
  },

  // 干运行
  dryRun: async (query, params) => {
    const state = get()
    if (!state.pipelineId) {
      return { success: false, executionPlan: [], errors: [{ message: '管道未加载', severity: 'error' }] }
    }

    const config: PipelineConfig = {
      domains: state.domains,
      aggregationNodes: state.aggregationNodes,
      edges: state.edges,
    }

    return pipelineApi.dryRunPipeline(state.pipelineId, config, { query, params })
  },

  // 加载管道
  loadPipeline: async (pipelineId) => {
    set({ isLoading: true, error: null, pipelineId })

    try {
      const pipeline = await pipelineApi.getPipeline(pipelineId)

      set({
        pipelineName: pipeline.name,
        pipelineVersion: pipeline.version,
        domains: pipeline.configSnapshot.domains || [],
        aggregationNodes: pipeline.configSnapshot.aggregationNodes || [],
        edges: pipeline.configSnapshot.edges || [],
        isLoading: false,
        isDirty: false,
        undoStack: [],
        redoStack: [],
      })
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : '加载失败',
      })
    }
  },

  // 加载复合节点库
  loadCompoundNodeLibrary: async () => {
    try {
      await pipelineApi.getCompoundNodes()
      // TODO: 转换为 CompoundNodeConfig 格式
      set({ compoundNodeLibrary: [] })
    } catch (error) {
      console.error('加载复合节点库失败:', error)
    }
  },

  // 创建快照
  snapshot: () => {
    const state = get()
    const snapshot = createSnapshot(state)
    const newUndoStack = [...state.undoStack, snapshot]

    // 限制栈深度
    if (newUndoStack.length > MAX_UNDO_STACK_SIZE) {
      newUndoStack.shift()
    }

    set({
      undoStack: newUndoStack,
      redoStack: [], // 新操作清空重做栈
    })
  },

  // 撤销
  undo: () => {
    const state = get()
    if (state.undoStack.length === 0) return

    const snapshot = state.undoStack[state.undoStack.length - 1]
    const currentSnapshot = createSnapshot(state)

    set({
      domains: snapshot.domains,
      aggregationNodes: snapshot.aggregationNodes,
      edges: snapshot.edges,
      undoStack: state.undoStack.slice(0, -1),
      redoStack: [...state.redoStack, currentSnapshot],
      isDirty: true,
    })
  },

  // 重做
  redo: () => {
    const state = get()
    if (state.redoStack.length === 0) return

    const snapshot = state.redoStack[state.redoStack.length - 1]
    const currentSnapshot = createSnapshot(state)

    set({
      domains: snapshot.domains,
      aggregationNodes: snapshot.aggregationNodes,
      edges: snapshot.edges,
      redoStack: state.redoStack.slice(0, -1),
      undoStack: [...state.undoStack, currentSnapshot],
      isDirty: true,
    })
  },

  // 选择节点
  selectNode: (nodeId) => {
    set({ selectedNodeId: nodeId, selectedDomainId: null })
  },

  // 选择域
  selectDomain: (domainId) => {
    set({ selectedDomainId: domainId, selectedNodeId: null })
  },

  // 检查域数量限制
  checkDomainLimit: () => {
    const state = get()
    return state.domains.length < MAX_DOMAINS
  },

  // 检查单域节点数限制
  checkNodeLimit: (domainId) => {
    const state = get()
    const domain = state.domains.find((d) => d.id === domainId)
    if (!domain) return false
    return domain.nodeIds.length < MAX_NODES_PER_DOMAIN
  },

  // 检查总节点数限制
  checkTotalNodeLimit: () => {
    const state = get()
    const domainNodeCount = state.domains.reduce((sum, d) => sum + d.nodeIds.length, 0)
    const totalNodes = domainNodeCount + state.aggregationNodes.length
    return totalNodes <= MAX_TOTAL_NODES
  },

  // 检查复合节点嵌套深度
  checkCompoundNesting: (_compoundId) => {
    // TODO: 实现嵌套深度检查
    return true
  },

  // 查找节点
  _findNode: (nodeId) => {
    const state = get()
    return state.aggregationNodes.find((n) => n.id === nodeId) || null
  },

  // 查找域
  _findDomain: (domainId) => {
    const state = get()
    return state.domains.find((d) => d.id === domainId) || null
  },

  // 生成ID
  _generateId: generateId,
}))
