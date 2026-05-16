/**
 * 域贡献度水平柱状图
 *
 * 展示每个域的激活准确率和贡献度。
 * 柱体颜色：≥0.8 绿色，0.6-0.8 黄色，<0.6 红色
 * 高度自适应（域数量 × 40px，最少 120px）
 */
import { Typography } from 'antd'
import type { DomainContribution } from '@/entities/rag-eval/types'

const { Text } = Typography

interface Props {
  domainContributions: DomainContribution[]
}

/** 按准确率返回颜色 */
function accuracyColor(value: number): string {
  if (value >= 0.8) return '#52c41a'
  if (value >= 0.6) return '#faad14'
  return '#ff4d4f'
}

export default function DomainContribChart({ domainContributions }: Props) {
  if (domainContributions.length === 0) {
    return <Text type="secondary">暂无域贡献数据</Text>
  }

  return (
    <div style={{ width: '100%' }}>
      {domainContributions.map((dc) => {
        const contribPct = Math.round(dc.contribution_score * 100)
        const accPct = Math.round(dc.activation_accuracy * 100)
        const barColor = accuracyColor(dc.activation_accuracy)

        return (
          <div
            key={dc.domain_id}
            style={{
              display: 'flex',
              alignItems: 'center',
              marginBottom: 12,
              height: 32,
            }}
          >
            {/* 域名称标签 */}
            <div style={{ width: 120, textAlign: 'right', paddingRight: 12, flexShrink: 0 }}>
              <Text strong style={{ fontSize: 13 }}>
                {dc.domain_name ?? dc.domain_id}
              </Text>
            </div>

            {/* 贡献度柱 */}
            <div style={{ flex: 1, position: 'relative', height: 32 }}>
              <div
                style={{
                  height: '100%',
                  width: `${contribPct}%`,
                  backgroundColor: barColor,
                  borderRadius: 4,
                  minWidth: contribPct > 0 ? 4 : 0,
                  transition: 'width 0.3s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  paddingRight: contribPct > 10 ? 8 : 0,
                }}
              >
                {contribPct > 10 && (
                  <span style={{ color: '#fff', fontSize: 12, fontWeight: 600 }}>
                    {contribPct}%
                  </span>
                )}
              </div>
              {contribPct <= 10 && (
                <span style={{ position: 'absolute', left: `${contribPct}%`, marginLeft: 8, fontSize: 12, color: '#888' }}>
                  {contribPct}%
                </span>
              )}
            </div>

            {/* 数值标签 */}
            <div style={{ width: 160, paddingLeft: 12, flexShrink: 0 }}>
              <Text style={{ fontSize: 12, color: barColor }}>
                激活 {accPct}% · {dc.chunk_count} 命中
              </Text>
            </div>
          </div>
        )
      })}
    </div>
  )
}
