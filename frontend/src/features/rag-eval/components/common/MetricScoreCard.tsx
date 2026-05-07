import { Card, Progress, Tooltip, Typography } from 'antd';
import { CheckCircleFilled, CloseCircleFilled, QuestionCircleOutlined } from '@ant-design/icons';
import type { MetricScore } from '@entities/rag-eval';
import { formatPercent, METRIC_METADATA } from '@entities/rag-eval';

const { Text } = Typography;

interface MetricScoreCardProps {
  name: string;
  score: MetricScore;
}

export function MetricScoreCard({ name, score }: MetricScoreCardProps) {
  const percent = Math.round(score.value * 100);
  const meta = METRIC_METADATA[name];
  const displayName = meta?.label ?? name;

  return (
    <Card size="small" style={{ minWidth: 180 }}>
      <div style={{ textAlign: 'center' }}>
        <Text strong style={{ fontSize: 13 }}>{displayName}</Text>
        {meta?.description && (
          <Tooltip title={meta.description}>
            <QuestionCircleOutlined style={{ color: '#8c8c8c', cursor: 'help', fontSize: 12, marginLeft: 4 }} />
          </Tooltip>
        )}
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
