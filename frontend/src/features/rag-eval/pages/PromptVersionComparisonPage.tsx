/**
 * 提示词版本对比页
 * 路由: /prompt-management/:key/versions
 */

import React, { useEffect, useState } from 'react';
import {
  Card,
  Select,
  Button,
  Space,
  Typography,
  Spin,
  Table,
  Tag,
  Row,
  Col,
  Divider,
  Alert,
} from 'antd';
import { notification } from '@shared/lib/notification';
import { ArrowLeftOutlined, DiffOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { Input } from 'antd';
import {
  getPromptDetail,
  comparePromptVersions,
  PromptDetail,
  PromptComparison,
} from '@/api/rag-eval/prompts';

const { Title } = Typography;
const { TextArea } = Input;

const PromptVersionComparisonPage: React.FC = () => {
  const { key } = useParams<{ key: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<PromptDetail | null>(null);
  const [version1, setVersion1] = useState<string>();
  const [version2, setVersion2] = useState<string>();
  const [comparison, setComparison] = useState<PromptComparison | null>(null);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    if (key) fetchDetail(key);
  }, [key]);

  const fetchDetail = async (promptKey: string) => {
    setLoading(true);
    try {
      const data = await getPromptDetail(promptKey);
      setDetail(data);
      if (data.versions.length >= 2) {
        setVersion1(data.versions[0].version_label);
        setVersion2(data.versions[1].version_label);
      }
    } catch (error) {
      notification.error('获取提示词详情失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!key || !version1 || !version2) return;

    setComparing(true);
    try {
      const data = await comparePromptVersions(key, version1, version2);
      setComparison(data);
    } catch (error) {
      notification.error('对比失败');
    } finally {
      setComparing(false);
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: 'block', marginTop: 100 }} />;
  }

  if (!detail) {
    return <Alert type="error" message="提示词未找到" />;
  }

  const columns = [
    {
      title: '版本',
      dataIndex: 'version_label',
      key: 'version_label',
      render: (text: string) => <Tag>{text}</Tag>,
    },
    {
      title: '变量',
      dataIndex: 'variables_extracted',
      key: 'variables_extracted',
      render: (vars: string[]) => vars?.map((v) => <Tag key={v}>{v}</Tag>) || '无',
    },
    {
      title: '变更摘要',
      dataIndex: 'change_summary',
      key: 'change_summary',
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
    },
    {
      title: '创建人',
      dataIndex: 'created_by',
      key: 'created_by',
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/prompt-management')}>
          返回列表
        </Button>
        <Title level={3} style={{ margin: 0 }}>
          {detail.metadata.name_zh} - 版本对比
        </Title>
      </Space>

      <Card title="版本列表" style={{ marginBottom: 16 }}>
        <Table
          columns={columns}
          dataSource={detail.versions}
          rowKey="version_label"
          pagination={false}
          size="small"
        />
      </Card>

      <Card title="选择对比版本" style={{ marginBottom: 16 }}>
        <Space>
          <Select
            style={{ width: 200 }}
            value={version1}
            onChange={setVersion1}
            options={detail.versions.map((v) => ({
              label: v.version_label,
              value: v.version_label,
            }))}
            placeholder="选择版本 1"
          />
          <DiffOutlined />
          <Select
            style={{ width: 200 }}
            value={version2}
            onChange={setVersion2}
            options={detail.versions.map((v) => ({
              label: v.version_label,
              value: v.version_label,
            }))}
            placeholder="选择版本 2"
          />
          <Button
            type="primary"
            onClick={handleCompare}
            disabled={!version1 || !version2}
            loading={comparing}
          >
            对比
          </Button>
        </Space>
      </Card>

      {comparison && (
        <Row gutter={16}>
          <Col span={12}>
            <Card title={`版本 ${comparison.version_1.version_label}`} size="small">
              <TextArea
                value={comparison.version_1.content}
                rows={15}
                readOnly
                style={{ fontFamily: 'monospace' }}
              />
              <Divider />
              <p>变量: {comparison.version_1.variables_extracted?.join(', ') || '无'}</p>
              <p>创建时间: {comparison.version_1.created_at}</p>
            </Card>
          </Col>
          <Col span={12}>
            <Card title={`版本 ${comparison.version_2.version_label}`} size="small">
              <TextArea
                value={comparison.version_2.content}
                rows={15}
                readOnly
                style={{ fontFamily: 'monospace' }}
              />
              <Divider />
              <p>变量: {comparison.version_2.variables_extracted?.join(', ') || '无'}</p>
              <p>创建时间: {comparison.version_2.created_at}</p>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
};

export default PromptVersionComparisonPage;
