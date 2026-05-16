/**
 * 内联调优建议卡片
 *
 * 在评估详情中展示单条调优建议。
 * 包含：严重度色条、建议标题、描述、当前值与建议值、
 * "去编辑器中打开"按钮、"采纳此建议"按钮、"忽略"按钮。
 */
import { useState } from 'react'
import { Button, Modal, Space, Tag, Typography, message } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, ToolOutlined, WarningOutlined } from '@ant-design/icons'
import type { TuningSuggestion, Severity } from '@/entities/rag-eval/types'
import { adoptSuggestion, rejectSuggestion } from '@/api/rag-eval/evaluation'

const { Text, Paragraph } = Typography

interface Props {
  suggestion: TuningSuggestion
  conflictingIds: string[]
  onAdopted: (id: string) => void
  onIgnored: (id: string) => void
  onOpenInEditor: (targetNodeId: string) => void
}

/** 严重性 → 图标与颜色 */
function severityMeta(level: Severity): { color: string; icon: React.ReactNode; label: string } {
  switch (level) {
    case 'critical':
      return { color: '#ff4d4f', icon: <CloseCircleOutlined />, label: '严重' }
    case 'warning':
      return { color: '#faad14', icon: <WarningOutlined />, label: '警告' }
    case 'info':
      return { color: '#1890ff', icon: <CheckCircleOutlined />, label: '提示' }
  }
}

export default function InlineTuningCard({
  suggestion,
  conflictingIds,
  onAdopted,
  onIgnored,
  onOpenInEditor,
}: Props) {
  const [adopting, setAdopting] = useState(false)
  const [ignoring, setIgnoring] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const meta = severityMeta(suggestion.severity)
  const isPending = suggestion.status === 'pending'
  const isAdopted = suggestion.status === 'adopted'
  const hasConflict = conflictingIds.length > 0

  async function handleAdopt() {
    setAdopting(true)
    try {
      await adoptSuggestion(suggestion.id)
      message.success('建议已采纳，配置已更新')
      onAdopted(suggestion.id)
    } catch {
      message.error('采纳失败')
    } finally {
      setAdopting(false)
      setConfirmOpen(false)
    }
  }

  async function handleIgnore() {
    setIgnoring(true)
    try {
      await rejectSuggestion(suggestion.id)
      message.info('建议已忽略')
      onIgnored(suggestion.id)
    } catch {
      message.error('操作失败')
    } finally {
      setIgnoring(false)
    }
  }

  return (
    <div
      style={{
        border: `1px solid ${isAdopted ? '#d9d9d9' : '#f0f0f0'}`,
        borderLeft: `4px solid ${isAdopted ? '#d9d9d9' : meta.color}`,
        borderRadius: 8,
        padding: 16,
        marginBottom: 12,
        backgroundColor: isAdopted ? '#fafafa' : '#fff',
        opacity: isAdopted ? 0.75 : 1,
      }}
    >
      {/* 顶部：严重性 + 标题 */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: meta.color, fontSize: 16, marginRight: 8 }}>
          {meta.icon}
        </span>
        <Text strong style={{ flex: 1 }}>
          {suggestion.title}
        </Text>
        <Tag color={meta.color}>{meta.label}</Tag>
        {isAdopted && <Tag>已采纳</Tag>}
      </div>

      {/* 描述 */}
      {suggestion.description && (
        <Paragraph type="secondary" style={{ marginBottom: 8, fontSize: 13 }}>
          {suggestion.description}
        </Paragraph>
      )}

      {/* 当前值 vs 建议值 */}
      <div style={{ marginBottom: 8 }}>
        {suggestion.current_value && (
          <Tag style={{ marginRight: 8 }}>
            当前: {suggestion.current_value}
          </Tag>
        )}
        {suggestion.suggested_value && (
          <Tag color="blue">
            建议: {suggestion.suggested_value}
          </Tag>
        )}
      </div>

      {/* 预期影响 */}
      {suggestion.expected_impact && (
        <Text style={{ fontSize: 12, color: '#52c41a' }}>
          ⤷ {suggestion.expected_impact}
        </Text>
      )}

      {/* 冲突警告 */}
      {hasConflict && (
        <div
          style={{
            marginTop: 8,
            padding: 8,
            backgroundColor: '#fff2f0',
            border: '1px solid #ffccc7',
            borderRadius: 4,
          }}
        >
          <Text style={{ fontSize: 12, color: '#ff4d4f' }}>
            ⚠ 该建议与 {conflictingIds.length} 条建议存在冲突，请谨慎采纳
          </Text>
        </div>
      )}

      {/* 操作按钮 */}
      {isPending && (
        <Space style={{ marginTop: 12 }}>
          <Button
            size="small"
            icon={<ToolOutlined />}
            onClick={() => onOpenInEditor(suggestion.id)}
          >
            去编辑器中打开
          </Button>
          <Button
            size="small"
            type="primary"
            loading={adopting}
            onClick={() => setConfirmOpen(true)}
          >
            采纳此建议
          </Button>
          <Button
            size="small"
            danger
            loading={ignoring}
            onClick={handleIgnore}
          >
            忽略
          </Button>
        </Space>
      )}

      {/* 采纳确认弹窗 */}
      <Modal
        title="确认采纳调优建议"
        open={confirmOpen}
        onOk={handleAdopt}
        onCancel={() => setConfirmOpen(false)}
        confirmLoading={adopting}
        okText="确认采纳"
        cancelText="取消"
      >
        <Paragraph>
          确认应用以下变更？
        </Paragraph>
        <div style={{ padding: '8px 16px', backgroundColor: '#f5f5f5', borderRadius: 4 }}>
          <Text strong>节点: </Text>
          <Text code>{suggestion.id}</Text>
          <br />
          {suggestion.current_value && (
            <>
              <Text strong>当前值: </Text>
              <Text delete>{suggestion.current_value}</Text>
              <br />
            </>
          )}
          {suggestion.suggested_value && (
            <>
              <Text strong>新值: </Text>
              <Text style={{ color: '#52c41a' }}>{suggestion.suggested_value}</Text>
            </>
          )}
        </div>
        {hasConflict && (
          <Paragraph style={{ marginTop: 12, color: '#faad14' }}>
            提示：此建议与其他建议存在冲突，确认采纳后可能需要手动调整其他参数。
          </Paragraph>
        )}
      </Modal>
    </div>
  )
}
