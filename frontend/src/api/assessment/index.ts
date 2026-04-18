import apiClient from '@shared/api/client';
import type { UserInput, FinalReport, LayeredProgressStatus } from './types';
import type { StreamingReportData } from '@entities/assessment/types';

export const assessDevelopment = async (data: UserInput): Promise<FinalReport> => {
  const response = await apiClient.post<FinalReport>('/assess', { ...data, is_streaming: false });
  return response.data;
};

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

export const getLayeredProgress = async (taskId: string): Promise<LayeredProgressStatus> => {
  const response = await apiClient.get<LayeredProgressStatus>(`/rag/layered-progress/${taskId}`);
  return response.data;
};

export const getAllLayeredProgress = async (): Promise<{ tasks: LayeredProgressStatus[] }> => {
  const response = await apiClient.get<{ tasks: LayeredProgressStatus[] }>('/rag/layered-progress');
  return response.data;
};
