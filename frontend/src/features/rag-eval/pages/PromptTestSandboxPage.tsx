/**
 * 提示词测试沙箱页
 * 路由: /rag-eval/prompts/:id/test
 */

import React, { useEffect, useState } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Space,
  Typography,
  Spin,
  message,
  Select,
  Tag,
  Descriptions,
  Alert,
  Row,
  Col,
} from 'antd';
import { ArrowLeftOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { getPromptDetail, testPrompt, PromptDetail, PromptTestResult } from '@/api/rag-eval/prompts';

const { Title } = Typography;
const { TextArea } = Input;

const PromptTestSandboxPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<PromptDetail | null>(null);
  const [testResult, setTestResult] = useState<PromptTestResult | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (id) fetchDetail(id);
  }, [id]);

  const fetchDetail = async (promptKey: string) => {
    setLoading(true);
    try {
      const data = await getPromptDetail(promptKey);
      setDetail(data);

      // 初始化变量表单
      const variables: Record<string, any> = {};
      data.current_version?.variables_extracted?.forEach((v) => {
        variables[v] = '';
      });
      form.setFieldsValue({ variables });
    } catch (error) {
      message.error('获取提示词详情失败');
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (!id) return;
    const values = form.getFieldsValue();

    setTesting(true);
    try {
      const result = await testPrompt(
        id,
        values.variables || {},
        values.version
      );
      setTestResult(result);
    } catch (error) {
      message.error('测试失败');
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: 'block', marginTop: 100 }} />;
  }

  if (!detail) {
    return <Alert type="error" message="提示词未找到" />;
  }

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/rag-eval/prompts/${id}`)}>
          返回
        </Button>
        <Title level={3} style={{ margin: 0 }}>
          {detail.metadata.name_zh} - 测试沙箱
        </Title>
      </Space>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="测试参数" style={{ marginBottom: 16 }}>
            <Form form={form} layout="vertical">
              <Form.Item name="version" label="版本">
                <Select
                  options={detail.versions.map((v) => ({
                    label: v.version_label,
                    value: v.version_label,
                  }))}
                  placeholder="选择版本（默认最新）"
                  allowClear
                />
              </Form.Item>

              <Form.Item label="变量输入">
                {detail.current_version?.variables_extracted?.map((v) => (
                  <Form.Item key={v} name={['variables', v]} label={v} style={{ marginBottom: 8 }}>
                    <Input placeholder={`输入 ${v} 的值`} />
                  </Form.Item>
                )) || <Tag>无变量</Tag>}
              </Form.Item>

              <Form.Item>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={handleTest}
                  loading={testing}
                >
                  运行测试
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col span={12}>
          <Card title="测试结果" style={{ marginBottom: 16 }}>
            {testResult ? (
              <>
                {testResult.variables_missing.length > 0 && (
                  <Alert
                    type="warning"
                    message="未使用的变量"
                    description={testResult.variables_missing.join(', ')}
                    style={{ marginBottom: 16 }}
                  />
                )}
                <Descriptions size="small" style={{ marginBottom: 16 }}>
                  <Descriptions.Item label="使用的变量">
                    {testResult.variables_used.map((v) => (
                      <Tag key={v} color="green">{v}</Tag>
                    ))}
                  </Descriptions.Item>
                </Descriptions>
                <TextArea
                  value={testResult.rendered_prompt}
                  rows={15}
                  readOnly
                  style={{ fontFamily: 'monospace' }}
                />
              </>
            ) : (
              <Alert type="info" message="输入变量后点击运行测试" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PromptTestSandboxPage;
