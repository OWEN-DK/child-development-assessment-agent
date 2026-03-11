import React from 'react';
import Markdown from 'react-markdown';
import { Card, Button, Typography, Space, Collapse } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { FinalReport } from '../models';

const { Title, Paragraph } = Typography;
const { Panel } = Collapse;

interface ReportViewerProps {
  report: FinalReport;
  onBack: () => void;
}

export const ReportViewer: React.FC<ReportViewerProps> = ({ report, onBack }) => {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
        返回编辑
      </Button>

      <Card title={<Title level={3} style={{ margin: 0 }}>评估报告</Title>}>
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
              {report.markdown_content}
            </Markdown>
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
    </Space>
  );
};
