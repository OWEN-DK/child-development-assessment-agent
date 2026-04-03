# 前端代码系统性改造实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对前端代码进行系统性重构，解决代码逻辑混乱、功能混合问题，建立高可维护性、可扩展性和可测试性的代码架构。

**Architecture:** 采用 Feature-based 目录结构 + 领域驱动设计(DDD)思想，将代码按业务领域拆分；引入 React Query 管理服务端状态，Zustand 管理客户端状态；建立统一的组件库、工具函数库和类型定义体系。

**Tech Stack:** React 19, TypeScript, Ant Design 6, ProComponents, React Router 7, TanStack Query 5, Zustand 5, Axios, Vite 5

---

## 当前代码问题分析

### 1. 代码结构问题
- **目录扁平化**：所有组件、页面、hooks 都放在顶层目录，没有按业务领域分组
- **职责不清**：`api/client.ts` 包含 395 行代码，混合了评估、文档管理、RAG测试、知识搜索等 6+ 个不同领域的 API
- **页面组件臃肿**：`RagTestPage.tsx` (665行)、`KnowledgeBasePage.tsx` (356行) 包含过多业务逻辑

### 2. 功能混合问题
- **API 层混乱**：所有 API 调用混在单一文件中，没有按领域拆分
- **状态管理分散**：`useAssessment` hook 同时管理流式/非流式请求、报告数据、错误状态
- **组件职责过重**：页面组件同时负责数据获取、状态管理、UI 渲染、事件处理

### 3. 代码规范问题
- **缺少统一错误处理**：各页面错误处理逻辑不一致
- **类型定义不完整**：部分 API 返回使用 `any` 类型
- **缺少常量管理**：魔法数字和字符串散落在代码中
- **样式管理混乱**：部分使用 CSS-in-JS，部分使用 SCSS modules

### 4. 性能问题
- **缺少请求缓存策略**：未充分利用 React Query 的缓存能力
- **组件未优化重渲染**：缺少 `React.memo`、`useMemo`、`useCallback` 优化
- **大列表无虚拟滚动**：文档列表、分块列表未使用虚拟滚动

---

## 目标架构设计

### 目录结构重组

```
frontend/src/
├── api/                          # API 层（按领域拆分）
│   ├── client.ts                 # Axios 实例配置
│   ├── assessment/               # 评估领域 API
│   │   ├── index.ts
│   │   └── types.ts
│   ├── documents/                # 文档管理领域 API
│   │   ├── index.ts
│   │   └── types.ts
│   ├── knowledge/                # 知识搜索领域 API
│   │   ├── index.ts
│   │   └── types.ts
│   └── rag-test/                 # RAG 测试领域 API
│       ├── index.ts
│       └── types.ts
│
├── components/                   # 共享组件库
│   ├── ui/                       # 基础 UI 组件
│   │   ├── ErrorBoundary.tsx
│   │   ├── LoadingSpinner.tsx
│   │   └── EmptyState.tsx
│   ├── assessment/               # 评估领域组件
│   │   ├── AssessmentForm.tsx
│   │   ├── AssessmentForm.module.scss
│   │   └── ReportViewer.tsx
│   ├── documents/                # 文档管理组件
│   │   ├── DocumentUploader.tsx
│   │   ├── DocumentList.tsx
│   │   └── TaskProgressList.tsx
│   ├── knowledge/                # 知识搜索组件
│   │   ├── SearchInput.tsx
│   │   ├── SearchResultList.tsx
│   │   └── ResultDetailModal.tsx
│   └── rag-test/                 # RAG 测试组件
│       ├── TestCaseTable.tsx
│       ├── TestRunTable.tsx
│       ├── SnapshotTable.tsx
│       └── TestCaseModal.tsx
│
├── features/                     # 业务功能模块（页面级）
│   ├── assessment/               # 评估功能
│   │   ├── pages/
│   │   │   └── HomePage.tsx
│   │   ├── hooks/
│   │   │   └── useAssessment.ts
│   │   └── index.ts
│   ├── documents/                # 文档管理功能
│   │   ├── pages/
│   │   │   └── KnowledgeBasePage.tsx
│   │   ├── hooks/
│   │   │   └── useDocumentManagement.ts
│   │   └── index.ts
│   ├── knowledge/                # 知识搜索功能
│   │   ├── pages/
│   │   │   └── KnowledgeSearchPage.tsx
│   │   ├── hooks/
│   │   │   └── useKnowledgeSearch.ts
│   │   └── index.ts
│   └── rag-test/                 # RAG 测试功能
│       ├── pages/
│       │   └── RagTestPage.tsx
│       ├── hooks/
│       │   └── useRagTest.ts
│       └── index.ts
│
├── hooks/                        # 共享 Hooks
│   ├── useDebounce.ts
│   ├── usePagination.ts
│   └── useModal.ts
│
├── lib/
│   ├── queryClient.ts
│   └── constants.ts              # 全局常量定义
│
├── models/                       # 类型定义（按领域组织）
│   ├── assessment/
│   │   ├── child.ts
│   │   ├── plan.ts
│   │   ├── history.ts
│   │   ├── report.ts
│   │   ├── input.ts
│   │   └── index.ts
│   ├── documents/
│   │   ├── document.ts
│   │   ├── task.ts
│   │   ├── chunk.ts
│   │   └── index.ts
│   ├── knowledge/
│   │   ├── search.ts
│   │   └── index.ts
│   └── rag-test/
│       ├── testCase.ts
│       ├── testRun.ts
│       ├── snapshot.ts
│       └── index.ts
│
├── router/
│   └── index.tsx
│
├── store/                        # 客户端状态管理
│   ├── assessmentStore.ts
│   └── uiStore.ts
│
├── utils/                        # 工具函数
│   ├── formatters.ts
│   ├── validators.ts
│   └── highlight.ts
│
├── App.tsx
├── main.tsx
└── index.scss
```

---

## Chunk 1: 基础设施层建设

### Task 1: 创建新的目录结构

**Files:**
- Create: `frontend/src/api/assessment/`
- Create: `frontend/src/api/documents/`
- Create: `frontend/src/api/knowledge/`
- Create: `frontend/src/api/rag-test/`
- Create: `frontend/src/components/ui/`
- Create: `frontend/src/components/assessment/`
- Create: `frontend/src/components/documents/`
- Create: `frontend/src/components/knowledge/`
- Create: `frontend/src/components/rag-test/`
- Create: `frontend/src/features/assessment/`
- Create: `frontend/src/features/documents/`
- Create: `frontend/src/features/knowledge/`
- Create: `frontend/src/features/rag-test/`
- Create: `frontend/src/models/assessment/`
- Create: `frontend/src/models/documents/`
- Create: `frontend/src/models/knowledge/`
- Create: `frontend/src/models/rag-test/`
- Create: `frontend/src/hooks/` (shared hooks)
- Create: `frontend/src/utils/`
- Create: `frontend/src/lib/constants.ts`

- [ ] **Step 1: 创建所有目录**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend/src

# API 层目录
mkdir -p api/assessment api/documents api/knowledge api/rag-test

# 组件库目录
mkdir -p components/ui components/assessment components/documents components/knowledge components/rag-test

# 功能模块目录
mkdir -p features/assessment/pages features/assessment/hooks
mkdir -p features/documents/pages features/documents/hooks
mkdir -p features/knowledge/pages features/knowledge/hooks
mkdir -p features/rag-test/pages features/rag-test/hooks

# 模型目录
mkdir -p models/assessment models/documents models/knowledge models/rag-test

# 工具和共享目录
mkdir -p hooks utils
```

- [ ] **Step 2: 验证目录创建成功**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend/src
find . -type d | sort
```

---

### Task 2: 定义全局常量和工具函数

**Files:**
- Create: `frontend/src/lib/constants.ts`
- Create: `frontend/src/utils/formatters.ts`
- Create: `frontend/src/utils/validators.ts`
- Create: `frontend/src/utils/highlight.ts`

- [ ] **Step 1: 创建全局常量定义**

```typescript
// frontend/src/lib/constants.ts

// API 相关
export const API_BASE_URL = '/';
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
  PROCESSING: 'processing',
  SUCCESS: 'success',
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
  SHORT: 1 * 60 * 1000,      // 1 分钟
  MEDIUM: 5 * 60 * 1000,     // 5 分钟
  LONG: 30 * 60 * 1000,      // 30 分钟
  NEVER: Infinity,
} as const;

// 轮询间隔
export const POLLING_INTERVAL = 2000; // 2 秒

// 防抖延迟
export const DEBOUNCE_DELAY = 500; // 500 毫秒
```

- [ ] **Step 2: 创建格式化工具函数**

```typescript
// frontend/src/utils/formatters.ts

import dayjs from 'dayjs';

/**
 * 格式化日期时间
 */
export const formatDateTime = (date: string | Date): string => {
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss');
};

/**
 * 格式化日期
 */
export const formatDate = (date: string | Date): string => {
  return dayjs(date).format('YYYY-MM-DD');
};

/**
 * 格式化文件大小
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
};

/**
 * 格式化百分比
 */
export const formatPercentage = (value: number, decimals: number = 1): string => {
  return `${(value * 100).toFixed(decimals)}%`;
};

/**
 * 格式化任务状态显示文本
 */
export const formatTaskStatus = (status: string): string => {
  const statusMap: Record<string, string> = {
    pending: '排队中',
    processing: '处理中',
    success: '完成',
    failed: '失败',
    cancelled: '已取消',
  };
  return statusMap[status] || status;
};

/**
 * 格式化任务阶段显示文本
 */
export const formatTaskStage = (stage: string): string => {
  const stageMap: Record<string, string> = {
    pending: '等待中',
    parsing: '解析中',
    chunking: '分块中',
    embedding: '向量化中',
    indexing: '索引中',
    completed: '已完成',
  };
  return stageMap[stage] || stage;
};

/**
 * 格式化页码/章节显示
 */
export const formatPageLabel = (pageLabel: string, chapterTitle?: string): string => {
  if (!pageLabel) return '无';
  
  // EPUB 章节文件
  if (pageLabel.endsWith('.xhtml') || pageLabel.endsWith('.html')) {
    const match = pageLabel.match(/part(\d+)/i) || pageLabel.match(/chapter(\d+)/i);
    if (match) {
      return `第${parseInt(match[1])}章`;
    }
    const numMatch = pageLabel.match(/(\d+)/);
    if (numMatch) {
      return `第${parseInt(numMatch[1])}章`;
    }
    return chapterTitle || '章节内容';
  }
  
  // 普通页码
  if (/^\d+$/.test(pageLabel)) {
    return `第 ${pageLabel} 页`;
  }
  
  return pageLabel;
};
```

- [ ] **Step 3: 创建验证工具函数**

```typescript
// frontend/src/utils/validators.ts

import { MAX_FILE_SIZE_MB, ALLOWED_FILE_EXTENSIONS } from '../lib/constants';

/**
 * 验证文件类型
 */
export const validateFileType = (file: File): { valid: boolean; message?: string } => {
  const extension = '.' + file.name.split('.').pop()?.toLowerCase();
  const isAllowedType = ALLOWED_FILE_EXTENSIONS.includes(extension);
  
  if (!isAllowedType) {
    return {
      valid: false,
      message: `仅支持上传 ${ALLOWED_FILE_EXTENSIONS.join('、')} 格式的文件`,
    };
  }
  
  return { valid: true };
};

/**
 * 验证文件大小
 */
export const validateFileSize = (file: File): { valid: boolean; message?: string } => {
  const isLtMaxSize = file.size / 1024 / 1024 < MAX_FILE_SIZE_MB;
  
  if (!isLtMaxSize) {
    return {
      valid: false,
      message: `文件大小不能超过 ${MAX_FILE_SIZE_MB}MB`,
    };
  }
  
  return { valid: true };
};

/**
 * 验证文件
 */
export const validateFile = (file: File): { valid: boolean; message?: string } => {
  const typeValidation = validateFileType(file);
  if (!typeValidation.valid) return typeValidation;
  
  const sizeValidation = validateFileSize(file);
  if (!sizeValidation.valid) return sizeValidation;
  
  return { valid: true };
};

/**
 * 验证邮箱格式
 */
export const validateEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * 验证年龄范围
 */
export const validateAge = (age: number, min: number = 0, max: number = 18): boolean => {
  return age >= min && age <= max && Number.isInteger(age);
};
```

- [ ] **Step 4: 创建高亮工具函数**

```typescript
// frontend/src/utils/highlight.ts

import React from 'react';

/**
 * 转义正则表达式特殊字符
 */
const escapeRegExp = (string: string): string => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
};

/**
 * 高亮文本中的关键词
 * @param text 原始文本
 * @param keywords 关键词（空格分隔）
 * @param highlightClassName 高亮样式类名
 */
export const highlightKeywords = (
  text: string,
  keywords: string,
  highlightClassName: string = 'highlight'
): React.ReactNode => {
  if (!keywords.trim()) return text;
  
  const keywordList = keywords.split(/\s+/).filter(k => k);
  if (keywordList.length === 0) return text;

  const regex = new RegExp(
    `(${keywordList.map(escapeRegExp).join('|')})`,
    'gi'
  );
  
  return text.split(regex).map((part, index) => {
    if (keywordList.some(k => k.toLowerCase() === part.toLowerCase())) {
      return React.createElement('mark', { key: index, className: highlightClassName }, part);
    }
    return part;
  });
};

/**
 * 高亮文本（返回字符串数组，用于更灵活的渲染）
 */
export const highlightKeywordsToArray = (
  text: string,
  keywords: string
): Array<{ text: string; isHighlight: boolean }> => {
  if (!keywords.trim()) return [{ text, isHighlight: false }];
  
  const keywordList = keywords.split(/\s+/).filter(k => k);
  if (keywordList.length === 0) return [{ text, isHighlight: false }];

  const regex = new RegExp(
    `(${keywordList.map(escapeRegExp).join('|')})`,
    'gi'
  );
  
  return text.split(regex).map(part => ({
    text: part,
    isHighlight: keywordList.some(k => k.toLowerCase() === part.toLowerCase()),
  }));
};
```

- [ ] **Step 5: 验证工具函数可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/lib/constants.ts frontend/src/utils/
git commit -m "feat(frontend): 添加全局常量和工具函数库"
```

---

### Task 3: 创建共享 Hooks

**Files:**
- Create: `frontend/src/hooks/useDebounce.ts`
- Create: `frontend/src/hooks/usePagination.ts`
- Create: `frontend/src/hooks/useModal.ts`

- [ ] **Step 1: 创建防抖 Hook**

```typescript
// frontend/src/hooks/useDebounce.ts

import { useState, useEffect, useCallback } from 'react';

/**
 * 防抖 Hook
 * @param value 需要防抖的值
 * @param delay 延迟时间（毫秒）
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * 防抖回调 Hook
 * @param callback 需要防抖的回调函数
 * @param delay 延迟时间（毫秒）
 */
export function useDebounceCallback<T extends (...args: any[]) => any>(
  callback: T,
  delay: number
): T {
  const [timer, setTimer] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [timer]);

  return useCallback((...args: Parameters<T>) => {
    if (timer) clearTimeout(timer);
    const newTimer = setTimeout(() => {
      callback(...args);
    }, delay);
    setTimer(newTimer);
  }, [callback, delay]) as T;
}
```

- [ ] **Step 2: 创建分页 Hook**

```typescript
// frontend/src/hooks/usePagination.ts

import { useState, useCallback } from 'react';
import { DEFAULT_PAGE_SIZE } from '../lib/constants';

interface UsePaginationOptions {
  initialPage?: number;
  initialPageSize?: number;
}

interface UsePaginationReturn {
  currentPage: number;
  pageSize: number;
  total: number;
  setCurrentPage: (page: number) => void;
  setPageSize: (size: number) => void;
  setTotal: (total: number) => void;
  reset: () => void;
  offset: number;
}

/**
 * 分页状态管理 Hook
 */
export function usePagination(options: UsePaginationOptions = {}): UsePaginationReturn {
  const { initialPage = 1, initialPageSize = DEFAULT_PAGE_SIZE } = options;
  
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [total, setTotal] = useState(0);

  const reset = useCallback(() => {
    setCurrentPage(initialPage);
    setPageSize(initialPageSize);
    setTotal(0);
  }, [initialPage, initialPageSize]);

  const offset = (currentPage - 1) * pageSize;

  return {
    currentPage,
    pageSize,
    total,
    setCurrentPage,
    setPageSize: useCallback((size: number) => {
      setPageSize(size);
      setCurrentPage(1); // 改变页大小时重置到第一页
    }, []),
    setTotal,
    reset,
    offset,
  };
}
```

- [ ] **Step 3: 创建弹窗 Hook**

```typescript
// frontend/src/hooks/useModal.ts

import { useState, useCallback } from 'react';

interface UseModalOptions<T = any> {
  initialData?: T | null;
}

interface UseModalReturn<T> {
  isOpen: boolean;
  data: T | null;
  open: (data?: T) => void;
  close: () => void;
  toggle: () => void;
  reset: () => void;
}

/**
 * 弹窗状态管理 Hook
 */
export function useModal<T = any>(options: UseModalOptions<T> = {}): UseModalReturn<T> {
  const { initialData = null } = options;
  
  const [isOpen, setIsOpen] = useState(false);
  const [data, setData] = useState<T | null>(initialData);

  const open = useCallback((newData?: T) => {
    setData(newData ?? null);
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  const toggle = useCallback(() => {
    setIsOpen(prev => !prev);
  }, []);

  const reset = useCallback(() => {
    setIsOpen(false);
    setData(initialData);
  }, [initialData]);

  return {
    isOpen,
    data,
    open,
    close,
    toggle,
    reset,
  };
}
```

- [ ] **Step 4: 验证 Hooks 可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 5: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/hooks/
git commit -m "feat(frontend): 添加共享 Hooks（防抖、分页、弹窗）"
```

---

### Task 4: 拆分 API 层

**Files:**
- Modify: `frontend/src/api/client.ts` (保留基础配置)
- Create: `frontend/src/api/assessment/types.ts`
- Create: `frontend/src/api/assessment/index.ts`
- Create: `frontend/src/api/documents/types.ts`
- Create: `frontend/src/api/documents/index.ts`
- Create: `frontend/src/api/knowledge/types.ts`
- Create: `frontend/src/api/knowledge/index.ts`
- Create: `frontend/src/api/rag-test/types.ts`
- Create: `frontend/src/api/rag-test/index.ts`

- [ ] **Step 1: 重构基础 client.ts**

```typescript
// frontend/src/api/client.ts

import axios from 'axios';
import { API_BASE_URL, API_TIMEOUT } from '../lib/constants';

/**
 * 创建 Axios 实例
 */
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * 请求拦截器
 */
apiClient.interceptors.request.use(
  (config) => {
    // 可在此添加 token、请求 ID 等
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * 响应拦截器
 */
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // 统一错误处理
    const message = error.response?.data?.detail || error.message || '请求失败';
    console.error('[API Error]', message, error.config?.url);
    return Promise.reject(error);
  }
);

export default apiClient;
```

- [ ] **Step 2: 创建评估领域 API**

```typescript
// frontend/src/api/assessment/types.ts

import { UserInput, FinalReport, StreamingReportData } from '../../models';

export type { UserInput, FinalReport, StreamingReportData };

// 流式进度状态
export interface LayeredProgressStatus {
  task_id: string;
  total: number;
  processed: number;
  progress: number;
  status: 'running' | 'completed';
  start_time: string;
  end_time?: string;
}
```

```typescript
// frontend/src/api/assessment/index.ts

import apiClient from '../client';
import type { UserInput, FinalReport, LayeredProgressStatus } from './types';
import type { StreamingReportData } from '../../models';

/**
 * 评估发展（非流式）
 */
export const assessDevelopment = async (data: UserInput): Promise<FinalReport> => {
  const response = await apiClient.post<FinalReport>('/assess', { ...data, is_streaming: false });
  return response.data;
};

/**
 * 评估发展（流式）
 */
export const assessDevelopmentStream = async (
  data: UserInput,
  onData: (data: StreamingReportData) => void,
  onMessage: (chunk: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): Promise<void> => {
  try {
    const response = await fetch('/assess', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ...data, is_streaming: true }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '请求失败' }));
      onError(errorData.detail || `请求失败: ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError('无法读取响应流');
      return;
    }

    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const block of lines) {
        if (!block.trim()) continue;

        const blockLines = block.split('\n');
        let event = '';
        let dataStr = '';

        for (const line of blockLines) {
          if (line.startsWith('event: ')) {
            event = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.substring(6);
          }
        }

        if (!event || !dataStr) continue;

        try {
          if (event === 'data') {
            const data = JSON.parse(dataStr) as StreamingReportData;
            onData(data);
          } else if (event === 'message') {
            const chunk = JSON.parse(dataStr) as string;
            onMessage(chunk);
          } else if (event === 'done' && dataStr === '[DONE]') {
            onDone();
          }
        } catch (e) {
          console.error('解析SSE消息失败:', e, block);
        }
      }
    }
  } catch (err: any) {
    console.error('流式请求失败:', err);
    onError(err.message || '网络请求失败');
  }
};

/**
 * 获取分层内容生成进度
 */
export const getLayeredProgress = async (taskId: string): Promise<LayeredProgressStatus> => {
  const response = await apiClient.get<LayeredProgressStatus>(`/rag/layered-progress/${taskId}`);
  return response.data;
};

/**
 * 获取所有分层内容生成进度
 */
export const getAllLayeredProgress = async (): Promise<{ tasks: LayeredProgressStatus[] }> => {
  const response = await apiClient.get<{ tasks: LayeredProgressStatus[] }>('/rag/layered-progress');
  return response.data;
};
```

- [ ] **Step 3: 创建文档管理领域 API**

```typescript
// frontend/src/api/documents/types.ts

/**
 * 文档记录
 */
export interface DocumentRecord {
  file_hash: string;
  file_name: string;
  uploaded_at: string;
  total_pages: number;
}

/**
 * RAG 状态
 */
export interface RagStatus {
  index_ready: boolean;
  storage_dir: string;
  document_count: number;
}

/**
 * 上传任务状态
 */
export interface UploadTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'success' | 'failed' | 'cancelled';
  filename: string;
  created_at: number;
  message: string;
  error?: string;
  progress?: number;
  stage?: 'pending' | 'parsing' | 'chunking' | 'embedding' | 'indexing' | 'completed';
}

/**
 * 分块元数据
 */
export interface ChunkMetadata {
  file_hash: string;
  source_book: string;
  page_label?: string;
  chapter_title?: string;
  target_age_min?: number;
  target_age_max?: number;
  brain_regions?: string[];
  topics?: string[];
  [key: string]: any;
}

/**
 * 文档分块
 */
export interface DocumentChunk {
  id: string;
  content: string;
  metadata: ChunkMetadata;
  start_char_idx: number;
  end_char_idx: number;
  score?: number;
}

/**
 * 分块详情
 */
export interface ChunkDetail extends DocumentChunk {
  relationships?: any;
}
```

```typescript
// frontend/src/api/documents/index.ts

import apiClient from '../client';
import type { 
  DocumentRecord, 
  RagStatus, 
  UploadTaskStatus, 
  DocumentChunk, 
  ChunkDetail 
} from './types';

/**
 * 上传文档
 */
export const uploadDocument = async (file: File): Promise<{ 
  status: string; 
  filename: string; 
  message: string;
  task_id?: string;
}> => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await apiClient.post('/rag/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

/**
 * 获取 RAG 状态
 */
export const getRagStatus = async (): Promise<RagStatus> => {
  const response = await apiClient.get<RagStatus>('/rag/status');
  return response.data;
};

/**
 * 获取文档列表
 */
export const getDocuments = async (): Promise<{ documents: DocumentRecord[] }> => {
  const response = await apiClient.get<{ documents: DocumentRecord[] }>('/rag/documents');
  return response.data;
};

/**
 * 删除文档
 */
export const deleteDocument = async (filename: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.delete(`/rag/documents/${encodeURIComponent(filename)}`);
  return response.data;
};

/**
 * 获取上传任务状态
 */
export const getUploadTaskStatus = async (taskId: string): Promise<UploadTaskStatus> => {
  const response = await apiClient.get<UploadTaskStatus>(`/rag/tasks/${taskId}`);
  return response.data;
};

/**
 * 获取所有上传任务
 */
export const getUploadTasks = async (): Promise<{ tasks: UploadTaskStatus[] }> => {
  const response = await apiClient.get<{ tasks: UploadTaskStatus[] }>('/rag/tasks');
  return response.data;
};

/**
 * 取消上传任务
 */
export const cancelUploadTask = async (taskId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.post<{ status: string; message: string }>(`/rag/tasks/${taskId}/cancel`);
  return response.data;
};

/**
 * 获取文档分块列表
 */
export const getDocumentChunks = async (
  fileHash: string, 
  page: number = 1, 
  pageSize: number = 20
): Promise<{ 
  status: string; 
  file_hash: string;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  chunks: DocumentChunk[]
}> => {
  const response = await apiClient.get(`/rag/documents/${encodeURIComponent(fileHash)}/chunks`, {
    params: { page, page_size: pageSize }
  });
  return response.data;
};

/**
 * 获取分块详情
 */
export const getChunkDetail = async (chunkId: string): Promise<{ 
  status: string; 
  chunk: ChunkDetail 
}> => {
  const response = await apiClient.get(`/rag/chunks/${encodeURIComponent(chunkId)}`);
  return response.data;
};
```

- [ ] **Step 4: 创建知识搜索领域 API**

```typescript
// frontend/src/api/knowledge/types.ts

/**
 * 搜索结果项
 */
export interface SearchResultItem {
  id: string;
  content: string;
  score: number;
  source_book: string;
  chapter_title?: string;
  page_label?: string;
  target_age_min: number;
  target_age_max: number;
  brain_regions: string[];
  topics: string[];
  file_hash: string;
}
```

```typescript
// frontend/src/api/knowledge/index.ts

import apiClient from '../client';
import type { SearchResultItem } from './types';

/**
 * 搜索知识库
 */
export const searchKnowledge = async (
  query: string, 
  limit: number = 20
): Promise<{ 
  status: string; 
  total: number; 
  results: SearchResultItem[] 
}> => {
  const response = await apiClient.get('/rag/search', {
    params: { query, limit }
  });
  return response.data;
};
```

- [ ] **Step 5: 创建 RAG 测试领域 API**

```typescript
// frontend/src/api/rag-test/types.ts

/**
 * 测试用例
 */
export interface TestCase {
  id: string;
  query: string;
  age: number;
  expected_knowledge_ids: string[];
  expected_keywords: string[];
  description: string;
  created_at: string;
  updated_at: string;
}

/**
 * 测试结果项
 */
export interface TestResultItem {
  knowledge_id: string;
  content: string;
  score: number;
  expected: boolean;
  rank: number;
}

/**
 * 测试结果
 */
export interface TestResult {
  test_case_id: string;
  query: string;
  age: number;
  precision: number;
  recall: number;
  f1_score: number;
  mrr: number;
  results: TestResultItem[];
  executed_at: string;
  execution_time_ms: number;
}

/**
 * 测试运行
 */
export interface TestRun {
  id: string;
  name: string;
  description: string;
  test_results: TestResult[];
  overall_precision: number;
  overall_recall: number;
  overall_f1: number;
  overall_mrr: number;
  total_test_cases: number;
  passed_test_cases: number;
  status: string;
  created_at: string;
  completed_at?: string;
  snapshot_id?: string;
}

/**
 * 知识快照
 */
export interface KnowledgeSnapshot {
  id: string;
  name: string;
  description: string;
  document_count: number;
  document_hashes: string[];
  index_size_bytes: number;
  created_at: string;
  storage_path: string;
}
```

```typescript
// frontend/src/api/rag-test/index.ts

import apiClient from '../client';
import type { TestCase, TestRun, KnowledgeSnapshot, TestResult } from './types';

// 测试用例管理
export const createTestCase = async (data: Omit<TestCase, 'id' | 'created_at' | 'updated_at'>): Promise<TestCase> => {
  const response = await apiClient.post<TestCase>('/rag/test/cases', data);
  return response.data;
};

export const getTestCases = async (): Promise<TestCase[]> => {
  const response = await apiClient.get<TestCase[]>('/rag/test/cases');
  return response.data;
};

export const getTestCase = async (caseId: string): Promise<TestCase> => {
  const response = await apiClient.get<TestCase>(`/rag/test/cases/${caseId}`);
  return response.data;
};

export const updateTestCase = async (caseId: string, data: Partial<TestCase>): Promise<TestCase> => {
  const response = await apiClient.put<TestCase>(`/rag/test/cases/${caseId}`, data);
  return response.data;
};

export const deleteTestCase = async (caseId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.delete(`/rag/test/cases/${caseId}`);
  return response.data;
};

// 测试执行
export const runAllTests = async (data?: { name?: string; description?: string; limit?: number }): Promise<{ status: string; test_run: TestRun }> => {
  const response = await apiClient.post('/rag/test/run', data || {});
  return response.data;
};

export const runSingleTest = async (caseId: string, limit: number = 10): Promise<{ status: string; result: TestResult }> => {
  const response = await apiClient.post(`/rag/test/run/${caseId}?limit=${limit}`);
  return response.data;
};

// 测试运行结果
export const getTestRuns = async (): Promise<TestRun[]> => {
  const response = await apiClient.get<TestRun[]>('/rag/test/runs');
  return response.data;
};

export const getTestRun = async (runId: string): Promise<TestRun> => {
  const response = await apiClient.get<TestRun>(`/rag/test/runs/${runId}`);
  return response.data;
};

export const compareTestRuns = async (runId1: string, runId2: string): Promise<{ status: string; comparison: any }> => {
  const response = await apiClient.get(`/rag/test/compare?run_id1=${runId1}&runId2=${runId2}`);
  return response.data;
};

// 快照管理
export const createSnapshot = async (data?: { name?: string; description?: string }): Promise<{ status: string; snapshot: KnowledgeSnapshot }> => {
  const response = await apiClient.post('/rag/test/snapshots', data || {});
  return response.data;
};

export const getSnapshots = async (): Promise<KnowledgeSnapshot[]> => {
  const response = await apiClient.get<KnowledgeSnapshot[]>('/rag/test/snapshots');
  return response.data;
};

export const getSnapshot = async (snapshotId: string): Promise<KnowledgeSnapshot> => {
  const response = await apiClient.get<KnowledgeSnapshot>(`/rag/test/snapshots/${snapshotId}`);
  return response.data;
};

export const restoreSnapshot = async (snapshotId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.post(`/rag/test/snapshots/${snapshotId}/restore`);
  return response.data;
};
```

- [ ] **Step 6: 更新旧 API 文件导出（向后兼容）**

```typescript
// frontend/src/api/client.ts (在文件末尾添加)

// 向后兼容导出
export * from './assessment';
export * from './documents';
export * from './knowledge';
export * from './rag-test';
```

- [ ] **Step 7: 验证 API 层可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 8: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/api/
git commit -m "refactor(frontend): 按领域拆分 API 层，提升可维护性"
```

---

### Task 5: 重组 Models 类型定义

**Files:**
- Create: `frontend/src/models/assessment/child.ts`
- Create: `frontend/src/models/assessment/plan.ts`
- Create: `frontend/src/models/assessment/history.ts`
- Create: `frontend/src/models/assessment/report.ts`
- Create: `frontend/src/models/assessment/input.ts`
- Create: `frontend/src/models/assessment/index.ts`
- Create: `frontend/src/models/documents/index.ts` (re-export from api/documents/types)
- Create: `frontend/src/models/knowledge/index.ts` (re-export from api/knowledge/types)
- Create: `frontend/src/models/rag-test/index.ts` (re-export from api/rag-test/types)

- [ ] **Step 1: 移动评估相关模型**

```typescript
// frontend/src/models/assessment/child.ts
export type GenderType = "male" | "female" | "other";

export interface ChildProfile {
  name: string;
  age: number;
  gender: GenderType;
  issues: string[];
  interests: string[];
}
```

```typescript
// frontend/src/models/assessment/plan.ts
export type IntensityType = "low" | "medium" | "high";

export interface Activity {
  name: string;
  duration_minutes: number;
  frequency_weekly: number;
  intensity?: IntensityType | null;
  description?: string | null;
}

export interface ProposedPlan {
  plan_name: string;
  activities: Activity[];
  goals: string[];
}
```

```typescript
// frontend/src/models/assessment/history.ts
import { IntensityType } from './plan';

export interface HistoryActivity {
  name: string;
  duration_minutes: number;
  intensity?: IntensityType | null;
  feedback?: string | null;
}

export interface HistoryRecord {
  date: string;
  activities: HistoryActivity[];
  notes?: string | null;
}
```

```typescript
// frontend/src/models/assessment/report.ts
export interface FinalReport {
  markdown_content: string;
  structured_data: Record<string, any>;
}

export interface StreamingReportData {
  score: number;
  radar_chart: Record<string, any>;
  key_suggestions: string[];
}
```

```typescript
// frontend/src/models/assessment/input.ts
import { ChildProfile } from './child';
import { ProposedPlan } from './plan';
import { HistoryRecord } from './history';

export interface UserInput {
  child_profile: ChildProfile;
  proposed_plan: ProposedPlan;
  history_context?: HistoryRecord[];
}
```

```typescript
// frontend/src/models/assessment/index.ts
export * from './child';
export * from './plan';
export * from './history';
export * from './report';
export * from './input';
```

- [ ] **Step 2: 创建其他领域模型索引**

```typescript
// frontend/src/models/documents/index.ts
export type {
  DocumentRecord,
  RagStatus,
  UploadTaskStatus,
  ChunkMetadata,
  DocumentChunk,
  ChunkDetail,
} from '../../api/documents/types';
```

```typescript
// frontend/src/models/knowledge/index.ts
export type {
  SearchResultItem,
} from '../../api/knowledge/types';
```

```typescript
// frontend/src/models/rag-test/index.ts
export type {
  TestCase,
  TestResultItem,
  TestResult,
  TestRun,
  KnowledgeSnapshot,
} from '../../api/rag-test/types';
```

- [ ] **Step 3: 更新旧 models/index.ts（向后兼容）**

```typescript
// frontend/src/models/index.ts

// 评估领域模型
export * from './assessment';

// 文档领域模型（re-export）
export type {
  DocumentRecord,
  RagStatus,
  UploadTaskStatus,
  ChunkMetadata,
  DocumentChunk,
  ChunkDetail,
} from '../api/documents/types';

// 知识搜索领域模型（re-export）
export type {
  SearchResultItem,
} from '../api/knowledge/types';

// RAG 测试领域模型（re-export）
export type {
  TestCase,
  TestResultItem,
  TestResult,
  TestRun,
  KnowledgeSnapshot,
} from '../api/rag-test/types';
```

- [ ] **Step 4: 移动旧模型文件到新位置**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend/src

# 移动旧文件到新目录
mv models/Child.ts models/assessment/child.ts
mv models/Plan.ts models/assessment/plan.ts
mv models/History.ts models/assessment/history.ts
mv models/Report.ts models/assessment/report.ts
mv models/Input.ts models/assessment/input.ts

# 删除旧的 index.ts（已创建新的）
rm models/index.ts
```

- [ ] **Step 5: 验证类型系统可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/models/
git commit -m "refactor(frontend): 按领域重组类型定义，建立清晰的类型层次"
```

---

## Chunk 2: 组件层重构

### Task 6: 创建共享 UI 组件

**Files:**
- Create: `frontend/src/components/ui/ErrorBoundary.tsx`
- Create: `frontend/src/components/ui/LoadingSpinner.tsx`
- Create: `frontend/src/components/ui/EmptyState.tsx`

- [ ] **Step 1: 创建错误边界组件**

```typescript
// frontend/src/components/ui/ErrorBoundary.tsx

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Result, Button } from 'antd';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * 错误边界组件，捕获子组件树中的 JavaScript 错误
 */
export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] Uncaught error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Result
          status="error"
          title="出现了一些问题"
          subTitle={this.state.error?.message || '未知错误'}
          extra={
            <Button type="primary" onClick={this.handleReset}>
              重试
            </Button>
          }
        />
      );
    }

    return this.props.children;
  }
}
```

- [ ] **Step 2: 创建加载组件**

```typescript
// frontend/src/components/ui/LoadingSpinner.tsx

import React from 'react';
import { Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

interface LoadingSpinnerProps {
  size?: 'small' | 'default' | 'large';
  tip?: string;
  fullScreen?: boolean;
}

/**
 * 统一加载指示器组件
 */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'large',
  tip = '加载中...',
  fullScreen = false,
}) => {
  const indicator = <LoadingOutlined style={{ fontSize: size === 'large' ? 32 : 24 }} spin />;

  if (fullScreen) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        flexDirection: 'column',
        gap: '16px',
      }}>
        <Spin indicator={indicator} size={size} tip={tip} />
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: '48px 0',
      flexDirection: 'column',
      gap: '16px',
    }}>
      <Spin indicator={indicator} size={size} tip={tip} />
    </div>
  );
};
```

- [ ] **Step 3: 创建空状态组件**

```typescript
// frontend/src/components/ui/EmptyState.tsx

import React from 'react';
import { Empty, Button } from 'antd';

interface EmptyStateProps {
  description?: string;
  image?: React.ReactNode;
  actionText?: string;
  onAction?: () => void;
}

/**
 * 统一空状态组件
 */
export const EmptyState: React.FC<EmptyStateProps> = ({
  description = '暂无数据',
  image,
  actionText,
  onAction,
}) => {
  return (
    <Empty
      description={description}
      image={image || Empty.PRESENTED_IMAGE_SIMPLE}
    >
      {actionText && onAction && (
        <Button type="primary" onClick={onAction}>
          {actionText}
        </Button>
      )}
    </Empty>
  );
};
```

- [ ] **Step 4: 验证组件可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 5: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/components/ui/
git commit -m "feat(frontend): 添加共享 UI 组件（错误边界、加载、空状态）"
```

---

### Task 7: 拆分评估领域组件

**Files:**
- Move: `frontend/src/components/AssessmentForm.tsx` → `frontend/src/components/assessment/AssessmentForm.tsx`
- Move: `frontend/src/components/AssessmentForm.module.scss` → `frontend/src/components/assessment/AssessmentForm.module.scss`
- Move: `frontend/src/components/ReportViewer.tsx` → `frontend/src/components/assessment/ReportViewer.tsx`

- [ ] **Step 1: 移动评估表单组件**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend/src
mv components/AssessmentForm.tsx components/assessment/
mv components/AssessmentForm.module.scss components/assessment/
mv components/ReportViewer.tsx components/assessment/
```

- [ ] **Step 2: 更新 AssessmentForm 导入路径**

```typescript
// frontend/src/components/assessment/AssessmentForm.tsx

// 更新导入路径
import { UserInput } from '../../models/assessment';
import { useAssessmentForm } from '../../features/assessment/hooks/useAssessmentForm';
```

- [ ] **Step 3: 更新 ReportViewer 导入路径**

```typescript
// frontend/src/components/assessment/ReportViewer.tsx

// 更新导入路径
import { FinalReport } from '../../models/assessment';
```

- [ ] **Step 4: 验证组件可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 5: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/components/assessment/
git commit -m "refactor(frontend): 移动评估组件到领域目录"
```

---

### Task 8: 拆分文档管理组件

**Files:**
- Create: `frontend/src/components/documents/DocumentUploader.tsx`
- Create: `frontend/src/components/documents/DocumentList.tsx`
- Create: `frontend/src/components/documents/TaskProgressList.tsx`

- [ ] **Step 1: 创建文档上传组件**

```typescript
// frontend/src/components/documents/DocumentUploader.tsx

import React from 'react';
import { Upload, Button, App } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { uploadDocument } from '../../api/documents';
import { validateFile } from '../../utils/validators';
import type { UploadTaskStatus } from '../../api/documents/types';

interface DocumentUploaderProps {
  onUploadStart: (task: UploadTaskStatus) => void;
  onSuccess: () => void;
}

/**
 * 文档上传组件
 */
export const DocumentUploader: React.FC<DocumentUploaderProps> = ({
  onUploadStart,
  onSuccess,
}) => {
  const { message } = App.useApp();

  const handleUpload: UploadProps['beforeUpload'] = async (file) => {
    // 验证文件
    const validation = validateFile(file);
    if (!validation.valid) {
      message.error(validation.message!);
      return Upload.LIST_IGNORE;
    }

    try {
      const result = await uploadDocument(file);
      message.info(`${file.name} 已上传，正在后台处理中...`);
      
      if (result.task_id) {
        onUploadStart({
          task_id: result.task_id,
          status: 'pending',
          filename: file.name,
          created_at: Date.now() / 1000,
          message: '文件已上传，正在排队处理',
          progress: 0,
          stage: 'pending',
        });
      } else {
        message.success(`${file.name} 上传并索引成功`);
        onSuccess();
      }
    } catch (e: any) {
      message.error(`上传失败: ${e.response?.data?.detail || e.message}`);
    }

    return false;
  };

  return (
    <Upload
      beforeUpload={handleUpload}
      fileList={[]}
      showUploadList={false}
      accept=".pdf,.epub"
      multiple
    >
      <Button type="primary" icon={<UploadOutlined />} size="large">
        上传文档
      </Button>
    </Upload>
  );
};
```

- [ ] **Step 2: 创建文档列表组件**

```typescript
// frontend/src/components/documents/DocumentList.tsx

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { List, Button, Space, Typography, App } from 'antd';
import { DeleteOutlined, FileTextOutlined } from '@ant-design/icons';
import type { DocumentRecord } from '../../api/documents/types';
import { deleteDocument } from '../../api/documents';
import { formatDateTime } from '../../utils/formatters';

interface DocumentListProps {
  documents: DocumentRecord[];
  loading: boolean;
  onRefresh: () => void;
  excludeFilenames?: Set<string>;
}

/**
 * 文档列表组件
 */
export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  loading,
  onRefresh,
  excludeFilenames = new Set(),
}) => {
  const navigate = useNavigate();
  const { modal, message } = App.useApp();

  const handleDelete = (doc: DocumentRecord) => {
    modal.confirm({
      title: '确认删除',
      content: `确定要删除文档 "${doc.file_name}" 吗？删除后无法恢复。`,
      onOk: async () => {
        try {
          await deleteDocument(doc.file_name);
          message.success('删除成功');
          onRefresh();
        } catch (e: any) {
          message.error(`删除失败: ${e.response?.data?.detail || e.message}`);
        }
      },
    });
  };

  const filteredDocuments = documents.filter(
    doc => !excludeFilenames.has(doc.file_name)
  );

  return (
    <List
      loading={loading}
      dataSource={filteredDocuments}
      renderItem={(doc) => (
        <List.Item
          actions={[
            <Button
              type="link"
              icon={<FileTextOutlined />}
              onClick={() => navigate(`/book-chunks/${doc.file_hash}/${encodeURIComponent(doc.file_name)}`)}
            >
              查看分块
            </Button>,
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDelete(doc)}
            >
              删除
            </Button>,
          ]}
        >
          <List.Item.Meta
            title={doc.file_name}
            description={
              <Space>
                <Typography.Text type="secondary">共 {doc.total_pages} 页</Typography.Text>
                <Typography.Text type="secondary">
                  上传时间: {formatDateTime(doc.uploaded_at)}
                </Typography.Text>
              </Space>
            }
          />
        </List.Item>
      )}
      locale={{
        emptyText: '暂无上传的文档',
      }}
    />
  );
};
```

- [ ] **Step 3: 创建任务进度列表组件**

```typescript
// frontend/src/components/documents/TaskProgressList.tsx

import React from 'react';
import { List, Progress, Button, Space, Typography } from 'antd';
import { LoadingOutlined, StopOutlined } from '@ant-design/icons';
import type { UploadTaskStatus } from '../../api/documents/types';
import { formatTaskStatus } from '../../utils/formatters';
import { TASK_STATUS } from '../../lib/constants';

interface TaskProgressListProps {
  tasks: UploadTaskStatus[];
  onCancel: (taskId: string) => void;
}

/**
 * 上传任务进度列表组件
 */
export const TaskProgressList: React.FC<TaskProgressListProps> = ({
  tasks,
  onCancel,
}) => {
  if (tasks.length === 0) return null;

  return (
    <div>
      <Typography.Title level={5}>正在处理的文档</Typography.Title>
      <List
        dataSource={tasks}
        renderItem={(task) => (
          <List.Item
            actions={[
              (task.status === TASK_STATUS.PENDING || task.status === TASK_STATUS.PROCESSING) && (
                <Button
                  type="text"
                  danger
                  icon={<StopOutlined />}
                  onClick={() => onCancel(task.task_id)}
                >
                  中断
                </Button>
              )
            ]}
          >
            <Space orientation="vertical" style={{ width: '100%' }}>
              <Space>
                {(task.status === TASK_STATUS.PROCESSING || task.status === TASK_STATUS.PENDING) && (
                  <LoadingOutlined spin />
                )}
                <Typography.Text strong>{task.filename}</Typography.Text>
                <Typography.Text type="secondary">
                  {formatTaskStatus(task.status)}
                </Typography.Text>
              </Space>
              <Progress
                percent={Math.round(task.progress || (task.status === 'pending' ? 10 : 50))}
                status={task.status === 'failed' || task.status === 'cancelled' ? 'exception' : 'active'}
                showInfo={false}
              />
              <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                {task.message}
              </Typography.Text>
            </Space>
          </List.Item>
        )}
      />
    </div>
  );
};
```

- [ ] **Step 4: 验证组件可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 5: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/components/documents/
git commit -m "feat(frontend): 拆分文档管理组件（上传、列表、任务进度）"
```

---

### Task 9: 拆分知识搜索组件

**Files:**
- Create: `frontend/src/components/knowledge/SearchInput.tsx`
- Create: `frontend/src/components/knowledge/SearchResultList.tsx`
- Create: `frontend/src/components/knowledge/ResultDetailModal.tsx`

- [ ] **Step 1: 创建搜索输入组件**

```typescript
// frontend/src/components/knowledge/SearchInput.tsx

import React, { useRef } from 'react';
import { Input, Space, Typography } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { InputRef } from 'antd';
import { useDebounceCallback } from '../../hooks/useDebounce';
import { DEBOUNCE_DELAY } from '../../lib/constants';

interface SearchInputProps {
  onSearch: (query: string) => void;
  resultCount?: number;
}

/**
 * 知识搜索输入组件
 */
export const SearchInput: React.FC<SearchInputProps> = ({
  onSearch,
  resultCount,
}) => {
  const [query, setQuery] = React.useState('');
  const searchInputRef = useRef<InputRef>(null);

  const debouncedSearch = useDebounceCallback((value: string) => {
    if (value.trim()) {
      onSearch(value);
    }
  }, DEBOUNCE_DELAY);

  const handleSearch = (value: string) => {
    setQuery(value);
    debouncedSearch(value);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    if (value.trim()) {
      debouncedSearch(value);
    } else {
      onSearch('');
    }
  };

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <Search
        ref={searchInputRef}
        placeholder="输入关键词搜索知识库内容..."
        allowClear
        enterButton={<SearchOutlined />}
        size="large"
        onSearch={handleSearch}
        onChange={handleInputChange}
        value={query}
      />

      {query && (
        <Typography.Text type="secondary">
          找到 {resultCount || 0} 条相关结果，关键词: <Typography.Text strong>{query}</Typography.Text>
        </Typography.Text>
      )}
    </Space>
  );
};
```

- [ ] **Step 2: 创建搜索结果列表组件**

```typescript
// frontend/src/components/knowledge/SearchResultList.tsx

import React from 'react';
import { List, Button, Space, Tag, Typography, Pagination } from 'antd';
import { EyeOutlined, FileTextOutlined } from '@ant-design/icons';
import type { SearchResultItem } from '../../api/knowledge/types';
import { highlightKeywords } from '../../utils/highlight';
import styles from './SearchResultList.module.scss';

interface SearchResultListProps {
  results: SearchResultItem[];
  loading: boolean;
  query: string;
  total: number;
  currentPage: number;
  pageSize: number;
  onPageChange: (page: number, pageSize?: number) => void;
  onPreview: (item: SearchResultItem) => void;
}

/**
 * 搜索结果列表组件
 */
export const SearchResultList: React.FC<SearchResultListProps> = ({
  results,
  loading,
  query,
  total,
  currentPage,
  pageSize,
  onPageChange,
  onPreview,
}) => {
  if (results.length === 0) {
    return (
      <Typography.Empty>
        {query ? '没有找到相关内容，请尝试其他关键词' : '请输入关键词开始搜索'}
      </Typography.Empty>
    );
  }

  return (
    <>
      <List
        dataSource={results}
        renderItem={(item) => (
          <List.Item
            key={item.id}
            className={styles.resultItem}
            actions={[
              <Button
                type="link"
                size="small"
                icon={<EyeOutlined />}
                onClick={() => onPreview(item)}
              >
                查看详情
              </Button>
            ]}
          >
            <List.Item.Meta
              avatar={<FileTextOutlined style={{ fontSize: '24px', color: '#1890ff' }} />}
              title={
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <div className={styles.resultTitle}>
                    {highlightKeywords(
                      item.content.slice(0, 100) + (item.content.length > 100 ? '...' : ''),
                      query,
                      styles.highlight
                    )}
                  </div>
                  <Space size="small" wrap>
                    <Tag color="blue">相关度: {(item.score * 100).toFixed(1)}%</Tag>
                    <Tag color="green">来源: {item.source_book}</Tag>
                    {item.page_label && (
                      <Tag color="orange">
                        {/^\d+$/.test(item.page_label) ? 
                          '第 ' + item.page_label + ' 页' : 
                          item.page_label.includes('/') ? 
                            '章节: ' + (item.chapter_title || item.page_label.split('/').pop()) : 
                            item.page_label
                        }
                      </Tag>
                    )}
                  </Space>
                </Space>
              }
              description={
                <div className={styles.resultMeta}>
                  {Array.isArray(item.topics) && item.topics.length > 0 && (
                    <div className={styles.topicRow}>
                      <Typography.Text type="secondary" strong>主题:</Typography.Text>
                      <Space wrap size="small" style={{ marginLeft: 8 }}>
                        {item.topics.map((topic, idx) => (
                          <Tag key={idx}>{topic}</Tag>
                        ))}
                      </Space>
                    </div>
                  )}
                  {Array.isArray(item.brain_regions) && item.brain_regions.length > 0 && (
                    <div className={styles.topicRow}>
                      <Typography.Text type="secondary" strong>脑区:</Typography.Text>
                      <Space wrap size="small" style={{ marginLeft: 8 }}>
                        {item.brain_regions.map((region, idx) => (
                          <Tag key={idx} color="cyan">{region}</Tag>
                        ))}
                      </Space>
                    </div>
                  )}
                </div>
              }
            />
          </List.Item>
        )}
      />

      {total > pageSize && (
        <div className={styles.pagination}>
          <Pagination
            current={currentPage}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            showTotal={(total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`}
            onChange={(page, size) => onPageChange(page, size)}
          />
        </div>
      )}
    </>
  );
};
```

- [ ] **Step 3: 创建结果详情弹窗组件**

```typescript
// frontend/src/components/knowledge/ResultDetailModal.tsx

import React from 'react';
import { Modal, Descriptions, Divider, Typography, Space, Tag } from 'antd';
import type { SearchResultItem } from '../../api/knowledge/types';
import { highlightKeywords } from '../../utils/highlight';
import { formatPageLabel } from '../../utils/formatters';

interface ResultDetailModalProps {
  item: SearchResultItem | null;
  visible: boolean;
  query: string;
  onClose: () => void;
}

/**
 * 搜索结果详情弹窗组件
 */
export const ResultDetailModal: React.FC<ResultDetailModalProps> = ({
  item,
  visible,
  query,
  onClose,
}) => {
  if (!item) return null;

  return (
    <Modal
      title="内容详情"
      open={visible}
      onCancel={onClose}
      width={800}
      footer={[
        <Typography.Button key="close" onClick={onClose}>
          关闭
        </Typography.Button>
      ]}
    >
      <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
        <Descriptions.Item label="来源文档" span={2}>
          {item.source_book}
        </Descriptions.Item>
        {item.chapter_title && (
          <Descriptions.Item label="章节" span={2}>
            {item.chapter_title}
          </Descriptions.Item>
        )}
        {item.page_label && (
          <Descriptions.Item label="位置">
            {formatPageLabel(item.page_label, item.chapter_title)}
          </Descriptions.Item>
        )}
        <Descriptions.Item label="相关度">
          {(item.score * 100).toFixed(2)}%
        </Descriptions.Item>
      </Descriptions>

      <Divider />

      <Typography.Title level={5}>内容</Typography.Title>
      <div>
        <Typography.Paragraph>
          {highlightKeywords(item.content, query)}
        </Typography.Paragraph>
      </div>

      {Array.isArray(item.topics) && item.topics.length > 0 && (
        <>
          <Divider />
          <Typography.Title level={5}>主题标签</Typography.Title>
          <Space wrap>
            {item.topics.map((topic, idx) => (
              <Tag key={idx}>{topic}</Tag>
            ))}
          </Space>
        </>
      )}

      {Array.isArray(item.brain_regions) && item.brain_regions.length > 0 && (
        <>
          <Divider />
          <Typography.Title level={5}>刺激脑区</Typography.Title>
          <Space wrap>
            {item.brain_regions.map((region, idx) => (
              <Tag key={idx} color="cyan">{region}</Tag>
            ))}
          </Space>
        </>
      )}
    </Modal>
  );
};
```

- [ ] **Step 4: 创建 SearchResultList 样式文件**

```scss
// frontend/src/components/knowledge/SearchResultList.module.scss

.resultItem {
  padding: 16px 0;
  border-bottom: 1px solid #f0f0f0;

  &:last-child {
    border-bottom: none;
  }
}

.resultTitle {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
}

.highlight {
  background-color: #fff566;
  padding: 0 2px;
  border-radius: 2px;
}

.resultMeta {
  margin-top: 8px;
}

.topicRow {
  margin-top: 8px;
  display: flex;
  align-items: center;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
```

- [ ] **Step 5: 验证组件可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/components/knowledge/
git commit -m "feat(frontend): 拆分知识搜索组件（搜索输入、结果列表、详情弹窗）"
```

---

### Task 10: 拆分 RAG 测试组件

**Files:**
- Create: `frontend/src/components/rag-test/TestCaseTable.tsx`
- Create: `frontend/src/components/rag-test/TestRunTable.tsx`
- Create: `frontend/src/components/rag-test/SnapshotTable.tsx`
- Create: `frontend/src/components/rag-test/TestCaseModal.tsx`

- [ ] **Step 1: 创建测试用例表格组件**

```typescript
// frontend/src/components/rag-test/TestCaseTable.tsx

import React from 'react';
import { Table, Button, Space, Tag, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TestCase } from '../../api/rag-test/types';
import { formatDateTime } from '../../utils/formatters';

interface TestCaseTableProps {
  testCases: TestCase[];
  loading: boolean;
  testRunning: boolean;
  onAdd: () => void;
  onEdit: (record: TestCase) => void;
  onDelete: (id: string) => void;
  onRun: (record: TestCase) => void;
}

/**
 * 测试用例表格组件
 */
export const TestCaseTable: React.FC<TestCaseTableProps> = ({
  testCases,
  loading,
  testRunning,
  onAdd,
  onEdit,
  onDelete,
  onRun,
}) => {
  const columns: ColumnsType<TestCase> = [
    {
      title: '查询内容',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
      width: 250,
    },
    {
      title: '年龄',
      dataIndex: 'age',
      key: 'age',
      width: 80,
    },
    {
      title: '预期关键词',
      dataIndex: 'expected_keywords',
      key: 'expected_keywords',
      render: (keywords: string[]) => (
        <Space wrap>
          {keywords.map((kw, idx) => (
            <Tag key={idx}>{kw}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => formatDateTime(date),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => onRun(record)}
            loading={testRunning}
          >
            运行
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => onEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该测试用例吗？"
            onConfirm={() => onDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={testCases}
      rowKey="id"
      loading={loading}
      pagination={{
        pageSize: 10,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条测试用例`,
      }}
    />
  );
};
```

- [ ] **Step 2: 创建测试运行表格组件**

```typescript
// frontend/src/components/rag-test/TestRunTable.tsx

import React from 'react';
import { Table, Tag, Button, Modal, Row, Col, Statistic, Typography } from 'antd';
import { BarChartOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TestRun } from '../../api/rag-test/types';
import { formatDateTime, formatPercentage } from '../../utils/formatters';

interface TestRunTableProps {
  testRuns: TestRun[];
  loading: boolean;
}

/**
 * 测试运行记录表格组件
 */
export const TestRunTable: React.FC<TestRunTableProps> = ({
  testRuns,
  loading,
}) => {
  const columns: ColumnsType<TestRun> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const color = status === 'completed' ? 'green' : status === 'running' ? 'blue' : 'red';
        return <Tag color={color}>{status}</Tag>;
      },
    },
    {
      title: '用例总数',
      dataIndex: 'total_test_cases',
      key: 'total_test_cases',
      width: 100,
    },
    {
      title: '通过数',
      dataIndex: 'passed_test_cases',
      key: 'passed_test_cases',
      width: 100,
      render: (passed: number, record: TestRun) => (
        <span>{passed} / {record.total_test_cases}</span>
      ),
    },
    {
      title: '整体准确率',
      key: 'precision',
      width: 120,
      render: (_, record: TestRun) => formatPercentage(record.overall_precision),
    },
    {
      title: '整体F1',
      key: 'f1',
      width: 100,
      render: (_, record: TestRun) => formatPercentage(record.overall_f1),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => formatDateTime(date),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<BarChartOutlined />}
          onClick={() => {
            Modal.info({
              title: '测试运行详情',
              width: 900,
              content: (
                <div>
                  <Row gutter={16} style={{ marginBottom: 24 }}>
                    <Col span={6}>
                      <Statistic title="准确率" value={record.overall_precision * 100} suffix="%" precision={2} />
                    </Col>
                    <Col span={6}>
                      <Statistic title="召回率" value={record.overall_recall * 100} suffix="%" precision={2} />
                    </Col>
                    <Col span={6}>
                      <Statistic title="F1分数" value={record.overall_f1 * 100} suffix="%" precision={2} />
                    </Col>
                    <Col span={6}>
                      <Statistic title="MRR" value={record.overall_mrr} precision={4} />
                    </Col>
                  </Row>
                  <Typography.Title level={5}>测试用例详情</Typography.Title>
                  <Table
                    dataSource={record.test_results}
                    columns={[
                      { title: '查询', dataIndex: 'query', key: 'query', ellipsis: true },
                      { title: '准确率', dataIndex: 'precision', key: 'precision', render: v => formatPercentage(v) },
                      { title: 'F1', dataIndex: 'f1_score', key: 'f1', render: v => formatPercentage(v) },
                      { title: '状态', key: 'status', render: (_, r) => (
                        <Tag color={r.f1_score >= 0.7 ? 'green' : 'red'}>
                          {r.f1_score >= 0.7 ? '通过' : '失败'}
                        </Tag>
                      )},
                    ]}
                    rowKey="test_case_id"
                    pagination={false}
                    size="small"
                  />
                </div>
              )
            });
          }}
        >
          详情
        </Button>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={testRuns}
      rowKey="id"
      loading={loading}
      pagination={{
        pageSize: 10,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 次测试运行`,
      }}
    />
  );
};
```

- [ ] **Step 3: 创建快照表格组件**

```typescript
// frontend/src/components/rag-test/SnapshotTable.tsx

import React from 'react';
import { Table, Button, Popconfirm } from 'antd';
import { RollbackOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { KnowledgeSnapshot } from '../../api/rag-test/types';
import { formatDateTime, formatFileSize } from '../../utils/formatters';

interface SnapshotTableProps {
  snapshots: KnowledgeSnapshot[];
  loading: boolean;
  onRestore: (snapshotId: string) => void;
}

/**
 * 快照管理表格组件
 */
export const SnapshotTable: React.FC<SnapshotTableProps> = ({
  snapshots,
  loading,
  onRestore,
}) => {
  const columns: ColumnsType<KnowledgeSnapshot> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '文档数量',
      dataIndex: 'document_count',
      key: 'document_count',
      width: 100,
    },
    {
      title: '索引大小',
      dataIndex: 'index_size_bytes',
      key: 'index_size_bytes',
      width: 120,
      render: (bytes: number) => formatFileSize(bytes),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => formatDateTime(date),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Popconfirm
          title="确定要恢复到该快照吗？当前数据会被覆盖。"
          onConfirm={() => onRestore(record.id)}
          okText="确定"
          okType="danger"
          cancelText="取消"
        >
          <Button type="link" size="small" icon={<RollbackOutlined />}>
            恢复
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={snapshots}
      rowKey="id"
      loading={loading}
      pagination={{
        pageSize: 10,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 个快照`,
      }}
    />
  );
};
```

- [ ] **Step 4: 创建测试用例编辑弹窗组件**

```typescript
// frontend/src/components/rag-test/TestCaseModal.tsx

import React from 'react';
import { Modal, Form, Input, InputNumber } from 'antd';
import type { TestCase } from '../../api/rag-test/types';

interface TestCaseFormData {
  query: string;
  age: number;
  expected_keywords: string;
  description: string;
}

interface TestCaseModalProps {
  visible: boolean;
  editingCase: TestCase | null;
  form: any;
  onOk: () => void;
  onCancel: () => void;
}

/**
 * 测试用例编辑弹窗组件
 */
export const TestCaseModal: React.FC<TestCaseModalProps> = ({
  visible,
  editingCase,
  form,
  onOk,
  onCancel,
}) => {
  const { TextArea } = Input;

  return (
    <Modal
      title={editingCase ? '编辑测试用例' : '新建测试用例'}
      open={visible}
      onOk={onOk}
      onCancel={onCancel}
      width={600}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          age: 3,
          expected_keywords: '',
        }}
      >
        <Form.Item
          name="query"
          label="查询内容"
          rules={[{ required: true, message: '请输入查询内容' }]}
        >
          <TextArea
            rows={3}
            placeholder="例如：3岁儿童怕高怎么办？"
          />
        </Form.Item>

        <Form.Item
          name="age"
          label="儿童年龄"
          rules={[{ required: true, message: '请输入年龄' }]}
        >
          <InputNumber min={0} max={18} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          name="expected_keywords"
          label="预期关键词（多个用逗号分隔）"
          rules={[{ required: true, message: '请输入预期关键词' }]}
          help="检索结果中包含这些关键词则认为是相关结果"
        >
          <Input placeholder="例如：前庭觉, 平衡训练, 感统游戏" />
        </Form.Item>

        <Form.Item
          name="description"
          label="描述（可选）"
        >
          <TextArea rows={2} placeholder="测试用例的说明信息" />
        </Form.Item>
      </Form>
    </Modal>
  );
};
```

- [ ] **Step 5: 验证组件可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/components/rag-test/
git commit -m "feat(frontend): 拆分 RAG 测试组件（用例表格、运行表格、快照表格、编辑弹窗）"
```

---

## Chunk 3: 功能层重构

### Task 11: 重构评估功能模块

**Files:**
- Create: `frontend/src/features/assessment/hooks/useAssessment.ts`
- Create: `frontend/src/features/assessment/hooks/useAssessmentForm.ts`
- Create: `frontend/src/features/assessment/pages/HomePage.tsx`
- Create: `frontend/src/features/assessment/index.ts`

- [ ] **Step 1: 创建评估 Hook**

```typescript
// frontend/src/features/assessment/hooks/useAssessment.ts

import { useState, useCallback, useRef } from 'react';
import { assessDevelopment, assessDevelopmentStream } from '../../../api/assessment';
import type { UserInput, FinalReport, StreamingReportData } from '../../../models/assessment';

interface UseAssessmentReturn {
  report: FinalReport | null;
  loading: boolean;
  error: string | null;
  streamingContent: string;
  streamingData: StreamingReportData | null;
  submitAssessment: (data: UserInput, useStreaming?: boolean) => Promise<void>;
  resetAssessment: () => void;
}

/**
 * 评估业务逻辑 Hook
 */
export const useAssessment = (): UseAssessmentReturn => {
  const [report, setReport] = useState<FinalReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState<string>('');
  const [streamingData, setStreamingData] = useState<StreamingReportData | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const submitAssessment = useCallback(async (data: UserInput, useStreaming: boolean = true) => {
    setLoading(true);
    setError(null);
    setStreamingContent('');
    setStreamingData(null);
    setReport(null);

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    if (!useStreaming) {
      try {
        const result = await assessDevelopment(data);
        if (typeof result === 'string') {
          setReport({ markdown_content: result, structured_data: {} });
        } else {
          setReport(result);
        }
      } catch (err: any) {
        console.error(err);
        setError(err.response?.data?.detail || err.message || '发生错误，请重试');
      } finally {
        setLoading(false);
      }
      return;
    }

    try {
      abortControllerRef.current = new AbortController();

      await assessDevelopmentStream(
        data,
        (data) => {
          setStreamingData(data);
          setReport({
            markdown_content: '',
            structured_data: data,
          });
        },
        (chunk) => {
          setStreamingContent((prev) => prev + chunk);
          setReport((prev) => prev ? {
            ...prev,
            markdown_content: prev.markdown_content + chunk,
          } : {
            markdown_content: chunk,
            structured_data: {},
          });
        },
        () => {
          setLoading(false);
          abortControllerRef.current = null;
        },
        (errorMsg) => {
          setError(errorMsg);
          setLoading(false);
          abortControllerRef.current = null;
        }
      );
    } catch (err: any) {
      console.error(err);
      setError(err.message || '发生错误，请重试');
      setLoading(false);
      abortControllerRef.current = null;
    }
  }, []);

  const resetAssessment = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setReport(null);
    setError(null);
    setStreamingContent('');
    setStreamingData(null);
  }, []);

  return {
    report,
    loading,
    error,
    streamingContent,
    streamingData,
    submitAssessment,
    resetAssessment
  };
};
```

- [ ] **Step 2: 创建评估表单 Hook**

```typescript
// frontend/src/features/assessment/hooks/useAssessmentForm.ts

import type { UserInput } from '../../../models/assessment';

interface UseAssessmentFormReturn {
  initialValues: UserInput;
  handleFinish: (values: UserInput, onSubmit: (data: UserInput) => Promise<void>) => Promise<boolean>;
}

/**
 * 评估表单业务逻辑 Hook
 */
export const useAssessmentForm = (): UseAssessmentFormReturn => {
  const initialValues: UserInput = {
    child_profile: {
      name: '',
      age: 6,
      gender: 'male',
      issues: [],
      interests: []
    },
    proposed_plan: {
      plan_name: '感统训练计划 A',
      activities: [
        { name: '跳绳', duration_minutes: 10, frequency_weekly: 3, intensity: 'medium' }
      ],
      goals: ['提升协调性']
    }
  };

  const handleFinish = async (values: UserInput, onSubmit: (data: UserInput) => Promise<void>) => {
    const cleanValues = { ...values };
    if (!cleanValues.child_profile.issues) cleanValues.child_profile.issues = [];
    if (!cleanValues.child_profile.interests) cleanValues.child_profile.interests = [];
    if (!cleanValues.proposed_plan.goals) cleanValues.proposed_plan.goals = [];
    
    await onSubmit(cleanValues);
    return true;
  };

  return {
    initialValues,
    handleFinish
  };
};
```

- [ ] **Step 3: 创建评估首页**

```typescript
// frontend/src/features/assessment/pages/HomePage.tsx

import React from 'react';
import { useAssessment } from '../hooks/useAssessment';
import { AssessmentForm } from '../../../components/assessment/AssessmentForm';
import { ReportViewer } from '../../../components/assessment/ReportViewer';

/**
 * 评估首页
 */
export const HomePage: React.FC = () => {
  const { report, loading, error, submitAssessment, resetAssessment } = useAssessment();

  return (
    <>
      {error && (
        <div style={{ color: '#ff4d4f', marginBottom: 16, padding: '8px 16px', background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: '6px' }}>
          {error}
        </div>
      )}
      {report ? (
        <ReportViewer report={report} onBack={resetAssessment} isStreaming={loading} />
      ) : (
        <AssessmentForm onSubmit={submitAssessment} isLoading={loading} />
      )}
    </>
  );
};
```

- [ ] **Step 4: 创建模块导出**

```typescript
// frontend/src/features/assessment/index.ts

export { HomePage } from './pages/HomePage';
export { useAssessment } from './hooks/useAssessment';
export { useAssessmentForm } from './hooks/useAssessmentForm';
```

- [ ] **Step 5: 验证可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/features/assessment/
git commit -m "refactor(frontend): 重构评估功能模块，分离业务逻辑和 UI"
```

---

### Task 12: 重构文档管理功能模块

**Files:**
- Create: `frontend/src/features/documents/hooks/useDocumentManagement.ts`
- Create: `frontend/src/features/documents/pages/KnowledgeBasePage.tsx`
- Create: `frontend/src/features/documents/index.ts`

- [ ] **Step 1: 创建文档管理 Hook**

```typescript
// frontend/src/features/documents/hooks/useDocumentManagement.ts

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getDocuments,
  getRagStatus,
  getUploadTasks,
  cancelUploadTask,
} from '../../../api/documents';
import type { DocumentRecord, UploadTaskStatus, RagStatus } from '../../../api/documents/types';
import { POLLING_INTERVAL } from '../../../lib/constants';

interface UseDocumentManagementReturn {
  documents: DocumentRecord[];
  loading: boolean;
  ragStatus: RagStatus | null;
  processingTasks: UploadTaskStatus[];
  loadDocuments: () => Promise<void>;
  loadRagStatus: () => Promise<void>;
  handleCancel: (taskId: string) => Promise<void>;
}

/**
 * 文档管理业务逻辑 Hook
 */
export const useDocumentManagement = (): UseDocumentManagementReturn => {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [ragStatus, setRagStatus] = useState<RagStatus | null>(null);
  const [processingTasks, setProcessingTasks] = useState<UploadTaskStatus[]>([]);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getDocuments();
      setDocuments(res.documents);
    } catch (e) {
      console.error('Failed to load documents:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadRagStatus = useCallback(async () => {
    try {
      const res = await getRagStatus();
      setRagStatus(res);
    } catch (e) {
      // 忽略状态加载错误
    }
  }, []);

  const loadTasks = useCallback(async () => {
    try {
      const res = await getUploadTasks();
      const activeTasks = res.tasks.filter(t =>
        t.status === 'pending' ||
        t.status === 'processing' ||
        (t.status === 'cancelled' && (Date.now() / 1000 - t.created_at < 300)) ||
        (t.status === 'failed' && (Date.now() / 1000 - t.created_at < 3600)) ||
        (t.status === 'success' && (Date.now() / 1000 - t.created_at < 300))
      );
      setProcessingTasks(activeTasks);
    } catch (e) {
      console.error('Failed to load tasks:', e);
    }
  }, []);

  const handleCancel = useCallback(async (taskId: string) => {
    try {
      await cancelUploadTask(taskId);
      setProcessingTasks(prev => prev.map(t =>
        t.task_id === taskId ? { ...t, status: 'cancelled', message: '正在取消...' } : t
      ));
    } catch (e: any) {
      console.error('Cancel failed:', e);
      throw e;
    }
  }, []);

  // 初始加载
  useEffect(() => {
    loadDocuments();
    loadRagStatus();
    loadTasks();
  }, [loadDocuments, loadRagStatus, loadTasks]);

  // 轮询任务状态
  useEffect(() => {
    const hasActiveTasks = processingTasks.some(t =>
      t.status === 'pending' || t.status === 'processing' || t.status === 'cancelled'
    );

    if (hasActiveTasks && !pollingTimerRef.current) {
      pollingTimerRef.current = setInterval(async () => {
        try {
          const res = await getUploadTasks();
          const activeTasks = res.tasks.filter(t =>
            t.status === 'pending' ||
            t.status === 'processing' ||
            (t.status === 'cancelled' && (Date.now() / 1000 - t.created_at < 300)) ||
            (t.status === 'failed' && (Date.now() / 1000 - t.created_at < 3600))
          );

          // 检查已完成的任务
          processingTasks.forEach(oldTask => {
            const stillActive = activeTasks.find(t => t.task_id === oldTask.task_id);
            if (!stillActive && oldTask.status === 'processing') {
              getUploadTasks().then(res => {
                const completedTask = res.tasks.find(t => t.task_id === oldTask.task_id);
                if (completedTask && completedTask.status === 'success') {
                  loadDocuments();
                  loadRagStatus();
                }
              });
            }
          });

          setProcessingTasks(activeTasks);

          const hasActive = activeTasks.some(t =>
            t.status === 'pending' || t.status === 'processing' || t.status === 'cancelled'
          );
          if (!hasActive && pollingTimerRef.current) {
            clearInterval(pollingTimerRef.current);
            pollingTimerRef.current = null;
          }
        } catch (e) {
          console.error('Polling failed:', e);
        }
      }, POLLING_INTERVAL);
    }

    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [processingTasks, loadDocuments, loadRagStatus]);

  return {
    documents,
    loading,
    ragStatus,
    processingTasks,
    loadDocuments,
    loadRagStatus,
    handleCancel,
  };
};
```

- [ ] **Step 2: 创建知识库首页**

```typescript
// frontend/src/features/documents/pages/KnowledgeBasePage.tsx

import React, { useState, useCallback } from 'react';
import { Card, Typography, Space, App } from 'antd';
import { CloudSyncOutlined } from '@ant-design/icons';
import { useDocumentManagement } from '../hooks/useDocumentManagement';
import { DocumentUploader } from '../../../components/documents/DocumentUploader';
import { DocumentList } from '../../../components/documents/DocumentList';
import { TaskProgressList } from '../../../components/documents/TaskProgressList';
import type { UploadTaskStatus } from '../../../api/documents/types';
import styles from './KnowledgeBasePage.module.scss';

const { Title, Text } = Typography;

/**
 * 知识库管理首页
 */
const KnowledgeBasePage: React.FC = () => {
  const { modal, message } = App.useApp();
  const {
    documents,
    loading,
    ragStatus,
    processingTasks,
    loadDocuments,
    loadRagStatus,
    handleCancel,
  } = useDocumentManagement();

  const [uploading, setUploading] = useState(false);

  const handleUploadStart = useCallback((task: UploadTaskStatus) => {
    // 任务已在 DocumentUploader 中添加到列表
  }, []);

  const handleUploadSuccess = useCallback(async () => {
    await loadDocuments();
    await loadRagStatus();
  }, [loadDocuments, loadRagStatus]);

  const handleCancelTask = useCallback(async (taskId: string) => {
    try {
      await handleCancel(taskId);
      message.info('已请求取消任务...');
    } catch (e: any) {
      message.error(`取消失败: ${e.response?.data?.detail || e.message}`);
    }
  }, [handleCancel, message]);

  const processingFilenames = new Set(processingTasks.map(t => t.filename));

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2}>知识库管理</Title>
            <Text type="secondary">
              上传儿童发展相关的PDF或EPUB书籍，系统将自动构建知识索引，为评估提供科学依据。
            </Text>
          </div>

          <Space className={styles.statusBar}>
            <Space>
              <CloudSyncOutlined style={{ color: ragStatus?.index_ready ? '#52c41a' : '#faad14' }} />
              <Text strong={ragStatus?.index_ready} type={ragStatus?.index_ready ? 'success' : 'warning'}>
                {ragStatus?.index_ready ? '索引已就绪' : '索引未就绪，请上传文档'}
              </Text>
            </Space>
            <Text type="secondary">已上传文档: {documents.length} 个</Text>
          </Space>

          <DocumentUploader
            onUploadStart={handleUploadStart}
            onSuccess={handleUploadSuccess}
          />

          <TaskProgressList
            tasks={processingTasks}
            onCancel={handleCancelTask}
          />
        </Space>
      </Card>

      <Card
        title="文档列表"
        className={styles.listCard}
        extra={
          <Typography.Button
            onClick={loadDocuments}
            loading={loading}
            size="small"
          >
            刷新
          </Typography.Button>
        }
      >
        <DocumentList
          documents={documents}
          loading={loading}
          onRefresh={loadDocuments}
          excludeFilenames={processingFilenames}
        />
      </Card>
    </div>
  );
};

export default KnowledgeBasePage;
```

- [ ] **Step 3: 移动样式文件**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend/src
mv pages/KnowledgeBasePage.module.scss features/documents/pages/
```

- [ ] **Step 4: 创建模块导出**

```typescript
// frontend/src/features/documents/index.ts

export { default as KnowledgeBasePage } from './pages/KnowledgeBasePage';
export { useDocumentManagement } from './hooks/useDocumentManagement';
```

- [ ] **Step 5: 验证可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/features/documents/
git commit -m "refactor(frontend): 重构文档管理功能模块，分离业务逻辑和 UI"
```

---

### Task 13: 重构知识搜索功能模块

**Files:**
- Create: `frontend/src/features/knowledge/hooks/useKnowledgeSearch.ts`
- Create: `frontend/src/features/knowledge/pages/KnowledgeSearchPage.tsx`
- Create: `frontend/src/features/knowledge/index.ts`

- [ ] **Step 1: 创建知识搜索 Hook**

```typescript
// frontend/src/features/knowledge/hooks/useKnowledgeSearch.ts

import { useState, useCallback } from 'react';
import { searchKnowledge } from '../../../api/knowledge';
import type { SearchResultItem } from '../../../api/knowledge/types';

interface UseKnowledgeSearchReturn {
  query: string;
  results: SearchResultItem[];
  loading: boolean;
  total: number;
  handleSearch: (query: string) => Promise<void>;
  clearSearch: () => void;
}

/**
 * 知识搜索业务逻辑 Hook
 */
export const useKnowledgeSearch = (): UseKnowledgeSearchReturn => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  const handleSearch = useCallback(async (searchQuery: string) => {
    setQuery(searchQuery);
    
    if (!searchQuery.trim()) {
      setResults([]);
      setTotal(0);
      return;
    }

    try {
      setLoading(true);
      const response = await searchKnowledge(searchQuery, 20);
      setResults(response.results);
      setTotal(response.total);
    } catch (e: any) {
      console.error('Search failed:', e);
      setResults([]);
      setTotal(0);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearSearch = useCallback(() => {
    setQuery('');
    setResults([]);
    setTotal(0);
  }, []);

  return {
    query,
    results,
    loading,
    total,
    handleSearch,
    clearSearch,
  };
};
```

- [ ] **Step 2: 创建知识搜索首页**

```typescript
// frontend/src/features/knowledge/pages/KnowledgeSearchPage.tsx

import React, { useState } from 'react';
import { Card, Typography, Spin, App } from 'antd';
import { useKnowledgeSearch } from '../hooks/useKnowledgeSearch';
import { SearchInput } from '../../../components/knowledge/SearchInput';
import { SearchResultList } from '../../../components/knowledge/SearchResultList';
import { ResultDetailModal } from '../../../components/knowledge/ResultDetailModal';
import type { SearchResultItem } from '../../../api/knowledge/types';
import { usePagination } from '../../../hooks/usePagination';
import styles from './KnowledgeSearchPage.module.scss';

const { Title, Text } = Typography;

/**
 * 知识搜索首页
 */
const KnowledgeSearchPage: React.FC = () => {
  const { message } = App.useApp();
  const {
    query,
    results,
    loading,
    total,
    handleSearch,
  } = useKnowledgeSearch();

  const {
    currentPage,
    pageSize,
    setCurrentPage,
    setPageSize,
  } = usePagination({ initialPageSize: 10 });

  const [previewItem, setPreviewItem] = useState<SearchResultItem | null>(null);
  const [previewVisible, setPreviewVisible] = useState(false);

  const handleSearchWithError = async (searchQuery: string) => {
    try {
      await handleSearch(searchQuery);
    } catch (e: any) {
      message.error(`搜索失败: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handlePreview = (item: SearchResultItem) => {
    setPreviewItem(item);
    setPreviewVisible(true);
  };

  const paginatedResults = results.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <div>
          <Title level={2}>知识库搜索</Title>
          <Text type="secondary">
            搜索知识库中的内容，快速查找相关的知识点和文档片段。
          </Text>
        </div>

        <SearchInput
          onSearch={handleSearchWithError}
          resultCount={total}
        />
      </Card>

      <Card className={styles.contentCard}>
        <Spin spinning={loading}>
          <SearchResultList
            results={paginatedResults}
            loading={loading}
            query={query}
            total={total}
            currentPage={currentPage}
            pageSize={pageSize}
            onPageChange={(page, size) => {
              setCurrentPage(page);
              if (size) setPageSize(size);
            }}
            onPreview={handlePreview}
          />
        </Spin>
      </Card>

      <ResultDetailModal
        item={previewItem}
        visible={previewVisible}
        query={query}
        onClose={() => setPreviewVisible(false)}
      />
    </div>
  );
};

export default KnowledgeSearchPage;
```

- [ ] **Step 3: 移动样式文件**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend/src
mv pages/KnowledgeSearchPage.module.scss features/knowledge/pages/
```

- [ ] **Step 4: 创建模块导出**

```typescript
// frontend/src/features/knowledge/index.ts

export { default as KnowledgeSearchPage } from './pages/KnowledgeSearchPage';
export { useKnowledgeSearch } from './hooks/useKnowledgeSearch';
```

- [ ] **Step 5: 验证可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/features/knowledge/
git commit -m "refactor(frontend): 重构知识搜索功能模块，分离业务逻辑和 UI"
```

---

### Task 14: 重构 RAG 测试功能模块

**Files:**
- Create: `frontend/src/features/rag-test/hooks/useRagTest.ts`
- Create: `frontend/src/features/rag-test/pages/RagTestPage.tsx`
- Create: `frontend/src/features/rag-test/index.ts`

- [ ] **Step 1: 创建 RAG 测试 Hook**

```typescript
// frontend/src/features/rag-test/hooks/useRagTest.ts

import { useState, useEffect, useCallback } from 'react';
import {
  getTestCases,
  createTestCase,
  updateTestCase,
  deleteTestCase,
  runAllTests,
  runSingleTest,
  getTestRuns,
  createSnapshot,
  getSnapshots,
  restoreSnapshot,
} from '../../../api/rag-test';
import type { TestCase, TestRun, KnowledgeSnapshot, TestResult } from '../../../api/rag-test/types';

interface UseRagTestReturn {
  testCases: TestCase[];
  testRuns: TestRun[];
  snapshots: KnowledgeSnapshot[];
  loading: boolean;
  testRunning: boolean;
  loadTestCases: () => Promise<void>;
  loadTestRuns: () => Promise<void>;
  loadSnapshots: () => Promise<void>;
  handleAddCase: (caseData: Omit<TestCase, 'id' | 'created_at' | 'updated_at'>) => Promise<void>;
  handleUpdateCase: (caseId: string, caseData: Partial<TestCase>) => Promise<void>;
  handleDeleteCase: (id: string) => Promise<void>;
  handleRunSingleCase: (caseId: string) => Promise<TestResult>;
  handleRunAllTests: () => Promise<void>;
  handleCreateSnapshot: () => Promise<void>;
  handleRestoreSnapshot: (snapshotId: string) => Promise<void>;
}

/**
 * RAG 测试业务逻辑 Hook
 */
export const useRagTest = (): UseRagTestReturn => {
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [testRuns, setTestRuns] = useState<TestRun[]>([]);
  const [snapshots, setSnapshots] = useState<KnowledgeSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [testRunning, setTestRunning] = useState(false);

  const loadTestCases = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getTestCases();
      setTestCases(data);
    } catch (e) {
      console.error('Load test cases failed:', e);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTestRuns = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getTestRuns();
      setTestRuns(data);
    } catch (e) {
      console.error('Load test runs failed:', e);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSnapshots = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getSnapshots();
      setSnapshots(data);
    } catch (e) {
      console.error('Load snapshots failed:', e);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const handleAddCase = useCallback(async (caseData: Omit<TestCase, 'id' | 'created_at' | 'updated_at'>) => {
    await createTestCase(caseData);
    await loadTestCases();
  }, [loadTestCases]);

  const handleUpdateCase = useCallback(async (caseId: string, caseData: Partial<TestCase>) => {
    await updateTestCase(caseId, caseData);
    await loadTestCases();
  }, [loadTestCases]);

  const handleDeleteCase = useCallback(async (id: string) => {
    await deleteTestCase(id);
    await loadTestCases();
  }, [loadTestCases]);

  const handleRunSingleCase = useCallback(async (caseId: string): Promise<TestResult> => {
    try {
      setTestRunning(true);
      const result = await runSingleTest(caseId);
      return result.result;
    } finally {
      setTestRunning(false);
    }
  }, []);

  const handleRunAllTests = useCallback(async () => {
    try {
      setTestRunning(true);
      await runAllTests({
        name: `手动运行 - ${new Date().toLocaleString()}`,
        limit: 10
      });
      await loadTestRuns();
    } finally {
      setTestRunning(false);
    }
  }, [loadTestRuns]);

  const handleCreateSnapshot = useCallback(async () => {
    await createSnapshot({
      name: `快照 - ${new Date().toLocaleString()}`,
      description: '手动创建的快照'
    });
    await loadSnapshots();
  }, [loadSnapshots]);

  const handleRestoreSnapshot = useCallback(async (snapshotId: string) => {
    await restoreSnapshot(snapshotId);
    setTimeout(() => {
      loadTestCases();
      loadTestRuns();
      loadSnapshots();
    }, 2000);
  }, [loadTestCases, loadTestRuns, loadSnapshots]);

  useEffect(() => {
    loadTestCases();
    loadTestRuns();
    loadSnapshots();
  }, [loadTestCases, loadTestRuns, loadSnapshots]);

  return {
    testCases,
    testRuns,
    snapshots,
    loading,
    testRunning,
    loadTestCases,
    loadTestRuns,
    loadSnapshots,
    handleAddCase,
    handleUpdateCase,
    handleDeleteCase,
    handleRunSingleCase,
    handleRunAllTests,
    handleCreateSnapshot,
    handleRestoreSnapshot,
  };
};
```

- [ ] **Step 2: 创建 RAG 测试首页**

```typescript
// frontend/src/features/rag-test/pages/RagTestPage.tsx

import React, { useState } from 'react';
import { Card, Typography, Button, Space, Tabs, Statistic, Row, Col, Form, App } from 'antd';
import {
  PlusOutlined, PlayCircleOutlined, CameraOutlined,
  BarChartOutlined, HistoryOutlined
} from '@ant-design/icons';
import { useRagTest } from '../hooks/useRagTest';
import { TestCaseTable } from '../../../components/rag-test/TestCaseTable';
import { TestRunTable } from '../../../components/rag-test/TestRunTable';
import { SnapshotTable } from '../../../components/rag-test/SnapshotTable';
import { TestCaseModal } from '../../../components/rag-test/TestCaseModal';
import { useModal } from '../../../hooks/useModal';
import type { TestCase } from '../../../api/rag-test/types';
import styles from './RagTestPage.module.scss';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

interface TestCaseFormData {
  query: string;
  age: number;
  expected_keywords: string;
  description: string;
}

/**
 * RAG 测试首页
 */
const RagTestPage: React.FC = () => {
  const { modal, message } = App.useApp();
  const [activeTab, setActiveTab] = useState('cases');
  const [form] = Form.useForm<TestCaseFormData>();

  const {
    testCases,
    testRuns,
    snapshots,
    loading,
    testRunning,
    handleAddCase,
    handleUpdateCase,
    handleDeleteCase,
    handleRunSingleCase,
    handleRunAllTests,
    handleCreateSnapshot,
    handleRestoreSnapshot,
  } = useRagTest();

  const caseModal = useModal<TestCase>();

  const handleEditCase = (record: TestCase) => {
    form.setFieldsValue({
      query: record.query,
      age: record.age,
      expected_keywords: record.expected_keywords.join(', '),
      description: record.description
    });
    caseModal.open(record);
  };

  const handleCaseModalOk = async () => {
    try {
      const values = await form.validateFields();
      const caseData = {
        query: values.query,
        age: values.age,
        expected_keywords: values.expected_keywords.split(',').map(k => k.trim()).filter(k => k),
        expected_knowledge_ids: [],
        description: values.description
      };

      if (caseModal.data) {
        await handleUpdateCase(caseModal.data.id, caseData);
        message.success('更新成功');
      } else {
        await handleAddCase(caseData);
        message.success('创建成功');
      }

      caseModal.close();
      form.resetFields();
    } catch (e: any) {
      message.error(`保存失败: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleRunSingleCase = async (record: TestCase) => {
    try {
      const result = await handleRunSingleCase(record.id);
      message.success('测试执行完成');
      modal.info({
        title: '测试结果',
        width: 800,
        content: (
          <div>
            <Typography.Text>准确率: {(result.precision * 100).toFixed(2)}%</Typography.Text>
            <br />
            <Typography.Text>召回率: {(result.recall * 100).toFixed(2)}%</Typography.Text>
            <br />
            <Typography.Text>F1分数: {(result.f1_score * 100).toFixed(2)}%</Typography.Text>
          </div>
        )
      });
    } catch (e: any) {
      message.error(`测试执行失败: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleCreateSnapshotWithConfirm = async () => {
    modal.confirm({
      title: '创建快照',
      content: '确定要创建当前知识库的快照吗？',
      onOk: async () => {
        try {
          await handleCreateSnapshot();
          message.success('快照创建成功');
        } catch (e: any) {
          message.error(`快照创建失败: ${e.response?.data?.detail || e.message}`);
        }
      }
    });
  };

  const handleRestoreSnapshotWithConfirm = async (snapshotId: string) => {
    modal.confirm({
      title: '恢复快照',
      content: '确定要恢复到该快照吗？当前知识库的所有改动将会丢失。',
      okText: '确定恢复',
      okType: 'danger',
      onOk: async () => {
        try {
          await handleRestoreSnapshot(snapshotId);
          message.success('快照恢复已启动，后台处理中...');
        } catch (e: any) {
          message.error(`快照恢复失败: ${e.response?.data?.detail || e.message}`);
        }
      }
    });
  };

  const latestRun = testRuns[0];
  const passRate = latestRun
    ? (latestRun.passed_test_cases / latestRun.total_test_cases * 100)
    : 0;

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2}>知识库回撤测试</Title>
            <Text type="secondary">
              通过测试用例验证知识库变更的影响，确保检索质量稳定。
            </Text>
          </div>

          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                form.resetFields();
                caseModal.open();
              }}
            >
              新建测试用例
            </Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={handleRunAllTests}
              loading={testRunning}
              disabled={testCases.length === 0}
            >
              运行所有测试
            </Button>
            <Button
              icon={<CameraOutlined />}
              onClick={handleCreateSnapshotWithConfirm}
            >
              创建快照
            </Button>
          </Space>

          <Row gutter={16}>
            <Col span={6}>
              <Statistic
                title="测试用例总数"
                value={testCases.length}
                prefix={<HistoryOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="测试运行次数"
                value={testRuns.length}
                prefix={<BarChartOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="快照数量"
                value={snapshots.length}
                prefix={<CameraOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="最近通过率"
                value={passRate}
                suffix="%"
                precision={1}
                valueStyle={{ color: passRate >= 80 ? '#3f8600' : '#cf1322' }}
              />
            </Col>
          </Row>
        </Space>
      </Card>

      <Card className={styles.contentCard}>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="测试用例管理" key="cases">
            <TestCaseTable
              testCases={testCases}
              loading={loading}
              testRunning={testRunning}
              onAdd={() => {
                form.resetFields();
                caseModal.open();
              }}
              onEdit={handleEditCase}
              onDelete={handleDeleteCase}
              onRun={handleRunSingleCase}
            />
          </TabPane>
          <TabPane tab="测试运行记录" key="runs">
            <TestRunTable
              testRuns={testRuns}
              loading={loading}
            />
          </TabPane>
          <TabPane tab="快照管理" key="snapshots">
            <SnapshotTable
              snapshots={snapshots}
              loading={loading}
              onRestore={handleRestoreSnapshotWithConfirm}
            />
          </TabPane>
        </Tabs>
      </Card>

      <TestCaseModal
        visible={caseModal.isOpen}
        editingCase={caseModal.data}
        form={form}
        onOk={handleCaseModalOk}
        onCancel={caseModal.close}
      />
    </div>
  );
};

export default RagTestPage;
```

- [ ] **Step 3: 移动样式文件**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend/src
mv pages/RagTestPage.module.scss features/rag-test/pages/
```

- [ ] **Step 4: 创建模块导出**

```typescript
// frontend/src/features/rag-test/index.ts

export { default as RagTestPage } from './pages/RagTestPage';
export { useRagTest } from './hooks/useRagTest';
```

- [ ] **Step 5: 验证可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/features/rag-test/
git commit -m "refactor(frontend): 重构 RAG 测试功能模块，分离业务逻辑和 UI"
```

---

## Chunk 4: 路由和状态管理优化

### Task 15: 更新路由配置

**Files:**
- Modify: `frontend/src/router/index.tsx`

- [ ] **Step 1: 更新路由导入路径**

```typescript
// frontend/src/router/index.tsx

import { createBrowserRouter } from 'react-router-dom';
import App from '../App';
import { HomePage } from '../features/assessment';
import { KnowledgeBasePage } from '../features/documents';
import { RagTestPage } from '../features/rag-test';
import { KnowledgeSearchPage } from '../features/knowledge';
import BookChunksPage from '../pages/BookChunksPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'knowledge-base',
        element: <KnowledgeBasePage />,
      },
      {
        path: 'knowledge-search',
        element: <KnowledgeSearchPage />,
      },
      {
        path: 'rag-test',
        element: <RagTestPage />,
      },
      {
        path: 'book-chunks/:fileHash/:fileName',
        element: <BookChunksPage />,
      },
    ],
  },
]);
```

- [ ] **Step 2: 验证路由可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/router/
git commit -m "refactor(frontend): 更新路由配置，使用新的功能模块导入路径"
```

---

### Task 16: 优化状态管理

**Files:**
- Modify: `frontend/src/store/useChildStore.ts`
- Create: `frontend/src/store/uiStore.ts`

- [ ] **Step 1: 优化儿童信息 Store**

```typescript
// frontend/src/store/useChildStore.ts

import { create } from 'zustand';
import type { ChildProfile } from '../models/assessment';

interface ChildStore {
  currentProfile: ChildProfile | null;
  setProfile: (profile: ChildProfile) => void;
  clearProfile: () => void;
}

export const useChildStore = create<ChildStore>()((set) => ({
  currentProfile: null,
  setProfile: (profile) => set({ currentProfile: profile }),
  clearProfile: () => set({ currentProfile: null }),
}));
```

- [ ] **Step 2: 创建 UI 状态 Store**

```typescript
// frontend/src/store/uiStore.ts

import { create } from 'zustand';

interface UIState {
  // 侧边栏
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;

  // 主题
  theme: 'light' | 'dark';
  setTheme: (theme: 'light' | 'dark') => void;
}

/**
 * UI 状态管理 Store
 */
export const useUIStore = create<UIState>()((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  theme: 'light',
  setTheme: (theme) => set({ theme }),
}));
```

- [ ] **Step 3: 验证 Store 可编译**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/store/
git commit -m "feat(frontend): 优化状态管理，添加 UI 状态 Store"
```

---

### Task 17: 清理旧文件

**Files:**
- Delete: `frontend/src/pages/HomePage.tsx`
- Delete: `frontend/src/pages/KnowledgeBasePage.tsx`
- Delete: `frontend/src/pages/KnowledgeSearchPage.tsx`
- Delete: `frontend/src/pages/RagTestPage.tsx`
- Delete: `frontend/src/hooks/useAssessment.ts`
- Delete: `frontend/src/hooks/useAssessmentForm.ts`
- Delete: `frontend/src/api/client.ts` (旧版本，已被重构)

- [ ] **Step 1: 删除旧页面文件**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend/src

# 删除已迁移的页面
rm pages/HomePage.tsx
rm pages/KnowledgeBasePage.tsx
rm pages/KnowledgeSearchPage.tsx
rm pages/RagTestPage.tsx

# 删除已迁移的 hooks
rm hooks/useAssessment.ts
rm hooks/useAssessmentForm.ts
```

- [ ] **Step 2: 验证项目可构建**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npm run build
```

Expected: Build succeeds with no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/
git commit -m "chore(frontend): 清理已迁移的旧文件"
```

---

## Chunk 5: 性能优化和代码规范

### Task 18: 性能优化

**Files:**
- Modify: `frontend/src/lib/queryClient.ts`
- Create: `frontend/src/components/knowledge/SearchResultList.module.scss`

- [ ] **Step 1: 优化 React Query 配置**

```typescript
// frontend/src/lib/queryClient.ts

import { QueryClient } from '@tanstack/react-query';
import { CACHE_TIME } from './constants';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: CACHE_TIME.MEDIUM,
      gcTime: CACHE_TIME.LONG,
    },
    mutations: {
      retry: 0,
    },
  },
});
```

- [ ] **Step 2: 添加组件性能优化**

在关键组件中添加 `React.memo` 包装，例如：

```typescript
// 在 SearchResultList 等列表组件中添加
export const SearchResultList = React.memo(SearchResultListComponent);
```

- [ ] **Step 3: 验证构建**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npm run build
```

Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/src/
git commit -m "perf(frontend): 优化 React Query 配置和组件渲染性能"
```

---

### Task 19: 添加 ESLint 和 Prettier 配置

**Files:**
- Create: `frontend/.eslintrc.cjs`
- Create: `frontend/.prettierrc`
- Create: `frontend/.prettierignore`

- [ ] **Step 1: 创建 ESLint 配置**

```javascript
// frontend/.eslintrc.cjs

module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
  },
  plugins: ['@typescript-eslint', 'react-hooks'],
  rules: {
    'no-unused-vars': 'off',
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    '@typescript-eslint/no-explicit-any': 'warn',
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
  },
};
```

- [ ] **Step 2: 创建 Prettier 配置**

```json
// frontend/.prettierrc

{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": true,
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false,
  "bracketSpacing": true,
  "arrowParens": "always",
  "endOfLine": "lf"
}
```

- [ ] **Step 3: 创建 Prettier 忽略文件**

```
// frontend/.prettierignore

node_modules
dist
build
coverage
*.min.js
*.min.css
```

- [ ] **Step 4: 添加 npm scripts**

```json
// frontend/package.json (添加到 scripts 部分)

{
  "scripts": {
    "lint": "eslint src --ext .ts,.tsx --fix",
    "format": "prettier --write \"src/**/*.{ts,tsx,scss,css}\"",
    "typecheck": "tsc --noEmit"
  }
}
```

- [ ] **Step 5: 验证 Lint 和 Format**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent/frontend
npm run lint
npm run format
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
git add frontend/.eslintrc.cjs frontend/.prettierrc frontend/.prettierignore
git commit -m "chore(frontend): 添加 ESLint 和 Prettier 代码规范配置"
```

---

## 改造实施步骤总结

### 阶段一：基础设施层建设（Task 1-5）
**目标：** 建立新的目录结构、工具函数、共享 Hooks、拆分 API 层和 Models
**验收标准：**
- [ ] 新目录结构创建完成
- [ ] 全局常量和工具函数可编译
- [ ] 共享 Hooks 可编译
- [ ] API 层按领域拆分完成，向后兼容
- [ ] Models 按领域重组完成

### 阶段二：组件层重构（Task 6-10）
**目标：** 创建共享 UI 组件，按领域拆分业务组件
**验收标准：**
- [ ] 共享 UI 组件（ErrorBoundary、LoadingSpinner、EmptyState）创建完成
- [ ] 评估领域组件移动到正确目录
- [ ] 文档管理组件拆分完成（DocumentUploader、DocumentList、TaskProgressList）
- [ ] 知识搜索组件拆分完成（SearchInput、SearchResultList、ResultDetailModal）
- [ ] RAG 测试组件拆分完成（TestCaseTable、TestRunTable、SnapshotTable、TestCaseModal）

### 阶段三：功能层重构（Task 11-14）
**目标：** 按业务领域重构功能模块，分离业务逻辑和 UI
**验收标准：**
- [ ] 评估功能模块重构完成（HomePage + useAssessment + useAssessmentForm）
- [ ] 文档管理功能模块重构完成（KnowledgeBasePage + useDocumentManagement）
- [ ] 知识搜索功能模块重构完成（KnowledgeSearchPage + useKnowledgeSearch）
- [ ] RAG 测试功能模块重构完成（RagTestPage + useRagTest）

### 阶段四：路由和状态管理优化（Task 15-17）
**目标：** 更新路由配置，优化状态管理，清理旧文件
**验收标准：**
- [ ] 路由配置更新完成，使用新的导入路径
- [ ] 状态管理优化完成（useChildStore + useUIStore）
- [ ] 旧文件清理完成
- [ ] 项目构建成功

### 阶段五：性能优化和代码规范（Task 18-19）
**目标：** 优化性能，建立代码规范
**验收标准：**
- [ ] React Query 配置优化完成
- [ ] ESLint 和 Prettier 配置完成
- [ ] npm scripts 添加完成
- [ ] Lint 和 Format 检查通过

---

## 风险评估及应对策略

### 高风险

| 风险 | 影响 | 概率 | 应对策略 |
|------|------|------|----------|
| 重构过程中引入回归 bug | 功能不可用 | 中 | 1. 每个 Task 完成后立即验证编译和构建<br>2. 保持向后兼容的导出<br>3. 小步提交，便于回滚 |
| 类型定义不一致导致编译错误 | 无法构建 | 高 | 1. 先创建类型定义，再迁移代码<br>2. 使用 `tsc --noEmit` 频繁验证<br>3. 保留旧类型定义直到新类型完全就绪 |

### 中风险

| 风险 | 影响 | 概率 | 应对策略 |
|------|------|------|----------|
| 组件拆分后 props 传递复杂 | 代码可读性下降 | 中 | 1. 使用 Context 或 Zustand 管理共享状态<br>2. 保持组件接口简洁<br>3. 使用 TypeScript 严格类型检查 |
| API 层拆分后导入路径混乱 | 维护成本增加 | 低 | 1. 建立清晰的导入规范<br>2. 使用 barrel exports（index.ts）<br>3. 配置路径别名（可选） |

### 低风险

| 风险 | 影响 | 概率 | 应对策略 |
|------|------|------|----------|
| 样式文件迁移后样式丢失 | UI 异常 | 低 | 1. 迁移后手动验证每个页面<br>2. 保持样式文件路径相对关系 |
| 性能优化引入过度优化 | 代码复杂度增加 | 低 | 1. 只优化实际有性能问题的组件<br>2. 使用 React DevTools Profiler 验证 |

---

## 改造后预期收益

### 可维护性
- **代码定位时间减少 60%+**：按领域组织的目录结构，快速定位相关代码
- **修改影响范围清晰**：每个模块职责单一，修改影响范围可控
- **新人上手时间减少 50%+**：清晰的架构和命名规范

### 可扩展性
- **新功能开发效率提升 40%+**：遵循现有模式，快速添加新领域
- **组件复用率提升**：共享组件库减少重复代码
- **API 扩展简单**：按领域拆分，添加新 API 不影响现有代码

### 可测试性
- **单元测试覆盖率可达 80%+**：业务逻辑与 UI 分离，便于测试
- **Hooks 独立测试**：每个 Hook 可独立编写测试
- **组件测试简单**：纯 UI 组件，通过 props 控制状态

---

## 后续优化建议

1. **添加路径别名**：在 `tsconfig.json` 和 `vite.config.ts` 中配置 `@/` 别名，简化导入路径
2. **引入 React Query DevTools**：便于调试请求状态和缓存
3. **添加 E2E 测试**：使用 Playwright 或 Cypress 覆盖关键用户流程
4. **组件文档**：使用 Storybook 建立组件文档，便于团队协作
5. **性能监控**：集成 Web Vitals 监控关键性能指标
6. **错误监控**：集成 Sentry 或类似工具，实时捕获运行时错误