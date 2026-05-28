/** 从 S3/S4 structured_data 渲染 Markdown 展示 */

import type { SectionOutput } from '../types';

/** S3 运动类型推荐 Markdown 渲染 */
export function renderS3Markdown(structuredData: Record<string, any>): string {
  const sd = structuredData || {};
  const ets = sd.exercise_types || [];
  if (!Array.isArray(ets) || ets.length === 0) return '';

  const lines: string[] = [];
  const childAge = sd.child_age_group || '';
  if (childAge) {
    lines.push(`> 适用年龄段：**${childAge}**`);
    lines.push('');
  }

  const tierLabels: Record<string, string> = {
    primary: '🔴 核心推荐',
    secondary: '🟡 辅助推荐',
    supplementary: '🟢 补充推荐',
  };

  for (const et of ets) {
    const name = et.name || '';
    const tier = tierLabels[et.tier] || et.tier || '';
    const rationale = (et.recommendation_rationale || '').slice(0, 200);
    const typeId = et.type_id || '';
    const category = et.category || '';
    const skills = (et.target_skills || []).join('、');
    const citations = (et.citation_ids || []).join(', ');

    lines.push(`### ${name}`);
    if (tier) lines.push(`**等级**: ${tier}`);
    if (typeId) lines.push(`**类型ID**: \`${typeId}\``);
    if (category) lines.push(`**分类**: ${category}`);
    if (skills) lines.push(`**训练目标**: ${skills}`);
    if (rationale) lines.push(`> ${rationale}`);
    if (citations) lines.push(`*引用: ${citations}*`);
    lines.push('');
  }

  return lines.join('\n');
}

/** S4 运动方案 Markdown 渲染 */
export function renderS4Markdown(structuredData: Record<string, any>): string {
  const sd = structuredData || {};
  const phases = sd.phases || [];
  const lines: string[] = [];

  // 方案总览
  const ps = sd.plan_summary || {};
  if (ps.total_duration_days) {
    lines.push(
      `> **方案总览**：共 ${ps.total_duration_days} 天，` +
        `${ps.total_phases || '?'} 个阶段，` +
        `每天约 ${ps.daily_duration_min || '?'} 分钟，` +
        `每周 ${ps.weekly_frequency || '?'} 天`
    );
    lines.push('');
  }

  // 如果没有 phases 数据，只渲染摘要
  if (phases.length === 0) {
    const caution = sd.caution || '';
    if (caution) {
      lines.push('### ⚠️ 注意事项');
      lines.push(`> ${caution}`);
      lines.push('');
    }
    return lines.join('\n');
  }

  // 阶段 & 周 & 天 & 运动
  for (let pi = 0; pi < phases.length; pi++) {
    const phase = phases[pi];
    const phaseName = phase.phase_name || `第${pi + 1}阶段`;
    const goal = phase.goal || '';
    lines.push(`### 第${pi + 1}阶段：${phaseName}`);
    if (goal) lines.push(`> ${goal}`);
    lines.push('');

    const weeks = phase.weeks || [];
    for (const week of weeks) {
      const weekIdx = week.week_index || 1;
      const focus = week.focus || '';
      lines.push(`#### 第${weekIdx}周`);
      if (focus) lines.push(`**本周重点**：${focus}`);
      lines.push('');

      const days = week.days || [];
      for (const day of days) {
        const dayIdx = day.day_index || 1;
        const dayLabel = day.day_label || `第${dayIdx}天`;
        const exercises = day.main_exercises || [];

        if (exercises.length === 0) {
          lines.push(`**${dayLabel}**：休息日`);
          lines.push('');
          continue;
        }

        // Warmup
        const warmup = day.warmup || {};
        if (warmup.activity) {
          lines.push(`**${dayLabel}**`);
          lines.push(
            `- 🏃 热身：${warmup.activity}（${warmup.duration_min || 0}分钟）`
          );
        } else {
          lines.push(`**${dayLabel}**`);
        }

        // Main exercises
        for (const ex of exercises) {
          const name = ex.name || '未命名';
          const duration = ex.duration_min || 0;
          const intensity = ex.intensity || '';
          const intensityHint = ex.intensity_hint || '';
          const sets = ex.sets;
          const reps = ex.reps;
          const notes = ex.notes || '';

          const params: string[] = [];
          if (duration) params.push(`${duration}分钟`);
          if (intensity) {
            const hint = intensityHint ? `（${intensityHint}）` : '';
            params.push(`${intensity}${hint}`);
          }
          if (sets) params.push(`${sets}组`);
          if (reps) params.push(`${reps}`);

          let line = `- 🎯 **${name}**`;
          if (params.length > 0) line += ` — ${params.join(' · ')}`;
          lines.push(line);

          if (notes) lines.push(`  > ${notes}`);
        }

        // Cooldown
        const cooldown = day.cooldown || {};
        if (cooldown.activity) {
          lines.push(
            `- 🧘 放松：${cooldown.activity}（${cooldown.duration_min || 0}分钟）`
          );
        }

        const total = day.total_duration_min || 0;
        if (total) lines.push(`  *当日总计：约${total}分钟*`);
        lines.push('');
      }
    }
  }

  // 注意事项
  const caution = sd.caution || '';
  if (caution) {
    lines.push('### ⚠️ 注意事项');
    lines.push(`> ${caution}`);
    lines.push('');
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
    return Array.isArray(phases) && phases.length > 0;
  }
  return false;
}

/**
 * 获取 Section 的展示内容：
 * - S3/S4：优先从 structured_data 渲染，数据不完整时 fallback 到 content
 * - 其他节直接使用 content
 */
export function getDisplayContent(section: SectionOutput): string {
  if (section.index === 3 || section.index === 4) {
    if (hasRenderableStructuredData(section)) {
      return section.index === 3
        ? renderS3Markdown(section.structured_data)
        : renderS4Markdown(section.structured_data);
    }
    // fallback: structured_data 不完整，直接显示 content（可能是未精简的旧数据或大纲）
    if (section.content && section.content.length > 80) {
      return section.content;
    }
    // content 也精简了但 structured_data 不完整 → 显示摘要
    return section.content || '';
  }
  return section.content;
}
