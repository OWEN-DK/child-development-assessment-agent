import React, { useEffect, useState, useCallback } from 'react';
import {
  Button, Table, Tag, Switch, Space, Modal, Upload, Input,
  message, Popconfirm, Tooltip, Card, Descriptions,
} from 'antd';
import {
  UploadOutlined, DeleteOutlined,
  SearchOutlined, ReloadOutlined, FileTextOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { curationApi } from '../api/curationApi';

interface CustomRule {
  rule_id: string;
  title?: string;
  content?: string;
  category?: string;
  priority?: number;
  enabled?: boolean;
  keywords?: string[];
}

const CATEGORY_LABELS: Record<string, string> = {
  expert_rule: '专家经验',
  clinical_guideline: '临床指南',
  policy: '政策规范',
  faq: '常见问答',
  general: '通用',
};

const CATEGORY_COLORS: Record<string, string> = {
  expert_rule: '#7C3AED',
  clinical_guideline: '#DC2626',
  policy: '#2563EB',
  faq: '#10B981',
  general: '#6B7280',
};

export const CustomKnowledgePage: React.FC = () => {
  const [rules, setRules] = useState<CustomRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [parsedRules, setParsedRules] = useState<any[]>([]);
  const [matchText, setMatchText] = useState('');
  const [matchResult, setMatchResult] = useState<any>(null);
  const [matching, setMatching] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailRule, setDetailRule] = useState<CustomRule | null>(null);
  const [fileList, setFileList] = useState<any[]>([]);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await (curationApi as any).listCustomRules();
      setRules(res.items || []);
    } catch {
      message.error('加载自定义知识列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchRules(); }, [fetchRules]);

  const handleUpload = async () => {
    if (fileList.length === 0) return;
    setUploading(true);
    try {
      const formData = new FormData();
      fileList.forEach((f: any) => formData.append('files', f.originFileObj || f));
      const res = await fetch('/api/v1/custom-knowledge/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.success) {
        setParsedRules(data.data?.rules || []);
        message.success(`解析完成: ${data.data?.total || 0} 条规则`);
      } else {
        message.error(data.message || '解析失败');
      }
    } catch {
      message.error('上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleConfirmSave = async () => {
    if (parsedRules.length === 0) return;
    try {
      await (curationApi as any).confirmCustomRules(parsedRules);
      message.success('入库成功');
      setUploadOpen(false);
      setParsedRules([]);
      setFileList([]);
      fetchRules();
    } catch {
      message.error('入库失败');
    }
  };

  const handleToggle = async (ruleId: string, enabled: boolean) => {
    try {
      await (curationApi as any).updateCustomRule(ruleId, { enabled });
      setRules((prev) => prev.map((r) => (r.rule_id === ruleId ? { ...r, enabled } : r)));
    } catch {
      message.error('更新失败');
    }
  };

  const handleDelete = async (ruleId: string) => {
    try {
      await (curationApi as any).deleteCustomRule(ruleId);
      message.success('已删除');
      fetchRules();
    } catch {
      message.error('删除失败');
    }
  };

  const handleMatchTest = async () => {
    if (!matchText.trim()) return;
    setMatching(true);
    try {
      const res = await (curationApi as any).matchCustomKnowledge(matchText);
      setMatchResult(res);
    } catch {
      message.error('匹配测试失败');
    } finally {
      setMatching(false);
    }
  };

  const columns: ColumnsType<CustomRule> = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 220,
      render: (text: string, record: CustomRule) => (
        <a onClick={() => { setDetailRule(record); setDetailOpen(true); }}>
          {text || record.rule_id}
        </a>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (cat: string) => (
        <Tag color={CATEGORY_COLORS[cat] || '#6B7280'}>
          {CATEGORY_LABELS[cat] || cat || '通用'}
        </Tag>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a: CustomRule, b: CustomRule) => (a.priority || 0) - (b.priority || 0),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (val: boolean, record: CustomRule) => (
        <Switch
          checked={val !== false}
          size="small"
          onChange={(checked) => handleToggle(record.rule_id, checked)}
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: any, record: CustomRule) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button size="small" icon={<FileTextOutlined />} onClick={() => { setDetailRule(record); setDetailOpen(true); }} />
          </Tooltip>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.rule_id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '0 0 16px' }}>
      {/* 工具栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, gap: 12, flexWrap: 'wrap' }}>
        <Space>
          <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>
            上传 .md 文件
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchRules} loading={loading}>
            刷新
          </Button>
        </Space>

        <Space.Compact style={{ width: 360 }}>
          <Input
            placeholder="输入测试问题，测试匹配..."
            prefix={<SearchOutlined />}
            value={matchText}
            onChange={(e) => setMatchText(e.target.value)}
            onPressEnter={handleMatchTest}
          />
          <Button onClick={handleMatchTest} loading={matching}>测试</Button>
        </Space.Compact>
      </div>

      {/* 匹配测试结果 */}
      {matchResult && (
        <Card
          size="small"
          title={`匹配结果: ${matchResult.hit ? '✅ 命中' : '❌ 未命中'} (${matchResult.match_channel || '无'})`}
          style={{ marginBottom: 16 }}
          extra={<Button size="small" onClick={() => setMatchResult(null)}>关闭</Button>}
        >
          {matchResult.matched_items?.map((item: any, i: number) => (
            <div key={i} style={{ marginBottom: 8 }}>
              <Tag color="blue">{item.category || '通用'}</Tag>
              <strong>{item.title}</strong>
              <div style={{ color: '#666', fontSize: 13, marginTop: 4 }}>
                {(item.content || '').substring(0, 200)}...
              </div>
            </div>
          ))}
        </Card>
      )}

      {/* 规则表格 */}
      <Table
        columns={columns}
        dataSource={rules}
        rowKey="rule_id"
        loading={loading}
        size="middle"
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        locale={{ emptyText: '暂无自定义知识，点击"上传 .md 文件"添加' }}
      />

      {/* 上传弹窗 */}
      <Modal
        title="上传自定义知识"
        open={uploadOpen}
        onCancel={() => { setUploadOpen(false); setParsedRules([]); setFileList([]); }}
        width={640}
        footer={
          parsedRules.length > 0
            ? [
                <Button key="cancel" onClick={() => { setUploadOpen(false); setParsedRules([]); setFileList([]); }}>取消</Button>,
                <Button key="confirm" type="primary" onClick={handleConfirmSave}>确认入库 ({parsedRules.length} 条)</Button>,
              ]
            : [
                <Button key="cancel" onClick={() => { setUploadOpen(false); setFileList([]); }}>取消</Button>,
                <Button key="upload" type="primary" onClick={handleUpload} loading={uploading} disabled={fileList.length === 0}>
                  解析文件
                </Button>,
              ]
        }
      >
        {parsedRules.length === 0 ? (
          <>
            <p style={{ color: '#666', marginBottom: 12 }}>
              上传 .md 文件（最多 5 份），AI 将自动提取规则、生成关键词和匹配模式。
            </p>
            <Upload
              accept=".md"
              multiple
              maxCount={5}
              fileList={fileList}
              beforeUpload={(file) => { setFileList((prev) => [...prev, file]); return false; }}
              onRemove={(file) => { setFileList((prev) => prev.filter((f: any) => f.uid !== file.uid)); }}
            >
              <Button icon={<UploadOutlined />}>选择 .md 文件</Button>
            </Upload>
          </>
        ) : (
          <div>
            <p style={{ color: '#10B981', marginBottom: 12 }}>
              ✅ 解析完成，共 {parsedRules.length} 条规则。请确认后入库。
            </p>
            {parsedRules.map((rule: any, i: number) => (
              <Card key={i} size="small" style={{ marginBottom: 8 }}>
                <div><strong>{rule.title}</strong></div>
                <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                  分类: {CATEGORY_LABELS[rule.category] || rule.category} | 优先级: {rule.priority}
                </div>
                {rule.keywords?.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    {rule.keywords.map((kw: string) => <Tag key={kw} style={{ fontSize: 11 }}>{kw}</Tag>)}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </Modal>

      {/* 详情弹窗 */}
      <Modal
        title="规则详情"
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={<Button onClick={() => setDetailOpen(false)}>关闭</Button>}
        width={600}
      >
        {detailRule && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="ID">{detailRule.rule_id}</Descriptions.Item>
            <Descriptions.Item label="标题">{detailRule.title || '-'}</Descriptions.Item>
            <Descriptions.Item label="分类">
              <Tag color={CATEGORY_COLORS[detailRule.category || '']}>
                {CATEGORY_LABELS[detailRule.category || ''] || detailRule.category || '通用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="优先级">{detailRule.priority || 100}</Descriptions.Item>
            <Descriptions.Item label="状态">
              {detailRule.enabled !== false ? '✅ 启用' : '⛔ 禁用'}
            </Descriptions.Item>
            <Descriptions.Item label="关键词">
              {(detailRule.keywords || []).map((kw: string) => <Tag key={kw}>{kw}</Tag>)}
            </Descriptions.Item>
            <Descriptions.Item label="内容">
              <div style={{ whiteSpace: 'pre-wrap', maxHeight: 300, overflow: 'auto', fontSize: 13 }}>
                {detailRule.content || '（无内容）'}
              </div>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};
