import React, { useMemo } from 'react';
import { Tag } from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import type { SectionOutput } from '../types';
import { getDisplayContent } from '../utils/renderMarkdown';

interface Props {
  section: SectionOutput;
}

/** 节标题配置：序号标签 + 颜色 */
const SECTION_CONFIG: Record<number, { color: string }> = {
  1: { color: 'blue' },
  2: { color: 'orange' },
  3: { color: 'red' },
  4: { color: 'green' },
  5: { color: 'purple' },
};

export const SectionRenderer: React.FC<Props> = ({ section }) => {
  const displayContent = useMemo(
    () => getDisplayContent(section),
    [section],
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
          rehypePlugins={[rehypeSanitize]}
          disallowedElements={['img', 'script']}
          components={{
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
