import { List, Tag, Typography } from 'antd';
import { WarningFilled, InfoCircleFilled, AlertFilled } from '@ant-design/icons';
import type { LayerIssue } from '@entities/rag-eval';

const { Text, Paragraph } = Typography;

const SEVERITY_CONFIG: Record<string, { color: string; icon: React.ReactNode }> = {
  critical: { color: 'red', icon: <AlertFilled /> },
  warning: { color: 'orange', icon: <WarningFilled /> },
  info: { color: 'blue', icon: <InfoCircleFilled /> },
};

interface IssueListProps {
  issues: LayerIssue[];
}

export function IssueList({ issues }: IssueListProps) {
  if (issues.length === 0) {
    return <Text type="secondary">无问题</Text>;
  }

  return (
    <List
      size="small"
      dataSource={issues}
      renderItem={(issue) => {
        const severity = SEVERITY_CONFIG[issue.severity] || SEVERITY_CONFIG.info;
        return (
          <List.Item style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Tag color={severity.color} icon={severity.icon}>
                {issue.severity}
              </Tag>
              <Tag>{issue.category}</Tag>
            </div>
            <Paragraph
              ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
              style={{ margin: 0, fontSize: 13 }}
            >
              {issue.description}
            </Paragraph>
            {issue.affected_items.length > 0 && (
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {issue.affected_items.map((item) => (
                  <Tag key={item} style={{ fontSize: 11 }}>{item}</Tag>
                ))}
              </div>
            )}
            {issue.suggestion && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                建议: {issue.suggestion}
              </Text>
            )}
          </List.Item>
        );
      }}
    />
  );
}
