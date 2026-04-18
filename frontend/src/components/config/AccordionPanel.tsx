import React from 'react';
import { Collapse } from 'antd';
import { ConfigCard } from './ConfigCard';

const { Panel } = Collapse;

interface AccordionPanelProps {
  fields: Array<{
    key: string;
    label: string;
    type: string;
    category: string;
    min?: number;
    max?: number;
    options?: { label: string; value: any }[];
    sensitive?: boolean;
    description?: string;
    defaultValue: any;
  }>;
  draftChanges: Record<string, any>;
  originalValues: Record<string, any>;
  onUpdateDraft: (key: string, value: any) => void;
  onUndo: (key: string) => void;
}

export const AccordionPanel: React.FC<AccordionPanelProps> = ({
  fields,
  draftChanges,
  originalValues,
  onUpdateDraft,
  onUndo
}) => {
  // 按分类分组
  const groupedFields = fields.reduce((groups, field) => {
    const category = field.category || '其他配置';
    if (!groups[category]) {
      groups[category] = [];
    }
    groups[category].push(field);
    return groups;
  }, {} as Record<string, typeof fields>);

  return (
    <Collapse defaultActiveKey={Object.keys(groupedFields).slice(0, 3)}>
      {Object.entries(groupedFields).map(([category, categoryFields]) => (
        <Panel header={category} key={category}>
          {categoryFields.map(field => {
            const currentValue = draftChanges[field.key] !== undefined
              ? draftChanges[field.key]
              : field.defaultValue;
            const originalValue = originalValues[field.key] ?? field.defaultValue;
            const isModified = draftChanges[field.key] !== undefined &&
              draftChanges[field.key] !== originalValue;

            return (
              <ConfigCard
                key={field.key}
                field={field}
                value={currentValue}
                originalValue={originalValue}
                isModified={isModified}
                onChange={(value) => onUpdateDraft(field.key, value)}
                onUndo={() => onUndo(field.key)}
              />
            );
          })}
        </Panel>
      ))}
    </Collapse>
  );
};
