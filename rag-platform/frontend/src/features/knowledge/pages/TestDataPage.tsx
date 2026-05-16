/**
 * 测试数据页
 *
 * 3 选项卡（测试用例 / 测试集 / 草稿），复用 rag-eval API
 * 通过 URL 路径推导当前激活选项卡
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
  ImportOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import type {
  TestCase,
  TestSet,
  TestCaseDraft,
  DifficultyLevel,
  DraftStatus,
} from '@/entities/rag-eval/types'
import {
  getTestCases,
  createTestCase,
  updateTestCase,
  deleteTestCase,
  batchDeleteTestCases,
  importTestCases,
  getTestSets,
  createTestSet,
  deleteTestSet,
  getDrafts,
  deleteDraft,
  generateDrafts,
  reviewDraft,
  importDraft,
} from '@/api/rag-eval/evaluation'
import { getKnowledgeBases } from '@/api/knowledge/knowledge-base'

const { Title } = Typography

/** URL 到 Tab 的映射 */
const PATH_TO_TAB: Record<string, string> = {
  cases: 'cases',
  sets: 'sets',
  drafts: 'drafts',
}

/** 难度颜色映射 */
const DIFFICULTY_COLOR: Record<DifficultyLevel, string> = {
  easy: 'green',
  medium: 'orange',
  hard: 'red',
}

/** 难度中文标签 */
const DIFFICULTY_LABEL: Record<DifficultyLevel, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

/** 来源中文标签 */
const SOURCE_LABEL: Record<string, string> = {
  manual: '手动',
  import: '导入',
  draft: '草稿导入',
}

/** 草稿状态中文标签 */
const DRAFT_STATUS_LABEL: Record<DraftStatus, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
  imported: '已导入',
}

/** 草稿状态颜色 */
const DRAFT_STATUS_COLOR: Record<DraftStatus, string> = {
  pending: 'orange',
  approved: 'green',
  rejected: 'red',
  imported: 'blue',
}

/** 忠实度分数颜色 */
function faithfulnessColor(score: number | null): string {
  if (score === null) return 'default'
  if (score > 0.8) return '#52c41a'
  if (score > 0.6) return '#faad14'
  return '#ff4d4f'
}

// ==================== 用例选项卡 ====================

/** 用例选项卡列定义 */
function buildCaseColumns(
  onEdit: (record: TestCase) => void,
  onDelete: (id: string) => void,
): ColumnsType<TestCase> {
  return [
    {
      title: '查询',
      dataIndex: 'query',
      ellipsis: true,
      width: 300,
    },
    {
      title: '来源',
      dataIndex: 'source',
      width: 100,
      render: (source: string) => (
        <Tag>{SOURCE_LABEL[source] ?? source}</Tag>
      ),
    },
    {
      title: '难度',
      dataIndex: 'difficulty_level',
      width: 80,
      render: (level: DifficultyLevel) => (
        <Tag color={DIFFICULTY_COLOR[level]}>
          {DIFFICULTY_LABEL[level]}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作',
      width: 140,
      render: (_: unknown, record: TestCase) => (
        <Space>
          <Button type="link" size="small" onClick={() => onEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确认删除该用例？" onConfirm={() => onDelete(record.id)}>
            <Button type="link" size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]
}

// ==================== 测试集选项卡 ====================

/** 测试集选项卡列定义 */
function buildSetColumns(
  onDelete: (id: string) => void,
): ColumnsType<TestSet> {
  return [
    {
      title: '名称',
      dataIndex: 'name',
      width: 200,
    },
    {
      title: '用例数',
      dataIndex: 'case_count',
      width: 80,
    },
    {
      title: '来源类型',
      dataIndex: 'source_type',
      width: 100,
      render: (v: string) => <Tag>{v}</Tag>,
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
      render: (_: unknown, record: TestSet) => (
        <Popconfirm title="确认删除该测试集？" onConfirm={() => onDelete(record.id)}>
          <Button type="link" size="small" danger>删除</Button>
        </Popconfirm>
      ),
    },
  ]
}

// ==================== 草稿选项卡 ====================

/** 草稿选项卡列定义 */
function buildDraftColumns(
  onApprove: (id: string) => void,
  onReject: (id: string) => void,
  onDelete: (id: string) => void,
): ColumnsType<TestCaseDraft> {
  return [
    {
      title: '查询',
      dataIndex: 'query',
      ellipsis: true,
      width: 260,
    },
    {
      title: '忠实度',
      dataIndex: 'faithfulness_score',
      width: 90,
      render: (score: number | null) => (
        <span style={{ color: faithfulnessColor(score), fontWeight: 600 }}>
          {score !== null ? score.toFixed(2) : '-'}
        </span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (status: DraftStatus) => (
        <Tag color={DRAFT_STATUS_COLOR[status]}>
          {DRAFT_STATUS_LABEL[status]}
        </Tag>
      ),
    },
    {
      title: '来源文档',
      dataIndex: 'source_document_id',
      width: 160,
      ellipsis: true,
      render: (v: string | null) => v ?? '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作',
      width: 180,
      render: (_: unknown, record: TestCaseDraft) => (
        <Space>
          {record.status === 'pending' && (
            <>
              <Button
                type="link"
                size="small"
                icon={<CheckOutlined />}
                onClick={() => onApprove(record.id)}
              >
                通过
              </Button>
              <Button
                type="link"
                size="small"
                danger
                icon={<CloseOutlined />}
                onClick={() => onReject(record.id)}
              >
                拒绝
              </Button>
            </>
          )}
          <Popconfirm title="确认删除该草稿？" onConfirm={() => onDelete(record.id)}>
            <Button type="link" size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]
}

// ==================== 主页面组件 ====================

export default function TestDataPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [caseForm] = Form.useForm()
  const [setForm] = Form.useForm()

  // 从 URL 推导当前 Tab
  const pathSegments = location.pathname.split('/')
  const lastSegment = pathSegments[pathSegments.length - 1]
  const activeTab = PATH_TO_TAB[lastSegment] ?? 'cases'

  // ---- 用例 Tab 状态 ----
  const [cases, setCases] = useState<TestCase[]>([])
  const [casesTotal, setCasesTotal] = useState(0)
  const [casesLoading, setCasesLoading] = useState(false)
  const [casesPage, setCasesPage] = useState(1)
  const [casesSearch, setCasesSearch] = useState('')
  const [casesSourceFilter, setCasesSourceFilter] = useState<string | undefined>(undefined)
  const [casesDifficultyFilter, setCasesDifficultyFilter] = useState<DifficultyLevel | undefined>(undefined)
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
  const [caseModalOpen, setCaseModalOpen] = useState(false)
  const [editingCase, setEditingCase] = useState<TestCase | null>(null)
  const [caseSubmitting, setCaseSubmitting] = useState(false)
  const [jsonImportModalOpen, setJsonImportModalOpen] = useState(false)

  // ---- 测试集 Tab 状态 ----
  const [sets, setSets] = useState<TestSet[]>([])
  const [setsTotal, setSetsTotal] = useState(0)
  const [setsLoading, setSetsLoading] = useState(false)
  const [setsPage, setSetsPage] = useState(1)
  const [setModalOpen, setSetModalOpen] = useState(false)
  const [setSubmitting, setSetSubmitting] = useState(false)

  // ---- 草稿 Tab 状态 ----
  const [drafts, setDrafts] = useState<TestCaseDraft[]>([])
  const [draftsTotal, setDraftsTotal] = useState(0)
  const [draftsLoading, setDraftsLoading] = useState(false)
  const [draftsPage, setDraftsPage] = useState(1)
  const [draftsSearch, setDraftsSearch] = useState('')
  const [draftsStatusFilter, setDraftsStatusFilter] = useState<DraftStatus | undefined>(undefined)
  const [generateModalOpen, setGenerateModalOpen] = useState(false)
  const [generateForm] = Form.useForm()
  const [knowledgeBases, setKnowledgeBases] = useState<Array<{ id: string; name: string }>>([])

  // ==================== 用例加载 ====================

  const loadCases = useCallback(async () => {
    setCasesLoading(true)
    try {
      const result = await getTestCases({
        page: casesPage,
        page_size: 20,
        search: casesSearch || undefined,
        source: casesSourceFilter,
        difficulty: casesDifficultyFilter,
      })
      setCases(result.items ?? [])
      setCasesTotal(result.total ?? 0)
    } catch {
      message.error('加载测试用例失败')
    } finally {
      setCasesLoading(false)
    }
  }, [casesPage, casesSearch, casesSourceFilter, casesDifficultyFilter])

  useEffect(() => {
    if (activeTab === 'cases') {
      loadCases()
    }
  }, [activeTab, loadCases])

  // ==================== 测试集加载 ====================

  const loadSets = useCallback(async () => {
    setSetsLoading(true)
    try {
      const result = await getTestSets({ page: setsPage, page_size: 20 })
      setSets(result.items ?? [])
      setSetsTotal(result.total ?? 0)
    } catch {
      message.error('加载测试集失败')
    } finally {
      setSetsLoading(false)
    }
  }, [setsPage])

  useEffect(() => {
    if (activeTab === 'sets') {
      loadSets()
    }
  }, [activeTab, loadSets])

  // ==================== 草稿加载 ====================

  const loadDrafts = useCallback(async () => {
    setDraftsLoading(true)
    try {
      const result = await getDrafts({
        page: draftsPage,
        page_size: 20,
        search: draftsSearch || undefined,
        status: draftsStatusFilter,
      })
      setDrafts(result.items ?? [])
      setDraftsTotal(result.total ?? 0)
    } catch {
      message.error('加载草稿失败')
    } finally {
      setDraftsLoading(false)
    }
  }, [draftsPage, draftsSearch, draftsStatusFilter])

  useEffect(() => {
    if (activeTab === 'drafts') {
      loadDrafts()
    }
  }, [activeTab, loadDrafts])

  // ==================== 知识库列表（草稿生成用） ====================

  useEffect(() => {
    if (activeTab === 'drafts' && knowledgeBases.length === 0) {
      getKnowledgeBases({ page: 1, page_size: 100 })
        .then((result) => {
          const list = (result.items ?? []).map((kb) => ({ id: kb.id, name: kb.name }))
          setKnowledgeBases(list)
        })
        .catch(() => {
          // 静默失败，不影响主流程
        })
    }
  }, [activeTab, knowledgeBases.length])

  // ==================== 用例操作 ====================

  /** 打开新建/编辑用例弹窗 */
  function handleOpenCaseModal(record?: TestCase) {
    if (record) {
      setEditingCase(record)
      caseForm.setFieldsValue({
        query: record.query,
        description: record.description ?? '',
        difficulty_level: record.difficulty_level,
        expected_knowledge_ids: record.expected_knowledge_ids ?? [],
        expected_keywords: record.expected_keywords ?? [],
      })
    } else {
      setEditingCase(null)
      caseForm.resetFields()
    }
    setCaseModalOpen(true)
  }

  /** 提交用例表单 */
  async function handleCaseSubmit() {
    try {
      const values = await caseForm.validateFields()
      setCaseSubmitting(true)

      if (editingCase) {
        await updateTestCase(editingCase.id, values)
        message.success('用例已更新')
      } else {
        await createTestCase(values)
        message.success('用例已创建')
      }

      setCaseModalOpen(false)
      loadCases()
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    } finally {
      setCaseSubmitting(false)
    }
  }

  /** 删除用例 */
  async function handleDeleteCase(caseId: string) {
    try {
      await deleteTestCase(caseId)
      message.success('用例已删除')
      loadCases()
    } catch {
      message.error('删除失败')
    }
  }

  /** 批量删除用例 */
  async function handleBatchDeleteCases() {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要删除的用例')
      return
    }
    try {
      await batchDeleteTestCases(selectedRowKeys)
      message.success(`已删除 ${selectedRowKeys.length} 条用例`)
      setSelectedRowKeys([])
      loadCases()
    } catch {
      message.error('批量删除失败')
    }
  }

  /** JSON 导入 */
  async function handleJsonImport() {
    // 从剪贴板读取 JSON 数据作为简单实现
    try {
      const text = await navigator.clipboard.readText()
      const parsed = JSON.parse(text)
      const casesData = Array.isArray(parsed) ? parsed : [parsed]
      await importTestCases(casesData)
      message.success(`成功导入 ${casesData.length} 条用例`)
      setJsonImportModalOpen(false)
      loadCases()
    } catch {
      message.error('导入失败，请确认剪贴板包含有效 JSON 数据')
    }
  }

  // ==================== 测试集操作 ====================

  /** 提交测试集表单 */
  async function handleSetSubmit() {
    try {
      const values = await setForm.validateFields()
      setSetSubmitting(true)
      await createTestSet(values)
      message.success('测试集已创建')
      setSetModalOpen(false)
      setForm.resetFields()
      loadSets()
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message)
      }
    } finally {
      setSetSubmitting(false)
    }
  }

  /** 删除测试集 */
  async function handleDeleteSet(setId: string) {
    try {
      await deleteTestSet(setId)
      message.success('测试集已删除')
      loadSets()
    } catch {
      message.error('删除失败')
    }
  }

  // ==================== 草稿操作 ====================

  /** 通过审核 → 导入为正式用例 */
  async function handleApproveDraft(draftId: string) {
    try {
      await reviewDraft(draftId, 'approve')
      await importDraft(draftId)
      message.success('草稿已导入为用例')
      loadDrafts()
    } catch {
      message.error('导入失败')
    }
  }

  /** 拒绝草稿 */
  async function handleRejectDraft(draftId: string) {
    try {
      await reviewDraft(draftId, 'reject')
      message.success('草稿已拒绝')
      loadDrafts()
    } catch {
      message.error('操作失败')
    }
  }

  /** 删除草稿 */
  async function handleDeleteDraft(draftId: string) {
    try {
      await deleteDraft(draftId)
      message.success('草稿已删除')
      loadDrafts()
    } catch {
      message.error('删除失败')
    }
  }

  /** 生成草稿 */
  async function handleGenerateDrafts() {
    try {
      const values = await generateForm.validateFields()
      await generateDrafts({
        kb_id: values.kb_id,
        document_ids: [],
        max_qa_per_chunk: 3,
      })
      message.success('草稿生成任务已提交')
      setGenerateModalOpen(false)
      generateForm.resetFields()
      loadDrafts()
    } catch {
      message.error('生成失败')
    }
  }

  // ==================== Tab 切换 ====================

  function handleTabChange(key: string) {
    navigate(`/knowledge/test-data/${key}`, { replace: true })
  }

  // ==================== 列定义 ====================

  const caseColumns = buildCaseColumns(
    (record) => handleOpenCaseModal(record),
    (id) => handleDeleteCase(id),
  )

  const setColumns = buildSetColumns(
    (id) => handleDeleteSet(id),
  )

  const draftColumns = buildDraftColumns(
    (id) => handleApproveDraft(id),
    (id) => handleRejectDraft(id),
    (id) => handleDeleteDraft(id),
  )

  // ==================== 渲染 ====================

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginBottom: 16 }}>测试数据</Title>

      <Tabs
        activeKey={activeTab}
        onChange={handleTabChange}
        items={[
          // ---- 用例 Tab ----
          {
            key: 'cases',
            label: '测试用例',
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <Space wrap>
                  <Input.Search
                    placeholder="搜索用例"
                    style={{ width: 200 }}
                    allowClear
                    onSearch={(val) => { setCasesSearch(val); setCasesPage(1) }}
                  />
                  <Select
                    placeholder="来源"
                    style={{ width: 120 }}
                    allowClear
                    value={casesSourceFilter}
                    onChange={(val) => { setCasesSourceFilter(val); setCasesPage(1) }}
                    options={[
                      { value: 'manual', label: '手动' },
                      { value: 'import', label: '导入' },
                      { value: 'draft', label: '草稿导入' },
                    ]}
                  />
                  <Select
                    placeholder="难度"
                    style={{ width: 120 }}
                    allowClear
                    value={casesDifficultyFilter}
                    onChange={(val) => { setCasesDifficultyFilter(val); setCasesPage(1) }}
                    options={Object.entries(DIFFICULTY_LABEL).map(([value, label]) => ({
                      value,
                      label,
                    }))}
                  />
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenCaseModal()}>
                    新建用例
                  </Button>
                  <Button icon={<ImportOutlined />} onClick={() => setJsonImportModalOpen(true)}>
                    JSON 导入
                  </Button>
                  <Popconfirm
                    title={`确认删除选中的 ${selectedRowKeys.length} 条用例？`}
                    onConfirm={handleBatchDeleteCases}
                    disabled={selectedRowKeys.length === 0}
                  >
                    <Button danger icon={<DeleteOutlined />} disabled={selectedRowKeys.length === 0}>
                      批量删除
                    </Button>
                  </Popconfirm>
                </Space>

                <Table<TestCase>
                  rowKey="id"
                  columns={caseColumns}
                  dataSource={cases}
                  loading={casesLoading}
                  rowSelection={{
                    selectedRowKeys,
                    onChange: (keys) => setSelectedRowKeys(keys as string[]),
                  }}
                  pagination={{
                    current: casesPage,
                    total: casesTotal,
                    pageSize: 20,
                    showTotal: (total) => `共 ${total} 条`,
                    onChange: (page) => setCasesPage(page),
                  }}
                />
              </div>
            ),
          },

          // ---- 测试集 Tab ----
          {
            key: 'sets',
            label: '测试集',
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <Space>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setSetModalOpen(true)}>
                    新建测试集
                  </Button>
                </Space>

                <Table<TestSet>
                  rowKey="id"
                  columns={setColumns}
                  dataSource={sets}
                  loading={setsLoading}
                  pagination={{
                    current: setsPage,
                    total: setsTotal,
                    pageSize: 20,
                    showTotal: (total) => `共 ${total} 条`,
                    onChange: (page) => setSetsPage(page),
                  }}
                />
              </div>
            ),
          },

          // ---- 草稿 Tab ----
          {
            key: 'drafts',
            label: '草稿',
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <Space wrap>
                  <Input.Search
                    placeholder="搜索草稿"
                    style={{ width: 200 }}
                    allowClear
                    onSearch={(val) => { setDraftsSearch(val); setDraftsPage(1) }}
                  />
                  <Select
                    placeholder="状态"
                    style={{ width: 120 }}
                    allowClear
                    value={draftsStatusFilter}
                    onChange={(val) => { setDraftsStatusFilter(val); setDraftsPage(1) }}
                    options={Object.entries(DRAFT_STATUS_LABEL).map(([value, label]) => ({
                      value,
                      label,
                    }))}
                  />
                  <Button
                    type="primary"
                    icon={<ThunderboltOutlined />}
                    onClick={() => setGenerateModalOpen(true)}
                  >
                    生成草稿
                  </Button>
                </Space>

                <Table<TestCaseDraft>
                  rowKey="id"
                  columns={draftColumns}
                  dataSource={drafts}
                  loading={draftsLoading}
                  pagination={{
                    current: draftsPage,
                    total: draftsTotal,
                    pageSize: 20,
                    showTotal: (total) => `共 ${total} 条`,
                    onChange: (page) => setDraftsPage(page),
                  }}
                />
              </div>
            ),
          },
        ]}
      />

      {/* ---- 新建/编辑用例弹窗 ---- */}
      <Modal
        title={editingCase ? '编辑用例' : '新建用例'}
        open={caseModalOpen}
        onOk={handleCaseSubmit}
        onCancel={() => setCaseModalOpen(false)}
        confirmLoading={caseSubmitting}
        width={560}
      >
        <Form form={caseForm} layout="vertical" autoComplete="off">
          <Form.Item name="query" label="查询" rules={[{ required: true, message: '请输入查询内容' }]}>
            <Input.TextArea rows={2} placeholder="输入测试查询语句" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="可选描述" />
          </Form.Item>
          <Form.Item name="difficulty_level" label="难度">
            <Select
              placeholder="选择难度"
              options={Object.entries(DIFFICULTY_LABEL).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
          <Form.Item name="expected_knowledge_ids" label="期望知识 ID">
            <Select mode="tags" placeholder="输入知识 ID 后回车添加" />
          </Form.Item>
          <Form.Item name="expected_keywords" label="期望关键词">
            <Select mode="tags" placeholder="输入关键词后回车添加" />
          </Form.Item>
        </Form>
      </Modal>

      {/* ---- JSON 导入弹窗 ---- */}
      <Modal
        title="JSON 导入"
        open={jsonImportModalOpen}
        onOk={handleJsonImport}
        onCancel={() => setJsonImportModalOpen(false)}
        okText="从剪贴板导入"
      >
        <Typography.Paragraph type="secondary">
          请先将 JSON 数据复制到剪贴板，然后点击导入。支持单条或数组格式。
        </Typography.Paragraph>
      </Modal>

      {/* ---- 新建测试集弹窗 ---- */}
      <Modal
        title="新建测试集"
        open={setModalOpen}
        onOk={handleSetSubmit}
        onCancel={() => setSetModalOpen(false)}
        confirmLoading={setSubmitting}
      >
        <Form form={setForm} layout="vertical" autoComplete="off">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入测试集名称' }]}>
            <Input placeholder="测试集名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="可选描述" />
          </Form.Item>
        </Form>
      </Modal>

      {/* ---- 生成草稿弹窗 ---- */}
      <Modal
        title="生成草稿"
        open={generateModalOpen}
        onOk={handleGenerateDrafts}
        onCancel={() => setGenerateModalOpen(false)}
        okText="开始生成"
      >
        <Form form={generateForm} layout="vertical" autoComplete="off">
          <Form.Item
            name="kb_id"
            label="知识库"
            rules={[{ required: true, message: '请选择知识库' }]}
          >
            <Select
              placeholder="选择知识库"
              options={knowledgeBases.map((kb) => ({
                value: kb.id,
                label: kb.name,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
