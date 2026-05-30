import React, { useEffect, useState } from 'react';
import { Button, Tag, App, Spin, Input } from 'antd';
import {
  LinkOutlined,
  SearchOutlined,
  CheckCircleFilled,
  BookOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { curationApi } from '../api/curationApi';
import type { KBBook } from '../types';
import styles from './BindBookPage.module.scss';

export const BindBookPage: React.FC = () => {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [books, setBooks] = useState<KBBook[]>([]);
  const [loading, setLoading] = useState(false);
  const [binding, setBinding] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadBooks();
  }, []);

  const loadBooks = async () => {
    setLoading(true);
    try {
      const res = await curationApi.listKBBooks();
      setBooks(res.books || []);
    } catch {
      message.error('加载知识库书籍失败');
    } finally {
      setLoading(false);
    }
  };

  const handleBind = async (book: KBBook) => {
    setBinding(book.id);
    try {
      await curationApi.bindBook({
        kb_book_id: book.id,
        book_title: book.title,
        author: book.author,
      });
      message.success(`「${book.title}」绑定成功，正在进入生成流程...`);
      // 跳转到生成页
      navigate(`/curation/generate/${book.id}`);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '绑定失败';
      message.error(detail);
    } finally {
      setBinding(null);
    }
  };

  const filteredBooks = books.filter(
    (b) => !search || b.title.toLowerCase().includes(search.toLowerCase()),
  );

  const epubBooks = filteredBooks.filter((b) => b.file_type === 'epub');
  const nonEpubBooks = filteredBooks.filter((b) => b.file_type !== 'epub');

  return (
    <div className={styles['bind-book-page']}>
      {/* 面包屑 */}
      <div className={styles.breadcrumb}>
        <a onClick={() => navigate('/curation')}>📚 知识管理</a>
        <span> / </span>
        <span>从知识库绑定</span>
      </div>

      {/* 信息提示 */}
      <div className={styles['info-banner']}>
        <span className={styles['info-banner__icon']}>💡</span>
        <div>
          <div className={styles['info-banner__title']}>策管流程说明</div>
          <div className={styles['info-banner__text']}>
            所有书籍必须先上传到知识库并获得 <code>kb_book_id</code>，然后回到此处绑定。
            绑定后策管独立读取原始 EPUB，按章节重新解析并 AI 生成结构化知识。
            知识库的 chunks 仅用于 RAG 检索，与策管无关。
          </div>
        </div>
      </div>

      {/* 流程步骤 */}
      <div className={styles['flow-steps']}>
        <div className={styles.step}>
          <div className={`${styles.step__number} ${styles['step__number--active']}`}>1</div>
          <div className={styles.step__content}>
            <div className={styles.step__title}>前往知识库上传 EPUB</div>
            <div className={styles.step__desc}>
              上传后系统自动分块、建立 Chroma 向量索引，并分配 <code>kb_book_id</code>
            </div>
            <div className={styles.step__action}>
              <Button onClick={() => navigate('/knowledge-base')}>
                前往知识库 →
              </Button>
            </div>
          </div>
        </div>
        <div className={styles.step}>
          <div className={`${styles.step__number} ${styles['step__number--active']}`}>2</div>
          <div className={styles.step__content}>
            <div className={styles.step__title}>回到此处绑定并策管</div>
            <div className={styles.step__desc}>
              在下方选择已上传的 EPUB 书籍，点击「选定并绑定」进入 AI 生成流程
            </div>
          </div>
        </div>
      </div>

      <div className={styles.divider} />

      {/* 可绑定书籍列表 */}
      <div className={styles['book-list__title']}>
        <BookOutlined /> 知识库中可绑定的 EPUB 书籍
      </div>

      <Input
        placeholder="搜索书籍..."
        prefix={<SearchOutlined />}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 16 }}
        allowClear
      />

      <Spin spinning={loading}>
        {epubBooks.length === 0 && !loading ? (
          <div className={styles['empty-books']}>
            <div className={styles['empty-books__icon']}>📭</div>
            <div>知识库中没有可绑定的 EPUB 书籍</div>
            <div style={{ marginTop: 8, fontSize: 13 }}>
              请先到知识库上传 EPUB 格式的书籍
            </div>
          </div>
        ) : (
          epubBooks.map((book) => (
            <div
              key={book.id}
              className={`${styles['book-item']} ${book.bound ? styles['book-item--bound'] : ''}`}
            >
              <div className={styles['book-item__info']}>
                <div className={styles['book-item__title']}>{book.title}</div>
                <div className={styles['book-item__meta']}>
                  <span>ID: {book.id}</span>
                  {book.author && <span>作者: {book.author}</span>}
                  {book.chapter_count && <span>{book.chapter_count} 章</span>}
                  <span>类型: {book.file_type.toUpperCase()}</span>
                </div>
              </div>
              <div>
                {book.bound ? (
                  <Tag icon={<CheckCircleFilled />} color="success">
                    已绑定
                  </Tag>
                ) : (
                  <Button
                    type="primary"
                    icon={<LinkOutlined />}
                    loading={binding === book.id}
                    onClick={() => handleBind(book)}
                  >
                    选定并绑定
                  </Button>
                )}
              </div>
            </div>
          ))
        )}

        {/* 非 EPUB 提示 */}
        {nonEpubBooks.length > 0 && (
          <div style={{ marginTop: 24 }}>
            <div style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 8 }}>
              ⚠️ 以下书籍非 EPUB 格式，无法绑定到策管（需要 EPUB 章节结构）
            </div>
            {nonEpubBooks.map((book) => (
              <div key={book.id} className={`${styles['book-item']} ${styles['book-item--bound']}`}>
                <div className={styles['book-item__info']}>
                  <div className={styles['book-item__title']}>{book.title}</div>
                  <div className={styles['book-item__meta']}>
                    <span>类型: {book.file_type.toUpperCase()}</span>
                  </div>
                </div>
                <Tag>不支持</Tag>
              </div>
            ))}
          </div>
        )}
      </Spin>
    </div>
  );
};
