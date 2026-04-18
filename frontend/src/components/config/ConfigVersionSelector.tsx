import React from 'react';
import { useConfigStore } from '../../store/configStore';
import { Button, Tooltip, Modal, message } from 'antd';
import { RollbackOutlined } from '@ant-design/icons';
import styles from './ConfigVersionSelector.module.scss';

export const ConfigVersionSelector: React.FC = () => {
  const { versions = [], activeVersion, rollbackToVersion } = useConfigStore();

  const handleRollback = async (versionId: string) => {
    if (versionId === activeVersion) return;
    Modal.confirm({
      title: '确认回滚',
      content: `确定要回滚到版本 ${versionId} 吗？`,
      onOk: async () => {
        try {
          await rollbackToVersion(versionId);
          message.success('已回滚到指定版本');
        } catch (error) {
          message.error('回滚失败');
        }
      },
    });
  };

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>历史版本</h3>
      <div className={styles.versionList}>
        {versions.length === 0 && (
          <div className={styles.empty}>暂无历史版本</div>
        )}
        {versions.map((v) => {
          const versionId = v.id || v.version_id;
          if (!versionId) return null;
          const isActive = v.id === activeVersion || v.version_id === activeVersion;
          return (
            <div key={versionId} className={styles.versionItem}>
              <div className={styles.versionInfo}>
                <span className={styles.versionId}>
                  {versionId}
                  {isActive && <span className={styles.activeBadge}>当前</span>}
                </span>
                <span className={styles.versionTime}>
                  {new Date(v.created_at).toLocaleString('zh-CN')}
                </span>
                {v.description && (
                  <span className={styles.versionDesc}>{v.description}</span>
                )}
              </div>
              {!isActive && (
                <Tooltip title="回滚到此版本">
                  <Button
                    icon={<RollbackOutlined />}
                    size="small"
                    onClick={() => handleRollback(versionId)}
                  />
                </Tooltip>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
