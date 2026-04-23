import { useState, useEffect, useCallback, useRef } from 'react';
import { notification } from '@shared/lib/notification';
import {
  getDocuments,
  getRagStatus,
  getUploadTasks,
  cancelUploadTask,
} from '../../../api/documents';
import type { DocumentRecord, UploadTaskStatus, RagStatus } from '../../../api/documents/types';
import { API_BASE_URL } from '@shared/lib/constants';

interface UseDocumentManagementReturn {
  documents: DocumentRecord[];
  loading: boolean;
  ragStatus: RagStatus | null;
  processingTasks: UploadTaskStatus[];
  loadDocuments: () => Promise<void>;
  loadRagStatus: () => Promise<void>;
  loadTasks: () => Promise<void>;
  handleCancel: (taskId: string) => Promise<void>;
  addTask: (task: UploadTaskStatus) => void;
}

interface SSEConnection {
  eventSource: EventSource;
  taskId: string;
}

function buildSSEUrl(taskId: string): string {
  const base = API_BASE_URL.replace(/\/$/, '');
  return `${base}/api/v1/tasks/upload/${taskId}/stream`;
}

const ACTIVE_STATUS_FILTER = ['pending', 'running'] as const;

export const useDocumentManagement = (): UseDocumentManagementReturn => {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [ragStatus, setRagStatus] = useState<RagStatus | null>(null);
  const [processingTasks, setProcessingTasks] = useState<UploadTaskStatus[]>([]);
  const sseConnectionsRef = useRef<Map<string, SSEConnection>>(new Map());
  const callbacksRef = useRef({ loadDocuments: () => {}, loadRagStatus: () => {} });
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

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

  // 同步最新回调到 ref，供 SSE 闭包使用
  useEffect(() => {
    callbacksRef.current = { loadDocuments, loadRagStatus };
  }, [loadDocuments, loadRagStatus]);

  const closeSSE = useCallback((taskId: string) => {
    const conn = sseConnectionsRef.current.get(taskId);
    if (conn) {
      conn.eventSource.close();
      sseConnectionsRef.current.delete(taskId);
    }
  }, []);

  const connectSSE = useCallback((taskId: string) => {
    if (sseConnectionsRef.current.has(taskId)) {
      return;
    }

    const url = buildSSEUrl(taskId);
    const es = new EventSource(url);
    sseConnectionsRef.current.set(taskId, { eventSource: es, taskId });

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const eventType = data.type || data.event || 'message';

        setProcessingTasks(prev => {
          const taskIndex = prev.findIndex(t => t.task_id === taskId);
          if (taskIndex === -1) {
            return prev;
          }

          const updatedTasks = [...prev];
          const task = { ...updatedTasks[taskIndex] };

          if (eventType === 'progress') {
            task.status = data.status || 'running';
            task.progress = data.progress ?? task.progress;
            task.stage = data.stage || task.stage;
            task.message = data.message || task.message;
            updatedTasks[taskIndex] = task;
          } else if (eventType === 'complete') {
            // 立即从列表中移除（完成的任务不展示）
            const { loadDocuments: ld, loadRagStatus: lr } = callbacksRef.current;
            if (data.status === 'completed') {
              notification.success(`${task.filename} 上传并索引成功`);
              ld();
              lr();
            } else if (data.status === 'cancelled') {
              notification.info(`${task.filename} 已取消`);
              ld();
            }
            closeSSE(taskId);
            return prev.filter(t => t.task_id !== taskId);
          } else if (eventType === 'error') {
            // 立即从列表中移除（失败的任务不展示）
            closeSSE(taskId);
            notification.error(`${task.filename} 处理失败：${data.error || '未知错误'}`);
            return prev.filter(t => t.task_id !== taskId);
          }

          return updatedTasks;
        });
      } catch (e) {
        console.error('SSE message parse failed:', e);
      }
    };

    es.onerror = () => {
      console.error(`SSE connection error for task ${taskId}`);
      es.close();
      sseConnectionsRef.current.delete(taskId);
    };
  }, [closeSSE]);

  const filterActiveTasks = (tasks: UploadTaskStatus[]): UploadTaskStatus[] => {
    // 后端已经只返回活跃任务（pending/running），直接返回
    // 但需要处理 SSE 事件中的终态任务（completed/failed/cancelled）的短暂展示
    return tasks.filter(t => 
      ACTIVE_STATUS_FILTER.includes(t.status as typeof ACTIVE_STATUS_FILTER[number])
    );
  };

  const loadTasks = useCallback(async () => {
    try {
      const res = await getUploadTasks();
      const activeTasks = filterActiveTasks(res.tasks);
      
      // 去重：确保不会有重复的任务 ID
      const uniqueTasks = activeTasks.filter((task, index, self) =>
        index === self.findIndex(t => t.task_id === task.task_id)
      );
      
      setProcessingTasks(uniqueTasks);

      // 为 pending/running 任务建立 SSE 连接
      uniqueTasks.forEach(task => {
        if (ACTIVE_STATUS_FILTER.includes(task.status as typeof ACTIVE_STATUS_FILTER[number])) {
          connectSSE(task.task_id);
        }
      });

      // 如果有运行中的任务，启动轮询兜底（每 5 秒）
      const hasRunningTasks = uniqueTasks.some(t => 
        ACTIVE_STATUS_FILTER.includes(t.status as typeof ACTIVE_STATUS_FILTER[number])
      );
      
      if (hasRunningTasks && !pollingIntervalRef.current) {
        pollingIntervalRef.current = setInterval(async () => {
          try {
            const res = await getUploadTasks();
            const activeTasks = filterActiveTasks(res.tasks);
            // 轮询时也去重
            const uniqueTasks = activeTasks.filter((task, index, self) =>
              index === self.findIndex(t => t.task_id === task.task_id)
            );
            setProcessingTasks(uniqueTasks);
          } catch (e) {
            console.error('Polling failed:', e);
          }
        }, 5000);
      } else if (!hasRunningTasks && pollingIntervalRef.current) {
        // 没有运行中的任务，停止轮询
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    } catch (e) {
      console.error('Failed to load tasks:', e);
    }
  }, [connectSSE]);

  const handleCancel = useCallback(async (taskId: string) => {
    try {
      await cancelUploadTask(taskId);
      closeSSE(taskId);
      setProcessingTasks(prev => prev.filter(t => t.task_id !== taskId));
    } catch (e) {
      console.error('Cancel failed:', e);
      throw e;
    }
  }, [closeSSE]);

  const addTask = useCallback((task: UploadTaskStatus) => {
    setProcessingTasks(prev => {
      const exists = prev.find(t => t.task_id === task.task_id);
      if (exists) {
        return prev.map(t => t.task_id === task.task_id ? task : t);
      }
      return [...prev, task];
    });

    if (ACTIVE_STATUS_FILTER.includes(task.status as typeof ACTIVE_STATUS_FILTER[number])) {
      connectSSE(task.task_id);
    }
  }, [connectSSE]);

  useEffect(() => {
    loadDocuments();
    loadRagStatus();
    loadTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 只在组件挂载时执行一次，避免依赖循环导致重复加载

  useEffect(() => {
    return () => {
      // 清理 SSE 连接
      sseConnectionsRef.current.forEach(conn => {
        conn.eventSource.close();
      });
      sseConnectionsRef.current.clear();
      
      // 清理轮询定时器
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, []);

  return {
    documents,
    loading,
    ragStatus,
    processingTasks,
    loadDocuments,
    loadRagStatus,
    loadTasks,
    handleCancel,
    addTask,
  };
};
