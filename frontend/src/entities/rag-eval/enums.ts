/** RAG 评估模块全部枚举类型 */

/** 测试运行状态 */
export type TestRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

/** 草稿状态 */
export type DraftStatus =
  | 'pending'
  | 'generating'
  | 'generated'
  | 'approved'
  | 'rejected'
  | 'archived'
  | 'imported';

/** 测试用例状态（兼容旧名） */
export type TestCaseStatus = DraftStatus;

/** 六层诊断单层状态 */
export type LayerResultStatus = 'pass' | 'warn' | 'fail' | 'skip' | 'error';

/** 兼容旧名 */
export type LayerStatus = LayerResultStatus;

/** 问题严重级别 */
export type IssueSeverity = 'critical' | 'warning' | 'info';

/** 调优建议状态 */
export type TuningActionStatus = 'pending' | 'adopted' | 'rejected' | 'ignored';

/** 兼容旧名 */
export type SuggestionStatus = TuningActionStatus;

/** 调优建议分类 */
export type SuggestionCategory =
  | 'retrieval'
  | 'generation'
  | 'configuration'
  | 'cost'
  | 'prompt';

/** 用例来源类型 */
export type TestCaseSource = 'manual' | 'draft' | 'import';

/** 兼容旧名 */
export type TestSourceType =
  | 'manual'
  | 'draft'
  | 'import'
  | 'json_import'
  | 'book_generated'
  | 'mixed';

/** 难度等级 */
export type DifficultyLevel = 'easy' | 'medium' | 'hard';

/** 源文档状态 */
export type DocumentStatus = 'uploaded' | 'parsing' | 'ready' | 'archived';

/** 报告导出格式 */
export type ReportExportFormat = 'markdown' | 'json' | 'csv';
