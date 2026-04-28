import { Tag } from 'antd';

interface AgeStageTagProps {
  ageStageLabel: string;
}

export function AgeStageTag({ ageStageLabel }: AgeStageTagProps) {
  return <Tag>{ageStageLabel}</Tag>;
}
