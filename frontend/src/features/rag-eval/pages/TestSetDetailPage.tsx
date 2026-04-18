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
  Form,
} from 'antd';
import { ArrowLeftOutlined, PlayCircleOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTestSetDetail } from '../hooks/useTestSetDetail';
import { TestSetDetailTable } from '../components/TestSetDetailTable';

const { Title } = Typography;

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

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Link to="/rag-eval/test-sets">
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
            <Link to={`/rag-eval/test-sets/${id}/drafts`}>
              <Button>草稿审核</Button>
            </Link>
          </Space>
        }
      >
        <Descriptions.Item label="描述">{testSet.description || '-'}</Descriptions.Item>
        <Descriptions.Item label="来源类型">{testSet.source_type}</Descriptions.Item>
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
        <Form layout="vertical">
          <Form.Item label="运行名称（可选）">
            <Input value={modals.runName} onChange={e => modals.setRunName(e.target.value)} placeholder="留空则使用测试集名称" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="添加用例"
        open={modals.addModalVisible}
        onCancel={() => modals.setAddModalVisible(false)}
        onOk={() => modals.form.submit()}
      >
        <Form form={modals.form} layout="vertical" onFinish={actions.handleAddCases}>
          <Form.Item name="case_ids" label="选择用例" rules={[{ required: true, message: '请选择用例' }]}>
            <Select
              mode="multiple"
              placeholder="选择要添加的用例"
              options={availableCases.map(c => ({ label: c.query, value: c.id }))}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}