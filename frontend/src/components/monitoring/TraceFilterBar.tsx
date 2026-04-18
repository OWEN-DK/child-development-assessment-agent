import React from 'react';
import { Form, Select, DatePicker, Input, Button, Space } from 'antd';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';

const { RangePicker } = DatePicker;

interface TraceFilterBarProps {
  onFilter: (filters: Record<string, any>) => void;
}

export const TraceFilterBar: React.FC<TraceFilterBarProps> = ({ onFilter }) => {
  const [form] = Form.useForm();

  const handleSearch = () => {
    const values = form.getFieldsValue();
    const filters: Record<string, any> = {};

    if (values.time_range) {
      filters.start_time = values.time_range[0]?.toISOString();
      filters.end_time = values.time_range[1]?.toISOString();
    }
    if (values.scenes?.length) filters.scenes = values.scenes;
    if (values.models?.length) filters.models = values.models;
    if (values.status) filters.status = values.status;
    if (values.user_id) filters.user_id = values.user_id;
    if (values.trace_id) filters.trace_id = values.trace_id;

    onFilter(filters);
  };

  const handleReset = () => {
    form.resetFields();
    onFilter({});
  };

  return (
    <Form form={form} layout="inline" style={{ marginBottom: 16 }}>
      <Form.Item name="time_range" label="时间范围">
        <RangePicker showTime />
      </Form.Item>
      <Form.Item name="scenes" label="场景">
        <Select mode="multiple" placeholder="选择场景" style={{ width: 200 }} allowClear>
          <Select.Option value="assessment">评估</Select.Option>
          <Select.Option value="reporting">报告生成</Select.Option>
          <Select.Option value="retrieval">检索</Select.Option>
          <Select.Option value="test_execution">测试执行</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item name="models" label="模型">
        <Select mode="multiple" placeholder="选择模型" style={{ width: 200 }} allowClear>
          <Select.Option value="qwen-plus">通义千问 Plus</Select.Option>
          <Select.Option value="qwen-turbo">通义千问 Turbo</Select.Option>
          <Select.Option value="qwen-vl">通义千问 VL</Select.Option>
          <Select.Option value="text-embedding-v4">嵌入模型 v4</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item name="status" label="状态">
        <Select placeholder="选择状态" style={{ width: 120 }} allowClear>
          <Select.Option value="success">成功</Select.Option>
          <Select.Option value="failed">失败</Select.Option>
          <Select.Option value="partial">部分成功</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item name="user_id" label="用户 ID">
        <Input placeholder="搜索用户 ID" style={{ width: 150 }} allowClear />
      </Form.Item>
      <Form.Item name="trace_id" label="Trace ID">
        <Input placeholder="精确搜索 Trace ID" style={{ width: 220 }} allowClear />
      </Form.Item>
      <Form.Item>
        <Space>
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置
          </Button>
        </Space>
      </Form.Item>
    </Form>
  );
};
