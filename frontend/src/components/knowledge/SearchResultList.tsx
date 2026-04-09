import React from 'react';
import { List, Button, Space, Tag, Typography, Pagination, Empty } from 'antd';
import { EyeOutlined, FileTextOutlined } from '@ant-design/icons';
import type { SearchResultItem } from '../../api/knowledge/types';
import { highlightKeywords } from '../../utils/highlight';
import styles from './SearchResultList.module.scss';

interface SearchResultListProps {
  results: SearchResultItem[];
  loading: boolean;
  query: string;
  total: number;
  currentPage: number;
  pageSize: number;
  onPageChange: (page: number, pageSize?: number) => void;
  onPreview: (item: SearchResultItem) => void;
}

export const SearchResultList: React.FC<SearchResultListProps> = React.memo(({
  results,
  loading: _loading,
  query,
  total,
  currentPage,
  pageSize,
  onPageChange,
  onPreview,
}) => {
  if (results.length === 0) {
    return (
      <Empty
        description={
          query ? '没有找到相关内容，请尝试其他关键词' : '请输入关键词开始搜索'
        }
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <>
      <List
        dataSource={results}
        renderItem={(item) => (
          <List.Item
            key={item.id}
            className={styles.resultItem}
            actions={[
              <Button
                type="link"
                size="small"
                icon={<EyeOutlined />}
                onClick={() => onPreview(item)}
              >
                查看详情
              </Button>
            ]}
          >
            <List.Item.Meta
              avatar={<FileTextOutlined style={{ fontSize: '24px', color: '#1890ff' }} />}
              title={
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <div className={styles.resultTitle}>
                    {highlightKeywords(
                      item.content.slice(0, 100) + (item.content.length > 100 ? '...' : ''),
                      query,
                      styles.highlight
                    )}
                  </div>
                  <Space size="small" wrap>
                    <Tag color="blue">相关度: {(item.score * 100).toFixed(1)}%</Tag>
                    <Tag color="green">来源: {item.source_book}</Tag>
                    {item.page_label && (
                      <Tag color="orange">
                        {/^\d+$/.test(item.page_label) ? 
                          '第 ' + item.page_label + ' 页' : 
                          item.page_label.includes('/') ? 
                            '章节: ' + (item.chapter_title || item.page_label.split('/').pop()) : 
                            item.page_label
                        }
                      </Tag>
                    )}
                  </Space>
                </Space>
              }
              description={
                <div className={styles.resultMeta}>
                  {Array.isArray(item.topics) && item.topics.length > 0 && (
                    <div className={styles.topicRow}>
                      <Typography.Text type="secondary" strong>主题:</Typography.Text>
                      <Space wrap size="small" style={{ marginLeft: 8 }}>
                        {item.topics.map((topic: string, idx: number) => (
                          <Tag key={idx}>{topic}</Tag>
                        ))}
                      </Space>
                    </div>
                  )}
                  {Array.isArray(item.brain_regions) && item.brain_regions.length > 0 && (
                    <div className={styles.topicRow}>
                      <Typography.Text type="secondary" strong>脑区:</Typography.Text>
                      <Space wrap size="small" style={{ marginLeft: 8 }}>
                        {item.brain_regions.map((region: string, idx: number) => (
                          <Tag key={idx} color="cyan">{region}</Tag>
                        ))}
                      </Space>
                    </div>
                  )}
                </div>
              }
            />
          </List.Item>
        )}
      />

      {total > pageSize && (
        <div className={styles.pagination}>
          <Pagination
            current={currentPage}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            showTotal={(total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`}
            onChange={(page) => onPageChange(page)}
            onShowSizeChange={(_, size) => onPageChange(1, size)}
          />
        </div>
      )}
    </>
  );
});
