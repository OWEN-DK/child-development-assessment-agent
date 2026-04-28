import { Badge } from 'antd';
import type { TestRunStatus, DraftStatus } from '@entities/rag-eval';
import { getRunStatusLabel, getDraftStatusLabel } from '@entities/rag-eval';

const RUN_STATUS_BADGE: Record<TestRunStatus, 'success' | 'processing' | 'error' | 'warning' | 'default'> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
};

const DRAFT_STATUS_BADGE: Record<DraftStatus, 'success' | 'processing' | 'error' | 'warning' | 'default'> = {
  pending: 'default',
  generating: 'processing',
  generated: 'warning',
  approved: 'success',
  rejected: 'error',
  archived: 'default',
  imported: 'success',
};

interface StatusBadgeProps {
  status: TestRunStatus | DraftStatus;
  type?: 'run' | 'draft';
}

export function StatusBadge({ status, type = 'run' }: StatusBadgeProps) {
  if (type === 'draft') {
    return (
      <Badge
        status={DRAFT_STATUS_BADGE[status as DraftStatus] || 'default'}
        text={getDraftStatusLabel(status as DraftStatus)}
      />
    );
  }
  return (
    <Badge
      status={RUN_STATUS_BADGE[status as TestRunStatus] || 'default'}
      text={getRunStatusLabel(status as TestRunStatus)}
    />
  );
}
