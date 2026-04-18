/**
 * 推荐模式 - 默认模式，展示调优建议
 */

import { useState, useEffect } from 'react';
import { Card, Button, Space, Tag, Typography, Empty, Spin, Popconfirm } from 'antd';
import { notification } from '@shared/lib/notification';
import { CheckOutlined, CloseOutlined, DiffOutlined } from '@ant-design/icons';
import type { TuningSuggestion } from './types';
import { getSuggestions, ignoreSuggestion } from '@/api/rag-eval/tuning';
import { useRecommendationPanelStore } from '@/features/rag-eval/stores/recommendationPanelStore';
import ConfigComparisonModal from '../ConfigComparison';
import PromptComparisonModal from '../PromptComparison';

const { Text } = Typography;

const PRIORITY_COLORS: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'blue',
};

const SOURCE_LABELS: Record<string, string> = {
  rule_engine: '规则引擎',
  history: '历史分析',
  llm: 'LLM诊断',
};

interface RecommendationModeProps {
  reportId: string;
  testSetId: string;
}

export default function RecommendationMode({ reportId, testSetId }: RecommendationModeProps) {
  const [suggestions, setSuggestions] = useState<TuningSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const { ignoredSuggestions, adoptSuggestionDetail, ignoreSuggestion: markIgnored } =
    useRecommendationPanelStore();

  // 对比模态框状态
  const [configComparisonVisible, setConfigComparisonVisible] = useState(false);
  const [configComparisonParam, setConfigComparisonParam] = useState<string>('');
  const [promptComparisonVisible, setPromptComparisonVisible] = useState(false);
  const [promptComparisonKey, setPromptComparisonKey] = useState<string>('');

  useEffect(() => {
    loadSuggestions();
  }, [reportId, testSetId]);

  const loadSuggestions = async () => {
    setLoading(true);
    try {
      const data = await getSuggestions(reportId, testSetId);
      setSuggestions(data);
    } catch {
      notification.error('加载建议失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAdopt = async (suggestion: TuningSuggestion) => {
    adoptSuggestionDetail({
      id: suggestion.id,
      param_name: suggestion.param_name,
      current_value: suggestion.current_value,
      suggested_value: suggestion.suggested_value,
      reason: suggestion.reason,
      expected_effect: suggestion.expected_effect,
      source_version: suggestion.source,
    });
    notification.success('已采纳建议');
  };

  const handleIgnore = async (suggestion: TuningSuggestion) => {
    try {
      await ignoreSuggestion(suggestion.id, {
        scope: 'report',
        test_set_id: testSetId,
        report_id: reportId,
        param_name: suggestion.param_name,
      });
      markIgnored(suggestion.id);
      notification.success('已忽略建议');
    } catch {
      notification.error('忽略建议失败');
    }
  };

  // 打开配置对比
  const handleOpenConfigComparison = (paramName: string) => {
    setConfigComparisonParam(paramName);
    setConfigComparisonVisible(true);
  };

  // 打开提示词对比
  const handleOpenPromptComparison = (promptKey: string) => {
    setPromptComparisonKey(promptKey);
    setPromptComparisonVisible(true);
  };

  // 采纳配置值
  const handleAdoptConfig = (paramName: string, _value: unknown) => {
    // 找到对应的建议并采纳
    const suggestion = suggestions.find((s) => s.param_name === paramName);
    if (suggestion) {
      handleAdopt(suggestion);
    }
  };

  // 采纳提示词版本
  const handleAdoptPrompt = (promptKey: string, _version: string) => {
    // 找到对应的建议并采纳
    const suggestion = suggestions.find((s) => s.param_name === promptKey);
    if (suggestion) {
      handleAdopt(suggestion);
    }
  };

  if (loading) {
    return <Spin size="small" style={{ display: 'block', margin: '20px auto' }} />;
  }

  if (suggestions.length === 0) {
    return <Empty description="暂无调优建议" />;
  }

  // 过滤掉已忽略的建议
  const activeSuggestions = suggestions.filter(
    (s) => !ignoredSuggestions.includes(s.id)
  );

  if (activeSuggestions.length === 0) {
    return <Empty description="所有建议已被忽略" />;
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {activeSuggestions.map((suggestion) => (
        <Card key={suggestion.id} size="small">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>{suggestion.param_name}</Text>
                {suggestion.priority && (
                  <Tag color={PRIORITY_COLORS[suggestion.priority]} style={{ marginLeft: 8 }}>
                    {suggestion.priority === 'high' ? '高' : suggestion.priority === 'medium' ? '中' : '低'}
                  </Tag>
                )}
                {suggestion.source && (
                  <Tag style={{ marginLeft: 4 }}>
                    {SOURCE_LABELS[suggestion.source] || suggestion.source}
                  </Tag>
                )}
              </div>
              {suggestion.reason && (
                <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>
                  {suggestion.reason}
                </Text>
              )}
              {suggestion.current_value && suggestion.suggested_value && (
                <Text type="secondary">
                  当前: {JSON.stringify(suggestion.current_value)} → 建议: {JSON.stringify(suggestion.suggested_value)}
                </Text>
              )}
            </div>
            <Space>
              <Button
                size="small"
                icon={<DiffOutlined />}
                onClick={() => {
                  // 根据建议类型打开不同的对比模态框
                  // 这里假设 param_name 包含 "prompt" 关键字时为提示词建议
                  if (suggestion.param_name.toLowerCase().includes('prompt')) {
                    handleOpenPromptComparison(suggestion.param_name);
                  } else {
                    handleOpenConfigComparison(suggestion.param_name);
                  }
                }}
              >
                查看对比
              </Button>
              <Button
                type="primary"
                size="small"
                icon={<CheckOutlined />}
                onClick={() => handleAdopt(suggestion)}
                disabled={suggestion.applied}
              >
                采纳
              </Button>
              <Popconfirm
                title="确认忽略"
                description="确定要忽略这条建议吗？"
                onConfirm={() => handleIgnore(suggestion)}
                okText="确定"
                cancelText="取消"
              >
                <Button size="small" icon={<CloseOutlined />}>
                  忽略
                </Button>
              </Popconfirm>
            </Space>
          </div>
        </Card>
      ))}

      {/* 配置对比模态框 */}
      <ConfigComparisonModal
        visible={configComparisonVisible}
        paramName={configComparisonParam}
        onClose={() => setConfigComparisonVisible(false)}
        onAdopt={handleAdoptConfig}
      />

      {/* 提示词对比模态框 */}
      <PromptComparisonModal
        visible={promptComparisonVisible}
        promptKey={promptComparisonKey}
        onClose={() => setPromptComparisonVisible(false)}
        onAdopt={handleAdoptPrompt}
      />
    </Space>
  );
}
