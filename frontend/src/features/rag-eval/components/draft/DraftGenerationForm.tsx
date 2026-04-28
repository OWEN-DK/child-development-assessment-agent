import { Form, Select, InputNumber, Button, Space, Card, Typography } from 'antd';
import { RocketOutlined } from '@ant-design/icons';
import type { TestDomain } from '@entities/rag-eval';
import { DOMAIN_MAP, AGE_STAGES } from '@entities/rag-eval';

const { Title } = Typography;

const domainOptions = Object.entries(DOMAIN_MAP).map(([value, label]) => ({ value, label }));

interface DraftGenerationFormValues {
  document_id: string;
  max_qa_per_chunk: number;
  min_qa_per_chunk: number;
  age_ranges: string[];
  domains: TestDomain[];
}

interface DraftGenerationFormProps {
  documents: Array<{ id: string; name: string }>;
  loading?: boolean;
  onSubmit: (values: DraftGenerationFormValues) => void;
}

export function DraftGenerationForm({ documents, loading, onSubmit }: DraftGenerationFormProps) {
  return (
    <Card
      title={
        <Space>
          <RocketOutlined />
          <Title level={5} style={{ margin: 0 }}>生成配置</Title>
        </Space>
      }
      size="small"
    >
      <Form
        layout="vertical"
        size="small"
        initialValues={{
          max_qa_per_chunk: 3,
          min_qa_per_chunk: 1,
          age_ranges: ['1-2岁', '2-3岁'],
          domains: ['gross_motor', 'fine_motor', 'language', 'cognitive', 'social_emotional', 'sensory_integration'],
        }}
        onFinish={onSubmit}
      >
        <Form.Item
          label="源文档"
          name="document_id"
          rules={[{ required: true, message: '请选择源文档' }]}
        >
          <Select
            showSearch
            placeholder="选择知识库文档"
            options={documents.map((d) => ({ value: d.id, label: d.name }))}
            filterOption={(input, option) =>
              (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Space style={{ width: '100%' }} size="middle">
          <Form.Item
            label="每块最小 QA 数"
            name="min_qa_per_chunk"
            rules={[{ required: true }]}
            style={{ flex: 1 }}
          >
            <InputNumber min={1} max={10} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            label="每块最大 QA 数"
            name="max_qa_per_chunk"
            rules={[{ required: true }]}
            style={{ flex: 1 }}
          >
            <InputNumber min={1} max={20} style={{ width: '100%' }} />
          </Form.Item>
        </Space>

        <Form.Item label="年龄段范围" name="age_ranges">
          <Select
            mode="multiple"
            placeholder="选择年龄段"
            options={AGE_STAGES.map((s) => ({ value: s, label: s }))}
          />
        </Form.Item>

        <Form.Item label="目标领域" name="domains">
          <Select mode="multiple" placeholder="选择领域" options={domainOptions} />
        </Form.Item>

        <Button type="primary" htmlType="submit" loading={loading} icon={<RocketOutlined />} block>
          开始生成
        </Button>
      </Form>
    </Card>
  );
}
