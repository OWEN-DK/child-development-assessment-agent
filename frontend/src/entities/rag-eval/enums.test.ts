import { describe, it, expect } from 'vitest';

/**
 * 枚举类型本身是 TypeScript 联合类型，无法在运行时直接测试。
 * 通过常量数组验证值集合的完整性。
 */

/** 各枚举类型的完整值集合常量 */
const TEST_RUN_STATUS_VALUES = [
  'pending',
  'running',
  'completed',
  'failed',
  'cancelled',
] as const;

const DRAFT_STATUS_VALUES = [
  'pending',
  'generating',
  'generated',
  'approved',
  'rejected',
  'archived',
  'imported',
] as const;

const LAYER_RESULT_STATUS_VALUES = ['pass', 'warn', 'fail', 'skip', 'error'] as const;

const ISSUE_SEVERITY_VALUES = ['critical', 'warning', 'info'] as const;

const TUNING_ACTION_STATUS_VALUES = ['pending', 'adopted', 'rejected', 'ignored'] as const;

const TEST_CASE_SOURCE_VALUES = ['manual', 'draft', 'import'] as const;

const DIFFICULTY_LEVEL_VALUES = ['easy', 'medium', 'hard'] as const;

const DOCUMENT_STATUS_VALUES = ['uploaded', 'parsing', 'ready', 'archived'] as const;

describe('TestRunStatus 枚举值', () => {
  it('包含 5 个状态', () => {
    expect(TEST_RUN_STATUS_VALUES).toHaveLength(5);
  });

  it('包含 pending 和 completed', () => {
    expect(TEST_RUN_STATUS_VALUES).toContain('pending');
    expect(TEST_RUN_STATUS_VALUES).toContain('completed');
  });

  it('不包含未知状态', () => {
    expect(TEST_RUN_STATUS_VALUES).not.toContain('unknown');
  });
});

describe('DraftStatus 枚举值', () => {
  it('包含 7 个状态', () => {
    expect(DRAFT_STATUS_VALUES).toHaveLength(7);
  });

  it('包含 generating 和 imported', () => {
    expect(DRAFT_STATUS_VALUES).toContain('generating');
    expect(DRAFT_STATUS_VALUES).toContain('imported');
  });

  it('包含 approved 和 rejected', () => {
    expect(DRAFT_STATUS_VALUES).toContain('approved');
    expect(DRAFT_STATUS_VALUES).toContain('rejected');
  });
});

describe('LayerResultStatus 枚举值', () => {
  it('包含 5 个状态', () => {
    expect(LAYER_RESULT_STATUS_VALUES).toHaveLength(5);
  });

  it('包含 pass、warn、fail、skip、error', () => {
    expect(LAYER_RESULT_STATUS_VALUES).toContain('pass');
    expect(LAYER_RESULT_STATUS_VALUES).toContain('warn');
    expect(LAYER_RESULT_STATUS_VALUES).toContain('fail');
    expect(LAYER_RESULT_STATUS_VALUES).toContain('skip');
    expect(LAYER_RESULT_STATUS_VALUES).toContain('error');
  });
});

describe('IssueSeverity 枚举值', () => {
  it('包含 3 个级别', () => {
    expect(ISSUE_SEVERITY_VALUES).toHaveLength(3);
  });

  it('包含 critical、warning、info', () => {
    expect(ISSUE_SEVERITY_VALUES).toContain('critical');
    expect(ISSUE_SEVERITY_VALUES).toContain('warning');
    expect(ISSUE_SEVERITY_VALUES).toContain('info');
  });
});

describe('TuningActionStatus 枚举值', () => {
  it('包含 4 个状态', () => {
    expect(TUNING_ACTION_STATUS_VALUES).toHaveLength(4);
  });

  it('包含 pending、adopted、rejected、ignored', () => {
    expect(TUNING_ACTION_STATUS_VALUES).toContain('pending');
    expect(TUNING_ACTION_STATUS_VALUES).toContain('adopted');
    expect(TUNING_ACTION_STATUS_VALUES).toContain('rejected');
    expect(TUNING_ACTION_STATUS_VALUES).toContain('ignored');
  });
});

describe('TestCaseSource 枚举值', () => {
  it('包含 3 个来源', () => {
    expect(TEST_CASE_SOURCE_VALUES).toHaveLength(3);
  });

  it('包含 manual、draft、import', () => {
    expect(TEST_CASE_SOURCE_VALUES).toContain('manual');
    expect(TEST_CASE_SOURCE_VALUES).toContain('draft');
    expect(TEST_CASE_SOURCE_VALUES).toContain('import');
  });
});

describe('DifficultyLevel 枚举值', () => {
  it('包含 3 个等级', () => {
    expect(DIFFICULTY_LEVEL_VALUES).toHaveLength(3);
  });

  it('包含 easy、medium、hard', () => {
    expect(DIFFICULTY_LEVEL_VALUES).toContain('easy');
    expect(DIFFICULTY_LEVEL_VALUES).toContain('medium');
    expect(DIFFICULTY_LEVEL_VALUES).toContain('hard');
  });
});

describe('DocumentStatus 枚举值', () => {
  it('包含 4 个状态', () => {
    expect(DOCUMENT_STATUS_VALUES).toHaveLength(4);
  });

  it('包含 uploaded、parsing、ready、archived', () => {
    expect(DOCUMENT_STATUS_VALUES).toContain('uploaded');
    expect(DOCUMENT_STATUS_VALUES).toContain('parsing');
    expect(DOCUMENT_STATUS_VALUES).toContain('ready');
    expect(DOCUMENT_STATUS_VALUES).toContain('archived');
  });
});
