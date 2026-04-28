import { Card, Progress, Typography } from 'antd';
import { CheckCircleFilled, CloseCircleFilled } from '@ant-design/icons';
import type { MetricScore } from '@entities/rag-eval';
import { formatPercent } from '@entities/rag-eval';

const { Text } = Typography;

interface MetricScoreCardProps {
  name: string;
  score: MetricScore;
}

export function MetricScoreCard({ name, score }: MetricScoreCardProps) {
  const percent = Math.round(score.value * 100);

  return (
    <Card size="small" style={{ minWidth: 180 }}>
      <div style={{ textAlign: 'center' }}>
        <Text strong style={{ fontSize: 13 }}>{name}</Text>
        <Progress
          type="circle"
          percent={percent}
          size={80}
          status={score.passed ? 'success' : 'exception'}
          format={() => formatPercent(score.value, 0)}
        />
        <div style={{ marginTop: 4 }}>
          {score.passed ? (
            <Text type="success"><CheckCircleFilled /> 通过</Text>
          ) : (
            <Text type="danger"><CloseCircleFilled /> 未通过</Text>
          )}
        </div>
        <Text type="secondary" style={{ fontSize: 12 }}>
          阈值: {formatPercent(score.threshold, 0)}
        </Text>
      </div>
    </Card>
  );
}
