import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import type { SectionOutput } from '../types';

interface Props {
  section: SectionOutput;
}

export const SectionRenderer: React.FC<Props> = ({ section }) => {
  return (
    <div style={{ marginBottom: 32 }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        disallowedElements={['img', 'pre', 'code', 'html', 'script']}
        components={{
          blockquote: ({ children }) => (
            <blockquote
              style={{
                borderLeft: '3px solid #1890ff',
                paddingLeft: 16,
                color: '#666',
              }}
            >
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                {children}
              </table>
            </div>
          ),
        }}
      >
        {section.content}
      </ReactMarkdown>
    </div>
  );
};
