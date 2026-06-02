import React, { useMemo } from 'react';
import { Tag, Tooltip } from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import type { Citation, SectionOutput } from '../types';
import { getDisplayContent } from '../utils/renderMarkdown';

interface Props {
  section: SectionOutput;
  /** 所有节的引用列表，用于在正文中显示引用来源书名 */
  allCitations?: Citation[];
}

/** 缩写书名：超过 6 字取前 6 字 + … */
function abbreviateBook(title: string): string {
  return title.length > 6 ? title.slice(0, 6) + '…' : title;
}

/**
 * 将正文中的 [C00X] 替换为带书名的内联引用标记。
 *
 * 渲染效果：C001《运动改变大脑》
 * - 上标编号 + 灰色小字书名缩写
 * - 整体可点击跳转到底部参考文献
 * - hover 时显示完整书名
 *
 * 使用 HTML 标签（span + sup），由 rehype-sanitize 白名单放行。
 */
function linkifyCitations(
  content: string,
  citationBookMap: Map<string, string>,
): string {
  return content.replace(
    /\[(C\d+)\]/g,
    (_, id: string) => {
      const book = citationBookMap.get(id);
      if (book) {
        const abbr = abbreviateBook(book);
        // span.cite-inline 由自定义 a 组件渲染为带样式的引用标记
        return `[<span class="cite-inline"><sup>${id}</sup>《${abbr}》</span>](#cite-${id})`;
      }
      return `[<sup>${id}</sup>](#cite-${id})`;
    },
  );
}

/** 构建 citation_id → book_title 映射 */
function buildCitationBookMap(citations?: Citation[]): Map<string, string> {
  const map = new Map<string, string>();
  if (!citations) return map;
  for (const c of citations) {
    if (c.citation_id && c.book_title) {
      map.set(c.citation_id, c.book_title);
    }
  }
  return map;
}

/** 节标题配置：序号标签 + 颜色 */
const SECTION_CONFIG: Record<number, { color: string }> = {
  1: { color: 'blue' },
  2: { color: 'orange' },
  3: { color: 'red' },
  4: { color: 'green' },
  5: { color: 'purple' },
};

/** rehype-sanitize 白名单：放行 span[class]（引用标记需要） */
const SANITIZE_SCHEMA = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames || []), 'span', 'sup'],
  attributes: {
    ...defaultSchema.attributes,
    span: ['className', 'title'],
    sup: [],
  },
};

export const SectionRenderer: React.FC<Props> = ({ section, allCitations }) => {
  const citationBookMap = useMemo(
    () => buildCitationBookMap(allCitations),
    [allCitations],
  );
  const displayContent = useMemo(
    () => linkifyCitations(getDisplayContent(section), citationBookMap),
    [section, citationBookMap],
  );

  const config = SECTION_CONFIG[section.index] || { color: 'default' };

  const borderColor = { 1: '#1890ff', 2: '#fa8c16', 3: '#f5222d', 4: '#52c41a', 5: '#722ed1' }[section.index] || '#d9d9d9';

  return (
    <div
      style={{
        marginBottom: 24,
        padding: '20px 24px',
        borderRadius: 12,
        border: `1px solid ${borderColor}20`,
        background: '#fff',
        boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
        transition: 'box-shadow 0.2s',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = '0 1px 4px rgba(0,0,0,0.04)';
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 16,
          paddingBottom: 12,
          borderBottom: `2px solid ${borderColor}20`,
        }}
      >
        <Tag color={config.color} style={{ margin: 0, fontSize: 14, fontWeight: 600, padding: '2px 10px' }}>
          S{section.index}
        </Tag>
        <span style={{ fontSize: 16, fontWeight: 700, color: '#1a1a1a' }}>
          {section.title}
        </span>
      </div>
      <div style={{ paddingLeft: 4, lineHeight: 1.8 }}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[[rehypeSanitize, SANITIZE_SCHEMA]]}
          disallowedElements={['img', 'script']}
          components={{
            a: ({ href, children }) => {
              // 引用锚链接：#cite-C00X → 渲染为内联引用标记
              if (href && href.startsWith('#cite-')) {
                const citationId = href.replace('#cite-', '');
                const bookTitle = citationBookMap.get(citationId);
                const inner = (
                  <a
                    href={href}
                    style={{
                      color: 'inherit',
                      textDecoration: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    {children}
                  </a>
                );
                // 有完整书名时加 hover tooltip
                if (bookTitle) {
                  return (
                    <Tooltip title={bookTitle} placement="top">
                      <span
                        style={{
                          display: 'inline',
                          background: `${borderColor}12`,
                          borderBottom: `1px dashed ${borderColor}`,
                          padding: '1px 4px',
                          borderRadius: 3,
                          margin: '0 1px',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {inner}
                      </span>
                    </Tooltip>
                  );
                }
                return inner;
              }
              return <a href={href}>{children}</a>;
            },
            // 放行 linkifyCitations 注入的 <sup> 和 <span>
            sup: ({ children }) => <sup style={{ color: borderColor, fontWeight: 600, fontSize: '0.75em' }}>{children}</sup>,
            span: ({ className, children, ...rest }) => {
              if (className === 'cite-inline') {
                return <>{children}</>;
              }
              return <span {...(rest as React.HTMLAttributes<HTMLSpanElement>)} className={className}>{children}</span>;
            },
            h2: ({ children }) => (
              <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 24, marginBottom: 12, color: '#262626', borderBottom: '1px solid #f0f0f0', paddingBottom: 8 }}>
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 style={{ fontSize: 16, fontWeight: 600, marginTop: 20, marginBottom: 10, color: '#434343' }}>
                {children}
              </h3>
            ),
            h4: ({ children }) => (
              <h4 style={{ fontSize: 15, fontWeight: 600, marginTop: 16, marginBottom: 8, color: '#595959' }}>
                {children}
              </h4>
            ),
            blockquote: ({ children }) => (
              <blockquote
                style={{
                  borderLeft: `3px solid ${borderColor}`,
                  background: `${borderColor}08`,
                  padding: '10px 16px',
                  margin: '12px 0',
                  borderRadius: '0 6px 6px 0',
                  color: '#555',
                }}
              >
                {children}
              </blockquote>
            ),
            table: ({ children }) => (
              <div style={{ overflowX: 'auto', margin: '12px 0' }}>
                <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 14 }}>
                  {children}
                </table>
              </div>
            ),
            thead: ({ children }) => (
              <thead style={{ background: `${borderColor}10` }}>
                {children}
              </thead>
            ),
            th: ({ children }) => (
              <th style={{ border: '1px solid #e8e8e8', padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td style={{ border: '1px solid #f0f0f0', padding: '8px 12px', verticalAlign: 'top' }}>
                {children}
              </td>
            ),
            hr: () => (
              <hr style={{ border: 'none', borderTop: '1px dashed #e8e8e8', margin: '20px 0' }} />
            ),
            strong: ({ children }) => (
              <strong style={{ color: '#262626', fontWeight: 600 }}>{children}</strong>
            ),
          }}
        >
          {displayContent}
        </ReactMarkdown>
      </div>
    </div>
  );
};
