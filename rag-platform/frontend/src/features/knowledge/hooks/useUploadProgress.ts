/**
 * 上传进度追踪 Hook
 *
 * 管理文件上传的进度状态、去重检测和错误处理
 */
import { useCallback } from 'react'
import { useKnowledgeBaseStore } from '@/features/knowledge/stores/knowledgeBaseStore'
import type { UploadProgressItem } from '@/entities/knowledge/types'

/** 使用上传进度的 Hook */
export function useUploadProgress() {
  const uploadProgress = useKnowledgeBaseStore((s) => s.uploadProgress)
  const uploadDocuments = useKnowledgeBaseStore((s) => s.uploadDocuments)

  /** 上传状态统计 */
  const stats = useCallback(() => {
    const items = useKnowledgeBaseStore.getState().uploadProgress
    return {
      total: items.length,
      completed: items.filter((i) => i.status === 'done').length,
      duplicated: items.filter((i) => i.status === 'duplicate').length,
      errored: items.filter((i) => i.status === 'error').length,
      uploading: items.filter((i) => i.status === 'uploading' || i.status === 'pending').length,
    }
  }, [])

  /** 是否全部完成（成功或失败） */
  const allDone = uploadProgress.length > 0 && uploadProgress.every(
    (i) => i.status === 'done' || i.status === 'duplicate' || i.status === 'error'
  )

  /** 清除已完成的进度项 */
  const clearCompleted = useCallback(() => {
    const store = useKnowledgeBaseStore.getState()
    const remaining = store.uploadProgress.filter(
      (i: UploadProgressItem) => i.status === 'uploading' || i.status === 'pending'
    )
    useKnowledgeBaseStore.setState({ uploadProgress: remaining })
  }, [])

  return {
    uploadProgress,
    uploadDocuments,
    stats,
    allDone,
    clearCompleted,
  }
}
