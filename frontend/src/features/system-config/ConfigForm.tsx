import React from 'react';
import { Form, Card, Space, Button, message } from 'antd';
import { CONFIG_SCHEMAS } from './schema';
import type { ConfigFieldSchema } from './schema';
import { ConfigFieldRenderer } from './ConfigFieldRenderer';
import { useMutation, useQuery } from '@tanstack/react-query';
import { configApi } from '@/api/config';

export const ConfigForm: React.FC = () => {
  const [form] = Form.useForm();
  
  // 加载当前配置
  const { data: configResponse, isLoading: _isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: () => configApi.getConfig(),
  });
  
  // 构建配置值映射
  const configValues = React.useMemo(() => {
    if (!configResponse?.config) return {};
    return configResponse.config.reduce((acc, field) => {
      acc[field.key] = field.current_value ?? field.default_value;
      return acc;
    }, {} as Record<string, any>);
  }, [configResponse]);
  
  // 保存配置
  const saveMutation = useMutation({
    mutationFn: (values: Record<string, any>) => 
      configApi.updateConfig({
        config: values,
        description: '通过配置页面更新',
        created_by: 'admin',
      }),
    onSuccess: () => {
      message.success('配置保存成功');
    },
    onError: () => {
      message.error('配置保存失败');
    },
  });
  
  // 按模块分组渲染
  const renderModule = (moduleName: string, fields: ConfigFieldSchema[]) => {
    return (
      <Card key={moduleName} title={moduleName} style={{ marginBottom: 24 }}>
        {fields.map((field) => (
          <Form.Item
            key={field.key}
            label={field.label}
            name={field.key}
            initialValue={configValues[field.key] ?? field.default}
            rules={[{ required: field.required, message: `${field.label}不能为空` }]}
          >
            <ConfigFieldRenderer
              schema={field}
              disabled={field.disabled}
            />
          </Form.Item>
        ))}
      </Card>
    );
  };
  
  const onFinish = (values: any) => {
    saveMutation.mutate(values);
  };
  
  return (
    <Form form={form} layout="vertical" onFinish={onFinish}>
      {Object.entries(CONFIG_SCHEMAS).map(([moduleName, fields]) =>
        renderModule(moduleName, fields)
      )}
      
      <Form.Item>
        <Space>
          <Button
            type="primary"
            htmlType="submit"
            loading={saveMutation.isPending}
          >
            保存配置
          </Button>
          <Button
            onClick={() => form.resetFields()}
          >
            重置
          </Button>
        </Space>
      </Form.Item>
    </Form>
  );
};