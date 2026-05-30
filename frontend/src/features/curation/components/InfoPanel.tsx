import React from 'react';
import { Tag, Space, Button } from 'antd';
import { ApartmentOutlined, DownloadOutlined } from '@ant-design/icons';
import styles from './InfoPanel.module.scss';

interface InfoPanelProps {
  bookTitle: string;
  status: string;
  version: number;
  generatedAt: string | null;
  reviewedAt?: string | null;
  reviewedBy?: string | null;
  totalEntities: number;
  confirmedCount: number;
  entityDistribution: { type: string; label: string; count: number }[];
  onViewGraph?: () => void;
  onExportMD?: () => void;
}

export const InfoPanel: React.FC<InfoPanelProps> = ({
  bookTitle,
  status,
  version,
  generatedAt,
  totalEntities,
  confirmedCount,
  entityDistribution,
  reviewedAt,
  reviewedBy,
  onViewGraph,
  onExportMD,
}) => {
  const statusMap: Record<string, { color: string; label: string }> = {
    draft: { color: 'default', label: '草稿' },
    reviewed: { color: 'warning', label: '已审核' },
    published: { color: 'success', label: '已入库' },
  };
  const statusCfg = statusMap[status] || { color: 'default', label: status };
  const confirmRate = totalEntities > 0 ? Math.round((confirmedCount / totalEntities) * 100) : 0;

  return (
    <div className={styles.panel}>
      <div className={styles.section}>
        <div className={styles.section__title}>📖 书籍信息</div>
        <div className={styles.row}>
          <span>书名</span>
          <span className={styles.row__value}>{bookTitle}</span>
        </div>
        <div className={styles.row}>
          <span>状态</span>
          <Tag color={statusCfg.color}>{statusCfg.label}</Tag>
        </div>
        <div className={styles.row}>
          <span>版本</span>
          <span className={styles.row__value}>v{version}</span>
        </div>
        <div className={styles.row}>
          <span>生成时间</span>
          <span className={styles.row__value}>
            {generatedAt ? new Date(generatedAt).toLocaleString('zh-CN') : '-'}
          </span>
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.section__title}>📊 统计</div>
        <div className={styles.row}>
          <span>实体</span>
          <span className={styles.row__value}>{totalEntities}</span>
        </div>
        <div className={styles.row}>
          <span>已确认</span>
          <span className={styles.row__value}>{confirmedCount}</span>
        </div>
        <div className={styles.row}>
          <span>确认率</span>
          <span className={styles.row__value}>{confirmRate}%</span>
        </div>
      </div>

      {entityDistribution.length > 0 && (
        <div className={styles.section}>
          <div className={styles.section__title}>📋 实体分布</div>
          {entityDistribution.map((d) =>
            d.count > 0 ? (
              <div key={d.type} className={styles.row}>
                <span>{d.label}</span>
                <span className={styles.row__value}>{d.count}</span>
              </div>
            ) : null,
          )}
        </div>
      )}

      <div className={styles.section}>
        <div className={styles.section__title}>📝 审核历史</div>
        <div className={styles.row}>
          <span>AI 生成</span>
          <span className={styles.row__value}>
            {generatedAt ? new Date(generatedAt).toLocaleDateString('zh-CN') : '-'}
          </span>
        </div>
        {reviewedBy && (
          <div className={styles.row}>
            <span>审核者</span>
            <span className={styles.row__value}>{reviewedBy}</span>
          </div>
        )}
        {reviewedAt && (
          <div className={styles.row}>
            <span>审核时间</span>
            <span className={styles.row__value}>
              {new Date(reviewedAt).toLocaleDateString('zh-CN')}
            </span>
          </div>
        )}
        {!reviewedBy && status === 'draft' && (
          <div className={styles.row}>
            <span style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>尚未审核</span>
          </div>
        )}
      </div>

      <div className={styles.section}>
        <div className={styles.section__title}>⚡ 操作</div>
        <Space orientation="vertical" style={{ width: '100%' }}>
          {onViewGraph && (
            <Button block icon={<ApartmentOutlined />} onClick={onViewGraph}>
              查看知识图谱
            </Button>
          )}
          {onExportMD && (
            <Button block icon={<DownloadOutlined />} onClick={onExportMD}>
              导出 MD
            </Button>
          )}
        </Space>
      </div>
    </div>
  );
};
