import { describe, it, expect } from 'vitest';
import {
  DOMAIN_MAP,
  DOMAIN_COLORS,
  RUN_STATUS_MAP,
  STATUS_MAP,
  DRAFT_STATUS_MAP,
  LAYER_STATUS_MAP,
  LAYER_NAMES,
  DIFFICULTY_MAP,
  SOURCE_MAP,
  AGE_STAGES,
  getAgeStage,
} from './constants';

/** 测试领域全部枚举值 */
const ALL_DOMAINS = [
  'gross_motor',
  'fine_motor',
  'language',
  'cognitive',
  'social_emotional',
  'sensory_integration',
] as const;

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

describe('DOMAIN_MAP', () => {
  it('包含全部 6 个领域', () => {
    expect(Object.keys(DOMAIN_MAP)).toHaveLength(6);
  });

  it('每个领域均有非空中文标签', () => {
    for (const domain of ALL_DOMAINS) {
      expect(DOMAIN_MAP[domain]).toBeTruthy();
      expect(typeof DOMAIN_MAP[domain]).toBe('string');
    }
  });

  it('大运动映射正确', () => {
    expect(DOMAIN_MAP.gross_motor).toBe('大运动');
  });

  it('感觉统合映射正确', () => {
    expect(DOMAIN_MAP.sensory_integration).toBe('感觉统合');
  });
});

describe('DOMAIN_COLORS', () => {
  it('包含全部 6 个领域', () => {
    expect(Object.keys(DOMAIN_COLORS)).toHaveLength(6);
  });

  it('每个领域均有颜色值', () => {
    for (const domain of ALL_DOMAINS) {
      expect(DOMAIN_COLORS[domain]).toBeTruthy();
    }
  });

  it('大运动颜色为 blue', () => {
    expect(DOMAIN_COLORS.gross_motor).toBe('blue');
  });
});

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

describe('AGE_STAGES', () => {
  it('包含 10 个年龄段', () => {
    expect(AGE_STAGES).toHaveLength(10);
  });

  it('第一个年龄段为 0-1个月', () => {
    expect(AGE_STAGES[0]).toBe('0-1个月');
  });
});

describe('getAgeStage', () => {
  it('0 个月返回 0-6m', () => {
    expect(getAgeStage(0)).toBe('0-6m');
  });

  it('6 个月返回 0-6m（含边界）', () => {
    expect(getAgeStage(6)).toBe('0-6m');
  });

  it('7 个月返回 6-12m', () => {
    expect(getAgeStage(7)).toBe('6-12m');
  });

  it('12 个月返回 6-12m（含边界）', () => {
    expect(getAgeStage(12)).toBe('6-12m');
  });

  it('18 个月返回 1-2y', () => {
    expect(getAgeStage(18)).toBe('1-2y');
  });

  it('24 个月返回 1-2y（含边界）', () => {
    expect(getAgeStage(24)).toBe('1-2y');
  });

  it('30 个月返回 2-3y', () => {
    expect(getAgeStage(30)).toBe('2-3y');
  });

  it('36 个月返回 2-3y（含边界）', () => {
    expect(getAgeStage(36)).toBe('2-3y');
  });

  it('42 个月返回 3-4y', () => {
    expect(getAgeStage(42)).toBe('3-4y');
  });

  it('60 个月返回 4-6y', () => {
    expect(getAgeStage(60)).toBe('4-6y');
  });

  it('72 个月返回 4-6y（含边界）', () => {
    expect(getAgeStage(72)).toBe('4-6y');
  });

  it('非常大的值返回 6+y', () => {
    expect(getAgeStage(120)).toBe('6+y');
    expect(getAgeStage(999)).toBe('6+y');
  });
});
