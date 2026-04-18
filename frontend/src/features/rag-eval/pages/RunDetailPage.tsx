/**
 * 运行详情页
 * 路由: /rag-eval/runs/:id
 */

import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  Descriptions,
  Button,
  Tag,
  Space,
  Card,
  Statistic,
  Row,
  Col,
  Progress,
  Input,
  Typography,
  Spin,
} from 'antd';
import { ArrowLeftOutlined, FileTextOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useRunDetail } from '../hooks/useRunDetail';
import { RunDetailTable } from '../components/RunDetailTable';

const { Title } = Typography;

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  running: { label: '运行中', color: 'blue', icon: <LoadingOutlined /> },
  completed: { label: '已完成', color: 'green', icon: <CheckCircleOutlined /> },
  failed: { label: '失败', color: 'red', icon: <CloseCircleOutlined /> },
};

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { run, caseResults, loading, progress, filters } = useRunDetail(id);

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
            value={filters.keyword}
            onChange={e => filters.setKeyword(e.target.value)}
            allowClear
          />
          <Space>
            <Button type={filters.filter === 'all' ? 'primary' : 'default'} onClick={() => filters.setFilter('all')}>全部</Button>
            <Button type={filters.filter === 'hit1' ? 'primary' : 'default'} onClick={() => filters.setFilter('hit1')}>命中@1</Button>
            <Button type={filters.filter === 'miss' ? 'primary' : 'default'} onClick={() => filters.setFilter('miss')}>未命中</Button>
          </Space>
        </div>

        <RunDetailTable results={caseResults} />
      </div>
    </div>
  );
}