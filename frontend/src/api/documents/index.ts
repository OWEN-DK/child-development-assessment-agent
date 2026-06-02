import apiClient from '@shared/api/client';
import type { 
  DocumentRecord, 
  RagStatus, 
  UploadTaskStatus, 
  DocumentChunk, 
  ChunkDetail 
} from './types';

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

export const getRagStatus = async (): Promise<RagStatus> => {
  const response = await apiClient.get<RagStatus>('/rag/status');
  return response.data;
};

export const getDocuments = async (): Promise<{ documents: DocumentRecord[] }> => {
  const response = await apiClient.get<{ documents: DocumentRecord[] }>('/rag/documents');
  return response.data;
};

export interface DocumentBindings {
  book_id: string;
  graph_ready: boolean;
  bindings: {
    entities: number;
    relations: number;
    communities: number;
    total: number;
  };
  has_bindings: boolean;
}

export const getDocumentBindings = async (filename: string): Promise<DocumentBindings> => {
  const response = await apiClient.get(`/rag/documents/${encodeURIComponent(filename)}/bindings`);
  return response.data;
};

export const deleteDocument = async (filename: string, cascade: boolean = false): Promise<{ status: string; message: string }> => {
  const response = await apiClient.delete(`/rag/documents/${encodeURIComponent(filename)}`, {
    params: cascade ? { cascade: true } : undefined,
  });
  return response.data;
};

export const deleteTask = async (taskId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.delete(`/rag/tasks/${encodeURIComponent(taskId)}`);
  return response.data;
};

export const getUploadTaskStatus = async (taskId: string): Promise<UploadTaskStatus> => {
  const response = await apiClient.get<UploadTaskStatus>(`/rag/tasks/${taskId}`);
  return response.data;
};

export const getUploadTasks = async (): Promise<{ tasks: UploadTaskStatus[] }> => {
  const response = await apiClient.get<{ tasks: UploadTaskStatus[] }>('/rag/tasks');
  return response.data;
};

export const cancelUploadTask = async (taskId: string): Promise<{ status: string; message: string }> => {
  const response = await apiClient.post<{ status: string; message: string }>(`/rag/tasks/${taskId}/cancel`);
  return response.data;
};

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

export const getChunkDetail = async (chunkId: string): Promise<{ 
  status: string; 
  chunk: ChunkDetail 
}> => {
  const response = await apiClient.get(`/rag/chunks/${encodeURIComponent(chunkId)}`);
  return response.data;
};
