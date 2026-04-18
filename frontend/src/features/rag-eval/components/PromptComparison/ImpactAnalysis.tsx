/**
 * 影响分析展示组件
 */

import { Typography, Tag, Space } from 'antd';
import { WarningOutlined, CheckCircleOutlined, InfoCircleOutlined } from '@ant-design/icons';
import type { ImpactAnalysis } from './types';

const { Text } = Typography;

interface ImpactAnalysisProps {
  analysis: ImpactAnalysis;
}

export default function ImpactAnalysis({ analysis }: ImpactAnalysisProps) {
  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* 预期效果 */}
      {analysis.expected_effects.length > 0 && (
        <div>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 4 }} />
            预期效果:
          </Text>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {analysis.expected_effects.map((effect, index) => (
              <div key={index} style={{ paddingLeft: 24 }}>
                <Tag color="green">✓</Tag>
                <Text>{effect}</Text>
              </div>
            ))}
          </Space>
        </div>
      )}

      {/* 风险警告 */}
      {analysis.risk_warnings.length > 0 && (
        <div>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            <WarningOutlined style={{ color: '#faad14', marginRight: 4 }} />
            风险警告:
          </Text>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {analysis.risk_warnings.map((warning, index) => (
              <div key={index} style={{ paddingLeft: 24 }}>
                <Tag color="orange">⚠</Tag>
                <Text type="warning">{warning}</Text>
              </div>
            ))}
          </Space>
        </div>
      )}

      {/* 受影响功能 */}
      {analysis.affected_features.length > 0 && (
        <div>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            <InfoCircleOutlined style={{ color: '#1890ff', marginRight: 4 }} />
            受影响功能:
          </Text>
          <Space style={{ paddingLeft: 24 }}>
            {analysis.affected_features.map((feature, index) => (
              <Tag key={index} color="blue">
                {feature}
              </Tag>
            ))}
          </Space>
        </div>
      )}
    </Space>
  );
}
