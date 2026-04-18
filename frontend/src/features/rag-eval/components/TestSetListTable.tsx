import { Table, Button, Tag, Space, Popconfirm, Empty } from 'antd';
import { PlayCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import type { SourceType } from '../hooks/useTestSetStore';

const SOURCE_TYPE_MAP: Record<SourceType, { label: string; color: string }> = {
  BOOK_GENERATED: { label: '书籍生成', color: 'blue' },
  JSON_IMPORTED: { label: 'JSON导入', color: 'green' },
  MANUAL: { label: '手动创建', color: 'orange' },
};

interface TestSetListTableProps {
  testSets: any[];
  loading: boolean;
  total: number;
  page: number;
  pageSize: number;
  setPagination: (page: number, pageSize: number) => void;
  onDelete: (id: string) => void;
}

export function TestSetListTable({
  testSets,
  loading,
  total,
  page,
  pageSize,
  setPagination,
  onDelete,
}: TestSetListTableProps) {
  const navigate = useNavigate();

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: any) => (
        <Link to={`/rag-eval/test-sets/${record.id}`}>{text}</Link>
      ),
    },
    {
      title: '来源类型',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 120,
      render: (type: SourceType) => (
        <Tag color={SOURCE_TYPE_MAP[type]?.color}>{SOURCE_TYPE_MAP[type]?.label || type}</Tag>
      ),
    },
    {
      title: '用例数',
      dataIndex: 'total_cases',
      key: 'total_cases',
      width: 80,
      sorter: (a: any, b: any) => a.total_cases - b.total_cases,
    },
    {
      title: '运行次数',
      dataIndex: 'run_count',
      key: 'run_count',
      width: 80,
    },
    {
      title: '最近运行',
      dataIndex: 'last_run_at',
      key: 'last_run_at',
      width: 160,
      render: (val: string | null) => (val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-'),
      sorter: (a: any, b: any) => {
        if (!a.last_run_at) return 1;
        if (!b.last_run_at) return -1;
        return dayjs(a.last_run_at).valueOf() - dayjs(b.last_run_at).valueOf();
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
      sorter: (a: any, b: any) =>
        dayjs(a.created_at).valueOf() - dayjs(b.created_at).valueOf(),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: any) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<PlayCircleOutlined />}
            disabled={record.total_cases === 0}
            onClick={() => navigate(`/rag-eval/test-sets/${record.id}`)}
          >
            运行测试
          </Button>
          <Popconfirm
            title="确定删除此测试集？"
            onConfirm={() => onDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={testSets}
      rowKey="id"
      loading={loading}
      pagination={{
        current: page,
        pageSize,
        total,
        showSizeChanger: true,
        pageSizeOptions: ['10', '20', '50'],
        onChange: (p, ps) => setPagination(p, ps),
        showTotal: t => `共 ${t} 条`,
      }}
      locale={{
        emptyText: (
          <Empty
            description="暂无测试集，点击创建开始"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ),
      }}
    />
  );
}