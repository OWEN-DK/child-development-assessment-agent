import React from 'react';
import { Typography } from 'antd';
import type { Citation } from '../types';

const { Title, Text, Paragraph } = Typography;

interface Props {
  citations: Citation[];
}

export const CitationsList: React.FC<Props> = ({ citations }) => {
  if (!citations.length) return null;

  return (
    <div style={{ marginTop: 32, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
      <Title level={4}>参考文献</Title>
      {citations.map((c) => (
        <div
          key={c.citation_id}
          id={`cite-${c.citation_id}`}
          style={{ marginBottom: 12 }}
        >
          <Text>
            [{c.citation_id}] {c.book_title}, {c.chapter}
            {c.section ? `, ${c.section}` : ''}
          </Text>
          <br />
          <Paragraph
            style={{ marginLeft: 16, color: '#666' }}
            ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
          >
            {c.excerpt}
          </Paragraph>
        </div>
      ))}
    </div>
  );
};
