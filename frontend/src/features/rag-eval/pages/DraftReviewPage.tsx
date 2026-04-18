/**
 * 草稿审核页
 * 路由: /rag-eval/test-sets/:id/drafts
 */

import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Table,
  Button,
  Tag,
  Space,
  Popconfirm,
  Typography,
  Spin,
  Select,
  Input,
  Modal,
} from 'antd';
import { notification } from '@shared/lib/notification';
import { ArrowLeftOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getDrafts, reviewDraft, getTestSet } from '@/api/rag-test';
import type { TestCaseDraft } from '@/api/rag-test';

const { Title } = Typography;

// 后端 DraftStatus: draft, reviewed, rejected, imported
const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: '待审核', color: 'orange' },
  reviewed: { label: '已通过', color: 'green' },
  rejected: { label: '已拒绝', color: 'red' },
  imported: { label: '已归入', color: 'blue' },
};

export default function DraftReviewPage() {
  const { id } = useParams<{ id: string }>();
  const [drafts, setDrafts] = useState<TestCaseDraft[]>([]);
  const [testSetName, setTestSetName] = useState('');
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('draft');
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [rejectModalVisible, setRejectModalVisible] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    loadData();
  }, [id]);

  const loadData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [testSet, allDrafts] = await Promise.all([getTestSet(id), getDrafts()]);
      setTestSetName(testSet.name);
      // 草稿通过 source_document_id 关联，当前无直接 test_set 关联，展示全部草稿
      setDrafts(allDrafts);
    } catch {
      notification.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (draftId: string, action: 'reviewed' | 'rejected') => {
    try {
      await reviewDraft(draftId, action);
      notification.success(action === 'reviewed' ? '已通过' : '已拒绝');
      loadData();
    } catch {
      notification.error('操作失败');
    }
  };

  const handleBatchApprove = async () => {
    if (selectedRowKeys.length === 0) return;
    try {
      // 批量归入：逐个通过
      for (const key of selectedRowKeys) {
        await reviewDraft(key as string, 'reviewed');
      }
      notification.success('批量归入成功');
      setSelectedRowKeys([]);
      loadData();
    } catch {
      notification.error('批量归入失败');
    }
  };

  const handleBatchReject = async () => {
    if (selectedRowKeys.length === 0) return;
    try {
      // 批量拒绝：逐个拒绝
      for (const key of selectedRowKeys) {
        await reviewDraft(key as string, 'rejected');
      }
      notification.success('批量拒绝成功');
      setSelectedRowKeys([]);
      setRejectModalVisible(false);
      setRejectReason('');
      loadData();
    } catch {
      notification.error('批量拒绝失败');
    }
  };

  const filteredDrafts = drafts.filter(d => {
    if (statusFilter && d.status !== statusFilter) return false;
    return true;
  });

  const pendingCount = drafts.filter(d => d.status === 'draft').length;

  const columns = [
    {
      title: '查询语句',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
    },
    {
      title: '年龄',
      dataIndex: 'age',
      key: 'age',
      width: 80,
      render: (age: number) => `${age}月`,
    },
    {
      title: '领域',
      dataIndex: 'domain',
      key: 'domain',
      width: 120,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={STATUS_MAP[status]?.color}>{STATUS_MAP[status]?.label || status}</Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: { id: string; status: string }) => {
        const isDraft = record.status === 'draft';
        return (
          <Space>
            {isDraft && (
              <>
                <Popconfirm title="通过此草稿？" onConfirm={() => handleReview(record.id, 'reviewed')}>
                  <Button type="link" size="small" icon={<CheckOutlined />}>通过</Button>
                </Popconfirm>
                <Popconfirm title="拒绝此草稿？" onConfirm={() => handleReview(record.id, 'rejected')}>
                  <Button type="link" size="small" danger icon={<CloseOutlined />}>拒绝</Button>
                </Popconfirm>
              </>
            )}
            {!isDraft && '-'}
          </Space>
        );
      },
    },
  ];

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Link to={`/rag-eval/test-sets/${id}`}>
          <Button type="link" icon={<ArrowLeftOutlined />}>返回测试集详情</Button>
        </Link>
      </div>

      <Title level={4}>草稿审核 - {testSetName}</Title>

      <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
        <Select
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 140 }}
          options={[
            { label: '待审核', value: 'draft' },
            { label: '已通过', value: 'reviewed' },
            { label: '已拒绝', value: 'rejected' },
            { label: '已归入', value: 'imported' },
          ]}
        />
        <Tag color="orange">待审核: {pendingCount}</Tag>
        <Tag>总数: {drafts.length}</Tag>
        {selectedRowKeys.length > 0 && (
          <Space>
            <Button type="primary" onClick={handleBatchApprove}>
              批量归入 ({selectedRowKeys.length})
            </Button>
            <Button danger onClick={() => setRejectModalVisible(true)}>
              批量拒绝 ({selectedRowKeys.length})
            </Button>
          </Space>
        )}
      </div>

      <Table
        columns={columns}
        dataSource={filteredDrafts}
        rowKey="id"
        rowSelection={{
          selectedRowKeys,
          onChange: keys => setSelectedRowKeys(keys),
          getCheckboxProps: record => ({ disabled: record.status !== 'draft' }),
        }}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
        locale={{ emptyText: '暂无草稿，请先从书籍生成' }}
      />

      <Modal
        title="批量拒绝"
        open={rejectModalVisible}
        onCancel={() => { setRejectModalVisible(false); setRejectReason(''); }}
        onOk={handleBatchReject}
      >
        <Input.TextArea
          rows={3}
          placeholder="拒绝原因（可选）"
          value={rejectReason}
          onChange={e => setRejectReason(e.target.value)}
        />
      </Modal>
    </div>
  );
}
