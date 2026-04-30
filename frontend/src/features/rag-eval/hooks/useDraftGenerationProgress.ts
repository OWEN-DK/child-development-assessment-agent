import { useState, useCallback, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { createSSEConnection } from '../utils/sse';
import type { DraftGenerationTask } from '../../../components/progress/configs/draftGeneration';

/** localStorage 存储键 */
const STORAGE_KEY = 'draft-generation-active-tasks';

/** SSE 各阶段对应进度百分比（流水线化后的新阶段分布） */
const STAGE_PROGRESS: Record<string, number> = {
  generation_started: 5,
  metadata_analyzed: 15,
  pipeline_running: 20,     // 20-85%，动态由 metadata.pct 驱动
  drafts_generated: 85,
  faithfulness_checked: 88,
  deduplication_completed: 90,
};

/** 从 localStorage 读取活跃的 batch_id 列表 */
function loadActiveTaskIds(): Array<{ taskId: string; documentName?: string }> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

/** 持久化活跃的 batch_id 列表到 localStorage */
function saveActiveTaskIds(entries: Array<{ taskId: string; documentName?: string }>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
}

/**
 * 基于 SSE 的草稿生成进度管理
 *
 * 后端生成与忠诚度检查已流水线化，pipeline_running 阶段同时覆盖
 * 生成和校验进度，通过 metadata.pct 提供动态百分比。
 *
 * 支持页面刷新后恢复：通过 localStorage 持久化活跃的 batch_id，
 * 挂载时自动重新建立 SSE 连接。
 */
export function useDraftGenerationProgress() {
  const [tasks, setTasks] = useState<DraftGenerationTask[]>([]);
  const abortControllers = useRef<Map<string, AbortController>>(new Map());
  const qc = useQueryClient();
  const initialized = useRef(false);

  /** 建立 SSE 连接并跟踪指定 taskId 的进度 */
  const trackTask = useCallback((taskId: string, documentName?: string) => {
    const now = Date.now();
    const task: DraftGenerationTask = {
      taskId,
      status: 'pending',
      progress: 0,
      message: '等待开始...',
      createdAt: now,
      documentName,
    };

    setTasks(prev => {
      // 避免重复跟踪
      if (prev.some(t => t.taskId === taskId)) return prev;
      return [...prev, task];
    });

    const abortController = new AbortController();
    abortControllers.current.set(taskId, abortController);

    createSSEConnection(
      `/api/v1/rag/eval/drafts/generation/${taskId}/stream`,
      abortController.signal,
      {
        onOpen: () => {
          setTasks(prev => prev.map(t =>
            t.taskId === taskId ? { ...t, status: 'running', message: '已连接' } : t,
          ));
        },
        onMessage: (raw) => {
          try {
            const evt = JSON.parse(raw);
            setTasks(prev => prev.map(t => {
              if (t.taskId !== taskId) return t;

              if (evt.type === 'progress') {
                const stage = evt.stage as string | undefined;
                const message = (evt.message as string) ?? stage ?? t.message;
                let progress: number;

                if (stage === 'pipeline_running' && typeof evt.metadata?.pct === 'number') {
                  progress = evt.metadata.pct;
                } else {
                  progress = stage ? (STAGE_PROGRESS[stage] ?? t.progress) : t.progress;
                }

                return { ...t, status: 'running', progress, message };
              }

              if (evt.type === 'complete') {
                const result = evt.result as { saved_count?: number; skipped?: number } | undefined;
                // 完成后从 localStorage 移除
                const active = loadActiveTaskIds().filter(e => e.taskId !== taskId);
                saveActiveTaskIds(active);
                setTimeout(() => {
                  setTasks(prev => prev.filter(tt => tt.taskId !== taskId));
                  qc.invalidateQueries({ queryKey: ['rag-eval', 'drafts'] });
                }, 5000);
                return {
                  ...t,
                  status: 'completed' as const,
                  progress: 100,
                  message: (evt.message as string) ?? '生成完成',
                  generated: result?.saved_count,
                  skipped: result?.skipped,
                };
              }

              if (evt.type === 'error') {
                // 失败也从 localStorage 移除
                const active = loadActiveTaskIds().filter(e => e.taskId !== taskId);
                saveActiveTaskIds(active);
                return {
                  ...t,
                  status: 'failed' as const,
                  error: (evt.error as string) ?? '生成失败',
                  message: (evt.message as string) ?? '生成失败',
                };
              }

              return t;
            }));
          } catch {
            // 忽略解析异常
          }
        },
        onError: () => {
          setTasks(prev => prev.map(t =>
            t.taskId === taskId ? { ...t, status: 'failed', error: 'SSE 连接异常' } : t,
          ));
          // 连接异常也移除，避免无限重连
          const active = loadActiveTaskIds().filter(e => e.taskId !== taskId);
          saveActiveTaskIds(active);
        },
      },
    );
  }, [qc]);

  /** 用户触发生成后调用，开始跟踪并持久化 */
  const startTracking = useCallback((taskId: string, documentName?: string) => {
    // 持久化到 localStorage
    const active = loadActiveTaskIds();
    if (!active.some(e => e.taskId === taskId)) {
      active.push({ taskId, documentName });
      saveActiveTaskIds(active);
    }
    trackTask(taskId, documentName);
  }, [trackTask]);

  const removeTask = useCallback((taskId: string) => {
    const ac = abortControllers.current.get(taskId);
    ac?.abort();
    abortControllers.current.delete(taskId);
    setTasks(prev => prev.filter(t => t.taskId !== taskId));
    // 同步清理 localStorage
    const active = loadActiveTaskIds().filter(e => e.taskId !== taskId);
    saveActiveTaskIds(active);
  }, []);

  // 挂载时从 localStorage 恢复未完成的任务
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const active = loadActiveTaskIds();
    for (const entry of active) {
      trackTask(entry.taskId, entry.documentName);
    }
  }, [trackTask]);

  // 卸载时清理所有 SSE 连接
  useEffect(() => {
    return () => {
      abortControllers.current.forEach(ac => ac.abort());
      abortControllers.current.clear();
    };
  }, []);

  return { tasks, startTracking, removeTask };
}
