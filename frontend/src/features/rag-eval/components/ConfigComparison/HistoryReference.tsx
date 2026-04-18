/**
 * 历史参考展示组件
 */

import { Timeline, Tag, Typography } from 'antd';
import type { HistoryReference } from './types';

const { Text } = Typography;

interface HistoryReferenceProps {
  history: HistoryReference[];
}

export default function HistoryReference({ history }: HistoryReferenceProps) {
  if (history.length === 0) {
    return (
      <Text type="secondary" style={{ fontStyle: 'italic' }}>
        暂无历史变更记录
      </Text>
    );
  }

  // 格式化变更效果
  const formatEffect = (effect?: HistoryReference['effect']): string => {
    if (!effect) return '';

    const parts: string[] = [];
    if (effect.p_at_5 !== undefined) {
      const delta = effect.p_at_5 >= 0 ? '+' : '';
      parts.push(`P@5${delta}${effect.p_at_5.toFixed(2)}`);
    }
    if (effect.r_at_5 !== undefined) {
      const delta = effect.r_at_5 >= 0 ? '+' : '';
      parts.push(`R@5${delta}${effect.r_at_5.toFixed(2)}`);
    }

    // 添加其他指标
    Object.entries(effect).forEach(([key, value]) => {
      if (key !== 'p_at_5' && key !== 'r_at_5' && value !== undefined) {
        const delta = value >= 0 ? '+' : '';
        parts.push(`${key}${delta}${value.toFixed(2)}`);
      }
    });

    return parts.join(', ');
  };

  return (
    <Timeline
      items={history.map((item) => ({
        children: (
          <div>
            <div style={{ marginBottom: 4 }}>
              <Tag color="blue">{item.version}</Tag>
              <Text type="secondary" style={{ marginLeft: 8 }}>
                {item.changed_at}
              </Text>
            </div>
            <div style={{ marginBottom: 4 }}>
              <Text>
                {String(item.from_value)} → <Text strong>{String(item.to_value)}</Text>
              </Text>
            </div>
            {item.effect && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                效果: {formatEffect(item.effect)}
              </Text>
            )}
          </div>
        ),
      }))}
    />
  );
}
