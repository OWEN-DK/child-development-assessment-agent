/**
 * 审查抽屉容器组件
 */

import { Drawer, Button, Space, Typography, Divider, Empty, message } from 'antd';
import { useState, useMemo } from 'react';
import ReviewItem from './ReviewItem';
import ImpactPreview from './ImpactPreview';
import type { AdoptedSuggestion, ImpactPreview as ImpactPreviewType } from './types';

const { Text, Title } = Typography;

interface ReviewDrawerProps {
  open: boolean;
  adoptedSuggestions: AdoptedSuggestion[];
  onClose: () => void;
  onRemove: (id: string) => void;
  onCustomValueChange: (id: string, value: string) => void;
  onSaveVersion: (suggestions: AdoptedSuggestion[]) => Promise<void>;
  onCancelAll: () => void;
}

export default function ReviewDrawer({
  open,
  adoptedSuggestions,
  onClose,
  onRemove,
  onCustomValueChange,
  onSaveVersion,
  onCancelAll,
}: ReviewDrawerProps) {
  const [saving, setSaving] = useState(false);

  // 计算影响预览
  const impactPreview: ImpactPreviewType | null = useMemo(() => {
    if (adoptedSuggestions.length === 0) return null;

    const metrics: Record<string, {
      current: number;
      predicted_min: number;
      predicted_max: number;
      delta_min: number;
      delta_max: number;
    }> = {};

    adoptedSuggestions.forEach((item) => {
      if (item.expected_effect) {
        Object.entries(item.expected_effect).forEach(([key, value]) => {
          if (typeof value === 'object' && value !== null && 'min' in value && 'max' in value) {
            const effect = value as { min: number; max: number };
            if (!metrics[key]) {
              metrics[key] = {
                current: 0,
                predicted_min: effect.min,
                predicted_max: effect.max,
                delta_min: effect.min,
                delta_max: effect.max,
              };
            } else {
              metrics[key].predicted_min = Math.min(metrics[key].predicted_min, effect.min);
              metrics[key].predicted_max = Math.max(metrics[key].predicted_max, effect.max);
              metrics[key].delta_min += effect.min;
              metrics[key].delta_max += effect.max;
            }
          } else if (typeof value === 'number') {
            // 简单数值型预期
            if (!metrics[key]) {
              metrics[key] = {
                current: 0,
                predicted_min: value,
                predicted_max: value,
                delta_min: value,
                delta_max: value,
              };
            }
          }
        });
      }
    });

    return {
      metrics,
      total_changes: adoptedSuggestions.length,
    };
  }, [adoptedSuggestions]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSaveVersion(adoptedSuggestions);
      message.success('新版本已保存');
      onClose();
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      title={
        <Space>
          <Title level={5} style={{ margin: 0 }}>📋 变更审查清单</Title>
        </Space>
      }
      placement="right"
      width="40%"
      style={{ minWidth: 480 }}
      open={open}
      onClose={onClose}
      extra={
        <Button type="link" onClick={onClose}>
          返回
        </Button>
      }
      footer={
        adoptedSuggestions.length > 0 ? (
          <Space>
            <Button onClick={onCancelAll}>取消全部</Button>
            <Button type="primary" loading={saving} onClick={handleSave}>
              保存为新版本
            </Button>
          </Space>
        ) : undefined
      }
    >
      {adoptedSuggestions.length === 0 ? (
        <Empty description="暂无已采纳的建议" />
      ) : (
        <>
          <div style={{ marginBottom: 16 }}>
            <Text>
              本次变更包含 <Text strong>{adoptedSuggestions.length}</Text> 项修改，保存后将创建新版本。
            </Text>
          </div>

          <Divider />

          {adoptedSuggestions.map((item, index) => (
            <ReviewItem
              key={item.id}
              item={item}
              index={index + 1}
              onRemove={onRemove}
              onCustomValueChange={onCustomValueChange}
            />
          ))}

          <Divider />

          <ImpactPreview impact={impactPreview} />
        </>
      )}
    </Drawer>
  );
}
