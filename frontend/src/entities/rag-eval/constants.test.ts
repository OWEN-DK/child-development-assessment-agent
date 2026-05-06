import { describe, it, expect } from 'vitest';
import {
  RUN_STATUS_MAP,
  STATUS_MAP,
  DRAFT_STATUS_MAP,
  LAYER_STATUS_MAP,
  LAYER_NAMES,
  DIFFICULTY_MAP,
  SOURCE_MAP,
} from './constants';

/** 测试运行状态全部枚举值 */
const ALL_RUN_STATUSES = [
  'pending',
  'running',
  'completed',
  'failed',
  'cancelled',
] as const;

/** 草稿状态全部枚举值 */
const ALL_DRAFT_STATUSES = [
  'pending',
  'generating',
  'generated',
  'approved',
  'rejected',
  'archived',
  'imported',
] as const;

/** 六层诊断状态全部枚举值 */
const ALL_LAYER_STATUSES = ['pass', 'warn', 'fail', 'skip', 'error'] as const;

describe('RUN_STATUS_MAP', () => {
  it('包含全部 5 个状态', () => {
    expect(Object.keys(RUN_STATUS_MAP)).toHaveLength(5);
  });

  it('每个状态均包含 label 和 color', () => {
    for (const status of ALL_RUN_STATUSES) {
      expect(RUN_STATUS_MAP[status]).toHaveProperty('label');
      expect(RUN_STATUS_MAP[status]).toHaveProperty('color');
    }
  });

  it('completed 状态标签为 已完成', () => {
    expect(RUN_STATUS_MAP.completed.label).toBe('已完成');
  });

  it('failed 状态颜色为 error', () => {
    expect(RUN_STATUS_MAP.failed.color).toBe('error');
  });
});

describe('STATUS_MAP', () => {
  it('包含全部 5 个状态', () => {
    expect(Object.keys(STATUS_MAP)).toHaveLength(5);
  });

  it('pending 映射为 待运行', () => {
    expect(STATUS_MAP.pending).toBe('待运行');
  });

  it('cancelled 映射为 已取消', () => {
    expect(STATUS_MAP.cancelled).toBe('已取消');
  });
});

describe('DRAFT_STATUS_MAP', () => {
  it('包含全部 7 个状态', () => {
    expect(Object.keys(DRAFT_STATUS_MAP)).toHaveLength(7);
  });

  it('每个状态均包含 label 和 color', () => {
    for (const status of ALL_DRAFT_STATUSES) {
      expect(DRAFT_STATUS_MAP[status]).toHaveProperty('label');
      expect(DRAFT_STATUS_MAP[status]).toHaveProperty('color');
    }
  });

  it('approved 标签为 已通过', () => {
    expect(DRAFT_STATUS_MAP.approved.label).toBe('已通过');
  });

  it('imported 颜色为 purple', () => {
    expect(DRAFT_STATUS_MAP.imported.color).toBe('purple');
  });
});

describe('LAYER_STATUS_MAP', () => {
  it('包含全部 5 个状态', () => {
    expect(Object.keys(LAYER_STATUS_MAP)).toHaveLength(5);
  });

  it('每个状态均包含 label、color、icon', () => {
    for (const status of ALL_LAYER_STATUSES) {
      expect(LAYER_STATUS_MAP[status]).toHaveProperty('label');
      expect(LAYER_STATUS_MAP[status]).toHaveProperty('color');
      expect(LAYER_STATUS_MAP[status]).toHaveProperty('icon');
    }
  });

  it('pass 状态标签为 通过', () => {
    expect(LAYER_STATUS_MAP.pass.label).toBe('通过');
  });

  it('fail 状态图标为 ❌', () => {
    expect(LAYER_STATUS_MAP.fail.icon).toBe('❌');
  });
});

describe('LAYER_NAMES', () => {
  it('包含 6 层', () => {
    expect(Object.keys(LAYER_NAMES)).toHaveLength(6);
  });

  it('第 1 层为 规则引擎校验', () => {
    expect(LAYER_NAMES['1']).toBe('规则引擎校验');
  });

  it('第 6 层为 回归检测', () => {
    expect(LAYER_NAMES['6']).toBe('回归检测');
  });

  it('每层名称为非空字符串', () => {
    for (let i = 1; i <= 6; i++) {
      expect(LAYER_NAMES[String(i)]).toBeTruthy();
    }
  });
});

describe('DIFFICULTY_MAP', () => {
  it('包含 easy/medium/hard 三种难度', () => {
    expect(Object.keys(DIFFICULTY_MAP)).toHaveLength(3);
  });

  it('easy 映射为 简单', () => {
    expect(DIFFICULTY_MAP.easy).toBe('简单');
  });

  it('medium 映射为 中等', () => {
    expect(DIFFICULTY_MAP.medium).toBe('中等');
  });

  it('hard 映射为 困难', () => {
    expect(DIFFICULTY_MAP.hard).toBe('困难');
  });
});

describe('SOURCE_MAP', () => {
  it('包含至少 manual/draft/import 三种来源', () => {
    expect(SOURCE_MAP.manual).toBe('手动');
    expect(SOURCE_MAP.draft).toBe('草稿');
    expect(SOURCE_MAP.import).toBe('导入');
  });

  it('json_import 也映射为 导入', () => {
    expect(SOURCE_MAP.json_import).toBe('导入');
  });
});

