/** 租户管理页面——超管专属 */
import { useCallback, useEffect, useState } from 'react'
import {
  Button, Form, Input, Modal,
  Table, Tag, Typography, message,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { Tenant } from '@/entities/auth/types'
import { getTenants, createTenant, updateTenant } from '@/api/auth'

const { Title } = Typography

const STATUS_COLOR: Record<string, string> = {
  active: 'green', disabled: 'orange', archived: 'default',
}

export default function TenantListPage() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Tenant | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getTenants({ page, page_size: 20 })
      setTenants(res.items)
      setTotal(res.total)
    } catch { message.error('加载租户列表失败') }
    finally { setLoading(false) }
  }, [page])

  useEffect(() => { load() }, [load])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      if (editing) {
        await updateTenant(editing.id, values)
        message.success('租户已更新')
      } else {
        await createTenant(values)
        message.success('租户已创建')
      }
      setModalOpen(false)
      form.resetFields()
      load()
    } catch { /* validation error */ }
    finally { setSubmitting(false) }
  }

  const columns: ColumnsType<Tenant> = [
    { title: '名称', dataIndex: 'name', width: 200 },
    { title: 'Slug', dataIndex: 'slug', width: 150 },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
    },
    { title: '用户数', dataIndex: 'user_count', width: 80 },
    {
      title: '存储用量', dataIndex: 'storage_usage_gb', width: 100,
      render: (v: number) => `${v.toFixed(1)} GB`,
    },
    {
      title: '创建时间', dataIndex: 'created_at', width: 180,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '操作', width: 100,
      render: (_: unknown, record: Tenant) => (
        <Button type="link" size="small" onClick={() => {
          setEditing(record)
          form.setFieldsValue(record)
          setModalOpen(true)
        }}>编辑</Button>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>租户管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditing(null); form.resetFields(); setModalOpen(true)
        }}>新建租户</Button>
      </div>

      <Table<Tenant>
        rowKey="id" columns={columns} dataSource={tenants} loading={loading}
        pagination={{ current: page, total, pageSize: 20, showTotal: (t) => `共 ${t} 个租户`, onChange: setPage }}
      />

      <Modal
        title={editing ? '编辑租户' : '新建租户'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：仁和医院" />
          </Form.Item>
          <Form.Item name="slug" label="唯一标识 (Slug)" rules={[{ required: true, pattern: /^[a-z0-9\-]+$/ }]}>
            <Input placeholder="如：renhe-hospital" disabled={!!editing} />
          </Form.Item>
          {!editing && (
            <>
              <Form.Item name={['admin_user', 'username']} label="管理员用户名" rules={[{ required: true }]}>
                <Input placeholder="初始管理员" />
              </Form.Item>
              <Form.Item name={['admin_user', 'email']} label="管理员邮箱" rules={[{ required: true, type: 'email' }]}>
                <Input placeholder="admin@example.com" />
              </Form.Item>
              <Form.Item name={['admin_user', 'password']} label="管理员密码" rules={[{ required: true, min: 6 }]}>
                <Input.Password placeholder="至少 6 位" />
              </Form.Item>
            </>
          )}
          {editing && (
            <Form.Item name="status" label="状态">
              <Input placeholder="active / disabled / archived" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  )
}
