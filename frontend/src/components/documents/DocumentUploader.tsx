import React from 'react';
import { Upload, Button } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { uploadDocument } from '../../api/documents';
import { validateFile } from '@shared/lib/validators';
import type { UploadTaskStatus } from '../../api/documents/types';
import { extractApiError, notification } from '@shared/lib/notification';

interface DocumentUploaderProps {
  onUploadStart: (task: UploadTaskStatus) => void;
  onSuccess: () => void;
}

export const DocumentUploader: React.FC<DocumentUploaderProps> = ({
  onUploadStart,
  onSuccess,
}) => {
  const handleUpload: UploadProps['beforeUpload'] = async (file) => {
    const validation = validateFile(file);
    if (!validation.valid) {
      notification.error(validation.message!);
      return Upload.LIST_IGNORE;
    }

    try {
      const result = await uploadDocument(file);
      notification.info(`${file.name} 已上传，正在后台处理中...`);
      
      if (result.task_id) {
        onUploadStart({
          task_id: result.task_id,
          status: 'pending',
          filename: file.name,
          created_at: Date.now() / 1000,
          message: '文件已上传，正在排队处理',
          progress: 0,
          stage: 'pending',
        });
      } else {
        notification.success(`${file.name} 上传并索引成功`);
        onSuccess();
      }
    } catch (e: any) {
      const apiError = extractApiError(e);
      notification.error(`上传失败: ${apiError.message}`);
    }

    return false;
  };

  return (
    <Upload
      beforeUpload={handleUpload}
      fileList={[]}
      showUploadList={false}
      accept=".pdf,.epub"
      multiple
    >
      <Button type="primary" icon={<UploadOutlined />} size="large">
        上传文档
      </Button>
    </Upload>
  );
};
