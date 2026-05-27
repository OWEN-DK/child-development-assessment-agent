import { useCallback } from 'react';
import type { KnowledgeQAResponse } from '../types';

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
    parts.push(`\n${sec.content}\n`);
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

  return { downloadMarkdown };
}
