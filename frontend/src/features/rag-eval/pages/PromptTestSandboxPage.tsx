import { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Card, Button, Space, Typography, Tag, Input, Select, Alert, Spin, Form, Row, Col, Descriptions, message,
} from 'antd';
import { ArrowLeftOutlined, PlayCircleOutlined, ClearOutlined } from '@ant-design/icons';
import { usePromptDetail, useTestPrompt } from '../hooks/usePrompts';
import type { PromptTestResult } from '@entities/rag-eval';
import { getPromptCategoryLabel, getPromptCategoryColor } from '@entities/rag-eval';

const { Title, Text, Paragraph } = Typography;

export function PromptTestSandboxPage() {
  const { key } = useParams<{ key: string }>();
  const navigate = useNavigate();
  const promptKey = key || '';

  const { data: detail, isLoading } = usePromptDetail(promptKey);
  const testMutation = useTestPrompt();

  const [selectedVersion, setSelectedVersion] = useState<string | undefined>();
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [result, setResult] = useState<PromptTestResult | null>(null);

  // 初始化变量
  useEffect(() => {
    if (detail?.current_version?.variables_extracted) {
      const initial: Record<string, string> = {};
      for (const v of detail.current_version.variables_extracted) {
        initial[v] = '';
      }
      setVariables(initial);
    }
  }, [detail?.current_version?.variables_extracted]);

  const handleVariableChange = useCallback((name: string, value: string) => {
    setVariables((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleTest = useCallback(async () => {
    if (!promptKey) return;
    try {
      const testResult = await testMutation.mutateAsync({
        prompt_key: promptKey,
        version: selectedVersion,
        variables,
      });
      setResult(testResult);
    } catch {
      message.error('测试失败');
    }
  }, [promptKey, selectedVersion, variables, testMutation]);

  const handleClear = useCallback(() => {
    setResult(null);
    setVariables((prev) => {
      const cleared: Record<string, string> = {};
      for (const key of Object.keys(prev)) {
        cleared[key] = '';
      }
      return cleared;
    });
  }, []);

  if (isLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (!detail) {
    return <Alert type="error" message="加载提示词详情失败" showIcon />;
  }

  const { metadata, versions } = detail;
  const variableNames = detail.current_version?.variables_extracted || [];

  return (
    <div>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompt-management')}>
            返回
          </Button>
          <Title level={4} style={{ margin: 0 }}>测试沙箱</Title>
          <Text type="secondary">— {metadata.name_zh}</Text>
          <Tag color={getPromptCategoryColor(metadata.category)}>
            {getPromptCategoryLabel(metadata.category)}
          </Tag>
        </Space>
      </div>

      <Row gutter={16}>
        {/* 左侧：输入区 */}
        <Col xs={24} lg={12}>
          <Card size="small" title="测试参数" style={{ marginBottom: 16 }}>
            <Form layout="vertical" size="small">
              <Form.Item label="版本（可选）">
                <Select
                  placeholder="默认使用当前版本"
                  allowClear
                  value={selectedVersion}
                  onChange={setSelectedVersion}
                  options={versions.map((v) => ({
                    value: v.version_label,
                    label: `${v.version_label}${v.change_summary ? ` - ${v.change_summary}` : ''}`,
                  }))}
                />
              </Form.Item>
            </Form>
          </Card>

          <Card
            size="small"
            title={
              <Space>
                <Text>变量输入</Text>
                {variableNames.length > 0 && <Tag color="blue">{variableNames.length} 个变量</Tag>}
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            {variableNames.length === 0 ? (
              <Text type="secondary">该提示词没有变量</Text>
            ) : (
              <Form layout="vertical" size="small">
                {variableNames.map((varName) => (
                  <Form.Item key={varName} label={<Text code>{`{${varName}}`}</Text>}>
                    <Input
                      value={variables[varName] || ''}
                      onChange={(e) => handleVariableChange(varName, e.target.value)}
                      placeholder={`输入 ${varName} 的值...`}
                    />
                  </Form.Item>
                ))}
              </Form>
            )}
          </Card>

          <Space>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleTest}
              loading={testMutation.isPending}
            >
              执行测试
            </Button>
            <Button icon={<ClearOutlined />} onClick={handleClear}>
              清空结果
            </Button>
          </Space>
        </Col>

        {/* 右侧：结果区 */}
        <Col xs={24} lg={12}>
          {result && (
            <>
              {result.variables_missing.length > 0 && (
                <Alert
                  type="warning"
                  message="缺失变量"
                  description={
                    <Space wrap>
                      {result.variables_missing.map((v) => (
                        <Tag key={v} color="warning">{`{${v}}`}</Tag>
                      ))}
                    </Space>
                  }
                  showIcon
                  style={{ marginBottom: 16 }}
                />
              )}

              <Card size="small" title="渲染结果" style={{ marginBottom: 16 }}>
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
                  {result.rendered_prompt}
                </Paragraph>
              </Card>

              <Card size="small" title="测试信息">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="使用变量">
                    {result.variables_used.length > 0 ? (
                      <Space wrap>
                        {result.variables_used.map((v) => (
                          <Tag key={v} color="blue">{`{${v}}`}</Tag>
                        ))}
                      </Space>
                    ) : (
                      <Text type="secondary">无</Text>
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label="渲染长度">
                    {result.rendered_prompt.length} 字符
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </>
          )}

          {!result && (
            <Card size="small">
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
                <PlayCircleOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                <div>填写变量后点击"执行测试"查看渲染结果</div>
              </div>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
}
