import { Alert, Space } from 'antd';

interface ConflictAlertProps {
  conflicts: Array<{ suggestionA: string; suggestionB: string; configKey: string }>;
}

export function ConflictAlert({ conflicts }: ConflictAlertProps) {
  if (conflicts.length === 0) return null;

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {conflicts.map((conflict, i) => (
        <Alert
          key={i}
          type="warning"
          showIcon
          message={`配置冲突: ${conflict.configKey}`}
          description={
            <span>
              建议 {conflict.suggestionA} 与建议 {conflict.suggestionB} 存在冲突，请择一采纳
            </span>
          }
        />
      ))}
    </Space>
  );
}
