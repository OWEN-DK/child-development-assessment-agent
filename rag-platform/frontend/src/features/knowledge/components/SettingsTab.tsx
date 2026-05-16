/**
 * 设置 Tab 组件
 *
 * 包含基本信息编辑和危险区域（删除知识库）
 */
import { useState, useEffect } from 'react'
import {
  Card,
  Input,
  Button,
  Divider,
  Typography,
  Modal,
  Alert,
  message,
  Space,
} from 'antd'
import {
  SaveOutlined,
  DeleteOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useKnowledgeBaseStore } from '@/features/knowledge/stores/knowledgeBaseStore'
import type { KbDeletionConflict } from '@/entities/knowledge/types'

const { Text, Paragraph } = Typography
const { TextArea } = Input

export interface SettingsTabProps {
  kbId: string
}

export default function SettingsTab({ kbId }: SettingsTabProps) {
  const navigate = useNavigate()
  const currentKB = useKnowledgeBaseStore((s) => s.currentKB)
  const updateKnowledgeBaseInfo = useKnowledgeBaseStore((s) => s.updateKnowledgeBaseInfo)

  const [name, setName] = useState(currentKB?.name ?? '')
  const [description, setDescription] = useState(currentKB?.description ?? '')
  const [saving, setSaving] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [blockModalOpen, setBlockModalOpen] = useState(false)
  const [conflict, setConflict] = useState<KbDeletionConflict | null>(null)

  useEffect(() => {
    setName(currentKB?.name ?? '')
    setDescription(currentKB?.description ?? '')
  }, [currentKB])

  /** 保存基本信息 */
  const handleSave = async () => {
    setSaving(true)
    try {
      await updateKnowledgeBaseInfo(kbId, {
        name: name.trim(),
        description: description.trim() || undefined,
      })
      message.success('保存成功')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  /** 删除知识库（含管道引用检查） */
  const handleDelete = () => {
    // 先弹出二次确认
    setDeleteModalOpen(true)
  }

  /** 确认删除 */
  const confirmDelete = async () => {
    try {
      // 通过 store 删除，同步更新列表缓存
      await useKnowledgeBaseStore.getState().deleteKnowledgeBase(kbId)
      message.success('知识库已删除')
      navigate('/knowledge')
    } catch (error: unknown) {
      // 检查是否为管道引用冲突
      const err = error as { response?: { data?: { data?: KbDeletionConflict } } }
      const conflictData = err?.response?.data?.data
      if (conflictData?.pipelines && conflictData.pipelines.length > 0) {
        setConflict(conflictData)
        setBlockModalOpen(true)
      } else {
        message.error('删除失败')
      }
    } finally {
      setDeleteModalOpen(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 600 }}>
      {/* 基本信息编辑 */}
      <Card title="基本信息" size="small">
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <div>
            <Text>名称</Text>
            <Input
              maxLength={64}
              showCount
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <Text>描述</Text>
            <TextArea
              maxLength={512}
              showCount
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={{ marginTop: 4 }}
            />
          </div>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            disabled={
              name.trim() === (currentKB?.name ?? '') &&
              (description.trim() || '') === (currentKB?.description ?? '')
            }
            onClick={handleSave}
          >
            保存
          </Button>
        </Space>
      </Card>

      {/* 危险区域 */}
      <Divider />
      <Card size="small" style={{ borderColor: '#ff4d4f' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text strong style={{ color: '#ff4d4f' }}>
            <WarningOutlined /> 危险区域
          </Text>
          <Text type="secondary">删除后不可恢复，请谨慎操作。</Text>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={handleDelete}
          >
            删除此知识库
          </Button>
        </Space>
      </Card>

      {/* 二次确认 Modal */}
      <Modal
        title={
          <span style={{ color: '#ff4d4f' }}>
            <WarningOutlined /> 确认删除
          </span>
        }
        open={deleteModalOpen}
        onCancel={() => setDeleteModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setDeleteModalOpen(false)}>
            取消
          </Button>,
          <Button key="confirm" danger type="primary" onClick={confirmDelete}>
            确认删除
          </Button>,
        ]}
      >
        <Paragraph>
          确定删除知识库「{currentKB?.name}」？
        </Paragraph>
        <Paragraph>
          将同时删除：
          <br />· {currentKB?.document_count ?? 0} 份文档
          <br />· {currentKB?.chunk_count ?? 0} 条分块
          <br />· 全部向量索引
        </Paragraph>
        <Alert type="error" message="此操作不可撤销。" showIcon />
      </Modal>

      {/* 阻止 Modal（有管道引用） */}
      <Modal
        title={
          <span style={{ color: '#faad14' }}>
            <WarningOutlined /> 无法删除此知识库
          </span>
        }
        open={blockModalOpen}
        onCancel={() => {
          setBlockModalOpen(false)
          setConflict(null)
        }}
        footer={[
          <Button key="ok" onClick={() => {
            setBlockModalOpen(false)
            setConflict(null)
          }}>
            知道了
          </Button>,
        ]}
      >
        <Text>以下管道正在引用此知识库：</Text>
        <div style={{ margin: '12px 0' }}>
          {conflict?.pipelines.map((p) => (
            <div key={p.pipeline_id} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
              <Space>
                <Text>{p.pipeline_name}（v{p.version_number}）</Text>
                <Button
                  type="link"
                  size="small"
                  onClick={() => window.open(`/pipelines/${p.pipeline_id}/edit`, '_blank')}
                >
                  查看
                </Button>
              </Space>
            </div>
          ))}
        </div>
        <Alert
          type="warning"
          message="请先从这些管道中移除对该知识库的引用后再尝试删除。"
          showIcon
        />
      </Modal>
    </div>
  )
}
