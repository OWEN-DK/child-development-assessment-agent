import React, { useState } from 'react';
import { Drawer, Descriptions, Spin, Alert } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { tracingApi } from '@/api/tracing';
import { SpanTreeView } from './SpanTreeView';
import { SpanDetailPanel } from './SpanDetailPanel';
import type { Span } from '@entities/tracing/types';

interface TraceDetailDrawerProps {
  traceId: string | null;
  onClose: () => void;
}

export const TraceDetailDrawer: React.FC<TraceDetailDrawerProps> = ({
  traceId,
  onClose,
}) => {
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['traceDetail', traceId],
    queryFn: () => tracingApi.getTraceDetail(traceId!),
    enabled: !!traceId,
  });

  return (
    <Drawer
      title="Trace 详情"
      width={800}
      open={!!traceId}
      onClose={onClose}
    >
      {isLoading ? (
        <Spin size="large" />
      ) : isError ? (
        <Alert message="加载 Trace 详情失败" type="error" />
      ) : data ? (
        <>
          <Descriptions title="基本信息" bordered column={2}>
            <Descriptions.Item label="Trace ID">
              {data.trace_id}
            </Descriptions.Item>
            <Descriptions.Item label="名称">{data.name}</Descriptions.Item>
            <Descriptions.Item label="用户 ID">
              {data.user_id || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="状态">{data.status}</Descriptions.Item>
            <Descriptions.Item label="开始时间">
              {new Date(data.start_time).toLocaleString()}
            </Descriptions.Item>
            <Descriptions.Item label="结束时间">
              {data.end_time
                ? new Date(data.end_time).toLocaleString()
                : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="总耗时">
              {data.total_duration_ms}ms
            </Descriptions.Item>
            <Descriptions.Item label="总 Token">
              {data.total_tokens}
            </Descriptions.Item>
            <Descriptions.Item label="总成本">
              {data.total_cost ? `¥${data.total_cost}` : '未配置'}
            </Descriptions.Item>
          </Descriptions>

          <div style={{ marginTop: 16 }}>
            <h4>Span 层级树</h4>
            <SpanTreeView
              spans={data.spans || []}
              onSpanClick={setSelectedSpan}
            />
          </div>

          {selectedSpan && (
            <div style={{ marginTop: 16 }}>
              <h4>Span 详情</h4>
              <SpanDetailPanel span={selectedSpan} />
            </div>
          )}
        </>
      ) : (
        <Alert message="Trace 不存在" type="error" />
      )}
    </Drawer>
  );
};
