/**
 * 回滚确认对话框组件
 * 用户确认回滚操作并填写回滚原因
 */

import React, { useState } from 'react';
import { Modal, Input, Typography, Alert } from 'antd';
import type { RollbackConfirmDialogProps } from './types';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

const RollbackConfirmDialog: React.FC<RollbackConfirmDialogProps> = ({
  visible,
  targetVersion,
  onConfirm,
  onCancel,
  loading = false,
}) => {
  const [reason, setReason] = useState('');

  const handleConfirm = () => {
    if (!reason.trim()) {
      return;
    }
    onConfirm(reason.trim());
    setReason('');
  };

  const handleCancel = () => {
    setReason('');
    onCancel();
  };

  return (
    <Modal
      title="确认回滚配置版本"
      open={visible}
      onOk={handleConfirm}
      onCancel={handleCancel}
      okText="确认回滚"
      cancelText="取消"
      okButtonProps={{
        disabled: !reason.trim(),
        loading,
        danger: true,
      }}
    >
      <Alert
        message="警告"
        description="回滚操作将创建新的配置版本并标记为回滚状态，此操作不可撤销。"
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
      />

      {targetVersion && (
        <div style={{ marginBottom: 16 }}>
          <Text strong>目标版本:</Text>
          <Paragraph style={{ margin: '8px 0 0' }}>
            <Text strong>{targetVersion.version_label}</Text>
            {targetVersion.created_at && (
              <Text type="secondary" style={{ marginLeft: 8 }}>
                (创建于 {new Date(targetVersion.created_at).toLocaleString()})
              </Text>
            )}
          </Paragraph>
        </div>
      )}

      <div style={{ marginBottom: 8 }}>
        <Text strong>回滚原因 <Text type="danger">*</Text></Text>
      </div>
      <TextArea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="请详细说明回滚原因，以便后续追溯..."
        rows={4}
        maxLength={500}
        showCount
      />
    </Modal>
  );
};

export default RollbackConfirmDialog;
