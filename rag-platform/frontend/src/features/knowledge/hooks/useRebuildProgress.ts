/**
 * 重建进度 SSE 订阅 Hook
 *
 * 订阅知识库重建进度 SSE 流，自动管理连接生命周期
 */
import { useEffect, useRef } from 'react'
import { useKnowledgeBaseStore } from '@/features/knowledge/stores/knowledgeBaseStore'

/** 使用重建进度的 Hook */
export function useRebuildProgress(kbId: string | undefined) {
  const unsubscribeRef = useRef<(() => void) | null>(null)
  const rebuildStatus = useKnowledgeBaseStore((s) => s.rebuildStatus)
  const recentRebuildTasks = useKnowledgeBaseStore((s) => s.recentRebuildTasks)
  const subscribeRebuildProgress = useKnowledgeBaseStore((s) => s.subscribeRebuildProgress)
  const clearRebuildStatus = useKnowledgeBaseStore((s) => s.clearRebuildStatus)

  useEffect(() => {
    if (!kbId) return

    // 如果有正在运行的重建任务，订阅进度
    const currentTask = useKnowledgeBaseStore.getState().rebuildStatus
    if (currentTask && currentTask.status === 'running') {
      unsubscribeRef.current = subscribeRebuildProgress(kbId)
    }

    return () => {
      // 组件卸载时关闭 SSE 连接
      unsubscribeRef.current?.()
      unsubscribeRef.current = null
    }
  }, [kbId, subscribeRebuildProgress])

  /** 手动订阅重建进度 */
  const startSubscription = () => {
    if (!kbId) return
    // 先关闭旧连接
    unsubscribeRef.current?.()
    unsubscribeRef.current = subscribeRebuildProgress(kbId)
  }

  /** 清除重建状态 */
  const cleanup = () => {
    unsubscribeRef.current?.()
    unsubscribeRef.current = null
    clearRebuildStatus()
  }

  return {
    rebuildStatus,
    recentRebuildTasks,
    isRebuilding: rebuildStatus?.status === 'running',
    startSubscription,
    cleanup,
  }
}
