import { useState, useCallback } from 'react';
import {
  Button, Select, Typography, Spin, Alert, Empty, message, Popconfirm, Row, Col, Modal, Timeline,
} from 'antd';
import { RollbackOutlined, HistoryOutlined } from '@ant-design/icons';
import type { TestRun } from '@entities/rag-eval';
import { useTuningSuggestions, useAdoptSuggestion, useRejectSuggestion, useIgnoreSuggestion, useConfigVersions, useRollbackConfig } from '../hooks/useTuning';
import { useTestRuns } from '../hooks/useTestRuns';
import { ConflictAlert } from '../components/tuning/ConflictAlert';
import { SuggestionPanel } from '../components/tuning/SuggestionPanel';
import { formatTimestamp } from '@entities/rag-eval';

const { Title, Text } = Typography;

export function TuningPage() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [versionsModalOpen, setVersionsModalOpen] = useState(false);

  const { data: runsData } = useTestRuns();
  const { data: suggestions = [], isLoading, isError } = useTuningSuggestions(selectedRunId || '');
  const adoptMutation = useAdoptSuggestion();
  const rejectMutation = useRejectSuggestion();
  const ignoreMutation = useIgnoreSuggestion();
  const { data: configVersions = [] } = useConfigVersions();
  const rollbackMutation = useRollbackConfig();

  const runs = runsData?.items || [];

  const filteredSuggestions = statusFilter
    ? suggestions.filter((s) => s.status === statusFilter)
    : suggestions;

  const conflicts: Array<{ suggestionA: string; suggestionB: string; configKey: string }> = [];

  const handleAdopt = useCallback(async (id: string) => {
    await adoptMutation.mutateAsync({ suggestionId: id, runId: selectedRunId || '' });
    message.success('已采纳');
  }, [adoptMutation, selectedRunId]);

  const handleReject = useCallback(async (id: string) => {
    await rejectMutation.mutateAsync({ suggestionId: id, runId: selectedRunId || '' });
    message.success('已驳回');
  }, [rejectMutation, selectedRunId]);

  const handleIgnore = useCallback(async (id: string) => {
    await ignoreMutation.mutateAsync({ suggestionId: id, runId: selectedRunId || '' });
    message.success('已忽略');
  }, [ignoreMutation, selectedRunId]);

  const handleRollback = useCallback(async (versionId: string) => {
    Modal.confirm({
      title: '确认回滚', content: '回滚后将恢复该版本的配置，确定继续？',
      onOk: async () => { await rollbackMutation.mutateAsync(versionId); message.success('已回滚'); },
    });
  }, [rollbackMutation]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>调优管理</Title>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Select placeholder="选择运行" value={selectedRunId} onChange={setSelectedRunId} allowClear style={{ width: '100%' }} showSearch
            filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
            options={runs.map((r: TestRun) => ({ value: r.id, label: r.name }))} notFoundContent={null} />
        </Col>
        <Col xs={12} sm={4}>
          <Select placeholder="状态筛选" value={statusFilter} onChange={setStatusFilter} allowClear style={{ width: '100%' }}
            options={['pending', 'adopted', 'rejected', 'ignored'].map((s) => ({ value: s, label: s === 'adopted' ? '已采纳' : s === 'rejected' ? '已驳回' : s === 'ignored' ? '已忽略' : '待处理' }))} />
        </Col>
        <Col xs={12} sm={3}>
          <Button icon={<HistoryOutlined />} onClick={() => setVersionsModalOpen(true)}>配置版本</Button>
        </Col>
      </Row>

      {conflicts.length > 0 && <div style={{ marginBottom: 16 }}><ConflictAlert conflicts={conflicts} /></div>}
      {isError && <Alert type="error" message="加载调优建议失败" showIcon style={{ marginBottom: 16 }} />}

      {!selectedRunId ? (
        <Empty description="请先选择一个运行" style={{ padding: 60 }} />
      ) : isLoading ? (
        <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
      ) : (
        <SuggestionPanel suggestions={filteredSuggestions} onAdopt={handleAdopt} onReject={handleReject} onIgnore={handleIgnore} />
      )}

      <Modal title="配置版本历史" open={versionsModalOpen} onCancel={() => setVersionsModalOpen(false)} footer={null} width={560}>
        {configVersions.length === 0 ? (
          <Empty description="暂无版本记录" />
        ) : (
          <Timeline items={configVersions.map((v) => ({
            color: 'blue',
            children: (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text strong>{formatTimestamp(v.created_at)}</Text><br />
                  <Text type="secondary">{v.description || '无描述'}</Text>
                </div>
                <Popconfirm title="回滚到此版本？" onConfirm={() => handleRollback(v.id)}>
                  <Button size="small" icon={<RollbackOutlined />} loading={rollbackMutation.isPending}>回滚</Button>
                </Popconfirm>
              </div>
            ),
          }))} />
        )}
      </Modal>
    </div>
  );
}
