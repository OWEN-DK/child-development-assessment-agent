import React from 'react';
import { Card, Tag, Typography } from 'antd';
import { BookOutlined } from '@ant-design/icons';
import type { MatchedBook } from '../types';

const { Text } = Typography;

interface Props {
  books: MatchedBook[];
}

export const BookInfoCard: React.FC<Props> = ({ books }) => {
  if (!books.length) return null;

  return (
    <Card
      size="small"
      title={
        <span style={{ fontSize: 15, fontWeight: 600 }}>
          <BookOutlined style={{ marginRight: 6 }} />
          参考书籍（{books.length} 本）
        </span>
      }
      style={{
        marginBottom: 20,
        borderRadius: 10,
        border: '1px solid #e6f4ff',
        background: '#fafcff',
      }}
    >
      {books.map((book, i) => (
        <div
          key={book.book_id}
          style={{
            marginBottom: i < books.length - 1 ? 12 : 0,
            paddingBottom: i < books.length - 1 ? 12 : 0,
            borderBottom: i < books.length - 1 ? '1px solid #f0f0f0' : 'none',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 28 }}>{i === 0 ? '📖' : '📚'}</span>
            <div>
              <Text strong style={{ fontSize: 14 }}>{book.title}</Text>
              {book.author && <Text type="secondary" style={{ fontSize: 12 }}> — {book.author}</Text>}
              {book.is_primary && (
                <Tag color="blue" style={{ marginLeft: 8, fontSize: 11 }}>
                  ⭐ 主要参考
                </Tag>
              )}
            </div>
          </div>
          <Text type="secondary" style={{ fontSize: 12, paddingLeft: 38, display: 'block' }}>
            {book.match_reason}
          </Text>
        </div>
      ))}
    </Card>
  );
};
