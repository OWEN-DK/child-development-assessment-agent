import React from 'react';
import { Modal, Form, Input, InputNumber } from 'antd';
import type { TestCase } from '../../api/rag-test/types';

interface TestCaseModalProps {
  visible: boolean;
  editingCase: TestCase | null;
  form: any;
  onOk: () => void;
  onCancel: () => void;
}

export const TestCaseModal: React.FC<TestCaseModalProps> = ({
  visible,
  editingCase,
  form,
  onOk,
  onCancel,
}) => {
  const { TextArea } = Input;

  return (
    <Modal
      title={editingCase ? '编辑测试用例' : '新建测试用例'}
      open={visible}
      onOk={onOk}
      onCancel={onCancel}
      width={600}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          age: 3,
          expected_keywords: '',
        }}
      >
        <Form.Item
          name="query"
          label="查询内容"
          rules={[{ required: true, message: '请输入查询内容' }]}
        >
          <TextArea
            rows={3}
            placeholder="例如：3岁儿童怕高怎么办？"
          />
        </Form.Item>

        <Form.Item
          name="age"
          label="儿童年龄"
          rules={[{ required: true, message: '请输入年龄' }]}
        >
          <InputNumber min={0} max={18} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          name="expected_keywords"
          label="预期关键词（多个用逗号分隔）"
          rules={[{ required: true, message: '请输入预期关键词' }]}
          help="检索结果中包含这些关键词则认为是相关结果"
        >
          <Input placeholder="例如：前庭觉, 平衡训练, 感统游戏" />
        </Form.Item>

        <Form.Item
          name="description"
          label="描述（可选）"
        >
          <TextArea rows={2} placeholder="测试用例的说明信息" />
        </Form.Item>
      </Form>
    </Modal>
  );
};
