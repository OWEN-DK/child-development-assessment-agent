/** 知识问答类型定义 */

export interface MatchedBook {
  book_id: string;
  title: string;
  author: string | null;
  source_type: 'book' | 'paper' | 'guideline' | 'manual';
  match_reason: string;
  is_primary: boolean;
}

export interface Citation {
  citation_id: string;
  book_title: string;
  source_type: string;
  chapter: string;
  section: string | null;
  page: string | null;
  excerpt: string;
  relevance: string;
}

export interface SectionOutput {
  index: number;
  title: string;
  content: string;
  citations: Citation[];
  structured_data: Record<string, any>;
}

export interface GenerationMetadata {
  total_sections: number;
  total_citations: number;
  total_time_ms: number;
  model_used: string;
  review_model_used: string;
  retries: Record<string, number>;
  partial: boolean;
}

export interface KnowledgeQAResponse {
  question: string;
  matched_books: MatchedBook[];
  sections: SectionOutput[];
  generation_metadata: GenerationMetadata;
}

export interface ProgressState {
  step: string;
  message: string;
  status: 'running' | 'completed' | 'failed' | 'timeout';
  metadata?: Record<string, any>;
}

export type QAStatus = 'idle' | 'submitting' | 'streaming' | 'done' | 'error';
