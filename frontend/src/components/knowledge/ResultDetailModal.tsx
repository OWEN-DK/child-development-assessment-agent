import React from 'react';
import { Modal, Descriptions, Divider, Typography, Space, Tag, Button } from 'antd';
import type { SearchResultItem } from '../../api/knowledge/types';
import { highlightKeywords } from '../../utils/highlight';
import { formatPageLabel } from '../../utils/formatters';

interface ResultDetailModalProps {
  item: SearchResultItem | null;
  visible: boolean;
  query: string;
  onClose: () => void;
}

export const ResultDetailModal: React.FC<ResultDetailModalProps> = ({
  item,
  visible,
  query,
  onClose,
}) => {
  if (!item) return null;

  return (
    <Modal
      title="内容详情"
      open={visible}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>
      ]}
    >
      <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
        <Descriptions.Item label="来源文档" span={2}>
          {item.source_book}
        </Descriptions.Item>
        {item.chapter_title && (
          <Descriptions.Item label="章节" span={2}>
            {item.chapter_title}
          </Descriptions.Item>
        )}
        {item.page_label && (
          <Descriptions.Item label="位置">
            {formatPageLabel(item.page_label, item.chapter_title)}
          </Descriptions.Item>
        )}
        <Descriptions.Item label="相关度">
          {(item.score * 100).toFixed(2)}%
        </Descriptions.Item>
      </Descriptions>

      <Divider />

      <Typography.Title level={5}>内容</Typography.Title>
      <div>
        <Typography.Paragraph>
          {highlightKeywords(item.content, query)}
        </Typography.Paragraph>
      </div>

      {Array.isArray(item.topics) && item.topics.length > 0 && (
        <>
          <Divider />
          <Typography.Title level={5}>主题标签</Typography.Title>
          <Space wrap>
            {item.topics.map((topic, idx) => (
              <Tag key={idx}>{topic}</Tag>
            ))}
          </Space>
        </>
      )}

      {Array.isArray(item.brain_regions) && item.brain_regions.length > 0 && (
        <>
          <Divider />
          <Typography.Title level={5}>刺激脑区</Typography.Title>
          <Space wrap>
            {item.brain_regions.map((region, idx) => (
              <Tag key={idx} color="cyan">{region}</Tag>
            ))}
          </Space>
        </>
      )}
    </Modal>
  );
};
