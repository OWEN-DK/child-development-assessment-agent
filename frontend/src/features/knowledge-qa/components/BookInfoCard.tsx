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
        <>
          <BookOutlined /> 参考书籍
        </>
      }
      style={{ marginBottom: 16 }}
    >
      {books.map((book) => (
        <div key={book.book_id} style={{ marginBottom: 8 }}>
          <Text strong>{book.title}</Text>
          {book.author && <Text type="secondary"> — {book.author}</Text>}
          {book.is_primary && (
            <Tag color="blue" style={{ marginLeft: 8 }}>
              主参考
            </Tag>
          )}
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {book.match_reason}
          </Text>
        </div>
      ))}
    </Card>
  );
};
