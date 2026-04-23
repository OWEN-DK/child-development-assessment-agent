export interface DocumentRecord {
  file_hash: string;
  file_name: string;
  uploaded_at: string;
  total_pages: number;
}

export interface RagStatus {
  index_ready: boolean;
  storage_dir: string;
  document_count: number;
}

export interface UploadTaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  filename: string;
  created_at: number;
  message: string;
  error?: string;
  progress?: number;
  stage?: 'pending' | 'parsing' | 'chunking' | 'embedding' | 'indexing' | 'completed';
}

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

export interface DocumentChunk {
  id: string;
  content: string;
  metadata: ChunkMetadata;
  start_char_idx: number;
  end_char_idx: number;
  score?: number;
}

export interface ChunkDetail extends DocumentChunk {
  relationships?: any;
}
