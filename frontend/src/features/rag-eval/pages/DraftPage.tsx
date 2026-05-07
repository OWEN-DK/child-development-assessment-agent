import { useState, useCallback } from 'react';
import {
  Space, Button, Select, Input, Modal, message, Typography, Alert, Row, Col,
} from 'antd';
import type { TestCaseDraft } from '@entities/rag-eval';
import {
  useDrafts, useDeleteDrafts, useCreateDrafts, useReviewDraft, useSourceDocuments,
} from '../hooks/useDrafts';
import { useDraftGenerationProgress } from '../hooks/useDraftGenerationProgress';
import { DraftTable } from '../components/draft/DraftTable';
import { DraftGenerationForm } from '../components/draft/DraftGenerationForm';
import { StatusBadge } from '../components/common/StatusBadge';
import { getDraftStatusLabel } from '@entities/rag-eval';
import { formatPercent, formatTimestamp } from '@entities/rag-eval';
import { ProgressList } from '../../../components/progress';
import { draftGenerationConfig } from '../../../components/progress/configs/draftGeneration';
import { usePagination } from '@shared/hooks/usePagination';

const { Title, Text, Paragraph } = Typography;

export function DraftPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState<string | undefined>();
  const [sortOrder, setSortOrder] = useState<string | undefined>();
  const { currentPage, pageSize, total, setCurrentPage, setPageSize, setTotal } = usePagination();

  const { data, isLoading, isError } = useDrafts({
    status: statusFilter as 'pending' | 'approved' | 'rejected' | undefined,
    page: currentPage,
    page_size: pageSize,
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  // 同步服务端返回的 total
  const serverTotal = data?.total ?? 0;
  if (serverTotal !== total) setTotal(serverTotal);

  const { data: sourceDocsData } = useSourceDocuments();
  const sourceDocuments = sourceDocsData?.items || [];

  const deleteMutation = useDeleteDrafts();
  const generateMutation = useCreateDrafts();
  const reviewMutation = useReviewDraft();

  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [detailDraft, setDetailDraft] = useState<TestCaseDraft | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);

  const { tasks: genTasks, startTracking, removeTask, cancelTask } = useDraftGenerationProgress();

  const filteredDrafts = (data?.items || []).filter((d) => {
    if (!searchText) return true;
    return d.query.toLowerCase().includes(searchText.toLowerCase());
  });

  const handlePageChange = useCallback((page: number, size: number) => {
    setCurrentPage(page);
    if (size !== pageSize) setPageSize(size);
  }, [pageSize, setCurrentPage, setPageSize]);

  // 状态筛选变更时重置到第一页
  const handleStatusChange = useCallback((value: string | undefined) => {
    setStatusFilter(value);
    setCurrentPage(1);
  }, [setCurrentPage]);

  const handleSortChange = useCallback((by?: string, order?: string) => {
    setSortBy(by);
    setSortOrder(order);
    setCurrentPage(1);
  }, [setCurrentPage]);

  const handleDelete = useCallback(
    (id: string) => {
      Modal.confirm({
        title: '确认删除',
        content: '删除后不可恢复，确定要删除该草稿吗？',
        onOk: async () => {
          await deleteMutation.mutateAsync([id]);
          message.success('已删除');
        },
      });
    },
    [deleteMutation],
  );

  const handleBatchDelete = useCallback(async () => {
    if (selectedRowKeys.length === 0) return;
    Modal.confirm({
      title: '批量删除',
      content: `确定要删除选中的 ${selectedRowKeys.length} 个草稿吗？`,
      onOk: async () => {
        await deleteMutation.mutateAsync(selectedRowKeys);
        setSelectedRowKeys([]);
        message.success(`已删除 ${selectedRowKeys.length} 个草稿`);
      },
    });
  }, [selectedRowKeys, deleteMutation]);

  const handleBatchApprove = useCallback(async () => {
    if (selectedRowKeys.length === 0) return;
    Modal.confirm({
      title: '批量通过',
      content: `确定要通过选中的 ${selectedRowKeys.length} 个草稿吗？`,
      onOk: async () => {
        // 后端仅支持单个审核，逐个调用
        const results = await Promise.allSettled(
          selectedRowKeys.map(id => reviewMutation.mutateAsync({ id, status: 'approved' })),
        );
        const succeeded = results.filter(r => r.status === 'fulfilled').length;
        const failed = results.filter(r => r.status === 'rejected').length;
        setSelectedRowKeys([]);
        if (failed > 0) {
          message.warning(`通过 ${succeeded} 个，失败 ${failed} 个`);
        } else {
          message.success(`已通过 ${succeeded} 个草稿`);
        }
      },
    });
  }, [selectedRowKeys, reviewMutation]);

  const handleGenerate = useCallback(
    async (values: { document_id: string; max_qa_per_chunk: number; min_qa_per_chunk: number }) => {
      const result = await generateMutation.mutateAsync({
        documentId: values.document_id,
        config: {
          max_qa_per_chunk: values.max_qa_per_chunk,
          min_qa_per_chunk: values.min_qa_per_chunk,
        },
      });
      setShowGenerateModal(false);
      const docName = sourceDocuments.find(d => d.id === values.document_id)?.name;
      startTracking(result.batch_id, docName);
    },
    [generateMutation, sourceDocuments, startTracking],
  );

  const handleApprove = useCallback(
    async (id: string) => {
      await reviewMutation.mutateAsync({ id, status: 'approved' });
      message.success('已通过');
    },
    [reviewMutation],
  );

  const handleReject = useCallback(
    async (id: string) => {
      await reviewMutation.mutateAsync({ id, status: 'rejected' });
      message.success('已驳回');
    },
    [reviewMutation],
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>草稿管理</Title>
        <Button type="primary" onClick={() => setShowGenerateModal(true)}>AI 生成草稿</Button>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Input.Search placeholder="搜索查询..." allowClear onSearch={setSearchText} style={{ width: '100%' }} />
        </Col>
        <Col xs={12} sm={6}>
          <Select placeholder="状态筛选" allowClear value={statusFilter} onChange={handleStatusChange}
            options={['pending', 'generating', 'generated', 'approved', 'rejected', 'archived', 'imported'].map((s) => ({ value: s, label: getDraftStatusLabel(s as never) }))}
            style={{ width: '100%' }} />
        </Col>
        <Col xs={24} sm={10}>
          <Space>
            <Button disabled={selectedRowKeys.length === 0} onClick={handleBatchApprove}>批量通过</Button>
            <Button danger disabled={selectedRowKeys.length === 0} onClick={handleBatchDelete} loading={deleteMutation.isPending}>批量删除</Button>
          </Space>
        </Col>
      </Row>

      <ProgressList
        config={{ ...draftGenerationConfig, onCancel: (task) => cancelTask(task.taskId), onDelete: (task) => removeTask(task.taskId) }}
        tasks={genTasks}
      />

      {isError && <Alert type="error" message="加载草稿列表失败" showIcon style={{ marginBottom: 16 }} />}

      <DraftTable
        drafts={filteredDrafts}
        loading={isLoading}
        pagination={{ current: currentPage, pageSize, total, onPageChange: handlePageChange }}
        sort={{ sortBy, sortOrder }}
        onSortChange={handleSortChange}
        onView={setDetailDraft}
        onApprove={handleApprove}
        onReject={handleReject}
        onDelete={handleDelete}
        selectedRowKeys={selectedRowKeys}
        onSelectChange={setSelectedRowKeys}
      />

      <Modal title="草稿详情" open={!!detailDraft} onCancel={() => setDetailDraft(null)} footer={null} width={700}>
        {detailDraft && (
          <div>
            <Space wrap style={{ marginBottom: 12 }}>
              <StatusBadge status={detailDraft.status} type="draft" />
            </Space>
            <Paragraph><Text strong>查询: </Text>{detailDraft.query}</Paragraph>
            <Paragraph><Text strong>忠实度: </Text>{detailDraft.faithfulness_score != null ? formatPercent(detailDraft.faithfulness_score, 1) : '未评估'}</Paragraph>
            {detailDraft.expected_keywords.length > 0 && <Paragraph><Text strong>预期关键词: </Text>{detailDraft.expected_keywords.join(', ')}</Paragraph>}
            <Text type="secondary" style={{ fontSize: 12 }}>创建: {formatTimestamp(detailDraft.created_at)} | 更新: {formatTimestamp(detailDraft.updated_at)}</Text>
          </div>
        )}
      </Modal>

      <Modal title="AI 生成草稿" open={showGenerateModal} onCancel={() => setShowGenerateModal(false)} footer={null} width={560}>
        <DraftGenerationForm
          documents={sourceDocuments.map((d) => ({ id: d.id, name: d.name }))}
          loading={generateMutation.isPending}
          onSubmit={handleGenerate}
        />
      </Modal>
    </div>
  );
}
