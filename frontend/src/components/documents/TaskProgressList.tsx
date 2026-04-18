import React from 'react';
import { List, Progress, Button, Space, Typography } from 'antd';
import { LoadingOutlined, StopOutlined } from '@ant-design/icons';
import type { UploadTaskStatus } from '../../api/documents/types';
import { formatTaskStatus } from '../../utils/formatters';
import { TASK_STATUS } from '@shared/lib/constants';

interface TaskProgressListProps {
  tasks: UploadTaskStatus[];
  onCancel: (taskId: string) => void;
}

export const TaskProgressList: React.FC<TaskProgressListProps> = ({
  tasks,
  onCancel,
}) => {
  if (tasks.length === 0) return null;

  return (
    <div>
      <Typography.Title level={5}>正在处理的文档</Typography.Title>
      <List
        dataSource={tasks}
        renderItem={(task) => (
          <List.Item
            actions={[
              (task.status === TASK_STATUS.PENDING || task.status === TASK_STATUS.PROCESSING) && (
                <Button
                  type="text"
                  danger
                  icon={<StopOutlined />}
                  onClick={() => onCancel(task.task_id)}
                >
                  中断
                </Button>
              )
            ]}
          >
            <Space orientation="vertical" style={{ width: '100%' }}>
              <Space>
                {(task.status === TASK_STATUS.PROCESSING || task.status === TASK_STATUS.PENDING) && (
                  <LoadingOutlined spin />
                )}
                <Typography.Text strong>{task.filename}</Typography.Text>
                <Typography.Text type="secondary">
                  {formatTaskStatus(task.status)}
                </Typography.Text>
              </Space>
              <Progress
                percent={Math.round(task.progress || (task.status === 'pending' ? 10 : 50))}
                status={task.status === 'failed' || task.status === 'cancelled' ? 'exception' : 'active'}
                showInfo={false}
              />
              <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                {task.message}
              </Typography.Text>
            </Space>
          </List.Item>
        )}
      />
    </div>
  );
};
