/**
 * 管道列表页
 *
 * 展示当前租户所有管道，支持新建、搜索、筛选
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Input, Select, Space, Typography, Empty, Spin, message, Modal } from 'antd'
import { PlusOutlined, SearchOutlined, ImportOutlined } from '@ant-design/icons'
import { usePipelineListStore } from '../stores/pipelineListStore'
import PipelineCard from '../components/PipelineCard'
import * as pipelineApi from '@/api/pipeline/pipeline'

const { Title } = Typography
const { Option } = Select

export default function PipelineListPage() {
  const navigate = useNavigate()
  const {
    pipelines,
    total,
    isLoading,
    error,
    searchQuery,
    statusFilter,
    page,
    pageSize,
    loadPipelines,
    deletePipeline,
    setSearchQuery,
    setStatusFilter,
    setPage,
  } = usePipelineListStore()

  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [newPipelineName, setNewPipelineName] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  // 加载管道列表
  useEffect(() => {
    loadPipelines()
  }, [loadPipelines])

  // 创建空白管道
  const handleCreateBlank = async () => {
    if (!newPipelineName.trim()) {
      message.error('请输入管道名称')
      return
    }

    setIsCreating(true)
    try {
      const pipeline = await pipelineApi.createPipeline({
        name: newPipelineName.trim(),
      })
      message.success('管道创建成功')
      setCreateModalVisible(false)
      setNewPipelineName('')
      navigate(`/pipelines/${pipeline.id}/edit`)
    } catch (error) {
      message.error('创建失败')
    } finally {
      setIsCreating(false)
    }
  }

  // 删除管道
  const handleDelete = async (id: string, name: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定删除管道「${name}」及其全部版本历史？此操作不可撤销。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deletePipeline(id)
          message.success('删除成功')
        } catch (error) {
          message.error('删除失败')
        }
      },
    })
  }

  return (
    <div style={{ padding: '24px' }}>
      {/* 顶部标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          管道管理
        </Title>
        <Space>
          <Button icon={<ImportOutlined />}>导入</Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            新建管道
          </Button>
        </Space>
      </div>

      {/* 搜索筛选栏 */}
      <Space style={{ marginBottom: 24 }} size="middle">
        <Input
          placeholder="搜索管道名称"
          prefix={<SearchOutlined />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ width: 300 }}
          allowClear
        />
        <Select
          placeholder="状态筛选"
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 150 }}
          allowClear
        >
          <Option value={null}>全部</Option>
          <Option value="draft">草稿</Option>
          <Option value="published">已发布</Option>
          <Option value="archived">已归档</Option>
        </Select>
      </Space>

      {/* 错误提示 */}
      {error && (
        <div style={{ marginBottom: 16, color: '#ff4d4f' }}>
          {error}
          <Button type="link" onClick={loadPipelines}>
            重试
          </Button>
        </div>
      )}

      {/* 加载态 */}
      {isLoading && (
        <div style={{ textAlign: 'center', padding: '100px 0' }}>
          <Spin size="large" />
        </div>
      )}

      {/* 空状态 */}
      {!isLoading && pipelines.length === 0 && (
        <Empty
          description="暂无管道"
          style={{ padding: '100px 0' }}
        >
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            创建第一个管道
          </Button>
        </Empty>
      )}

      {/* 管道卡片网格 */}
      {!isLoading && pipelines.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 16,
          }}
        >
          {pipelines.map((pipeline) => (
            <PipelineCard
              key={pipeline.id}
              pipeline={pipeline}
              onEdit={() => navigate(`/pipelines/${pipeline.id}/edit`)}
              onEvaluate={() => navigate(`/pipelines/${pipeline.id}/evaluate`)}
              onPublish={() => navigate(`/pipelines/${pipeline.id}/publish`)}
              onDelete={() => handleDelete(pipeline.id, pipeline.name)}
            />
          ))}
        </div>
      )}

      {/* 分页 */}
      {total > pageSize && (
        <div style={{ textAlign: 'center', marginTop: 24 }}>
          <Button
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
            style={{ marginRight: 8 }}
          >
            上一页
          </Button>
          <span>{page} / {Math.ceil(total / pageSize)}</span>
          <Button
            disabled={page >= Math.ceil(total / pageSize)}
            onClick={() => setPage(page + 1)}
            style={{ marginLeft: 8 }}
          >
            下一页
          </Button>
        </div>
      )}

      {/* 新建管道对话框 */}
      <Modal
        title="新建管道"
        open={createModalVisible}
        onOk={handleCreateBlank}
        onCancel={() => {
          setCreateModalVisible(false)
          setNewPipelineName('')
        }}
        confirmLoading={isCreating}
        okText="创建"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 8 }}>管道名称</label>
          <Input
            placeholder="请输入管道名称"
            value={newPipelineName}
            onChange={(e) => setNewPipelineName(e.target.value)}
            onPressEnter={handleCreateBlank}
          />
        </div>
      </Modal>
    </div>
  )
}
