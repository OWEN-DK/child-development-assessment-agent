import React, { useState, useCallback } from 'react';
import { Card, Typography, Spin, App } from 'antd';
import { useKnowledgeSearch } from '../hooks/useKnowledgeSearch';
import { SearchInput } from '../../../components/knowledge/SearchInput';
import { SearchResultList } from '../../../components/knowledge/SearchResultList';
import { ResultDetailModal } from '../../../components/knowledge/ResultDetailModal';
import type { SearchResultItem } from '../../../api/knowledge/types';
import { usePagination } from '../../../hooks/usePagination';
import styles from './KnowledgeSearchPage.module.scss';

const { Title, Text } = Typography;

const KnowledgeSearchPage: React.FC = () => {
  const { message } = App.useApp();
  const {
    query,
    results,
    loading,
    total,
    handleSearch,
  } = useKnowledgeSearch();

  const {
    currentPage,
    pageSize,
    setCurrentPage,
    setPageSize,
  } = usePagination({ initialPageSize: 10 });

  const [previewItem, setPreviewItem] = useState<SearchResultItem | null>(null);
  const [previewVisible, setPreviewVisible] = useState(false);
  
  // 保存当前搜索关键词，用于分页时重新搜索
  const [currentSearchQuery, setCurrentSearchQuery] = useState('');

  // 执行搜索的函数
  const executeSearch = useCallback(async (searchQuery: string, page: number, size: number) => {
    const offset = (page - 1) * size;
    try {
      await handleSearch(searchQuery, size, offset);
    } catch (e: any) {
      message.error(`搜索失败: ${e.response?.data?.detail || e.message}`);
    }
  }, [handleSearch, message]);

  const handleSearchWithError = useCallback(async (searchQuery: string) => {
    setCurrentSearchQuery(searchQuery);
    setCurrentPage(1); // 新搜索时重置到第一页
    await executeSearch(searchQuery, 1, pageSize);
  }, [pageSize, executeSearch, setCurrentPage]);

  const handlePageChange = useCallback((page: number, size?: number) => {
    const newPageSize = size || pageSize;
    setCurrentPage(page);
    if (size) setPageSize(size);
    
    // 如果有搜索关键词，重新搜索
    if (currentSearchQuery) {
      executeSearch(currentSearchQuery, page, newPageSize);
    }
  }, [currentSearchQuery, pageSize, executeSearch, setCurrentPage, setPageSize]);

  const handlePreview = useCallback((item: SearchResultItem) => {
    setPreviewItem(item);
    setPreviewVisible(true);
  }, []);

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <div>
          <Title level={2}>知识库搜索</Title>
          <Text type="secondary">
            搜索知识库中的内容，快速查找相关的知识点和文档片段。
          </Text>
        </div>

        <SearchInput
          onSearch={handleSearchWithError}
          resultCount={total}
        />
      </Card>

      <Card className={styles.contentCard}>
        <Spin spinning={loading}>
          <SearchResultList
            results={results}
            loading={loading}
            query={query}
            total={total}
            currentPage={currentPage}
            pageSize={pageSize}
            onPageChange={handlePageChange}
            onPreview={handlePreview}
          />
        </Spin>
      </Card>

      <ResultDetailModal
        item={previewItem}
        visible={previewVisible}
        query={query}
        onClose={() => setPreviewVisible(false)}
      />
    </div>
  );
};

export default KnowledgeSearchPage;
