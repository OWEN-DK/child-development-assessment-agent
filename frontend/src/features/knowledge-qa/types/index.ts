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

// ===== 运动类型推荐项（与后端 ExerciseTypeItem 一致） =====
export interface ExerciseTypeItem {
  type_id: string;          // ET001-ET999
  name: string;             // 运动名称，精确匹配权威运动清单
  tier: 'primary' | 'secondary' | 'supplementary';
  category: string;         // 运动分类（行走/跑步/力量训练/舞蹈…）
  target_problem_ids: string[];
  target_skills: string[];
  recommendation_rationale: string;
  citation_ids: string[];
}

// ===== S3 结构化数据 =====
export interface Section3StructuredData {
  exercise_types: ExerciseTypeItem[];
  child_age_group: string;
}

// ===== S4 结构化数据 =====
export interface Section4StructuredData {
  exercise_types: ExerciseTypeItem[];  // 方案中所有运动的扁平列表
  phases: Record<string, any>[];       // 阶段列表
  plan_summary: Record<string, any>;   // 方案摘要
  caution: string;                     // 注意事项
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
