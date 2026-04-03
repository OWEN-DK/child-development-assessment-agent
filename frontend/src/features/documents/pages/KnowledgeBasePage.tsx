import React, { useCallback } from 'react';
import { Card, Typography, Space, App, Button } from 'antd';
import { CloudSyncOutlined } from '@ant-design/icons';
import { useDocumentManagement } from '../hooks/useDocumentManagement';
import { DocumentUploader } from '../../../components/documents/DocumentUploader';
import { DocumentList } from '../../../components/documents/DocumentList';
import { TaskProgressList } from '../../../components/documents/TaskProgressList';
import type { UploadTaskStatus } from '../../../api/documents/types';
import styles from './KnowledgeBasePage.module.scss';

const { Title, Text } = Typography;

const KnowledgeBasePage: React.FC = () => {
  const { message } = App.useApp();
  const {
    documents,
    loading,
    ragStatus,
    processingTasks,
    loadDocuments,
    loadRagStatus,
    handleCancel,
  } = useDocumentManagement();

  const handleUploadStart = useCallback((_task: UploadTaskStatus) => {
    // 任务已在 DocumentUploader 中添加到列表
  }, []);

  const handleUploadSuccess = useCallback(async () => {
    await loadDocuments();
    await loadRagStatus();
  }, [loadDocuments, loadRagStatus]);

  const handleCancelTask = useCallback(async (taskId: string) => {
    try {
      await handleCancel(taskId);
      message.info('已请求取消任务...');
    } catch (e: any) {
      message.error(`取消失败: ${e.response?.data?.detail || e.message}`);
    }
  }, [handleCancel, message]);

  const processingFilenames = new Set(processingTasks.map(t => t.filename));

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2}>知识库管理</Title>
            <Text type="secondary">
              上传儿童发展相关的PDF或EPUB书籍，系统将自动构建知识索引，为评估提供科学依据。
            </Text>
          </div>

          <Space className={styles.statusBar}>
            <Space>
              <CloudSyncOutlined style={{ color: ragStatus?.index_ready ? '#52c41a' : '#faad14' }} />
              <Text strong={ragStatus?.index_ready} type={ragStatus?.index_ready ? 'success' : 'warning'}>
                {ragStatus?.index_ready ? '索引已就绪' : '索引未就绪，请上传文档'}
              </Text>
            </Space>
            <Text type="secondary">已上传文档: {documents.length} 个</Text>
          </Space>

          <DocumentUploader
            onUploadStart={handleUploadStart}
            onSuccess={handleUploadSuccess}
          />

          <TaskProgressList
            tasks={processingTasks}
            onCancel={handleCancelTask}
          />
        </Space>
      </Card>

      <Card
        title="文档列表"
        className={styles.listCard}
        extra={
          <Button
            onClick={loadDocuments}
            loading={loading}
            size="small"
          >
            刷新
          </Button>
        }
      >
        <DocumentList
          documents={documents}
          loading={loading}
          onRefresh={loadDocuments}
          excludeFilenames={processingFilenames}
        />
      </Card>
    </div>
  );
};

export default KnowledgeBasePage;
