import React from 'react';
import { Alert, Button, Space, Tabs, Typography } from 'antd';
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
  const { downloadMarkdown, downloadJSON } = useReportDownload(result);

  return (
    <div style={{ marginTop: 24 }}>
      <BookInfoCard books={result.matched_books} />

      {result.contradictions && result.contradictions.length > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={
            <span>
              本报告涉及 {result.matched_books.length} 本书籍，
              发现 {result.contradictions.length} 处跨书籍观点差异
            </span>
          }
          description={
            <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
              {result.contradictions.map((c, i) => (
                <li key={i} style={{ marginBottom: 8 }}>
                  <strong>{c.topic}</strong>
                  <br />
                  {c.view_a}
                  <br />
                  {c.view_b}
                  <br />
                  <span style={{ color: '#666' }}>
                    建议: {c.resolution || '请根据实际情况判断'}
                  </span>
                </li>
              ))}
            </ul>
          }
        />
      )}

      <div
        style={{
          background: '#fafafa',
          borderRadius: 12,
          border: '1px solid #f0f0f0',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 20px',
            background: '#fff',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <Tabs
            activeKey={viewMode}
            onChange={(key) => setViewMode(key as 'markdown' | 'json')}
            style={{ marginBottom: 0 }}
            tabBarStyle={{ marginBottom: 0 }}
            items={[
              {
                key: 'markdown',
                label: (
                  <span>
                    <FileTextOutlined /> Markdown 视图
                  </span>
                ),
              },
              {
                key: 'json',
                label: (
                  <span>
                    <CodeOutlined /> JSON 数据
                  </span>
                ),
              },
            ]}
          />
          <Space>
            <Button
              icon={<DownloadOutlined />}
              onClick={downloadMarkdown}
              size="small"
            >
              Markdown
            </Button>
            <Button
              icon={<DownloadOutlined />}
              onClick={downloadJSON}
              size="small"
            >
              JSON
            </Button>
          </Space>
        </div>

        <div style={{ padding: viewMode === 'markdown' ? '20px' : '0' }}>
          {viewMode === 'markdown' ? (
            <div>
              {result.sections.map((sec) => (
                <SectionRenderer key={sec.index} section={sec} />
              ))}
              <CitationsList
                citations={result.sections.flatMap((s) => s.citations)}
              />
            </div>
          ) : (
            <pre
              style={{
                background: '#f6f8fa',
                borderRadius: 0,
                padding: 24,
                fontSize: 13,
                lineHeight: 1.6,
                overflow: 'auto',
                maxHeight: '80vh',
                fontFamily: 'SF Mono, Monaco, Consolas, monospace',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                margin: 0,
              }}
            >
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </div>
      </div>

      {result.generation_metadata.partial && (
        <Text type="warning" style={{ display: 'block', marginTop: 12 }}>
          注意：此结果为部分生成（存在超时或降级处理），内容可能不完整。
        </Text>
      )}
    </div>
  );
};
