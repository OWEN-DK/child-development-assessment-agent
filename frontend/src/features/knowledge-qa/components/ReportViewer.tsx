import React from 'react';
import { Button, Card, Tabs, Typography } from 'antd';
import {
  CodeOutlined,
  DownloadOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { BookInfoCard } from './BookInfoCard';
import { CitationsList } from './CitationsList';
import { SectionRenderer } from './SectionRenderer';
import { useKnowledgeQAStore } from '../stores/knowledgeQAStore';
import { useReportDownload } from '../hooks/useReportDownload';
import type { KnowledgeQAResponse } from '../types';

const { Text } = Typography;

interface Props {
  result: KnowledgeQAResponse;
}

export const ReportViewer: React.FC<Props> = ({ result }) => {
  const { viewMode, setViewMode } = useKnowledgeQAStore();
  const { downloadMarkdown } = useReportDownload(result);

  return (
    <div style={{ marginTop: 24 }}>
      <BookInfoCard books={result.matched_books} />

      <Card>
        <Tabs
          activeKey={viewMode}
          onChange={(key) => setViewMode(key as 'markdown' | 'json')}
          tabBarExtraContent={
            <Button
              icon={<DownloadOutlined />}
              onClick={downloadMarkdown}
            >
              Markdown
            </Button>
          }
          items={[
            {
              key: 'markdown',
              label: (
                <span>
                  <FileTextOutlined /> Markdown 视图
                </span>
              ),
              children: (
                <div>
                  {result.sections.map((sec) => (
                    <SectionRenderer key={sec.index} section={sec} />
                  ))}
                  <CitationsList
                    citations={result.sections.flatMap((s) => s.citations)}
                  />
                </div>
              ),
            },
            {
              key: 'json',
              label: (
                <span>
                  <CodeOutlined /> JSON 数据
                </span>
              ),
              children: (
                <pre
                  style={{
                    background: '#f6f8fa',
                    borderRadius: 8,
                    padding: 24,
                    fontSize: 13,
                    lineHeight: 1.6,
                    overflow: 'auto',
                    maxHeight: '80vh',
                    fontFamily: 'SF Mono, Monaco, Consolas, monospace',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(result, null, 2)}
                </pre>
              ),
            },
          ]}
        />
      </Card>

      {result.generation_metadata.partial && (
        <Text type="warning" style={{ display: 'block', marginTop: 12 }}>
          注意：此结果为部分生成（存在超时或降级处理），内容可能不完整。
        </Text>
      )}
    </div>
  );
};
