/**
 * 测试用例新增表单组件
 */

import { useEffect, useState } from 'react';
import { Modal, Form, Input, InputNumber, Select, Button, Space, App } from 'antd';
import { createTestCase } from '@/api/rag-test';

const { TextArea } = Input;

const DOMAIN_OPTIONS = [
  { label: '大运动', value: 'gross_motor' },
  { label: '精细运动', value: 'fine_motor' },
  { label: '语言', value: 'language' },
  { label: '认知', value: 'cognitive' },
  { label: '社交情感', value: 'social_emotional' },
  { label: '感觉统合', value: 'sensory_integration' },
];

interface TestCaseCreateFormProps {
  visible: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function TestCaseCreateForm({ visible, onClose, onSuccess }: TestCaseCreateFormProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!visible) return;
    form.resetFields();
  }, [visible, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      await createTestCase({
        ...values,
        expected_knowledge_ids: values.expected_knowledge_ids || [],
        expected_keywords: values.expected_keywords || [],
      });
      message.success('测试用例创建成功');
      form.resetFields();
      onSuccess();
    } catch (e: any) {
      if (e.errorFields) return;
      message.error(e.response?.data?.message || '创建测试用例失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="新增测试用例"
      open={visible}
      onCancel={onClose}
      footer={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={loading} onClick={handleSubmit}>
            创建
          </Button>
        </Space>
      }
      width={640}
      destroyOnClose
    >
      <Form form={form} layout="vertical" autoComplete="off">
        <Form.Item
          name="query"
          label="查询语句"
          rules={[{ required: true, message: '请输入查询语句' }]}
        >
          <TextArea rows={3} placeholder="请输入查询语句" />
        </Form.Item>

        <Form.Item
          name="age"
          label="年龄（月）"
          rules={[{ required: true, message: '请输入年龄' }]}
        >
          <InputNumber min={0} max={216} style={{ width: '100%' }} placeholder="请输入月龄" />
        </Form.Item>

        <Form.Item
          name="domain"
          label="领域"
          rules={[{ required: true, message: '请选择领域' }]}
        >
          <Select placeholder="请选择领域" options={DOMAIN_OPTIONS} />
        </Form.Item>

        <Form.Item name="description" label="描述">
          <TextArea rows={2} placeholder="请输入描述（可选）" />
        </Form.Item>

        <Form.Item name="expected_keywords" label="期望关键词">
          <Select
            mode="tags"
            placeholder="输入后按回车添加"
            style={{ width: '100%' }}
          />
        </Form.Item>

        <Form.Item name="expected_knowledge_ids" label="期望知识点">
          <Select
            mode="tags"
            placeholder="输入后按回车添加"
            style={{ width: '100%' }}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
