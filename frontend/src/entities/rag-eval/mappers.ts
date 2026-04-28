/** 格式化映射工具函数 */

import {
  DOMAIN_MAP,
  RUN_STATUS_MAP,
  DRAFT_STATUS_MAP,
  LAYER_STATUS_MAP,
  getAgeStage,
} from './constants';
import type {
  TestDomain,
  TestRunStatus,
  DraftStatus,
  LayerResultStatus,
} from './enums';

/** 格式化领域 */
export function formatDomain(domain: TestDomain): string {
  return DOMAIN_MAP[domain] || domain;
}

/** 格式化年龄段 */
export function formatAge(age: number): string {
  return getAgeStage(age);
}

/** ⚠️ age 参数单位为岁，转换后展示为中文月龄 */
export function formatAgeRange(age?: number): string {
  if (age == null) return '未知';
  if (age < 1) return `${Math.round(age * 12)}个月`;
  const years = Math.floor(age);
  const months = Math.round((age - years) * 12);
  if (years === 0) return `${months}个月`;
  if (months === 0) return `${years}岁`;
  return `${years}岁${months}个月`;
}

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
