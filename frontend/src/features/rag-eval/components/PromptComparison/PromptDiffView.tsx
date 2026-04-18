/**
 * 提示词差异展示组件（双列对比）
 */

import { Row, Col } from 'antd';

interface PromptDiffViewProps {
  currentContent: string;
  suggestedContent: string;
}

interface DiffLine {
  type: 'added' | 'removed' | 'unchanged';
  content: string;
}

/**
 * 简单的行级差异计算
 */
function computeDiffLines(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split('\n');
  const newLines = newText.split('\n');
  const lines: DiffLine[] = [];

  const maxLen = Math.max(oldLines.length, newLines.length);

  for (let i = 0; i < maxLen; i++) {
    const oldLine = i < oldLines.length ? oldLines[i] : undefined;
    const newLine = i < newLines.length ? newLines[i] : undefined;

    if (oldLine === undefined) {
      // 新增行
      lines.push({ type: 'added', content: newLine! });
    } else if (newLine === undefined) {
      // 删除行
      lines.push({ type: 'removed', content: oldLine });
    } else if (oldLine === newLine) {
      // 未变行
      lines.push({ type: 'unchanged', content: oldLine });
    } else {
      // 修改行：先显示删除，再显示新增
      lines.push({ type: 'removed', content: oldLine });
      lines.push({ type: 'added', content: newLine });
    }
  }

  return lines;
}

/**
 * 渲染单行差异
 */
function renderDiffLine(line: DiffLine, isLeft: boolean): React.ReactNode {
  const prefix = line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' ';
  const bgColor =
    line.type === 'added'
      ? '#f6ffed'
      : line.type === 'removed'
        ? '#fff1f0'
        : 'transparent';

  const textColor =
    line.type === 'added'
      ? '#52c41a'
      : line.type === 'removed'
        ? '#ff4d4f'
        : 'inherit';

  // 左侧面板只显示 unchanged 和 removed
  if (isLeft && line.type === 'added') return null;
  // 右侧面板只显示 unchanged 和 added
  if (!isLeft && line.type === 'removed') return null;

  return (
    <div
      style={{
        background: bgColor,
        padding: '2px 8px',
        fontFamily: 'monospace',
        fontSize: 13,
        lineHeight: '1.6',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
      }}
    >
      <span style={{ color: textColor, marginRight: 8, userSelect: 'none' }}>
        {prefix}
      </span>
      <span style={{ color: textColor }}>{line.content}</span>
    </div>
  );
}

export default function PromptDiffView({ currentContent, suggestedContent }: PromptDiffViewProps) {
  const diffLines_result = computeDiffLines(currentContent, suggestedContent);

  return (
    <Row gutter={16}>
      {/* 左侧：当前版本 */}
      <Col span={12}>
        <div
          style={{
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            overflow: 'auto',
            maxHeight: 400,
          }}
        >
          <div
            style={{
              padding: '8px 12px',
              background: '#fafafa',
              borderBottom: '1px solid #d9d9d9',
              fontWeight: 'bold',
            }}
          >
            当前版本
          </div>
          <div>
            {diffLines_result.map((line, index) => {
              const rendered = renderDiffLine(line, true);
              return rendered ? <div key={`left-${index}`}>{rendered}</div> : null;
            })}
          </div>
        </div>
      </Col>

      {/* 右侧：建议版本 */}
      <Col span={12}>
        <div
          style={{
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            overflow: 'auto',
            maxHeight: 400,
          }}
        >
          <div
            style={{
              padding: '8px 12px',
              background: '#fafafa',
              borderBottom: '1px solid #d9d9d9',
              fontWeight: 'bold',
            }}
          >
            建议版本
          </div>
          <div>
            {diffLines_result.map((line, index) => {
              const rendered = renderDiffLine(line, false);
              return rendered ? <div key={`right-${index}`}>{rendered}</div> : null;
            })}
          </div>
        </div>
      </Col>
    </Row>
  );
}
