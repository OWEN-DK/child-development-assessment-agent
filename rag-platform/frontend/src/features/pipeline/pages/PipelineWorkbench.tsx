/**
 * 管道工作台
 *
 * 三视图切换容器（编辑/评估/发布）
 */
import { useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { Spin, Result, Button } from 'antd'
import { usePipelineWorkbenchStore, type WorkbenchView } from '../stores/pipelineWorkbenchStore'
import WorkbenchToolbar from '../components/WorkbenchToolbar'
import PipelineCanvas from '../components/Canvas/PipelineCanvas'
import EvaluateView from '../components/EvaluateView'
import PublishView from '../components/PublishView'

export default function PipelineWorkbench() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const {
    isLoading,
    error,
    activeView,
    switchView,
    loadPipeline,
  } = usePipelineWorkbenchStore()

  // 从 URL 路径解析当前视图
  const getViewFromPath = (): WorkbenchView => {
    const path = location.pathname
    if (path.includes('/evaluate')) return 'evaluate'
    if (path.includes('/publish')) return 'publish'
    return 'edit'
  }

  // 加载管道数据
  useEffect(() => {
    if (id) {
      loadPipeline(id)
    }
  }, [id, loadPipeline])

  // 同步 URL 视图到 store
  useEffect(() => {
    const view = getViewFromPath()
    if (view !== activeView) {
      switchView(view)
    }
  }, [location.pathname])

  // 切换视图
  const handleViewChange = (view: WorkbenchView) => {
    switchView(view)
    navigate(`/pipelines/${id}/${view}`)
  }

  // 加载态
  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  // 错误态
  if (error) {
    return (
      <Result
        status="error"
        title="加载失败"
        subTitle={error}
        extra={[
          <Button key="back" onClick={() => navigate('/pipelines')}>
            返回列表
          </Button>,
          <Button key="retry" type="primary" onClick={() => id && loadPipeline(id)}>
            重试
          </Button>,
        ]}
      />
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* 顶部工具栏 */}
      <WorkbenchToolbar activeView={activeView} onViewChange={handleViewChange} />

      {/* 视图内容区域 */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {/* 编辑视图 */}
        <div style={{ display: activeView === 'edit' ? 'block' : 'none', height: '100%' }}>
          <PipelineCanvas />
        </div>

        {/* 评估视图 */}
        <div style={{ display: activeView === 'evaluate' ? 'block' : 'none', height: '100%' }}>
          <EvaluateView />
        </div>

        {/* 发布视图 */}
        <div style={{ display: activeView === 'publish' ? 'block' : 'none', height: '100%' }}>
          <PublishView />
        </div>
      </div>
    </div>
  )
}
