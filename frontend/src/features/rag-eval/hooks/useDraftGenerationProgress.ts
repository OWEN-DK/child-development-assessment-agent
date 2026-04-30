import { useState, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { createSSEConnection } from '../utils/sse';
import type { DraftGenerationTask } from '../../../components/progress/configs/draftGeneration';

/** SSE 各阶段对应进度百分比（流水线化后的新阶段分布） */
const STAGE_PROGRESS: Record<string, number> = {
  generation_started: 5,
  metadata_analyzed: 15,
  pipeline_running: 20,     // 20-85%，动态由 metadata.pct 驱动
  drafts_generated: 85,
  faithfulness_checked: 88,
  deduplication_completed: 90,
};

/**
 * 基于 SSE 的草稿生成进度管理
 *
 * 后端生成与忠诚度检查已流水线化，pipeline_running 阶段同时覆盖
 * 生成和校验进度，通过 metadata.pct 提供动态百分比。
 */
export function useDraftGenerationProgress() {
  const [tasks, setTasks] = useState<DraftGenerationTask[]>([]);
  const abortControllers = useRef<Map<string, AbortController>>(new Map());
  const qc = useQueryClient();

  const startTracking = useCallback((taskId: string, documentName?: string) => {
    const now = Date.now();
    const task: DraftGenerationTask = {
      taskId,
      status: 'pending',
      progress: 0,
      message: '等待开始...',
      createdAt: now,
      documentName,
    };

    setTasks(prev => [...prev, task]);

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
                  // 流水线阶段使用后端动态百分比 (20-85%)
                  progress = evt.metadata.pct;
                } else {
                  progress = stage ? (STAGE_PROGRESS[stage] ?? t.progress) : t.progress;
                }

                return { ...t, status: 'running', progress, message };
              }

              if (evt.type === 'complete') {
                const result = evt.result as { saved_count?: number; skipped?: number } | undefined;
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
        },
      },
    );
  }, [qc]);

  const removeTask = useCallback((taskId: string) => {
    const ac = abortControllers.current.get(taskId);
    ac?.abort();
    abortControllers.current.delete(taskId);
    setTasks(prev => prev.filter(t => t.taskId !== taskId));
  }, []);

  return { tasks, startTracking, removeTask };
}
