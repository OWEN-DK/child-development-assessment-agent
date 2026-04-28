import { Card, Typography, Empty } from 'antd';

const { Text } = Typography;

interface TrendPoint {
  label: string;
  value: number;
}

interface TrendChartProps {
  data: TrendPoint[];
  title?: string;
  threshold?: number;
}

export function TrendChart({ data, title = '指标趋势', threshold }: TrendChartProps) {
  if (data.length === 0) {
    return (
      <Card size="small" title={title}>
        <Empty description="暂无趋势数据" />
      </Card>
    );
  }

  const maxValue = Math.max(...data.map((d) => d.value), threshold || 0, 1);
  const barWidth = Math.max(30, Math.floor(600 / data.length) - 8);

  return (
    <Card size="small" title={title}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 160, padding: '0 8px' }}>
        {data.map((point, i) => {
          const heightPct = (point.value / maxValue) * 100;
          const avgColor =
            point.value >= (threshold || 0.7) ? '#52c41a' : point.value >= (threshold || 0.5) ? '#faad14' : '#ff4d4f';

          return (
            <div
              key={i}
              style={{
                flex: 1,
                minWidth: barWidth,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'flex-end',
              }}
            >
              <Text style={{ fontSize: 10, marginBottom: 2 }}>
                {(point.value * 100).toFixed(0)}%
              </Text>
              <div
                style={{
                  width: '100%',
                  height: `${Math.max(heightPct, 2)}%`,
                  backgroundColor: avgColor,
                  borderRadius: '4px 4px 0 0',
                  minHeight: 4,
                  transition: 'height 0.3s',
                }}
              />
              <Text
                style={{ fontSize: 10, marginTop: 4, maxWidth: barWidth, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              >
                {point.label}
              </Text>
            </div>
          );
        })}
      </div>
      {threshold != null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
          <div style={{ width: 16, height: 2, backgroundColor: '#faad14', borderTop: '1px dashed #d9d9d9' }} />
          <Text type="secondary" style={{ fontSize: 11 }}>
            阈值: {(threshold * 100).toFixed(0)}%
          </Text>
        </div>
      )}
    </Card>
  );
}
