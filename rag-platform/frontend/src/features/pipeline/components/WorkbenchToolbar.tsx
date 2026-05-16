/**
 * 工作台顶部工具栏
 *
 * 包含返回按钮、管道名称、版本号、视图切换、保存等操作
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Space,
  Tag,
  Typography,
  Dropdown,
  Modal,
  Input,
  message,
} from 'antd'
import {
  ArrowLeftOutlined,
  SaveOutlined,
  PlayCircleOutlined,
  MoreOutlined,
  HistoryOutlined,
  RollbackOutlined,
  SwapOutlined,
  ExportOutlined,
} from '@ant-design/icons'
import { usePipelineWorkbenchStore, type WorkbenchView } from '../stores/pipelineWorkbenchStore'

const { Text } = Typography

interface WorkbenchToolbarProps {
  activeView: WorkbenchView
  onViewChange: (view: WorkbenchView) => void
}

/** 视图按钮配置 */
const VIEW_BUTTONS: Array<{ key: WorkbenchView; label: string }> = [
  { key: 'edit', label: '编辑' },
  { key: 'evaluate', label: '评估' },
  { key: 'publish', label: '发布' },
]

export default function WorkbenchToolbar({ activeView, onViewChange }: WorkbenchToolbarProps) {
  const navigate = useNavigate()

  const {
    pipelineName,
    pipelineVersion,
    isDirty,
    isSaving,
    save,
    validate,
  } = usePipelineWorkbenchStore()

  const [saveModalVisible, setSaveModalVisible] = useState(false)
  const [changeLog, setChangeLog] = useState('')
  const [isSavingLocal, setIsSavingLocal] = useState(false)

  // 保存管道
  const handleSave = async () => {
    setIsSavingLocal(true)
    try {
      await save()
      message.success(`保存成功，版本号: v${pipelineVersion + 1}`)
      setSaveModalVisible(false)
      setChangeLog('')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setIsSavingLocal(false)
    }
  }

  // 干运行
  const handleDryRun = async () => {
    try {
      const result = await validate()
      if (!result.valid) {
        message.error(`校验失败: ${result.errors.map((e) => e.message).join(', ')}`)
        return
      }

      // TODO: 弹出输入对话框输入测试查询
      message.info('干运行功能开发中')
    } catch (error) {
      message.error('校验失败')
    }
  }

  // 更多操作菜单
  const moreMenuItems = [
    {
      key: 'history',
      label: '版本历史',
      icon: <HistoryOutlined />,
      onClick: () => {
        // TODO: 打开版本历史面板
        message.info('版本历史功能开发中')
      },
    },
    {
      key: 'rollback',
      label: '回滚...',
      icon: <RollbackOutlined />,
      onClick: () => {
        // TODO: 打开回滚对话框
        message.info('回滚功能开发中')
      },
    },
    {
      key: 'compare',
      label: '版本对比',
      icon: <SwapOutlined />,
      onClick: () => {
        // TODO: 打开版本对比面板
        message.info('版本对比功能开发中')
      },
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'export',
      label: '导出 JSON',
      icon: <ExportOutlined />,
      onClick: () => {
        // TODO: 实现导出功能
        message.info('导出功能开发中')
      },
    },
  ]

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 16px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fff',
      }}
    >
      {/* 左侧区域 */}
      <Space>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/pipelines')}
        >
          管道列表
        </Button>
        <Text strong>{pipelineName}</Text>
        <Tag color="blue">v{pipelineVersion}</Tag>
        {isDirty && (
          <Tag color="orange">未保存</Tag>
        )}
      </Space>

      {/* 中央区域：视图切换 */}
      <Space>
        {VIEW_BUTTONS.map((btn) => (
          <Button
            key={btn.key}
            type={activeView === btn.key ? 'primary' : 'default'}
            onClick={() => onViewChange(btn.key)}
          >
            {btn.label}
          </Button>
        ))}
      </Space>

      {/* 右侧区域 */}
      <Space>
        {activeView === 'edit' && (
          <>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => setSaveModalVisible(true)}
              loading={isSaving}
            >
              保存
              {isDirty && <span style={{ marginLeft: 4, color: '#fff' }}>●</span>}
            </Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={handleDryRun}
            >
              干运行
            </Button>
            <Dropdown menu={{ items: moreMenuItems }} trigger={['click']}>
              <Button icon={<MoreOutlined />} />
            </Dropdown>
          </>
        )}
      </Space>

      {/* 保存对话框 */}
      <Modal
        title="保存管道"
        open={saveModalVisible}
        onOk={handleSave}
        onCancel={() => {
          setSaveModalVisible(false)
          setChangeLog('')
        }}
        confirmLoading={isSavingLocal}
        okText="保存"
        cancelText="取消"
      >
        <div>
          <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>
            版本号将自动从 v{pipelineVersion} 递增到 v{pipelineVersion + 1}
          </Text>
          <label style={{ display: 'block', marginBottom: 8 }}>变更日志（可选）</label>
          <Input.TextArea
            placeholder="描述此次修改的内容..."
            value={changeLog}
            onChange={(e) => setChangeLog(e.target.value)}
            rows={4}
          />
        </div>
      </Modal>
    </div>
  )
}
