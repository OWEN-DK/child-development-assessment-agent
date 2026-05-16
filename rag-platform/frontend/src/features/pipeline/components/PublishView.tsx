/**
 * 发布视图
 *
 * 复用 Phase 4 发布配置面板，配置搜索端点发布
 */
import { useEffect, useState } from 'react'
import {
  Typography,
  Empty,
  Button,
  Spin,
  Card,
  Form,
  Input,
  Select,
  Switch,
  InputNumber,
  Space,
  message,
} from 'antd'
import { SendOutlined, PlusOutlined } from '@ant-design/icons'
import { usePipelineWorkbenchStore } from '../stores/pipelineWorkbenchStore'

const { Title, Text } = Typography
const { Option } = Select

export default function PublishView() {
  const { pipelineId, pipelineName, pipelineVersion } = usePipelineWorkbenchStore()

  const [isLoading, setIsLoading] = useState(false)
  const [endpoints, setEndpoints] = useState<any[]>([])
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [form] = Form.useForm()

  // 加载已发布端点
  useEffect(() => {
    if (pipelineId) {
      loadEndpoints()
    }
  }, [pipelineId])

  const loadEndpoints = async () => {
    setIsLoading(true)
    try {
      // TODO: 调用 API 获取已发布端点
      // const result = await pipelineApi.getPublishedEndpoints(pipelineId)
      // setEndpoints(result)
      setEndpoints([])
    } catch (error) {
      console.error('加载端点失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  // 发布管道
  const handlePublish = async (_values: any) => {
    try {
      // TODO: 调用发布 API
      message.success('发布成功')
      setShowCreateForm(false)
      form.resetFields()
      loadEndpoints()
    } catch (error) {
      message.error('发布失败')
    }
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
      {/* 标题 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <SendOutlined style={{ marginRight: 8 }} />
            发布视图
          </Title>
          <Text type="secondary">
            管道: {pipelineName} (v{pipelineVersion})
          </Text>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setShowCreateForm(true)}
        >
          发布新端点
        </Button>
      </div>

      {/* 创建发布表单 */}
      {showCreateForm && (
        <Card title="发布新端点" style={{ marginBottom: 24 }}>
          <Form
            form={form}
            layout="vertical"
            onFinish={handlePublish}
          >
            <Form.Item
              label="URL 路径"
              name="urlPath"
              rules={[
                { required: true, message: '请输入 URL 路径' },
                { pattern: /^[a-zA-Z0-9_-]+$/, message: '仅允许字母、数字、下划线、连字符' },
                { min: 4, max: 50, message: '长度 4-50 字符' },
              ]}
            >
              <Input
                placeholder="例如: medical-consultation"
                addonBefore="/search/"
              />
            </Form.Item>

            <Form.Item
              label="绑定版本"
              name="boundVersion"
              initialValue={pipelineVersion}
            >
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item
              label="认证方式"
              name="authType"
              initialValue="jwt"
            >
              <Select>
                <Option value="jwt">JWT</Option>
                <Option value="api_key">API Key</Option>
                <Option value="none">无认证</Option>
              </Select>
            </Form.Item>

            <Form.Item
              label="速率限制 (QPS)"
              name="rateLimit"
              initialValue={0}
            >
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item
              label="启用"
              name="enabled"
              valuePropName="checked"
              initialValue={true}
            >
              <Switch />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">
                  发布
                </Button>
                <Button onClick={() => setShowCreateForm(false)}>
                  取消
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      )}

      {/* 已发布端点列表 */}
      {endpoints.length === 0 ? (
        <Empty
          description={
            <div>
              <Text>暂无已发布端点</Text>
              <br />
              <Text type="secondary">
                发布管道后，外部系统可通过生成的 URL 调用搜索 API
              </Text>
            </div>
          }
        >
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setShowCreateForm(true)}
          >
            发布第一个端点
          </Button>
        </Empty>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {endpoints.map((endpoint: any) => (
            <Card key={endpoint.endpointId}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <Text strong>/search/{endpoint.urlPath}</Text>
                  <br />
                  <Text type="secondary">
                    版本: v{endpoint.boundVersion} | 认证: {endpoint.authType} | QPS: {endpoint.rateLimit || '无限制'}
                  </Text>
                </div>
                <Space>
                  <Button size="small">编辑</Button>
                  <Button size="small" danger>停用</Button>
                </Space>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
