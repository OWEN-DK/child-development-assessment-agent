import React, { useState } from 'react';
import { Collapse, Descriptions, Tabs, Typography } from 'antd';
import type { Span } from '@/types/tracing';

const { Text } = Typography;

interface SpanDetailPanelProps {
  span: Span;
}

export const SpanDetailPanel: React.FC<SpanDetailPanelProps> = ({ span }) => {
  const [activeTab, setActiveTab] = useState('input');

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

      <Collapse.Panel header="输入/输出" key="io">
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <Tabs.TabPane tab="输入 (Prompt)" key="input">
            <Text
              copyable
              style={{ whiteSpace: 'pre-wrap', display: 'block' }}
            >
              {span.prompt_messages
                ? JSON.stringify(span.prompt_messages, null, 2)
                : '-'}
            </Text>
          </Tabs.TabPane>
          <Tabs.TabPane tab="输出 (Completion)" key="output">
            <Text
              copyable
              style={{ whiteSpace: 'pre-wrap', display: 'block' }}
            >
              {span.completion_message || '-'}
            </Text>
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
