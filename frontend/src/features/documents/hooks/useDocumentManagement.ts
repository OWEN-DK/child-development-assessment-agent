import { useState, useEffect, useCallback, useRef } from 'react';
import { App } from 'antd';
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
  addTask: (task: UploadTaskStatus) => void;
}

export const useDocumentManagement = (): UseDocumentManagementReturn => {
  const { message } = App.useApp();
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
        (t.status === 'success' && (Date.now() / 1000 - t.created_at < 5))
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

  const addTask = useCallback((task: UploadTaskStatus) => {
    setProcessingTasks(prev => {
      const exists = prev.find(t => t.task_id === task.task_id);
      if (exists) {
        return prev.map(t => t.task_id === task.task_id ? task : t);
      }
      return [...prev, task];
    });
  }, []);

  useEffect(() => {
    loadDocuments();
    loadRagStatus();
    loadTasks();
  }, [loadDocuments, loadRagStatus, loadTasks]);

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
            (t.status === 'failed' && (Date.now() / 1000 - t.created_at < 3600)) ||
            (t.status === 'success' && (Date.now() / 1000 - t.created_at < 5))
          );

          processingTasks.forEach(oldTask => {
            const stillActive = activeTasks.find(t => t.task_id === oldTask.task_id);
            if (!stillActive && oldTask.status === 'processing') {
              getUploadTasks().then(res => {
                const completedTask = res.tasks.find(t => t.task_id === oldTask.task_id);
                if (completedTask && completedTask.status === 'success') {
                  message.success(`${completedTask.filename} 上传并索引成功`);
                  loadDocuments();
                  loadRagStatus();
                } else if (completedTask && completedTask.status === 'failed') {
                  message.error(`${completedTask.filename} 处理失败：${completedTask.error || '未知错误'}`);
                }
              });
            } else if (!stillActive && oldTask.status === 'cancelled') {
              message.info(`${oldTask.filename} 已取消`);
              loadDocuments();
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
    addTask,
  };
};
