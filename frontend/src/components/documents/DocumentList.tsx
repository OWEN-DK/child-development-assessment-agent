import React from 'react';
import { useNavigate } from 'react-router-dom';
import { List, Button, Space, Typography, App } from 'antd';
import { DeleteOutlined, FileTextOutlined } from '@ant-design/icons';
import type { DocumentRecord } from '../../api/documents/types';
import { deleteDocument } from '../../api/documents';
import { formatDateTime } from '../../utils/formatters';

interface DocumentListProps {
  documents: DocumentRecord[];
  loading: boolean;
  onRefresh: () => void;
  excludeFilenames?: Set<string>;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  loading,
  onRefresh,
  excludeFilenames = new Set(),
}) => {
  const navigate = useNavigate();
  const { modal, message } = App.useApp();

  const handleDelete = (doc: DocumentRecord) => {
    modal.confirm({
      title: '确认删除',
      content: `确定要删除文档 "${doc.file_name}" 吗？删除后无法恢复。`,
      onOk: async () => {
        try {
          await deleteDocument(doc.file_name);
          message.success('删除成功');
          onRefresh();
        } catch (e: any) {
          message.error(`删除失败: ${e.response?.data?.detail || e.message}`);
        }
      },
    });
  };

  const filteredDocuments = documents.filter(
    doc => !excludeFilenames.has(doc.file_name)
  );

  return (
    <List
      loading={loading}
      dataSource={filteredDocuments}
      renderItem={(doc) => (
        <List.Item
          actions={[
            <Button
              type="link"
              icon={<FileTextOutlined />}
              onClick={() => navigate(`/book-chunks/${doc.file_hash}/${encodeURIComponent(doc.file_name)}`)}
            >
              查看分块
            </Button>,
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDelete(doc)}
            >
              删除
            </Button>,
          ]}
        >
          <List.Item.Meta
            title={doc.file_name}
            description={
              <Space>
                <Typography.Text type="secondary">共 {doc.total_pages} 页</Typography.Text>
                <Typography.Text type="secondary">
                  上传时间: {formatDateTime(doc.uploaded_at)}
                </Typography.Text>
              </Space>
            }
          />
        </List.Item>
      )}
      locale={{
        emptyText: '暂无上传的文档',
      }}
    />
  );
};
