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
