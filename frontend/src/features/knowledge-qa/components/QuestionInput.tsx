import React, { useState, useEffect } from 'react';
import { Button, Input, Space } from 'antd';
import { SendOutlined, StopOutlined, RollbackOutlined } from '@ant-design/icons';

const { TextArea } = Input;

interface Props {
  onSubmit: (question: string, bookIds?: string[]) => void;
  onCancel?: () => void;
  onReturn?: () => void;
  loading: boolean;
  /** 查看历史记录时为 true，此时显示"返回"按钮而非"中断" */
  isViewingHistory?: boolean;
  /** 当前显示的问题文本（运行时显示当前问题，查看历史时显示历史问题） */
  displayQuestion?: string;
}

export const QuestionInput: React.FC<Props> = ({
  onSubmit,
  onCancel,
  onReturn,
  loading,
  isViewingHistory = false,
  displayQuestion,
}) => {
  const [value, setValue] = useState('');

  // 查看历史记录时，将历史问题填入输入框
  useEffect(() => {
    if (isViewingHistory && displayQuestion) {
      setValue(displayQuestion);
    }
  }, [isViewingHistory, displayQuestion]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || loading) return;
    onSubmit(trimmed);
  };

  const renderButton = () => {
    if (!loading) {
      return (
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSubmit}
          style={{ height: 'auto' }}
        >
          提交
        </Button>
      );
    }
    if (isViewingHistory) {
      return (
        <Button
          icon={<RollbackOutlined />}
          onClick={onReturn}
          style={{ height: 'auto' }}
        >
          返回
        </Button>
      );
    }
    return (
      <Button
        danger
        icon={<StopOutlined />}
        onClick={onCancel}
        style={{ height: 'auto' }}
      >
        中断
      </Button>
    );
  };

  return (
    <Space.Compact style={{ width: '100%' }}>
      <TextArea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="例如：我的孩子注意力不集中，根据《运动改变大脑》推荐一些运动改善方案"
        autoSize={{ minRows: 5, maxRows: 12 }}
        onPressEnter={(e) => {
          if (!e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          }
        }}
        disabled={loading && !isViewingHistory}
        style={{ flex: 1, fontSize: 16, padding: '12px 16px' }}
      />
      {renderButton()}
    </Space.Compact>
  );
};
