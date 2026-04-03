import React, { useState } from 'react';
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

  const handleSearchWithError = async (searchQuery: string) => {
    try {
      await handleSearch(searchQuery);
    } catch (e: any) {
      message.error(`搜索失败: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handlePreview = (item: SearchResultItem) => {
    setPreviewItem(item);
    setPreviewVisible(true);
  };

  const paginatedResults = results.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

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
            results={paginatedResults}
            loading={loading}
            query={query}
            total={total}
            currentPage={currentPage}
            pageSize={pageSize}
            onPageChange={(page, size) => {
              setCurrentPage(page);
              if (size) setPageSize(size);
            }}
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
