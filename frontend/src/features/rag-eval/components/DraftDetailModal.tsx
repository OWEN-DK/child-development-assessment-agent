/**
 * 草稿详情弹窗组件
 */

import { useEffect, useState } from 'react';
import { Modal, Descriptions, Tag, Spin, Empty, Typography } from 'antd';
import { getDraft } from '@/api/rag-test';
import type { TestCaseDraft } from '@/api/rag-test';

const { Text } = Typography;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: '待审核', color: 'orange' },
  reviewed: { label: '已通过', color: 'green' },
  rejected: { label: '已拒绝', color: 'red' },
  imported: { label: '已归入', color: 'blue' },
};

const DOMAIN_MAP: Record<string, string> = {
  gross_motor: '大运动',
  fine_motor: '精细运动',
  language: '语言',
  cognitive: '认知',
  social_emotional: '社交情感',
  sensory_integration: '感觉统合',
};

interface DraftDetailModalProps {
  visible: boolean;
  draftId: string | null;
  onClose: () => void;
  onReview?: (draftId: string, action: 'reviewed' | 'rejected') => void;
}

export default function DraftDetailModal({ visible, draftId, onClose, onReview }: DraftDetailModalProps) {
  const [draft, setDraft] = useState<TestCaseDraft | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!visible || !draftId) return;

    const fetchDraft = async () => {
      setLoading(true);
      setDraft(null);
      try {
        const data = await getDraft(draftId);
        setDraft(data);
      } catch (e) {
        console.error('获取草稿详情失败:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchDraft();
  }, [visible, draftId]);

  const handleReview = async (action: 'reviewed' | 'rejected') => {
    if (!draftId || !onReview) return;
    await onReview(draftId, action);
    onClose();
  };

  const footer = draft?.status === 'draft' && onReview ? (
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <Text type="secondary">创建时间：{draft.created_at ? new Date(draft.created_at).toLocaleString('zh-CN') : '-'}</Text>
      <div>
        <button
          onClick={() => handleReview('rejected')}
          style={{ marginRight: 8, padding: '4px 16px', cursor: 'pointer', border: '1px solid #ff4d4f', background: '#fff', color: '#ff4d4f', borderRadius: 4 }}
        >
          拒绝
        </button>
        <button
          onClick={() => handleReview('reviewed')}
          style={{ padding: '4px 16px', cursor: 'pointer', border: 'none', background: '#52c41a', color: '#fff', borderRadius: 4 }}
        >
          通过
        </button>
      </div>
    </div>
  ) : (
    <Text type="secondary">创建时间：{draft?.created_at ? new Date(draft.created_at).toLocaleString('zh-CN') : '-'}</Text>
  );

  return (
    <Modal
      title="草稿详情"
      open={visible}
      onCancel={onClose}
      footer={footer}
      width={720}
      destroyOnClose
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : !draft ? (
        <Empty description="草稿未找到" />
      ) : (
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="查询语句" span={2}>
            <Text strong>{draft.query}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="来源文档">
            {draft.source_document_name || draft.source_document_id.slice(0, 8)}
          </Descriptions.Item>
          <Descriptions.Item label="年龄">
            {(() => {
              if (!draft.age && draft.age !== 0) return '-';
              const years = Math.floor(draft.age / 12);
              const months = draft.age % 12;
              if (years > 0 && months > 0) return `${years}岁${months}月`;
              if (years > 0) return `${years}岁`;
              return `${months}月`;
            })()}
          </Descriptions.Item>
          <Descriptions.Item label="领域">
            <Tag color="blue">{DOMAIN_MAP[draft.domain] || draft.domain}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={STATUS_MAP[draft.status]?.color}>{STATUS_MAP[draft.status]?.label || draft.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="描述" span={2}>
            {draft.description || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="期望知识点" span={2}>
            {draft.expected_knowledge_ids && draft.expected_knowledge_ids.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {draft.expected_knowledge_ids.map((id, idx) => (
                  <li key={idx}>{id}</li>
                ))}
              </ul>
            ) : (
              '-'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="期望关键词" span={2}>
            {draft.expected_keywords && draft.expected_keywords.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {draft.expected_keywords.map((kw, idx) => (
                  <Tag key={idx}>{kw}</Tag>
                ))}
              </div>
            ) : (
              '-'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="答题要点" span={2}>
            {draft.answer_points && draft.answer_points.length > 0 ? (
              <ol style={{ margin: 0, paddingLeft: 20 }}>
                {draft.answer_points.map((point, idx) => (
                  <li key={idx}>{point}</li>
                ))}
              </ol>
            ) : (
              '-'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="专业术语" span={2}>
            {draft.professional_terms && draft.professional_terms.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {draft.professional_terms.map((term, idx) => (
                  <Tag key={idx} color="purple">{term}</Tag>
                ))}
              </div>
            ) : (
              '-'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="年龄要求" span={2}>
            {draft.age_requirement || '-'}
          </Descriptions.Item>
          {draft.generation_params && (
            <Descriptions.Item label="生成参数" span={2}>
              <pre style={{ margin: 0, fontSize: 12, background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                {JSON.stringify(draft.generation_params, null, 2)}
              </pre>
            </Descriptions.Item>
          )}
        </Descriptions>
      )}
    </Modal>
  );
}
