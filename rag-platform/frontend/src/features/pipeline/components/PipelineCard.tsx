/**
 * 管道卡片组件
 *
 * 展示管道基本信息，提供快捷操作
 */
import { Card, Tag, Button, Dropdown, Typography } from 'antd'
import {
  EditOutlined,
  ExperimentOutlined,
  SendOutlined,
  MoreOutlined,
  CopyOutlined,
  ExportOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import type { PipelineListItem } from '@/entities/pipeline/types'

const { Text } = Typography

interface PipelineCardProps {
  pipeline: PipelineListItem
  onEdit: () => void
  onEvaluate: () => void
  onPublish: () => void
  onDelete: () => void
}

/** 状态标签颜色映射 */
const STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  published: 'success',
  archived: 'warning',
}

/** 状态标签文本映射 */
const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档',
}

export default function PipelineCard({
  pipeline,
  onEdit,
  onEvaluate,
  onPublish,
  onDelete,
}: PipelineCardProps) {
  // 更多操作菜单
  const menuItems = [
    {
      key: 'copy',
      label: '复制',
      icon: <CopyOutlined />,
      onClick: () => {
        // TODO: 实现复制功能
      },
    },
    {
      key: 'export',
      label: '导出 JSON',
      icon: <ExportOutlined />,
      onClick: () => {
        // TODO: 实现导出功能
      },
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'delete',
      label: '删除',
      icon: <DeleteOutlined />,
      danger: true,
      onClick: onDelete,
    },
  ]

  return (
    <Card
      hoverable
      style={{ height: '100%' }}
      actions={[
        <Button key="edit" type="text" icon={<EditOutlined />} onClick={onEdit}>
          编辑
        </Button>,
        <Button key="evaluate" type="text" icon={<ExperimentOutlined />} onClick={onEvaluate}>
          评估
        </Button>,
        <Button key="publish" type="text" icon={<SendOutlined />} onClick={onPublish}>
          发布
        </Button>,
      ]}
    >
      {/* 卡片头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <Text strong style={{ fontSize: 16 }}>
            {pipeline.name}
          </Text>
          <Tag color="blue" style={{ marginLeft: 8 }}>
            v{pipeline.version}
          </Tag>
        </div>
        <Dropdown menu={{ items: menuItems }} trigger={['click']}>
          <Button type="text" icon={<MoreOutlined />} size="small" />
        </Dropdown>
      </div>

      {/* 域数和节点数 */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">
          {pipeline.domainCount} 域 · {pipeline.nodeCount} 节点
        </Text>
      </div>

      {/* 最近评估得分 */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">最近评估: </Text>
        {pipeline.lastEvalScore !== undefined ? (
          <Text
            style={{
              color: pipeline.lastEvalScore >= 0.8 ? '#52c41a' :
                     pipeline.lastEvalScore >= 0.6 ? '#faad14' : '#ff4d4f',
              fontWeight: 'bold',
            }}
          >
            {pipeline.lastEvalScore.toFixed(2)}
          </Text>
        ) : (
          <Text type="secondary">—</Text>
        )}
      </div>

      {/* 发布状态 */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">已发布: </Text>
        {pipeline.publishedEndpoints > 0 ? (
          <Tag color="green">
            {pipeline.publishedEndpoints} 个端点
          </Tag>
        ) : (
          <Text type="secondary">—</Text>
        )}
      </div>

      {/* 状态标签 */}
      <div>
        <Tag color={STATUS_COLORS[pipeline.status]}>
          {STATUS_LABELS[pipeline.status]}
        </Tag>
      </div>
    </Card>
  )
}
