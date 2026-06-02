import React, { useMemo } from 'react';
import { Tag, Typography } from 'antd';
import type { Citation } from '../types';

const { Title, Text, Paragraph } = Typography;

/** 引用条目附带所属节号，用于按节分组展示 */
interface CitationWithSection extends Citation {
  _section_index: number;
}

/** 节标签颜色 */
const SECTION_COLORS: Record<number, string> = {
  1: 'blue', 2: 'orange', 3: 'red', 4: 'green', 5: 'purple',
};

interface Props {
  citations: CitationWithSection[];
}

export const CitationsList: React.FC<Props> = ({ citations }) => {
  const grouped = useMemo(() => {
    /** 按书名 → 引用列表 分组，同时去重 */
    const map = new Map<string, CitationWithSection[]>();
    const seen = new Set<string>();
    for (const c of citations) {
      // 去重 key: 书名 + 章节 + 摘要前50字
      const key = `${c.book_title}||${c.chapter}||${(c.excerpt || '').slice(0, 50)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const book = c.book_title || '未知';
      if (!map.has(book)) map.set(book, []);
      map.get(book)!.push(c);
    }
    return map;
  }, [citations]);

  if (!grouped.size) return null;

  return (
    <div style={{ marginTop: 32, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
      <Title level={4}>参考文献</Title>
      {Array.from(grouped.entries()).map(([book, cites]) => (
        <div key={book} style={{ marginBottom: 16 }}>
          <Title level={5} style={{ marginBottom: 4 }}>{book}</Title>
          {cites.map((c) => (
            <div
              key={c.citation_id}
              id={`cite-${c.citation_id}`}
              style={{ marginBottom: 8, paddingLeft: 12 }}
            >
              <Text>
                <Tag
                  color={SECTION_COLORS[c._section_index] || 'default'}
                  style={{ fontSize: 11, lineHeight: '18px', padding: '0 4px', marginRight: 4 }}
                >
                  S{c._section_index}
                </Tag>
                [{c.citation_id}] {c.chapter}
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
      ))}
    </div>
  );
};
