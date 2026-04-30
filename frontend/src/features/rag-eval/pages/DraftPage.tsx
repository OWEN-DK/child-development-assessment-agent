import { useState, useCallback } from 'react';
import {
  Space, Button, Select, Input, Modal, message, Typography, Alert, Row, Col,
} from 'antd';
import type { TestCaseDraft, TestDomain } from '@entities/rag-eval';
import { DOMAIN_MAP } from '@entities/rag-eval';
import {
  useDrafts, useDeleteDrafts, useCreateDrafts, useReviewDraft, useSourceDocuments,
} from '../hooks/useDrafts';
import { useDraftGenerationProgress } from '../hooks/useDraftGenerationProgress';
import { DraftTable } from '../components/draft/DraftTable';
import { DraftGenerationForm } from '../components/draft/DraftGenerationForm';
import { DomainTag } from '../components/common/DomainTag';
import { StatusBadge } from '../components/common/StatusBadge';
import { getDraftStatusLabel } from '@entities/rag-eval';
import { formatPercent, formatAgeRange, formatTimestamp } from '@entities/rag-eval';
import { ProgressList } from '../../../components/progress';
import { draftGenerationConfig } from '../../../components/progress/configs/draftGeneration';

const { Title, Text, Paragraph } = Typography;

export function DraftPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [domainFilter, setDomainFilter] = useState<string | undefined>();
  const [searchText, setSearchText] = useState('');

  const { data, isLoading, isError } = useDrafts({
    status: statusFilter as 'pending' | 'approved' | 'rejected' | undefined,
    domain: domainFilter,
    page_size: 20,
  });

  const { data: sourceDocsData } = useSourceDocuments();
  const sourceDocuments = sourceDocsData?.items || [];

  const deleteMutation = useDeleteDrafts();
  const generateMutation = useCreateDrafts();
  const reviewMutation = useReviewDraft();

  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [detailDraft, setDetailDraft] = useState<TestCaseDraft | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);

  const { tasks: genTasks, startTracking, removeTask } = useDraftGenerationProgress();

  const filteredDrafts = (data?.items || []).filter((d) => {
    if (!searchText) return true;
    return d.query.toLowerCase().includes(searchText.toLowerCase());
  });

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

  const handleBatchImport = useCallback(async () => {
    if (selectedRowKeys.length === 0) return;
    message.info('批量导入用例功能开发中');
  }, [selectedRowKeys]);

  const handleGenerate = useCallback(
    async (values: { document_id: string; max_qa_per_chunk: number; min_qa_per_chunk: number; age_ranges: string[]; domains: TestDomain[] }) => {
      const result = await generateMutation.mutateAsync({
        documentId: values.document_id,
        config: {
          max_qa_per_chunk: values.max_qa_per_chunk,
          min_qa_per_chunk: values.min_qa_per_chunk,
          age_ranges: values.age_ranges,
          domains: values.domains,
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
        <Col xs={24} sm={6}>
          <Input.Search placeholder="搜索查询..." allowClear onSearch={setSearchText} style={{ width: '100%' }} />
        </Col>
        <Col xs={12} sm={4}>
          <Select placeholder="领域筛选" allowClear value={domainFilter} onChange={setDomainFilter}
            options={Object.entries(DOMAIN_MAP).map(([v, l]) => ({ value: v, label: l }))} style={{ width: '100%' }} />
        </Col>
        <Col xs={12} sm={4}>
          <Select placeholder="状态筛选" allowClear value={statusFilter} onChange={setStatusFilter}
            options={['pending', 'generating', 'generated', 'approved', 'rejected', 'archived', 'imported'].map((s) => ({ value: s, label: getDraftStatusLabel(s as never) }))}
            style={{ width: '100%' }} />
        </Col>
        <Col xs={24} sm={10}>
          <Space>
            <Button danger disabled={selectedRowKeys.length === 0} onClick={handleBatchDelete} loading={deleteMutation.isPending}>批量删除</Button>
            <Button disabled={selectedRowKeys.length === 0} onClick={handleBatchImport}>批量导入用例</Button>
          </Space>
        </Col>
      </Row>

      <ProgressList
        config={{ ...draftGenerationConfig, onDelete: (task) => removeTask(task.taskId) }}
        tasks={genTasks}
      />

      {isError && <Alert type="error" message="加载草稿列表失败" showIcon style={{ marginBottom: 16 }} />}

      <DraftTable
        drafts={filteredDrafts}
        loading={isLoading}
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
              <DomainTag domain={detailDraft.domain} />
              <StatusBadge status={detailDraft.status} type="draft" />
            </Space>
            <Paragraph><Text strong>查询: </Text>{detailDraft.query}</Paragraph>
            <Paragraph><Text strong>年龄段: </Text>{formatAgeRange(detailDraft.age)}</Paragraph>
            <Paragraph><Text strong>忠实度: </Text>{detailDraft.faithfulness_score != null ? formatPercent(detailDraft.faithfulness_score, 1) : '未评估'}</Paragraph>
            {detailDraft.answer_points_summary && <Paragraph><Text strong>答案要点: </Text>{detailDraft.answer_points_summary}</Paragraph>}
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
