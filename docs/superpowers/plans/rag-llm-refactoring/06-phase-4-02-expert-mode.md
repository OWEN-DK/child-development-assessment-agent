# Phase 4.2: 专家模式实施

> **优先级:** P0（核心功能）
> **预估工作量:** 8-12 小时

---

## 🎯 目标

实现专家模式完整 UI，包括：
1. 侧边栏导航（分类树 + 收藏 + 健康度卡片）
2. 顶部工具栏（搜索 + 状态筛选 + 操作按钮）
3. 手风琴面板（折叠/展开 + 配置卡片）
4. 修改标记与单个撤销
5. 响应式布局适配（4 断点）

---

## 🏗️ 组件架构

```
ExpertMode (容器)
├── Sidebar (侧边栏 280px)
│   ├── CategoryTree (分类树)
│   ├── Favorites (我的收藏)
│   └── HealthScoreCard (健康度卡片 - P1)
├── TopToolbar (顶部工具栏 64px)
│   ├── SearchBox (搜索框)
│   ├── StatusFilter (状态筛选)
│   └── ActionButtons (导入/导出/保存)
└── AccordionPanel (主内容区)
    └── AccordionItem[] (折叠项)
        └── ConfigCard (配置卡片)
            ├── ConfigField (字段编辑器)
            ├── ChangeIndicator (修改标记)
            └── UndoButton (撤销按钮)
```

---

## 📐 布局与响应式

### 断点定义

**文件:** `frontend/src/components/config/constants.ts`

```typescript
export const BREAKPOINTS = {
  MOBILE: 768,
  TABLET: 1200,
  DESKTOP: 1400
} as const;

export type Breakpoint = 'mobile' | 'tablet' | 'desktop' | 'wide';

export function getBreakpoint(width: number): Breakpoint {
  if (width < BREAKPOINTS.MOBILE) return 'mobile';
  if (width < BREAKPOINTS.TABLET) return 'tablet';
  if (width < BREAKPOINTS.DESKTOP) return 'desktop';
  return 'wide';
}
```

### 布局策略

| 断点 | 侧边栏 | 主内容区 | 特殊处理 |
|------|--------|----------|----------|
| ≥1400px (wide) | 280px 固定 | 双列布局 | 健康度卡片置顶 |
| 1200-1399px (desktop) | 260px 固定 | 单列布局 | - |
| 768-1199px (tablet) | 可折叠，默认收起 | 全宽 | 汉堡菜单展开 |
| <768px (mobile) | 底部导航 | 全宽 | 配置项全宽显示 |

### 样式实现

**文件:** `frontend/src/pages/SystemConfigPage.module.scss`

```scss
.system-config-page {
  display: flex;
  height: 100vh;
  overflow: hidden;
  
  // Wide (≥1400px)
  @media (min-width: 1400px) {
    .sidebar {
      width: 280px;
      flex-shrink: 0;
    }
    .main-content {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
  }
  
  // Desktop (1200-1399px)
  @media (min-width: 1200px) and (max-width: 1399px) {
    .sidebar {
      width: 260px;
      flex-shrink: 0;
    }
    .main-content {
      flex: 1;
    }
  }
  
  // Tablet (768-1199px)
  @media (min-width: 768px) and (max-width: 1199px) {
    .sidebar {
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 260px;
      transform: translateX(-100%);
      transition: transform 0.3s ease;
      z-index: 100;
      
      &.open {
        transform: translateX(0);
      }
    }
    .main-content {
      flex: 1;
    }
  }
  
  // Mobile (<768px)
  @media (max-width: 767px) {
    flex-direction: column;
    
    .sidebar {
      display: none; // 改为底部导航
    }
    .main-content {
      flex: 1;
    }
  }
}
```

---

## 🔧 核心组件实现

### 1. Sidebar 侧边栏

**文件:** `frontend/src/components/config/Sidebar.tsx`

```typescript
import React from 'react';
import { Tree, Divider } from 'antd';
import { useConfigStore } from '../../store/configStore';
import { CATEGORY_TREE } from './constants';

interface SidebarProps {
  onSelectCategory: (key: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onSelectCategory }) => {
  const { favorites, healthDiagnostic } = useConfigStore();
  
  return (
    <div className="sidebar">
      {/* 配置分类树 */}
      <Tree
        treeData={CATEGORY_TREE}
        onSelect={(keys) => onSelectCategory(keys[0] as string)}
        defaultExpandAll
      />
      
      <Divider />
      
      {/* 我的收藏 */}
      {favorites.length > 0 && (
        <div className="favorites">
          <h4>⭐ 我的收藏</h4>
          {/* 收藏列表 */}
        </div>
      )}
      
      <Divider />
      
      {/* 健康度卡片 (P1) */}
      <div className="health-card">
        <h4>📊 健康度</h4>
        <div className="score">{healthDiagnostic?.score ?? '--'}/100</div>
      </div>
    </div>
  );
};
```

### 2. TopToolbar 顶部工具栏

**文件:** `frontend/src/components/config/TopToolbar.tsx`

```typescript
import React from 'react';
import { Button, Space } from 'antd';
import { SearchBox } from './SearchBox';
import { useConfigStore } from '../../store/configStore';

export const TopToolbar: React.FC = () => {
  const { saveConfig, isSaving } = useConfigStore();
  
  return (
    <div className="top-toolbar">
      <SearchBox />
      
      <Space>
        <Button>导入</Button>
        <Button>导出</Button>
        <Button 
          type="primary" 
          loading={isSaving}
          onClick={() => saveConfig('手动保存')}
        >
          保存
        </Button>
      </Space>
    </div>
  );
};
```

### 3. SearchBox 搜索框

**文件:** `frontend/src/components/config/SearchBox.tsx`

```typescript
import React, { useEffect, useState, useMemo, useRef } from 'react';
import { Input, AutoComplete } from 'antd';
import { useConfigStore } from '../../store/configStore';
import { CONFIG_FIELDS } from './constants';

export const SearchBox: React.FC = () => {
  const { searchQuery, setSearchQuery, configFields } = useConfigStore();
  const [localQuery, setLocalQuery] = useState(searchQuery);
  const inputRef = useRef<any>(null);
  
  // ⌘K 快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);
  
  // 使用 useMemo 缓存搜索结果，提升性能
  const options = useMemo(() => {
    if (!localQuery.trim()) return [];
    
    const query = localQuery.toLowerCase();
    return configFields
      .filter(f => 
        f.label.toLowerCase().includes(query) ||
        f.description?.toLowerCase().includes(query) ||
        f.category.toLowerCase().includes(query)
      )
      .slice(0, 10)
      .map(f => ({
        label: (
          <div>
            <div>{f.label}</div>
            <div style={{ fontSize: 12, color: '#999' }}>{f.category}</div>
          </div>
        ),
        value: f.key,
      }));
  }, [localQuery, configFields]);
  
  const handleSelect = (value: string) => {
    setSearchQuery(value);
    // 可以添加滚动到对应配置项的逻辑
  };
  
  return (
    <AutoComplete
      options={options}
      style={{ width: 300 }}
      onSelect={handleSelect}
    >
      <Input.Search
        ref={inputRef}
        placeholder="搜索配置... (⌘K)"
        value={localQuery}
        onChange={(e) => setLocalQuery(e.target.value)}
        allowClear
      />
    </AutoComplete>
  );
};
```

### 4. AccordionPanel 手风琴面板

**文件:** `frontend/src/components/config/AccordionPanel.tsx`

```typescript
import React from 'react';
import { Collapse } from 'antd';
import { ConfigCard } from './ConfigCard';
import { useConfigStore } from '../../store/configStore';
import { CATEGORY_CONFIG } from './constants';

const { Panel } = Collapse;

export const AccordionPanel: React.FC = () => {
  const { configFields, draftChanges, expandedKeys, toggleAccordion } = useConfigStore();
  
  // 按分类分组
  const groupedFields = groupByCategory(configFields);
  
  return (
    <Collapse
      activeKey={expandedKeys}
      onChange={(keys) => {
        // 更新展开状态
        toggleAccordion(keys as string[]);
      }}
    >
      {Object.entries(groupedFields).map(([category, fields]) => (
        <Panel 
          header={category} 
          key={category}
          extra={<StatusBadge category={category} />}
        >
          {fields.map(field => (
            <ConfigCard
              key={field.key}
              field={field}
              value={draftChanges[field.key] ?? field.defaultValue}
              originalValue={field.defaultValue}
              isModified={draftChanges[field.key] !== undefined}
            />
          ))}
        </Panel>
      ))}
    </Collapse>
  );
};

function groupByCategory(fields: any[]) {
  const grouped: Record<string, any[]> = {};
  fields.forEach(f => {
    const category = f.category.split('.')[0]; // 顶级分类
    if (!grouped[category]) grouped[category] = [];
    grouped[category].push(f);
  });
  return grouped;
}
```

### 5. ConfigCard 配置卡片

**文件:** `frontend/src/components/config/ConfigCard.tsx`

```typescript
import React from 'react';
import { Card, Tag } from 'antd';
import { ConfigField } from './ConfigField';
import { ChangeIndicator } from './ChangeIndicator';

interface ConfigCardProps {
  field: any;
  value: any;
  originalValue: any;
  isModified: boolean;
}

export const ConfigCard: React.FC<ConfigCardProps> = ({
  field,
  value,
  originalValue,
  isModified
}) => {
  return (
    <Card 
      className={`config-card ${isModified ? 'modified' : ''}`}
      size="small"
    >
      <div className="card-header">
        <h4>{field.label}</h4>
        {isModified && <Tag color="orange">已修改</Tag>}
      </div>
      
      <ConfigField
        field={field}
        value={value}
        onChange={(newValue) => {/* 更新 draft */}}
      />
      
      {isModified && (
        <ChangeIndicator
          originalValue={originalValue}
          newValue={value}
          onUndo={() => {/* 撤销 */}}
        />
      )}
    </Card>
  );
};
```

### 6. ChangeIndicator 修改标记

**文件:** `frontend/src/components/config/ChangeIndicator.tsx`

```typescript
import React from 'react';
import { Button, Space, Typography } from 'antd';
import { UndoOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface ChangeIndicatorProps {
  originalValue: any;
  newValue: any;
  onUndo: () => void;
}

export const ChangeIndicator: React.FC<ChangeIndicatorProps> = ({
  originalValue,
  newValue,
  onUndo
}) => {
  return (
    <div className="change-indicator">
      <Space direction="vertical" size="small">
        <div>
          <Text delete type="secondary">
            原值: {String(originalValue)}
          </Text>
        </div>
        <div>
          <Text type="success">
            新值: {String(newValue)}
          </Text>
        </div>
        <Button 
          size="small" 
          icon={<UndoOutlined />}
          onClick={onUndo}
        >
          撤销
        </Button>
      </Space>
    </div>
  );
};
```

### 7. ConfigField 字段编辑器（共享）

**文件:** `frontend/src/components/config/ConfigField.tsx`

```typescript
import React from 'react';
import { Input, InputNumber, Switch, Select } from 'antd';

interface ConfigFieldProps {
  field: any;
  value: any;
  onChange: (value: any) => void;
}

export const ConfigField: React.FC<ConfigFieldProps> = ({
  field,
  value,
  onChange
}) => {
  switch (field.type) {
    case 'bool':
      return <Switch checked={value} onChange={onChange} />;
    
    case 'int':
      return (
        <InputNumber
          value={value}
          onChange={onChange}
          min={field.min}
          max={field.max}
        />
      );
    
    case 'float':
      return (
        <InputNumber
          value={value}
          onChange={onChange}
          min={field.min}
          max={field.max}
          step={0.1}
        />
      );
    
    case 'str':
      return (
        <Input.Password 
          value={value} 
          onChange={(e) => onChange(e.target.value)}
          visibilityToggle={field.sensitive}
        />
      );
    
    case 'select':
      return (
        <Select
          value={value}
          onChange={onChange}
          options={field.options}
        />
      );
    
    default:
      return <Input value={value} onChange={(e) => onChange(e.target.value)} />;
  }
};
```

### 8. MobileNav 移动端底部导航

**文件:** `frontend/src/components/config/MobileNav.tsx`

```typescript
import React from 'react';
import { BottomNavigation, BottomNavigationAction } from '@mui/material';
import { useConfigStore } from '../../store/configStore';
import { CATEGORY_TREE } from './constants';

// 图标映射
const CATEGORY_ICONS: Record<string, string> = {
  credentials: '🔑',
  ai_models: '🤖',
  rag: '📚',
  rules: '⚙️',
  system: '📦'
};

export const MobileNav: React.FC = () => {
  const { selectedCategory, setSelectedCategory } = useConfigStore();
  
  // 仅显示顶级分类
  const topCategories = CATEGORY_TREE.filter(c => !c.key.includes('.'));
  
  const handleChange = (_event: React.SyntheticEvent, newValue: string) => {
    setSelectedCategory(newValue);
  };
  
  return (
    <BottomNavigation
      value={selectedCategory}
      onChange={handleChange}
      showLabels
      className="mobile-nav"
    >
      {topCategories.map(cat => (
        <BottomNavigationAction
          key={cat.key}
          label={cat.title.replace(/[^\u4e00-\u9fa5]/g, '')} // 仅保留中文
          value={cat.key}
          icon={<span style={{ fontSize: 20 }}>{CATEGORY_ICONS[cat.key] || '📋'}</span>}
        />
      ))}
    </BottomNavigation>
  );
};
```

**样式:** `frontend/src/components/config/MobileNav.module.scss`

```scss
.mobile-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  background: #fff;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
  
  // 仅移动端显示
  @media (min-width: 768px) {
    display: none;
  }
}
```

**集成到 SystemConfigPage:**

```typescript
// SystemConfigPage.tsx
import { MobileNav } from '../components/config/MobileNav';

const SystemConfigPage: React.FC = () => {
  const { modePreference } = useConfigStore();
  
  return (
    <div className="system-config-page">
      {/* 主内容 */}
      {modePreference === 'expert' ? <ExpertMode /> : <WizardMode />}
      
      {/* 移动端底部导航 */}
      <MobileNav />
    </div>
  );
};
```

### 9. ConfigErrorBoundary 错误边界

**文件:** `frontend/src/components/config/ConfigErrorBoundary.tsx`

```typescript
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Result, Button } from 'antd';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ConfigErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('配置组件错误:', error, errorInfo);
    // 可以上报错误日志
  }

  public render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <Result
          status="error"
          title="配置加载失败"
          subTitle={this.state.error?.message || '未知错误'}
          extra={[
            <Button 
              type="primary" 
              key="retry"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              重试
            </Button>
          ]}
        />
      );
    }

    return this.props.children;
  }
}
```

**使用方式:**

```typescript
// SystemConfigPage.tsx
import { ConfigErrorBoundary } from '../components/config/ConfigErrorBoundary';

const SystemConfigPage: React.FC = () => {
  return (
    <ConfigErrorBoundary>
      {modePreference === 'expert' ? <ExpertMode /> : <WizardMode />}
    </ConfigErrorBoundary>
  );
};
```

---

## 📊 配置分类常量

**文件:** `frontend/src/components/config/constants.ts`

```typescript
export const CATEGORY_TREE = [
  {
    title: '🔑 凭证管理',
    key: 'credentials',
    children: [
      { title: 'LLM 提供商', key: 'credentials.llm_providers' }
    ]
  },
  {
    title: '🤖 AI模型配置',
    key: 'ai_models',
    children: [
      { title: '场景模型', key: 'ai_models.scene_configs' }
    ]
  },
  {
    title: '📚 RAG知识库',
    key: 'rag',
    children: [
      { title: '检索策略', key: 'rag.retrieval' },
      { title: '分块设置', key: 'rag.chunking' }
    ]
  },
  {
    title: '⚙️ 业务规则',
    key: 'rules',
    children: [
      { title: '校验规则', key: 'rules.validation' },
      { title: '评分规则', key: 'rules.scoring' }
    ]
  },
  {
    title: '📦 系统设置',
    key: 'system',
    children: [
      { title: '日志配置', key: 'system.logging' },
      { title: '路径配置', key: 'system.paths' }
    ]
  }
];

export const SCENE_NAME_MAP: Record<string, string> = {
  assessment: '发展评估',
  reporting: '报告生成',
  validation: '数据校验',
  // ... 从后端 Schema 动态获取
};
```

---

## ✅ 验收清单

- [ ] **侧边栏导航**
  - [ ] 5 大分类显示正常
  - [ ] 点击分类平滑滚动到对应区域
  - [ ] 状态图标显示正常

- [ ] **搜索功能**
  - [ ] ⌘K 快捷键聚焦
  - [ ] 模糊匹配（名称/描述/分类）
  - [ ] 结果高亮
  - [ ] 响应时间 ≤200ms

- [ ] **手风琴折叠**
  - [ ] 展开/收起正常
  - [ ] 避免页面过长

- [ ] **修改标记**
  - [ ] 已修改配置项高亮
  - [ ] 展示"原值→新值"对比

- [ ] **单个撤销**
  - [ ] 每个修改项旁边有撤销按钮
  - [ ] 点击撤销恢复原值

- [ ] **响应式布局**
  - [ ] ≥1400px: 双列布局
  - [ ] 1200-1399px: 单列布局
  - [ ] 768-1199px: 侧边栏可折叠
  - [ ] <768px: 底部导航

---

## 📝 实施步骤

1. **Step 1:** 创建共享常量与类型定义
   - `constants.ts`: 分类树、场景映射、断点
   - `types.ts`: ConfigFieldMetadata、Category 等

2. **Step 2:** 实现基础组件
   - `ConfigField.tsx`: 字段编辑器
   - `ChangeIndicator.tsx`: 修改标记
   - `ConfigCard.tsx`: 配置卡片

3. **Step 3:** 实现布局组件
   - `Sidebar.tsx`: 侧边栏
   - `TopToolbar.tsx`: 顶部工具栏
   - `SearchBox.tsx`: 搜索框
   - `AccordionPanel.tsx`: 手风琴面板

4. **Step 4:** 重构 SystemConfigPage
   - 集成 ExpertMode
   - 实现响应式样式
   - 修复分类过滤逻辑

5. **Step 5:** 测试与验证
   - 功能测试
   - 响应式测试
   - 性能测试（搜索 ≤200ms）

---

**返回总览：** [06-phase-4-00-overview.md](./06-phase-4-00-overview.md)
