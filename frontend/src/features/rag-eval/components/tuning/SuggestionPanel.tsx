import { List, Card, Tag, Button, Space, Typography, Tooltip } from 'antd';
import type { TuningSuggestion, IssueSeverity } from '@entities/rag-eval';
import { formatTimestamp } from '@entities/rag-eval';

const { Text, Paragraph } = Typography;

const SEVERITY_TAG_COLOR: Record<IssueSeverity, string> = {
  critical: 'red',
  warning: 'orange',
  info: 'blue',
};

interface SuggestionPanelProps {
  suggestions: TuningSuggestion[];
  onAdopt: (id: string) => void;
  onReject: (id: string) => void;
  onIgnore: (id: string) => void;
  loading?: boolean;
}

export function SuggestionPanel({ suggestions, onAdopt, onReject, onIgnore, loading }: SuggestionPanelProps) {
  return (
    <List
      dataSource={suggestions}
      loading={loading}
      locale={{ emptyText: '暂无调优建议' }}
      renderItem={(item) => (
        <List.Item style={{ display: 'block', padding: '12px 0' }}
          actions={[
            <Tooltip title="采纳" key="adopt"><Button size="small" type="primary" onClick={() => onAdopt(item.id)}>采纳</Button></Tooltip>,
            <Button size="small" danger key="reject" onClick={() => onReject(item.id)}>驳回</Button>,
            <Button size="small" key="ignore" onClick={() => onIgnore(item.id)}>忽略</Button>,
          ]}
        >
          <Card size="small" style={{ width: '100%' }}>
            <Space wrap style={{ marginBottom: 4 }}>
              <Tag color={SEVERITY_TAG_COLOR[item.severity]}>{item.severity}</Tag>
              <Tag>{item.category}</Tag>
              <Text strong>{item.title}</Text>
            </Space>
            <Paragraph ellipsis={{ rows: 2, expandable: true }} style={{ marginBottom: 8 }}>{item.description}</Paragraph>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div><Text type="secondary" style={{ fontSize: 12 }}>当前值: </Text><Text code style={{ fontSize: 12 }}>{typeof item.current_value === 'object' ? JSON.stringify(item.current_value) : String(item.current_value)}</Text></div>
              <div><Text type="secondary" style={{ fontSize: 12 }}>建议值: </Text><Text code style={{ fontSize: 12, color: '#52c41a' }}>{typeof item.suggested_value === 'object' ? JSON.stringify(item.suggested_value) : String(item.suggested_value)}</Text></div>
              <div><Text type="secondary" style={{ fontSize: 12 }}>配置键: {item.config_key}</Text></div>
              {item.conflict_ids.length > 0 && <Text type="warning" style={{ fontSize: 12 }}>⚠️ 冲突项: {item.conflict_ids.length} 个</Text>}
              <Text type="secondary" style={{ fontSize: 11 }}>{formatTimestamp(item.created_at)}</Text>
            </Space>
          </Card>
        </List.Item>
      )}
    />
  );
}
