import { Card, Progress, Space, Typography } from 'antd';
import type { LayerResult } from '@entities/rag-eval';
import { LayerStatusBadge } from '../common/LayerStatusBadge';
import { IssueList } from './IssueList';
import { formatPercent } from '@entities/rag-eval';

const { Text, Title } = Typography;

interface LayerResultCardProps {
  result: LayerResult;
}

export function LayerResultCard({ result }: LayerResultCardProps) {
  const percent = Math.round(result.score * 100);

  return (
    <Card
      size="small"
      title={
        <Space>
          <Text strong>Layer {result.layer}</Text>
          <Text type="secondary">{result.name}</Text>
          <LayerStatusBadge status={result.status} />
        </Space>
      }
      style={{ marginBottom: 8 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
        <Progress
          type="circle"
          percent={percent}
          size={60}
          status={result.status === 'fail' ? 'exception' : 'success'}
          format={() => formatPercent(result.score, 0)}
        />
        <div>
          <Title level={5} style={{ margin: 0 }}>得分: {formatPercent(result.score, 1)}</Title>
          <Text type="secondary">
            {result.total_cases > 0
              ? `受影响 ${result.affected_cases}/${result.total_cases} 用例`
              : `${result.issues.length} 个问题`}
            {result.issues.filter((i) => i.severity === 'critical').length > 0 &&
              `（${result.issues.filter((i) => i.severity === 'critical').length} 严重）`}
          </Text>
        </div>
      </div>
      <IssueList issues={result.issues} />
    </Card>
  );
}
