import React, { useState } from 'react';
import { Tree, Tag } from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { Span } from '@entities/tracing/types';

interface SpanTreeViewProps {
  spans: Span[];
  onSpanClick: (span: Span) => void;
}

export const SpanTreeView: React.FC<SpanTreeViewProps> = ({ spans, onSpanClick }) => {
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);

  const buildTree = (spanList: Span[]): DataNode[] => {
    const spanMap = new Map<string, Span>();
    const rootNodes: DataNode[] = [];
    const childrenMap = new Map<string, Span[]>();

    spanList.forEach((span) => {
      if (!span.span_id) return;
      spanMap.set(span.span_id, span);
      if (!span.parent_span_id) {
        rootNodes.push(spanToDataNode(span));
      } else {
        if (!childrenMap.has(span.parent_span_id)) {
          childrenMap.set(span.parent_span_id, []);
        }
        childrenMap.get(span.parent_span_id)!.push(span);
      }
    });

    const attachChildren = (node: DataNode) => {
      const children = childrenMap.get(node.key as string);
      if (children) {
        node.children = children.map((child) => {
          const childNode = spanToDataNode(child);
          attachChildren(childNode);
          return childNode;
        });
      }
    };

    rootNodes.forEach(attachChildren);
    return rootNodes;
  };

  const spanToDataNode = (span: Span): DataNode => ({
    key: span.span_id || '',
    title: (
      <div onClick={() => onSpanClick(span)} style={{ cursor: 'pointer', padding: '2px 0' }}>
        <span>{span.name}</span>
        <Tag color="blue" style={{ marginLeft: 8 }}>
          {span.duration_ms}ms
        </Tag>
        {span.tokens && <Tag>{span.tokens} tokens</Tag>}
        {span.status === 'error' && <Tag color="red">Error</Tag>}
      </div>
    ),
  });

  const treeData = buildTree(spans);

  return (
    <Tree
      treeData={treeData}
      expandedKeys={expandedKeys}
      onExpand={(keys) => setExpandedKeys(keys)}
      defaultExpandAll
      showLine
    />
  );
};
