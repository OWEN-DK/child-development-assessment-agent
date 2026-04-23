import React from 'react';
import { Progress, Button, Flex, Typography, App, Divider } from 'antd';
import {
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  StopOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { BaseProgressTask, ProgressListConfig, TaskStatus } from './types';

const { Text } = Typography;

const STATUS_CONFIG: Record<TaskStatus, {
  icon: React.ReactNode;
  color: string;
  progressStatus: 'normal' | 'active' | 'success' | 'exception';
  label: string;
}> = {
  pending: {
    icon: <ClockCircleOutlined />,
    color: '#999',
    progressStatus: 'normal',
    label: '等待中',
  },
  running: {
    icon: <LoadingOutlined spin />,
    color: '#1677ff',
    progressStatus: 'active',
    label: '处理中',
  },
  completed: {
    icon: <CheckCircleOutlined />,
    color: '#52c41a',
    progressStatus: 'success',
    label: '已完成',
  },
  failed: {
    icon: <CloseCircleOutlined />,
    color: '#ff4d4f',
    progressStatus: 'exception',
    label: '失败',
  },
  cancelled: {
    icon: <StopOutlined />,
    color: '#fa8c16',
    progressStatus: 'exception',
    label: '已取消',
  },
};

interface ProgressListItemProps<T extends BaseProgressTask> {
  task: T;
  config: ProgressListConfig<T>;
}

export function ProgressListItem<T extends BaseProgressTask>({
  task,
  config,
}: ProgressListItemProps<T>) {
  const { modal } = App.useApp();
  const statusConfig = STATUS_CONFIG[task.status];

  const handleCancel = () => {
    modal.confirm({
      title: '确认取消',
      content: '确定要取消此任务吗？',
      onOk: () => {
        config.onCancel?.(task);
      },
    });
  };

  const handleDelete = () => {
    modal.confirm({
      title: '确认删除',
      content: '确定要删除此任务记录吗？',
      onOk: () => {
        config.onDelete?.(task);
      },
    });
  };

  const handleRetry = () => {
    config.onRetry?.(task);
  };

  const renderActions = () => {
    const actions: React.ReactNode[] = [];

    if (task.status === 'running' || task.status === 'pending') {
      if (config.onCancel) {
        actions.push(
          <Button
            key="cancel"
            type="text"
            danger
            size="small"
            icon={<StopOutlined />}
            onClick={handleCancel}
          >
            取消
          </Button>
        );
      }
    }

    if (task.status === 'failed') {
      if (config.onRetry) {
        actions.push(
          <Button
            key="retry"
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            onClick={handleRetry}
          >
            重试
          </Button>
        );
      }
      if (config.onDelete) {
        actions.push(
          <Button
            key="delete"
            type="text"
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={handleDelete}
          >
            删除
          </Button>
        );
      }
    }

    if (task.status === 'cancelled' && config.onDelete) {
      actions.push(
        <Button
          key="delete"
          type="text"
          danger
          size="small"
          icon={<DeleteOutlined />}
          onClick={handleDelete}
        >
          删除
        </Button>
      );
    }

    return actions;
  };

  return (
    <Flex vertical gap="small">
      <Flex align="center" gap="small">
        <span style={{ color: statusConfig.color, fontSize: 16 }}>
          {statusConfig.icon}
        </span>
        <Text strong>{config.getItemTitle(task)}</Text>
        {config.getItemSubtitle && (
          <Text type="secondary">{config.getItemSubtitle(task)}</Text>
        )}
        <Text type="secondary">
          {statusConfig.label}
        </Text>
      </Flex>

      {config.showProgress && (
        <Progress
          percent={Math.round(task.progress)}
          status={statusConfig.progressStatus}
          showInfo={false}
          size="small"
        />
      )}

      {config.showStage && config.getStageText && (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {config.getStageText(task)}
        </Text>
      )}

      {task.status === 'failed' && task.error && (
        <Text type="danger" style={{ fontSize: 12 }}>
          错误：{task.error}
        </Text>
      )}

      {renderActions().length > 0 && (
        <>
          <Divider style={{ margin: '8px 0' }} />
          <Flex gap="small" justify="flex-end">
            {renderActions()}
          </Flex>
        </>
      )}
    </Flex>
  );
}
