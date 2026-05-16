/**
 * 节点面板
 *
 * 左侧面板，展示 28 种节点按分类折叠，支持拖拽放置到画布
 */
import { useState } from 'react'
import { Collapse, Input, Typography, Space, Tooltip } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { NodeType, NodeCategory } from '@/entities/pipeline/types'

const { Text } = Typography
const { Panel } = Collapse

/** 节点元数据 */
interface NodeMeta {
  type: NodeType
  label: string
  description: string
  category: NodeCategory
  icon: string
  color: string
}

/** 节点分类配置 */
interface CategoryConfig {
  key: NodeCategory
  label: string
  description: string
  nodes: NodeMeta[]
}

/** 节点分类定义 */
const NODE_CATEGORIES: CategoryConfig[] = [
  {
    key: 'query_understanding',
    label: '查询理解',
    description: '处理和优化用户查询',
    nodes: [
      { type: 'query_rewrite', label: '查询改写', description: '使用 LLM 改写查询以提高检索效果', category: 'query_understanding', icon: '✏️', color: '#1890ff' },
      { type: 'synonym_expand', label: '同义词扩展', description: '扩展查询中的同义词', category: 'query_understanding', icon: '🔗', color: '#1890ff' },
      { type: 'query_decompose', label: '查询分解', description: '将复杂查询分解为多个子查询', category: 'query_understanding', icon: '✂️', color: '#1890ff' },
      { type: 'term_normalize', label: '术语标准化', description: '标准化专业术语', category: 'query_understanding', icon: '📝', color: '#1890ff' },
      { type: 'intent_classify', label: '意图分类', description: '识别查询意图并路由', category: 'query_understanding', icon: '🎯', color: '#1890ff' },
      { type: 'stopword_filter', label: '禁用词过滤', description: '过滤禁用词', category: 'query_understanding', icon: '🚫', color: '#1890ff' },
      { type: 'query_expand', label: '查询扩展', description: '生成扩展查询', category: 'query_understanding', icon: '🔄', color: '#1890ff' },
    ],
  },
  {
    key: 'retrieval_strategy',
    label: '检索策略',
    description: '从知识库检索相关文档',
    nodes: [
      { type: 'bm25_search', label: 'BM25 检索', description: '基于关键词的 BM25 检索', category: 'retrieval_strategy', icon: '🔍', color: '#52c41a' },
      { type: 'vector_search', label: '向量检索', description: '基于语义的向量检索', category: 'retrieval_strategy', icon: '🧠', color: '#52c41a' },
      { type: 'hybrid_search', label: '混合检索', description: 'BM25 + 向量混合检索', category: 'retrieval_strategy', icon: '⚡', color: '#52c41a' },
      { type: 'multimodal_search', label: '多模态检索', description: '支持文本/图片/表格多模态', category: 'retrieval_strategy', icon: '🖼️', color: '#52c41a' },
      { type: 'result_fusion', label: '结果融合', description: '融合多路检索结果', category: 'retrieval_strategy', icon: '🔀', color: '#52c41a' },
    ],
  },
  {
    key: 'security_compliance',
    label: '安全合规',
    description: '安全过滤和合规检查',
    nodes: [
      { type: 'sensitive_filter', label: '敏感词过滤', description: '过滤敏感词汇', category: 'security_compliance', icon: '🛡️', color: '#ff4d4f' },
      { type: 'pii_mask', label: 'PII 脱敏', description: '个人信息脱敏处理', category: 'security_compliance', icon: '🔒', color: '#ff4d4f' },
      { type: 'content_audit', label: '内容审核', description: '内容合规性审核', category: 'security_compliance', icon: '👁️', color: '#ff4d4f' },
    ],
  },
  {
    key: 'quality_enhancement',
    label: '质量增强',
    description: '提升检索和生成质量',
    nodes: [
      { type: 'rerank', label: '重排序', description: '对检索结果重排序', category: 'quality_enhancement', icon: '📊', color: '#722ed1' },
      { type: 'dedup', label: '去重', description: '去除重复文档', category: 'quality_enhancement', icon: '🗑️', color: '#722ed1' },
      { type: 'hallucination_check', label: '幻觉检测', description: '检测生成内容的幻觉', category: 'quality_enhancement', icon: '🔍', color: '#722ed1' },
      { type: 'citation_verify', label: '引用验证', description: '验证引用的准确性', category: 'quality_enhancement', icon: '✅', color: '#722ed1' },
    ],
  },
  {
    key: 'performance_optimization',
    label: '性能优化',
    description: '优化系统性能',
    nodes: [
      { type: 'semantic_cache', label: '语义缓存', description: '语义相似度缓存', category: 'performance_optimization', icon: '💾', color: '#fa8c16' },
      { type: 'rate_limiter', label: '速率限制', description: '请求速率限制', category: 'performance_optimization', icon: '⏱️', color: '#fa8c16' },
    ],
  },
  {
    key: 'answer_synthesis',
    label: '答案合成',
    description: '生成最终答案',
    nodes: [
      { type: 'structured_output', label: '结构化输出', description: '格式化输出为 JSON/表格', category: 'answer_synthesis', icon: '📋', color: '#faad14' },
    ],
  },
]

/** 聚合节点定义 */
const AGGREGATION_NODES: NodeMeta[] = [
  { type: 'query_analyzer', label: '查询分析', description: '分析查询涉及的领域', category: 'aggregation', icon: '🔎', color: '#13c2c2' },
  { type: 'domain_dispatch', label: '域分发', description: '将查询分发到各域管道', category: 'aggregation', icon: '📤', color: '#13c2c2' },
  { type: 'cross_fusion', label: '跨域融合', description: '融合多域检索结果', category: 'aggregation', icon: '🔀', color: '#13c2c2' },
  { type: 'cross_dedup', label: '跨域去重', description: '去除跨域重复文档', category: 'aggregation', icon: '🗑️', color: '#13c2c2' },
  { type: 'conflict_detect', label: '冲突检测', description: '检测跨域矛盾信息', category: 'aggregation', icon: '⚠️', color: '#13c2c2' },
  { type: 'unified_generate', label: '统一生成', description: '综合多域生成最终答案', category: 'aggregation', icon: '✨', color: '#13c2c2' },
]

export default function NodePanel() {
  const [searchQuery, setSearchQuery] = useState('')
  const [collapsed, setCollapsed] = useState(false)

  // 过滤节点
  const filterNodes = (nodes: NodeMeta[]) => {
    if (!searchQuery) return nodes
    return nodes.filter(
      (node) =>
        node.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        node.description.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }

  // 拖拽开始
  const onDragStart = (event: React.DragEvent, nodeType: NodeType, category: string) => {
    event.dataTransfer.setData(
      'application/json',
      JSON.stringify({ nodeType, category })
    )
    event.dataTransfer.effectAllowed = 'move'
  }

  if (collapsed) {
    return (
      <div
        style={{
          width: 40,
          background: '#fafafa',
          borderRight: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
        }}
        onClick={() => setCollapsed(false)}
      >
        <span style={{ writingMode: 'vertical-rl' }}>节点面板</span>
      </div>
    )
  }

  return (
    <div
      style={{
        width: 240,
        background: '#fafafa',
        borderRight: '1px solid #f0f0f0',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* 头部 */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Text strong>节点面板</Text>
        <span
          style={{ cursor: 'pointer', color: '#999' }}
          onClick={() => setCollapsed(true)}
        >
          ◀
        </span>
      </div>

      {/* 搜索框 */}
      <div style={{ padding: '12px 16px' }}>
        <Input
          placeholder="搜索节点"
          prefix={<SearchOutlined />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          allowClear
        />
      </div>

      {/* 节点列表 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 16px 16px' }}>
        <Collapse
          defaultActiveKey={NODE_CATEGORIES.map((c) => c.key)}
          ghost
          size="small"
        >
          {/* 域内节点 */}
          {NODE_CATEGORIES.map((category) => {
            const filteredNodes = filterNodes(category.nodes)
            if (filteredNodes.length === 0) return null

            return (
              <Panel
                header={
                  <Space>
                    <Text strong>{category.label}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      ({filteredNodes.length})
                    </Text>
                  </Space>
                }
                key={category.key}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {filteredNodes.map((node) => (
                    <Tooltip key={node.type} title={node.description} placement="right">
                      <div
                        draggable
                        onDragStart={(e) => onDragStart(e, node.type, 'intra_domain')}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '8px 12px',
                          background: '#fff',
                          borderRadius: 4,
                          border: '1px solid #d9d9d9',
                          cursor: 'grab',
                          transition: 'all 0.2s',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = node.color
                          e.currentTarget.style.boxShadow = `0 0 0 2px ${node.color}20`
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = '#d9d9d9'
                          e.currentTarget.style.boxShadow = 'none'
                        }}
                      >
                        <span>{node.icon}</span>
                        <div>
                          <div style={{ fontSize: 13 }}>{node.label}</div>
                          <div style={{ fontSize: 11, color: '#999' }}>{node.description}</div>
                        </div>
                      </div>
                    </Tooltip>
                  ))}
                </div>
              </Panel>
            )
          })}

          {/* 聚合节点 */}
          <Panel
            header={
              <Space>
                <Text strong>聚合节点</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  ({filterNodes(AGGREGATION_NODES).length})
                </Text>
              </Space>
            }
            key="aggregation"
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {filterNodes(AGGREGATION_NODES).map((node) => (
                <Tooltip key={node.type} title={node.description} placement="right">
                  <div
                    draggable
                    onDragStart={(e) => onDragStart(e, node.type, 'aggregation')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 12px',
                      background: '#fff',
                      borderRadius: 4,
                      border: '1px solid #d9d9d9',
                      cursor: 'grab',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = node.color
                      e.currentTarget.style.boxShadow = `0 0 0 2px ${node.color}20`
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = '#d9d9d9'
                      e.currentTarget.style.boxShadow = 'none'
                    }}
                  >
                    <span>{node.icon}</span>
                    <div>
                      <div style={{ fontSize: 13 }}>{node.label}</div>
                      <div style={{ fontSize: 11, color: '#999' }}>{node.description}</div>
                    </div>
                  </div>
                </Tooltip>
              ))}
            </div>
          </Panel>

          {/* 复合节点 */}
          <Panel
            header={
              <Space>
                <Text strong>我的复合节点</Text>
              </Space>
            }
            key="compound"
          >
            <div style={{ textAlign: 'center', color: '#999', padding: '20px 0' }}>
              暂无复合节点
            </div>
          </Panel>
        </Collapse>
      </div>
    </div>
  )
}
