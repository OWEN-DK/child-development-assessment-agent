import { Collapse, Space, Typography, Button } from 'antd';
import { CaretRightOutlined } from '@ant-design/icons';
import { useState } from 'react';
import type { DiagnosisResult, LayerResult } from '@entities/rag-eval';
import { LayerResultCard } from './LayerResultCard';
import { LAYER_NAMES } from '@entities/rag-eval';

const { Title, Text } = Typography;

interface DiagnosisPanelProps {
  diagnosis: DiagnosisResult;
}

export function DiagnosisPanel({ diagnosis }: DiagnosisPanelProps) {
  const [activeKeys, setActiveKeys] = useState<string[]>([]);

  const allKeys = ['1', '2', '3', '4', '5', '6'];

  const handleExpandAll = () => setActiveKeys(allKeys);
  const handleCollapseAll = () => setActiveKeys([]);

  const layerResults: LayerResult[] = [
    diagnosis.layer1,
    diagnosis.layer2,
    diagnosis.layer3,
    diagnosis.layer4,
    diagnosis.layer5,
    diagnosis.layer6,
  ];

  const items = layerResults.map((layer) => ({
    key: String(layer.layer),
    label: (
      <Space>
        <Text strong>
          Layer {layer.layer}: {LAYER_NAMES[String(layer.layer)] || layer.name}
        </Text>
        <Text type="secondary">
          {layer.issues.length > 0 ? `${layer.issues.length} 个问题` : '无问题'}
        </Text>
      </Space>
    ),
    children: <LayerResultCard result={layer} />,
  }));

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}>六层诊断详情</Title>
          <Text type="secondary">
            综合健康度: {Math.round(diagnosis.overall_health * 100)}% | 总问题: {diagnosis.total_issues} | 严重: {diagnosis.critical_issues}
          </Text>
        </Space>
        <Space>
          <Button size="small" onClick={handleExpandAll}>展开全部</Button>
          <Button size="small" onClick={handleCollapseAll}>折叠全部</Button>
        </Space>
      </div>
      <Collapse
        activeKey={activeKeys}
        onChange={(keys) => setActiveKeys(Array.isArray(keys) ? keys as string[] : [keys as string])}
        expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} />}
        items={items}
        style={{ background: 'transparent' }}
      />
    </div>
  );
}
