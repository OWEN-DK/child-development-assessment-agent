import type { ProgressListConfig } from '../types';
import type { UploadTaskStatus } from '../../../api/documents/types';
import { cancelUploadTask, deleteTask } from '../../../api/documents';

// 适配 UploadTaskStatus 到 BaseProgressTask
function adaptUploadTask(task: UploadTaskStatus) {
  return {
    taskId: task.task_id,
    status: task.status,
    progress: task.progress || 0,
    message: task.message,
    createdAt: task.created_at,
    error: task.error,
    // 扩展字段
    filename: task.filename,
    stage: task.stage,
  };
}

export type AdaptedUploadTask = ReturnType<typeof adaptUploadTask>;

// 文档上传配置
export const documentUploadConfig: ProgressListConfig<AdaptedUploadTask> = {
  title: '正在处理的文档',
  emptyText: '暂无正在处理的任务',
  getItemKey: (task) => task.taskId,
  getItemTitle: (task) => task.filename,
  getStageText: (task) => {
    const stageMap: Record<string, string> = {
      pending: '等待处理',
      parsing: '正在解析',
      chunking: '正在分块',
      metadata_extraction: '正在提取元数据',
      embedding: '正在嵌入',
      indexing: '正在索引',
      completed: '处理完成',
    };
    return task.stage ? stageMap[task.stage] || task.message : task.message;
  },
  showProgress: true,
  showStage: true,
  onCancel: async (task) => {
    try {
      await cancelUploadTask(task.taskId);
    } catch (error) {
      console.error('Failed to cancel upload task:', error);
    }
  },
  onDelete: async (task) => {
    try {
      await deleteTask(task.taskId);
    } catch (error) {
      console.error('Failed to delete task:', error);
    }
  },
  autoRemoveOnSuccess: true,
  autoRemoveOnCancel: true,
  successKeepSeconds: 3,
  cancelKeepSeconds: 2,
  failedKeepSeconds: 3600,
};

// 导出适配器函数
export { adaptUploadTask };
