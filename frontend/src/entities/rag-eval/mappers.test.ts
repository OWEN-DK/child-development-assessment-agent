import { describe, it, expect } from 'vitest';
import {
  formatDomain,
  formatAge,
  formatAgeRange,
  getRunStatusLabel,
  getRunStatusColor,
  getDraftStatusLabel,
  getDraftStatusColor,
  getLayerStatusIcon,
  getLayerStatusLabel,
  formatPercent,
  formatDuration,
  formatTimestamp,
  formatStatus,
  formatDifficulty,
} from './mappers';
import type {
  TestDomain,
  TestRunStatus,
  DraftStatus,
  LayerResultStatus,
} from './enums';

describe('formatDomain', () => {
  it('gross_motor 返回 大运动', () => {
    expect(formatDomain('gross_motor' as TestDomain)).toBe('大运动');
  });

  it('language 返回 语言', () => {
    expect(formatDomain('language' as TestDomain)).toBe('语言');
  });

  it('sensory_integration 返回 感觉统合', () => {
    expect(formatDomain('sensory_integration' as TestDomain)).toBe('感觉统合');
  });

  it('未知领域返回原始字符串', () => {
    expect(formatDomain('unknown_domain' as TestDomain)).toBe('unknown_domain');
  });

  it('cognitive 返回 认知', () => {
    expect(formatDomain('cognitive' as TestDomain)).toBe('认知');
  });
});

describe('formatAge', () => {
  it('0 个月返回 0-6m', () => {
    expect(formatAge(0)).toBe('0-6m');
  });

  it('18 个月返回 1-2y', () => {
    expect(formatAge(18)).toBe('1-2y');
  });

  it('120 个月返回 6+y', () => {
    expect(formatAge(120)).toBe('6+y');
  });
});

describe('formatAgeRange', () => {
  it('undefined 返回 未知', () => {
    expect(formatAgeRange(undefined)).toBe('未知');
  });

  it('0.5 岁（6个月）返回 6个月', () => {
    expect(formatAgeRange(0.5)).toBe('6个月');
  });

  it('1 岁返回 1岁', () => {
    expect(formatAgeRange(1)).toBe('1岁');
  });

  it('1.5 岁返回 1岁6个月', () => {
    expect(formatAgeRange(1.5)).toBe('1岁6个月');
  });

  it('2 岁返回 2岁', () => {
    expect(formatAgeRange(2)).toBe('2岁');
  });

  it('0.25 岁（3个月）返回 3个月', () => {
    expect(formatAgeRange(0.25)).toBe('3个月');
  });

  it('0.08 岁（约1个月）返回 1个月', () => {
    expect(formatAgeRange(0.08)).toBe('1个月');
  });

  it('3 岁返回 3岁', () => {
    expect(formatAgeRange(3)).toBe('3岁');
  });

  it('2.5 岁返回 2岁6个月', () => {
    expect(formatAgeRange(2.5)).toBe('2岁6个月');
  });
});

describe('getRunStatusLabel', () => {
  it('completed 返回 已完成', () => {
    expect(getRunStatusLabel('completed' as TestRunStatus)).toBe('已完成');
  });

  it('failed 返回 失败', () => {
    expect(getRunStatusLabel('failed' as TestRunStatus)).toBe('失败');
  });

  it('pending 返回 待运行', () => {
    expect(getRunStatusLabel('pending' as TestRunStatus)).toBe('待运行');
  });

  it('running 返回 运行中', () => {
    expect(getRunStatusLabel('running' as TestRunStatus)).toBe('运行中');
  });

  it('cancelled 返回 已取消', () => {
    expect(getRunStatusLabel('cancelled' as TestRunStatus)).toBe('已取消');
  });
});

describe('getRunStatusColor', () => {
  it('completed 颜色为 success', () => {
    expect(getRunStatusColor('completed' as TestRunStatus)).toBe('success');
  });

  it('failed 颜色为 error', () => {
    expect(getRunStatusColor('failed' as TestRunStatus)).toBe('error');
  });

  it('running 颜色为 processing', () => {
    expect(getRunStatusColor('running' as TestRunStatus)).toBe('processing');
  });

  it('pending 颜色为 default', () => {
    expect(getRunStatusColor('pending' as TestRunStatus)).toBe('default');
  });

  it('cancelled 颜色为 warning', () => {
    expect(getRunStatusColor('cancelled' as TestRunStatus)).toBe('warning');
  });
});

describe('getDraftStatusLabel', () => {
  it('pending 返回 待处理', () => {
    expect(getDraftStatusLabel('pending' as DraftStatus)).toBe('待处理');
  });

  it('approved 返回 已通过', () => {
    expect(getDraftStatusLabel('approved' as DraftStatus)).toBe('已通过');
  });

  it('imported 返回 已导入', () => {
    expect(getDraftStatusLabel('imported' as DraftStatus)).toBe('已导入');
  });

  it('archived 返回 已归档', () => {
    expect(getDraftStatusLabel('archived' as DraftStatus)).toBe('已归档');
  });

  it('rejected 返回 已驳回', () => {
    expect(getDraftStatusLabel('rejected' as DraftStatus)).toBe('已驳回');
  });
});

describe('getDraftStatusColor', () => {
  it('approved 颜色为 success', () => {
    expect(getDraftStatusColor('approved' as DraftStatus)).toBe('success');
  });

  it('rejected 颜色为 error', () => {
    expect(getDraftStatusColor('rejected' as DraftStatus)).toBe('error');
  });

  it('generating 颜色为 processing', () => {
    expect(getDraftStatusColor('generating' as DraftStatus)).toBe('processing');
  });

  it('imported 颜色为 purple', () => {
    expect(getDraftStatusColor('imported' as DraftStatus)).toBe('purple');
  });

  it('pending 颜色为 default', () => {
    expect(getDraftStatusColor('pending' as DraftStatus)).toBe('default');
  });
});

describe('getLayerStatusIcon', () => {
  it('pass 图标为 ✅', () => {
    expect(getLayerStatusIcon('pass' as LayerResultStatus)).toBe('✅');
  });

  it('warn 图标为 ⚠️', () => {
    expect(getLayerStatusIcon('warn' as LayerResultStatus)).toBe('⚠️');
  });

  it('fail 图标为 ❌', () => {
    expect(getLayerStatusIcon('fail' as LayerResultStatus)).toBe('❌');
  });

  it('skip 图标为 ⏭️', () => {
    expect(getLayerStatusIcon('skip' as LayerResultStatus)).toBe('⏭️');
  });

  it('error 图标为 💥', () => {
    expect(getLayerStatusIcon('error' as LayerResultStatus)).toBe('💥');
  });
});

describe('getLayerStatusLabel', () => {
  it('pass 返回 通过', () => {
    expect(getLayerStatusLabel('pass' as LayerResultStatus)).toBe('通过');
  });

  it('warn 返回 警告', () => {
    expect(getLayerStatusLabel('warn' as LayerResultStatus)).toBe('警告');
  });

  it('fail 返回 失败', () => {
    expect(getLayerStatusLabel('fail' as LayerResultStatus)).toBe('失败');
  });

  it('skip 返回 跳过', () => {
    expect(getLayerStatusLabel('skip' as LayerResultStatus)).toBe('跳过');
  });

  it('error 返回 错误', () => {
    expect(getLayerStatusLabel('error' as LayerResultStatus)).toBe('错误');
  });
});

describe('formatPercent', () => {
  it('0.5 默认 1 位小数 → 50.0%', () => {
    expect(formatPercent(0.5)).toBe('50.0%');
  });

  it('0.12345 默认 1 位小数 → 12.3%', () => {
    expect(formatPercent(0.12345)).toBe('12.3%');
  });

  it('0.5 指定 2 位小数 → 50.00%', () => {
    expect(formatPercent(0.5, 2)).toBe('50.00%');
  });

  it('0 默认 → 0.0%', () => {
    expect(formatPercent(0)).toBe('0.0%');
  });

  it('1 默认 → 100.0%', () => {
    expect(formatPercent(1)).toBe('100.0%');
  });

  it('0.9999 指定 2 位小数 → 99.99%', () => {
    expect(formatPercent(0.9999, 2)).toBe('99.99%');
  });

  it('0.3333 指定 0 位小数 → 33%', () => {
    expect(formatPercent(0.3333, 0)).toBe('33%');
  });
});

describe('formatDuration', () => {
  it('30 秒 → 30.0秒', () => {
    expect(formatDuration(30)).toBe('30.0秒');
  });

  it('0 秒 → 0.0秒', () => {
    expect(formatDuration(0)).toBe('0.0秒');
  });

  it('90 秒 → 1分30秒', () => {
    expect(formatDuration(90)).toBe('1分30秒');
  });

  it('60 秒 → 1分0秒', () => {
    expect(formatDuration(60)).toBe('1分0秒');
  });

  it('59.9 秒 → 59.9秒', () => {
    expect(formatDuration(59.9)).toBe('59.9秒');
  });

  it('125 秒 → 2分5秒', () => {
    expect(formatDuration(125)).toBe('2分5秒');
  });

  it('0.5 秒 → 0.5秒', () => {
    expect(formatDuration(0.5)).toBe('0.5秒');
  });
});

describe('formatTimestamp', () => {
  it('格式化 ISO 时间戳为中文本地化格式', () => {
    const result = formatTimestamp('2024-06-15T10:30:00Z');
    expect(result).toContain('2024');
    expect(result).toContain('06');
    expect(result).toContain('15');
  });

  it('不同时间戳生成不同结果', () => {
    const a = formatTimestamp('2024-01-01T00:00:00Z');
    const b = formatTimestamp('2025-12-31T23:59:00Z');
    expect(a).not.toBe(b);
  });

  it('返回字符串类型', () => {
    const result = formatTimestamp('2024-06-15T10:30:00Z');
    expect(typeof result).toBe('string');
  });
});

describe('formatStatus', () => {
  it('completed 返回 已完成（兼容旧名）', () => {
    expect(formatStatus('completed' as TestRunStatus)).toBe('已完成');
  });

  it('failed 返回 失败', () => {
    expect(formatStatus('failed' as TestRunStatus)).toBe('失败');
  });

  it('running 返回 运行中', () => {
    expect(formatStatus('running' as TestRunStatus)).toBe('运行中');
  });
});

describe('formatDifficulty', () => {
  it('easy 返回 简单', () => {
    expect(formatDifficulty('easy')).toBe('简单');
  });

  it('medium 返回 中等', () => {
    expect(formatDifficulty('medium')).toBe('中等');
  });

  it('hard 返回 困难', () => {
    expect(formatDifficulty('hard')).toBe('困难');
  });

  it('未知等级返回原始字符串', () => {
    expect(formatDifficulty('extreme')).toBe('extreme');
  });

  it('空字符串返回空字符串', () => {
    expect(formatDifficulty('')).toBe('');
  });
});
