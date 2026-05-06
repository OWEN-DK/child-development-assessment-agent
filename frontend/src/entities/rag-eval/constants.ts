/** RAG 评估模块常量定义 —— 领域、状态映射等唯一真相源 */

import type {
  TestRunStatus,
  DraftStatus,
  LayerResultStatus,
  DifficultyLevel,
} from './enums';

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

