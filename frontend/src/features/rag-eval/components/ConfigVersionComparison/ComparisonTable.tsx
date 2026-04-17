/**
 * 配置对比表格组件
 * 展示两个配置版本的差异，包括新增、删除和修改的配置项
 */

import React from 'react';
import { Table, Tag, Typography } from 'antd';
import type { ConfigDiff } from './types';
import ChangeHighlight from './ChangeHighlight';

const { Text } = Typography;

interface ComparisonTableProps {
  diff: ConfigDiff;
}

const ComparisonTable: React.FC<ComparisonTableProps> = ({ diff }) => {
  const { added, removed, changed } = diff;

  // 构建表格数据
  const dataSource: any[] = [];

  // 新增的配置项
  Object.entries(added).forEach(([key, value]) => {
    dataSource.push({
      key: `added-${key}`,
      type: 'added',
      keyName: key,
      oldValue: null,
      newValue: value,
    });
  });

  // 删除的配置项
  Object.entries(removed).forEach(([key, value]) => {
    dataSource.push({
      key: `removed-${key}`,
      type: 'removed',
      keyName: key,
      oldValue: value,
      newValue: null,
    });
  });

  // 修改的配置项
  changed.forEach((item, index) => {
    dataSource.push({
      key: `changed-${index}`,
      type: 'changed',
      keyName: item.key,
      oldValue: item.old_value,
      newValue: item.new_value,
    });
  });

  const columns = [
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (type: string) => {
        const config: Record<string, { label: string; color: string }> = {
          added: { label: '新增', color: 'green' },
          removed: { label: '删除', color: 'red' },
          changed: { label: '修改', color: 'orange' },
        };
        const { label, color } = config[type] || { label: type, color: 'default' };
        return <Tag color={color}>{label}</Tag>;
      },
    },
    {
      title: '配置项',
      dataIndex: 'keyName',
      key: 'keyName',
      width: 200,
      render: (keyName: string) => <Text strong>{keyName}</Text>,
    },
    {
      title: '变更详情',
      key: 'detail',
      render: (_: unknown, record: any) => (
        <ChangeHighlight
          keyName={record.keyName}
          oldValue={record.oldValue}
          newValue={record.newValue}
        />
      ),
    },
  ];

  if (dataSource.length === 0) {
    return <Text type="secondary">两个版本配置完全一致</Text>;
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Tag color="green">新增 {Object.keys(added).length}</Tag>
        <Tag color="red">删除 {Object.keys(removed).length}</Tag>
        <Tag color="orange">修改 {changed.length}</Tag>
      </div>
      <Table
        columns={columns}
        dataSource={dataSource}
        rowKey="key"
        pagination={false}
        size="small"
      />
    </div>
  );
};

export default ComparisonTable;
