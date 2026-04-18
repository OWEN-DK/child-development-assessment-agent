/**
 * 导出 API 客户端
 */

import apiClient from '@shared/api/client';

export interface ExportTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  file_path: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExportCreateResponse {
  status: string;
  task_id: string;
  message: string;
}

export interface ExportStatusResponse {
  status: string;
  data: ExportTaskStatus;
}

/**
 * 创建异步 PDF 导出任务
 */
export const createExportTask = async (reportId: string): Promise<ExportCreateResponse> => {
  const response = await apiClient.post<ExportCreateResponse>(
    `/api/v1/rag/test/reports/${reportId}/export`
  );
  return response.data;
};

/**
 * 获取导出任务状态
 */
export const getExportStatus = async (taskId: string): Promise<ExportStatusResponse> => {
  const response = await apiClient.get<ExportStatusResponse>(
    `/api/v1/rag/test/exports/${taskId}/status`
  );
  return response.data;
};

/**
 * 下载导出文件
 */
export const downloadExport = async (taskId: string): Promise<void> => {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
  const response = await fetch(`${apiBaseUrl}/api/v1/rag/test/exports/${taskId}/download`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '下载失败' }));
    throw new Error(errorData.message || errorData.detail || '下载失败');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `rag_eval_report_${taskId.slice(0, 8)}.pdf`;
  a.click();
  window.URL.revokeObjectURL(url);
};
