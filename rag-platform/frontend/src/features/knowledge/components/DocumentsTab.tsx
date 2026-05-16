/**
 * 文档 Tab 组件
 *
 * 包含拖拽上传区域、上传进度、文档列表、文档详情抽屉
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Table,
  Button,
  Input,
  Select,
  Tag,
  Space,
  Drawer,
  Descriptions,
  Skeleton,
  Alert,
  Popconfirm,
  Typography,
  message,
} from 'antd'
import {
  SearchOutlined,
  DeleteOutlined,
  ReloadOutlined,
  RedoOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import FileDropZone from '@/shared/components/FileDropZone'
import { useKnowledgeBaseStore } from '@/features/knowledge/stores/knowledgeBaseStore'
import type { KBDocument, ParseStatus, DocAccessLevel } from '@/entities/knowledge/types'
import { getDocument } from '@/api/knowledge/knowledge-base'
import type { KBDocumentDetail } from '@/entities/knowledge/types'

const { Text } = Typography

/** 解析状态配置 */
const PARSE_STATUS_MAP: Record<ParseStatus, { label: string; color: string }> = {
  pending: { label: '待解析', color: 'default' },
  parsing: { label: '解析中', color: 'processing' },
  parsed: { label: '已解析', color: 'success' },
  error: { label: '异常', color: 'error' },
}

/** 格式化文件大小 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export interface DocumentsTabProps {
  kbId: string
}

export default function DocumentsTab({ kbId }: DocumentsTabProps) {
  const documents = useKnowledgeBaseStore((s) => s.documents)
  const documentsTotal = useKnowledgeBaseStore((s) => s.documentsTotal)
  const documentsLoading = useKnowledgeBaseStore((s) => s.documentsLoading)
  const documentsPage = useKnowledgeBaseStore((s) => s.documentsPage)
  const documentsPageSize = useKnowledgeBaseStore((s) => s.documentsPageSize)
  const documentSearch = useKnowledgeBaseStore((s) => s.documentSearch)
  const uploadProgress = useKnowledgeBaseStore((s) => s.uploadProgress)
  const loadDocuments = useKnowledgeBaseStore((s) => s.loadDocuments)
  const setDocumentSearch = useKnowledgeBaseStore((s) => s.setDocumentSearch)
  const setDocumentFileTypeFilter = useKnowledgeBaseStore((s) => s.setDocumentFileTypeFilter)
  const setDocumentsPage = useKnowledgeBaseStore((s) => s.setDocumentsPage)
  const uploadDocuments = useKnowledgeBaseStore((s) => s.uploadDocuments)
  const deleteDocument = useKnowledgeBaseStore((s) => s.deleteDocument)
  const batchDeleteDocuments = useKnowledgeBaseStore((s) => s.batchDeleteDocuments)
  const reparseDocument = useKnowledgeBaseStore((s) => s.reparseDocument)
  const previewChunks = useKnowledgeBaseStore((s) => s.previewChunks)

  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailDoc, setDetailDoc] = useState<KBDocumentDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  /** 加载文档详情 */
  const openDetail = useCallback(async (docId: string) => {
    setDetailOpen(true)
    setDetailLoading(true)
    try {
      const detail = await getDocument(kbId, docId)
      setDetailDoc(detail)
    } catch {
      message.error('加载文档详情失败')
    } finally {
      setDetailLoading(false)
    }
  }, [kbId])

  /** 搜索防抖 */
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleSearch = useCallback(
    (value: string) => {
      setDocumentSearch(value)
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
      searchTimerRef.current = setTimeout(() => loadDocuments(kbId), 300)
    },
    [setDocumentSearch, loadDocuments, kbId]
  )

  useEffect(() => {
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    }
  }, [])

  /** 表格列定义 */
  const columns: ColumnsType<KBDocument> = [
    {
      title: '文件名',
      dataIndex: 'filename',
      ellipsis: true,
      render: (name: string, record) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => openDetail(record.id)}>
          {name}
        </Button>
      ),
    },
    {
      title: '类型',
      dataIndex: 'file_type',
      width: 80,
      render: (type: string) => <Tag>{type.toUpperCase()}</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      width: 90,
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '分块数',
      dataIndex: 'chunk_count',
      width: 80,
    },
    {
      title: '解析状态',
      dataIndex: 'parse_status',
      width: 90,
      render: (status: ParseStatus) => {
        const cfg = PARSE_STATUS_MAP[status]
        return <Tag color={cfg.color}>{cfg.label}</Tag>
      },
    },
    {
      title: '权限',
      dataIndex: 'access_level',
      width: 80,
      render: (level: DocAccessLevel) => (level === 'inherit' ? '继承' : '受限'),
    },
    {
      title: '上传时间',
      dataIndex: 'uploaded_at',
      width: 160,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      width: 140,
      render: (_, record) => (
        <Space size={4}>
          {(record.parse_status === 'error') && (
            <Button size="small" icon={<RedoOutlined />} onClick={() => reparseDocument(kbId, record.id)}>
              重试
            </Button>
          )}
          <Popconfirm
            title="确认删除此文档？"
            onConfirm={() => deleteDocument(kbId, record.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 拖拽上传区域 */}
      <FileDropZone onFiles={(files) => uploadDocuments(kbId, files)} />

      {/* 上传进度列表 */}
      {uploadProgress.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {uploadProgress.map((item) => (
            <div
              key={item.file.name}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '4px 8px',
                background: '#fafafa',
                borderRadius: 4,
              }}
            >
              <Text ellipsis style={{ maxWidth: 200, fontSize: 13 }}>
                {item.file.name}
              </Text>
              {item.status === 'uploading' && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {item.percentage}%
                </Text>
              )}
              {item.status === 'done' && <Tag color="success">完成</Tag>}
              {item.status === 'duplicate' && <Tag color="warning">已存在</Tag>}
              {item.status === 'error' && (
                <Tag color="error">{item.errorMessage || '失败'}</Tag>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 搜索/筛选栏 */}
      <Space>
        <Input
          placeholder="搜索文件名"
          prefix={<SearchOutlined />}
          value={documentSearch}
          onChange={(e) => handleSearch(e.target.value)}
          style={{ width: 200 }}
          allowClear
        />
        <Select
          placeholder="文件类型"
          allowClear
          style={{ width: 120 }}
          onChange={(v) => {
            setDocumentFileTypeFilter(v || '')
            loadDocuments(kbId)
          }}
          options={[
            { label: '全部', value: '' },
            { label: 'PDF', value: 'pdf' },
            { label: 'TXT', value: 'txt' },
            { label: 'Markdown', value: 'md' },
            { label: 'HTML', value: 'html' },
            { label: 'EPUB', value: 'epub' },
          ]}
        />
        <Button
          icon={<ReloadOutlined />}
          onClick={() => loadDocuments(kbId)}
        >
          刷新
        </Button>
        {selectedRowKeys.length > 0 && (
          <Popconfirm
            title={`确认删除 ${selectedRowKeys.length} 个文档？`}
            onConfirm={async () => {
              await batchDeleteDocuments(kbId, selectedRowKeys)
              setSelectedRowKeys([])
            }}
          >
            <Button danger icon={<DeleteOutlined />}>
              批量删除 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        )}
      </Space>

      {/* 文档表格 */}
      {documentsLoading ? (
        <Skeleton active paragraph={{ rows: 6 }} />
      ) : documents.length === 0 ? (
        <Alert
          type="info"
          message="暂无文档，拖拽文件到上方区域上传"
          showIcon
        />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={documents}
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys as string[]),
          }}
          pagination={{
            current: documentsPage,
            pageSize: documentsPageSize,
            total: documentsTotal,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page) => {
              setDocumentsPage(page)
              loadDocuments(kbId)
            },
          }}
          size="small"
        />
      )}

      {/* 文档详情抽屉 */}
      <Drawer
        title={detailDoc?.filename ?? '文档详情'}
        open={detailOpen}
        onClose={() => {
          setDetailOpen(false)
          setDetailDoc(null)
        }}
        width={520}
      >
        {detailLoading ? (
          <Skeleton active />
        ) : detailDoc ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="文件名">{detailDoc.filename}</Descriptions.Item>
              <Descriptions.Item label="大小">{formatFileSize(detailDoc.file_size)}</Descriptions.Item>
              <Descriptions.Item label="页数">{detailDoc.page_count ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="MD5">
                <Text copyable style={{ fontSize: 12 }}>{detailDoc.md5_hash}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="解析状态">
                <Tag color={PARSE_STATUS_MAP[detailDoc.parse_status].color}>
                  {PARSE_STATUS_MAP[detailDoc.parse_status].label}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="上传时间">
                {new Date(detailDoc.uploaded_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
            </Descriptions>

            {/* 分块预览 */}
            {detailDoc.chunk_preview.length > 0 && (
              <div>
                <Text strong>前 {detailDoc.chunk_preview.length} 块预览</Text>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                  {detailDoc.chunk_preview.map((chunk) => (
                    <div
                      key={chunk.chunk_index}
                      style={{
                        padding: 8,
                        background: '#fafafa',
                        borderRadius: 4,
                        fontSize: 12,
                      }}
                    >
                      <Text type="secondary">#{chunk.chunk_index}</Text>
                      <Text ellipsis style={{ display: 'block', maxHeight: 60, overflow: 'hidden' }}>
                        {chunk.content.slice(0, 200)}...
                      </Text>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 操作按钮 */}
            <Space>
              <Button
                icon={<RedoOutlined />}
                onClick={() => {
                  reparseDocument(kbId, detailDoc.id)
                  setDetailOpen(false)
                }}
              >
                重新解析
              </Button>
              <Button
                type="link"
                onClick={() => {
                  setDetailOpen(false)
                  // 跳转到分块 Tab 并预览该文档（由父组件处理）
                  previewChunks(kbId, detailDoc.id)
                }}
              >
                查看全部分块 →
              </Button>
            </Space>
          </div>
        ) : null}
      </Drawer>
    </div>
  )
}
