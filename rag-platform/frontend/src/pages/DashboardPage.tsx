/**
 * 仪表盘首页
 *
 * 展示知识库/管道统计概览 + 快捷入口
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Col, Row, Skeleton, Statistic, Typography, Alert, Button } from 'antd'
import {
  BookOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import * as pipelineApi from '@/api/pipeline/pipeline'
import * as kbApi from '@/api/knowledge/knowledge-base'

const { Title, Text } = Typography




/** 仪表盘统计数据 */
interface DashboardStats {
  kbCount: number
  pipelineCount: number
  documentCount: number
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<DashboardStats>({ kbCount: 0, pipelineCount: 0, documentCount: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadStats() {
      setLoading(true)
      setError(null)
      try {
        const [kbResult, pipelineResult] = await Promise.all([
          kbApi.getKnowledgeBases({ page_size: 1 }),
          pipelineApi.getPipelines({ pageSize: 1 }),
        ])

        if (cancelled) return

        setStats({
          kbCount: kbResult.total ?? 0,
          pipelineCount: pipelineResult.total ?? 0,
          documentCount: kbResult.items?.reduce((sum, item) => sum + (item.document_count ?? 0), 0) ?? 0,
        })
      } catch {
        if (!cancelled) {
          setError('无法加载仪表盘数据，请确认后端服务已启动')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadStats()
    return () => { cancelled = true }
  }, [])

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginBottom: 24 }}>
        仪表盘
      </Title>

      {/* 错误提示 */}
      {error && (
        <Alert
          type="warning"
          message={error}
          showIcon
          style={{ marginBottom: 24 }}
          action={
            <Button size="small" onClick={() => window.location.reload()}>
              重试
            </Button>
          }
        />
      )}

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            {loading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic
                title="知识库"
                value={stats.kbCount}
                prefix={<BookOutlined />}
                valueStyle={{ color: '#1677ff' }}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            {loading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic
                title="管道"
                value={stats.pipelineCount}
                prefix={<ApartmentOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            {loading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic
                title="文档总数"
                value={stats.documentCount}
                prefix={<FileTextOutlined />}
                valueStyle={{ color: '#faad14' }}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="搜索 API"
              value="--"
              prefix={<SearchOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 快捷入口 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12}>
          <Card
            hoverable
            onClick={() => navigate('/pipelines')}
            style={{ cursor: 'pointer' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ApartmentOutlined style={{ fontSize: 32, color: '#1677ff' }} />
              <div>
                <Title level={5} style={{ margin: 0 }}>
                  管道管理
                </Title>
                <Text type="secondary">
                  创建和配置 RAG 检索管道，可视化编辑管道拓扑
                </Text>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card
            hoverable
            onClick={() => navigate('/knowledge')}
            style={{ cursor: 'pointer' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <BookOutlined style={{ fontSize: 32, color: '#52c41a' }} />
              <div>
                <Title level={5} style={{ margin: 0 }}>
                  知识库管理
                </Title>
                <Text type="secondary">
                  管理文档上传、分块策略和 Embedding 配置
                </Text>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}


