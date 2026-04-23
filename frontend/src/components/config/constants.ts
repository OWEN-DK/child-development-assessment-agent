/**
 * 系统配置页面共享常量与类型定义
 */

// 断点定义
export const BREAKPOINTS = {
  MOBILE: 768,
  TABLET: 1200,
  DESKTOP: 1400
} as const;

export type Breakpoint = 'mobile' | 'tablet' | 'desktop' | 'wide';

export function getBreakpoint(width: number): Breakpoint {
  if (width < BREAKPOINTS.MOBILE) return 'mobile';
  if (width < BREAKPOINTS.TABLET) return 'tablet';
  if (width < BREAKPOINTS.DESKTOP) return 'desktop';
  return 'wide';
}

// 配置分类树（key 必须唯一，且需与后端 category 映射）
export const CATEGORY_TREE = [
  {
    title: '🤖 AI模型配置',
    key: 'models',
    children: [
      { title: 'LLM 提供商', key: 'models.llm' },
      { title: '场景模型', key: 'models.llm.scenes' },
      { title: 'Embedding 模型', key: 'models.embedding' },
      { title: 'ML 评分模型', key: 'models.ml_scoring' }
    ]
  },
  {
    title: '📚 RAG知识库',
    key: 'rag',
    children: [
      { title: '核心设置', key: 'rag.core' },
      { title: '检索策略', key: 'rag.retrieval' },
      { title: '分块设置', key: 'rag.chunking' },
      { title: '向量存储', key: 'rag.vector_store' },
      { title: 'PageIndex', key: 'rag.pageindex' },
      { title: '导入流水线', key: 'rag.pipeline' }
    ]
  },
  {
    title: '⚙️ 业务规则',
    key: 'rules',
    children: [
      { title: '元数据规则', key: 'rules.metadata' }
    ]
  },
  {
    title: '📦 系统设置',
    key: 'system',
    children: [
      { title: '应用设置', key: 'app' },
      { title: '日志配置', key: 'logging' },
      { title: '路径配置', key: 'paths' }
    ]
  },
  {
    title: ' 其他配置',
    key: 'other',
    children: [
      { title: '通用配置', key: 'other.general' }
    ]
  },
  {
    title: '📝 草稿生成',
    key: 'draft',
    children: [
      { title: '草稿生成配置', key: 'rag.testing' }
    ]
  }
];

// 场景名称映射
export const SCENE_NAME_MAP: Record<string, string> = {
  assessment: '发展评估',
  reporting: '报告生成',
  validation: '数据校验',
  query_rewrite: '查询重写',
  metadata_extraction: '元数据提取',
  vl_parsing: '多模态解析',
  query_classification: '查询分类',
  ml_scoring: 'ML 评分',
  content_generation: '内容生成'
};

// 提供商选项
export const PROVIDER_OPTIONS = [
  { label: 'DashScope（阿里云百炼）', value: 'dashscope' },
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Ollama（本地）', value: 'ollama' },
];

// 场景详细说明
export const SCENE_DESCRIPTIONS: Record<string, string> = {
  '报告生成': '用于生成儿童发展评估报告，包含评估结果、发展建议、训练计划等内容。建议使用高质量模型以保证报告的专业性和可读性。',
  '儿童评估': '核心评估节点，根据儿童画像和发展里程碑进行能力评估。需要较强的推理能力，建议使用高性能模型。',
  '结果校验': '对评估结果进行二次校验，确保评估结论的合理性和一致性。可使用中等性能模型以降低成本。',
  '查询重写': 'RAG 检索前对用户查询进行改写和扩展，提升检索准确率。需要理解语义，建议使用中等性能模型。',
  '元数据提取': '从上传的文档中提取标题、年龄段、发展领域等元数据信息。需要较强的文本理解能力。',
  '多模态解析': '解析图片、PDF 等多模态文档内容，提取文本信息。需要使用支持视觉理解的模型。',
  '查询分类': '对用户查询进行分类（如评估类、检索类、闲聊类），路由到不同的处理流程。可使用轻量级模型。',
  'ML 评分': '结合机器学习模型对 RAG 检索结果进行相关性评分。需要较强的判断能力。',
  '内容生成': '生成训练计划、活动建议等内容。需要创造性和专业性，建议使用高质量模型。',
};

// 格式化场景名称
export function formatSceneName(sceneName: string): string {
  const nameMap: Record<string, string> = {
    report_generation: '报告生成',
    assessment: '儿童评估',
    validation: '结果校验',
    query_rewrite: '查询重写',
    metadata_extraction: '元数据提取',
    vl_parsing: '多模态解析',
    query_classification: '查询分类',
    ml_scoring: 'ML 评分',
    content_generation: '内容生成',
  };
  return nameMap[sceneName] || sceneName;
}

// 格式化标签
export function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase());
}

// 推断字段类型
export function inferType(value: any): 'bool' | 'int' | 'float' | 'str' | 'list' | 'dict' | 'select' {
  if (typeof value === 'boolean') return 'bool';
  if (typeof value === 'number') return Number.isInteger(value) ? 'int' : 'float';
  if (typeof value === 'string') return 'str';
  if (Array.isArray(value)) return 'list';
  return 'dict';
}
