/**
 * 评估视图
 *
 * 管道评估入口：展示评估运行历史、新建评估配置、运行详情（指标卡片 + 调优建议）
 * 从 PipelineWorkbench store 获取 pipelineId，无需独立路由参数
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Drawer,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExperimentOutlined,
  PlusOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type {
  TestRun,
  TestRunStatus,
  RunMetrics,
  TuningSuggestion,
  Severity,
  TestSet,
} from '@/entities/rag-eval/types'
import {
  getTestRuns,
  createTestRun,
  deleteTestRun,
  executeTestRun,
  getRunMetrics,
  getTuningSuggestions,
} from '@/api/rag-eval/evaluation'
import { getTestSets } from '@/api/rag-eval/evaluation'
import { usePipelineWorkbenchStore } from '../stores/pipelineWorkbenchStore'

const { Title, Text } = Typography

/** 运行状态颜色映射 */
const RUN_STATUS_COLOR: Record<TestRunStatus, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
}

/** 运行状态中文标签 */
const RUN_STATUS_LABEL: Record<TestRunStatus, string> = {
  pending: '待执行',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

/** 严重性图标与颜色 */
function severityStyle(level: Severity): { color: string; icon: React.ReactNode } {
  switch (level) {
    case 'critical':
      return { color: '#ff4d4f', icon: <CloseCircleOutlined /> }
    case 'warning':
      return { color: '#faad14', icon: <WarningOutlined /> }
    case 'info':
      return { color: '#1890ff', icon: <CheckCircleOutlined /> }
  }
}

/** 指标卡片分数颜色 */
function scoreColor(score: number): string {
  if (score >= 0.8) return '#52c41a'
  if (score >= 0.6) return '#faad14'
  return '#ff4d4f'
}

/** 格式化分数 */
function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return '-'
  return (score * 100).toFixed(1) + '%'
}

// ==================== 运行列表列定义 ====================

function buildRunColumns(
  onDelete: (id: string) => void,
): ColumnsType<TestRun> {
  return [
    {
      title: '名称',
      dataIndex: 'name',
      width: 200,
      render: (name: string | null) => name ?? '未命名',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: TestRunStatus) => (
        <Tag color={RUN_STATUS_COLOR[status]}>
          {RUN_STATUS_LABEL[status]}
        </Tag>
      ),
    },
    {
      title: '综合得分',
      dataIndex: 'overall_score',
      width: 110,
      render: (score: number | null) => (
        <span style={{ color: score !== null ? scoreColor(score) : undefined, fontWeight: 600 }}>
          {formatScore(score)}
        </span>
      ),
    },
    {
      title: '通过率',
      width: 110,
      render: (_: unknown, record: TestRun) => {
        if (record.total_test_cases === 0) return '-'
        return `${record.passed_test_cases}/${record.total_test_cases}`
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作',
      width: 80,
      render: (_: unknown, record: TestRun) => (
        <Popconfirm title="确认删除该运行记录？" onConfirm={(e) => { e?.stopPropagation(); onDelete(record.id) }}>
          <Button type="link" size="small" danger onClick={(e) => e.stopPropagation()}>
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ]
}

// ==================== 主组件 ====================

export default function EvaluateView() {
  const { pipelineId, pipelineName } = usePipelineWorkbenchStore()
  const [newEvalForm] = Form.useForm()

  // 运行列表状态
  const [runs, setRuns] = useState<TestRun[]>([])
  const [runsTotal, setRunsTotal] = useState(0)
  const [runsLoading, setRunsLoading] = useState(false)
  const [runsPage, setRunsPage] = useState(1)

  // 新建评估弹窗
  const [newEvalOpen, setNewEvalOpen] = useState(false)
  const [newEvalSubmitting, setNewEvalSubmitting] = useState(false)
  const [availableTestSets, setAvailableTestSets] = useState<TestSet[]>([])

  // 运行详情面板
  const [selectedRun, setSelectedRun] = useState<TestRun | null>(null)
  const [runMetrics, setRunMetrics] = useState<RunMetrics | null>(null)
  const [tuningSuggestions, setTuningSuggestions] = useState<TuningSuggestion[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  // ==================== 加载运行列表 ====================

  const loadRuns = useCallback(async () => {
    if (!pipelineId) return
    setRunsLoading(true)
    try {
      const result = await getTestRuns({
        page: runsPage,
        page_size: 20,
        pipeline_id: pipelineId,
      })
      setRuns(result.items ?? [])
      setRunsTotal(result.total ?? 0)
    } catch {
      message.error('加载评估历史失败')
    } finally {
      setRunsLoading(false)
    }
  }, [pipelineId, runsPage])

  useEffect(() => {
    loadRuns()
  }, [loadRuns])

  // ==================== 加载可用测试集 ====================

  useEffect(() => {
    if (newEvalOpen && availableTestSets.length === 0) {
      getTestSets({ page: 1, page_size: 100 })
        .then((result) => setAvailableTestSets(result.items ?? []))
        .catch(() => {
          // 静默失败
        })
    }
  }, [newEvalOpen, availableTestSets.length])

  // ==================== 新建评估 ====================

  async function handleCreateEval() {
    try {
      const values = await newEvalForm.validateFields()
      setNewEvalSubmitting(true)

      const run = await createTestRun({
        pipeline_id: pipelineId!,
        test_set_ids: values.test_set_ids,
        name: values.name,
        auto_snapshot: values.auto_snapshot ?? false,
      })

      // 立即执行
      await executeTestRun(run.id)

      message.success('评估运行已创建并开始执行')
      setNewEvalOpen(false)
      newEvalForm.resetFields()
      loadRuns()
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    } finally {
      setNewEvalSubmitting(false)
    }
  }

  // ==================== 删除运行 ====================

  async function handleDeleteRun(runId: string) {
    try {
      await deleteTestRun(runId)
      message.success('运行记录已删除')
      loadRuns()
    } catch {
      message.error('删除失败')
    }
  }

  // ==================== 查看运行详情 ====================

  async function handleViewRun(run: TestRun) {
    setSelectedRun(run)
    setDetailLoading(true)

    try {
      const [metrics, suggestions] = await Promise.all([
        getRunMetrics(run.id).catch(() => null),
        getTuningSuggestions(run.id).catch(() => []),
      ])
      setRunMetrics(metrics)
      setTuningSuggestions(suggestions)
    } catch {
      message.error('加载运行详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  /** 关闭详情面板 */
  function handleCloseDetail() {
    setSelectedRun(null)
    setRunMetrics(null)
    setTuningSuggestions([])
  }

  // ==================== 列定义 ====================

  const runColumns = buildRunColumns(
    (id) => handleDeleteRun(id),
  )

  // ==================== 渲染 ====================

  return (
    <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <ExperimentOutlined style={{ marginRight: 8 }} />
            评估视图
          </Title>
          <Text type="secondary">管道: {pipelineName}</Text>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setNewEvalOpen(true)}
          disabled={!pipelineId}
        >
          新建评估
        </Button>
      </div>

      {/* 运行列表 */}
      <Table<TestRun>
        rowKey="id"
        columns={runColumns}
        dataSource={runs}
        loading={runsLoading}
        onRow={(record) => ({
          onClick: () => handleViewRun(record),
          style: { cursor: 'pointer' },
        })}
        pagination={{
          current: runsPage,
          total: runsTotal,
          pageSize: 20,
          showTotal: (total) => `共 ${total} 条运行记录`,
          onChange: (page) => setRunsPage(page),
        }}
      />

      {/* ---- 新建评估弹窗 ---- */}
      <Modal
        title="新建评估"
        open={newEvalOpen}
        onOk={handleCreateEval}
        onCancel={() => setNewEvalOpen(false)}
        confirmLoading={newEvalSubmitting}
        width={520}
      >
        <Form form={newEvalForm} layout="vertical" autoComplete="off">
          <Form.Item name="name" label="运行名称">
            <Input placeholder="可选，如不填写将自动生成" />
          </Form.Item>
          <Form.Item name="test_set_ids" label="测试集" rules={[{ required: true, message: '请选择至少一个测试集' }]}>
            <Select
              mode="multiple"
              placeholder="选择测试集"
              options={availableTestSets.map((set) => ({
                value: set.id,
                label: `${set.name} (${set.case_count} 用例)`,
              }))}
            />
          </Form.Item>
          <Form.Item name="auto_snapshot" label="自动快照" valuePropName="checked" initialValue={true}>
            <Select
              options={[
                { value: true, label: '运行前自动创建知识库快照' },
                { value: false, label: '不创建快照' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* ---- 运行详情抽屉 ---- */}
      <Drawer
        title={selectedRun?.name ?? '运行详情'}
        open={selectedRun !== null}
        onClose={handleCloseDetail}
        width={640}
        loading={detailLoading}
      >
        {selectedRun && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* 基本信息 */}
            <div>
              <Space>
                <Tag color={RUN_STATUS_COLOR[selectedRun.status]}>
                  {RUN_STATUS_LABEL[selectedRun.status]}
                </Tag>
                <Text type="secondary">
                  {selectedRun.total_test_cases} 用例 / {selectedRun.passed_test_cases} 通过
                </Text>
              </Space>
            </div>

            {/* 指标卡片 */}
            {runMetrics && (
              <Row gutter={16}>
                <Col span={6}>
                  <Card size="small">
                    <Statistic
                      title="综合得分"
                      value={runMetrics.overall_score}
                      precision={1}
                      suffix="%"
                      valueStyle={{ color: scoreColor(runMetrics.overall_score), fontSize: 20 }}
                      formatter={(value) => formatScore(value as number)}
                    />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic
                      title="L1 检索"
                      value={runMetrics.l1?.avg_score}
                      formatter={(value) => formatScore(value as number)}
                      valueStyle={{ color: runMetrics.l1 ? scoreColor(runMetrics.l1.avg_score) : undefined, fontSize: 20 }}
                    />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic
                      title="L2 理解"
                      value={runMetrics.l2?.avg_score}
                      formatter={(value) => formatScore(value as number)}
                      valueStyle={{ color: runMetrics.l2 ? scoreColor(runMetrics.l2.avg_score) : undefined, fontSize: 20 }}
                    />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic
                      title="L3 生成"
                      value={runMetrics.l3?.avg_score}
                      formatter={(value) => formatScore(value as number)}
                      valueStyle={{ color: runMetrics.l3 ? scoreColor(runMetrics.l3.avg_score) : undefined, fontSize: 20 }}
                    />
                  </Card>
                </Col>
              </Row>
            )}

            {/* 调优建议 */}
            {tuningSuggestions.length > 0 && (
              <div>
                <Title level={5}>调优建议</Title>
                <List
                  size="small"
                  dataSource={tuningSuggestions}
                  renderItem={(item) => {
                    const style = severityStyle(item.severity)
                    return (
                      <List.Item>
                        <List.Item.Meta
                          avatar={<span style={{ color: style.color, fontSize: 16 }}>{style.icon}</span>}
                          title={item.title}
                          description={
                            <div>
                              {item.description && (
                                <Text type="secondary">{item.description}</Text>
                              )}
                              {item.suggested_value && (
                                <div style={{ marginTop: 4 }}>
                                  <Tag color="blue">建议值: {item.suggested_value}</Tag>
                                  {item.current_value && (
                                    <Tag>当前值: {item.current_value}</Tag>
                                  )}
                                </div>
                              )}
                            </div>
                          }
                        />
                      </List.Item>
                    )
                  }}
                />
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  )
}
