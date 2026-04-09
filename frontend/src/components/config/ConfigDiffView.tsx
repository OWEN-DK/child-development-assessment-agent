import React from 'react';
import { Table, Tag } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';

interface ConfigDiffViewProps {
  version1Snapshot: Record<string, any>;
  version2Snapshot: Record<string, any>;
  configFields: any[];
}

export const ConfigDiffView: React.FC<ConfigDiffViewProps> = ({
  version1Snapshot,
  version2Snapshot,
  configFields,
}) => {
  const diffData = configFields
    .filter((field) => {
      const val1 = version1Snapshot[field.key];
      const val2 = version2Snapshot[field.key];
      return val1 !== val2;
    })
    .map((field) => {
      const val1 = version1Snapshot[field.key];
      const val2 = version2Snapshot[field.key];
      const changed = typeof val1 === 'number' && typeof val2 === 'number'
        ? val2 - val1
        : 0;
      const percentChange = typeof val1 === 'number' && val1 !== 0
        ? ((changed / val1) * 100).toFixed(2)
        : 'N/A';

      return {
        key: field.key,
        category: field.category,
        oldValue: val1,
        newValue: val2,
        change: changed,
        percentChange,
        direction: typeof val1 === 'number' && typeof val2 === 'number'
          ? (changed > 0 ? 'up' : 'down')
          : 'neutral',
      };
    });

  const columns = [
    {
      title: '配置项',
      dataIndex: 'key',
      key: 'key',
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
    },
    {
      title: '旧值',
      dataIndex: 'oldValue',
      key: 'oldValue',
    },
    {
      title: '新值',
      dataIndex: 'newValue',
      key: 'newValue',
    },
    {
      title: '变化',
      key: 'change',
      render: (_: any, record: any) => {
        if (record.direction === 'neutral') {
          return <Tag>已变更</Tag>;
        }
        return (
          <Tag
            color={record.direction === 'up' ? 'green' : 'red'}
            icon={
              record.direction === 'up' ? (
                <ArrowUpOutlined />
              ) : (
                <ArrowDownOutlined />
              )
            }
          >
            {record.percentChange}%
          </Tag>
        );
      },
    },
  ];

  if (diffData.length === 0) {
    return <div style={{ color: '#8c8c8c', padding: '16px 0' }}>两个版本配置无差异</div>;
  }

  return <Table columns={columns} dataSource={diffData} size="small" pagination={false} />;
};
