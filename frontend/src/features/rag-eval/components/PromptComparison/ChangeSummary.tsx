/**
 * 变更摘要展示组件
 */

import { Typography, Tag, Space } from 'antd';
import type { DiffSummary } from './types';

const { Text } = Typography;

interface ChangeSummaryProps {
  summary: DiffSummary;
}

export default function ChangeSummary({ summary }: ChangeSummaryProps) {
  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      <div>
        <Text strong>变更摘要: </Text>
        <Text>{summary.summary}</Text>
      </div>

      <Space>
        {summary.lines_added > 0 && (
          <Tag color="green">+{summary.lines_added} 行新增</Tag>
        )}
        {summary.lines_removed > 0 && (
          <Tag color="red">-{summary.lines_removed} 行删除</Tag>
        )}
        {summary.lines_modified > 0 && (
          <Tag color="orange">~{summary.lines_modified} 行修改</Tag>
        )}
        <Tag color="default">{summary.lines_unchanged} 行未变</Tag>
      </Space>
    </Space>
  );
}
