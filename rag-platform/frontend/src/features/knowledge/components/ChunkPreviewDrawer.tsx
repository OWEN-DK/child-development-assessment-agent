/**
 * 分块预览侧滑面板
 *
 * 展示选中文档的分块结果，包含统计信息和块列表
 */
import { Drawer, Card, Tag, Spin, Empty, Typography, Space } from 'antd'
import { useKnowledgeBaseStore } from '@/features/knowledge/stores/knowledgeBaseStore'

const { Text, Paragraph } = Typography

export interface ChunkPreviewDrawerProps {
  open: boolean
  onClose: () => void
}

/** 格式化字符数 */
function formatCharCount(count: number): string {
  return count >= 1000 ? `${(count / 1000).toFixed(1)}k` : String(count)
}

export default function ChunkPreviewDrawer({ open, onClose }: ChunkPreviewDrawerProps) {
  const chunkPreview = useKnowledgeBaseStore((s) => s.chunkPreview)
  const chunkPreviewLoading = useKnowledgeBaseStore((s) => s.chunkPreviewLoading)
  const chunkTotalCount = useKnowledgeBaseStore((s) => s.chunkTotalCount)

  // 统计信息
  const totalChars = chunkPreview.reduce((sum, c) => sum + c.char_count, 0)
  const avgChars = chunkPreview.length > 0 ? Math.round(totalChars / chunkPreview.length) : 0
  const totalTokens = chunkPreview.reduce((sum, c) => sum + c.token_estimate, 0)

  return (
    <Drawer
      title="分块预览"
      placement="right"
      width={560}
      open={open}
      onClose={onClose}
    >
      {chunkPreviewLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : chunkPreview.length === 0 ? (
        <Empty description="暂无分块数据" />
      ) : (
        <>
          {/* 统计摘要 */}
          <Card size="small" style={{ marginBottom: 16 }}>
            <Space size={24}>
              <div>
                <Text type="secondary">总块数</Text>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{chunkTotalCount}</div>
              </div>
              <div>
                <Text type="secondary">总字符数</Text>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{totalChars.toLocaleString()}</div>
              </div>
              <div>
                <Text type="secondary">平均块大小</Text>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{avgChars}</div>
              </div>
              <div>
                <Text type="secondary">预估 Token</Text>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{totalTokens.toLocaleString()}</div>
              </div>
            </Space>
          </Card>

          {/* 分块列表 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {chunkPreview.map((chunk) => (
              <Card key={chunk.chunk_index} size="small" title={
                <span>
                  #{chunk.chunk_index}
                  <Tag style={{ marginLeft: 8 }}>
                    {formatCharCount(chunk.char_count)} 字符
                  </Tag>
                  <Tag>{chunk.token_estimate} tokens</Tag>
                </span>
              }>
                <Paragraph
                  ellipsis={{ rows: 4, expandable: true, symbol: '展开' }}
                  style={{ margin: 0, fontSize: 13 }}
                >
                  {chunk.content}
                </Paragraph>
              </Card>
            ))}
          </div>
        </>
      )}
    </Drawer>
  )
}
