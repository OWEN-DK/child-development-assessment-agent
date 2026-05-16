/** 用户管理页面——租户管理员 */
import { useCallback, useEffect, useState } from 'react'
import {
  Button, Form, Input, Modal, Popconfirm, Select, Space,
  Table, Tag, Typography, message,
} from 'antd'
import { PlusOutlined, MailOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { User, Role } from '@/entities/auth/types'
import { getUsers, createUser, deleteUser, inviteUser, getRoles } from '@/api/auth'

const { Title } = Typography

export default function UserListPage() {
  const [users, setUsers] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [roles, setRoles] = useState<Role[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()
  const [inviteForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [res, roleList] = await Promise.all([
        getUsers({ page, page_size: 20 }),
        getRoles(),
      ])
      setUsers(res.items)
      setTotal(res.total)
      setRoles(roleList)
    } catch { message.error('加载用户列表失败') }
    finally { setLoading(false) }
  }, [page])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      await createUser(values)
      message.success('用户已创建')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch { /* validation */ }
    finally { setSubmitting(false) }
  }

  const handleInvite = async () => {
    try {
      const values = await inviteForm.validateFields()
      setSubmitting(true)
      await inviteUser(values)
      message.success('邀请已发送')
      setInviteOpen(false)
      inviteForm.resetFields()
    } catch { /* validation */ }
    finally { setSubmitting(false) }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteUser(id)
      message.success('用户已删除')
      load()
    } catch { message.error('删除失败') }
  }

  const columns: ColumnsType<User> = [
    { title: '用户名', dataIndex: 'username', width: 150 },
    { title: '邮箱', dataIndex: 'email', width: 220 },
    {
      title: '状态', dataIndex: 'status', width: 80,
      render: (s: string) => <Tag color={s === 'active' ? 'green' : 'red'}>{s}</Tag>,
    },
    {
      title: '角色', dataIndex: 'roles', width: 200,
      render: (r: string[]) => r?.map((role) => <Tag key={role}>{role}</Tag>),
    },
    {
      title: '创建时间', dataIndex: 'created_at', width: 160,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作', width: 80,
      render: (_: unknown, record: User) => (
        <Popconfirm title="确认删除该用户？" onConfirm={() => handleDelete(record.id)}>
          <Button type="link" size="small" danger>删除</Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>用户管理</Title>
        <Space>
          <Button icon={<MailOutlined />} onClick={() => setInviteOpen(true)}>邀请用户</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setModalOpen(true) }}>新建用户</Button>
        </Space>
      </div>

      <Table<User>
        rowKey="id" columns={columns} dataSource={users} loading={loading}
        pagination={{ current: page, total, pageSize: 20, showTotal: (t) => `共 ${t} 个用户`, onChange: setPage }}
      />

      {/* 新建用户弹窗 */}
      <Modal title="新建用户" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)} confirmLoading={submitting}>
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="roles" label="角色">
            <Select mode="multiple" placeholder="选择角色" options={roles.map((r) => ({ value: r.slug, label: r.name }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 邀请用户弹窗 */}
      <Modal title="邀请用户" open={inviteOpen} onOk={handleInvite} onCancel={() => setInviteOpen(false)} confirmLoading={submitting}>
        <Form form={inviteForm} layout="vertical">
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}>
            <Input placeholder="user@example.com" />
          </Form.Item>
          <Form.Item name="roles" label="分配角色" rules={[{ required: true }]}>
            <Select mode="multiple" placeholder="选择角色" options={roles.map((r) => ({ value: r.slug, label: r.name }))} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
