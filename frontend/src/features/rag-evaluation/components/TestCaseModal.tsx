import React, { useEffect, useState } from 'react';
import { Modal, Form, Input, InputNumber, Select, Button, Space, message } from 'antd';
import type { TestCase } from '@/api/rag-test/types';
import { createTestCase, updateTestCase } from '@/api/rag-test';

interface TestCaseModalProps {
  visible: boolean;
  testCase?: TestCase;
  onClose: () => void;
  onSuccess: () => void;
}

export const TestCaseModal: React.FC<TestCaseModalProps> = ({
  visible,
  testCase,
  onClose,
  onSuccess,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (testCase) {
      form.setFieldsValue(testCase);
    } else {
      form.resetFields();
    }
  }, [testCase, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      
      const payload = {
        ...values,
        expected_keywords: values.expected_keywords || [],
        expected_knowledge_ids: values.expected_knowledge_ids || [],
      };

      if (testCase) {
        await updateTestCase(testCase.id, payload);
      } else {
        await createTestCase(payload);
      }
      
      message.success(testCase ? '测试用例更新成功' : '测试用例创建成功');
      onSuccess();
      onClose();
    } catch (err) {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title={testCase ? '编辑测试用例' : '新建测试用例'}
      open={visible}
      onCancel={onClose}
      footer={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={loading} onClick={handleSubmit}>
            保存
          </Button>
        </Space>
      }
      width={700}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="query"
          label="查询内容"
          rules={[{ required: true, message: '请输入查询内容' }]}
        >
          <Input.TextArea rows={3} placeholder="请输入测试查询内容" />
        </Form.Item>

        <Form.Item
          name="age"
          label="年龄"
          rules={[{ required: true, message: '请输入年龄' }]}
        >
          <InputNumber min={0} max={12} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item name="domain" label="领域">
          <Select
            options={[
              { label: '粗大动作', value: '粗大动作' },
              { label: '精细动作', value: '精细动作' },
              { label: '语言发展', value: '语言发展' },
              { label: '认知能力', value: '认知能力' },
              { label: '社交情感', value: '社交情感' },
              { label: '感觉统合', value: '感觉统合' },
            ]}
          />
        </Form.Item>

        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} placeholder="测试用例描述" />
        </Form.Item>

        <Form.Item name="expected_keywords" label="预期关键词">
          <Select mode="tags" placeholder="输入预期关键词" />
        </Form.Item>

        <Form.Item name="expected_knowledge_ids" label="预期知识ID">
          <Select mode="tags" placeholder="输入预期知识ID" />
        </Form.Item>
      </Form>
    </Modal>
  );
};
