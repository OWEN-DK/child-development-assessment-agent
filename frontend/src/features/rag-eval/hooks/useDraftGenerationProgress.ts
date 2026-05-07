/**
 * 基于 Zustand store 的草稿生成进度管理
 *
 * 状态持久化到 draftGenerationStore（跨组件生命周期），
 * SSE 连接在组件卸载时断开但 task 状态保留，重挂载时自动重连。
 * localStorage 不再需要，Zustand store 在模块作用域存活。
 */

import { useCallback, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useDraftGenerationStore } from '../stores/draftGenerationStore';
import { apiClient } from '@shared/api/client';

export function useDraftGenerationProgress() {
  const qc = useQueryClient();

  const tasks = useDraftGenerationStore(s => s.tasks);
  const startTracking = useDraftGenerationStore(s => s.startTracking);
  const removeTask = useDraftGenerationStore(s => s.removeTask);
  const onMount = useDraftGenerationStore(s => s.onMount);
  const onUnmount = useDraftGenerationStore(s => s.onUnmount);

  /** 取消草稿生成任务（调用后端 cancel API + 清理前端状态） */
  const cancelTask = useCallback(async (taskId: string) => {
    try {
      await apiClient.post(`/api/v1/tasks/draft_generation/${taskId}/cancel`);
    } catch {
      // 即使后端取消失败（如任务已进入终态），也清理前端状态
    }
    removeTask(taskId);
  }, [removeTask]);

  /** 生成完成后刷新列表并延迟移除 task */
  useEffect(() => {
    const completedTasks = tasks.filter(t => t.status === 'completed');
    if (completedTasks.length === 0) return;

    qc.invalidateQueries({ queryKey: ['rag-eval', 'drafts'] });

    const timers = completedTasks.map(t =>
      setTimeout(() => removeTask(t.taskId), 5000),
    );
    return () => timers.forEach(clearTimeout);
  }, [tasks, qc, removeTask]);

  // 挂载/卸载生命周期管理
  useEffect(() => {
    onMount();
    return onUnmount;
  }, [onMount, onUnmount]);

  return { tasks, startTracking, removeTask, cancelTask };
}
