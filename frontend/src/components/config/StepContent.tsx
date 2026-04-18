import React from 'react';
import { Card, Typography, Divider } from 'antd';
import { ConfigField } from './ConfigField';
import { RecommendationTip } from './RecommendationTip';
import { useConfigStore } from '../../store/configStore';

const { Title, Paragraph } = Typography;

interface StepContentProps {
  step: {
    title: string;
    description: string;
    categories: string[];
    skipAction: string;
  };
  stepIndex: number;
}

export const StepContent: React.FC<StepContentProps> = ({ step }) => {
  const { configFields, draftChanges, updateDraft } = useConfigStore();
  
  const filteredFields = configFields.filter(f =>
    step.categories.some((cat: string) =>
      f.category === cat || f.category.startsWith(`${cat}.`)
    )
  );
  
  const groupedFields = groupByScene(filteredFields);
  
  if (filteredFields.length === 0) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center' }}>
        <Paragraph type="secondary">
          此步骤暂无可配置项，可以跳过或继续下一步
        </Paragraph>
      </div>
    );
  }
  
  return (
    <div style={{ padding: '0 16px' }}>
      <Title level={4}>{step.title}</Title>
      <Paragraph type="secondary">{step.description}</Paragraph>
      
      <Divider />
      
      {Object.entries(groupedFields).map(([scene, fields]) => (
        <Card
          key={scene}
          title={formatSceneTitle(scene)}
          size="small"
          style={{ marginBottom: 16 }}
          extra={<RecommendationTip scene={scene} />}
        >
          {fields.map(field => {
            const currentValue = draftChanges[field.key] !== undefined
              ? draftChanges[field.key]
              : field.current_value ?? field.default_value;
            
            return (
              <div key={field.key} style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>
                  {field.key.split('.').pop()}
                  {field.description && (
                    <span style={{ fontWeight: 400, color: '#999', marginLeft: 8 }}>
                      {field.description}
                    </span>
                  )}
                </div>
                <ConfigField
                  field={field}
                  value={currentValue}
                  onChange={(value) => updateDraft(field.key, value)}
                />
              </div>
            );
          })}
        </Card>
      ))}
    </div>
  );
};

function groupByScene(fields: any[]) {
  const grouped: Record<string, any[]> = {};
  fields.forEach(f => {
    const scene = f.category.split('.')[1] || f.category;
    if (!grouped[scene]) grouped[scene] = [];
    grouped[scene].push(f);
  });
  return grouped;
}

function formatSceneTitle(scene: string): string {
  return scene
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase());
}
