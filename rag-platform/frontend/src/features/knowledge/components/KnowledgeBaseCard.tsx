/**
 * 知识库卡片组件
 *
 * 在列表页展示知识库摘要信息，支持操作菜单
 */
import { useCallback } from 'react'
import { Card, Tag, Dropdown, Typography, Space } from 'antd'
import {
  DatabaseOutlined,
  LockOutlined,
  GlobalOutlined,
  TeamOutlined,
  MoreOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { KnowledgeBaseListItem, VectorBackend } from '@/entities/knowledge/types'

const { Text, Paragraph } = Typography

/** 向量后端颜色映射 */
const BACKEND_COLORS: Record<VectorBackend, string> = {
  chroma: 'cyan',
  elasticsearch: 'gold',
  milvus: 'blue',
}

/** 向量后端显示名 */
const BACKEND_LABELS: Record<VectorBackend, string> = {
  chroma: 'Chroma',
  elasticsearch: 'Elasticsearch',
  milvus: 'Milvus',
}

/** 状态配置 */
const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  ready: { label: '就绪', color: 'green' },
  rebuilding: { label: '重建中', color: 'orange' },
  indexing: { label: '索引中', color: 'blue' },
  error: { label: '异常', color: 'red' },
}

/** 可见性图标映射 */
const VISIBILITY_CONFIG: Record<string, { icon: React.ReactNode; label: string }> = {
  public: { icon: <GlobalOutlined />, label: '公开' },
  role_scoped: { icon: <TeamOutlined />, label: '角色可见' },
  private: { icon: <LockOutlined />, label: '私有' },
}

/** 格式化存储大小 */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

export interface KnowledgeBaseCardProps {
  item: KnowledgeBaseListItem
  onDelete: (id: string) => void
  onRename: (id: string) => void
}

export default function KnowledgeBaseCard({ item, onDelete, onRename }: KnowledgeBaseCardProps) {
  const navigate = useNavigate()

  const handleOpen = useCallback(() => {
    navigate(`/knowledge/${item.id}`)
  }, [navigate, item.id])

  const statusCfg = STATUS_CONFIG[item.status] ?? STATUS_CONFIG.ready
  const visCfg = VISIBILITY_CONFIG[item.visibility] ?? VISIBILITY_CONFIG.public

  const menuItems = [
    {
      key: 'rename',
      icon: <EditOutlined />,
      label: '重命名',
      onClick: () => onRename(item.id),
    },
    {
      key: 'visibility',
      icon: <EyeOutlined />,
      label: '更改可见性',
      onClick: () => {
        // 由父组件处理
      },
    },
    { type: 'divider' as const },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: '删除',
      danger: true,
      onClick: () => onDelete(item.id),
    },
  ]

  return (
    <Card
      hoverable
      style={{ height: '100%' }}
      styles={{ body: { padding: 16 } }}
      actions={[
        <span key="open" onClick={handleOpen} style={{ color: '#1677ff' }}>
          打开
        </span>,
        <Dropdown key="more" menu={{ items: menuItems }} trigger={['click']}>
          <MoreOutlined style={{ cursor: 'pointer' }} />
        </Dropdown>,
      ]}
    >
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        {/* 名称 + 后端标签 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Paragraph
            strong
            ellipsis={{ tooltip: item.name }}
            style={{ margin: 0, maxWidth: '70%' }}
          >
            {item.name}
          </Paragraph>
          <Tag color={BACKEND_COLORS[item.vector_backend]}>
            {BACKEND_LABELS[item.vector_backend]}
          </Tag>
        </div>

        {/* 描述 */}
        {item.description && (
          <Text type="secondary" ellipsis style={{ fontSize: 12 }}>
            {item.description}
          </Text>
        )}

        {/* 文档数 × 分块数 */}
        <Text style={{ fontSize: 13 }}>
          <DatabaseOutlined style={{ marginRight: 4 }} />
          {item.document_count.toLocaleString()} 文档 · {item.chunk_count.toLocaleString()} 块
        </Text>

        {/* 可见性 + 状态 + 大小 */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Text style={{ fontSize: 12 }}>
            {visCfg.icon} {visCfg.label}
          </Text>
          <Tag color={statusCfg.color} style={{ margin: 0 }}>
            {statusCfg.label}
          </Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {formatSize(item.storage_size_bytes)}
          </Text>
        </div>
      </Space>
    </Card>
  )
}
