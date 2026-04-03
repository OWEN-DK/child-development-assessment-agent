import React from 'react';
import { Table, Button, Popconfirm } from 'antd';
import { RollbackOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { KnowledgeSnapshot } from '../../api/rag-test/types';
import { formatDateTime, formatFileSize } from '../../utils/formatters';

interface SnapshotTableProps {
  snapshots: KnowledgeSnapshot[];
  loading: boolean;
  onRestore: (snapshotId: string) => void;
}

export const SnapshotTable: React.FC<SnapshotTableProps> = ({
  snapshots,
  loading,
  onRestore,
}) => {
  const columns: ColumnsType<KnowledgeSnapshot> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '文档数量',
      dataIndex: 'document_count',
      key: 'document_count',
      width: 100,
    },
    {
      title: '索引大小',
      dataIndex: 'index_size_bytes',
      key: 'index_size_bytes',
      width: 120,
      render: (bytes: number) => formatFileSize(bytes),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => formatDateTime(date),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Popconfirm
          title="确定要恢复到该快照吗？当前数据会被覆盖。"
          onConfirm={() => onRestore(record.id)}
          okText="确定"
          okType="danger"
          cancelText="取消"
        >
          <Button type="link" size="small" icon={<RollbackOutlined />}>
            恢复
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={snapshots}
      rowKey="id"
      loading={loading}
      pagination={{
        pageSize: 10,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 个快照`,
      }}
    />
  );
};
