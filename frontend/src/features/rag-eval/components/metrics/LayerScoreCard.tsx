import { Card, Typography, Row, Col } from 'antd';
import type { LayerMetrics } from '@entities/rag-eval';
import { MetricScoreCard } from '../common/MetricScoreCard';

const { Title } = Typography;

interface LayerScoreCardProps {
  title: string;
  metrics: LayerMetrics;
}

export function LayerScoreCard({ title, metrics }: LayerScoreCardProps) {
  const entries = Object.entries(metrics);

  if (entries.length === 0) {
    return (
      <Card size="small" title={<Title level={5} style={{ margin: 0 }}>{title}</Title>}>
        <Typography.Text type="secondary">暂无指标数据</Typography.Text>
      </Card>
    );
  }

  return (
    <Card size="small" title={<Title level={5} style={{ margin: 0 }}>{title}</Title>}>
      <Row gutter={[12, 12]}>
        {entries.map(([name, score]) => (
          <Col key={name} xs={12} sm={8} md={6} lg={4}>
            <MetricScoreCard name={name} score={score} />
          </Col>
        ))}
      </Row>
    </Card>
  );
}
