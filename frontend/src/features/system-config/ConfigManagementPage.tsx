import React, { useState } from 'react';
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { Button, Modal, Form, Input, Space, message } from 'antd';
import { useQuery, useMutation } from '@tanstack/react-query';
import { configApi } from '@/api/config';
import type { ConfigVersion } from '@/api/config/types';
import { ConfigForm } from './ConfigForm';

export const ConfigManagementPage: React.FC = () => {
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [form] = Form.useForm();

  // 查询配置版本列表
  const { data: versions, refetch, isLoading } = useQuery({
    queryKey: ['configVersions'],
    queryFn: () => configApi.listVersions(),
  });

  // 创建新版本
  const createMutation = useMutation({
    mutationFn: (data: { description: string }) => 
      configApi.updateConfig({
        config: {},
        description: data.description,
        created_by: 'admin',
      }),
    onSuccess: () => {
      message.success('版本创建成功');
      refetch();
      setCreateModalVisible(false);
      form.resetFields();
    },
    onError: () => {
      message.error('版本创建失败');
    },
  });

  // 回滚
  const rollbackMutation = useMutation({
    mutationFn: (versionId: string) => configApi.rollbackToVersion(versionId),
    onSuccess: () => {
      message.success('回滚成功');
      refetch();
    },
    onError: () => {
      message.error('回滚失败');
    },
  });

  const columns: ProColumns<ConfigVersion>[] = [
    {
      title: '版本 ID',
      dataIndex: 'version_id',
      key: 'version_id',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text) => text ? new Date(text as string).toLocaleString() : '-',
    },
    {
      title: '创建者',
      dataIndex: 'created_by',
      key: 'created_by',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive) => isActive ? '当前版本' : '历史版本',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            onClick={() => handleViewDetail(record.version_id)}
          >
            查看
          </Button>
          {!record.is_active && (
            <Button
              size="small"
              danger
              onClick={() => handleRollback(record.version_id)}
            >
              回滚
            </Button>
          )}
        </Space>
      ),
    },
  ];

  const handleViewDetail = (_versionId: string) => {
    // 后续实现详情弹窗
  };

  const handleRollback = (versionId: string) => {
    Modal.confirm({
      title: '确认回滚',
      content: '确定要回滚到此版本吗？',
      onOk: () => rollbackMutation.mutate(versionId),
    });
  };

  const handleCreateVersion = () => {
    form.validateFields().then((values) => {
      createMutation.mutate(values);
    });
  };

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ marginBottom: 24 }}>系统配置</h1>
      
      {/* 配置表单 */}
      <ConfigForm />
      
      {/* 版本管理表格 */}
      <ProTable
        columns={columns}
        dataSource={versions}
        rowKey="version_id"
        headerTitle="配置版本管理"
        loading={isLoading}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            onClick={() => setCreateModalVisible(true)}
          >
            创建新版本
          </Button>,
        ]}
        pagination={{
          pageSize: 10,
        }}
      />

      <Modal
        title="创建配置版本"
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        onOk={handleCreateVersion}
        confirmLoading={createMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="描述"
            name="description"
            rules={[{ required: true, message: '请输入版本描述' }]}
          >
            <Input.TextArea rows={4} placeholder="请输入版本描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};