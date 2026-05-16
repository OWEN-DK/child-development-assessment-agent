/** 角色管理页面——租户管理员 */
import { useCallback, useEffect, useState } from 'react'
import {
  Button, Checkbox, Form, Input, Modal, Popconfirm, Space,
  Table, Tag, Typography, message,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { Role } from '@/entities/auth/types'
import { PERMISSION_OPTIONS } from '@/entities/auth/types'
import { getRoles, createRole, updateRole, deleteRole } from '@/api/auth'

const { Title, Text } = Typography

export default function RoleListPage() {
  const [roles, setRoles] = useState<Role[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Role | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const list = await getRoles()
      setRoles(list)
    } catch { message.error('加载角色列表失败') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      if (editing) {
        await updateRole(editing.id, values)
        message.success('角色已更新')
      } else {
        await createRole(values)
        message.success('角色已创建')
      }
      setModalOpen(false)
      form.resetFields()
      load()
    } catch { /* validation */ }
    finally { setSubmitting(false) }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteRole(id)
      message.success('角色已删除')
      load()
    } catch { message.error('删除失败') }
  }

  const columns: ColumnsType<Role> = [
    { title: '名称', dataIndex: 'name', width: 150 },
    { title: '标识', dataIndex: 'slug', width: 120 },
    {
      title: '类型', dataIndex: 'is_builtin', width: 80,
      render: (v: boolean) => v ? <Tag color="blue">内置</Tag> : <Tag>自定义</Tag>,
    },
    {
      title: '权限', dataIndex: 'permissions', width: 400,
      render: (perms: string[]) => (
        <Space wrap>
          {perms?.map((p) => <Tag key={p} style={{ fontSize: 11 }}>{p}</Tag>)}
        </Space>
      ),
    },
    {
      title: '操作', width: 120,
      render: (_: unknown, record: Role) => (
        <Space>
          <Button type="link" size="small" onClick={() => {
            setEditing(record)
            form.setFieldsValue({ ...record, permissions: record.permissions || [] })
            setModalOpen(true)
          }}>编辑</Button>
          {!record.is_builtin && (
            <Popconfirm title="确认删除该角色？" onConfirm={() => handleDelete(record.id)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>角色管理</Title>
          <Text type="secondary">内置角色不可删除，自定义角色可自由配置权限</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditing(null); form.resetFields(); setModalOpen(true)
        }}>新建角色</Button>
      </div>

      <Table<Role>
        rowKey="id" columns={columns} dataSource={roles} loading={loading}
        pagination={false}
      />

      <Modal
        title={editing ? '编辑角色' : '新建角色'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        width={600}
      >
        <Form form={form} layout="vertical" initialValues={{ permissions: [] }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：知识库编辑者" />
          </Form.Item>
          <Form.Item name="slug" label="标识 (Slug)" rules={[{ required: true, pattern: /^[a-z0-9\-_]+$/ }]}>
            <Input placeholder="如：kb-editor" disabled={!!editing?.is_builtin} />
          </Form.Item>
          <Form.Item name="permissions" label="权限列表" rules={[{ required: true }]}>
            <Checkbox.Group options={PERMISSION_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
