import type { ProgressListConfig, BaseProgressTask } from '../types';

/** 草稿生成任务类型 */
export interface DraftGenerationTask extends BaseProgressTask {
  documentName?: string;
  generated?: number;
  skipped?: number;
}

const STAGE_LABELS: Record<string, string> = {
  generation_started: '初始化生成任务',
  metadata_analyzed: '文档元数据分析完成',
  generating: '生成草稿中',
  drafts_generated: '草稿已生成',
  checking: '忠实度校验中',
  faithfulness_checked: '忠实度校验完成',
  deduplication_completed: '去重完成',
};

export const draftGenerationConfig: ProgressListConfig<DraftGenerationTask> = {
  title: '草稿生成任务',
  emptyText: '暂无草稿生成任务',
  getItemKey: (task) => task.taskId,
  getItemTitle: (task) => task.documentName ? `生成草稿：${task.documentName}` : '生成草稿',
  getStageText: (task) => {
    if (task.status === 'completed') {
      return `已完成，生成 ${task.generated ?? 0} 个，跳过 ${task.skipped ?? 0} 个`;
    }
    if (task.status === 'failed') {
      return task.error ?? '生成失败';
    }
    return task.message || '处理中...';
  },
  showProgress: true,
  showStage: true,
  autoRemoveOnSuccess: true,
  successKeepSeconds: 5,
  failedKeepSeconds: 3600,
};

export { STAGE_LABELS };
