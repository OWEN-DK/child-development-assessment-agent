import React, { useEffect, useState } from 'react';
import { Button, Space, Tag } from 'antd';
import {
  CheckCircleFilled,
  CloseCircleFilled,
  LoadingOutlined,
  EditOutlined,
  WarningOutlined,
  RedoOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useSSEGeneration } from '../hooks/useSSEGeneration';
import { useCurationStore } from '../stores/curationStore';
import { ProgressBar } from '../components/ProgressBar';
import { StatsGrid } from '../components/StatsGrid';
import styles from './GeneratePage.module.scss';

export const GeneratePage: React.FC = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { progress, status, error, start } = useSSEGeneration();
  const { generateBookTitle, generateChapters } = useCurationStore();
  const bookTitle = generateBookTitle;
  const chapters = generateChapters;
  const currentChapter = chapters.find((c) => c.status === 'generating')?.title || '';

  // 聚合摘要状态
  const [summary, setSummary] = useState<{
    entityStats: { type: string; count: number }[];
    failedChapters: string[];
    contradictions: { desc: string; chA: string; chB: string }[];
  } | null>(null);

  useEffect(() => {
    if (bookId) start(bookId);
  }, [bookId, start]);

  // 模拟从SSE获取摘要数据
  useEffect(() => {
    if (status === 'completed') {
      // 实际应从SSE或API获取，这里用模拟数据
      setSummary({
        entityStats: [
          { type: '问题', count: 12 },
          { type: '方案', count: 8 },
          { type: '脑区', count: 6 },
          { type: '主张', count: 15 },
          { type: '处方', count: 5 },
        ],
        failedChapters: chapters.filter((c) => c.status === 'failed').map((c) => c.title),
        contradictions: [],
      });
    }
  }, [status, chapters]);

  const completedCount = chapters.filter((c) => c.status === 'completed').length;
  const failedCount = chapters.filter((c) => c.status === 'failed').length;
  const totalCount = chapters.length;

  return (
    <div className={styles['generate-page']}>
      <div className={styles.breadcrumb}>
        <a onClick={() => navigate('/curation')}>📚 知识管理</a>
        <span> / </span>
        <a onClick={() => navigate('/curation/bind')}>绑定书籍</a>
        <span> / </span>
        <span>AI 生成</span>
      </div>

      {status === 'generating' && (
        <div className={styles['progress-card']}>
          <div className={styles['progress-card__icon']}>🤖</div>
          <div className={styles['progress-card__title']}>AI 正在生成知识结构</div>
          <div className={styles['progress-card__subtitle']}>
            {bookTitle && `《${bookTitle}》`}
            {currentChapter && ` · 当前: ${currentChapter}`}
          </div>

          <div className={styles['progress-bar-wrapper']}>
            <ProgressBar percent={progress} showLabel />
            {totalCount > 0 && (
              <div className={styles['progress-text']}>
                {completedCount} / {totalCount} 章
              </div>
            )}
          </div>

          {chapters.length > 0 && (
            <div className={styles['chapter-list']}>
              <div className={styles['chapter-list__title']}>章节进度</div>
              {chapters.map((ch, i) => (
                <div
                  key={i}
                  className={`${styles['chapter-item']} ${styles[`chapter-item--${ch.status}`]}`}
                >
                  <span className={styles['chapter-item__icon']}>
                    {ch.status === 'completed' && <CheckCircleFilled />}
                    {ch.status === 'generating' && <LoadingOutlined spin />}
                    {ch.status === 'failed' && <CloseCircleFilled />}
                    {ch.status === 'pending' && '○'}
                  </span>
                  <span>{ch.title}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {status === 'completed' && (
        <div className={`${styles['result-card']} ${styles['result-card--success']}`}>
          <div className={styles['result-card__icon']}><CheckCircleFilled /></div>
          <div className={styles['result-card__title']}>
            AI 生成完成 ✓
            {bookTitle && ` — ${bookTitle}`}
          </div>

          {/* 聚合摘要 */}
          <div className={styles.summary}>
            {totalCount > 0 && (
              <div className={styles.summary__row}>
                <span>成功: {completedCount}/{totalCount} 章</span>
                {failedCount > 0 && (
                  <Tag color="error">失败: {failedCount} 章</Tag>
                )}
              </div>
            )}

            {summary && (
              <>
                {/* 实体统计网格 */}
                <StatsGrid
                  items={summary.entityStats.map((s) => ({
                    value: s.count,
                    label: s.type,
                  }))}
                  columns={5}
                />

                {/* 章节进度 */}
              {totalCount > 0 && (
                <div className={styles['chapter-list']}>
                  <div className={styles['chapter-list__title']}>章节完成情况</div>
                  {chapters.map((ch, i) => (
                    <div
                      key={i}
                      className={`${styles['chapter-item']} ${styles[`chapter-item--${ch.status}`]}`}
                    >
                      <span className={styles['chapter-item__icon']}>
                        {ch.status === 'completed' && <CheckCircleFilled />}
                        {ch.status === 'generating' && <LoadingOutlined spin />}
                        {ch.status === 'failed' && <CloseCircleFilled />}
                        {ch.status === 'pending' && '○'}
                      </span>
                      <span>{ch.title}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* 章间矛盾 */}
                {summary.contradictions.length > 0 && (
                  <div className={styles.summary__contradictions}>
                    <Tag icon={<WarningOutlined />} color="warning">
                      章间矛盾: {summary.contradictions.length} 处
                    </Tag>
                    {summary.contradictions.map((c, i) => (
                      <div key={i} className={styles["summary__conflict-item"]}>
                        "{c.desc}" — {c.chA} vs {c.chB}
                      </div>
                    ))}
                  </div>
                )}

                {/* 失败章节 */}
                {summary.failedChapters.length > 0 && (
                  <div className={styles.summary__failed}>
                    <Tag color="error">失败章节</Tag>
                    {summary.failedChapters.map((ch, i) => (
                      <div key={i} className={styles["summary__conflict-item"]}>{ch}</div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          <Space style={{ marginTop: 16 }}>
            {failedCount > 0 && (
              <Button icon={<RedoOutlined />} onClick={() => bookId && start(bookId)}>
                重试失败章节
              </Button>
            )}
            <Button onClick={() => navigate('/curation')}>返回书籍列表</Button>
            <Button type="primary" icon={<EditOutlined />} onClick={() => navigate(`/curation/editor/${bookId}`)}>
              查看 MD 草稿 →
            </Button>
          </Space>
        </div>
      )}

      {status === 'failed' && (
        <div className={`${styles['result-card']} ${styles['result-card--error']}`}>
          <div className={styles['result-card__icon']}><CloseCircleFilled /></div>
          <div className={styles['result-card__title']}>生成失败</div>
          <div className={styles['result-card__desc']}>{error || 'AI 生成过程中出现错误，请重试'}</div>
          <Space>
            <Button onClick={() => navigate('/curation')}>返回书籍列表</Button>
            <Button type="primary" onClick={() => bookId && start(bookId)}>重试</Button>
          </Space>
        </div>
      )}

      {status === 'idle' && (
        <div className={styles['progress-card']}>
          <div className={styles['progress-card__icon']}>⏳</div>
          <div className={styles['progress-card__title']}>准备中...</div>
          <div className={styles['progress-card__subtitle']}>正在启动 AI 生成流程</div>
        </div>
      )}
    </div>
  );
};
