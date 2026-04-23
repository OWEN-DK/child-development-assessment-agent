import React, { useCallback } from 'react';
import { Card, Typography, Space, Button } from 'antd';
import { CloudSyncOutlined } from '@ant-design/icons';
import { useDocumentManagement } from '../hooks/useDocumentManagement';
import { DocumentUploader } from '../../../components/documents/DocumentUploader';
import { DocumentList } from '../../../components/documents/DocumentList';
import { ProgressList } from '../../../components/progress';
import { documentUploadConfig, adaptUploadTask, type AdaptedUploadTask } from '../../../components/progress/configs/documentUpload';
import type { UploadTaskStatus } from '../../../api/documents/types';
import { extractApiError, notification } from '@shared/lib/notification';
import styles from './KnowledgeBasePage.module.scss';

const { Title, Text } = Typography;

const KnowledgeBasePage: React.FC = () => {
  const {
    documents,
    loading,
    ragStatus,
    processingTasks,
    loadDocuments,
    loadRagStatus,
    loadTasks,
    handleCancel,
    addTask,
  } = useDocumentManagement();

  const handleUploadStart = useCallback((task: UploadTaskStatus) => {
    addTask(task);
  }, [addTask]);

  const handleUploadSuccess = useCallback(async () => {
    await loadDocuments();
    await loadRagStatus();
    await loadTasks();
  }, [loadDocuments, loadRagStatus, loadTasks]);

  const handleCancelTask = useCallback(async (taskId: string) => {
    try {
      await handleCancel(taskId);
      notification.info('已请求取消任务...');
    } catch (e: any) {
      const apiError = extractApiError(e);
      notification.error(`取消失败: ${apiError.message}`);
    }
  }, [handleCancel]);

  // 适配任务数据格式
  const adaptedTasks: AdaptedUploadTask[] = processingTasks.map(adaptUploadTask);

  const processingFilenames = new Set(
    processingTasks
      .filter(t => t.status !== 'completed')
      .map(t => t.filename)
  );

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

          <ProgressList
            config={{
              ...documentUploadConfig,
              onCancel: async (task) => {
                await handleCancelTask(task.taskId);
              },
              onDelete: async (task) => {
                try {
                  const { deleteTask } = await import('../../../api/documents');
                  await deleteTask(task.taskId);
                  notification.success('删除成功');
                  loadDocuments();
                  loadTasks();
                } catch (e: any) {
                  const apiError = extractApiError(e);
                  notification.error(`删除失败: ${apiError.message}`);
                }
              },
            }}
            tasks={adaptedTasks}
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
