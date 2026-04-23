import { Flex, Typography, Card, Spin } from 'antd';
import type { BaseProgressTask, ProgressListConfig } from './types';
import { ProgressListItem } from './ProgressListItem';

const { Title } = Typography;

interface ProgressListProps<T extends BaseProgressTask> {
  config: ProgressListConfig<T>;
  tasks: T[];
  loading?: boolean;
}

export function ProgressList<T extends BaseProgressTask>({
  config,
  tasks,
  loading = false,
}: ProgressListProps<T>) {
  if (tasks.length === 0 && !loading) {
    return null;
  }

  return (
    <div>
      <Title level={5}>{config.title}</Title>
      {loading ? (
        <Flex justify="center" style={{ padding: '24px 0' }}>
          <Spin />
        </Flex>
      ) : (
        <Flex vertical gap="small">
          {tasks.map((task) => (
            <Card key={config.getItemKey(task)} size="small">
              <ProgressListItem task={task} config={config} />
            </Card>
          ))}
        </Flex>
      )}
    </div>
  );
}
