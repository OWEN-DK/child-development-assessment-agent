/**
 * 提示词对比入口组件（基于模态框）
 */

import { useState, useEffect } from 'react';
import { Modal, Spin, Typography, Divider, message, Button } from 'antd';
import PromptDiffView from './PromptDiffView';
import ChangeSummary from './ChangeSummary';
import ImpactAnalysis from './ImpactAnalysis';
import { getPromptComparison } from '@/api/rag-eval/tuning';
import type { PromptComparison } from './types';

const { Title, Text } = Typography;

interface PromptComparisonModalProps {
  visible: boolean;
  promptKey: string;
  currentVersion?: string;
  targetVersion?: string;
  onClose: () => void;
  onAdopt?: (promptKey: string, version: string) => void;
}

export default function PromptComparisonModal({
  visible,
  promptKey,
  currentVersion,
  targetVersion,
  onClose,
  onAdopt,
}: PromptComparisonModalProps) {
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState<PromptComparison | null>(null);

  useEffect(() => {
    if (visible && promptKey) {
      loadComparison();
    }
  }, [visible, promptKey, currentVersion, targetVersion]);

  const loadComparison = async () => {
    setLoading(true);
    try {
      const data = await getPromptComparison(promptKey, currentVersion, targetVersion);
      setComparison(data);
    } catch {
      message.error('加载提示词对比数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAdopt = () => {
    if (!comparison) return;
    onAdopt?.(comparison.prompt_key, comparison.suggested_version.version);
    message.success('已采纳建议版本');
    onClose();
  };

  return (
    <Modal
      title={
        <Title level={5} style={{ margin: 0 }}>
          提示词对比: {comparison?.prompt_name_zh || comparison?.prompt_key || promptKey}
        </Title>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={1000}
      destroyOnClose
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : comparison ? (
        <div>
          {/* 版本信息 */}
          <div style={{ marginBottom: 16 }}>
            <Text type="secondary">
              当前版本: {comparison.current_version.version}
              {comparison.current_version.created_at && ` (${comparison.current_version.created_at})`}
            </Text>
            <Text type="secondary" style={{ marginLeft: 24 }}>
              建议版本: {comparison.suggested_version.version}
            </Text>
          </div>

          {/* 双列差异展示 */}
          <PromptDiffView
            currentContent={comparison.current_version.content}
            suggestedContent={comparison.suggested_version.content}
          />

          <Divider />

          {/* 变更摘要 */}
          <div style={{ marginBottom: 16 }}>
            <ChangeSummary summary={comparison.diff_summary} />
          </div>

          <Divider />

          {/* 影响分析 */}
          <div style={{ marginBottom: 16 }}>
            <ImpactAnalysis analysis={comparison.impact_analysis} />
          </div>

          <Divider />

          {/* 操作按钮 */}
          <div style={{ textAlign: 'right' }}>
            <Button onClick={onClose} style={{ marginRight: 8 }}>
              取消
            </Button>
            <Button type="primary" onClick={handleAdopt}>
              采纳建议版本
            </Button>
          </div>
        </div>
      ) : (
        <Text type="secondary">暂无对比数据</Text>
      )}
    </Modal>
  );
}
