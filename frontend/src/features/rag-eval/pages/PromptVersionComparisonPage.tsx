import { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Card, Select, Button, Space, Typography, Tag, Descriptions, Alert, Spin, Row, Col,
} from 'antd';
import { ArrowLeftOutlined, SwapOutlined } from '@ant-design/icons';
import { usePromptDetail, useCompareVersions } from '../hooks/usePrompts';
import { formatTimestamp } from '@entities/rag-eval';

const { Title, Text, Paragraph } = Typography;

export function PromptVersionComparisonPage() {
  const { key } = useParams<{ key: string }>();
  const navigate = useNavigate();
  const promptKey = key || '';

  const { data: detail, isLoading: detailLoading } = usePromptDetail(promptKey);

  const versions = detail?.versions || [];
  const versionOptions = versions.map((v) => ({
    value: v.version_label,
    label: `${v.version_label} (${v.created_at ? formatTimestamp(v.created_at) : '-'})`,
  }));

  const [version1, setVersion1] = useState<string>('');
  const [version2, setVersion2] = useState<string>('');

  // 默认选中最近两个版本
  useEffect(() => {
    if (versions.length >= 2 && !version1 && !version2) {
      setVersion1(versions[1].version_label);
      setVersion2(versions[0].version_label);
    } else if (versions.length === 1 && !version1) {
      setVersion1(versions[0].version_label);
    }
  }, [versions, version1, version2]);

  const canCompare = version1 && version2 && version1 !== version2;

  const { data: comparison, isLoading: compareLoading, isError } = useCompareVersions(
    promptKey,
    version1,
    version2,
  );

  const version1Data = useMemo(() => {
    if (comparison) return comparison.version_1;
    return versions.find((v) => v.version_label === version1);
  }, [comparison, versions, version1]);

  const version2Data = useMemo(() => {
    if (comparison) return comparison.version_2;
    return versions.find((v) => v.version_label === version2);
  }, [comparison, versions, version2]);

  if (detailLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  return (
    <div>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompt-management')}>
            返回
          </Button>
          <Title level={4} style={{ margin: 0 }}>版本对比</Title>
          {detail?.metadata && (
            <Text type="secondary">— {detail.metadata.name_zh}</Text>
          )}
        </Space>
      </div>

      {/* 版本选择器 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space align="center" wrap>
          <Text>版本 A：</Text>
          <Select
            placeholder="选择版本"
            value={version1 || undefined}
            onChange={setVersion1}
            options={versionOptions}
            style={{ width: 250 }}
          />
          <SwapOutlined style={{ color: '#999' }} />
          <Text>版本 B：</Text>
          <Select
            placeholder="选择版本"
            value={version2 || undefined}
            onChange={setVersion2}
            options={versionOptions}
            style={{ width: 250 }}
          />
        </Space>
      </Card>

      {!canCompare && (
        <Alert
          type="info"
          message="请选择两个不同的版本进行对比"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {isError && (
        <Alert
          type="error"
          message="版本对比失败"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {compareLoading && (
        <Spin size="large" style={{ display: 'block', margin: '50px auto' }} />
      )}

      {/* 对比结果 */}
      {comparison && (
        <>
          {/* 统计信息 */}
          <Card size="small" title="变更统计" style={{ marginBottom: 16 }}>
            <Descriptions column={3} size="small">
              <Descriptions.Item label="版本 A 长度">
                {comparison.diff.version_1_length} 字符
              </Descriptions.Item>
              <Descriptions.Item label="版本 B 长度">
                {comparison.diff.version_2_length} 字符
              </Descriptions.Item>
              <Descriptions.Item label="字符变化">
                <Tag color={comparison.diff.added_chars > 0 ? 'green' : comparison.diff.added_chars < 0 ? 'red' : 'default'}>
                  {comparison.diff.added_chars > 0 ? '+' : ''}{comparison.diff.added_chars}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            {comparison.version_1.change_summary && (
              <Paragraph style={{ margin: '8px 0 0' }}>
                <Text type="secondary">版本 A 说明：</Text> {comparison.version_1.change_summary}
              </Paragraph>
            )}
            {comparison.version_2.change_summary && (
              <Paragraph style={{ margin: '4px 0 0' }}>
                <Text type="secondary">版本 B 说明：</Text> {comparison.version_2.change_summary}
              </Paragraph>
            )}
          </Card>

          {/* 并排对比 */}
          <Row gutter={16}>
            <Col xs={24} lg={12}>
              <Card
                size="small"
                title={
                  <Space>
                    <Text strong>版本 A</Text>
                    <Tag>{comparison.version_1.version_label}</Tag>
                  </Space>
                }
              >
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {comparison.version_1.created_at ? formatTimestamp(comparison.version_1.created_at) : '-'}
                    {comparison.version_1.created_by && ` · ${comparison.version_1.created_by}`}
                  </Text>
                </div>
                <Paragraph
                  style={{
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'monospace',
                    fontSize: 13,
                    background: '#fafafa',
                    padding: 12,
                    borderRadius: 6,
                    maxHeight: 500,
                    overflow: 'auto',
                  }}
                >
                  {comparison.version_1.content}
                </Paragraph>
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card
                size="small"
                title={
                  <Space>
                    <Text strong>版本 B</Text>
                    <Tag>{comparison.version_2.version_label}</Tag>
                  </Space>
                }
              >
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {comparison.version_2.created_at ? formatTimestamp(comparison.version_2.created_at) : '-'}
                    {comparison.version_2.created_by && ` · ${comparison.version_2.created_by}`}
                  </Text>
                </div>
                <Paragraph
                  style={{
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'monospace',
                    fontSize: 13,
                    background: '#fafafa',
                    padding: 12,
                    borderRadius: 6,
                    maxHeight: 500,
                    overflow: 'auto',
                  }}
                >
                  {comparison.version_2.content}
                </Paragraph>
              </Card>
            </Col>
          </Row>
        </>
      )}

      {/* 无对比数据时展示版本内容 */}
      {!comparison && version1Data && version2Data && canCompare && !compareLoading && (
        <Row gutter={16}>
          <Col xs={24} lg={12}>
            <Card size="small" title={<Space><Text strong>版本 A</Text><Tag>{version1Data.version_label}</Tag></Space>}>
              <Paragraph
                style={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  fontSize: 13,
                  background: '#fafafa',
                  padding: 12,
                  borderRadius: 6,
                  maxHeight: 500,
                  overflow: 'auto',
                }}
              >
                {version1Data.content}
              </Paragraph>
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card size="small" title={<Space><Text strong>版本 B</Text><Tag>{version2Data.version_label}</Tag></Space>}>
              <Paragraph
                style={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  fontSize: 13,
                  background: '#fafafa',
                  padding: 12,
                  borderRadius: 6,
                  maxHeight: 500,
                  overflow: 'auto',
                }}
              >
                {version2Data.content}
              </Paragraph>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}
