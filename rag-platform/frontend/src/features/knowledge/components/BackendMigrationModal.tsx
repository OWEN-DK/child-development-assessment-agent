/**
 * 后端迁移确认/进度 Modal
 *
 * 确认迁移向量后端，展示 SSE 实时进度
 */
import { useState, useEffect, useRef } from 'react'
import { Modal, Progress, Alert, Button, Typography, Space, Spin } from 'antd'
import { SwapOutlined } from '@ant-design/icons'
import type { VectorBackend } from '@/entities/knowledge/types'
import { migrateBackend, getMigrationEstimate, subscribeRebuildProgress } from '@/api/knowledge/knowledge-base'
import type { RebuildProgressEvent } from '@/entities/knowledge/types'

const { Text } = Typography

const BACKEND_LABELS: Record<VectorBackend, string> = {
  chroma: 'Chroma',
  elasticsearch: 'Elasticsearch',
  milvus: 'Milvus',
}

export interface BackendMigrationModalProps {
  open: boolean
  onClose: () => void
  kbId: string
  kbName: string
  currentBackend: VectorBackend
  targetBackend: VectorBackend
  onSuccess: () => void
}

export default function BackendMigrationModal({
  open,
  onClose,
  kbId,
  kbName,
  currentBackend,
  targetBackend,
  onSuccess,
}: BackendMigrationModalProps) {
  const [loading, setLoading] = useState(false)
  const [migrating, setMigrating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('')
  const [estimatedMinutes, setEstimatedMinutes] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const unsubRef = useRef<(() => void) | null>(null)

  // 加载迁移预估
  useEffect(() => {
    if (!open) return
    setLoading(true)
    getMigrationEstimate(kbId, targetBackend)
      .then((estimate) => {
        setEstimatedMinutes(estimate.estimated_minutes)
      })
      .catch(() => {
        // 预估失败不阻塞操作
      })
      .finally(() => setLoading(false))
  }, [open, kbId, targetBackend])

  // 清理 SSE 连接
  useEffect(() => {
    return () => {
      unsubRef.current?.()
    }
  }, [])

  /** 执行迁移 */
  const handleMigrate = async () => {
    setMigrating(true)
    setProgress(0)
    setError(null)

    try {
      await migrateBackend(kbId, targetBackend)

      // 订阅迁移进度
      unsubRef.current = subscribeRebuildProgress(
        kbId,
        (event: RebuildProgressEvent) => {
          setProgress(event.progress_pct)
          setMessage(event.progress_message || '')
          if (event.event === 'complete') {
            setMigrating(false)
            setProgress(100)
            setTimeout(() => {
              onSuccess()
              onClose()
            }, 2000)
          } else if (event.event === 'error') {
            setMigrating(false)
            setError(event.progress_message || '迁移失败')
          }
        },
        () => {
          setMigrating(false)
          setError('连接断开，请刷新页面查看状态')
        }
      )
    } catch (err) {
      setMigrating(false)
      setError(err instanceof Error ? err.message : '迁移失败')
    }
  }

  const handleClose = () => {
    if (migrating) return // 迁移中不允许关闭
    unsubRef.current?.()
    setProgress(0)
    setMessage('')
    setError(null)
    setMigrating(false)
    onClose()
  }

  return (
    <Modal
      title={
        <span>
          <SwapOutlined style={{ marginRight: 8 }} />
          迁移向量后端：{BACKEND_LABELS[currentBackend]} → {BACKEND_LABELS[targetBackend]}
        </span>
      }
      open={open}
      onCancel={handleClose}
      footer={
        migrating
          ? null
          : [
              <Button key="cancel" onClick={handleClose}>
                取消
              </Button>,
              <Button key="confirm" type="primary" danger onClick={handleMigrate}>
                确认迁移
              </Button>,
            ]
      }
      maskClosable={!migrating}
      closable={!migrating}
    >
      {/* 预估信息 */}
      {loading && <Spin />}
      {!loading && !migrating && !error && (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>
            知识库「{kbName}」
          </Text>
          {estimatedMinutes !== null && (
            <Text>
              根据当前文档量，预计需要 {estimatedMinutes} 分钟
            </Text>
          )}
          <Alert
            type="warning"
            message="迁移期间知识库可读不可写。迁移完成后自动切换到新后端。"
            showIcon
          />
        </Space>
      )}

      {/* 进度展示 */}
      {migrating && (
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <Progress percent={progress} status="active" />
          {message && <Text type="secondary">{message}</Text>}
        </Space>
      )}

      {/* 完成 */}
      {!migrating && progress === 100 && !error && (
        <Alert type="success" message="迁移完成" showIcon />
      )}

      {/* 失败 */}
      {error && (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert type="error" message={error} showIcon />
          <Text type="secondary">已回滚到原后端 {BACKEND_LABELS[currentBackend]}</Text>
          <Button onClick={handleClose}>关闭</Button>
        </Space>
      )}
    </Modal>
  )
}
