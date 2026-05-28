import { useCallback } from 'react';
import type { KnowledgeQAResponse, SectionOutput } from '../types';
import { renderS3Markdown, renderS4Markdown } from '../utils/renderMarkdown';

/** 根据 KnowledgeQAResponse 构建 Markdown 字符串 */
export function buildMarkdown(result: KnowledgeQAResponse): string {
  const parts: string[] = [];

  parts.push('# 知识问答报告\n');
  parts.push(`**问题**: ${result.question}\n`);

  if (result.matched_books.length > 0) {
    parts.push('\n## 参考书籍\n');
    for (const b of result.matched_books) {
      const author = b.author ? ` (${b.author})` : '';
      parts.push(`- **${b.title}**${author} — ${b.match_reason}\n`);
    }
  }

  for (const sec of result.sections) {
    const displayContent = getSectionMarkdown(sec);
    parts.push(`\n${displayContent}\n`);
    if (sec.citations.length > 0) {
      parts.push('\n### 本节引用\n');
      for (const c of sec.citations) {
        const section = c.section ? `, ${c.section}` : '';
        parts.push(
          `- [${c.citation_id}] ${c.book_title}, ${c.chapter}${section}\n` +
            `  > ${c.excerpt}\n`,
        );
      }
    }
  }

  return parts.join('\n');
}

/** 检查 structured_data 是否有足够的数据来渲染完整内容 */
function hasRenderableData(sec: SectionOutput): boolean {
  const sd = sec.structured_data || {};
  if (sec.index === 3) {
    const ets = sd.exercise_types;
    return Array.isArray(ets) && ets.length > 0;
  }
  if (sec.index === 4) {
    const phases = sd.phases;
    return Array.isArray(phases) && phases.length > 0;
  }
  return false;
}

/** 获取 Section 用于 Markdown 下载的完整内容 */
function getSectionMarkdown(sec: SectionOutput): string {
  if (sec.index === 3) {
    if (hasRenderableData(sec)) {
      return renderS3Markdown(sec.structured_data);
    }
    // fallback: 旧数据 content 可能还是完整 Markdown
    return sec.content && sec.content.length > 80 ? sec.content : '';
  }
  if (sec.index === 4) {
    if (hasRenderableData(sec)) {
      return renderS4Markdown(sec.structured_data);
    }
    // fallback: 旧数据 content 可能还是完整 Markdown
    return sec.content && sec.content.length > 80 ? sec.content : '';
  }
  return sec.content;
}

/** 触发浏览器下载 */
function triggerDownload(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function useReportDownload(result: KnowledgeQAResponse | null) {
  const downloadMarkdown = useCallback(() => {
    if (!result) return;
    const md = buildMarkdown(result);
    triggerDownload(md, `report-${Date.now()}.md`, 'text/markdown; charset=utf-8');
  }, [result]);

  const downloadJSON = useCallback(() => {
    if (!result) return;
    const json = JSON.stringify(result, null, 2);
    triggerDownload(json, `report-${Date.now()}.json`, 'application/json; charset=utf-8');
  }, [result]);

  return { downloadMarkdown, downloadJSON };
}
