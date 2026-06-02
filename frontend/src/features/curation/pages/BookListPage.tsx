import React, { useEffect } from 'react';
import { Button, Tag, Space, Dropdown, Modal, App, Spin } from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  MoreOutlined,
  DeleteOutlined,
  EditOutlined,
  ApartmentOutlined,
  ExperimentOutlined,
  EyeOutlined,
  SendOutlined,
  RedoOutlined,
  BookOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useCurationStore } from '../stores/curationStore';
import { curationApi } from '../api/curationApi';
import { StatsGrid } from '../components/StatsGrid';
import { StatusBadge } from '../components/StatusBadge';
import { EmptyState } from '../components/EmptyState';
import type { CurationBook } from '../types';
import styles from './BookListPage.module.scss';

export const BookListPage: React.FC = () => {
  const navigate = useNavigate();

  const handleCancelGeneration = async (book: any) => {
    Modal.confirm({
      title: '取消生成',
      content: `确定要取消《${book.book_title}》的生成任务吗？`,
      okText: '确认取消',
      cancelText: '返回',
      onOk: async () => {
        await curationApi.cancelGeneration(book.book_id);
        message.success('已取消');
        loadBooks();
      },
    });
  };
  const { message } = App.useApp();
  const { books, booksLoading, loadBooks } = useCurationStore();
  useEffect(() => {
    loadBooks();
  }, [loadBooks]);

  const handleDelete = (book: CurationBook) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除「${book.book_title}」的策管数据吗？知识库中的原始数据不受影响。`,
      okType: 'danger',
      onOk: async () => {
        try {
          await curationApi.deleteBook(book.book_id);
          message.success('删除成功');
          loadBooks();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  /** 根据状态返回可用操作 */
  const getActions = (book: CurationBook) => {
    const items: any[] = [];

    switch (book.status) {
      case 'bound':
        items.push(
          { key: 'generate', icon: <ExperimentOutlined />, label: '开始生成', onClick: () => navigate(`/curation/generate/${book.book_id}?autoStart=true`) },
        );
        break;
      case 'draft':
        items.push(
          { key: 'editor', icon: <EditOutlined />, label: '继续审核', onClick: () => navigate(`/curation/editor/${book.book_id}`) },
          { key: 'generate', icon: <ExperimentOutlined />, label: '重新生成', onClick: () => navigate(`/curation/generate/${book.book_id}?autoStart=true`) },
        );
        break;
      case 'reviewed':
        items.push(
          { key: 'publish', icon: <SendOutlined />, label: '入库 Neo4j', onClick: () => navigate(`/curation/editor/${book.book_id}`) },
          { key: 'editor', icon: <EditOutlined />, label: '查看 MD', onClick: () => navigate(`/curation/editor/${book.book_id}`) },
          { key: 'graph', icon: <ApartmentOutlined />, label: '查看 KG', onClick: () => navigate(`/curation/graph/${book.book_id}`), disabled: !book.neo4j_synced },
        );
        break;
      case 'published':
        items.push(
          { key: 'graph', icon: <ApartmentOutlined />, label: '查看 KG', onClick: () => navigate(`/curation/graph/${book.book_id}`) },
          { key: 'editor', icon: <EyeOutlined />, label: '查看 MD', onClick: () => navigate(`/curation/editor/${book.book_id}`) },
          { key: 'generate', icon: <ExperimentOutlined />, label: '重新生成', onClick: () => navigate(`/curation/generate/${book.book_id}?autoStart=true`) },
        );
        break;
      case 'generating':
        items.push(
          { key: 'cancel', icon: <StopOutlined />, label: '取消生成', onClick: () => handleCancelGeneration(book) },
        );
        break;
      case 'failed':
        items.push(
          { key: 'retry', icon: <RedoOutlined />, label: '重试', onClick: () => navigate(`/curation/generate/${book.book_id}?autoStart=true`) },
          { key: 'editor', icon: <EyeOutlined />, label: '查看日志', onClick: () => navigate(`/curation/editor/${book.book_id}`) },
        );
        break;
    }

    // Delete is always available
    if (true) {
      items.push({ type: 'divider' as const });
      items.push({
        key: 'delete',
        icon: <DeleteOutlined />,
        label: '删除',
        danger: true,
        onClick: () => handleDelete(book),
      });
    }

    return items;
  };

  const totalEntities = books.reduce((s, b) => s + (b.total_entities || 0), 0);
  const totalClaims = books.reduce((s, b) => s + (b.total_claims || 0), 0);
  const publishedCount = books.filter((b) => b.status === 'published').length;

  return (
    <div className={styles['book-list-page']}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.header__title}>📚 知识管理</h1>
          <p className={styles.header__subtitle}>
            管理已绑定的书籍，审核 AI 生成的知识结构，入库知识图谱
          </p>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={loadBooks} loading={booksLoading}>
            刷新
          </Button>
          {books.length >= 2 && (
            <>
              <Button
                icon={<ApartmentOutlined />}
                onClick={() => navigate('/curation/cross-book')}
              >
                跨书关系管理
              </Button>
              <Button
                icon={<ApartmentOutlined />}
                onClick={() => {
                  const published = books.filter(b => b.status === 'published').map(b => b.book_id);
                  if (published.length >= 2) {
                    navigate(`/curation/graph?compare=${published.slice(0, 2).join(',')}`);
                  } else {
                    message.warning('需要至少两本已入库的书籍才能对比');
                  }
                }}
              >
                📊 多书图谱对比
              </Button>
            </>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/curation/bind')}>
            添加书籍
          </Button>
        </Space>
      </div>

      <StatsGrid
        items={[
          { value: books.length, label: '书籍总数' },
          { value: totalEntities, label: '实体总数' },
          { value: totalClaims, label: '主张总数' },
          { value: `${publishedCount}/${books.length}`, label: '已入库' },
        ]}
      />

      <Spin spinning={booksLoading}>
        {books.length === 0 && !booksLoading ? (
          <EmptyState
            title="暂无策管书籍"
            action={
              <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/curation/bind')}>
                从知识库添加书籍
              </Button>
            }
          />
        ) : (
          books.map((book) => {
            const isGenerating = book.status === 'generating';
            const isBound = book.status === 'bound';
            const isFailed = book.status === 'failed';
            const sourceLabel = book.bind_source === 'direct'
              ? '直接上传'
              : `从知识库绑定 (${book.book_id})`;

            return (
              <div
                key={book.book_id}
                className={`${styles['book-card']} ${isGenerating ? styles['book-card--generating'] : ''} ${isFailed ? styles['book-card--failed'] : ''}`}
                onClick={() => { if (isGenerating) return; if (book.status === 'bound') navigate(`/curation/generate/${book.book_id}?autoStart=true`); else navigate(`/curation/editor/${book.book_id}`); }}
              >
                <div className={styles['book-card__header']}>
                  <div>
                    <h3 className={styles['book-card__title']}>
                      <BookOutlined style={{ marginRight: 8 }} />
                      {book.book_title}
                    </h3>
                    <div className={styles['book-card__subtitle']}>
                      {book.author && <span>{book.author} · </span>}
                      <span>{book.total_entities || 0} 节点 · {book.total_claims || 0} 主张</span>
                    </div>
                    <div className={styles['book-card__source']}>
                      来源: {sourceLabel}
                    </div>
                    {book.reviewed_by && (
                      <div className={styles['book-card__source']}>
                        审核者: {book.reviewed_by}
                      </div>
                    )}
                  </div>
                  <div className={styles['book-card__actions']} onClick={(e) => e.stopPropagation()}>
                    <StatusBadge status={book.status} />
                    <Tag>v{book.version}</Tag>
                    {book.neo4j_synced && <Tag color="success">已同步</Tag>}
                    {getActions(book).length > 0 && (
                      <Dropdown menu={{ items: getActions(book) }}>
                        <Button type="text" icon={<MoreOutlined />} size="small" />
                      </Dropdown>
                    )}
                  </div>
                </div>
                <div className={styles['book-card__stats']}>
                  <div className={styles['book-card__stat']}>
                    <div className={styles['book-card__stat-value']}>{book.total_entities || 0}</div>
                    <div className={styles['book-card__stat-label']}>实体</div>
                  </div>
                  <div className={styles['book-card__stat']}>
                    <div className={styles['book-card__stat-value']}>{book.total_claims || 0}</div>
                    <div className={styles['book-card__stat-label']}>主张</div>
                  </div>
                  <div className={styles['book-card__stat']}>
                    <div className={styles['book-card__stat-value']}>{book.total_prescriptions || 0}</div>
                    <div className={styles['book-card__stat-label']}>处方</div>
                  </div>
                  <div className={styles['book-card__stat']}>
                    <div className={styles['book-card__stat-value']}>
                      {book.updated_at ? new Date(book.updated_at).toLocaleDateString('zh-CN') : '-'}
                    </div>
                    <div className={styles['book-card__stat-label']}>更新时间</div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </Spin>
    </div>
  );
};
