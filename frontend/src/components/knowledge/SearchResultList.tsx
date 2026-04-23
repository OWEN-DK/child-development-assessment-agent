import React from 'react';
import { Button, Flex, Tag, Typography, Pagination, Empty, Tooltip, Card } from 'antd';
import { EyeOutlined, FileTextOutlined } from '@ant-design/icons';
import type { SearchResultItem } from '../../api/knowledge/types';
import { highlightKeywords } from '@shared/lib/highlight';
import styles from './SearchResultList.module.scss';

const getAgeFitScoreColor = (score: number): string => {
  if (score >= 0.8) return 'green';
  if (score >= 0.6) return 'blue';
  if (score >= 0.4) return 'orange';
  return 'red';
};

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
      <Flex vertical gap="small">
        {results.map((item) => (
          <Card key={item.id} size="small" className={styles.resultItem} extra={
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => onPreview(item)}
            >
              查看详情
            </Button>
          }>
            <Flex vertical gap="small" style={{ width: '100%' }}>
              <Flex align="flex-start" gap="small">
                <FileTextOutlined style={{ fontSize: '24px', color: '#1890ff', marginTop: 4 }} />
                <Flex vertical gap="small" style={{ flex: 1 }}>
                  <div className={styles.resultTitle}>
                    {highlightKeywords(
                      item.content.slice(0, 100) + (item.content.length > 100 ? '...' : ''),
                      query,
                      styles.highlight
                    )}
                  </div>
                  <Flex gap="small" wrap>
                    <Tooltip title="检索相关度：内容与查询关键词的相关程度，来自 Cross-Encoder 重排序">
                      <Tag color="blue">检索相关度: {(item.score * 100).toFixed(1)}%</Tag>
                    </Tooltip>
                    {item.age_fit_score !== undefined && item.age_fit_score !== null && (
                      <Tooltip title="年龄适配度：内容适合用户当前年龄的程度，基于年龄范围、内容特征和领域匹配度计算">
                        <Tag color={getAgeFitScoreColor(item.age_fit_score)}>
                          年龄适配度: {(item.age_fit_score * 100).toFixed(1)}%
                        </Tag>
                      </Tooltip>
                    )}
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
                  </Flex>
                </Flex>
              </Flex>
              <div className={styles.resultMeta}>
                {Array.isArray(item.topics) && item.topics.length > 0 && (
                  <div className={styles.topicRow}>
                    <Typography.Text type="secondary" strong>主题:</Typography.Text>
                    <Flex wrap gap="small" style={{ marginLeft: 8 }}>
                      {item.topics.map((topic: string, idx: number) => (
                        <Tag key={idx}>{topic}</Tag>
                      ))}
                    </Flex>
                  </div>
                )}
                {Array.isArray(item.brain_regions) && item.brain_regions.length > 0 && (
                  <div className={styles.topicRow}>
                    <Typography.Text type="secondary" strong>脑区:</Typography.Text>
                    <Flex wrap gap="small" style={{ marginLeft: 8 }}>
                      {item.brain_regions.map((region: string, idx: number) => (
                        <Tag key={idx} color="cyan">{region}</Tag>
                      ))}
                    </Flex>
                  </div>
                )}
              </div>
            </Flex>
          </Card>
        ))}
      </Flex>

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
