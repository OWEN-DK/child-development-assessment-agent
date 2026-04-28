import { Space, Typography, Progress } from 'antd';
import type { RunMetrics } from '@entities/rag-eval';
import { LayerScoreCard } from './LayerScoreCard';
import { formatPercent } from '@entities/rag-eval';

const { Title, Text } = Typography;

interface ScoringDashboardProps {
  metrics: RunMetrics;
}

export function ScoringDashboard({ metrics }: ScoringDashboardProps) {
  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>三层指标得分看板</Title>
        <Space>
          <Text strong>综合得分:</Text>
          <Progress
            type="circle"
            percent={Math.round(metrics.overall_score * 100)}
            size={48}
            format={() => formatPercent(metrics.overall_score, 0)}
          />
        </Space>
      </div>

      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <LayerScoreCard title="L1 检索质量" metrics={metrics.l1} />
        <LayerScoreCard title="L2 生成质量" metrics={metrics.l2} />
        <LayerScoreCard title="L3 系统质量" metrics={metrics.l3} />
      </Space>
    </div>
  );
}
