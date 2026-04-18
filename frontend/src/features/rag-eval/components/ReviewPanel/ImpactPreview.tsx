/**
 * 变更影响预览组件
 */

import { Card, Typography, Row, Col } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import type { ImpactPreview } from './types';

const { Text } = Typography;

interface ImpactPreviewProps {
  impact: ImpactPreview | null;
}

/** 指标名称映射 */
const METRIC_LABELS: Record<string, string> = {
  precision_at_5: 'P@5',
  recall_at_5: 'R@5',
  f1_score: 'F1',
  mrr: 'MRR',
  ndcg_at_5: 'NDCG@5',
};

export default function ImpactPreview({ impact }: ImpactPreviewProps) {
  if (!impact || Object.keys(impact.metrics).length === 0) {
    return null;
  }

  return (
    <Card size="small" title="变更影响预览" style={{ marginTop: 16 }}>
      <Row gutter={[16, 8]}>
        {Object.entries(impact.metrics).map(([key, metric]) => {
          const label = METRIC_LABELS[key] || key;
          const isPositive = metric.delta_min >= 0;

          return (
            <Col span={12} key={key}>
              <Text type="secondary">预计 {label}: </Text>
              <Text>{metric.current.toFixed(2)}</Text>
              <Text> → </Text>
              <Text strong style={{ color: isPositive ? '#52c41a' : '#ff4d4f' }}>
                {metric.predicted_min.toFixed(2)}-{metric.predicted_max.toFixed(2)}
              </Text>
              <Text style={{ marginLeft: 4 }}>
                {isPositive ? (
                  <ArrowUpOutlined style={{ color: '#52c41a' }} />
                ) : (
                  <ArrowDownOutlined style={{ color: '#ff4d4f' }} />
                )}
                {` (${metric.delta_min >= 0 ? '+' : ''}${metric.delta_min.toFixed(2)}~${metric.delta_max >= 0 ? '+' : ''}${metric.delta_max.toFixed(2)})`}
              </Text>
            </Col>
          );
        })}
      </Row>
    </Card>
  );
}
