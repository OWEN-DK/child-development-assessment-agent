import React, { useEffect, useState, useRef } from 'react';
import { Button, Space, Tag, Modal, message } from 'antd';
import {
  CheckCircleFilled,
  CloseCircleFilled,
  LoadingOutlined,
  EditOutlined,
  WarningOutlined,
  RedoOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useSSEGeneration } from '../hooks/useSSEGeneration';
import { useCurationStore } from '../stores/curationStore';
import { ProgressBar } from '../components/ProgressBar';
import { StatsGrid } from '../components/StatsGrid';
import styles from './GeneratePage.module.scss';

export const GeneratePage: React.FC = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();

  const { progress, status, error, phase, phaseLabel, start, resume, cancel } = useSSEGeneration();

  const handleCancel = async () => {
    if (!bookId) return;
    Modal.confirm({
      title: '取消生成',
      content: '确定要取消当前生成任务吗？已生成的部分数据将丢失。',
      okText: '确认取消',
      cancelText: '继续生成',
      onOk: async () => {
        try {
          await cancel(bookId);
          message.info('已取消');
          navigate('/curation/books');
        } catch (e: any) {
          message.error(e?.message || '取消失败');
        }
      },
    });
  };
  const { generateBookTitle, generateChapters } = useCurationStore();
  const bookTitle = generateBookTitle;
  const chapters = generateChapters;

  // 聚合摘要状态
  const [summary, setSummary] = useState<{
    entityStats: { type: string; count: number }[];
    failedChapters: string[];
    contradictions: { desc: string; chA: string; chB: string }[];
  } | null>(null);

  const [searchParams] = useSearchParams();
  const autoStart = searchParams.get('autoStart') === 'true';
  const autoStartTriggered = useRef(false);

  useEffect(() => {
    if (!bookId) return;
    if (autoStart && !autoStartTriggered.current) {
      // Auto-start: skip SSE resume, go directly to start
      autoStartTriggered.current = true;
      start(bookId);
    } else {
      resume(bookId);
    }
  }, [bookId, autoStart, resume, start]);

  // D2G 完成后，从实际章节状态聚合摘要
  useEffect(() => {
    if (status === 'completed') {
      const failed = chapters.filter((c) => c.status === 'failed').map((c) => c.title);
      setSummary({
        entityStats: [],  // D2G 流程不按类型统计，用章节完成度替代
        failedChapters: failed,
        contradictions: [],
      });
    } else {
      setSummary(null);
    }
  }, [status, chapters]);


  const completedCount = chapters.filter((c) => c.status === 'completed').length;
  const failedCount = chapters.filter((c) => c.status === 'failed').length;
  const totalCount = chapters.length;

  return (
    <div className={styles['generate-page']}>
      <div className={styles.breadcrumb}>
        <a onClick={() => navigate('/curation/books')}>📚 书籍管理</a>
        <span> / </span>
        <a onClick={() => navigate('/curation/bind')}>绑定书籍</a>
        <span> / </span>
        <span>AI 生成</span>
      </div>

      {status === 'generating' && (
        <div className={styles['progress-card']}>
          <div className={styles['progress-card__icon']}>🤖</div>
          <div className={styles['progress-card__title']}>
            {phaseLabel || 'AI 正在生成知识结构'}
          </div>

          {/* 流程步骤指示器 */}
          <div className={styles['pipeline-steps']}>
            {[
             { key: 'locating', label: '定位文件' },
             { key: 'parsing', label: '解析 EPUB' },
             { key: 'preparing', label: '准备模型' },
             { key: 'phase0_reading', label: '深度阅读' },
              { key: 'phase1_extraction', label: '逐章提取' },
              { key: 'phase2_resolution', label: '全局消歧' },
              { key: 'phase2_5_global_inference', label: '关系补全' },
              { key: 'phase3_quality', label: '质量检查' },
              { key: 'phase4_commit', label: '入库' },
            ].map((step, i, arr) => {
              const stepOrder = arr.map(s => s.key);
              const currentIdx = stepOrder.indexOf(phase);
              const stepIdx = stepOrder.indexOf(step.key);
              const isDone = currentIdx > stepIdx;
              const isCurrent = step.key === phase;
              return (
                <div
                  key={step.key}
                  className={`${styles['pipeline-step']} ${isDone ? styles['pipeline-step--done'] : ''} ${isCurrent ? styles['pipeline-step--current'] : ''}`}
                >
                  <span className={styles['pipeline-step__dot']}>
                    {isDone ? '✓' : isCurrent ? <LoadingOutlined spin /> : (i + 1)}
                  </span>
                  <span className={styles['pipeline-step__label']}>{step.label}</span>
                </div>
              );
            })}
          </div>

          <div className={styles['progress-card__subtitle']}>
            {bookTitle && `《${bookTitle}》`}
            {/* 阶段感知的副标题 */}
            {phase === 'phase1_extraction' && totalCount > 0 &&
              ` · ${completedCount}/${totalCount} 章已提取到暂存区`}
            {phase === 'phase2_resolution' &&
              ' · 正在对所有实体做跨章消歧...'}
            {phase === 'phase2_5_global_inference' &&
              ' · 正在补全跨章关系...'}
            <Button
              size="small"
              danger
              icon={<StopOutlined />}
              onClick={handleCancel}
              style={{ marginLeft: 16 }}
            >
              取消生成
            </Button>
          </div>

          <div className={styles['progress-bar-wrapper']}>
            <ProgressBar percent={progress} showLabel />
            {/* Phase 0/1/2 阶段显示有意义的进度文字 */}
            {phase === 'phase1_extraction' && totalCount > 0 && (
              <div className={styles['progress-text']}>
                {completedCount} / {totalCount} 章
              </div>
            )}
            {phase === 'phase2_resolution' && (
              <div className={styles['progress-text']}>
                全局消歧中...
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
                {/* 实体统计网格 - D2G 完成后显示章节统计 */}
                {summary && (
                <StatsGrid
                  items={[
                    { value: completedCount, label: '已完成章节' },
                    { value: failedCount, label: '失败章节' },
                    { value: totalCount, label: '总章节数' },
                  ]}
                  columns={3}
                />
                )}

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
            <Button onClick={() => navigate('/curation/books')}>返回书籍列表</Button>
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
            <Button onClick={() => navigate('/curation/books')}>返回书籍列表</Button>
            <Button type="primary" onClick={() => bookId && start(bookId)}>重试</Button>
          </Space>
        </div>
      )}

      {status === 'idle' && (
        <div className={styles['progress-card']}>
          <div className={styles['progress-card__icon']}>🤖</div>
          <div className={styles['progress-card__title']}>AI 知识生成</div>
          <div className={styles['progress-card__subtitle']}>
            {bookTitle ? `准备为《${bookTitle}》生成知识结构` : '点击下方按钮开始 AI 生成流程'}
          </div>
          <Space style={{ marginTop: 24 }}>
            <Button onClick={() => navigate('/curation/books')}>返回书籍列表</Button>
            <Button type="primary" onClick={() => bookId && start(bookId)}>
              开始生成
            </Button>
          </Space>
        </div>
      )}
    </div>
  );
};
