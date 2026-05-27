import React from 'react';
import { Card, Steps, Typography } from 'antd';
import { useKnowledgeQAStore } from '../stores/knowledgeQAStore';

const { Paragraph } = Typography;

const STEP_LABELS: Record<string, string> = {
  _connected: '已连接',
  started: '分析问题意图',
  section_1_generating: '正在生成第 1 节',
  section_2_generating: '正在生成第 2 节',
  section_3_generating: '正在生成第 3 节',
  section_4_outline: '正在生成方案大纲',
  section_4_expand: '正在展开运动方案',
  section_5_generating: '正在生成最终结论',
  verify_citations: '正在核验引用依据',
  books_matched: '匹配参考书籍',
  section_1_done: '第 1 节：孩子状态分析',
  section_2_done: '第 2 节：问题识别',
  section_3_done: '第 3 节：运动类型推荐',
  section_4_outline_done: '第 4 节：方案大纲',
  section_4_done: '第 4 节：运动方案',
  section_5_done: '第 5 节：最终结论',
  verify_citations_done: '核验引用依据',
  completed: '完成',
};

const MAIN_STEPS = [
  'started',
  'books_matched',
  'section_1_done',
  'section_2_done',
  'section_3_done',
  'section_4_outline_done',
  'section_4_done',
  'section_5_done',
  'verify_citations_done',
  'completed',
];

const SECTION_TITLES: Record<number, string> = {
  1: '第 1 节：孩子状态分析',
  2: '第 2 节：问题识别',
  3: '第 3 节：运动类型推荐',
  4: '第 4 节：运动方案',
  5: '第 5 节：最终结论',
};

export const ProgressPanel: React.FC = () => {
  const progress = useKnowledgeQAStore((s) => s.progress);
  const completedSections = useKnowledgeQAStore((s) => s.completedSections);

  // 没有 progress 时也要显示等待状态，避免用户看到空白卡住
  const currentStep = progress?.step;
  const stepIndex = currentStep ? MAIN_STEPS.indexOf(currentStep) : 0;
  const current = stepIndex >= 0 ? stepIndex : 0;

  const items = MAIN_STEPS.map((key, idx) => {
    const isCurrent = key === currentStep;
    const isGhostCurrent = !isCurrent && currentStep && !MAIN_STEPS.includes(currentStep) && idx === 0;
    const activeKey = isCurrent || isGhostCurrent;

    return {
      title: STEP_LABELS[key] || key,
      description:
        !progress
          ? idx === 0
            ? '正在连接…'
            : undefined
          : activeKey
            ? (progress.message)
            : undefined,
      status: !progress
        ? undefined
        : isCurrent
          ? ('process' as const)
          : undefined,
    };
  });

  return (
    <Card size="small" style={{ marginTop: 24 }}>
      <Steps
        direction="vertical"
        size="small"
        current={current}
        items={items}
      />

      {/* 流式过程中增量渲染已完成节内容预览 */}
      {completedSections.length > 0 && (
        <div style={{ marginTop: 16 }}>
          {completedSections.map((sec) => (
            <Card
              key={sec.index}
              size="small"
              type="inner"
              title={sec.title || SECTION_TITLES[sec.index] || `第 ${sec.index} 节`}
              style={{ marginBottom: 8 }}
            >
              <Paragraph
                ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
              >
                {sec.content}
              </Paragraph>
            </Card>
          ))}
        </div>
      )}
    </Card>
  );
};
