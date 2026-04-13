import React, { useState, useEffect, useRef } from 'react';
import { Modal, Upload, Button, message, Form, Input, Progress, Typography } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { uploadSourceDocument } from '@/api/rag-test';

const { Text } = Typography;

interface UploadDocumentModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const UploadDocumentModal: React.FC<UploadDocumentModalProps> = ({ open, onClose, onSuccess }) => {
  const [form] = Form.useForm();
  const [uploading, setUploading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState<string>('');
  const eventSourceRef = useRef<EventSource | null>(null);

  // 清理 SSE 连接
  const closeSSE = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  useEffect(() => {
    if (!open) {
      closeSSE();
      setUploading(false);
      setIsGenerating(false);
      setProgress(0);
      setStatusText('');
      form.resetFields();
    }
    return closeSSE;
  }, [open, form]);

  const uploadProps: UploadProps = {
    accept: '.pdf,.epub,.txt',
    maxCount: 1,
    showUploadList: false,
    beforeUpload: (file) => {
      const title = form.getFieldValue('title') || file.name;
      setUploading(true);
      setProgress(10);
      setStatusText('正在上传文档...');

      uploadSourceDocument(file, title)
        .then((res) => {
          if (res.auto_generate_started && res.task_id) {
            setIsGenerating(true);
            setProgress(30);
            setStatusText('文档上传成功，准备生成草稿...');
            
            // 启动 SSE 监听
            const sseUrl = `/rag/test/drafts/generate/${res.task_id}/stream`;
            const es = new EventSource(sseUrl);
            eventSourceRef.current = es;

            es.onmessage = (event) => {
              try {
                const data = JSON.parse(event.data);
                if (data.type === 'progress') {
                  // 进度映射：30% 到 99%
                  const mappedProgress = 30 + Math.floor((data.progress / 100) * 69);
                  setProgress(mappedProgress);
                  setStatusText(data.message || `正在生成 (${data.current}/${data.total})`);
                } else if (data.type === 'complete') {
                  setProgress(100);
                  setStatusText('生成完成！');
                  message.success('文档上传并自动生成草稿成功');
                  closeSSE();
                  setTimeout(() => {
                    onSuccess();
                    onClose();
                  }, 1000);
                } else if (data.type === 'error') {
                  message.error(`生成失败: ${data.error || data.message}`);
                  setStatusText('生成失败');
                  setUploading(false);
                  setIsGenerating(false);
                  closeSSE();
                } else if (data.type === 'heartbeat') {
                  // 忽略心跳
                }
              } catch (e) {
                console.error('Failed to parse SSE message', e);
              }
            };

            es.onerror = (err) => {
              console.error('SSE Error', err);
              message.error('与服务器断开连接');
              closeSSE();
              setUploading(false);
              setIsGenerating(false);
            };
          } else {
            setProgress(100);
            message.success('文档上传成功');
            onSuccess();
            onClose();
            form.resetFields();
            setProgress(0);
            setUploading(false);
          }
        })
        .catch((err) => {
          message.error(`上传失败: ${err.message}`);
          setProgress(0);
          setStatusText('');
          setUploading(false);
        });
      return false;
    },
  };

  return (
    <Modal
      title="上传书籍文档"
      open={open}
      onCancel={onClose}
      footer={null}
      width={600}
      closable={!uploading && !isGenerating}
      maskClosable={!uploading && !isGenerating}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="title" label="文档标题">
          <Input placeholder="请输入文档标题（可选）" />
        </Form.Item>

        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <Upload {...uploadProps}>
            <Button icon={<UploadOutlined />} loading={uploading || isGenerating} size="large" disabled={uploading || isGenerating}>
              {uploading || isGenerating ? '处理中...' : '选择文件'}
            </Button>
          </Upload>
          <p style={{ marginTop: 12, color: '#666' }}>
            支持 PDF/EPUB/TXT 格式
          </p>
        </div>

        {(progress > 0 || isGenerating) && (
          <div style={{ marginTop: 20 }}>
            <Progress percent={progress} status={progress === 100 ? 'success' : 'active'} />
            {statusText && (
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <Text type="secondary">{statusText}</Text>
              </div>
            )}
          </div>
        )}
      </Form>
    </Modal>
  );
};

export default UploadDocumentModal;
