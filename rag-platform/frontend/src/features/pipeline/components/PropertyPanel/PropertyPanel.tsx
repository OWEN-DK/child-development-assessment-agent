/**
 * 属性面板
 *
 * 右侧面板，根据选中节点类型动态渲染参数表单
 */
import { useMemo } from 'react'
import { Typography, Empty, Collapse, Form, Input, Select, Slider, Switch, InputNumber, Space, Tooltip } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { usePipelineWorkbenchStore } from '../../stores/pipelineWorkbenchStore'
import type { NodeType } from '@/entities/pipeline/types'

const { Text, Title } = Typography
const { Panel } = Collapse
const { Option } = Select

/** 节点参数表单配置 */
interface NodeParamConfig {
  key: string
  label: string
  type: 'input' | 'number' | 'select' | 'slider' | 'switch' | 'textarea' | 'tags'
  description?: string
  defaultValue?: unknown
  options?: Array<{ label: string; value: unknown }>
  min?: number
  max?: number
  step?: number
}

/** 节点参数定义映射 */
const NODE_PARAMS: Record<NodeType, NodeParamConfig[]> = {
  // 查询理解
  query_rewrite: [
    { key: 'model', label: 'LLM 模型', type: 'select', description: '用于改写的 LLM 模型', options: [] },
    { key: 'prompt_template', label: '提示词模板', type: 'select', description: '改写提示词模板' },
    { key: 'max_retries', label: '最大重试次数', type: 'number', min: 0, max: 5, defaultValue: 2 },
  ],
  synonym_expand: [
    { key: 'synonym_source', label: '同义词来源', type: 'select', options: [
      { label: '内置通用词库', value: 'builtin' },
      { label: '域专用词库', value: 'domain' },
      { label: '自定义上传', value: 'custom' },
    ]},
    { key: 'max_synonyms', label: '最大扩展数', type: 'number', min: 1, max: 10, defaultValue: 3 },
    { key: 'expansion_mode', label: '扩展模式', type: 'select', options: [
      { label: '全量扩展', value: 'all' },
      { label: '仅名词扩展', value: 'noun' },
      { label: '仅关键术语', value: 'keyword' },
    ]},
  ],
  query_decompose: [
    { key: 'model', label: 'LLM 模型', type: 'select' },
    { key: 'max_subqueries', label: '最大子查询数', type: 'number', min: 1, max: 10, defaultValue: 3 },
    { key: 'decomposition_strategy', label: '分解策略', type: 'select', options: [
      { label: '按并列关系', value: 'parallel' },
      { label: '按层级关系', value: 'hierarchical' },
      { label: '自动判断', value: 'auto' },
    ]},
  ],
  term_normalize: [
    { key: 'terminology_source', label: '术语来源', type: 'select', options: [
      { label: '域内置', value: 'builtin' },
      { label: '自定义上传', value: 'custom' },
    ]},
    { key: 'normalize_mode', label: '标准化模式', type: 'select', options: [
      { label: '精确匹配', value: 'exact' },
      { label: 'LLM 动态标准化', value: 'llm' },
      { label: '两者', value: 'both' },
    ]},
    { key: 'model', label: 'LLM 模型', type: 'select' },
  ],
  intent_classify: [
    { key: 'model', label: 'LLM 模型', type: 'select' },
    { key: 'categories', label: '分类体系', type: 'textarea', description: 'JSON 格式分类定义' },
    { key: 'routing_rules', label: '路由规则', type: 'textarea', description: 'JSON 格式路由规则' },
  ],
  stopword_filter: [
    { key: 'stop_words', label: '禁用词列表', type: 'tags', description: '支持在线编辑/导入/正则' },
    { key: 'enabled', label: '启用', type: 'switch', defaultValue: true },
    { key: 'case_sensitive', label: '区分大小写', type: 'switch', defaultValue: false },
  ],
  query_expand: [
    { key: 'model', label: 'LLM 模型', type: 'select' },
    { key: 'expansion_count', label: '扩展查询数', type: 'number', min: 1, max: 5, defaultValue: 2 },
    { key: 'expansion_method', label: '扩展方法', type: 'select', options: [
      { label: '改写', value: 'rewrite' },
      { label: '加限定条件', value: 'constrain' },
      { label: '换角度提问', value: 'perspective' },
    ]},
  ],

  // 检索策略
  bm25_search: [
    { key: 'top_k', label: '返回数量', type: 'number', min: 1, max: 100, defaultValue: 10 },
    { key: 'k1', label: 'k1 参数', type: 'number', min: 0, max: 3, step: 0.1, defaultValue: 1.5, description: '词频饱和度' },
    { key: 'b', label: 'b 参数', type: 'number', min: 0, max: 1, step: 0.01, defaultValue: 0.75, description: '文档长度归一化' },
    { key: 'score_threshold', label: '分数阈值', type: 'number', min: 0, max: 1, step: 0.01, defaultValue: 0 },
  ],
  vector_search: [
    { key: 'embedding_model', label: 'Embedding 模型', type: 'select' },
    { key: 'top_k', label: '返回数量', type: 'number', min: 1, max: 100, defaultValue: 10 },
    { key: 'similarity_threshold', label: '相似度阈值', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.7 },
    { key: 'similarity_metric', label: '相似度度量', type: 'select', options: [
      { label: 'Cosine', value: 'cosine' },
      { label: 'Euclidean', value: 'euclidean' },
      { label: 'Dot Product', value: 'dot_product' },
    ]},
  ],
  hybrid_search: [
    { key: 'vector_weight', label: '向量权重', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.5 },
    { key: 'keyword_weight', label: '关键词权重', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.5 },
    { key: 'top_k', label: '返回数量', type: 'number', min: 1, max: 100, defaultValue: 10 },
    { key: 'fusion_method', label: '融合方法', type: 'select', options: [
      { label: 'RRF', value: 'rrf' },
      { label: '加权求和', value: 'weighted_sum' },
      { label: '线性组合', value: 'linear' },
    ]},
    { key: 'rrf_k', label: 'RRF K 常数', type: 'number', min: 1, max: 100, defaultValue: 60 },
  ],
  multimodal_search: [
    { key: 'text_weight', label: '文本权重', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.5 },
    { key: 'image_weight', label: '图片权重', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.3 },
    { key: 'table_weight', label: '表格权重', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.2 },
    { key: 'top_k', label: '返回数量', type: 'number', min: 1, max: 100, defaultValue: 10 },
  ],
  result_fusion: [
    { key: 'fusion_method', label: '融合方法', type: 'select', options: [
      { label: 'RRF', value: 'rrf' },
      { label: '加权求和', value: 'weighted_sum' },
      { label: '线性组合', value: 'linear' },
    ]},
    { key: 'final_top_k', label: '最终返回数', type: 'number', min: 1, max: 100, defaultValue: 10 },
  ],

  // 安全合规
  sensitive_filter: [
    { key: 'word_list', label: '敏感词列表', type: 'tags' },
    { key: 'filter_mode', label: '过滤模式', type: 'select', options: [
      { label: '删除文档', value: 'delete' },
      { label: '脱敏替换', value: 'mask' },
      { label: '仅标记', value: 'mark' },
    ]},
    { key: 'apply_to', label: '应用范围', type: 'select', options: [
      { label: '过滤查询', value: 'query' },
      { label: '过滤结果', value: 'result' },
      { label: '两者', value: 'both' },
    ]},
  ],
  pii_mask: [
    { key: 'target_types', label: '脱敏目标', type: 'select', options: [
      { label: '手机号', value: 'phone' },
      { label: '身份证', value: 'id_card' },
      { label: '姓名', value: 'name' },
      { label: '邮箱', value: 'email' },
      { label: '地址', value: 'address' },
      { label: '银行卡号', value: 'bank_card' },
    ]},
    { key: 'mask_char', label: '替换字符', type: 'input', defaultValue: '*' },
    { key: 'preserve_pattern', label: '保留格式', type: 'input', description: '正则表达式' },
  ],
  content_audit: [
    { key: 'model', label: '审核模型', type: 'select' },
    { key: 'audit_rules', label: '审核规则', type: 'select', options: [
      { label: '色情', value: 'porn' },
      { label: '暴力', value: 'violence' },
      { label: '政治', value: 'politics' },
      { label: '违法', value: 'illegal' },
      { label: '歧视', value: 'discrimination' },
      { label: '广告', value: 'advertising' },
    ]},
    { key: 'action', label: '命中行为', type: 'select', options: [
      { label: '过滤文档', value: 'filter' },
      { label: '标记警告', value: 'warn' },
      { label: '拒绝查询', value: 'reject' },
    ]},
    { key: 'threshold', label: '敏感度', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.8 },
  ],

  // 质量增强
  rerank: [
    { key: 'model', label: '重排序模型', type: 'select' },
    { key: 'initial_k', label: '输入候选数', type: 'number', min: 1, max: 200, defaultValue: 50 },
    { key: 'final_k', label: '输出保留数', type: 'number', min: 1, max: 100, defaultValue: 10 },
  ],
  dedup: [
    { key: 'method', label: '去重方法', type: 'select', options: [
      { label: 'MinHash', value: 'minhash' },
      { label: 'Embedding', value: 'embedding' },
    ]},
    { key: 'threshold', label: '相似度阈值', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.85 },
    { key: 'scope', label: '去重范围', type: 'select', options: [
      { label: '域内去重', value: 'domain' },
      { label: '跨文档去重', value: 'cross_doc' },
      { label: '两者', value: 'both' },
    ]},
  ],
  hallucination_check: [
    { key: 'model', label: '检测模型', type: 'select' },
    { key: 'threshold', label: '检测阈值', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.8 },
    { key: 'action', label: '检测后行为', type: 'select', options: [
      { label: '过滤', value: 'filter' },
      { label: '标记', value: 'mark' },
      { label: '两者', value: 'both' },
    ]},
  ],
  citation_verify: [
    { key: 'mode', label: '验证模式', type: 'select', options: [
      { label: '严格验证', value: 'strict' },
      { label: '宽松验证', value: 'lax' },
    ]},
    { key: 'model', label: '验证模型', type: 'select' },
  ],

  // 性能优化
  semantic_cache: [
    { key: 'cache_backend', label: '缓存后端', type: 'select', options: [
      { label: 'Redis', value: 'redis' },
      { label: '内存', value: 'memory' },
    ]},
    { key: 'similarity_threshold', label: '命中阈值', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.95 },
    { key: 'ttl', label: '过期时间(秒)', type: 'number', min: 60, max: 86400, defaultValue: 3600 },
    { key: 'max_cache_size', label: '最大缓存数', type: 'number', min: 100, max: 100000, defaultValue: 10000 },
  ],
  rate_limiter: [
    { key: 'max_qps', label: '最大 QPS', type: 'number', min: 1, max: 10000, defaultValue: 100 },
    { key: 'algorithm', label: '限流算法', type: 'select', options: [
      { label: '滑动窗口', value: 'sliding_window' },
      { label: '令牌桶', value: 'token_bucket' },
      { label: '漏桶', value: 'leaky_bucket' },
    ]},
    { key: 'scope', label: '限流范围', type: 'select', options: [
      { label: '按域', value: 'domain' },
      { label: '按管道', value: 'pipeline' },
      { label: '按用户', value: 'user' },
    ]},
  ],

  // 答案合成
  structured_output: [
    { key: 'output_format', label: '输出格式', type: 'select', options: [
      { label: 'JSON', value: 'json' },
      { label: '表格', value: 'table' },
      { label: 'Markdown', value: 'markdown' },
      { label: '自定义 Schema', value: 'custom' },
    ]},
    { key: 'schema_definition', label: 'Schema 定义', type: 'textarea', description: 'JSON Schema 格式' },
    { key: 'model', label: 'LLM 模型', type: 'select' },
    { key: 'strict_mode', label: '严格模式', type: 'switch', defaultValue: true },
  ],

  // 聚合层
  query_analyzer: [
    { key: 'model', label: 'LLM 模型', type: 'select' },
    { key: 'max_domains', label: '最大激活域数', type: 'number', min: 1, max: 20, defaultValue: 5 },
    { key: 'min_confidence', label: '域激活阈值', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.5 },
    { key: 'domain_keywords', label: '域触发关键词', type: 'textarea', description: 'JSON 格式' },
  ],
  domain_dispatch: [
    { key: 'parallel', label: '并行执行', type: 'switch', defaultValue: true },
    { key: 'timeout_ms', label: '单域超时(ms)', type: 'number', min: 1000, max: 60000, defaultValue: 30000 },
    { key: 'max_concurrency', label: '最大并发数', type: 'number', min: 1, max: 20, defaultValue: 5 },
  ],
  cross_fusion: [
    { key: 'fusion_method', label: '融合方法', type: 'select', options: [
      { label: '加权 RRF', value: 'weighted_rrf' },
      { label: '加权求和', value: 'weighted_sum' },
      { label: '优先级排序', value: 'priority' },
    ]},
    { key: 'rrf_k', label: 'RRF K 常数', type: 'number', min: 1, max: 100, defaultValue: 60 },
    { key: 'final_top_k', label: '最终返回数', type: 'number', min: 1, max: 100, defaultValue: 10 },
  ],
  cross_dedup: [
    { key: 'dedup_threshold', label: '去重阈值', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.85 },
    { key: 'dedup_method', label: '去重方法', type: 'select', options: [
      { label: 'MinHash', value: 'minhash' },
      { label: 'Embedding', value: 'embedding' },
    ]},
  ],
  conflict_detect: [
    { key: 'model', label: 'LLM 模型', type: 'select' },
    { key: 'enabled', label: '启用', type: 'switch', defaultValue: true },
    { key: 'conflict_threshold', label: '检测敏感度', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.7 },
  ],
  unified_generate: [
    { key: 'model', label: 'LLM 模型', type: 'select' },
    { key: 'temperature', label: '温度', type: 'slider', min: 0, max: 1, step: 0.01, defaultValue: 0.3 },
    { key: 'max_tokens', label: '最大 Token 数', type: 'number', min: 100, max: 8000, defaultValue: 2000 },
    { key: 'include_citations', label: '包含引用', type: 'switch', defaultValue: true },
    { key: 'citation_format', label: '引用格式', type: 'select', options: [
      { label: '编号', value: 'number' },
      { label: '脚注', value: 'footnote' },
      { label: '行内', value: 'inline' },
    ]},
  ],

  // 复合节点
  compound: [],
}

export default function PropertyPanel() {
  const { selectedNodeId, aggregationNodes, updateNodeConfig } = usePipelineWorkbenchStore()

  // 查找选中的节点
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null
    return aggregationNodes.find((n) => n.id === selectedNodeId) || null
  }, [selectedNodeId, aggregationNodes])

  // 获取节点参数配置
  const nodeParams = useMemo(() => {
    if (!selectedNode) return []
    return NODE_PARAMS[selectedNode.type] || []
  }, [selectedNode])

  // 处理参数变更
  const handleParamChange = (key: string, value: unknown) => {
    if (!selectedNodeId) return
    updateNodeConfig(selectedNodeId, { [key]: value })
  }

  // 渲染参数控件
  const renderParamControl = (param: NodeParamConfig) => {
    const currentValue = selectedNode?.config?.[param.key] ?? param.defaultValue

    switch (param.type) {
      case 'input':
        return (
          <Input
            value={currentValue as string}
            onChange={(e) => handleParamChange(param.key, e.target.value)}
          />
        )

      case 'number':
        return (
          <InputNumber
            value={currentValue as number}
            min={param.min}
            max={param.max}
            step={param.step}
            onChange={(value) => handleParamChange(param.key, value)}
            style={{ width: '100%' }}
          />
        )

      case 'select':
        return (
          <Select
            value={currentValue}
            onChange={(value) => handleParamChange(param.key, value)}
            style={{ width: '100%' }}
          >
            {(param.options || []).map((opt) => (
              <Option key={String(opt.value)} value={opt.value}>
                {opt.label}
              </Option>
            ))}
          </Select>
        )

      case 'slider':
        return (
          <Slider
            value={currentValue as number}
            min={param.min}
            max={param.max}
            step={param.step}
            onChange={(value) => handleParamChange(param.key, value)}
          />
        )

      case 'switch':
        return (
          <Switch
            checked={currentValue as boolean}
            onChange={(checked) => handleParamChange(param.key, checked)}
          />
        )

      case 'textarea':
        return (
          <Input.TextArea
            value={currentValue as string}
            onChange={(e) => handleParamChange(param.key, e.target.value)}
            rows={4}
          />
        )

      case 'tags':
        return (
          <Select
            mode="tags"
            value={currentValue as string[]}
            onChange={(value) => handleParamChange(param.key, value)}
            style={{ width: '100%' }}
            placeholder="输入后按回车添加"
          />
        )

      default:
        return null
    }
  }

  // 无选中节点
  if (!selectedNode) {
    return (
      <div
        style={{
          width: 320,
          background: '#fafafa',
          borderLeft: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Empty
          description="选择节点查看属性"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    )
  }

  return (
    <div
      style={{
        width: 320,
        background: '#fafafa',
        borderLeft: '1px solid #f0f0f0',
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
        }}
      >
        <Title level={5} style={{ margin: 0 }}>
          {selectedNode.label}
        </Title>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {selectedNode.type}
        </Text>
      </div>

      {/* 参数表单 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        <Collapse defaultActiveKey={['params', 'degradation']} ghost>
          {/* 参数配置 */}
          <Panel header="参数配置" key="params">
            <Form layout="vertical" size="small">
              {nodeParams.map((param) => (
                <Form.Item
                  key={param.key}
                  label={
                    <Space>
                      <span>{param.label}</span>
                      {param.description && (
                        <Tooltip title={param.description}>
                          <QuestionCircleOutlined style={{ color: '#999' }} />
                        </Tooltip>
                      )}
                    </Space>
                  }
                >
                  {renderParamControl(param)}
                </Form.Item>
              ))}
            </Form>
          </Panel>

          {/* 降级路径配置 */}
          <Panel header="降级路径" key="degradation">
            <div style={{ textAlign: 'center', color: '#999', padding: '20px 0' }}>
              降级路径配置开发中
            </div>
          </Panel>
        </Collapse>
      </div>
    </div>
  )
}
