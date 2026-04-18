import React, { useState } from 'react';
import { Steps, Button, Space, Result, message } from 'antd';
import { StepContent } from './StepContent';
import { useConfig } from '../../features/config/hooks/useConfig';

const WIZARD_STEPS = [
  {
    title: '基础配置',
    description: '配置 LLM 提供商的 API 密钥和基础模型选择',
    categories: ['models'],
    skipAction: 'use_env_defaults'
  },
  {
    title: '高级配置',
    description: '配置 RAG 知识库和业务规则',
    categories: ['rag', 'rules'],
    skipAction: 'use_system_recommendations'
  },
  {
    title: '系统设置',
    description: '配置应用、日志、路径等系统设置',
    categories: ['app', 'logging', 'paths', 'other'],
    skipAction: 'use_factory_defaults'
  }
];

export const WizardMode: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [completed, setCompleted] = useState(false);
  
  const { saveConfig, isSaving, switchMode, updateDraft } = useConfig();
  
  const handleNext = () => {
    if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  };
  
  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };
  
  const handleSkip = () => {
    const step = WIZARD_STEPS[currentStep];
    applyDefaults(step.skipAction, updateDraft);
    handleNext();
  };
  
  const handleComplete = async () => {
    try {
      await saveConfig('向导模式配置完成');
      setCompleted(true);
      message.success('配置已保存');
    } catch (error) {
      message.error('保存失败');
    }
  };
  
  const handleSwitchToExpert = () => {
    switchMode('expert');
  };
  
  if (completed) {
    return (
      <Result
        status="success"
        title="配置完成"
        subTitle="所有配置已保存成功"
        extra={[
          <Button type="primary" key="done" onClick={() => setCompleted(false)}>
            继续编辑
          </Button>,
          <Button key="expert" onClick={handleSwitchToExpert}>
            切换专家模式
          </Button>
        ]}
      />
    );
  }
  
  return (
    <div style={{ padding: '24px', maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <Steps
          current={currentStep}
          onChange={setCurrentStep}
          items={WIZARD_STEPS.map((step, index) => ({
            title: step.title,
            description: step.description,
            status: index < currentStep ? 'finish' : index === currentStep ? 'process' : 'wait'
          }))}
        />
      </div>
      
      <StepContent
        step={WIZARD_STEPS[currentStep]}
        stepIndex={currentStep}
      />
      
      <div style={{ marginTop: 24, padding: '16px 0', borderTop: '1px solid #f0f0f0' }}>
        <Space>
          <Button onClick={handleSwitchToExpert}>
            ← 切换专家模式
          </Button>
          <Button onClick={handleSkip}>
            跳过此步
          </Button>
          {currentStep > 0 && (
            <Button onClick={handlePrev}>
              上一步
            </Button>
          )}
          <Button type="primary" onClick={handleNext} loading={isSaving}>
            {currentStep === WIZARD_STEPS.length - 1 ? '完成' : '下一步'}
          </Button>
        </Space>
      </div>
    </div>
  );
};

function applyDefaults(action: string, updateDraft: (key: string, value: any) => void) {
  const DEFAULT_VALUES: Record<string, Record<string, any>> = {
    use_env_defaults: {
      llm_providers: {
        dashscope: {
          api_key: '',
          base_url: 'https://dashscope.aliyuncs.com'
        }
      },
      llm_scene_configs: {
        assessment: { provider: 'dashscope', model: 'qwen-plus', temperature: 0.7, max_tokens: 2000 },
        reporting: { provider: 'dashscope', model: 'qwen-plus', temperature: 0.5, max_tokens: 4000 },
        validation: { provider: 'dashscope', model: 'qwen-turbo', temperature: 0.1, max_tokens: 1000 }
      }
    },
    use_system_recommendations: {
      rag_retrieval: {
        strategy: 'hybrid',
        chunk_size: 512,
        chunk_overlap: 50,
        score_threshold: 0.25,
        top_k: 5
      },
      rules: {
        validation: { enable_strict_mode: true, max_retries: 3 },
        scoring: { algorithm: 'weighted_average' }
      }
    },
    use_factory_defaults: {
      system: {
        logging: { level: 'INFO', path: '/var/log/app.log' },
        paths: { data_dir: './data', cache_dir: './cache' },
        app: { name: '儿童发展评估系统', version: '1.0.0' }
      }
    }
  };

  const defaults = DEFAULT_VALUES[action];
  if (!defaults) {
    console.warn(`未找到默认值配置: ${action}`);
    return;
  }
  
  Object.entries(defaults).forEach(([category, values]) => {
    function setValues(obj: any, prefix: string = '') {
      Object.entries(obj).forEach(([key, value]) => {
        const fullPath = prefix ? `${prefix}.${key}` : key;
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          setValues(value, fullPath);
        } else {
          updateDraft(fullPath, value);
        }
      });
    }
    setValues(values, category);
  });
}
