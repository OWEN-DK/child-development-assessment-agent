import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Space, Typography, App, Flex, Spin, Empty } from 'antd';
import { DeleteOutlined, FileTextOutlined, WarningOutlined } from '@ant-design/icons';
import type { DocumentRecord } from '../../api/documents/types';
import { deleteDocument, getDocumentBindings } from '../../api/documents';
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

  const handleDelete = async (doc: DocumentRecord) => {
    // 先查询绑定状态
    let bindings;
    try {
      bindings = await getDocumentBindings(doc.file_name);
    } catch {
      // 查询失败时降级为直接删除确认
      modal.confirm({
        title: '确认删除',
        content: `确定要删除文档 "${doc.file_name}" 吗？删除后无法恢复。`,
        onOk: async () => {
          try {
            await deleteDocument(doc.file_name);
            notification.success('删除成功');
            onRefresh();
          } catch (e: any) {
            notification.error(`删除失败: ${extractApiError(e).message}`);
          }
        },
      });
      return;
    }

    if (!bindings.has_bindings) {
      // 无绑定，直接删除
      modal.confirm({
        title: '确认删除',
        content: `确定要删除文档 "${doc.file_name}" 吗？删除后无法恢复。`,
        onOk: async () => {
          try {
            await deleteDocument(doc.file_name);
            notification.success('删除成功');
            onRefresh();
          } catch (e: any) {
            notification.error(`删除失败: ${extractApiError(e).message}`);
          }
        },
      });
      return;
    }

    // 有绑定，显示详细提示
    const { entities, relations, communities } = bindings.bindings;
    modal.confirm({
      title: '文档存在知识图谱绑定',
      icon: <WarningOutlined style={{ color: '#faad14' }} />,
      content: (
        <div>
          <p>文档 <strong>{doc.file_name}</strong> 已绑定知识图谱数据：</p>
          <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
            {entities > 0 && <li>实体：{entities} 个</li>}
            {relations > 0 && <li>关系：{relations} 条</li>}
            {communities > 0 && <li>社区节点：{communities} 个</li>}
          </ul>
          <p style={{ color: '#ff4d4f', marginTop: 8 }}>
            直接删除将同时清除所有绑定的图谱数据，此操作不可恢复。
          </p>
        </div>
      ),
      okText: '同时删除文档和图谱数据',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteDocument(doc.file_name, true);
          notification.success('文档和图谱数据已全部删除');
          onRefresh();
        } catch (e: any) {
          notification.error(`删除失败: ${extractApiError(e).message}`);
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
