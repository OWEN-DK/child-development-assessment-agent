import React, { useState } from 'react';
import { Modal, Upload, Button, Table, message, Progress, Space } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { previewImportCases, batchImportCases } from '@/api/rag-test';
import type { ImportPreviewResult } from '@/api/rag-test/types';

interface ImportJsonModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const ImportJsonModal: React.FC<ImportJsonModalProps> = ({ open, onClose, onSuccess }) => {
  const [previewData, setPreviewData] = useState<ImportPreviewResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectedCases, setSelectedCases] = useState<number[]>([]);

  const uploadProps: UploadProps = {
    accept: '.json',
    showUploadList: false,
    beforeUpload: (file) => {
      setUploading(true);
      previewImportCases(file)
        .then((data) => {
          setPreviewData(data);
          setSelectedCases(data.valid_cases.map(item => item.index));
          message.success(`解析完成，有效: ${data.valid_cases.length}，无效: ${data.invalid_cases.length}，重复: ${data.duplicates.length}`);
        })
        .catch((err) => {
          message.error(`解析失败: ${err.message}`);
        })
        .finally(() => {
          setUploading(false);
        });
      return false;
    },
  };

  const handleImport = () => {
    if (!previewData || selectedCases.length === 0) {
      message.warning('请选择要导入的测试用例');
      return;
    }

    setImporting(true);
    const casesToImport = selectedCases.map(index =>
      previewData.valid_cases.find(item => item.index === index)?.data
    ).filter(Boolean) as Record<string, any>[];

    batchImportCases({ cases: casesToImport })
      .then((result) => {
        message.success(`成功导入 ${result.imported_count} 条测试用例`);
        onSuccess();
        onClose();
        setPreviewData(null);
        setSelectedCases([]);
      })
      .catch((err) => {
        message.error(`导入失败: ${err.message}`);
      })
      .finally(() => {
        setImporting(false);
      });
  };

  const columns = [
    { title: '序号', dataIndex: 'index', key: 'index', width: 80 },
    { title: '查询', dataIndex: ['data', 'query'], key: 'query', ellipsis: true },
    { title: '年龄', dataIndex: ['data', 'age'], key: 'age', width: 80 },
    { title: '领域', dataIndex: ['data', 'domain'], key: 'domain', width: 120 },
  ];

  return (
    <Modal
      title="从JSON导入测试用例"
      open={open}
      onCancel={onClose}
      width={900}
      footer={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button
            type="primary"
            onClick={handleImport}
            loading={importing}
            disabled={!previewData || selectedCases.length === 0}
          >
            导入选中 ({selectedCases.length})
          </Button>
        </Space>
      }
    >
      {!previewData ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Upload {...uploadProps}>
            <Button icon={<UploadOutlined />} loading={uploading}>
              {uploading ? '解析中...' : '选择JSON文件'}
            </Button>
          </Upload>
          <p style={{ marginTop: 16, color: '#666' }}>
            支持批量导入测试用例，JSON格式请参考文档规范
          </p>
        </div>
      ) : (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Progress
              percent={Math.round((previewData.valid_cases.length / (previewData.valid_cases.length + previewData.invalid_cases.length + previewData.duplicates.length)) * 100)}
              format={(percent) => `${percent}% 有效`}
            />
            <div style={{ marginTop: 8, display: 'flex', gap: 16 }}>
              <span>总条目: {previewData.valid_cases.length + previewData.invalid_cases.length + previewData.duplicates.length}</span>
              <span style={{ color: '#52c41a' }}>有效: {previewData.valid_cases.length}</span>
              <span style={{ color: '#ff4d4f' }}>无效: {previewData.invalid_cases.length}</span>
              <span style={{ color: '#faad14' }}>重复: {previewData.duplicates.length}</span>
            </div>
          </div>

          <Table
            dataSource={previewData.valid_cases}
            columns={columns}
            rowKey="index"
            rowSelection={{
              selectedRowKeys: selectedCases,
              onChange: (keys) => setSelectedCases(keys as number[]),
            }}
            pagination={{ pageSize: 10 }}
            size="small"
          />
        </div>
      )}
    </Modal>
  );
};

export default ImportJsonModal;
