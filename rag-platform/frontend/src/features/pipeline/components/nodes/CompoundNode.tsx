/**
 * 复合节点组件
 *
 * 可折叠/展开的复合节点，内部包含多个子节点
 */
import { memo, useCallback, useState } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Typography, Badge, Tooltip, Dropdown } from 'antd'
import {
  FolderOutlined,
  FolderOpenOutlined,
  MoreOutlined,
  ExpandOutlined,
  CompressOutlined,
  EditOutlined,
  SaveOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import type { PipelineNode, EdgeConfig } from '@/entities/pipeline/types'

const { Text } = Typography

interface CompoundNodeData {
  id: string
  name: string
  description?: string
  nodes: PipelineNode[]
  edges: EdgeConfig[]
  inputHandles: string[]
  outputHandles: string[]
}

function CompoundNode({ data, selected }: NodeProps) {
  const { name, description, nodes, edges, inputHandles, outputHandles } =
    data as unknown as CompoundNodeData

  const [collapsed, setCollapsed] = useState(true)

  // 切换折叠/展开
  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev)
  }, [])

  // 右键菜单
  const menuItems = [
    {
      key: 'toggle',
      label: collapsed ? '展开' : '折叠',
      icon: collapsed ? <ExpandOutlined /> : <CompressOutlined />,
      onClick: toggleCollapse,
    },
    {
      key: 'edit',
      label: '编辑内部节点',
      icon: <EditOutlined />,
      onClick: () => {
        // TODO: 打开内部节点编辑器
        console.log('编辑内部节点')
      },
    },
    {
      key: 'save',
      label: '保存为复合节点',
      icon: <SaveOutlined />,
      onClick: () => {
        // TODO: 保存到复合节点库
        console.log('保存为复合节点')
      },
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'delete',
      label: '从库中移除',
      icon: <DeleteOutlined />,
      danger: true,
      onClick: () => {
        // TODO: 从复合节点库中移除
        console.log('从库中移除')
      },
    },
  ]

  return (
    <Dropdown menu={{ items: menuItems }} trigger={['contextMenu']}>
      <div
        onDoubleClick={toggleCollapse}
        style={{
          background: '#fff',
          border: `2px solid ${selected ? '#722ed1' : '#d9d9d9'}`,
          borderRadius: 8,
          minWidth: collapsed ? 180 : 300,
          transition: 'all 0.2s',
          cursor: 'pointer',
          position: 'relative',
        }}
      >
        {/* 复合节点标题栏 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '8px 12px',
            background: '#f9f0ff',
            borderBottom: collapsed ? 'none' : '1px solid #f0f0f0',
            borderRadius: '6px 6px 0 0',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {collapsed ? <FolderOutlined /> : <FolderOpenOutlined />}
            <Text strong>{name}</Text>
            <Badge
              count={nodes.length}
              style={{ backgroundColor: '#722ed1' }}
            />
          </div>

          <Tooltip title={description}>
            <MoreOutlined style={{ color: '#999' }} />
          </Tooltip>
        </div>

        {/* 内容区域（展开时显示） */}
        {!collapsed && (
          <div
            style={{
              padding: 12,
              minHeight: 100,
            }}
          >
            {/* 子节点列表 */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {nodes.map((node) => (
                <div
                  key={node.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 10px',
                    background: '#fafafa',
                    borderRadius: 4,
                    border: '1px solid #d9d9d9',
                    fontSize: 12,
                  }}
                >
                  <span>📦</span>
                  <span>{node.label}</span>
                  <span style={{ color: '#999' }}>({node.type})</span>
                </div>
              ))}
            </div>

            {/* 连线信息 */}
            {edges.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 11, color: '#999' }}>
                {edges.length} 条连线
              </div>
            )}
          </div>
        )}

        {/* 输入 Handle */}
        {inputHandles.map((handleId) => (
          <Handle
            key={handleId}
            type="target"
            id={handleId}
            position={Position.Top}
            style={{ background: '#722ed1' }}
          />
        ))}

        {/* 输出 Handle */}
        {outputHandles.map((handleId) => (
          <Handle
            key={handleId}
            type="source"
            id={handleId}
            position={Position.Bottom}
            style={{ background: '#722ed1' }}
          />
        ))}
      </div>
    </Dropdown>
  )
}

export default memo(CompoundNode)
