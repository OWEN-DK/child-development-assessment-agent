import React, { useEffect, useState } from 'react';
import { Button, Select, Spin } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useCurationStore } from '../stores/curationStore';
import { QueueItem } from '../components/QueueItem';
import { ProgressBar } from '../components/ProgressBar';
import { EmptyState } from '../components/EmptyState';
import styles from './PendingQueuePage.module.scss';

export const PendingQueuePage: React.FC = () => {
  const { pendingItems, pendingLoading, loadPendingQueue } = useCurationStore();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [bookFilter, setBookFilter] = useState<string | undefined>();

  useEffect(() => {
    loadPendingQueue({ status: statusFilter, book_id: bookFilter });
  }, [statusFilter, bookFilter, loadPendingQueue]);

  const pendingCount = pendingItems.filter((i) => i.status === 'pending').length;
  const processingCount = pendingItems.filter((i) => i.status === 'processing').length;
  const completedCount = pendingItems.filter((i) => i.status === 'completed').length;
  const failedCount = pendingItems.filter((i) => i.status === 'failed').length;
  const total = pendingItems.length;
  const completedPct = total > 0 ? Math.round((completedCount / total) * 100) : 0;

  const bookIds = [...new Set(pendingItems.map((i) => i.book_id))];

  return (
    <div className={styles['pending-queue-page']}>
      <div className={styles.header}>
        <h2 className={styles.header__title}>⏱️ 待提炼队列</h2>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => loadPendingQueue({ status: statusFilter, book_id: bookFilter })}
          loading={pendingLoading}
        >
          刷新
        </Button>
      </div>

      {/* 统计概览 */}
      <div className={styles['stats-bar']}>
        <div className={styles['stats-bar__item']}>
          <div className={styles['stats-bar__value']}>{total}</div>
          <div className={styles['stats-bar__label']}>总计</div>
        </div>
        <div className={styles['stats-bar__item']}>
          <div className={styles['stats-bar__value']}>{pendingCount}</div>
          <div className={styles['stats-bar__label']}>待处理</div>
        </div>
        <div className={styles['stats-bar__item']}>
          <div className={styles['stats-bar__value']}>{processingCount}</div>
          <div className={styles['stats-bar__label']}>处理中</div>
        </div>
        <div className={styles['stats-bar__item']}>
          <div className={styles['stats-bar__value']}>{completedCount}</div>
          <div className={styles['stats-bar__label']}>已提炼</div>
        </div>
        <div className={styles['stats-bar__item']}>
          <div className={styles['stats-bar__value']}>{failedCount}</div>
          <div className={styles['stats-bar__label']}>失败</div>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', textAlign: 'right' }}>
            {completedPct}% 已提炼
          </div>
          <ProgressBar percent={completedPct} color={completedPct === 100 ? 'success' : 'default'} showLabel={false} />
        </div>
      </div>

      {/* 筛选 */}
      <div className={styles.filters}>
        <Select
          placeholder="状态筛选"
          allowClear
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 140 }}
          options={[
            { label: '待处理', value: 'pending' },
            { label: '处理中', value: 'processing' },
            { label: '已提炼', value: 'completed' },
            { label: '失败', value: 'failed' },
          ]}
        />
        <Select
          placeholder="来源书筛选"
          allowClear
          value={bookFilter}
          onChange={setBookFilter}
          style={{ width: 200 }}
          options={bookIds.map((id) => ({ label: id, value: id }))}
        />
      </div>

      {/* 队列列表 */}
      <Spin spinning={pendingLoading}>
        {pendingItems.length === 0 && !pendingLoading ? (
          <EmptyState title="暂无待提炼队列" />
        ) : (
          pendingItems.map((item) => <QueueItem key={item.id} item={item} />)
        )}
      </Spin>
    </div>
  );
};
