import React, { useState } from 'react';
import { Collapse, Descriptions, Tabs, Typography, Button, Space, message, Tag } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import type { Span } from '@entities/tracing/types';

const { Text, Paragraph } = Typography;

interface SpanDetailPanelProps {
  span: Span;
}

/** 角色标签颜色映射 */
const ROLE_COLORS: Record<string, string> = {
  system: 'purple',
  user: 'blue',
  assistant: 'green',
};

/** 截断阈值：超过此长度的消息默认折叠 */
const COLLAPSE_THRESHOLD = 500;

const SpanDetailPanel: React.FC<SpanDetailPanelProps> = ({ span }) => {
  const [activeTab, setActiveTab] = useState('input');

  /** 复制全部内容到剪贴板 */
  const handleCopyAll = async () => {
    const parts: string[] = [];
    if (span.prompt_messages?.length) {
      parts.push('=== PROMPT ===');
      for (const msg of span.prompt_messages) {
        parts.push(`[${msg.role}]\n${msg.content}`);
      }
    }
    if (span.completion_message) {
      parts.push('=== COMPLETION ===\n' + span.completion_message);
    }
    try {
      await navigator.clipboard.writeText(parts.join('\n\n'));
      message.success('已复制到剪贴板');
    } catch {
      message.error('复制失败');
    }
  };

  /** 渲染单条 prompt 消息 */
  const renderPromptMessage = (msg: { role: string; content: string }, index: number) => {
    const isLong = msg.content.length > COLLAPSE_THRESHOLD;
    const roleLabel = msg.role === 'system' ? 'System' : msg.role === 'user' ? 'User' : 'Assistant';

    return (
      <Collapse.Panel
        key={index}
        header={
          <Space>
            <Tag color={ROLE_COLORS[msg.role] || 'default'}>{roleLabel}</Tag>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {msg.content.length} 字符
            </Text>
          </Space>
        }
        // 长消息默认折叠
        collapsible={isLong ? 'header' : undefined}
      >
        <Paragraph
          copyable
          style={{ whiteSpace: 'pre-wrap', margin: 0, maxHeight: 400, overflow: 'auto' }}
        >
          {msg.content}
        </Paragraph>
      </Collapse.Panel>
    );
  };

  return (
    <Collapse defaultActiveKey={['basic']}>
      <Collapse.Panel header="基本信息" key="basic">
        <Descriptions bordered column={2}>
          <Descriptions.Item label="Span ID">{span.span_id}</Descriptions.Item>
          <Descriptions.Item label="父 Span ID">
            {span.parent_span_id || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="耗时">
            {span.duration_ms ? `${span.duration_ms}ms` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="首 Token 延迟">
            -
          </Descriptions.Item>
          <Descriptions.Item label="Token">
            {span.tokens || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="状态">{span.status}</Descriptions.Item>
        </Descriptions>
      </Collapse.Panel>

      <Collapse.Panel
        header={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', paddingRight: 16 }}>
            <span>输入/输出</span>
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={(e) => { e.stopPropagation(); handleCopyAll(); }}
            >
              复制全部
            </Button>
          </div>
        }
        key="io"
      >
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <Tabs.TabPane tab="输入 (Prompt)" key="input">
            {span.prompt_messages?.length ? (
              <Collapse accordion style={{ background: 'transparent' }}>
                {span.prompt_messages.map((msg, i) => renderPromptMessage(msg, i))}
              </Collapse>
            ) : (
              <Text type="secondary">无 prompt 数据</Text>
            )}
          </Tabs.TabPane>
          <Tabs.TabPane tab="输出 (Completion)" key="output">
            {span.completion_message ? (
              <div style={{ maxHeight: 500, overflow: 'auto', padding: '8px 12px', background: '#fafafa', borderRadius: 4, border: '1px solid #f0f0f0' }}>
                <Paragraph copyable style={{ margin: 0 }}>
                  <ReactMarkdown>{span.completion_message}</ReactMarkdown>
                </Paragraph>
              </div>
            ) : (
              <Text type="secondary">无 completion 数据</Text>
            )}
          </Tabs.TabPane>
        </Tabs>
      </Collapse.Panel>

      {span.call_parameters && (
        <Collapse.Panel header="调用参数" key="params">
          <Descriptions bordered column={1}>
            {Object.entries(span.call_parameters).map(([key, value]) => (
              <Descriptions.Item key={key} label={key}>
                {String(value)}
              </Descriptions.Item>
            ))}
          </Descriptions>
        </Collapse.Panel>
      )}

      {span.error && (
        <Collapse.Panel header="错误信息" key="error">
          <Text type="danger">{span.error}</Text>
        </Collapse.Panel>
      )}
    </Collapse>
  );
};

export { SpanDetailPanel };
