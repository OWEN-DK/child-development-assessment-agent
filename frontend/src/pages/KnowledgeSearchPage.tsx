import { useState, useEffect, useRef } from 'react';
import { 
  Card, Typography, Input, Button, List, Tag, Space, 
  Empty, Spin, Pagination, Divider, Descriptions, Modal, App
} from 'antd';
import type { InputRef } from 'antd/es/input';
import { SearchOutlined, EyeOutlined, FileTextOutlined } from '@ant-design/icons';
import { debounce } from 'lodash-es';

import { searchKnowledge, SearchResultItem } from '../api/client';
import styles from './KnowledgeSearchPage.module.scss';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;

const KnowledgeSearchPage = () => {
  const { message } = App.useApp();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewItem, setPreviewItem] = useState<SearchResultItem | null>(null);
  const searchInputRef = useRef<InputRef>(null);

  // 防抖搜索
  const debouncedSearch = useRef(
    debounce(async (searchQuery: string, limit: number = 20) => {
      if (!searchQuery.trim()) {
        setResults([]);
        setTotal(0);
        return;
      }

      try {
        setLoading(true);
        const response = await searchKnowledge(searchQuery, limit);
        setResults(response.results);
        setTotal(response.total);
        setCurrentPage(1);
      } catch (e: any) {
        message.error(`搜索失败: ${e.response?.data?.detail || e.message}`);
        setResults([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    }, 500)
  ).current;

  useEffect(() => {
    return () => {
      debouncedSearch.cancel();
    };
  }, [debouncedSearch]);

  const handleSearch = (value: string) => {
    setQuery(value);
    debouncedSearch(value);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    if (value.trim()) {
      debouncedSearch(value);
    } else {
      setResults([]);
      setTotal(0);
    }
  };

  const handlePreview = (item: SearchResultItem) => {
    setPreviewItem(item);
    setPreviewVisible(true);
  };

  // 高亮关键词
  const highlightKeywords = (text: string, keywords: string) => {
    if (!keywords.trim()) return text;
    
    const keywordList = keywords.split(/\s+/).filter(k => k);
    if (keywordList.length === 0) return text;

    // 构建正则表达式，不区分大小写
    const regex = new RegExp(`(${keywordList.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
    
    return text.split(regex).map((part, index) => {
      if (keywordList.some(k => k.toLowerCase() === part.toLowerCase())) {
        return <mark key={index} className={styles.highlight}>{part}</mark>;
      }
      return part;
    });
  };

  // 分页处理
  const paginatedResults = results.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2}>知识库搜索</Title>
            <Text type="secondary">
              搜索知识库中的内容，快速查找相关的知识点和文档片段。
            </Text>
          </div>

          <Search
            ref={searchInputRef}
            placeholder="输入关键词搜索知识库内容..."
            allowClear
            enterButton={<SearchOutlined />}
            size="large"
            onSearch={handleSearch}
            onChange={handleInputChange}
            value={query}
            className={styles.searchInput}
          />

          {query && (
            <Text type="secondary">
              找到 {total} 条相关结果，关键词: <Text strong>{query}</Text>
            </Text>
          )}
        </Space>
      </Card>

      <Card className={styles.contentCard}>
        <Spin spinning={loading}>
          {results.length === 0 ? (
            <Empty
              description={
                query ? '没有找到相关内容，请尝试其他关键词' : '请输入关键词开始搜索'
              }
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ) : (
            <>
              <List
                dataSource={paginatedResults}
                renderItem={(item) => (
                  <List.Item
                    key={item.id}
                    className={styles.resultItem}
                    actions={[
                      <Button 
                        type="link" 
                        size="small" 
                        icon={<EyeOutlined />}
                        onClick={() => handlePreview(item)}
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
                            {highlightKeywords(item.content.slice(0, 100) + (item.content.length > 100 ? '...' : ''), query)}
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
                              <Text type="secondary" strong>主题:</Text>
                              <Space wrap size="small" style={{ marginLeft: 8 }}>
                                {item.topics.map((topic, idx) => (
                                  <Tag key={idx}>{topic}</Tag>
                                ))}
                              </Space>
                            </div>
                          )}
                          {Array.isArray(item.brain_regions) && item.brain_regions.length > 0 && (
                            <div className={styles.topicRow}>
                              <Text type="secondary" strong>脑区:</Text>
                              <Space wrap size="small" style={{ marginLeft: 8 }}>
                                {item.brain_regions.map((region, idx) => (
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
                    onChange={(page, size) => {
                      setCurrentPage(page);
                      setPageSize(size);
                    }}
                  />
                </div>
              )}
            </>
          )}
        </Spin>
      </Card>

      {/* 详情预览弹窗 */}
      <Modal
        title="内容详情"
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        width={800}
        footer={[
          <Button key="close" onClick={() => setPreviewVisible(false)}>
            关闭
          </Button>
        ]}
      >
        {previewItem && (
          <div>
            <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
              <Descriptions.Item label="来源文档" span={2}>
                {previewItem.source_book}
              </Descriptions.Item>
              {previewItem.chapter_title && (
                <Descriptions.Item label="章节" span={2}>
                  {previewItem.chapter_title}
                </Descriptions.Item>
              )}
              {previewItem.page_label && (
                <Descriptions.Item label="位置">
                  {/^\d+$/.test(previewItem.page_label) ? 
                    '第 ' + previewItem.page_label + ' 页' : 
                    previewItem.page_label.includes('/') ? 
                      (previewItem.chapter_title || previewItem.page_label.split('/').pop()) : 
                      previewItem.page_label
                  }
                </Descriptions.Item>
              )}
              <Descriptions.Item label="相关度">
                {(previewItem.score * 100).toFixed(2)}%
              </Descriptions.Item>
            </Descriptions>

            <Divider />

            <Title level={5}>内容</Title>
            <div className={styles.previewContent}>
              <Paragraph>
                {highlightKeywords(previewItem.content, query)}
              </Paragraph>
            </div>

            {Array.isArray(previewItem.topics) && previewItem.topics.length > 0 && (
              <>
                <Divider />
                <Title level={5}>主题标签</Title>
                <Space wrap>
                  {previewItem.topics.map((topic, idx) => (
                    <Tag key={idx}>{topic}</Tag>
                  ))}
                </Space>
              </>
            )}

            {Array.isArray(previewItem.brain_regions) && previewItem.brain_regions.length > 0 && (
              <>
                <Divider />
                <Title level={5}>刺激脑区</Title>
                <Space wrap>
                  {previewItem.brain_regions.map((region, idx) => (
                    <Tag key={idx} color="cyan">{region}</Tag>
                  ))}
                </Space>
              </>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default KnowledgeSearchPage;
