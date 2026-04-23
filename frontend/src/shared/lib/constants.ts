// API 相关
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
export const API_TIMEOUT = 30000;

// 分页相关
export const DEFAULT_PAGE_SIZE = 20;
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

// 文件上传相关
export const MAX_FILE_SIZE_MB = 100;
export const ALLOWED_FILE_TYPES = ['application/pdf', 'application/epub+zip'];
export const ALLOWED_FILE_EXTENSIONS = ['.pdf', '.epub'];

// 任务状态相关
export const TASK_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export const TASK_STAGES = {
  PENDING: 'pending',
  PARSING: 'parsing',
  CHUNKING: 'chunking',
  EMBEDDING: 'embedding',
  INDEXING: 'indexing',
  COMPLETED: 'completed',
} as const;

// 评估相关
export const GENDER_OPTIONS = [
  { label: '男', value: 'male' },
  { label: '女', value: 'female' },
  { label: '其他', value: 'other' },
] as const;

export const INTENSITY_OPTIONS = [
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
] as const;

// 年龄范围
export const MIN_AGE = 0;
export const MAX_AGE = 18;

// React Query 相关
export const QUERY_KEYS = {
  documents: {
    all: ['documents'] as const,
    list: () => [...QUERY_KEYS.documents.all, 'list'] as const,
    detail: (hash: string) => [...QUERY_KEYS.documents.all, 'detail', hash] as const,
    chunks: (hash: string) => [...QUERY_KEYS.documents.all, 'chunks', hash] as const,
  },
  assessment: {
    all: ['assessment'] as const,
  },
  knowledge: {
    all: ['knowledge'] as const,
    search: (query: string) => [...QUERY_KEYS.knowledge.all, 'search', query] as const,
  },
  ragTest: {
    all: ['ragTest'] as const,
    cases: () => [...QUERY_KEYS.ragTest.all, 'cases'] as const,
    runs: () => [...QUERY_KEYS.ragTest.all, 'runs'] as const,
    snapshots: () => [...QUERY_KEYS.ragTest.all, 'snapshots'] as const,
  },
} as const;

// 缓存时间配置
export const CACHE_TIME = {
  SHORT: 1 * 60 * 1000,
  MEDIUM: 5 * 60 * 1000,
  LONG: 30 * 60 * 1000,
  NEVER: Infinity,
} as const;

// 轮询间隔
export const POLLING_INTERVAL = 2000;

// 防抖延迟
export const DEBOUNCE_DELAY = 500;
