import React, { useState } from 'react';
import { Modal, Upload, Button, message, Form, Input, Progress } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { uploadSourceDocument } from '@/api/rag-test';

interface UploadDocumentModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const UploadDocumentModal: React.FC<UploadDocumentModalProps> = ({ open, onClose, onSuccess }) => {
  const [form] = Form.useForm();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const uploadProps: UploadProps = {
    accept: '.pdf,.epub,.txt',
    maxCount: 1,
    showUploadList: false,
    beforeUpload: (file) => {
      const title = form.getFieldValue('title') || file.name;
      setUploading(true);
      setProgress(30);

      uploadSourceDocument(file, title)
        .then(() => {
          setProgress(100);
          message.success('文档上传成功');
          onSuccess();
          onClose();
          form.resetFields();
          setProgress(0);
        })
        .catch((err) => {
          message.error(`上传失败: ${err.message}`);
          setProgress(0);
        })
        .finally(() => {
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
    >
      <Form form={form} layout="vertical">
        <Form.Item name="title" label="文档标题">
          <Input placeholder="请输入文档标题（可选）" />
        </Form.Item>

        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <Upload {...uploadProps}>
            <Button icon={<UploadOutlined />} loading={uploading} size="large">
              {uploading ? '上传中...' : '选择文件'}
            </Button>
          </Upload>
          <p style={{ marginTop: 12, color: '#666' }}>
            支持 PDF/EPUB/TXT 格式
          </p>
        </div>

        {progress > 0 && (
          <Progress percent={progress} status={progress === 100 ? 'success' : 'active'} />
        )}
      </Form>
    </Modal>
  );
};

export default UploadDocumentModal;
