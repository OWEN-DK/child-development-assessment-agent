/**
 * 测试集详情页
 * 路由: /rag-eval/test-sets/:id
 */

import { useParams, Link } from 'react-router-dom';
import {
  Descriptions,
  Button,
  Input,
  Select,
  Space,
  Typography,
  Spin,
  Modal,
  Transfer,
  Tag,
} from 'antd';
import { ArrowLeftOutlined, PlayCircleOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTestSetDetail } from '../hooks/useTestSetDetail';
import { TestSetDetailTable } from '../components/TestSetDetailTable';
import type { TestCase } from '@/api/rag-test';

const { Title } = Typography;

const DOMAIN_MAP: Record<string, string> = {
  gross_motor: '大运动',
  fine_motor: '精细运动',
  language: '语言',
  cognitive: '认知',
  social_emotional: '社交情感',
  sensory_integration: '感觉统合',
};

const formatAge = (age: number): string => {
  if (!age && age !== 0) return '-';
  const years = Math.floor(age / 12);
  const months = age % 12;
  if (years > 0 && months > 0) return `${years}岁${months}月`;
  if (years > 0) return `${years}岁`;
  return `${months}月`;
};

export default function TestSetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const {
    testSet,
    cases,
    availableCases,
    loading,
    domains,
    filters,
    modals,
    actions,
  } = useTestSetDetail(id);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!testSet) return <div>测试集不存在</div>;

  const transferDataSource = availableCases.map(c => ({
    key: c.id,
    ...c,
  }));

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Link to="/rag-eval?tab=test-sets">
          <Button type="link" icon={<ArrowLeftOutlined />}>返回</Button>
        </Link>
      </div>

      <Descriptions
        title={<Title level={4} style={{ margin: 0 }}>{testSet.name}</Title>}
        bordered
        column={3}
        extra={
          <Space>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => modals.setRunModalVisible(true)}
              disabled={testSet.test_case_ids?.length === 0}
            >
              运行测试
            </Button>
          </Space>
        }
      >
        <Descriptions.Item label="描述">{testSet.description || '-'}</Descriptions.Item>
        <Descriptions.Item label="用例数">{testSet.test_case_ids?.length || 0}</Descriptions.Item>
        <Descriptions.Item label="创建时间">{dayjs(testSet.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
      </Descriptions>

      <div style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 16, display: 'flex', gap: 12, justifyContent: 'space-between' }}>
          <Space>
            <Input
              placeholder="搜索查询语句"
              prefix={<SearchOutlined />}
              style={{ width: 240 }}
              value={filters.keyword}
              onChange={e => filters.setKeyword(e.target.value)}
              allowClear
            />
            <Select
              placeholder="领域筛选"
              style={{ width: 160 }}
              value={filters.domainFilter}
              onChange={filters.setDomainFilter}
              allowClear
              options={domains.map(d => ({ label: d, value: d }))}
            />
          </Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => modals.setAddModalVisible(true)}>
            添加用例
          </Button>
        </div>

        <TestSetDetailTable cases={cases} onRemove={actions.handleRemoveCase} />
      </div>

      <Modal
        title="运行测试"
        open={modals.runModalVisible}
        onCancel={() => modals.setRunModalVisible(false)}
        onOk={actions.handleRunTest}
      >
        <div style={{ marginBottom: 16 }}>
          <Input
            value={modals.runName}
            onChange={e => modals.setRunName(e.target.value)}
            placeholder="留空则使用测试集名称"
          />
        </div>
      </Modal>

      <Modal
        title="添加用例"
        open={modals.addModalVisible}
        onCancel={() => {
          modals.setAddModalVisible(false);
          modals.setTransferSelectedKeys([]);
        }}
        onOk={actions.handleAddCases}
        width={1400}
        style={{ top: 20 }}
        okButtonProps={{ disabled: modals.transferSelectedKeys.length === 0 }}
      >
        <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
          <Input
            placeholder="搜索查询语句"
            prefix={<SearchOutlined />}
            style={{ width: 280 }}
            value={filters.keyword}
            onChange={e => filters.setKeyword(e.target.value)}
            allowClear
          />
          <Select
            placeholder="领域筛选"
            style={{ width: 160 }}
            value={filters.domainFilter}
            onChange={filters.setDomainFilter}
            allowClear
            options={domains.map(d => ({ label: DOMAIN_MAP[d] || d, value: d }))}
          />
          <span style={{ color: '#666', fontSize: 13 }}>
            已选择 <strong style={{ color: '#1890ff' }}>{modals.transferSelectedKeys.length}</strong> 个用例
          </span>
        </div>

        <Transfer
          dataSource={transferDataSource}
          targetKeys={modals.transferSelectedKeys}
          onChange={keys => modals.setTransferSelectedKeys(keys as string[])}
          render={item => {
            const testCase = item as TestCase;
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontWeight: 500 }}>{testCase.query}</span>
                <div style={{ display: 'flex', gap: 8, fontSize: 12, color: '#666' }}>
                  <span>年龄: {formatAge(testCase.age)}</span>
                  {testCase.domain && <Tag color="blue" style={{ margin: 0 }}>{DOMAIN_MAP[testCase.domain] || testCase.domain}</Tag>}
                </div>
              </div>
            );
          }}
          listStyle={{
            width: 600,
            height: 600,
          }}
          titles={['可选用例', `已选用例`]}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
          }}
          locale={{
            searchPlaceholder: '搜索用例',
            notFoundContent: '暂无用例',
            itemUnit: '个',
            itemsUnit: '个',
          }}
        />
      </Modal>
    </div>
  );
}