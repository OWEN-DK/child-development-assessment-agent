/**
 * 运行详情页
 * 路由: /rag-eval/runs/:id
 */

import { useEffect, useState, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  Descriptions,
  Table,
  Button,
  Tag,
  Space,
  Card,
  Statistic,
  Row,
  Col,
  Progress,
  Input,
  message,
  Typography,
  Spin,
} from 'antd';
import { ArrowLeftOutlined, FileTextOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getTestRun } from '@/api/rag-test';
import { SseClient } from '@/services/sse-client';
import type { TestRun, TestResult } from '@/api/rag-test';

const { Title } = Typography;

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  running: { label: '运行中', color: 'blue', icon: <LoadingOutlined /> },
  completed: { label: '已完成', color: 'green', icon: <CheckCircleOutlined /> },
  failed: { label: '失败', color: 'red', icon: <CloseCircleOutlined /> },
};

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<TestRun | null>(null);
  const [caseResults, setCaseResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [filter, setFilter] = useState<string>('all');
  const [keyword, setKeyword] = useState('');
  const sseClientRef = useRef<SseClient | null>(null);

  useEffect(() => {
    if (!id) return;
    loadData();
    return () => {
      sseClientRef.current?.disconnect();
    };
  }, [id]);

  const loadData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await getTestRun(id);
      setRun(data);
      setCaseResults(data.test_results || []);
      setProgress({ current: data.passed_test_cases || 0, total: data.total_test_cases || 0 });

      if (data.status === 'running') {
        connectSSE(id);
      }
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const connectSSE = (runId: string) => {
    const client = new SseClient();
    sseClientRef.current = client;

    client.on('progress', (event) => {
      if (event.type !== 'progress') return;
      setProgress({ current: event.current_case || 0, total: event.total_cases || 0 });
    });

    client.on('case_result', (event) => {
      if (event.type !== 'case_result') return;
      setCaseResults(prev => [...prev, {
        test_case_id: event.case_id,
        query: event.query,
        age: 0,
        precision: event.hit_at_1 ? 1 : 0,
        recall: event.hit_at_5 ? 1 : 0,
        f1_score: event.hit_at_1 ? 1 : 0,
        mrr: event.hit_at_1 ? 1 : 0,
        ndcg_at_k: 0,
        results: [],
        executed_at: event.timestamp,
        execution_time_ms: 0,
      }]);
    });

    client.on('test_completed', (event) => {
      if (event.type !== 'test_completed') return;
      setRun(prev => prev ? {
        ...prev,
        status: 'completed',
        overall_precision: event.overall_metrics?.precision || 0,
        overall_recall: event.overall_metrics?.recall || 0,
        overall_f1: event.overall_metrics?.f1 || 0,
        overall_mrr: event.overall_metrics?.mrr || 0,
        overall_ndcg: event.overall_metrics?.ndcg || 0,
        total_test_cases: event.total_cases,
        passed_test_cases: event.passed_cases,
      } : null);
      setProgress({ current: event.passed_cases, total: event.total_cases });
    });

    client.on('run_failed', (event) => {
      if (event.type !== 'run_failed') return;
      setRun(prev => prev ? { ...prev, status: 'failed' } : null);
      message.error(`运行失败: ${event.error_message}`);
    });

    client.connect(runId);
  };

  const filteredResults = caseResults.filter(r => {
    if (keyword && !r.query.toLowerCase().includes(keyword.toLowerCase())) return false;
    if (filter === 'hit1' && r.precision !== 1) return false;
    if (filter === 'miss' && r.precision > 0) return false;
    return true;
  });

  const columns = [
    {
      title: '#',
      key: 'index',
      width: 50,
      render: (_: unknown, __: unknown, index: number) => index + 1,
    },
    {
      title: '查询语句',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
    },
    {
      title: '状态',
      key: 'status',
      width: 60,
      render: (_: unknown, record: TestResult) => (
        record.precision > 0
          ? <Tag color="green"><CheckCircleOutlined /></Tag>
          : <Tag color="red"><CloseCircleOutlined /></Tag>
      ),
    },
    {
      title: 'P@1',
      dataIndex: 'precision',
      key: 'precision',
      width: 70,
      render: (val: number) => val.toFixed(2),
    },
    {
      title: 'R@1',
      dataIndex: 'recall',
      key: 'recall',
      width: 70,
      render: (val: number) => val.toFixed(2),
    },
    {
      title: '耗时',
      dataIndex: 'execution_time_ms',
      key: 'execution_time_ms',
      width: 80,
      render: (val: number) => `${val}ms`,
    },
  ];

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!run) return <div>运行记录不存在</div>;

  const statusConfig = STATUS_CONFIG[run.status] || { label: run.status, color: 'default', icon: null };
  const pct = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Link to="/rag-eval/runs">
          <Button type="link" icon={<ArrowLeftOutlined />}>返回运行列表</Button>
        </Link>
      </div>

      <Descriptions
        title={<Title level={4} style={{ margin: 0 }}>{run.name}</Title>}
        bordered
        column={4}
        extra={
          run.status === 'completed' && (
            <Button type="primary" icon={<FileTextOutlined />} onClick={() => navigate(`/rag-eval/reports/${id}`)}>
              生成评估报告
            </Button>
          )
        }
      >
        <Descriptions.Item label="状态">
          <Tag color={statusConfig.color} icon={statusConfig.icon}>{statusConfig.label}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="开始时间">{dayjs(run.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
        <Descriptions.Item label="完成时间">
          {run.completed_at ? dayjs(run.completed_at).format('YYYY-MM-DD HH:mm') : '-'}
        </Descriptions.Item>
      </Descriptions>

      {run.status === 'running' && (
        <Card style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Statistic title="进度" value={pct} suffix="%" />
            </Col>
            <Col span={6}>
              <Statistic title="已完成" value={progress.current} />
            </Col>
            <Col span={6}>
              <Statistic title="总用例" value={progress.total} />
            </Col>
          </Row>
          <Progress percent={pct} style={{ marginTop: 16 }} />
        </Card>
      )}

      {run.status === 'completed' && (
        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col span={4}><Card><Statistic title="P@1" value={run.overall_precision || 0} precision={2} /></Card></Col>
          <Col span={4}><Card><Statistic title="R@5" value={run.overall_recall || 0} precision={2} /></Card></Col>
          <Col span={4}><Card><Statistic title="MRR" value={run.overall_mrr || 0} precision={2} /></Card></Col>
          <Col span={4}><Card><Statistic title="NDCG" value={run.overall_ndcg || 0} precision={2} /></Card></Col>
          <Col span={4}><Card><Statistic title="通过率" value={run.total_test_cases ? ((run.passed_test_cases || 0) / run.total_test_cases * 100) : 0} precision={1} suffix="%" /></Card></Col>
        </Row>
      )}

      <div style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 16, display: 'flex', gap: 12 }}>
          <Input
            placeholder="搜索用例结果"
            style={{ width: 240 }}
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            allowClear
          />
          <Space>
            <Button type={filter === 'all' ? 'primary' : 'default'} onClick={() => setFilter('all')}>全部</Button>
            <Button type={filter === 'hit1' ? 'primary' : 'default'} onClick={() => setFilter('hit1')}>命中@1</Button>
            <Button type={filter === 'miss' ? 'primary' : 'default'} onClick={() => setFilter('miss')}>未命中</Button>
          </Space>
        </div>

        <Table
          columns={columns}
          dataSource={filteredResults}
          rowKey="test_case_id"
          pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
        />
      </div>
    </div>
  );
}
