/** 从 S3/S4 structured_data 渲染 Markdown 展示 */

import type { SectionOutput } from '../types';

/** tier 排序顺序 + 标签 */
const TIER_ORDER = ['primary', 'secondary', 'supplementary'] as const;
const TIER_LABELS: Record<string, string> = {
  primary: '🔴 核心推荐',
  secondary: '🟡 辅助推荐',
  supplementary: '🟢 补充推荐',
};

/** S3 运动类型推荐 — 按 tier 分组渲染 */
export function renderS3Markdown(structuredData: Record<string, any>): string {
  const sd = structuredData || {};
  const ets = sd.exercise_types || [];
  if (!Array.isArray(ets) || ets.length === 0) return '';

  const lines: string[] = [];

  // 适用年龄
  const childAge = sd.child_age_group || '';
  if (childAge) {
    lines.push(`> 适用：**${childAge}**`);
    lines.push('');
  }

  // 按 tier 分组
  const grouped: Record<string, typeof ets> = {};
  for (const et of ets) {
    const key = et.tier || 'secondary';
    (grouped[key] ??= []).push(et);
  }

  for (const tier of TIER_ORDER) {
    const items = grouped[tier];
    if (!items || items.length === 0) continue;

    const tierDesc: Record<string, string> = {
      primary: '最针对性、解决首要问题的运动',
      secondary: '补充性运动，增强干预效果',
      supplementary: '可选运动，丰富方案',
    };
    lines.push(`**${TIER_LABELS[tier]}**  _${tierDesc[tier] || ''}_`);
    lines.push('');
    lines.push('| 运动名称 | 分类 | 训练目标 | 推荐理由 |');
    lines.push('|---------|------|---------|--------|');

    for (const et of items) {
      const name = et.name || '';
      const category = et.category || '';
      const skills = (et.target_skills || []).join('、');
      const rationale = (et.recommendation_rationale || '').slice(0, 100);

      lines.push(`| **${name}** | ${category} | ${skills} | ${rationale} |`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

/** S4 运动方案 — 表格化渲染 */
export function renderS4Markdown(structuredData: Record<string, any>): string {
  const sd = structuredData || {};
  const phases = sd.phases || [];
  const lines: string[] = [];

  // 方案总览
  const ps = sd.plan_summary || {};
  if (ps.total_duration_days) {
    lines.push(`> 📅 **方案总览**：${ps.total_phases || '?'} 阶段 · 共 ${ps.total_duration_days} 天 · 每天 ${ps.daily_duration_min || '?'} 分钟 · 每周 ${ps.weekly_frequency || '?'} 天`);
    lines.push('');
  }

  if (phases.length === 0) {
    const caution = sd.caution || '';
    if (caution) {
      lines.push('**⚠️ 注意事项**');
      lines.push(`> ${caution}`);
    }
    return lines.join('\n');
  }

  // 扁平化为统一表格
  lines.push('| 阶段 | 周 | 天 | 运动 | 时长 | 强度 | 训练目标 | 执行要点 |');
  lines.push('|------|---|---|------|------|------|---------|---------|');

  for (let pi = 0; pi < phases.length; pi++) {
    const phase = phases[pi];
    const phaseName = phase.phase_name || `阶段${pi + 1}`;
    let firstInPhase = true;

    for (const week of phase.weeks || []) {
      const weekIdx = week.week_index || 1;
      let firstInWeek = true;

      for (const day of week.days || []) {
        const dayIdx = day.day_index || 1;
        const exercises = day.main_exercises || [];

        if (exercises.length === 0) {
          // 休息日
          const phaseCell = firstInPhase ? `**${phaseName}**` : '';
          const weekCell = firstInWeek ? `第${weekIdx}周` : '';
          lines.push(`| ${phaseCell} | ${weekCell} | 第${dayIdx}天 | *休息* | - | - | - | - |`);
          firstInPhase = false;
          firstInWeek = false;
          continue;
        }

        let firstExInDay = true;
        for (const ex of exercises) {
          const name = ex.name || '未命名';
          const duration = ex.duration_min ? `${ex.duration_min}min` : '-';
          const intensity = ex.intensity || '-';
          const intensityHint = ex.intensity_hint ? ` (${ex.intensity_hint})` : '';
          const targetSkill = ex.target_skill || '';
          const desc = (ex.description || ex.notes || '').slice(0, 40);

          const phaseCell = firstInPhase ? `**${phaseName}**` : '';
          const weekCell = firstInWeek ? `第${weekIdx}周` : '';
          const dayCell = firstExInDay ? `第${dayIdx}天` : '';

          lines.push(`| ${phaseCell} | ${weekCell} | ${dayCell} | 🎯 ${name} | ${duration} | ${intensity}${intensityHint} | ${targetSkill || '-'} | ${desc || '-'} |`);

          firstInPhase = false;
          firstInWeek = false;
          firstExInDay = false;
        }
      }
    }
  }

  lines.push('');

  // 注意事项
  const caution = sd.caution || '';
  if (caution) {
    lines.push('**⚠️ 注意事项**');
    lines.push(`> ${caution}`);
  }

  return lines.join('\n');
}

/** 检查 structured_data 是否有足够的数据来渲染完整内容 */
function hasRenderableStructuredData(section: SectionOutput): boolean {
  const sd = section.structured_data || {};
  if (section.index === 3) {
    const ets = sd.exercise_types;
    return Array.isArray(ets) && ets.length > 0;
  }
  if (section.index === 4) {
    const phases = sd.phases;
    if (!Array.isArray(phases) || phases.length === 0) return false;
    return phases.some(
      (p: Record<string, any>) => Array.isArray(p.weeks) && p.weeks.length > 0
    );
  }
  return false;
}

/**
 * 获取 Section 的展示内容：
 * - S3/S4：永远从 structured_data 渲染，数据不完整时显示明确提示
 * - 其他节直接使用 content
 */
export function getDisplayContent(section: SectionOutput): string {
  if (section.index === 3) {
    if (hasRenderableStructuredData(section)) {
      return renderS3Markdown(section.structured_data);
    }
    return '> 运动推荐数据生成不完整，建议重试';
  }
  if (section.index === 4) {
    if (hasRenderableStructuredData(section)) {
      return renderS4Markdown(section.structured_data);
    }
    return '> 方案数据生成不完整，建议重试';
  }
  return section.content;
}
