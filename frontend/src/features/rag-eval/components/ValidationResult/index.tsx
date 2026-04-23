/**
 * 6层校验结果展示组件
 * 每层结果独立 Tab 页展示，支持按问题类型、严重程度筛选
 */

import { useState, useEffect } from 'react';
import { Card, Tabs, Table, Tag, Select, Empty, Spin, Descriptions, Alert } from 'antd';
import { getReportByRunId } from '@/api/rag-eval/reports';
import type { ValidationLayerResult } from '@/api/rag-eval/reports';
import { notification } from '@shared/lib/notification';

const LAYER_CONFIG: Record<number, { key: string; label: string; color: string }> = {
  1: { key: 'layer1', label: '规则引擎', color: 'blue' },
  2: { key: 'layer2', label: '历史对比', color: 'cyan' },
  3: { key: 'layer3', label: 'LLM 诊断', color: 'purple' },
  4: { key: 'layer4', label: '数据质量', color: 'orange' },
  5: { key: 'layer5', label: '检索链路', color: 'green' },
  6: { key: 'layer6', label: '验证保障', color: 'magenta' },
};

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pass: { label: '通过', color: 'green' },
  warn: { label: '警告', color: 'orange' },
  fail: { label: '失败', color: 'red' },
  skipped: { label: '跳过', color: 'default' },
  degraded: { label: '降级', color: 'volcano' },
};

interface ValidationResultProps {
  runId: string;
}

export default function ValidationResult({ runId }: ValidationResultProps) {
  const [loading, setLoading] = useState(false);
  const [layerResults, setLayerResults] = useState<ValidationLayerResult[]>([]);
  const [activeLayer, setActiveLayer] = useState<string>('1');
  const [statusFilter, setStatusFilter] = useState<string>();

  useEffect(() => {
    loadAllLayers();
  }, [runId]);

  const loadAllLayers = async () => {
    if (!runId) return;
    setLoading(true);
    try {
      const report = await getReportByRunId(runId);
      if (report.validation_results) {
        setLayerResults(report.validation_results);
      }
    } catch {
      notification.error('加载校验结果失败');
    } finally {
      setLoading(false);
    }
  };

  const filteredResults = layerResults.filter(r => {
    if (statusFilter && r.status !== statusFilter) return false;
    return true;
  });

  const columns = [
    {
      title: '层',
      dataIndex: 'layer',
      key: 'layer',
      width: 60,
      render: (layer: number) => <Tag color={LAYER_CONFIG[layer]?.color}>{layer}</Tag>,
    },
    {
      title: '名称',
      key: 'name',
      render: (_: unknown, record: ValidationLayerResult) =>
        LAYER_CONFIG[record.layer]?.label || `Layer ${record.layer}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={STATUS_CONFIG[status]?.color}>
          {STATUS_CONFIG[status]?.label || status}
        </Tag>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 100,
      render: (ms: number) => ms ? `${ms}ms` : '-',
    },
    {
      title: '详情',
      key: 'details',
      render: (_: unknown, record: ValidationLayerResult) => (
        <Tag color="processing" style={{ cursor: 'pointer' }} onClick={() => setActiveLayer(String(record.layer))}>
          查看
        </Tag>
      ),
    },
  ];

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />;

  if (layerResults.length === 0) {
    return (
      <Card title="6层校验结果">
        <Empty description="暂无校验结果，请先执行校验" />
      </Card>
    );
  }

  return (
    <Card title="6层校验结果" extra={
      <Select
        placeholder="状态筛选"
        style={{ width: 120 }}
        value={statusFilter}
        onChange={setStatusFilter}
        allowClear
        options={Object.entries(STATUS_CONFIG).map(([key, val]) => ({
          label: val.label,
          value: key,
        }))}
      />
    }>
      <Table
        columns={columns}
        dataSource={filteredResults}
        rowKey="layer"
        pagination={false}
        locale={{ emptyText: '暂无匹配的校验结果' }}
      />

      <Tabs
        activeKey={activeLayer}
        onChange={setActiveLayer}
        items={layerResults.map(r => ({
          key: String(r.layer),
          label: LAYER_CONFIG[r.layer]?.label || `Layer ${r.layer}`,
          children: <LayerDetail result={r} />,
        }))}
      />
    </Card>
  );
}

function LayerDetail({ result }: { result: ValidationLayerResult }) {
  const statusInfo = STATUS_CONFIG[result.status] || { label: result.status, color: 'default' };

  return (
    <div>
      <Alert
        message={`校验状态: ${statusInfo.label}`}
        type={result.status === 'pass' ? 'success' : result.status === 'fail' ? 'error' : 'warning'}
        style={{ marginBottom: 16 }}
      />

      {result.data && Object.keys(result.data).length > 0 && (
        <Descriptions bordered column={2}>
          {Object.entries(result.data).map(([key, value]) => (
            <Descriptions.Item key={key} label={key}>
              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
            </Descriptions.Item>
          ))}
        </Descriptions>
      )}

      {result.duration_ms && (
        <p style={{ marginTop: 16, color: '#888' }}>
          校验耗时: {result.duration_ms}ms
        </p>
      )}
    </div>
  );
}
