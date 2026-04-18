/**
 * 单个审查项组件
 */

import { useState } from 'react';
import { Card, Input, Button, Tag, Typography, Space } from 'antd';
import { CloseOutlined, DiffOutlined } from '@ant-design/icons';
import type { AdoptedSuggestion } from './types';
import PromptComparisonModal from '../PromptComparison';

const { Text } = Typography;

interface ReviewItemProps {
  item: AdoptedSuggestion;
  index: number;
  onRemove: (id: string) => void;
  onCustomValueChange: (id: string, value: string) => void;
}

/** 格式化值展示 */
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export default function ReviewItem({ item, index, onRemove, onCustomValueChange }: ReviewItemProps) {
  const [promptComparisonVisible, setPromptComparisonVisible] = useState(false);

  const handleOpenDiff = () => {
    setPromptComparisonVisible(true);
  };

  return (
    <Card
      size="small"
      style={{ marginBottom: 12 }}
      extra={
        <Space>
          <Button
            type="default"
            size="small"
            icon={<DiffOutlined />}
            onClick={handleOpenDiff}
          >
            查看 Diff
          </Button>
          <Button
            type="text"
            danger
            size="small"
            icon={<CloseOutlined />}
            onClick={() => onRemove(item.id)}
          >
            移除
          </Button>
        </Space>
      }
    >
      <div style={{ marginBottom: 8 }}>
        <Text strong>{index}. 配置: {item.param_name}</Text>
      </div>

      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <div>
          <Text type="secondary">当前值: </Text>
          <Text>{formatValue(item.current_value)}</Text>
          {item.source_version && (
            <Tag color="blue" style={{ marginLeft: 8 }}>v{item.source_version}</Tag>
          )}
        </div>

        <div>
          <Text type="secondary">建议值: </Text>
          <Text strong style={{ color: '#52c41a' }}>{formatValue(item.suggested_value)}</Text>
        </div>

        <div>
          <Text type="secondary">自定义值: </Text>
          <Input
            size="small"
            style={{ width: 200, marginLeft: 4 }}
            placeholder="可修改建议值"
            defaultValue={formatValue(item.custom_value ?? item.suggested_value)}
            onChange={(e) => onCustomValueChange(item.id, e.target.value)}
          />
        </div>

        {item.reason && (
          <div>
            <Text type="secondary">原因: </Text>
            <Text>{item.reason}</Text>
          </div>
        )}

        {item.expected_effect && (
          <div>
            <Text type="secondary">预期: </Text>
            <Text type="success">{formatValue(item.expected_effect)}</Text>
          </div>
        )}

        {item.risk && (
          <div>
            <Text type="secondary">风险: </Text>
            <Text type="warning">{item.risk}</Text>
          </div>
        )}
      </Space>

      {/* 提示词对比模态框 */}
      <PromptComparisonModal
        visible={promptComparisonVisible}
        promptKey={item.param_name}
        currentVersion={item.source_version}
        onClose={() => setPromptComparisonVisible(false)}
      />
    </Card>
  );
}
