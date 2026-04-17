# Phase 4.5: 向导模式实施

> **优先级:** P1
> **预估工作量:** 6-8 小时

---

## 🎯 目标

实现向导模式，提供分步引导配置体验：
1. 3 步流程（基础配置 → 高级配置 → 系统设置）
2. 每步可跳过，跳过则使用默认值
3. 推荐默认值展示
4. 进度保存（自动保存到 draftChanges）
5. 随时切换回专家模式，不丢失进度

---

## 🏗️ 组件架构

```
WizardMode (容器)
├── StepNavigator (步骤导航器)
│   ├── Step 1: 基础配置
│   ├── Step 2: 高级配置
│   └── Step 3: 系统设置
├── StepContent (步骤内容)
│   ├── SceneGroup (场景分组)
│   │   ├── ConfigField (配置字段)
│   │   └── RecommendationTip (推荐提示)
│   └── SkipButton (跳过按钮)
└── StepActions (步骤操作)
    ├── 上一步
    └── 下一步/完成
```

---

## 📋 步骤定义

| 步骤 | 名称 | 包含分类 | 跳过行为 |
|------|------|----------|----------|
| 1 | 基础配置 | 凭证管理 + 核心场景模型 | 使用 .env.dev 默认值 |
| 2 | 高级配置 | RAG 知识库 + 业务规则 | 使用系统推荐配置 |
| 3 | 系统设置 | 系统设置 + 其他配置 | 使用出厂默认值 |

---

## 🔧 核心组件实现

### 1. WizardMode 容器

**文件:** `frontend/src/components/config/WizardMode.tsx`

```typescript
import React, { useState } from 'react';
import { Steps, Button, Space, Result } from 'antd';
import { StepContent } from './StepContent';
import { StepNavigator } from './StepNavigator';
import { useConfigStore } from '../../store/configStore';

const WIZARD_STEPS = [
  {
    title: '基础配置',
    description: '配置 LLM 提供商的 API 密钥和基础模型选择',
    categories: ['credentials', 'ai_models'],
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
    description: '配置日志、路径等系统设置',
    categories: ['system'],
    skipAction: 'use_factory_defaults'
  }
];

export const WizardMode: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [completed, setCompleted] = useState(false);
  
  const { saveConfig, isSaving, switchMode, updateDraft } = useConfigStore();
  
  const handleNext = () => {
    if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      // 最后一步，保存配置
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
    // 根据 skipAction 应用默认值
    applyDefaults(step.skipAction, updateDraft);
    handleNext();
  };
  
  const handleComplete = async () => {
    await saveConfig('向导模式配置完成');
    setCompleted(true);
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
    <div className="wizard-mode">
      <StepNavigator
        steps={WIZARD_STEPS}
        current={currentStep}
        onChange={setCurrentStep}
      />
      
      <StepContent
        step={WIZARD_STEPS[currentStep]}
        stepIndex={currentStep}
      />
      
      <div className="step-actions">
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
```

### 2. StepNavigator 步骤导航器

**文件:** `frontend/src/components/config/StepNavigator.tsx`

```typescript
import React from 'react';
import { Steps } from 'antd';

interface StepInfo {
  title: string;
  description: string;
  categories: string[];
  skipAction: string;
}

interface StepNavigatorProps {
  steps: StepInfo[];
  current: number;
  onChange: (current: number) => void;
}

export const StepNavigator: React.FC<StepNavigatorProps> = ({
  steps,
  current,
  onChange
}) => {
  return (
    <Steps
      current={current}
      onChange={onChange}
      items={steps.map((step, index) => ({
        title: step.title,
        description: step.description,
        status: index < current ? 'finish' : index === current ? 'process' : 'wait'
      }))}
    />
  );
};
```

### 3. StepContent 步骤内容

**文件:** `frontend/src/components/config/StepContent.tsx`

```typescript
import React from 'react';
import { Card, Typography, Divider } from 'antd';
import { ConfigField } from './ConfigField';
import { RecommendationTip } from './RecommendationTip';
import { useConfigStore } from '../../store/configStore';

const { Title, Paragraph } = Typography;

interface StepContentProps {
  step: any;
  stepIndex: number;
}

export const StepContent: React.FC<StepContentProps> = ({ step, stepIndex }) => {
  const { configFields, draftChanges, updateDraft } = useConfigStore();
  
  // 过滤当前步骤的配置字段
  const filteredFields = configFields.filter(f =>
    step.categories.some((cat: string) =>
      f.category === cat || f.category.startsWith(`${cat}.`)
    )
  );
  
  // 按场景分组
  const groupedFields = groupByScene(filteredFields);
  
  return (
    <div className="step-content">
      <Title level={4}>{step.title}</Title>
      <Paragraph type="secondary">{step.description}</Paragraph>
      
      <Divider />
      
      {Object.entries(groupedFields).map(([scene, fields]) => (
        <Card
          key={scene}
          title={formatSceneTitle(scene)}
          size="small"
          className="scene-group"
          extra={<RecommendationTip scene={scene} />}
        >
          {fields.map(field => (
            <ConfigField
              key={field.key}
              field={field}
              value={draftChanges[field.key] ?? field.defaultValue}
              onChange={(value) => updateDraft(field.key, value)}
            />
          ))}
        </Card>
      ))}
    </div>
  );
};

function groupByScene(fields: any[]) {
  const grouped: Record<string, any[]> = {};
  fields.forEach(f => {
    const scene = f.category.split('.')[1] || f.category;
    if (!grouped[scene]) grouped[scene] = [];
    grouped[scene].push(f);
  });
  return grouped;
}

function formatSceneTitle(scene: string): string {
  return scene
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase());
}
```

### 5. applyDefaults 实现

**文件:** `frontend/src/components/config/WizardMode.tsx`

```typescript
// 默认值配置
const DEFAULT_VALUES: Record<string, Record<string, any>> = {
  use_env_defaults: {
    llm_providers: {
      dashscope: {
        api_key: process.env.REACT_APP_DASHSCOPE_API_KEY || '',
        base_url: process.env.REACT_APP_DASHSCOPE_BASE_URL || 'https://dashscope.aliyuncs.com'
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
      scoring: { algorithm: 'weighted_average', weights: { precision: 0.4, recall: 0.3, relevance: 0.3 } }
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

function applyDefaults(action: string, updateDraft: (key: string, value: any) => void) {
  const defaults = DEFAULT_VALUES[action];
  if (!defaults) {
    console.warn(`未找到默认值配置: ${action}`);
    return;
  }
  
  // 将默认值应用到 draftChanges
  Object.entries(defaults).forEach(([category, values]) => {
    // 递归设置所有字段
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
```

### 6. RecommendationTip 推荐提示

**文件:** `frontend/src/components/config/RecommendationTip.tsx`

```typescript
import React from 'react';
import { Alert, Tooltip } from 'antd';
import { BulbOutlined } from '@ant-design/icons';

interface RecommendationTipProps {
  scene: string;
}

export const RecommendationTip: React.FC<RecommendationTipProps> = ({ scene }) => {
  const recommendations: Record<string, string> = {
    'llm_providers': '推荐配置 DashScope API Key，使用 qwen-max 模型获得最佳效果',
    'scene_configs': '报告生成场景推荐使用 qwen-plus，温度 0.7',
    'retrieval': 'RAG 检索阈值建议设置为 0.25，分块大小 512',
    'validation': '建议启用数据校验规则，提高数据质量'
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
```

---

## 🔄 模式切换

### 切换入口

- **专家模式**: 侧边栏底部"→ 向导模式"链接
- **向导模式**: 步骤导航栏左侧"← 切换专家模式"链接

### 数据共享

- 两种模式编辑**同一份配置数据**
- draftChanges 在模式切换时**不丢失**
- 切换时不触发保存，仅切换 UI 展示方式

**实现:**

```typescript
// SystemConfigPage.tsx
const { modePreference } = useConfigStore();

return (
  <div className="system-config-page">
    {modePreference === 'expert' ? (
      <ExpertMode />
    ) : (
      <WizardMode />
    )}
  </div>
);
```

---

## ✅ 验收清单

- [ ] **步骤流程**
  - [ ] 3 步流程完整
  - [ ] 步骤导航器正常
  - [ ] 上一步/下一步正常

- [ ] **跳过功能**
  - [ ] 每步可跳过
  - [ ] 跳过应用默认值
  - [ ] 默认值正确

- [ ] **推荐提示**
  - [ ] 每个场景显示推荐配置
  - [ ] 提示信息准确

- [ ] **模式切换**
  - [ ] 可随时切换专家模式
  - [ ] 切换后 draftChanges 不丢失
  - [ ] 切换流畅

- [ ] **完成流程**
  - [ ] 最后一步显示"完成"
  - [ ] 点击完成保存配置
  - [ ] 显示成功结果页

---

## 📝 实施步骤

1. **Step 1:** 实现 WizardMode 容器
   - 步骤状态管理
   - 上一步/下一步逻辑
   - 跳过逻辑
   - 完成逻辑

2. **Step 2:** 实现 StepNavigator
   - Steps 组件
   - 状态显示

3. **Step 3:** 实现 StepContent
   - 配置字段过滤
   - 场景分组
   - 推荐提示

4. **Step 4:** 实现 RecommendationTip
   - 推荐配置映射
   - Alert 组件

5. **Step 5:** 模式切换集成
   - SystemConfigPage 集成
   - draftChanges 共享

6. **Step 6:** 测试与验证
   - 流程测试
   - 跳过测试
   - 切换测试

---

**返回总览：** [06-phase-4-00-overview.md](./06-phase-4-00-overview.md)
