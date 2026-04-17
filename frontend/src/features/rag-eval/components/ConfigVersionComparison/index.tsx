/**
 * 配置版本对比入口组件
 * 负责获取对比数据并展示差异
 */

import React, { useEffect, useState } from 'react';
import { Card, Select, Space, Spin, Empty, message } from 'antd';
import { compareConfigVersions } from '@/api/rag-eval/config';
import type { ConfigComparisonData } from './types';
import ComparisonTable from './ComparisonTable';
import type { ConfigVersionComparisonProps } from './types';

interface VersionOption {
  id: string;
  label: string;
}

interface ConfigVersionComparisonInnerProps extends ConfigVersionComparisonProps {
  versions?: VersionOption[];
}

const ConfigVersionComparison: React.FC<ConfigVersionComparisonInnerProps> = ({
  fromVersionId,
  toVersionId,
  versions = [],
}) => {
  const [data, setData] = useState<ConfigComparisonData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedFrom, setSelectedFrom] = useState(fromVersionId);
  const [selectedTo, setSelectedTo] = useState(toVersionId);

  useEffect(() => {
    if (selectedFrom && selectedTo) {
      fetchComparison();
    }
  }, [selectedFrom, selectedTo]);

  const fetchComparison = async () => {
    setLoading(true);
    try {
      const response = await compareConfigVersions(selectedFrom, selectedTo);
      setData(response.data);
    } catch {
      message.error('获取配置对比数据失败');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />;
  }

  if (!data) {
    return <Empty description="请选择要对比的版本" />;
  }

  return (
    <Card
      title="配置版本对比"
      extra={
        <Space>
          <Select
            value={selectedFrom}
            onChange={setSelectedFrom}
            options={versions.map((v) => ({ label: v.label, value: v.id }))}
            style={{ width: 150 }}
            placeholder="源版本"
          />
          <Select
            value={selectedTo}
            onChange={setSelectedTo}
            options={versions.map((v) => ({ label: v.label, value: v.id }))}
            style={{ width: 150 }}
            placeholder="目标版本"
          />
        </Space>
      }
    >
      <div style={{ marginBottom: 16 }}>
        <Space>
          <span>
            <strong>{data.from_version.version_label}</strong>
            {data.from_version.created_at && (
              <span style={{ color: '#999', marginLeft: 8 }}>
                ({new Date(data.from_version.created_at).toLocaleDateString()})
              </span>
            )}
          </span>
          <span>→</span>
          <span>
            <strong>{data.to_version.version_label}</strong>
            {data.to_version.created_at && (
              <span style={{ color: '#999', marginLeft: 8 }}>
                ({new Date(data.to_version.created_at).toLocaleDateString()})
              </span>
            )}
          </span>
        </Space>
      </div>
      <ComparisonTable diff={data.diff} />
    </Card>
  );
};

export default ConfigVersionComparison;
