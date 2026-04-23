import type { ProgressListConfig, BaseProgressTask } from '../types';

// 草稿生成任务类型
export interface DraftGenerationTask extends BaseProgressTask {
  // 扩展字段
  domain: string;
  ageStage: string;
  generated?: number;
  deduplicated?: number;
  totalCombinations?: number;
  currentCombination?: number;
}

// 草稿生成配置
export const draftGenerationConfig: ProgressListConfig<DraftGenerationTask> = {
  title: '草稿生成任务',
  emptyText: '暂无草稿生成任务',
  getItemKey: (task) => task.taskId,
  getItemTitle: (task) => `生成草稿：${task.domain}`,
  getItemSubtitle: (task) => `年龄段：${task.ageStage}`,
  getStageText: (task) => {
    if (task.status === 'running') {
      const progress = task.currentCombination && task.totalCombinations
        ? ` (${task.currentCombination}/${task.totalCombinations})`
        : '';
      return `正在生成 [${task.domain}] [${task.ageStage}]${progress}`;
    }
    if (task.status === 'completed') {
      return `已完成，共生成 ${task.generated || 0} 个草稿`;
    }
    if (task.status === 'cancelled') {
      return '已取消';
    }
    return task.message;
  },
  showProgress: true,
  showStage: true,
  onCancel: (task) => {
    fetch(`/api/v1/rag/test/drafts/generate/${task.taskId}/cancel`, {
      method: 'POST',
    }).catch((error) => {
      console.error('Failed to cancel draft generation:', error);
    });
  },
  autoRemoveOnSuccess: true,
  autoRemoveOnCancel: true,
  successKeepSeconds: 5,
  cancelKeepSeconds: 2,
  failedKeepSeconds: 3600,
};
