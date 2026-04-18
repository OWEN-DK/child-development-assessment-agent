/**
 * 已忽略建议列表组件
 */

import { useEffect, useState } from 'react';
import { Button, List, message, Typography, Spin, Empty } from 'antd';
import { UndoOutlined } from '@ant-design/icons';
import IgnoredSuggestionItem from './IgnoredSuggestionItem';
import {
  getIgnoredSuggestions,
  restoreIgnoredSuggestion,
  deleteIgnoredSuggestion,
} from '@/api/rag-eval/tuning';
import type { IgnoredSuggestion } from './types';

const { Title } = Typography;

interface IgnoredSuggestionsListProps {
  testSetId: string;
  reportId?: string;
  onRestore?: (id: string) => void;
}

export default function IgnoredSuggestionsList({
  testSetId,
  reportId,
  onRestore,
}: IgnoredSuggestionsListProps) {
  const [suggestions, setSuggestions] = useState<IgnoredSuggestion[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchIgnoredSuggestions = async () => {
    setLoading(true);
    try {
      const response = await getIgnoredSuggestions(testSetId, reportId);
      setSuggestions(response.items);
    } catch (error) {
      message.error('获取已忽略建议列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIgnoredSuggestions();
  }, [testSetId, reportId]);

  const handleRestore = async (id: string) => {
    try {
      const response = await restoreIgnoredSuggestion(id);
      message.success(response.message);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      onRestore?.(id);
    } catch (error) {
      message.error('恢复失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteIgnoredSuggestion(id);
      message.success('已删除');
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleRestoreAll = async () => {
    try {
      await Promise.all(suggestions.map((s) => restoreIgnoredSuggestion(s.id)));
      message.success('已恢复全部建议');
      setSuggestions([]);
    } catch (error) {
      message.error('批量恢复失败');
    }
  };

  if (loading) {
    return <Spin size="small" />;
  }

  if (suggestions.length === 0) {
    return <Empty description="暂无已忽略建议" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>
          已忽略建议 ({suggestions.length})
        </Title>
        <Button
          type="link"
          icon={<UndoOutlined />}
          onClick={handleRestoreAll}
          disabled={suggestions.length === 0}
        >
          全部恢复
        </Button>
      </div>

      <List
        dataSource={suggestions}
        renderItem={(suggestion) => (
          <List.Item>
            <IgnoredSuggestionItem
              suggestion={suggestion}
              onRestore={handleRestore}
              onDelete={handleDelete}
            />
          </List.Item>
        )}
      />
    </div>
  );
}
