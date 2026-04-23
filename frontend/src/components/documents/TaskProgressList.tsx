import React from 'react';
import { Progress, Button, Flex, Typography, App, Card, Divider } from 'antd';
import { LoadingOutlined, StopOutlined, DeleteOutlined } from '@ant-design/icons';
import type { UploadTaskStatus } from '../../api/documents/types';
import { formatTaskStatus } from '@shared/lib/formatters';
import { TASK_STATUS } from '@shared/lib/constants';
import { deleteTask } from '../../api/documents';
import { extractApiError, notification } from '@shared/lib/notification';

interface TaskProgressListProps {
  tasks: UploadTaskStatus[];
  onCancel: (taskId: string) => void;
  onRefresh: () => void;
  onRefreshTasks: () => void;
}

export const TaskProgressList: React.FC<TaskProgressListProps> = ({
  tasks,
  onCancel,
  onRefresh,
  onRefreshTasks,
}) => {
  const { modal } = App.useApp();
  
  const handleDelete = async (taskId: string, filename: string, onRefresh: () => void, onRefreshTasks: () => void) => {
    modal.confirm({
      title: '确认删除',
      content: `确定要删除失败的文档 "${filename}" 吗？删除后无法恢复。`,
      onOk: async () => {
        try {
          await deleteTask(taskId);
          notification.success('删除成功');
          onRefresh?.();
          onRefreshTasks?.();
        } catch (e: any) {
          const apiError = extractApiError(e);
          notification.error(`删除失败: ${apiError.message}`);
        }
      },
    });
  };

  if (tasks.length === 0) return null;

  return (
    <div>
      <Typography.Title level={5}>正在处理的文档</Typography.Title>
      <Flex vertical gap="small">
        {tasks.map((task) => (
          <Card key={task.task_id} size="small">
            <Flex vertical gap="small" style={{ width: '100%' }}>
              <Flex align="center" gap="small">
                {(task.status === TASK_STATUS.RUNNING || task.status === TASK_STATUS.PENDING) && (
                  <LoadingOutlined spin />
                )}
                <Typography.Text strong>{task.filename}</Typography.Text>
                <Typography.Text type="secondary">
                  {formatTaskStatus(task.status)}
                </Typography.Text>
              </Flex>
              <Progress
                percent={Math.round(task.progress || (task.status === 'pending' ? 10 : 50))}
                status={
                  task.status === 'failed' || task.status === 'cancelled' ? 'exception' :
                  task.status === 'completed' ? 'success' : 'active'
                }
                showInfo={false}
              />
              <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                {task.message}
              </Typography.Text>
              {((task.status === TASK_STATUS.PENDING || task.status === TASK_STATUS.RUNNING) || task.status === TASK_STATUS.FAILED) && (
                <>
                  <Divider style={{ margin: '8px 0' }} />
                  <Flex gap="small" justify="flex-end">
                    {(task.status === TASK_STATUS.PENDING || task.status === TASK_STATUS.RUNNING) && (
                      <Button
                        type="text"
                        danger
                        icon={<StopOutlined />}
                        onClick={() => onCancel(task.task_id)}
                      >
                        中断
                      </Button>
                    )}
                    {task.status === TASK_STATUS.FAILED && (
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleDelete(task.task_id, task.filename, onRefresh, onRefreshTasks)}
                      >
                        删除
                      </Button>
                    )}
                  </Flex>
                </>
              )}
            </Flex>
          </Card>
        ))}
      </Flex>
    </div>
  );
};
