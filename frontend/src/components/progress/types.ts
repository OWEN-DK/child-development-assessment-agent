import type { ReactNode } from 'react';

// 任务状态枚举
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

// 基础任务状态（所有场景通用）
export interface BaseProgressTask {
  taskId: string;
  status: TaskStatus;
  progress: number;           // 0-100
  message: string;            // 当前阶段描述
  createdAt: number;          // 创建时间戳
  error?: string;             // 错误信息
}

// 组件配置接口
export interface ProgressListConfig<T extends BaseProgressTask> {
  title: string;                              // 列表标题
  emptyText?: string;                         // 空状态文案
  getItemKey: (task: T) => string;            // 唯一键提取
  getItemTitle: (task: T) => ReactNode;       // 标题渲染
  getItemSubtitle?: (task: T) => ReactNode;   // 副标题（可选）
  getStageText?: (task: T) => ReactNode;      // 阶段信息（可选）
  showProgress: boolean;                      // 是否显示进度条
  showStage: boolean;                         // 是否显示阶段
  onCancel?: (task: T) => void;               // 取消回调
  onDelete?: (task: T) => void;               // 删除回调
  onRetry?: (task: T) => void;                // 重试回调（可选）
  autoRemoveOnSuccess?: boolean;              // 成功后自动移除
  autoRemoveOnCancel?: boolean;               // 取消后自动移除
  successKeepSeconds?: number;                // 成功后保留秒数
  cancelKeepSeconds?: number;                 // 取消后保留秒数
  failedKeepSeconds?: number;                 // 失败后保留秒数
}

// Hook 配置选项
export interface UseProgressPollingOptions<T extends BaseProgressTask> {
  fetchTasks: () => Promise<T[]>;             // 获取任务列表
  cancelTask: (taskId: string) => Promise<void>;  // 取消任务
  pollingInterval?: number;                   // 轮询间隔（默认 2000ms）
  onTaskComplete?: (task: T) => void;         // 任务完成回调
  onTaskFailed?: (task: T) => void;           // 任务失败回调
  onTaskCancelled?: (task: T) => void;        // 任务取消回调
}

// Hook 返回值
export interface UseProgressPollingReturn<T extends BaseProgressTask> {
  tasks: T[];
  loading: boolean;
  cancelTask: (taskId: string) => Promise<void>;
  refreshTasks: () => Promise<void>;
  removeTask: (taskId: string) => void;
}
