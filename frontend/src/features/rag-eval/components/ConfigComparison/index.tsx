/**
 * 配置对比入口组件（基于模态框）
 */

import { useState, useEffect } from 'react';
import { Modal, Spin, Typography, Divider, message } from 'antd';
import ConfigDiffView from './ConfigDiffView';
import HistoryReference from './HistoryReference';
import { getConfigComparison } from '@/api/rag-eval/tuning';
import type { ConfigComparison } from './types';

const { Title, Text } = Typography;

interface ConfigComparisonModalProps {
  visible: boolean;
  paramName: string;
  currentVersion?: string;
  onClose: () => void;
  onAdopt?: (paramName: string, value: unknown) => void;
}

export default function ConfigComparisonModal({
  visible,
  paramName,
  currentVersion,
  onClose,
  onAdopt,
}: ConfigComparisonModalProps) {
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState<ConfigComparison | null>(null);

  useEffect(() => {
    if (visible && paramName) {
      loadComparison();
    }
  }, [visible, paramName, currentVersion]);

  const loadComparison = async () => {
    setLoading(true);
    try {
      const data = await getConfigComparison(paramName, currentVersion);
      setComparison(data);
    } catch {
      message.error('加载配置对比数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAdoptSuggested = () => {
    if (!comparison) return;
    onAdopt?.(comparison.param_name, comparison.suggested_value);
    message.success('已采纳建议值');
    onClose();
  };

  const handleAdoptCustom = (value: number) => {
    if (!comparison) return;
    onAdopt?.(comparison.param_name, value);
    message.success('已采纳自定义值');
    onClose();
  };

  return (
    <Modal
      title={
        <Title level={5} style={{ margin: 0 }}>
          配置对比: {comparison?.param_name_zh || comparison?.param_name || paramName}
        </Title>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={800}
      destroyOnClose
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : comparison ? (
        <div>
          {/* 差异展示 */}
          <ConfigDiffView
            comparison={comparison}
            onAdoptSuggested={handleAdoptSuggested}
            onAdoptCustom={handleAdoptCustom}
          />

          <Divider />

          {/* 历史参考 */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 12 }}>
              历史参考:
            </Text>
            <HistoryReference history={comparison.history_references} />
          </div>
        </div>
      ) : (
        <Text type="secondary">暂无对比数据</Text>
      )}
    </Modal>
  );
}
