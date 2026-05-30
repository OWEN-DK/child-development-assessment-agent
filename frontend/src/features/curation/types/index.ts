/** 知识审核类型定义 */

/* ===== 书籍 ===== */
export interface CurationBook {
  id: string;
  book_id: string;
  book_title: string;
  author?: string;
  status: 'draft' | 'reviewed' | 'published' | 'generating' | 'failed';
  version: number;
  total_entities: number;
  total_claims: number;
  total_prescriptions: number;
  neo4j_synced: boolean;
  bind_source?: 'kb_bind' | 'direct';
  reviewed_by?: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CurationBookListResponse {
  books: CurationBook[];
  total: number;
  page: number;
  page_size: number;
}

/* ===== 草稿 ===== */
export interface DraftItem {
  id: string;
  book_id: string;
  book_title: string;
  status: 'draft' | 'reviewed' | 'published';
  version: number;
  generated_at: string | null;
  reviewed_by: string | null;
  total_entities?: number;
  total_claims?: number;
  total_prescriptions?: number;
}

export interface DraftDetail extends DraftItem {
  content: string;
  reviewed_at: string | null;
}

export interface DraftListResponse {
  drafts: DraftItem[];
  page: number;
  page_size: number;
}

/* ===== 知识图谱 ===== */
export interface KGNode {
  id: string;
  label: string;
  type: string;
  description: string;
  book_id?: string;
  confirmed?: boolean;
  severity?: string;
  category?: string;
  brain_regions?: string[];
  evidence?: string;
  key_figures?: string;
  mechanism_detail?: string;
  connected_nodes?: { id: string; label: string; type: string; relation: string }[];
}

export interface KGEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
  label?: string;
  evidence?: string;
  confidence?: string;
}

export interface KGData {
  nodes: KGNode[];
  edges: KGEdge[];
}

/* ===== 待提炼队列 ===== */
export interface PendingItem {
  id: string;
  book_id?: string;
  entity_name?: string;
  entity_type?: string;
  topic?: string;
  reason?: string;
  source_books?: string[];
  status: string;
  created_at: string;
}

/* ===== 知识库书籍 (用于绑定) ===== */
export interface KBBook {
  id: string;
  title: string;
  author?: string;
  file_type: string;
  file_hash: string;
  chapter_count?: number;
  status: string;
  created_at: string;
  bound: boolean; // 是否已绑定到策管
}

export interface KBBookListResponse {
  books: KBBook[];
  total: number;
}

/* ===== 绑定请求 ===== */
export interface BindBookRequest {
  kb_book_id: string;
  book_title: string;
  author?: string;
}

/* ===== 生成进度 ===== */
export interface GenerateProgress {
  book_id: string;
  book_title: string;
  status: 'pending' | 'generating' | 'completed' | 'failed';
  total_chapters: number;
  completed_chapters: number;
  current_chapter?: string;
  error?: string;
}

/* ===== 章节 ===== */
export interface ChapterInfo {
  index: number;
  title: string;
  token_count: number;
  selected: boolean;
  over_threshold: boolean;
}

/* ===== 实体 ===== */
export interface EntityItem {
  name: string;
  type: string;
  confirmed: boolean;
  chapter?: string;
  count?: number;
}


/** 生成聚合摘要 */
export interface GenerationSummary {
  total_chapters: number;
  success_chapters: number;
  failed_chapters: string[];
  entities: { type: string; count: number }[];
  contradictions: { description: string; chapter_a: string; chapter_b: string }[];
}
