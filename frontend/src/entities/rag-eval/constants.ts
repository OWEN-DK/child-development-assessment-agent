/** RAG 评估模块常量定义 —— 领域、状态映射等唯一真相源 */

import type {
  TestDomain,
  TestRunStatus,
  DraftStatus,
  LayerResultStatus,
  DifficultyLevel,
} from './enums';

/** 领域中文映射 */
export const DOMAIN_MAP: Record<TestDomain, string> = {
  gross_motor: '大运动',
  fine_motor: '精细运动',
  language: '语言',
  cognitive: '认知',
  social_emotional: '社交情感',
  sensory_integration: '感觉统合',
};

/** 领域颜色映射 */
export const DOMAIN_COLORS: Record<TestDomain, string> = {
  gross_motor: 'blue',
  fine_motor: 'cyan',
  language: 'green',
  cognitive: 'orange',
  social_emotional: 'purple',
  sensory_integration: 'red',
};

/** 运行状态映射 */
export const RUN_STATUS_MAP: Record<TestRunStatus, { label: string; color: string }> = {
  pending: { label: '待运行', color: 'default' },
  running: { label: '运行中', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
  cancelled: { label: '已取消', color: 'warning' },
};

/** 兼容旧名 */
export const STATUS_MAP: Record<TestRunStatus, string> = {
  pending: '待运行',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

/** 草稿状态映射 */
export const DRAFT_STATUS_MAP: Record<DraftStatus, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'default' },
  generating: { label: '生成中', color: 'processing' },
  generated: { label: '已生成', color: 'warning' },
  approved: { label: '已通过', color: 'success' },
  rejected: { label: '已驳回', color: 'error' },
  archived: { label: '已归档', color: 'default' },
  imported: { label: '已导入', color: 'purple' },
};

/** 六层诊断状态映射 */
export const LAYER_STATUS_MAP: Record<LayerResultStatus, { label: string; color: string; icon: string }> = {
  pass: { label: '通过', color: 'success', icon: '✅' },
  warn: { label: '警告', color: 'warning', icon: '⚠️' },
  fail: { label: '失败', color: 'error', icon: '❌' },
  skip: { label: '跳过', color: 'default', icon: '⏭️' },
  error: { label: '错误', color: 'red', icon: '💥' },
};

/** 六层命名 */
export const LAYER_NAMES: Record<string, string> = {
  '1': '规则引擎校验',
  '2': '历史趋势对比',
  '3': 'LLM 语义诊断',
  '4': '数据质量审查',
  '5': '效果评估',
  '6': '回归检测',
};

/** 难度等级中文映射 */
export const DIFFICULTY_MAP: Record<DifficultyLevel, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
};

/** 用例来源映射 */
export const SOURCE_MAP: Record<string, string> = {
  manual: '手动',
  draft: '草稿',
  import: '导入',
  json_import: '导入',
  book_generated: '书籍生成',
  mixed: '混合',
};

/** 年龄段列表 */
export const AGE_STAGES = [
  '0-1个月',
  '1-3个月',
  '3-6个月',
  '6-12个月',
  '1-2岁',
  '2-3岁',
  '3-4岁',
  '4-5岁',
  '5-6岁',
  '6-7岁',
];

/** 兼容旧版本 */
const AGE_STAGE_THRESHOLDS: { max: number; label: string }[] = [
  { max: 6, label: '0-6m' },
  { max: 12, label: '6-12m' },
  { max: 24, label: '1-2y' },
  { max: 36, label: '2-3y' },
  { max: 48, label: '3-4y' },
  { max: 72, label: '4-6y' },
  { max: Infinity, label: '6+y' },
];

export function getAgeStage(ageMonths: number): string {
  const stage = AGE_STAGE_THRESHOLDS.find((t) => ageMonths <= t.max);
  return stage?.label ?? '6+y';
}
