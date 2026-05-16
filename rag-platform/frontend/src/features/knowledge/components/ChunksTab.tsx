/**
 * 分块 & 向量 Tab 组件
 *
 * 包含分块策略配置、Embedding 配置、后端迁移、分块预览、重建历史
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Card,
  Select,
  InputNumber,
  Slider,
  Button,
  Alert,
  Space,
  Typography,
  Tag,
  Progress,
  Timeline,
  message,
} from 'antd'
import {
  SaveOutlined,
  EyeOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import { useKnowledgeBaseStore } from '@/features/knowledge/stores/knowledgeBaseStore'
import { useRebuildProgress } from '@/features/knowledge/hooks/useRebuildProgress'
import { getEmbeddingModels, getDocuments } from '@/api/knowledge/knowledge-base'
import ChunkPreviewDrawer from './ChunkPreviewDrawer'
import BackendMigrationModal from './BackendMigrationModal'
import type {
  ChunkType,
  ChunkStrategyConfig,
  EmbeddingConfig,
  VectorBackend,
  KBDocument,
} from '@/entities/knowledge/types'

const { Text } = Typography

/** 分块方式标签映射 */
const CHUNK_TYPE_LABELS: Record<ChunkType, string> = {
  fixed_size: '固定大小',
  semantic: '语义分块',
  paragraph: '按段落',
  heading: '按标题层级',
  recursive: '递归分块',
}

/** 默认分块策略 */
const DEFAULT_STRATEGY: ChunkStrategyConfig = {
  type: 'fixed_size',
  chunk_size: 512,
  overlap: 50,
  separator: '\n\n',
  min_chunk_size: 100,
  max_chunk_size: 4096,
}

export interface ChunksTabProps {
  kbId: string
}

export default function ChunksTab({ kbId }: ChunksTabProps) {
  const currentKB = useKnowledgeBaseStore((s) => s.currentKB)
  const configDirty = useKnowledgeBaseStore((s) => s.configDirty)
  const updateChunkStrategy = useKnowledgeBaseStore((s) => s.updateChunkStrategy)
  const updateEmbeddingConfig = useKnowledgeBaseStore((s) => s.updateEmbeddingConfig)
  const setConfigDirty = useKnowledgeBaseStore((s) => s.setConfigDirty)
  const previewChunks = useKnowledgeBaseStore((s) => s.previewChunks)

  const { rebuildStatus, recentRebuildTasks, isRebuilding, startSubscription } = useRebuildProgress(kbId)

  // 分块策略本地状态
  const [strategy, setStrategy] = useState<ChunkStrategyConfig>(
    currentKB?.chunk_strategy ?? DEFAULT_STRATEGY
  )
  // Embedding 本地状态
  const [embedding, setEmbedding] = useState<EmbeddingConfig | null>(
    currentKB?.embedding_config ?? null
  )
  // 选项数据
  const [embeddingModels, setEmbeddingModels] = useState<Array<{ model: string; provider: string; dimension: number }>>([])
  const [documents, setDocuments] = useState<KBDocument[]>([])
  // UI 状态
  const [previewDocId, setPreviewDocId] = useState<string | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [migrationTarget, setMigrationTarget] = useState<VectorBackend | null>(null)
  const [saving, setSaving] = useState(false)

  // 初始化配置
  useEffect(() => {
    if (currentKB?.chunk_strategy) {
      setStrategy(currentKB.chunk_strategy)
    }
    if (currentKB?.embedding_config) {
      setEmbedding(currentKB.embedding_config)
    }
  }, [currentKB])

  // 加载 Embedding 模型列表
  useEffect(() => {
    getEmbeddingModels().then(setEmbeddingModels).catch(() => {})
  }, [])

  // 加载已解析文档列表（用于预览选择）
  const loadParsedDocuments = useCallback(async () => {
    try {
      const result = await getDocuments(kbId, {
        page: 1,
        page_size: 200,
        parse_status: 'parsed',
      })
      setDocuments(result.items)
    } catch { /* 忽略 */ }
  }, [kbId])

  useEffect(() => {
    loadParsedDocuments()
  }, [loadParsedDocuments])

  /** 保存分块策略 */
  const handleSaveStrategy = async () => {
    setSaving(true)
    try {
      await updateChunkStrategy(kbId, strategy)
      startSubscription()
      message.success('分块策略已保存，重建任务已触发')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  /** 保存 Embedding 配置 */
  const handleSaveEmbedding = async () => {
    if (!embedding) return
    setSaving(true)
    try {
      await updateEmbeddingConfig(kbId, embedding)
      startSubscription()
      message.success('Embedding 配置已保存，重建任务已触发')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  /** 预览分块 */
  const handlePreview = (docId: string) => {
    setPreviewDocId(docId)
    setPreviewOpen(true)
    previewChunks(kbId, docId)
  }

  const currentBackend = currentKB?.vector_backend ?? 'chroma'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 重建进度 */}
      {isRebuilding && rebuildStatus && (
        <Card size="small">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text strong>重建进行中</Text>
            <Progress percent={rebuildStatus.progress_pct} status="active" />
            {rebuildStatus.progress_message && (
              <Text type="secondary">{rebuildStatus.progress_message}</Text>
            )}
          </Space>
        </Card>
      )}

      {/* ── 分块策略配置 ── */}
      <Card title="分块策略" size="small">
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {/* 分块方式选择 */}
          <div>
            <Text>分块方式</Text>
            <Select
              value={strategy.type}
              onChange={(type) => {
                setStrategy((s) => ({ ...s, type }))
                setConfigDirty(true)
              }}
              style={{ width: '100%', marginTop: 4 }}
              options={Object.entries(CHUNK_TYPE_LABELS).map(([k, v]) => ({ value: k, label: v }))}
            />
          </div>

          {/* 动态参数表单 */}
          {(strategy.type === 'fixed_size' || strategy.type === 'recursive') && (
            <>
              <div>
                <Text>分块大小（字符数）</Text>
                <InputNumber
                  min={128}
                  max={4096}
                  value={strategy.chunk_size}
                  onChange={(v) => {
                    setStrategy((s) => ({ ...s, chunk_size: v ?? 512 }))
                    setConfigDirty(true)
                  }}
                  style={{ width: '100%', marginTop: 4 }}
                />
              </div>
              <div>
                <Text>重叠大小（字符数）</Text>
                <Slider
                  min={0}
                  max={Math.floor((strategy.chunk_size ?? 512) / 2)}
                  value={strategy.overlap}
                  onChange={(v) => {
                    setStrategy((s) => ({ ...s, overlap: v }))
                    setConfigDirty(true)
                  }}
                />
              </div>
            </>
          )}

          {strategy.type === 'semantic' && (
            <>
              <div>
                <Text>相似度阈值</Text>
                <Slider
                  min={50}
                  max={95}
                  value={85}
                  marks={{ 50: '0.5', 95: '0.95' }}
                  onChange={() => setConfigDirty(true)}
                />
              </div>
            </>
          )}

          {/* 通用参数 */}
          <div>
            <Text>最小分块大小</Text>
            <InputNumber
              min={50}
              value={strategy.min_chunk_size}
              onChange={(v) => {
                setStrategy((s) => ({ ...s, min_chunk_size: v ?? 100 }))
                setConfigDirty(true)
              }}
              style={{ width: '100%', marginTop: 4 }}
            />
          </div>
          <div>
            <Text>最大分块大小</Text>
            <InputNumber
              min={256}
              max={8192}
              value={strategy.max_chunk_size}
              onChange={(v) => {
                setStrategy((s) => ({ ...s, max_chunk_size: v ?? 4096 }))
                setConfigDirty(true)
              }}
              style={{ width: '100%', marginTop: 4 }}
            />
          </div>

          {/* 变更警告 */}
          {configDirty && (
            <Alert
              type="warning"
              message="保存后将触发全量索引重建，预计需要数分钟。重建期间知识库可正常读取。"
              showIcon
            />
          )}

          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            disabled={!configDirty}
            onClick={handleSaveStrategy}
          >
            保存分块策略
          </Button>
        </Space>
      </Card>

      {/* ── Embedding 配置 ── */}
      <Card title="Embedding 配置" size="small">
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <div>
            <Text>Embedding 模型</Text>
            <Select
              value={embedding?.model}
              onChange={(model) => {
                const selected = embeddingModels.find((m) => m.model === model)
                setEmbedding((e) => ({
                  ...e!,
                  model,
                  provider: selected?.provider ?? e?.provider ?? 'dashscope',
                  dimension: selected?.dimension ?? e?.dimension ?? 1024,
                }))
                setConfigDirty(true)
              }}
              style={{ width: '100%', marginTop: 4 }}
              options={embeddingModels.map((m) => ({ value: m.model, label: `${m.model} (${m.provider})` }))}
            />
          </div>
          <div>
            <Text>向量维度</Text>
            <InputNumber
              min={64}
              max={4096}
              value={embedding?.dimension}
              onChange={(v) => {
                setEmbedding((e) => e ? { ...e, dimension: v ?? 1024 } : e)
                setConfigDirty(true)
              }}
              style={{ width: '100%', marginTop: 4 }}
            />
          </div>
          <div>
            <Text>批量大小</Text>
            <Select
              value={embedding?.batch_size ?? 64}
              onChange={(v) => {
                setEmbedding((e) => e ? { ...e, batch_size: v } : e)
                setConfigDirty(true)
              }}
              style={{ width: '100%', marginTop: 4 }}
              options={[16, 32, 64, 128].map((v) => ({ value: v, label: String(v) }))}
            />
          </div>
          <div>
            <Text>相似度度量</Text>
            <Select
              value={embedding?.similarity_metric ?? 'cosine'}
              onChange={(v) => {
                setEmbedding((e) => e ? { ...e, similarity_metric: v } : e)
                setConfigDirty(true)
              }}
              style={{ width: '100%', marginTop: 4 }}
              options={[
                { value: 'cosine', label: 'Cosine' },
                { value: 'euclidean', label: 'Euclidean' },
                { value: 'dot_product', label: 'Dot Product' },
              ]}
            />
          </div>

          {configDirty && (
            <Alert
              type="warning"
              message="Embedding 配置已修改，保存后将触发全量索引重建。"
              showIcon
            />
          )}

          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            disabled={!configDirty}
            onClick={handleSaveEmbedding}
          >
            保存 Embedding 配置
          </Button>
        </Space>
      </Card>

      {/* ── 向量后端迁移 ── */}
      <Card title="向量后端" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>
            当前后端：<Tag color={currentBackend === 'chroma' ? 'cyan' : currentBackend === 'elasticsearch' ? 'gold' : 'blue'}>{currentBackend}</Tag>
          </Text>
          <Space>
            {(['elasticsearch', 'milvus', 'chroma'] as VectorBackend[]).map((backend) =>
              backend === currentBackend ? null : (
                <Button
                  key={backend}
                  icon={<SwapOutlined />}
                  onClick={() => setMigrationTarget(backend)}
                  disabled={isRebuilding}
                >
                  迁移到 {backend === 'elasticsearch' ? 'Elasticsearch' : backend === 'milvus' ? 'Milvus' : 'Chroma'}
                </Button>
              )
            )}
          </Space>
        </Space>
      </Card>

      {/* ── 分块预览 ── */}
      <Card title="分块预览" size="small">
        <Space>
          <Select
            placeholder="选择要预览的文档..."
            showSearch
            style={{ width: 300 }}
            value={previewDocId ?? undefined}
            onChange={handlePreview}
            options={documents.map((d) => ({ value: d.id, label: d.filename }))}
            filterOption={(input, option) =>
              (option?.label as string)?.toLowerCase().includes(input.toLowerCase()) ?? false
            }
          />
          <Button
            icon={<EyeOutlined />}
            disabled={!previewDocId}
            onClick={() => previewDocId && handlePreview(previewDocId)}
          >
            预览分块结果
          </Button>
        </Space>
      </Card>

      {/* ── 重建历史 ── */}
      {recentRebuildTasks.length > 0 && (
        <Card title="重建历史" size="small">
          <Timeline
            items={recentRebuildTasks.slice(0, 5).map((task) => ({
              color: task.status === 'completed' ? 'green' : task.status === 'running' ? 'blue' : 'red',
              children: (
                <div>
                  <Text strong>
                    {task.trigger === 'chunk_change' ? '分块变更' : task.trigger === 'embedding_change' ? 'Embedding变更' : '后端迁移'}
                  </Text>
                  <Tag color={task.status === 'completed' ? 'success' : task.status === 'running' ? 'processing' : 'error'}>
                    {task.status === 'completed' ? '已完成' : task.status === 'running' ? '运行中' : '失败'}
                  </Tag>
                  {task.status === 'running' && <Progress percent={task.progress_pct} size="small" />}
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {new Date(task.started_at).toLocaleString('zh-CN')}
                  </Text>
                </div>
              ),
            }))}
          />
        </Card>
      )}

      {/* 分块预览抽屉 */}
      <ChunkPreviewDrawer open={previewOpen} onClose={() => setPreviewOpen(false)} />

      {/* 迁移 Modal */}
      {migrationTarget && (
        <BackendMigrationModal
          open
          onClose={() => setMigrationTarget(null)}
          kbId={kbId}
          kbName={currentKB?.name ?? ''}
          currentBackend={currentBackend}
          targetBackend={migrationTarget}
          onSuccess={() => {
            setMigrationTarget(null)
            useKnowledgeBaseStore.getState().loadKnowledgeBase(kbId)
          }}
        />
      )}
    </div>
  )
}
