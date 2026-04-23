/**
 * DiffViewer 通用对比组件
 * 支持 JSON 和文本两种对比模式，支持统一/分栏展示
 */

import { useState } from 'react';
import { Card, Segmented, Tag } from 'antd';
import { SplitCellsOutlined, ColumnWidthOutlined } from '@ant-design/icons';

export interface DiffItem {
  key: string;
  before: string | null;
  after: string | null;
  type: 'added' | 'removed' | 'modified';
}

export interface DiffViewerProps {
  /** 对比模式：json（键值对比）或 text（纯文本对比） */
  mode?: 'json' | 'text';
  /** JSON 模式下的差异数据 */
  diffItems?: DiffItem[];
  /** 文本模式下的原始文本 */
  beforeText?: string;
  afterText?: string;
  /** 展示模式：split（分栏）或 unified（统一） */
  viewMode?: 'split' | 'unified';
  /** 高度 */
  height?: number;
}

const TYPE_COLORS: Record<string, string> = {
  added: 'green',
  removed: 'red',
  modified: 'orange',
};

const TYPE_LABELS: Record<string, string> = {
  added: '新增',
  removed: '删除',
  modified: '修改',
};

export default function DiffViewer({
  mode = 'json',
  diffItems = [],
  beforeText = '',
  afterText = '',
  viewMode = 'split',
  height = 400,
}: DiffViewerProps) {
  const [localViewMode, setLocalViewMode] = useState<'split' | 'unified'>(viewMode);

  if (mode === 'text') {
    return (
      <Card
        title="文本对比"
        extra={
          <Segmented
            value={localViewMode}
            onChange={(val) => setLocalViewMode(val as 'split' | 'unified')}
            options={[
              { label: '分栏', value: 'split', icon: <SplitCellsOutlined /> },
              { label: '统一', value: 'unified', icon: <ColumnWidthOutlined /> },
            ]}
          />
        }
      >
        {localViewMode === 'split' ? (
          <div style={{ display: 'flex', gap: 8, height }}>
            <div style={{ flex: 1, overflow: 'auto' }}>
              <div style={{ fontWeight: 'bold', marginBottom: 8, color: '#ff4d4f' }}>修改前</div>
              <pre style={{ margin: 0, padding: 12, background: '#fff1f0', borderRadius: 4, fontSize: 12 }}>
                {beforeText || '（空）'}
              </pre>
            </div>
            <div style={{ flex: 1, overflow: 'auto' }}>
              <div style={{ fontWeight: 'bold', marginBottom: 8, color: '#52c41a' }}>修改后</div>
              <pre style={{ margin: 0, padding: 12, background: '#f6ffed', borderRadius: 4, fontSize: 12 }}>
                {afterText || '（空）'}
              </pre>
            </div>
          </div>
        ) : (
          <div style={{ height, overflow: 'auto' }}>
            <pre style={{ margin: 0, padding: 12, background: '#fafafa', borderRadius: 4, fontSize: 12 }}>
              {renderUnifiedTextDiff(beforeText, afterText)}
            </pre>
          </div>
        )}
      </Card>
    );
  }

  // JSON 模式
  return (
    <Card
      title="配置对比"
      extra={
        <Segmented
          value={localViewMode}
          onChange={(val) => setLocalViewMode(val as 'split' | 'unified')}
          options={[
            { label: '分栏', value: 'split', icon: <SplitCellsOutlined /> },
            { label: '统一', value: 'unified', icon: <ColumnWidthOutlined /> },
          ]}
        />
      }
    >
      {localViewMode === 'split' ? (
        <div style={{ display: 'flex', gap: 8, height, overflow: 'auto' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 'bold', marginBottom: 8, color: '#ff4d4f' }}>修改前</div>
            {diffItems
              .filter((item) => item.type !== 'added')
              .map((item) => (
                <div
                  key={item.key}
                  style={{
                    padding: '8px 12px',
                    marginBottom: 4,
                    borderRadius: 4,
                    background: item.type === 'removed' ? '#fff1f0' : '#fafafa',
                    fontSize: 12,
                  }}
                >
                  <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{item.key}</div>
                  <div style={{ color: item.type === 'removed' ? '#ff4d4f' : '#666' }}>
                    {item.before || '（无）'}
                  </div>
                </div>
              ))}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 'bold', marginBottom: 8, color: '#52c41a' }}>修改后</div>
            {diffItems
              .filter((item) => item.type !== 'removed')
              .map((item) => (
                <div
                  key={item.key}
                  style={{
                    padding: '8px 12px',
                    marginBottom: 4,
                    borderRadius: 4,
                    background: item.type === 'added' ? '#f6ffed' : item.type === 'modified' ? '#fffbe6' : '#fafafa',
                    fontSize: 12,
                  }}
                >
                  <div style={{ fontWeight: 'bold', marginBottom: 4 }}>
                    {item.key}{' '}
                    <Tag color={TYPE_COLORS[item.type]} style={{ fontSize: 10 }}>
                      {TYPE_LABELS[item.type]}
                    </Tag>
                  </div>
                  <div style={{ color: item.type === 'added' ? '#52c41a' : item.type === 'modified' ? '#faad14' : '#666' }}>
                    {item.after || '（无）'}
                  </div>
                </div>
              ))}
          </div>
        </div>
      ) : (
        <div style={{ height, overflow: 'auto' }}>
          {diffItems.map((item) => (
            <div
              key={item.key}
              style={{
                padding: '8px 12px',
                marginBottom: 4,
                borderRadius: 4,
                background:
                  item.type === 'added'
                    ? '#f6ffed'
                    : item.type === 'removed'
                    ? '#fff1f0'
                    : '#fffbe6',
                fontSize: 12,
              }}
            >
              <div style={{ fontWeight: 'bold', marginBottom: 4 }}>
                {item.key}{' '}
                <Tag color={TYPE_COLORS[item.type]} style={{ fontSize: 10 }}>
                  {TYPE_LABELS[item.type]}
                </Tag>
              </div>
              {item.type !== 'added' && (
                <div style={{ color: '#ff4d4f', marginBottom: 2 }}>
                  - {item.before || '（无）'}
                </div>
              )}
              {item.type !== 'removed' && (
                <div style={{ color: '#52c41a' }}>
                  + {item.after || '（无）'}
                </div>
              )}
            </div>
          ))}
          {diffItems.length === 0 && (
            <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
              无差异
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

/**
 * 简单的文本行级 diff（统一模式）
 */
function renderUnifiedTextDiff(before: string, after: string): string {
  const beforeLines = before.split('\n');
  const afterLines = after.split('\n');
  const result: string[] = [];

  const maxLen = Math.max(beforeLines.length, afterLines.length);
  for (let i = 0; i < maxLen; i++) {
    const bLine = beforeLines[i];
    const aLine = afterLines[i];

    if (bLine === undefined) {
      result.push(`+ ${aLine}`);
    } else if (aLine === undefined) {
      result.push(`- ${bLine}`);
    } else if (bLine !== aLine) {
      result.push(`- ${bLine}`);
      result.push(`+ ${aLine}`);
    } else {
      result.push(`  ${bLine}`);
    }
  }

  return result.join('\n');
}
