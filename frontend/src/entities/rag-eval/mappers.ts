/** 格式化映射工具函数 */

import {
  RUN_STATUS_MAP,
  DRAFT_STATUS_MAP,
  LAYER_STATUS_MAP,
} from './constants';
import type {
  TestRunStatus,
  DraftStatus,
  LayerResultStatus,
} from './enums';

/** 运行状态标签 */
export function getRunStatusLabel(status: TestRunStatus): string {
  return RUN_STATUS_MAP[status]?.label || status;
}

/** 运行状态颜色 */
export function getRunStatusColor(status: TestRunStatus): string {
  return RUN_STATUS_MAP[status]?.color || 'default';
}

/** 草稿状态标签 */
export function getDraftStatusLabel(status: DraftStatus): string {
  return DRAFT_STATUS_MAP[status]?.label || status;
}

/** 草稿状态颜色 */
export function getDraftStatusColor(status: DraftStatus): string {
  return DRAFT_STATUS_MAP[status]?.color || 'default';
}

/** 六层诊断状态图标 */
export function getLayerStatusIcon(status: LayerResultStatus): string {
  return LAYER_STATUS_MAP[status]?.icon || '';
}

/** 六层诊断状态标签 */
export function getLayerStatusLabel(status: LayerResultStatus): string {
  return LAYER_STATUS_MAP[status]?.label || status;
}

/** 百分比格式化 */
export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/** 时长格式化 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}秒`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}分${secs}秒`;
}

/** 时间戳格式化 */
export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** 兼容旧名 */
export function formatStatus(status: TestRunStatus): string {
  return getRunStatusLabel(status);
}

/** 兼容旧名 */
export function formatDifficulty(level: string): string {
  const DIFFICULTY_MAP: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' };
  return DIFFICULTY_MAP[level] || level;
}
