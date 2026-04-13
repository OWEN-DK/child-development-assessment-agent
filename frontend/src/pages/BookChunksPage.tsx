import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Typography, List, Button, Space, Tag, Input, Descriptions, Modal, App } from 'antd';
import { ArrowLeftOutlined, SearchOutlined, FileTextOutlined } from '@ant-design/icons';
import { getDocumentChunks, getChunkDetail } from '../api/documents';
import type { DocumentChunk, ChunkDetail } from '../api/documents/types';
import styles from './BookChunksPage.module.scss';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;

const BookChunksPage = () => {
  const { fileHash, fileName } = useParams<{ fileHash: string; fileName: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [filteredChunks, setFilteredChunks] = useState<DocumentChunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [selectedChunk, setSelectedChunk] = useState<ChunkDetail | null>(null);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  
  // 分页相关状态
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  useEffect(() => {
    if (fileHash) {
      loadChunks();
    }
  }, [fileHash]);

  useEffect(() => {
    if (searchKeyword.trim()) {
      const keyword = searchKeyword.toLowerCase();
      const filtered = chunks.filter(chunk => 
        chunk.content.toLowerCase().includes(keyword) ||
        chunk.metadata.chapter_title?.toLowerCase().includes(keyword) ||
        (Array.isArray(chunk.metadata.topics) && chunk.metadata.topics.some(topic => topic.toLowerCase().includes(keyword)))
      );
      setFilteredChunks(filtered);
    } else {
      setFilteredChunks(chunks);
    }
  }, [searchKeyword, chunks]);

  const loadChunks = async (page: number = currentPage, size: number = pageSize) => {
    if (!fileHash) return;
    try {
      setLoading(true);
      const res = await getDocumentChunks(fileHash, page, size);
      setChunks(res.chunks);
      setFilteredChunks(res.chunks);
      setTotal(res.total);
      setCurrentPage(res.page);
      setPageSize(res.page_size);
    } catch (e: any) {
      message.error(`加载分块失败：${e.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (page: number, pageSize?: number) => {
    setCurrentPage(page);
    if (pageSize) {
      setPageSize(pageSize);
    }
    loadChunks(page, pageSize || pageSize);
  };

  const handleViewChunkDetail = async (chunkId: string) => {
    try {
      setDetailLoading(true);
      const res = await getChunkDetail(chunkId);
      setSelectedChunk(res.chunk);
      setDetailModalVisible(true);
    } catch (e: any) {
      message.error(`加载分块详情失败: ${e.response?.data?.detail || e.message}`);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleBack = () => {
    navigate('/knowledge-base');
  };

  const renderChunkMetadata = (chunk: DocumentChunk) => {
    const tags = [];
    if (chunk.metadata.page_label) {
      const pageLabel = chunk.metadata.page_label;
      let displayLabel = pageLabel;
      let isChapter = false;
      if (pageLabel.endsWith('.xhtml') || pageLabel.endsWith('.html')) {
        isChapter = true;
        const match = pageLabel.match(/part(\d+)/i) || pageLabel.match(/chapter(\d+)/i);
        if (match) {
          displayLabel = `${parseInt(match[1])}`;
        } else {
          const numMatch = pageLabel.match(/(\d+)/);
          if (numMatch) {
            displayLabel = `${parseInt(numMatch[1])}`;
          } else {
            displayLabel = '章节';
          }
        }
      }
      tags.push(<Tag key="page" color="blue">第 {displayLabel} {isChapter ? '章' : '页'}</Tag>);
    }
    if (chunk.metadata.target_age_min !== undefined && chunk.metadata.target_age_max !== undefined) {
      tags.push(
        <Tag key="age" color="green">
          适合 {chunk.metadata.target_age_min}-{chunk.metadata.target_age_max} 岁
        </Tag>
      );
    }
    if (Array.isArray(chunk.metadata.topics) && chunk.metadata.topics.length > 0) {
      chunk.metadata.topics.forEach((topic, idx) => (
        tags.push(<Tag key={`topic-${idx}`} color="purple">{topic}</Tag>)
      ));
    }
    return tags;
  };

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          <div className={styles.header}>
            <Button 
              icon={<ArrowLeftOutlined />} 
              onClick={handleBack}
            >
              返回知识库
            </Button>
            <Title level={2} className={styles.title}>
              <FileTextOutlined /> {decodeURIComponent(fileName || '')} 分块详情
            </Title>
            <Text type="secondary">
              共 {total} 个分块
            </Text>
          </div>

          <Search
            placeholder="搜索分块内容、章节或主题"
            allowClear
            enterButton={<SearchOutlined />}
            size="large"
            onChange={(e) => setSearchKeyword(e.target.value)}
            value={searchKeyword}
          />
        </Space>
      </Card>

      <Card
        title={`分块列表 ${searchKeyword ? `(搜索结果: ${filteredChunks.length} 个)` : ''}`}
        className={styles.listCard}
        extra={
          <Button
            onClick={() => loadChunks(currentPage, pageSize)}
            loading={loading}
            size="small"
          >
            刷新
          </Button>
        }
      >
        <List
          loading={loading}
          dataSource={filteredChunks}
          renderItem={(chunk, index) => (
            <List.Item
              actions={[
                <Button
                  type="link"
                  onClick={() => handleViewChunkDetail(chunk.id)}
                >
                  查看详情
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Text strong>#{index + 1}</Text>
                    {chunk.metadata.page_label && (
                      <Text type="secondary">| 第 {(() => {
                        const pageLabel = chunk.metadata.page_label;
                        let displayLabel = pageLabel;
                        if (pageLabel.endsWith('.xhtml') || pageLabel.endsWith('.html')) {
                          const match = pageLabel.match(/part(\d+)/i) || pageLabel.match(/chapter(\d+)/i);
                          if (match) {
                            displayLabel = `${parseInt(match[1])}`;
                          } else {
                            const numMatch = pageLabel.match(/(\d+)/);
                            if (numMatch) {
                              displayLabel = `${parseInt(numMatch[1])}`;
                            } else {
                              displayLabel = '';
                            }
                          }
                        }
                        return displayLabel;
                      })()} {(() => {
                        const pageLabel = chunk.metadata.page_label;
                        return pageLabel.endsWith('.xhtml') || pageLabel.endsWith('.html') ? '章' : '页';
                      })()}</Text>
                    )}
                    {chunk.metadata.chapter_title && (
                      <Text type="secondary">| {chunk.metadata.chapter_title}</Text>
                    )}
                  </Space>
                }
                description={
                  <Space orientation="vertical" style={{ width: '100%' }}>
                    <Paragraph
                      ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                      className={styles.contentPreview}
                    >
                      {chunk.content}
                    </Paragraph>
                    <Space wrap>
                      {renderChunkMetadata(chunk)}
                    </Space>
                  </Space>
                }
              />
            </List.Item>
          )}
          locale={{
            emptyText: searchKeyword ? '没有找到匹配的分块' : '暂无分块数据',
          }}
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 个分块`,
            onChange: handlePageChange,
            onShowSizeChange: (_, size) => handlePageChange(1, size),
          }}
        />
      </Card>

      <Modal
        title="分块详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        width={800}
        footer={null}
        destroyOnHidden
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>加载中...</div>
        ) : selectedChunk && (
          <div className={styles.chunkDetail}>
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="分块 ID" span={2}>
                {selectedChunk.id}
              </Descriptions.Item>
              <Descriptions.Item label="页码/来源">
                {(() => {
                  const pageLabel = selectedChunk.metadata.page_label;
                  if (!pageLabel) return '无';
                  // 如果是 EPUB 文件的 xhtml 文件名，显示为章节序号
                  if (pageLabel.endsWith('.xhtml') || pageLabel.endsWith('.html')) {
                    const match = pageLabel.match(/part(\d+)/i) || pageLabel.match(/chapter(\d+)/i);
                    if (match) {
                      return `第${parseInt(match[1])}章`;
                    }
                    // 尝试提取数字
                    const numMatch = pageLabel.match(/(\d+)/);
                    if (numMatch) {
                      return `第${parseInt(numMatch[1])}章`;
                    }
                    return '章节内容';
                  }
                  return pageLabel;
                })()}
              </Descriptions.Item>
              <Descriptions.Item label="章节">
                {selectedChunk.metadata.chapter_title || '无'}
              </Descriptions.Item>
              <Descriptions.Item label="字符范围">
                {selectedChunk.start_char_idx !== undefined ? selectedChunk.start_char_idx : 'N/A'} - {selectedChunk.end_char_idx !== undefined ? selectedChunk.end_char_idx : 'N/A'}
              </Descriptions.Item>
              <Descriptions.Item label="内容长度">
                {selectedChunk.content ? selectedChunk.content.length : 0} 字符
              </Descriptions.Item>
              {selectedChunk.metadata.target_age_min !== undefined && (
                <Descriptions.Item label="适用年龄">
                  {selectedChunk.metadata.target_age_min} - {selectedChunk.metadata.target_age_max} 岁
                </Descriptions.Item>
              )}
              {selectedChunk.metadata.brain_regions && selectedChunk.metadata.brain_regions.length > 0 && (
                <Descriptions.Item label="脑区" span={2}>
                  {selectedChunk.metadata.brain_regions.join(', ')}
                </Descriptions.Item>
              )}
              {selectedChunk.metadata.topics && selectedChunk.metadata.topics.length > 0 && (
                <Descriptions.Item label="主题" span={2}>
                  {selectedChunk.metadata.topics.join(', ')}
                </Descriptions.Item>
              )}
            </Descriptions>

            <div className={styles.contentSection}>
              <Title level={5}>内容</Title>
              <div className={styles.content}>
                {selectedChunk.content}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default BookChunksPage;
