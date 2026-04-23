/**
 * 测试用例管理页
 * 路由: /rag-eval (Tab: 测试用例)
 *
 * 工作流约束：
 * - 数据来源：仅能从草稿审核通过自动流入
 * - 禁止操作：❌ 新建用例  ❌ 直接导入
 * - 允许操作：✅ 查看  ✅ 编辑  ✅ 删除  ✅ 导出
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table,
  Tag,
  Button,
  Space,
  Input,
  Select,
  Popconfirm,
  Typography,
  Spin,
  App,
} from 'antd';
import { notification } from '@shared/lib/notification';
import {
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { getTestCases, deleteTestCase, batchDeleteTestCases } from '@/api/rag-test';
import type { TestCase } from '@/api/rag-test';
import TestCaseCreateForm from '../components/TestCaseCreateForm';

const { Title } = Typography;

const DOMAIN_COLORS: Record<string, string> = {
  感觉统合: 'blue',
  粗大动作: 'green',
  精细动作: 'orange',
  语言发展: 'purple',
  认知发展: 'cyan',
  社交情感: 'magenta',
};

export default function TestCaseManagementPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [cases, setCases] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [domainFilter, setDomainFilter] = useState<string>();
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  useEffect(() => {
    loadCases();
  }, []);

  const loadCases = async () => {
    setLoading(true);
    try {
      const data = await getTestCases();
      setCases(data);
    } catch {
      notification.error('加载测试用例失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (caseId: string) => {
    try {
      await deleteTestCase(caseId);
      notification.success('用例已删除');
      loadCases();
    } catch {
      notification.error('删除失败');
    }
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的用例');
      return;
    }
    try {
      await batchDeleteTestCases(selectedRowKeys as string[]);
      notification.success(`已删除 ${selectedRowKeys.length} 个用例`);
      setSelectedRowKeys([]);
      loadCases();
    } catch {
      notification.error('批量删除失败');
    }
  };

  const filteredCases = cases.filter(c => {
    if (keyword && !c.query.toLowerCase().includes(keyword.toLowerCase())) return false;
    if (domainFilter && c.domain !== domainFilter) return false;
    return true;
  });

  const domains = [...new Set(cases.map(c => c.domain).filter(Boolean))];

  const columns = [
    {
      title: '查询语句',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
    },
    {
      title: '年龄',
      dataIndex: 'age',
      key: 'age',
      width: 80,
      render: (age: number) => {
        if (!age && age !== 0) return '-';
        const years = Math.floor(age / 12);
        const months = age % 12;
        if (years > 0 && months > 0) return `${years}岁${months}月`;
        if (years > 0) return `${years}岁`;
        return `${months}月`;
      },
    },
    {
      title: '领域',
      dataIndex: 'domain',
      key: 'domain',
      width: 120,
      render: (domain: string) => (
        <Tag color={DOMAIN_COLORS[domain] || 'default'}>{domain || '-'}</Tag>
      ),
    },
    {
      title: '难度',
      dataIndex: 'difficulty_level',
      key: 'difficulty_level',
      width: 100,
      render: (level: string) => {
        const map: Record<string, { label: string; color: string }> = {
          easy: { label: '简单', color: 'green' },
          medium: { label: '中等', color: 'orange' },
          hard: { label: '困难', color: 'red' },
        };
        const info = map[level] || { label: level, color: 'default' };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: TestCase) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => navigate(`/rag-eval/cases/${record.id}/edit`)}
          >
            编辑
          </Button>
          <Popconfirm title="确认删除此用例？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>测试用例管理</Title>
        <Button type="primary" onClick={() => setCreateModalVisible(true)}>
          新增用例
        </Button>
      </div>

      <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
        <Input
          placeholder="搜索查询语句"
          prefix={<SearchOutlined />}
          style={{ width: 240 }}
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          allowClear
        />
        <Select
          placeholder="领域筛选"
          style={{ width: 140 }}
          value={domainFilter}
          onChange={setDomainFilter}
          allowClear
          options={domains.map(d => ({ label: d, value: d }))}
        />
        <Tag>共 {filteredCases.length} 条</Tag>
        {selectedRowKeys.length > 0 && (
          <Popconfirm title={`确认删除 ${selectedRowKeys.length} 个用例？`} onConfirm={handleBatchDelete}>
            <Button danger>
              批量删除 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        )}
      </div>

      <Table
        columns={columns}
        dataSource={filteredCases}
        rowKey="id"
        rowSelection={{
          selectedRowKeys,
          onChange: keys => setSelectedRowKeys(keys),
        }}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
        locale={{ emptyText: '暂无测试用例' }}
      />

      <TestCaseCreateForm
        visible={createModalVisible}
        onClose={() => setCreateModalVisible(false)}
        onSuccess={() => { setCreateModalVisible(false); loadCases(); }}
      />
    </div>
  );
}
