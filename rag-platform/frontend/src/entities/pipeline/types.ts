/**
 * 管道编辑器实体类型定义
 *
 * 定义管道、节点、边、域等核心数据结构
 */

// ==================== 节点类型定义 ====================

/** 节点分类 */
export type NodeCategory =
  | 'query_understanding'    // 查询理解
  | 'retrieval_strategy'     // 检索策略
  | 'security_compliance'    // 安全合规
  | 'quality_enhancement'    // 质量增强
  | 'performance_optimization' // 性能优化
  | 'answer_synthesis'       // 答案合成
  | 'aggregation';           // 聚合层

/** 节点类型枚举（28种） */
export type NodeType =
  // 查询理解（7个）
  | 'query_rewrite'
  | 'synonym_expand'
  | 'query_decompose'
  | 'term_normalize'
  | 'intent_classify'
  | 'stopword_filter'
  | 'query_expand'
  // 检索策略（5个）
  | 'bm25_search'
  | 'vector_search'
  | 'hybrid_search'
  | 'multimodal_search'
  | 'result_fusion'
  // 安全合规（3个）
  | 'sensitive_filter'
  | 'pii_mask'
  | 'content_audit'
  // 质量增强（4个）
  | 'rerank'
  | 'dedup'
  | 'hallucination_check'
  | 'citation_verify'
  // 性能优化（2个）
  | 'semantic_cache'
  | 'rate_limiter'
  // 答案合成（1个）
  | 'structured_output'
  // 聚合层（6个）
  | 'query_analyzer'
  | 'domain_dispatch'
  | 'cross_fusion'
  | 'cross_dedup'
  | 'conflict_detect'
  | 'unified_generate'
  // 复合节点
  | 'compound';

/** 节点配置 */
export interface NodeConfig {
  [key: string]: unknown;
}

/** 节点定义 */
export interface PipelineNode {
  id: string;
  type: NodeType;
  label: string;
  category: NodeCategory;
  config: NodeConfig;
  position: { x: number; y: number };
  domainId?: string;  // 所属域ID（聚合节点无此字段）
  degradation?: DegradationConfig;
}

/** 降级配置 */
export interface DegradationConfig {
  strategy: 'skip' | 'use_cache' | 'fallback_node' | 'abort';
  fallbackNodeId?: string;
  timeoutMs?: number;
  maxRetries?: number;
  errorTypes?: string[];
}

// ==================== 边类型定义 ====================

/** 边类型 */
export type EdgeType = 'dataFlow' | 'conditional' | 'degradation';

/** 边配置 */
export interface EdgeConfig {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  sourceHandle?: string;
  targetHandle?: string;
  // 条件边属性
  condition?: ConditionConfig;
  // 降级边属性
  degradation?: DegradationConfig;
}

/** 条件配置 */
export interface ConditionConfig {
  field: string;
  operator: '>' | '<' | '==' | '>=' | '<=' | '!=' | 'contains' | 'in';
  value: string | number;
  logic?: 'AND' | 'OR';
  conditions?: ConditionConfig[];
}

// ==================== 域定义 ====================

/** 域配置 */
export interface DomainConfig {
  id: string;
  name: string;
  knowledgeBaseId?: string;
  weight: number;
  keywords: string[];
  collapsed: boolean;
  nodeIds: string[];
}

// ==================== 管道定义 ====================

/** 管道配置快照 */
export interface PipelineConfig {
  domains: DomainConfig[];
  aggregationNodes: PipelineNode[];
  edges: EdgeConfig[];
}

/** 管道列表项 */
export interface PipelineListItem {
  id: string;
  name: string;
  version: number;
  domainCount: number;
  nodeCount: number;
  lastEvalScore?: number;
  publishedEndpoints: number;
  status: 'draft' | 'published' | 'archived';
  createdAt: string;
  updatedAt: string;
}

/** 管道详情 */
export interface PipelineDetail {
  id: string;
  name: string;
  version: number;
  configSnapshot: PipelineConfig;
  createdAt: string;
  updatedAt: string;
  versions?: PipelineVersion[];
}

/** 管道版本 */
export interface PipelineVersion {
  version: number;
  changeLog?: string;
  createdAt: string;
  createdBy?: string;
}

/** 管道保存请求 */
export interface PipelineSaveRequest {
  configSnapshot: PipelineConfig;
  changeLog?: string;
  version: number;
}

/** 管道创建请求 */
export interface PipelineCreate {
  name: string;
  configSnapshot?: PipelineConfig;
}

/** 管道更新请求 */
export interface PipelineUpdate {
  name?: string;
}

/** 管道导入请求 */
export interface PipelineImport {
  name: string;
  configJson: string;
}

// ==================== 复合节点定义 ====================

/** 复合节点配置 */
export interface CompoundNodeConfig {
  id: string;
  name: string;
  description?: string;
  nodes: PipelineNode[];
  edges: EdgeConfig[];
  inputHandles: string[];
  outputHandles: string[];
}

/** 复合节点库项 */
export interface CompoundNodeRead {
  id: string;
  name: string;
  description?: string;
  nodeCount: number;
  createdAt: string;
}

// ==================== 校验与干运行 ====================

/** 校验错误 */
export interface ValidationError {
  nodeId?: string;
  field?: string;
  message: string;
  severity: 'error' | 'warning';
}

/** 校验结果 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

/** 节点执行步骤 */
export interface NodeExecutionStep {
  nodeId: string;
  nodeType: NodeType;
  domainId?: string;
  estimatedMs: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

/** 干运行结果 */
export interface DryRunResult {
  success: boolean;
  executionPlan: NodeExecutionStep[];
  errors: ValidationError[];
  totalEstimatedMs?: number;
}

// ==================== 版本对比 ====================

/** 版本对比结果 */
export interface VersionCompareResult {
  v1: number;
  v2: number;
  addedNodes: PipelineNode[];
  removedNodes: PipelineNode[];
  modifiedNodes: Array<{
    nodeId: string;
    nodeType: NodeType;
    changes: Array<{
      field: string;
      oldValue: unknown;
      newValue: unknown;
    }>;
  }>;
  addedEdges: EdgeConfig[];
  removedEdges: EdgeConfig[];
}

// ==================== 快照（撤销/重做） ====================

/** 管道快照 */
export interface PipelineSnapshot {
  domains: DomainConfig[];
  aggregationNodes: PipelineNode[];
  edges: EdgeConfig[];
  timestamp: number;
}

// ==================== 节点元数据 ====================

/** 节点类型元数据 */
export interface NodeTypeMetadata {
  type: NodeType;
  label: string;
  category: NodeCategory;
  description: string;
  icon: string;
  color: string;
  isIntraDomain: boolean;
  defaultConfig: NodeConfig;
}

/** 节点分类元数据 */
export interface NodeCategoryMetadata {
  category: NodeCategory;
  label: string;
  description: string;
  nodes: NodeType[];
}
