import React from 'react';
import Markdown from 'react-markdown';
import { Card, Button, Typography, Space, Collapse, Spin } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import type { FinalReport } from '@entities/assessment/types';

const { Title, Paragraph } = Typography;
const { Panel } = Collapse;

interface ReportViewerProps {
  report: FinalReport;
  onBack: () => void;
  isStreaming?: boolean;
}

export const ReportViewer: React.FC<ReportViewerProps> = ({ report, onBack, isStreaming = false }) => {
  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
        返回编辑
      </Button>

      <Card 
        title={
          <Title level={3} style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
            评估报告
            {isStreaming && <Spin size="small" />}
          </Title>
        }
      >
        <Typography>
          <div className="markdown-body">
            {/* 使用 react-markdown 渲染，可以通过 CSS 自定义样式，或者使用 Ant Design 的 Typography 样式 */}
            <Markdown
              components={{
                h1: ({children}) => <Title level={1}>{children}</Title>,
                h2: ({children}) => <Title level={2}>{children}</Title>,
                h3: ({children}) => <Title level={3}>{children}</Title>,
                h4: ({children}) => <Title level={4}>{children}</Title>,
                p: ({children}) => <Paragraph>{children}</Paragraph>,
                li: ({children}) => <li><Paragraph>{children}</Paragraph></li>,
              }}
            >
              {report.markdown_content || ''}
            </Markdown>
            {/* 流式生成中的光标效果 */}
            {isStreaming && (
              <span 
                style={{ 
                  display: 'inline-block',
                  width: '8px',
                  height: '1em',
                  background: '#1890ff',
                  marginLeft: '2px',
                  animation: 'blink 1s infinite',
                  verticalAlign: 'text-bottom'
                }} 
              />
            )}
          </div>
        </Typography>
      </Card>
      
      {/* 结构化数据展示 */}
      {Object.keys(report.structured_data || {}).length > 0 && (
        <Collapse>
          <Panel header="查看详细结构化数据" key="1">
            <pre style={{ background: '#f5f5f5', padding: '16px', borderRadius: '4px', overflow: 'auto' }}>
              {JSON.stringify(report.structured_data, null, 2)}
            </pre>
          </Panel>
        </Collapse>
      )}

      {/* 添加光标闪烁动画 */}
      <style>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </Space>
  );
};
