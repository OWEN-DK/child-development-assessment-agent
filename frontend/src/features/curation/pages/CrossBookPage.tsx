import React, { useEffect, useState } from 'react';
import { Button, Select, Space, Spin, App, Statistic, Row, Col, Card } from 'antd';
import {
  ApartmentOutlined,
  ExperimentOutlined,
  ReloadOutlined,
  BookOutlined,
} from '@ant-design/icons';
import { useCurationStore } from '../stores/curationStore';
import { curationApi } from '../api/curationApi';
import { CrossBookPanel } from '../components/CrossBookPanel';
import styles from './CrossBookPage.module.scss';

export const CrossBookPage: React.FC = () => {
  const { message } = App.useApp();
  const { books, booksLoading, loadBooks } = useCurationStore();

  // 主分析对象书籍
  const [primaryBookId, setPrimaryBookId] = useState<string | null>(null);
  // 全局分析状态
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisStats, setAnalysisStats] = useState<{
    total: number; published: number; analyzed: number;
  } | null>(null);

  useEffect(() => {
    loadBooks();
  }, [loadBooks]);

  useEffect(() => {
    const published = books.filter((b) => b.status === 'published');
    setAnalysisStats({
      total: books.length,
      published: published.length,
      analyzed: 0, // 无法直接从列表获取，需要额外 API
    });
    // 默认选择第一本已入库书籍
    if (!primaryBookId && published.length > 0) {
      setPrimaryBookId(published[0].book_id);
    }
  }, [books, primaryBookId]);

  /** 触发全量分析 */
  const handleAnalyzeAll = async (force?: boolean) => {
    if (analysisStats && analysisStats.published < 2) {
      message.warning('需要至少 2 本已入库的书籍才能分析');
      return;
    }
    setAnalyzing(true);
    try {
      const result = await curationApi.analyzeAllBooks(force);
      message.success(
        `分析完成: ${result.analyzed} 对, 跳过 ${result.skipped} 对` +
        (result.failed > 0 ? `, 失败 ${result.failed} 对` : ''),
      );
    } catch {
      message.error('全量分析失败');
    } finally {
      setAnalyzing(false);
    }
  };

  const publishedBooks = books.filter((b) => b.status === 'published');

  return (
    <div className={styles['cross-book-page']}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.header__title}>
            <ApartmentOutlined style={{ marginRight: 12 }} />
            跨书关系管理
          </h1>
          <p className={styles.header__subtitle}>
            查看和管理多本书籍之间的实体对应关系与知识关联
          </p>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={loadBooks} loading={booksLoading}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<ExperimentOutlined />}
            onClick={() => handleAnalyzeAll()}
            loading={analyzing}
            disabled={publishedBooks.length < 2}
          >
            全量分析
          </Button>
          <Button
            icon={<ExperimentOutlined />}
            onClick={() => handleAnalyzeAll(true)}
            loading={analyzing}
            disabled={publishedBooks.length < 2}
          >
            强制全量
          </Button>
        </Space>
      </div>

      {/* 概览统计 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="总书籍"
              value={analysisStats?.total ?? 0}
              prefix={<BookOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="已入库"
              value={analysisStats?.published ?? 0}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="待分析对"
              value={
                (analysisStats?.published ?? 0) < 2
                  ? 0
                  : ((analysisStats?.published ?? 0) * ((analysisStats?.published ?? 0) - 1)) / 2
              }
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="已分析"
              value={analysisStats?.analyzed ?? '-'}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 书籍选择 */}
      <Card size="small" style={{ marginBottom: 24 }}>
        <Space align="center" size="middle">
          <BookOutlined />
          <span>选择书籍查看其跨书分析结果：</span>
          <Select
            placeholder="选择已入库书籍"
            value={primaryBookId}
            onChange={setPrimaryBookId}
            style={{ minWidth: 300 }}
            loading={booksLoading}
            options={publishedBooks.map((b) => ({
              value: b.book_id,
              label: `${b.book_title}${b.author ? ` — ${b.author}` : ''}`,
            }))}
          />
          {primaryBookId && (
            <Button
              icon={<ReloadOutlined />}
              onClick={async () => {
                try {
                  await curationApi.retryCrossBookAnalysis(primaryBookId);
                  message.success('重分析已启动');
                } catch {
                  message.error('重分析失败');
                }
              }}
            >
              重分析此书
            </Button>
          )}
        </Space>
      </Card>

      {/* 跨书分析详情 */}
      <Spin spinning={booksLoading}>
        {primaryBookId ? (
          <CrossBookPanel bookId={primaryBookId} />
        ) : (
          <Card>
            <p style={{ textAlign: 'center', color: '#999', padding: 48 }}>
              请选择一本已入库的书籍以查看其跨书分析结果
            </p>
          </Card>
        )}
      </Spin>
    </div>
  );
};