import { useState, useEffect, useCallback, useRef } from 'react';
import type { BaseProgressTask, UseProgressPollingOptions, UseProgressPollingReturn } from '../types';

export function useProgressPolling<T extends BaseProgressTask>({
  fetchTasks,
  cancelTask,
  pollingInterval = 2000,
  onTaskComplete,
  onTaskFailed,
  onTaskCancelled,
}: UseProgressPollingOptions<T>): UseProgressPollingReturn<T> {
  const [tasks, setTasks] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const prevTasksRef = useRef<Map<string, T>>(new Map());

  // 刷新任务列表
  const refreshTasks = useCallback(async () => {
    try {
      setLoading(true);
      const newTasks = await fetchTasks();
      
      // 检测任务状态变化，触发回调
      const prevTasks = prevTasksRef.current;
      const currentTasksMap = new Map(newTasks.map(t => [t.taskId, t]));
      
      newTasks.forEach(task => {
        const prevTask = prevTasks.get(task.taskId);
        
        // 任务完成
        if (prevTask?.status !== 'completed' && task.status === 'completed') {
          onTaskComplete?.(task);
        }
        
        // 任务失败
        if (prevTask?.status !== 'failed' && task.status === 'failed') {
          onTaskFailed?.(task);
        }
        
        // 任务取消
        if (prevTask?.status !== 'cancelled' && task.status === 'cancelled') {
          onTaskCancelled?.(task);
        }
      });
      
      prevTasksRef.current = currentTasksMap;
      setTasks(newTasks);
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
    } finally {
      setLoading(false);
    }
  }, [fetchTasks, onTaskComplete, onTaskFailed, onTaskCancelled]);

  // 取消任务
  const handleCancelTask = useCallback(async (taskId: string) => {
    try {
      await cancelTask(taskId);
      // 立即从本地状态移除
      setTasks(prev => prev.filter(t => t.taskId !== taskId));
    } catch (error) {
      console.error('Failed to cancel task:', error);
      throw error;
    }
  }, [cancelTask]);

  // 移除任务（用于手动清理）
  const removeTask = useCallback((taskId: string) => {
    setTasks(prev => prev.filter(t => t.taskId !== taskId));
  }, []);

  // 初始加载
  useEffect(() => {
    refreshTasks();
  }, [refreshTasks]);

  // 轮询逻辑
  useEffect(() => {
    // 检查是否有活跃任务
    const hasActiveTasks = tasks.some(
      t => t.status === 'pending' || t.status === 'running'
    );

    if (hasActiveTasks && !pollingTimerRef.current) {
      pollingTimerRef.current = setInterval(() => {
        refreshTasks();
      }, pollingInterval);
    }

    // 清理定时器
    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [tasks, refreshTasks, pollingInterval]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
      }
    };
  }, []);

  return {
    tasks,
    loading,
    cancelTask: handleCancelTask,
    refreshTasks,
    removeTask,
  };
}
