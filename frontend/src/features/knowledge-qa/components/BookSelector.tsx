import React from 'react';
import { Select } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@shared/api/client';

interface BookOption {
  id: string;
  title: string;
  author: string | null;
}

interface Props {
  value?: string[];
  onChange?: (bookIds: string[]) => void;
}

export const BookSelector: React.FC<Props> = ({ value, onChange }) => {
  const { data: books } = useQuery({
    queryKey: ['knowledge-books'],
    queryFn: () =>
      apiClient.get('/api/v1/rag/documents').then((r) => {
        const docs = r.data.data?.documents ?? [];
        return docs.map(
          (d: any): BookOption => ({
            id: d.file_hash,
            title: d.file_name,
            author: d.author ?? null,
          }),
        );
      }),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Select
      mode="multiple"
      placeholder="可选：指定参考书籍（留空则自动匹配）"
      value={value}
      onChange={onChange}
      style={{ width: '100%', marginTop: 8 }}
      options={
        books?.map((b: BookOption) => ({
          value: b.id,
          label: `${b.title}${b.author ? ` (${b.author})` : ''}`,
        })) ?? []
      }
      allowClear
      maxTagCount={3}
    />
  );
};
