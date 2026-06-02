import React, { useRef, useEffect } from 'react';
import { Card, Steps } from 'antd';
import { useKnowledgeQAStore } from '../stores/knowledgeQAStore';


// ── 用户可感知的关键步骤（精简版）──
const MAIN_STEPS = [
  { key: 'started',           label: '分析问题' },
  { key: 'books_matched',     label: '匹配书籍' },
  { key: 'build_bundle_done', label: '检索知识' },
  { key: 'section_1_done',    label: '分析孩子状态' },
  { key: 'section_2_done',    label: '识别问题' },
  { key: 'section_3_done',    label: '推荐运动类型' },
  { key: 'section_4_done',    label: '制定运动方案' },
  { key: 'section_5_done',    label: '总结建议' },
  { key: 'completed',         label: '完成' },
];

const MAIN_STEP_KEYS = MAIN_STEPS.map(s => s.key);

// ── 所有步骤的中文化标签（含中间步骤）──
const STEP_LABELS: Record<string, string> = {
  _connected: '已连接',
  started: '分析问题意图',
  books_matched: '匹配参考书籍',
  prefetch_context: '预取知识上下文',
  build_bundle: '统一检索知识',
  build_bundle_done: '知识检索完成',
  build_bundle_failed: '检索降级',
  fast_knowledge_match: '匹配自定义知识',
  query_analysis: '分析问题意图',
  section_1_generating: '分析孩子状态',
  section_1_done: '孩子状态分析',
  section_2_generating: '识别问题',
  section_2_done: '问题识别',
  section_3_generating: '推荐运动类型',
  section_3_done: '运动类型推荐',
  s3_citations: '生成运动引用',
  s3_citations_done: '运动引用完成',
  section_4_outline: '生成方案大纲',
  section_4_expand: '展开运动方案',
  section_4_done: '运动方案',
  s4_citations: '生成方案引用',
  s4_citations_done: '方案引用完成',
  synthesis_done: '知识综合',
  section_5_done: '总结建议',
  verify_citations: '核验引用依据',
  verify_citations_done: '核验完成',
  completed: '完成',
};

export const ProgressPanel: React.FC = () => {
  const progress = useKnowledgeQAStore((s) => s.progress);

  const currentStep = progress?.step;

  // 找到当前步骤在 MAIN_STEPS 中的位置
  const currentMainIndex = currentStep
    ? MAIN_STEP_KEYS.indexOf(currentStep)
    : -1;

  // 用 ref 跟踪最后一个有效主步骤索引
  const lastValidIndexRef = useRef<number>(0);

  useEffect(() => {
    if (currentMainIndex >= 0) {
      lastValidIndexRef.current = currentMainIndex;
    }
  }, [currentMainIndex]);

  const current = lastValidIndexRef.current;

  // 判断当前步骤是否是主步骤
  const isMainStep = currentMainIndex >= 0;

  // 中间步骤的消息显示
  const displayMessage = isMainStep
    ? (progress?.message || '')
    : (progress?.message || STEP_LABELS[currentStep || ''] || '');

  const items = MAIN_STEPS.map((step, idx) => {
    const isCurrent = step.key === currentStep;
    const isGhostCurrent = !isMainStep && idx === current && currentStep;

    return {
      title: step.label,
      description: !progress
        ? idx === 0 ? '正在连接…' : undefined
        : isCurrent || isGhostCurrent
          ? displayMessage
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
    </Card>
  );
};
