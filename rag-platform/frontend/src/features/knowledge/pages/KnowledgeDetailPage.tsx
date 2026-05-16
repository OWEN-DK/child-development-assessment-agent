/**
 * 知识库详情页
 *
 * 4 选项卡布局（文档 / 分块&向量 / 权限 / 设置），URL 路由匹配
 */
import { useEffect } from 'react'
import {
  Tabs,
  Breadcrumb,
  Spin,
  Alert,
  Button,
  Tag,
  Typography,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useKnowledgeBaseStore } from '@/features/knowledge/stores/knowledgeBaseStore'
import type { DetailTab } from '@/features/knowledge/stores/knowledgeBaseStore'
import type { VectorBackend } from '@/entities/knowledge/types'
import DocumentsTab from '../components/DocumentsTab'
import ChunksTab from '../components/ChunksTab'
import PermissionsTab from '../components/PermissionsTab'
import SettingsTab from '../components/SettingsTab'

const { Text } = Typography

/** 向量后端颜色 */
const BACKEND_COLORS: Record<VectorBackend, string> = {
  chroma: 'cyan',
  elasticsearch: 'gold',
  milvus: 'blue',
}

/** 状态标签配置 */
const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  ready: { text: '就绪', color: 'green' },
  rebuilding: { text: '重建中', color: 'orange' },
  indexing: { text: '索引中', color: 'blue' },
  error: { text: '异常', color: 'red' },
}

/** 路径到 Tab 的映射 */
const PATH_TO_TAB: Record<string, DetailTab> = {
  documents: 'documents',
  chunks: 'chunks',
  permissions: 'permissions',
  settings: 'settings',
}

export default function KnowledgeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const currentKB = useKnowledgeBaseStore((s) => s.currentKB)
  const detailLoading = useKnowledgeBaseStore((s) => s.detailLoading)
  const detailError = useKnowledgeBaseStore((s) => s.detailError)
  const loadKnowledgeBase = useKnowledgeBaseStore((s) => s.loadKnowledgeBase)
  const loadDocuments = useKnowledgeBaseStore((s) => s.loadDocuments)
  const setActiveTab = useKnowledgeBaseStore((s) => s.setActiveTab)
  const activeTab = useKnowledgeBaseStore((s) => s.activeTab)
  const clearCurrentKB = useKnowledgeBaseStore((s) => s.clearCurrentKB)

  // 从 URL 推导当前 Tab
  const pathSegments = location.pathname.split('/')
  const lastSegment = pathSegments[pathSegments.length - 1]
  const tabFromUrl = PATH_TO_TAB[lastSegment] ?? 'documents'

  useEffect(() => {
    setActiveTab(tabFromUrl)
  }, [tabFromUrl, setActiveTab])

  // 加载详情
  useEffect(() => {
    if (id) {
      loadKnowledgeBase(id)
    }
    return () => clearCurrentKB()
  }, [id, loadKnowledgeBase, clearCurrentKB])

  // 切换 Tab 时按需加载文档列表
  useEffect(() => {
    if (id && activeTab === 'documents' && currentKB) {
      loadDocuments(id)
    }
  }, [id, activeTab, currentKB, loadDocuments])

  /** 切换 Tab，更新 URL */
  const handleTabChange = (key: string) => {
    const tab = key as DetailTab
    setActiveTab(tab)
    if (tab === 'documents') {
      navigate(`/knowledge/${id}`, { replace: true })
    } else {
      navigate(`/knowledge/${id}/${tab}`, { replace: true })
    }
  }

  if (detailLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (detailError) {
    return (
      <div style={{ padding: 24 }}>
        <Alert
          type="error"
          message="加载知识库详情失败"
          description={detailError}
          action={
            <Button onClick={() => navigate('/knowledge')}>
              返回列表
            </Button>
          }
          showIcon
        />
      </div>
    )
  }

  const statusCfg = STATUS_LABELS[currentKB?.status ?? 'ready']
  const backend = currentKB?.vector_backend ?? 'chroma'

  return (
    <div style={{ padding: 24 }}>
      {/* 面包屑 */}
      <Breadcrumb
        items={[
          {
            title: (
              <Button type="link" style={{ padding: 0 }} onClick={() => navigate('/knowledge')}>
                <ArrowLeftOutlined /> 知识库
              </Button>
            ),
          },
          {
            title: (
              <span>
                {currentKB?.name ?? '...'}
                <Tag color={BACKEND_COLORS[backend]} style={{ marginLeft: 8 }}>
                  {backend}
                </Tag>
                {currentKB && (
                  <>
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      {currentKB.document_count} 文档
                    </Text>
                    <Tag color={statusCfg.color} style={{ marginLeft: 8 }}>
                      {statusCfg.text}
                    </Tag>
                  </>
                )}
              </span>
            ),
          },
        ]}
        style={{ marginBottom: 16 }}
      />

      {/* 选项卡 */}
      <Tabs
        activeKey={activeTab}
        onChange={handleTabChange}
        items={[
          {
            key: 'documents',
            label: '文档',
            children: id ? <DocumentsTab kbId={id} /> : null,
          },
          {
            key: 'chunks',
            label: '分块 & 向量',
            children: id ? <ChunksTab kbId={id} /> : null,
          },
          {
            key: 'permissions',
            label: '权限',
            children: id ? <PermissionsTab kbId={id} /> : null,
          },
          {
            key: 'settings',
            label: '设置',
            children: id ? <SettingsTab kbId={id} /> : null,
          },
        ]}
      />
    </div>
  )
}
