import { Tag } from 'antd';
import type { LayerResultStatus } from '@entities/rag-eval';
import { getLayerStatusIcon, getLayerStatusLabel } from '@entities/rag-eval';

const STATUS_TAG_COLOR: Record<LayerResultStatus, string> = {
  pass: 'success',
  warn: 'warning',
  fail: 'error',
  skip: 'default',
  error: 'red',
};

interface LayerStatusBadgeProps {
  status: LayerResultStatus;
}

export function LayerStatusBadge({ status }: LayerStatusBadgeProps) {
  return (
    <Tag color={STATUS_TAG_COLOR[status]}>
      {getLayerStatusIcon(status)} {getLayerStatusLabel(status)}
    </Tag>
  );
}
