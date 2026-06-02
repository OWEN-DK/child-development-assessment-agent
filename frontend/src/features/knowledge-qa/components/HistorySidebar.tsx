import React, { useEffect, useState } from 'react';
import { Button, List, Spin, Tooltip, Typography, theme, Popconfirm, Tag } from 'antd';
import {
  HistoryOutlined,
  PlusOutlined,
  MessageOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  StopOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { knowledgeQAApi, STATUS_CONFIG } from '../api/knowledgeQAApi';
import type { HistoryItem, HistoryStatus } from '../api/knowledgeQAApi';
import dayjs from 'dayjs';

const { Text, Paragraph } = Typography;

/** 状态 → 图标 */
const STATUS_ICON: Record<HistoryStatus, React.ReactNode> = {
  completed: <CheckCircleOutlined />,
  partial: <ExclamationCircleOutlined />,
  cancelled: <StopOutlined />,
  timeout: <ClockCircleOutlined />,
  error: <CloseCircleOutlined />,
};

interface HistorySidebarProps {
  open: boolean;
  onSelect: (taskId: string) => void;
  onNewChat: () => void;
  activeTaskId?: string | null;
  activeQuestion?: string | null;
  /** 列表加载中（仅首次加载/刷新，不含详情加载） */
  loading: boolean;
  /** 由父组件传入的历史记录数据（父组件统一管理 useHistory） */
  items: HistoryItem[];
  listError: string | null;
  onRefresh: () => void;
  /** 是否有任务正在生成中 */
  isRunning: boolean;
}

export const HistorySidebar: React.FC<HistorySidebarProps> = ({
  open,
  onSelect,
  onNewChat,
  activeTaskId,
  activeQuestion,
  loading,
  items,
  listError,
  onRefresh,
  isRunning,
}) => {
  const { token } = theme.useToken();
  const [deleting, setDeleting] = useState<string | null>(null);

  // 侧边栏打开时刷新列表
  // 使用 ref 防止严格模式下重复请求，同时确保首次打开时一定会拉取数据。
  const fetchRequestedRef = React.useRef(false);
  useEffect(() => {
    if (!open) {
      fetchRequestedRef.current = false;
      return;
    }
    if (!fetchRequestedRef.current) {
      fetchRequestedRef.current = true;
      onRefresh();
    }
  }, [open, onRefresh]);

  const handleDelete = async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleting(taskId);
    try {
      await knowledgeQAApi.deleteHistory(taskId);
      await onRefresh();
    } catch (err) {
      console.error('Failed to delete history:', err);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div
      style={{
        width: open ? 280 : 0,
        minWidth: open ? 280 : 0,
        borderRight: open ? `1px solid ${token.colorBorderSecondary}` : 'none',
        background: token.colorBgContainer,
        overflow: 'hidden',
        transition: 'width 0.25s ease, min-width 0.25s ease',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      {/* 头部 */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Text strong style={{ fontSize: 14 }}>
          <HistoryOutlined style={{ marginRight: 8 }} />
          历史记录
        </Text>
        <Tooltip title={isRunning ? '任务生成中，无法新建对话' : '新建对话'}>
          <Button
            type="text"
            size="small"
            icon={<PlusOutlined />}
            onClick={onNewChat}
            disabled={isRunning}
            title="新建对话"
          />
        </Tooltip>
      </div>

      {/* 当前任务（正在生成中，不在历史列表中） */}
      {isRunning && activeTaskId && activeQuestion && (
        <div
          onClick={() => onSelect(activeTaskId)}
          style={{
            padding: '10px 16px',
            cursor: 'pointer',
            background: token.colorFillTertiary,
            borderRadius: 0,
            borderLeft: `3px solid ${token.colorPrimary}`,
            position: 'relative',
          }}
        >
          <Paragraph
            ellipsis={{ rows: 2 }}
            style={{
              margin: 0,
              fontSize: 13,
              lineHeight: '20px',
              color: token.colorText,
              fontWeight: 500,
            }}
          >
            <MessageOutlined
              style={{ marginRight: 6, fontSize: 12, opacity: 0.5 }}
            />
            {activeQuestion}
          </Paragraph>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
            <Tag
              color="processing"
              style={{ fontSize: 11, lineHeight: '18px', margin: 0, padding: '0 6px' }}
            >
              生成中…
            </Tag>
          </div>
        </div>
      )}

      {/* 列表 */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin size="small" />
          </div>
        ) : listError ? (
          <div style={{ padding: 16, color: token.colorError }}>{listError}</div>
        ) : items.length === 0 ? (
          <div
            style={{
              padding: 24,
              textAlign: 'center',
              color: token.colorTextTertiary,
              fontSize: 13,
            }}
          >
            暂无历史记录
          </div>
        ) : (
          <List
            dataSource={items}
            split={false}
            renderItem={(item: HistoryItem) => {
              const isActive = item.task_id === activeTaskId;
              const cfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.completed;
              return (
                <div
                  key={item.task_id}
                  onClick={() => onSelect(item.task_id)}
                  style={{
                    padding: '10px 16px',
                    cursor: 'pointer',
                    background: isActive ? token.colorFillTertiary : 'transparent',
                    borderRadius: 0,
                    transition: 'background 0.15s',
                    borderLeft: isActive
                      ? `3px solid ${token.colorPrimary}`
                      : '3px solid transparent',
                    position: 'relative',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive)
                      e.currentTarget.style.background = token.colorFillQuaternary;
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive)
                      e.currentTarget.style.background = 'transparent';
                  }}
                >
                  {/* 删除按钮（hover 显示） */}
                  <Popconfirm
                    title="确定删除这条记录？"
                    onConfirm={(e) => handleDelete(item.task_id, e as any)}
                    okText="删除"
                    cancelText="取消"
                    placement="left"
                  >
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      loading={deleting === item.task_id}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        position: 'absolute',
                        top: 4,
                        right: 4,
                        opacity: 0.4,
                        transition: 'opacity 0.15s',
                        zIndex: 1,
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.opacity = '1';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.opacity = '0.4';
                      }}
                    />
                  </Popconfirm>

                  <Tooltip title={item.question} placement="right">
                    <Paragraph
                      ellipsis={{ rows: 2 }}
                      style={{
                        margin: 0,
                        fontSize: 13,
                        lineHeight: '20px',
                        color: isActive
                          ? token.colorText
                          : token.colorTextSecondary,
                        fontWeight: isActive ? 500 : 400,
                        paddingRight: 24,
                      }}
                    >
                      <MessageOutlined
                        style={{ marginRight: 6, fontSize: 12, opacity: 0.5 }}
                      />
                      {item.question}
                    </Paragraph>
                  </Tooltip>

                  {/* 状态 + 时间 */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      marginTop: 4,
                    }}
                  >
                    <Tag
                      color={cfg.color}
                      icon={STATUS_ICON[item.status]}
                      style={{
                        fontSize: 11,
                        lineHeight: '18px',
                        margin: 0,
                        padding: '0 6px',
                      }}
                    >
                      {cfg.label}
                    </Tag>
                    {item.created_at && (
                      <Text
                        type="secondary"
                        style={{ fontSize: 11 }}
                      >
                        {dayjs(item.created_at).format('MM-DD HH:mm')}
                      </Text>
                    )}
                  </div>
                </div>
              );
            }}
          />
        )}
      </div>
    </div>
  );
};
