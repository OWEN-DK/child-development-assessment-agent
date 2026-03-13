import { useState, useEffect } from 'react';
import { Upload, Button, List, Card, Typography, Space, message, Modal, Progress } from 'antd';
import { UploadOutlined, DeleteOutlined, CloudSyncOutlined, LoadingOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { uploadDocument, getDocuments, deleteDocument, getRagStatus, getUploadTaskStatus, DocumentRecord, UploadTaskStatus } from '../api/client';
import styles from './KnowledgeBasePage.module.scss';

const { Title, Text } = Typography;

const KnowledgeBasePage = () => {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ragReady, setRagReady] = useState(false);
  const [processingTasks, setProcessingTasks] = useState<UploadTaskStatus[]>([]);
  const [pollingTimer, setPollingTimer] = useState<NodeJS.Timeout | null>(null);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const res = await getDocuments();
      setDocuments(res.documents);
    } catch (e) {
      message.error('加载文档列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadRagStatus = async () => {
    try {
      const res = await getRagStatus();
      setRagReady(res.index_ready);
    } catch (e) {
      // 忽略状态加载错误
    }
  };

  // 轮询查询任务状态
  const pollTaskStatus = async () => {
    if (processingTasks.length === 0) {
      if (pollingTimer) {
        clearInterval(pollingTimer);
        setPollingTimer(null);
      }
      return;
    }

    const updatedTasks = await Promise.all(
      processingTasks.map(async (task) => {
        if (task.status === 'success' || task.status === 'failed') {
          return task;
        }
        try {
          const updated = await getUploadTaskStatus(task.task_id);
          return updated;
        } catch (e) {
          return task;
        }
      })
    );

    // 检查是否有任务完成
    const completedTasks = updatedTasks.filter(t => t.status === 'success' || t.status === 'failed');
    if (completedTasks.length > 0) {
      // 重新加载文档列表
      await loadDocuments();
      await loadRagStatus();
      
      // 显示完成消息
      completedTasks.forEach(task => {
        if (task.status === 'success') {
          message.success(`${task.filename} 上传并索引成功`);
        } else {
          message.error(`${task.filename} 处理失败: ${task.error || '未知错误'}`);
        }
      });
    }

    // 更新任务列表，移除已完成的任务
    const remainingTasks = updatedTasks.filter(t => t.status !== 'success' && t.status !== 'failed');
    setProcessingTasks(remainingTasks);
  };

  useEffect(() => {
    loadDocuments();
    loadRagStatus();
  }, []);

  // 当有处理中的任务时启动轮询
  useEffect(() => {
    if (processingTasks.length > 0 && !pollingTimer) {
      const timer = setInterval(pollTaskStatus, 2000); // 每2秒查询一次
      setPollingTimer(timer);
    }

    return () => {
      if (pollingTimer) {
        clearInterval(pollingTimer);
      }
    };
  }, [processingTasks, pollingTimer]);

  const handleUpload: UploadProps['beforeUpload'] = async (file) => {
    const isPdfOrEpub = file.type === 'application/pdf' || file.name.endsWith('.epub');
    if (!isPdfOrEpub) {
      message.error('仅支持上传PDF或EPUB文件');
      return Upload.LIST_IGNORE;
    }

    const isLt100M = file.size / 1024 / 1024 < 100;
    if (!isLt100M) {
      message.error('文件大小不能超过100MB');
      return Upload.LIST_IGNORE;
    }

    try {
      setUploading(true);
      const result = await uploadDocument(file);
      message.info(`${file.name} 已上传，正在后台处理中...`);
      
      // 添加到处理任务列表
      if (result.task_id) {
        setProcessingTasks(prev => [...prev, {
          task_id: result.task_id as string,
          status: 'pending',
          filename: file.name,
          created_at: Date.now() / 1000,
          message: '文件已上传，正在排队处理',
          progress: 0,
          stage: 'pending'
        }]);
      } else {
        // 兼容旧接口
        message.success(`${file.name} 上传并索引成功`);
        await loadDocuments();
        await loadRagStatus();
      }
    } catch (e: any) {
      message.error(`上传失败: ${e.response?.data?.detail || e.message}`);
    } finally {
      setUploading(false);
    }

    return false; // 阻止默认上传行为，我们自己处理
  };

  const handleDelete = (doc: DocumentRecord) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除文档 "${doc.file_name}" 吗？删除后无法恢复。`,
      onOk: async () => {
        try {
          await deleteDocument(doc.file_name);
          message.success('删除成功');
          await loadDocuments();
          await loadRagStatus();
        } catch (e: any) {
          message.error(`删除失败: ${e.response?.data?.detail || e.message}`);
        }
      },
    });
  };

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2}>知识库管理</Title>
            <Text type="secondary">
              上传儿童发展相关的PDF或EPUB书籍，系统将自动构建知识索引，为评估提供科学依据。
            </Text>
          </div>

          <Space className={styles.statusBar}>
            <Space>
              <CloudSyncOutlined style={{ color: ragReady ? '#52c41a' : '#faad14' }} />
              <Text strong={ragReady} type={ragReady ? 'success' : 'warning'}>
                {ragReady ? '索引已就绪' : '索引未就绪，请上传文档'}
              </Text>
            </Space>
            <Text type="secondary">已上传文档: {documents.length} 个</Text>
          </Space>

          <Upload
            beforeUpload={handleUpload}
            fileList={[]}
            showUploadList={false}
            accept=".pdf,.epub"
            multiple={true}
          >
            <Button
              type="primary"
              icon={<UploadOutlined />}
              size="large"
            >
              上传文档
            </Button>
          </Upload>

          {/* 处理中的任务列表 */}
          {processingTasks.length > 0 && (
            <div className={styles.processingTasks}>
              <Title level={5}>正在处理的文档</Title>
              <List
                dataSource={processingTasks}
                renderItem={(task) => (
                  <List.Item>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Space>
                        <LoadingOutlined spin />
                        <Text strong>{task.filename}</Text>
                        <Text type="secondary">
                          {task.status === 'pending' ? '排队中' : '处理中'}
                        </Text>
                      </Space>
                      <Progress percent={Math.round(task.progress || (task.status === 'pending' ? 10 : 50))} status="active" showInfo={false} />
                       <Text type="secondary" style={{ fontSize: '12px' }}>{task.message}</Text>
                    </Space>
                  </List.Item>
                )}
              />
            </div>
          )}
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
        <List
          loading={loading}
          dataSource={documents}
          renderItem={(doc) => (
            <List.Item
              actions={[
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
                    <Text type="secondary">共 {doc.total_pages} 页</Text>
                    <Text type="secondary">上传时间: {new Date(doc.uploaded_at).toLocaleString()}</Text>
                  </Space>
                }
              />
            </List.Item>
          )}
          locale={{
            emptyText: '暂无上传的文档',
          }}
        />
      </Card>
    </div>
  );
};

export default KnowledgeBasePage;
