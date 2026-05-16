/**
 * 权限 Tab 组件
 *
 * 包含可见性设置、角色可见列表、文档 ACL 总览
 */
import { useState, useEffect } from 'react'
import {
  Radio,
  Card,
  Tag,
  Button,
  Table,
  Select,
  Space,
  Modal,
  Typography,
  Alert,
  message,
  Spin,
} from 'antd'
import {
  PlusOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useKnowledgeBaseStore } from '@/features/knowledge/stores/knowledgeBaseStore'
import { getRoles } from '@/api/knowledge/knowledge-base'
import type { KnowledgeBaseVisibility, DocAclEntry, DocAccessLevel } from '@/entities/knowledge/types'

const { Text } = Typography

export interface PermissionsTabProps {
  kbId: string
}

export default function PermissionsTab({ kbId }: PermissionsTabProps) {
  const currentKB = useKnowledgeBaseStore((s) => s.currentKB)
  const docAcls = useKnowledgeBaseStore((s) => s.docAcls)
  const aclLoading = useKnowledgeBaseStore((s) => s.aclLoading)
  const loadDocAcls = useKnowledgeBaseStore((s) => s.loadDocAcls)
  const updateVisibility = useKnowledgeBaseStore((s) => s.updateVisibility)
  const updateVisibleRoles = useKnowledgeBaseStore((s) => s.updateVisibleRoles)
  const updateDocAcl = useKnowledgeBaseStore((s) => s.updateDocAcl)

  const [roles, setRoles] = useState<Array<{ id: string; name: string }>>([])
  const [selectedRoles, setSelectedRoles] = useState<string[]>(currentKB?.visible_roles ?? [])
  const [aclModalOpen, setAclModalOpen] = useState(false)
  const [editingDocId, setEditingDocId] = useState<string | null>(null)
  const [editingDocAclRoles, setEditingDocAclRoles] = useState<string[]>([])
  const [dirtyAcls, setDirtyAcls] = useState<Map<string, { access_level: DocAccessLevel; doc_acl: string[] | null }>>(new Map())
  const [saving, setSaving] = useState(false)

  // 加载角色列表
  useEffect(() => {
    getRoles().then(setRoles).catch(() => {})
  }, [])

  // 加载文档 ACL
  useEffect(() => {
    loadDocAcls(kbId)
  }, [kbId, loadDocAcls])

  // 同步 visible_roles
  useEffect(() => {
    setSelectedRoles(currentKB?.visible_roles ?? [])
  }, [currentKB?.visible_roles])

  /** 切换可见性 */
  const handleVisibilityChange = async (visibility: KnowledgeBaseVisibility) => {
    try {
      await updateVisibility(kbId, visibility)
      message.success('可见性已更新')
    } catch {
      message.error('更新失败')
    }
  }

  /** 更新可见角色 */
  const handleSaveRoles = async () => {
    try {
      await updateVisibleRoles(kbId, selectedRoles)
      message.success('角色可见列表已更新')
    } catch {
      message.error('更新失败')
    }
  }

  /** 打开 ACL 编辑 Modal */
  const openAclModal = (docId: string, currentAcl: string[] | null) => {
    setEditingDocId(docId)
    setEditingDocAclRoles(currentAcl ?? [])
    setAclModalOpen(true)
  }

  /** 保存 ACL Modal */
  const handleSaveAclModal = () => {
    if (!editingDocId) return
    setDirtyAcls((prev) => {
      const next = new Map(prev)
      next.set(editingDocId, { access_level: 'restricted', doc_acl: editingDocAclRoles })
      return next
    })
    setAclModalOpen(false)
  }

  /** 批量保存所有 ACL 变更 */
  const handleSaveAll = async () => {
    setSaving(true)
    try {
      const promises = Array.from(dirtyAcls.entries()).map(([docId, acl]) =>
        updateDocAcl(kbId, docId, acl)
      )
      await Promise.all(promises)
      setDirtyAcls(new Map())
      message.success('权限已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  /** 表格列定义 */
  const columns: ColumnsType<DocAclEntry> = [
    {
      title: '文档名称',
      dataIndex: 'filename',
      ellipsis: true,
    },
    {
      title: '权限级别',
      dataIndex: 'access_level',
      width: 120,
      render: (level: DocAccessLevel, record) => {
        const dirty = dirtyAcls.get(record.doc_id)
        const currentLevel = dirty?.access_level ?? level
        return (
          <Select
            size="small"
            value={currentLevel}
            onChange={(v) => {
              setDirtyAcls((prev) => {
                const next = new Map(prev)
                next.set(record.doc_id, {
                  access_level: v,
                  doc_acl: v === 'restricted' ? (dirty?.doc_acl ?? record.doc_acl ?? []) : null,
                })
                return next
              })
            }}
            options={[
              { value: 'inherit', label: '继承' },
              { value: 'restricted', label: '受限' },
            ]}
          />
        )
      },
    },
    {
      title: '文档 ACL',
      dataIndex: 'doc_acl',
      render: (acl: string[] | null, record) => {
        const dirty = dirtyAcls.get(record.doc_id)
        const currentAcl = dirty?.doc_acl ?? acl
        const currentLevel = dirty?.access_level ?? record.access_level
        if (currentLevel === 'inherit') {
          return <Text type="secondary">继承自知识库</Text>
        }
        return (
          <Space size={4} wrap>
            {currentAcl?.map((role) => (
              <Tag key={role}>{role}</Tag>
            ))}
            <Button
              size="small"
              type="link"
              icon={<PlusOutlined />}
              onClick={() => openAclModal(record.doc_id, currentAcl)}
            >
              编辑
            </Button>
          </Space>
        )
      },
    },
  ]

  const visibility = currentKB?.visibility ?? 'public'

  // 知识库可见角色限制（ACL 角色不能超出此范围）
  const visibleRoles = currentKB?.visible_roles ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 可见性设置 */}
      <Card title="可见性设置" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Radio.Group
            value={visibility}
            onChange={(e) => handleVisibilityChange(e.target.value)}
            optionType="button"
            buttonStyle="solid"
          >
            <Radio.Button value="public">公开</Radio.Button>
            <Radio.Button value="role_scoped">角色可见</Radio.Button>
            <Radio.Button value="private">私有</Radio.Button>
          </Radio.Group>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {visibility === 'public' && '所有租户成员可见此知识库'}
            {visibility === 'role_scoped' && '仅指定角色的成员可见'}
            {visibility === 'private' && '仅创建者和知识库管理员可见'}
          </Text>
        </Space>
      </Card>

      {/* 角色可见列表 */}
      {visibility === 'role_scoped' && (
        <Card title="角色可见列表" size="small">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space wrap>
              {selectedRoles.map((roleId) => {
                const role = roles.find((r) => r.id === roleId)
                return role ? (
                  <Tag key={roleId} closable onClose={() => {
                    setSelectedRoles((prev) => prev.filter((id) => id !== roleId))
                  }}>
                    {role.name}
                  </Tag>
                ) : null
              })}
              <Select
                mode="multiple"
                placeholder="添加角色"
                style={{ width: 250 }}
                value={selectedRoles}
                onChange={setSelectedRoles}
                options={roles.map((r) => ({ value: r.id, label: r.name }))}
              />
            </Space>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveRoles}>
              保存角色列表
            </Button>
          </Space>
        </Card>
      )}

      {/* 文档 ACL 总览 */}
      <Card title="文档 ACL 总览" size="small">
        {aclLoading ? (
          <Spin />
        ) : (
          <>
            <Table
              rowKey="doc_id"
              columns={columns}
              dataSource={docAcls}
              size="small"
              pagination={{ pageSize: 20 }}
            />
            {dirtyAcls.size > 0 && (
              <div style={{ marginTop: 12 }}>
                <Alert
                  type="info"
                  message={`有 ${dirtyAcls.size} 项未保存的变更`}
                  showIcon
                  action={
                    <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSaveAll}>
                      保存全部变更
                    </Button>
                  }
                />
              </div>
            )}
          </>
        )}
      </Card>

      {/* ACL 编辑 Modal */}
      <Modal
        title="编辑文档 ACL"
        open={aclModalOpen}
        onCancel={() => setAclModalOpen(false)}
        onOk={handleSaveAclModal}
      >
        <Select
          mode="multiple"
          placeholder="选择可访问的角色"
          style={{ width: '100%' }}
          value={editingDocAclRoles}
          onChange={setEditingDocAclRoles}
          options={visibleRoles.map((roleId) => {
            const role = roles.find((r) => r.id === roleId)
            return { value: roleId, label: role?.name ?? roleId }
          })}
        />
        {visibleRoles.length === 0 && (
          <Alert
            type="warning"
            message="请先在上方设置知识库可见角色"
            style={{ marginTop: 8 }}
            showIcon
          />
        )}
      </Modal>
    </div>
  )
}
