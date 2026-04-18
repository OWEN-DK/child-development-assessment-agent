/**
 * 配置差异展示组件
 */

import { useState } from 'react';
import { Row, Col, InputNumber, Typography, Tag, Space, Button } from 'antd';
import { notification } from '@shared/lib/notification';
import type { ConfigComparison } from './types';

const { Text } = Typography;

interface ConfigDiffViewProps {
  comparison: ConfigComparison;
  onAdoptSuggested: () => void;
  onAdoptCustom: (value: number) => void;
}

export default function ConfigDiffView({ comparison, onAdoptSuggested, onAdoptCustom }: ConfigDiffViewProps) {
  const [customValue, setCustomValue] = useState<number | null>(null);

  // 格式化值展示
  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'number') return value.toString();
    return JSON.stringify(value);
  };

  // 判断值是否在安全范围内
  const isInSafeRange = (value: number): boolean => {
    if (!comparison.safe_range) return true;
    return value >= comparison.safe_range[0] && value <= comparison.safe_range[1];
  };

  // 判断值是否在推荐范围内
  const isInRecommendedRange = (value: number): boolean => {
    if (!comparison.recommended_range) return true;
    return value >= comparison.recommended_range[0] && value <= comparison.recommended_range[1];
  };

  const handleAdoptCustom = () => {
    if (customValue === null) {
      notification.warning('请输入自定义值');
      return;
    }
    onAdoptCustom(customValue);
  };

  return (
    <div>
      {/* 当前值 → 建议值 → 自定义值 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
            当前值 ({comparison.current_version || '当前'})
          </Text>
          <div
            style={{
              padding: '12px 16px',
              background: '#fafafa',
              border: '1px solid #d9d9d9',
              borderRadius: 6,
              fontSize: 18,
              textAlign: 'center',
            }}
          >
            {formatValue(comparison.current_value)}
          </div>
        </Col>

        <Col span={1} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Text type="secondary" style={{ fontSize: 20 }}>→</Text>
        </Col>

        <Col span={8}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
            建议值
          </Text>
          <div
            style={{
              padding: '12px 16px',
              background: '#f6ffed',
              border: '1px solid #b7eb8f',
              borderRadius: 6,
              fontSize: 18,
              textAlign: 'center',
              color: '#52c41a',
            }}
          >
            {formatValue(comparison.suggested_value)}
          </div>
        </Col>

        <Col span={7}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
            自定义值
          </Text>
          <InputNumber
            style={{ width: '100%' }}
            size="large"
            placeholder="输入自定义值"
            value={customValue}
            onChange={(val) => setCustomValue(val)}
            min={comparison.safe_range?.[0]}
            max={comparison.safe_range?.[1]}
            status={
              customValue !== null && !isInSafeRange(customValue)
                ? 'error'
                : customValue !== null && !isInRecommendedRange(customValue)
                  ? 'warning'
                  : undefined
            }
          />
        </Col>
      </Row>

      {/* 安全范围提示 */}
      {(comparison.safe_range || comparison.recommended_range) && (
        <div style={{ marginBottom: 16 }}>
          {comparison.safe_range && (
            <Tag color="red" style={{ marginRight: 8 }}>
              安全范围: [{comparison.safe_range[0]}, {comparison.safe_range[1]}]
            </Tag>
          )}
          {comparison.recommended_range && (
            <Tag color="orange">
              推荐范围: [{comparison.recommended_range[0]}, {comparison.recommended_range[1]}]
            </Tag>
          )}
        </div>
      )}

      {/* 操作按钮 */}
      <Space>
        <Button type="primary" onClick={onAdoptSuggested}>
          采纳建议值 ({formatValue(comparison.suggested_value)})
        </Button>
        <Button onClick={handleAdoptCustom} disabled={customValue === null}>
          采纳自定义值 ({customValue !== null ? customValue : '-'})
        </Button>
      </Space>
    </div>
  );
}
