/**
 * 知识库列表页
 *
 * 卡片网格视图展示当前租户所有知识库，支持搜索、筛选、新建
 */
import { useEffect, useCallback, useState } from 'react'
import {
  Button,
  Input,
  Select,
  Row,
  Col,
  Skeleton,
  Alert,
  Modal,
  Form,
  Radio,
  message,
  Typography,
} from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useKnowledgeBaseStore } from '@/features/knowledge/stores/knowledgeBaseStore'
import KnowledgeBaseCard from '../components/KnowledgeBaseCard'
import { getEmbeddingModels } from '@/api/knowledge/knowledge-base'
import type { VectorBackend, KnowledgeBaseVisibility, ChunkType } from '@/entities/knowledge/types'

const { Title } = Typography

/** 新建知识库表单值 */
interface CreateFormValues {
  name: string
  description?: string
  vector_backend: VectorBackend
  visibility: KnowledgeBaseVisibility
  visible_roles?: string[]
  chunk_type: ChunkType
  embedding_model?: string
}

export default function KnowledgeListPage() {
  const navigate = useNavigate()
  const knowledgeBases = useKnowledgeBaseStore((s) => s.knowledgeBases)
  const loading = useKnowledgeBaseStore((s) => s.loading)
  const error = useKnowledgeBaseStore((s) => s.error)
  const searchQuery = useKnowledgeBaseStore((s) => s.searchQuery)
  const backendFilter = useKnowledgeBaseStore((s) => s.backendFilter)
  const statusFilter = useKnowledgeBaseStore((s) => s.statusFilter)
  const visibilityFilter = useKnowledgeBaseStore((s) => s.visibilityFilter)
  const loadKnowledgeBases = useKnowledgeBaseStore((s) => s.loadKnowledgeBases)
  const setSearchQuery = useKnowledgeBaseStore((s) => s.setSearchQuery)
  const setBackendFilter = useKnowledgeBaseStore((s) => s.setBackendFilter)
  const setStatusFilter = useKnowledgeBaseStore((s) => s.setStatusFilter)
  const setVisibilityFilter = useKnowledgeBaseStore((s) => s.setVisibilityFilter)
  const deleteKnowledgeBase = useKnowledgeBaseStore((s) => s.deleteKnowledgeBase)
  const createKnowledgeBase = useKnowledgeBaseStore((s) => s.createKnowledgeBase)

  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form] = Form.useForm<CreateFormValues>()
  const [embeddingModels, setEmbeddingModels] = useState<Array<{ model: string; provider: string }>>([])

  // 加载列表
  useEffect(() => {
    loadKnowledgeBases()
  }, [loadKnowledgeBases])

  // 加载 Embedding 模型列表
  useEffect(() => {
    getEmbeddingModels().then(setEmbeddingModels).catch(() => {})
  }, [])

  /** 搜索防抖 */
  const handleSearch = useCallback(
    (value: string) => {
      setSearchQuery(value)
    },
    [setSearchQuery]
  )

  /** 创建知识库 */
  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      setCreating(true)
      const detail = await createKnowledgeBase({
        name: values.name,
        description: values.description,
        vector_backend: values.vector_backend,
        visibility: values.visibility,
        visible_roles: values.visible_roles,
        chunk_strategy: {
          type: values.chunk_type,
          chunk_size: 512,
          overlap: 50,
          separator: '\n\n',
          min_chunk_size: 100,
          max_chunk_size: 4096,
        },
        embedding_config: values.embedding_model
          ? {
              model: values.embedding_model,
              provider: embeddingModels.find((m) => m.model === values.embedding_model)?.provider ?? 'dashscope',
              dimension: 1024,
              batch_size: 64,
              similarity_metric: 'cosine',
            }
          : undefined,
      })
      setCreateOpen(false)
      form.resetFields()
      message.success('知识库创建成功')
      navigate(`/knowledge/${detail.id}`)
    } catch {
      // 表单校验失败
    } finally {
      setCreating(false)
    }
  }

  /** 删除知识库（带管道引用检查） */
  const handleDelete = async (id: string) => {
    try {
      await deleteKnowledgeBase(id)
      message.success('已删除')
    } catch {
      message.error('删除失败，可能有管道正在引用此知识库')
    }
  }

  /** 重命名知识库 */
  const handleRename = (id: string) => {
    const kb = knowledgeBases.find((k) => k.id === id)
    if (!kb) return
    // 简单的 prompt 重命名（生产环境应使用 Modal）
    Modal.confirm({
      title: '重命名知识库',
      content: (
        <Input
          id="rename-input"
          defaultValue={kb.name}
          maxLength={64}
        />
      ),
      onOk: async () => {
        const input = document.getElementById('rename-input') as HTMLInputElement
        if (input?.value.trim()) {
          // 通过 API 更新
          const { updateKnowledgeBase } = await import('@/api/knowledge/knowledge-base')
          await updateKnowledgeBase(id, { name: input.value.trim() })
          loadKnowledgeBases()
          message.success('已重命名')
        }
      },
    })
  }

  return (
    <div style={{ padding: 24 }}>
      {/* 顶部标题 + 新建按钮 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>知识库</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          创建知识库
        </Button>
      </div>

      {/* 搜索/筛选栏 */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <Input
          placeholder="搜索知识库名称"
          prefix={<SearchOutlined />}
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          style={{ width: 240 }}
          allowClear
        />
        <Select
          value={backendFilter}
          onChange={setBackendFilter}
          style={{ width: 140 }}
          options={[
            { value: 'all', label: '全部后端' },
            { value: 'chroma', label: 'Chroma' },
            { value: 'elasticsearch', label: 'Elasticsearch' },
            { value: 'milvus', label: 'Milvus' },
          ]}
        />
        <Select
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 120 }}
          options={[
            { value: 'all', label: '全部状态' },
            { value: 'ready', label: '就绪' },
            { value: 'rebuilding', label: '重建中' },
            { value: 'indexing', label: '索引中' },
            { value: 'error', label: '异常' },
          ]}
        />
        <Select
          value={visibilityFilter}
          onChange={setVisibilityFilter}
          style={{ width: 120 }}
          options={[
            { value: 'all', label: '全部可见性' },
            { value: 'public', label: '公开' },
            { value: 'role_scoped', label: '角色可见' },
            { value: 'private', label: '私有' },
          ]}
        />
      </div>

      {/* 内容区域 */}
      {loading ? (
        <Row gutter={[16, 16]}>
          {Array.from({ length: 6 }).map((_, i) => (
            <Col key={i} xs={24} sm={12} lg={8}>
              <Skeleton active paragraph={{ rows: 4 }} />
            </Col>
          ))}
        </Row>
      ) : error ? (
        <Alert
          type="error"
          message="加载失败"
          description={error}
          action={<Button onClick={loadKnowledgeBases}>重试</Button>}
          showIcon
        />
      ) : knowledgeBases.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Typography.Text type="secondary" style={{ fontSize: 16 }}>
            暂无知识库，点击创建第一个
          </Typography.Text>
          <div style={{ marginTop: 16 }}>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              创建知识库
            </Button>
          </div>
        </div>
      ) : (
        <Row gutter={[16, 16]}>
          {knowledgeBases.map((kb) => (
            <Col key={kb.id} xs={24} sm={12} lg={8}>
              <KnowledgeBaseCard
                item={kb}
                onDelete={handleDelete}
                onRename={handleRename}
              />
            </Col>
          ))}
        </Row>
      )}

      {/* 新建知识库 Modal */}
      <Modal
        title="创建知识库"
        open={createOpen}
        onCancel={() => {
          setCreateOpen(false)
          form.resetFields()
        }}
        onOk={handleCreate}
        confirmLoading={creating}
        width={520}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            vector_backend: 'chroma',
            visibility: 'public',
            chunk_type: 'fixed_size',
          }}
        >
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input maxLength={64} showCount placeholder="知识库名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea maxLength={512} showCount rows={2} placeholder="可选描述" />
          </Form.Item>
          <Form.Item name="vector_backend" label="向量后端">
            <Radio.Group optionType="button" buttonStyle="solid">
              <Radio.Button value="chroma">Chroma</Radio.Button>
              <Radio.Button value="elasticsearch">Elasticsearch</Radio.Button>
              <Radio.Button value="milvus">Milvus</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="visibility" label="可见性">
            <Radio.Group optionType="button" buttonStyle="solid">
              <Radio.Button value="public">公开</Radio.Button>
              <Radio.Button value="role_scoped">角色可见</Radio.Button>
              <Radio.Button value="private">私有</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="chunk_type" label="分块策略">
            <Select
              options={[
                { value: 'fixed_size', label: '固定大小' },
                { value: 'semantic', label: '语义分块' },
                { value: 'paragraph', label: '按段落' },
                { value: 'heading', label: '按标题层级' },
                { value: 'recursive', label: '递归分块' },
              ]}
            />
          </Form.Item>
          <Form.Item name="embedding_model" label="Embedding 模型">
            <Select
              allowClear
              placeholder="选择模型（可选）"
              options={embeddingModels.map((m) => ({
                value: m.model,
                label: `${m.model} (${m.provider})`,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
