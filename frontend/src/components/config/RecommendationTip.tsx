import React from 'react';
import { Alert } from 'antd';
import { BulbOutlined } from '@ant-design/icons';

interface RecommendationTipProps {
  scene: string;
}

export const RecommendationTip: React.FC<RecommendationTipProps> = ({ scene }) => {
  const recommendations: Record<string, string> = {
    'llm_providers': '推荐配置 DashScope API Key，使用 qwen-max 模型获得最佳效果',
    'scene_configs': '报告生成场景推荐使用 qwen-plus，温度 0.7',
    'retrieval': 'RAG 检索阈值建议设置为 0.25，分块大小 512',
    'chunking': '英文文档建议分块大小 800，中文文档建议 512',
    'validation': '建议启用数据校验规则，提高数据质量',
    'scoring': '评分算法推荐使用加权平均，精度权重 0.4',
    'logging': '生产环境建议使用 INFO 级别日志',
    'paths': '确保数据目录和缓存目录有写入权限'
  };
  
  const tip = recommendations[scene];
  if (!tip) return null;
  
  return (
    <Alert
      message={
        <span>
          <BulbOutlined /> 推荐配置
        </span>
      }
      description={tip}
      type="info"
      showIcon={false}
      style={{ marginBottom: 16 }}
    />
  );
};
