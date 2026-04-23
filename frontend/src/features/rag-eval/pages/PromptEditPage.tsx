/**
 * 提示词编辑页
 * 路由: /prompt-management/:key
 */

import React, { useEffect, useState } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Space,
  Typography,
  Tag,
  Spin,
  Descriptions,
  Alert,
  Collapse,
} from 'antd';
import { notification } from '@shared/lib/notification';
import { ArrowLeftOutlined, SaveOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getPromptDetail,
  updatePrompt,
  analyzePromptImpact,
  PromptDetail,
  ImpactAnalysis,
} from '@/api/rag-eval/prompts';

const { Title } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;

const RISK_LEVEL_MAP: Record<string, { color: string; text: string }> = {
  low: { color: 'green', text: '低风险' },
  medium: { color: 'orange', text: '中风险' },
  high: { color: 'red', text: '高风险' },
};

const PromptEditPage: React.FC = () => {
  const { key } = useParams<{ key: string }>();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<PromptDetail | null>(null);
  const [impact, setImpact] = useState<ImpactAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (key) fetchDetail(key);
  }, [key]);

  const fetchDetail = async (promptKey: string) => {
    setLoading(true);
    try {
      const data = await getPromptDetail(promptKey);
      setDetail(data);
      form.setFieldsValue({
        content: data.current_version?.content || '',
        change_summary: '',
      });
    } catch (error) {
      notification.error('获取提示词详情失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    const content = form.getFieldValue('content');
    if (!content || !key) return;

    setAnalyzing(true);
    try {
      const impactData = await analyzePromptImpact(key, content);
      setImpact(impactData);
    } catch (error) {
      notification.error('分析影响失败');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSave = async () => {
    if (!key) return;
    const values = form.getFieldsValue();

    setSaving(true);
    try {
      const result = await updatePrompt(key, {
        content: values.content,
        change_summary: values.change_summary,
        created_by: 'user',
      });
      notification.success(`提示词已更新到 ${result.version}`);
      fetchDetail(key);
    } catch (error) {
      notification.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: 'block', marginTop: 100 }} />;
  }

  if (!detail) {
    return <Alert type="error" message="提示词未找到" />;
  }

  const riskInfo = impact ? RISK_LEVEL_MAP[impact.risk_level] : null;

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompt-management')}>
          返回列表
        </Button>
        <Title level={3} style={{ margin: 0 }}>{detail.metadata.name_zh}</Title>
        <Tag color="blue">{detail.metadata.category}</Tag>
        {detail.metadata.is_system && <Tag color="gold">系统内置</Tag>}
      </Space>

      <Descriptions bordered style={{ marginBottom: 16 }} size="small">
        <Descriptions.Item label="标识">{detail.metadata.prompt_key}</Descriptions.Item>
        <Descriptions.Item label="用途" span={2}>{detail.metadata.purpose}</Descriptions.Item>
        <Descriptions.Item label="当前版本">
          {detail.current_version?.version_label || '无'}
        </Descriptions.Item>
        <Descriptions.Item label="变量">
          {detail.current_version?.variables_extracted?.map((v) => (
            <Tag key={v}>{v}</Tag>
          )) || '无'}
        </Descriptions.Item>
      </Descriptions>

      <Card title="编辑提示词" style={{ marginBottom: 16 }}>
        <Form form={form} layout="vertical" onValuesChange={handleAnalyze}>
          <Form.Item name="content" label="提示词内容">
            <TextArea rows={12} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="change_summary" label="变更摘要">
            <Input placeholder="描述本次修改的原因和内容" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={saving}
              >
                保存新版本
              </Button>
              <Button
                icon={<ThunderboltOutlined />}
                onClick={handleAnalyze}
                loading={analyzing}
              >
                分析影响
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      {impact && (
        <Card title="影响分析" style={{ marginBottom: 16 }}>
          <Space style={{ marginBottom: 16 }}>
            <Tag color={riskInfo?.color}>{riskInfo?.text}</Tag>
            {impact.variable_changes.added.length > 0 && (
              <Tag color="green">
                新增变量: {impact.variable_changes.added.join(', ')}
              </Tag>
            )}
            {impact.variable_changes.removed.length > 0 && (
              <Tag color="red">
                删除变量: {impact.variable_changes.removed.join(', ')}
              </Tag>
            )}
          </Space>

          <Collapse>
            {impact.code_references.length > 0 && (
              <Panel header={`代码引用 (${impact.code_references.length} 处)`} key="code">
                <ul>
                  {impact.code_references.map((ref, i) => (
                    <li key={i}>
                      <code>{ref.file}</code> 第 {ref.line} 行
                      {ref.function && ` (${ref.function})`}
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
            {impact.config_dependencies.length > 0 && (
              <Panel header={`配置依赖 (${impact.config_dependencies.length} 项)`} key="config">
                <ul>
                  {impact.config_dependencies.map((dep, i) => (
                    <li key={i}>
                      <code>{dep.param}</code>: {dep.description}
                      {dep.current_value && ` (当前值: {dep.current_value})`}
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </Collapse>
        </Card>
      )}
    </div>
  );
};

export default PromptEditPage;
