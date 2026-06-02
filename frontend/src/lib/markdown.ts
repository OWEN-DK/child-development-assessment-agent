/**
 * Strip YAML frontmatter from markdown content.
 * Handles:
 * 1. Frontmatter at the start of the string
 * 2. Intermediate frontmatter blocks between chapters (--- ... ---)
 */
export function stripFrontmatter(content: string): string {
  if (!content) return content;

  // Strip ALL frontmatter blocks: YAML between --- markers
  // Matches: --- \n YAML lines \n --- (with optional trailing newline)
  // Also handles consecutive --- blocks that appear between chapters
  let result = content;

  // First pass: strip leading frontmatter
  const leadingFm = /^---\s*\n[\s\S]*?\n---\s*\n?/;
  const leadingMatch = result.match(leadingFm);
  if (leadingMatch) {
    result = result.slice(leadingMatch[0].length);
  }

  // Second pass: strip intermediate frontmatter blocks (between chapters)
  // These appear as: \n---\nbook_id: ...\n---\n
  result = result.replace(/\n---\s*\n[\s\S]*?\n---\s*\n/g, '\n\n');

  return result.trim();
}

/**
 * Relation type enum → Chinese label mapping
 */
const RELATION_TYPE_LABELS: Record<string, string> = {
  // 因果
  CAUSAL_CAUSES: '导致',
  CAUSAL_LEADS_TO: '导向',
  CAUSAL_RESULTS_IN: '产生',
  CAUSAL_CONTRIBUTES_TO: '促成',
  CAUSAL_TRIGGERS: '触发',
  CAUSAL_ALLEVIATES: '缓解',
  // 治疗/干预
  THERAPEUTIC_TREATS: '治疗',
  THERAPEUTIC_PREVENTS: '预防',
  THERAPEUTIC_ALLEVIATES: '缓解',
  THERAPEUTIC_IMPROVES: '改善',
  THERAPEUTIC_INHIBITS: '抑制',
  THERAPEUTIC_ENHANCES: '增强',
  // 结构
  STRUCTURAL_PART_OF: '是…的一部分',
  STRUCTURAL_CONTAINS: '包含',
  STRUCTURAL_CONSISTS_OF: '由…组成',
  STRUCTURAL_BELONGS_TO: '属于',
  // 功能
  FUNCTIONAL_REGULATES: '调节',
  FUNCTIONAL_MODULATES: '调制',
  FUNCTIONAL_PARTICIPATES_IN: '参与',
  FUNCTIONAL_INVOLVED_IN: '涉及',
  FUNCTIONAL_PLAYS_ROLE_IN: '在…中发挥作用',
  FUNCTIONAL_MEDIATES: '介导',
  FUNCTIONAL_TRANSFORMS: '转化为',
  FUNCTIONAL_SECRETES: '分泌',
  FUNCTIONAL_USED_FOR: '用于',
  FUNCTIONAL_STUDIES: '研究',
  // 证据
  EVIDENCE_SUPPORTS: '支持',
  EVIDENCE_PROVEN_BY: '被…证明',
  EVIDENCE_BASED_ON: '基于',
  EVIDENCE_CONTRADICTS: '矛盾',
  EVIDENCE_DEMONSTRATES: '演示',
  // 时间
  TEMPORAL_PRECEDES: '先于',
  TEMPORAL_FOLLOWS: '后于',
  TEMPORAL_DURING: '在…期间',
  TEMPORAL_DEVELOPS_INTO: '发展为',
  // 比较
  COMPARISON_SIMILAR_TO: '类似于',
  COMPARISON_DIFFERENT_FROM: '不同于',
  COMPARISON_ALTERNATIVE_TO: '替代',
  // 属性
  ATTRIBUTE_ASSOCIATED_WITH: '相关',
  ATTRIBUTE_HAS_PROPERTY: '具有属性',
  ATTRIBUTE_CHARACTERIZED_BY: '以…为特征',
  ATTRIBUTE_MEASURED_BY: '通过…测量',
  // 评估/诊断
  ASSESSMENT_ASSESSES: '评估',
  ASSESSMENT_DIAGNOSES: '诊断',
  ASSESSMENT_MEASURES: '测量',
  // 空间/归属
  SPATIAL_LOCATED_IN: '位于',
  SPATIAL_CONNECTS_TO: '连接',
  // 层级/分类
  HIERARCHICAL_SUBCLASS_OF: '是…的子类',
  HIERARCHICAL_INSTANCE_OF: '是…的实例',
  // 发布/创作
  AUTHORSHIP_PUBLISHED_BY: '由…发表',
  AUTHORSHIP_CITED_BY: '被…引用',
  AUTHORSHIP_COLLABORATED_WITH: '与…合作',
  // 发展里程碑
  DEVELOPMENTAL_EMERGES_AT: '出现在…阶段',
  DEVELOPMENTAL_PREREQUISITE_FOR: '是…的前提',
  // 兜底
  RELATES_TO: '关联',
};

export function preprocessCurationMarkdown(content: string): string {
  if (!content) return content;

  let result = content;

  // 1. Strip UUID from "已在 ... 提取" patterns
  // [已在 92c50c6b-4506-4ec1-9ac6-d02f3384effd_ch009 提取] → [已提取 ch009]
  // Handle multiple chapters: [已在 UUID_ch009, UUID_ch005 提取]
  result = result.replace(
    /\[已在\s+([^\]]+?)\s*提取\]/g,
    (_match, refs: string) => {
      // Extract chapter IDs from UUID_chXXX patterns
      const chapters = refs
        .split(',')
        .map((r: string) => r.trim())
        .map((r: string) => {
          const chMatch = r.match(/[0-9a-f]{8}.*?(_ch\d+)/);
          return chMatch ? chMatch[1].replace('_', '') : r;
        });
      if (chapters.length > 0) {
        return `<span class="tag tag--extracted">已提取 ${chapters.join(', ')}</span>`;
      }
      return '<span class="tag tag--extracted">已提取</span>';
    },
  );

  // 2. Make relation_type easier to read at a glance:
  //    - Render as `关联类型：中文标签（英文枚举）`
  //    - Unknown enum values get a fallback chip
  result = result.replace(
    /\*\*relation_type\*\*[：:]\s*([\w_]+)/g,
    (_match, typeValue: string) => {
      const label = RELATION_TYPE_LABELS[typeValue] || typeValue;
      const isKnown = Boolean(RELATION_TYPE_LABELS[typeValue]);
      const chipClass = isKnown ? 'tag tag--relation-type' : 'tag tag--unknown-type';
      return `**关联类型**：<span class="${chipClass}">${label}（${typeValue}）</span>`;
    },
  );

  // 3. Truncate long "本章新增来源" lists and surface count
  result = result.replace(
    /(\*\*本章新增来源\*\*[：:]\s*)(.+)/g,
    (_match, prefix: string, sources: string) => {
      const items = sources.split(',').map((s: string) => s.trim());
      if (items.length > 6) {
        const shown = items.slice(0, 6).join(', ');
        return `${prefix}${shown} <span class="tag tag--more">+${items.length - 6} 更多</span>`;
      }
      return `${prefix}${sources}`;
    },
  );

  // 4. Clean up "来源" in relation sections
  result = result.replace(
    /(\*\*(?:来源|source)\*\*[：:]\s*)(.+)/g,
    (_match, prefix: string, sources: string) => {
      const items = sources.split(',').map((s: string) => s.trim());
      if (items.length > 4) {
        const shown = items.slice(0, 4).join(', ');
        return `${prefix}${shown} <span class="tag tag--more">+${items.length - 4}</span>`;
      }
      return `${prefix}${sources}`;
    },
  );

  // 5. Show entity type with backend-aligned Chinese label
  result = result.replace(
    /\*\*entity_type\*\*[：:]\s*([\w]+)/g,
    (_match, typeValue: string) => {
      const meta = ENTITY_TYPE_LABELS[typeValue];
      const label = meta ? `${meta.icon} ${meta.label}` : typeValue;
      const chipClass = meta ? 'tag tag--entity-type' : 'tag tag--unknown-type';
      return `**实体类型**：<span class="${chipClass}">${label}（${typeValue}）</span>`;
    },
  );

  // 6. Keep evidence readable but easier to scan:
  //    - Wrap long evidence content in a compact inline quote-like style
  result = result.replace(
    /(\*\*evidence\*\*[：:]\s*)(.+)/g,
    (_match, prefix: string, value: string) => {
      const trimmed = value.length > 220 ? `${value.slice(0, 217)}…` : value;
      return `${prefix}<span class="evidence-inline">${trimmed}</span>`;
    },
  );

  // 7. Collapse verbose "段落覆盖详情" sections into a compact summary
  result = result.replace(
    /## 段落覆盖详情\n([\s\S]*?)(?=\n## |$)/g,
    (_match, body: string) => {
      const bodyLines = body.trim().split('\n');
      const covered = bodyLines.filter((l) => l.includes('✅')).length;
      const uncovered = bodyLines.filter((l) => l.includes('❌')).length;
      const total = covered + uncovered;
      const pct = total > 0 ? Math.round((covered / total) * 100) : 0;
      return `## 段落覆盖详情\n\n` +
        `<div class="coverage-summary">` +
        `<span class="tag tag--covered">✅ ${covered} 已覆盖</span> ` +
        `<span class="tag tag--uncovered">❌ ${uncovered} 未覆盖</span> ` +
        `<span class="tag tag--entity-type">${pct}%</span>` +
        `</div>\n`;
    },
  );

  return result;
}
import { ENTITY_TYPE_LABELS } from '@features/curation/hooks/useDraftEditor';
