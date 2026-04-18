/**
 * 单个已忽略建议项组件
 */

import { Card, Button, Tag, Space, Typography, Popconfirm } from 'antd';
import { UndoOutlined, DeleteOutlined, ClockCircleOutlined } from '@ant-design/icons';
import type { IgnoredSuggestion } from './types';

const { Text } = Typography;

interface IgnoredSuggestionItemProps {
  suggestion: IgnoredSuggestion;
  onRestore: (id: string) => void;
  onDelete: (id: string) => void;
}

const typeLabels: Record<string, string> = {
  config: '配置建议',
  prompt: '提示词建议',
};

const typeColors: Record<string, string> = {
  config: 'blue',
  prompt: 'purple',
};

const scopeLabels: Record<string, string> = {
  report: '仅本次报告',
  test_set: '整个测试集',
};

export default function IgnoredSuggestionItem({
  suggestion,
  onRestore,
  onDelete,
}: IgnoredSuggestionItemProps) {
  const formatTime = (timeStr?: string | null) => {
    if (!timeStr) return '未知';
    const date = new Date(timeStr);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Card size="small" style={{ marginBottom: 8 }}>
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <div>
          <Text strong>参数: </Text>
          <Text>{suggestion.name_zh || suggestion.param_name}</Text>
        </div>

        <Space>
          <Tag color={typeColors[suggestion.suggestion_type] || 'default'}>
            类型: {typeLabels[suggestion.suggestion_type] || suggestion.suggestion_type}
          </Tag>
          <Tag color="orange">
            忽略范围: {scopeLabels[suggestion.ignore_scope] || suggestion.ignore_scope}
          </Tag>
        </Space>

        <div>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          <Text type="secondary">忽略时间: {formatTime(suggestion.ignored_at)}</Text>
        </div>

        {suggestion.ignore_reason && (
          <div>
            <Text type="secondary">忽略原因: {suggestion.ignore_reason}</Text>
          </div>
        )}

        <Space>
          <Button
            size="small"
            type="link"
            icon={<UndoOutlined />}
            onClick={() => onRestore(suggestion.id)}
          >
            恢复
          </Button>
          <Popconfirm
            title="确认删除"
            description="删除后无法恢复，确定要删除这条忽略记录吗？"
            onConfirm={() => onDelete(suggestion.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button size="small" type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      </Space>
    </Card>
  );
}
