import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Space, Typography, App, Flex, Spin, Empty } from 'antd';
import { DeleteOutlined, FileTextOutlined } from '@ant-design/icons';
import type { DocumentRecord } from '../../api/documents/types';
import { deleteDocument } from '../../api/documents';
import { formatDateTime } from '@shared/lib/formatters';
import { extractApiError, notification } from '@shared/lib/notification';

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
  const { modal } = App.useApp();

  const handleDelete = (doc: DocumentRecord) => {
    modal.confirm({
      title: '确认删除',
      content: `确定要删除文档 "${doc.file_name}" 吗？删除后无法恢复。`,
      onOk: async () => {
        try {
          await deleteDocument(doc.file_name);
          notification.success('删除成功');
          onRefresh();
        } catch (e: any) {
          const apiError = extractApiError(e);
          notification.error(`删除失败: ${apiError.message}`);
        }
      },
    });
  };

  const filteredDocuments = documents.filter(
    doc => !excludeFilenames.has(doc.file_name)
  );

  if (loading) {
    return <div style={{ padding: '40px 0', textAlign: 'center' }}><Spin size="large" /></div>;
  }

  if (filteredDocuments.length === 0) {
    return <Empty description="暂无上传的文档" />;
  }

  return (
    <Flex vertical gap={16}>
      {filteredDocuments.map((doc) => (
        <Card
          key={doc.file_hash}
          styles={{ body: { padding: '16px 24px' } }}
        >
          <Flex justify="space-between" align="center">
            <div>
              <Typography.Title level={5} style={{ margin: 0, marginBottom: 8 }}>
                {doc.file_name}
              </Typography.Title>
              <Space>
                <Typography.Text type="secondary">共 {doc.total_pages} 页</Typography.Text>
                <Typography.Text type="secondary">
                  上传时间: {formatDateTime(doc.uploaded_at)}
                </Typography.Text>
              </Space>
            </div>
            <Space>
              <Button
                type="link"
                icon={<FileTextOutlined />}
                onClick={() => navigate(`/book-chunks/${doc.file_hash}/${encodeURIComponent(doc.file_name)}`)}
              >
                查看分块
              </Button>
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(doc)}
              >
                删除
              </Button>
            </Space>
          </Flex>
        </Card>
      ))}
    </Flex>
  );
};
