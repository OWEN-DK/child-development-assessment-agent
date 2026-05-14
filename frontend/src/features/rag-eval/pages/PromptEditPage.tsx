import { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Card, Button, Space, Typography, Tag, Input, Modal, List, Alert, Descriptions, message, Spin, Row, Col,
} from 'antd';
import {
  SaveOutlined, AuditOutlined, ArrowLeftOutlined, HistoryOutlined,
} from '@ant-design/icons';
import type { PromptVersion, ImpactAnalysis } from '@entities/rag-eval';
import { getPromptCategoryLabel, getPromptCategoryColor, formatTimestamp } from '@entities/rag-eval';
import { usePromptDetail, useUpdatePrompt, useAnalyzeImpact } from '../hooks/usePrompts';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

export function PromptEditPage() {
  const { key } = useParams<{ key: string }>();
  const navigate = useNavigate();
  const promptKey = key || '';

  const { data: detail, isLoading, isError } = usePromptDetail(promptKey);
  const updateMutation = useUpdatePrompt();
  const analyzeMutation = useAnalyzeImpact();

  const [content, setContent] = useState('');
  const [changeSummary, setChangeSummary] = useState('');
  const [showImpactModal, setShowImpactModal] = useState(false);
  const [impactResult, setImpactResult] = useState<ImpactAnalysis | null>(null);
  const [showVersionHistory, setShowVersionHistory] = useState(false);

  // 初始化编辑内容
  useEffect(() => {
    if (detail?.current_version?.content) {
      setContent(detail.current_version.content);
    }
  }, [detail?.current_version?.content]);

  const handleSave = useCallback(async () => {
    if (!promptKey || !content.trim()) return;
    try {
      const result = await updateMutation.mutateAsync({
        promptKey,
        content,
        change_summary: changeSummary || undefined,
      });
      message.success(`已保存为 ${result.version}`);
      setChangeSummary('');
    } catch {
      message.error('保存失败');
    }
  }, [promptKey, content, changeSummary, updateMutation]);

  const handleAnalyze = useCallback(async () => {
    if (!promptKey || !content.trim()) return;
    try {
      const result = await analyzeMutation.mutateAsync({ promptKey, content });
      setImpactResult(result);
      setShowImpactModal(true);
    } catch {
      message.error('分析失败');
    }
  }, [promptKey, content, analyzeMutation]);

  const handleVersionClick = useCallback((version: PromptVersion) => {
    setContent(version.content);
    setShowVersionHistory(false);
  }, []);

  if (isLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (isError || !detail) {
    return <Alert type="error" message="加载提示词详情失败" showIcon />;
  }

  const { metadata, versions } = detail;

  return (
    <div>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompt-management')}>
            返回
          </Button>
          <Title level={4} style={{ margin: 0 }}>{metadata.name_zh}</Title>
          <Tag color={getPromptCategoryColor(metadata.category)}>
            {getPromptCategoryLabel(metadata.category)}
          </Tag>
          {metadata.is_system && <Tag color="purple">系统内置</Tag>}
        </Space>
        <Space>
          <Button
            icon={<HistoryOutlined />}
            onClick={() => setShowVersionHistory(true)}
          >
            版本历史 ({versions.length})
          </Button>
          <Button
            icon={<AuditOutlined />}
            onClick={handleAnalyze}
            loading={analyzeMutation.isPending}
          >
            影响分析
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={updateMutation.isPending}
          >
            保存新版本
          </Button>
        </Space>
      </div>

      <Row gutter={16}>
        {/* 左侧：编辑区 */}
        <Col xs={24} lg={16}>
          <Card size="small" title="提示词内容" style={{ marginBottom: 16 }}>
            <TextArea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={20}
              style={{ fontFamily: 'monospace', fontSize: 13 }}
              placeholder="输入提示词内容..."
            />
          </Card>

          <Card size="small" title="变更说明（可选）">
            <Input
              value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)}
              placeholder="描述本次修改的内容..."
            />
          </Card>
        </Col>

        {/* 右侧：元数据 */}
        <Col xs={24} lg={8}>
          <Card size="small" title="基本信息" style={{ marginBottom: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Key">
                <Text code>{metadata.prompt_key}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="用途">
                {metadata.purpose}
              </Descriptions.Item>
              <Descriptions.Item label="分类">
                <Tag color={getPromptCategoryColor(metadata.category)}>
                  {getPromptCategoryLabel(metadata.category)}
                </Tag>
              </Descriptions.Item>
              {metadata.subcategory && (
                <Descriptions.Item label="子分类">
                  {metadata.subcategory}
                </Descriptions.Item>
              )}
              <Descriptions.Item label="状态">
                {metadata.is_active ? (
                  <Tag color="success">启用</Tag>
                ) : (
                  <Tag color="default">禁用</Tag>
                )}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {detail.current_version?.variables_extracted && detail.current_version.variables_extracted.length > 0 && (
            <Card size="small" title="变量列表" style={{ marginBottom: 16 }}>
              <Space wrap>
                {detail.current_version.variables_extracted.map((v) => (
                  <Tag key={v} color="blue">{`{${v}}`}</Tag>
                ))}
              </Space>
            </Card>
          )}

          {detail.current_version && (
            <Card size="small" title="当前版本">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="版本">
                  {detail.current_version.version_label}
                </Descriptions.Item>
                <Descriptions.Item label="更新时间">
                  {detail.current_version.created_at ? formatTimestamp(detail.current_version.created_at) : '-'}
                </Descriptions.Item>
                {detail.current_version.change_summary && (
                  <Descriptions.Item label="变更说明">
                    {detail.current_version.change_summary}
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          )}
        </Col>
      </Row>

      {/* 版本历史弹窗 */}
      <Modal
        title="版本历史"
        open={showVersionHistory}
        onCancel={() => setShowVersionHistory(false)}
        footer={null}
        width={700}
      >
        <List
          dataSource={versions}
          renderItem={(version) => (
            <List.Item
              actions={[
                <Button size="small" onClick={() => handleVersionClick(version)}>
                  使用此版本
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Text strong>{version.version_label}</Text>
                    {version.created_by && <Text type="secondary">by {version.created_by}</Text>}
                  </Space>
                }
                description={
                  <div>
                    {version.change_summary && <Paragraph style={{ margin: 0 }}>{version.change_summary}</Paragraph>}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {version.created_at ? formatTimestamp(version.created_at) : '-'}
                    </Text>
                  </div>
                }
              />
            </List.Item>
          )}
        />
      </Modal>

      {/* 影响分析弹窗 */}
      <Modal
        title="影响分析"
        open={showImpactModal}
        onCancel={() => setShowImpactModal(false)}
        footer={null}
        width={700}
      >
        {impactResult && (
          <div>
            <Alert
              type={impactResult.risk_level === 'high' ? 'error' : impactResult.risk_level === 'medium' ? 'warning' : 'success'}
              message={`风险等级：${impactResult.risk_level.toUpperCase()}`}
              style={{ marginBottom: 16 }}
            />

            {impactResult.code_references.length > 0 && (
              <Card size="small" title="代码引用" style={{ marginBottom: 16 }}>
                <List
                  size="small"
                  dataSource={impactResult.code_references}
                  renderItem={(ref) => (
                    <List.Item>
                      <Text code>{ref.file}:{ref.line}</Text>
                      {ref.function && <Text type="secondary"> in {ref.function}</Text>}
                    </List.Item>
                  )}
                />
              </Card>
            )}

            {impactResult.variable_changes.added.length > 0 && (
              <Alert
                type="info"
                message={`新增变量：${impactResult.variable_changes.added.join(', ')}`}
                style={{ marginBottom: 8 }}
              />
            )}
            {impactResult.variable_changes.removed.length > 0 && (
              <Alert
                type="warning"
                message={`移除变量：${impactResult.variable_changes.removed.join(', ')}`}
                style={{ marginBottom: 8 }}
              />
            )}

            {impactResult.affected_files.length > 0 && (
              <Card size="small" title="受影响文件" style={{ marginTop: 16 }}>
                <Space wrap>
                  {impactResult.affected_files.map((f) => (
                    <Tag key={f}>{f}</Tag>
                  ))}
                </Space>
              </Card>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
