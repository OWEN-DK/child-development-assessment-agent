import React, { useState } from 'react';
import { Button, Input, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';

const { TextArea } = Input;

interface Props {
  onSubmit: (question: string, bookIds?: string[]) => void;
  loading: boolean;
}

export const QuestionInput: React.FC<Props> = ({ onSubmit, loading }) => {
  const [value, setValue] = useState('');

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || loading) return;
    onSubmit(trimmed);
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
        disabled={loading}
        style={{ flex: 1, fontSize: 16, padding: '12px 16px' }}
      />
      <Button
        type="primary"
        icon={<SendOutlined />}
        onClick={handleSubmit}
        loading={loading}
        style={{ height: 'auto' }}
      >
        提交
      </Button>
    </Space.Compact>
  );
};
