/**
 * 域容器节点
 *
 * 基于 React Flow 自定义节点，支持折叠/展开、防越界拖拽
 */
import { memo, useCallback } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Badge, Typography, Space, Button, Tooltip } from 'antd'
import {
  FolderOutlined,
  FolderOpenOutlined,
  CloseOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { usePipelineWorkbenchStore } from '../../stores/pipelineWorkbenchStore'

const { Text } = Typography

interface DomainContainerNodeData {
  id: string
  name: string
  knowledgeBaseId?: string
  weight: number
  keywords: string[]
  collapsed: boolean
  nodeIds: string[]
}

function DomainContainerNode({ data, selected }: NodeProps) {
  const { id, name, collapsed, nodeIds, keywords } = data as unknown as DomainContainerNodeData

  const { selectDomain, removeDomain, updateDomainConfig } = usePipelineWorkbenchStore()

  // 切换折叠/展开
  const toggleCollapse = useCallback(() => {
    updateDomainConfig(id, { collapsed: !collapsed })
  }, [id, collapsed, updateDomainConfig])

  // 删除域
  const handleDelete = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      if (confirm(`确定删除域「${name}」及其内部 ${nodeIds.length} 个节点？`)) {
        removeDomain(id)
      }
    },
    [id, name, nodeIds.length, removeDomain]
  )

  // 点击选中
  const handleClick = useCallback(() => {
    selectDomain(id)
  }, [id, selectDomain])

  return (
    <div
      onClick={handleClick}
      style={{
        background: '#fff',
        border: `2px solid ${selected ? '#1890ff' : '#d9d9d9'}`,
        borderRadius: 8,
        minWidth: collapsed ? 200 : 400,
        minHeight: collapsed ? 60 : 200,
        transition: 'all 0.2s',
      }}
    >
      {/* 域标题栏 */}
      <div
        onDoubleClick={toggleCollapse}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 12px',
          background: '#fafafa',
          borderBottom: collapsed ? 'none' : '1px solid #f0f0f0',
          borderRadius: '6px 6px 0 0',
          cursor: 'pointer',
        }}
      >
        <Space>
          {collapsed ? <FolderOutlined /> : <FolderOpenOutlined />}
          <Text strong>{name}</Text>
          <Badge count={nodeIds.length} style={{ backgroundColor: '#1890ff' }} />
        </Space>

        <Space size="small">
          <Tooltip title="域设置">
            <Button
              type="text"
              size="small"
              icon={<SettingOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                // TODO: 打开域设置面板
              }}
            />
          </Tooltip>
          <Tooltip title="删除域">
            <Button
              type="text"
              size="small"
              danger
              icon={<CloseOutlined />}
              onClick={handleDelete}
            />
          </Tooltip>
        </Space>
      </div>

      {/* 域内容区域（展开时显示） */}
      {!collapsed && (
        <div
          style={{
            padding: 12,
            minHeight: 150,
            position: 'relative',
          }}
        >
          {/* 关键词标签 */}
          {keywords.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              {keywords.map((keyword) => (
                <span
                  key={keyword}
                  style={{
                    display: 'inline-block',
                    padding: '2px 8px',
                    margin: '0 4px 4px 0',
                    background: '#f0f0f0',
                    borderRadius: 4,
                    fontSize: 12,
                  }}
                >
                  {keyword}
                </span>
              ))}
            </div>
          )}

          {/* 子节点占位（实际子节点由 React Flow 渲染） */}
          <div
            style={{
              textAlign: 'center',
              color: '#999',
              padding: '40px 0',
              border: '2px dashed #d9d9d9',
              borderRadius: 4,
            }}
          >
            {nodeIds.length === 0
              ? '拖拽节点到此处'
              : `${nodeIds.length} 个节点`}
          </div>
        </div>
      )}

      {/* 输入 Handle（用于聚合节点连接） */}
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: '#1890ff' }}
      />

      {/* 输出 Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: '#1890ff' }}
      />
    </div>
  )
}

export default memo(DomainContainerNode)
