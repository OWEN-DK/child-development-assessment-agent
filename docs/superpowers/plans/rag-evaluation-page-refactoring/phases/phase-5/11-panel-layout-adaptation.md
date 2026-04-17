# 11 - 面板布局适配 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 11 - 面板布局适配

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **Phase**: 5
> **需求点**: 11
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现固定分栏 (380px) / Drawer 抽屉式 (< 1440px) 布局适配。

## 方案设计

### 布局模式

| 模式 | 适用场景 | 宽度 | 行为 |
|------|---------|------|------|
| **固定分栏** | 屏幕宽度 >= 1440px | 380px | 右侧固定分栏，与主内容区并排 |
| **Drawer 抽屉式** | 屏幕宽度 < 1440px | 40% 屏幕宽度（最小 480px） | 从右侧滑出，覆盖主内容区 |

### 响应式策略

```typescript
// 使用 CSS media query + JavaScript 检测
const useResponsiveLayout = () => {
  const [layout, setLayout] = useState<'fixed' | 'drawer'>('fixed')
  
  useEffect(() => {
    const checkLayout = () => {
      if (window.innerWidth < 1440) {
        setLayout('drawer')
      } else {
        setLayout('fixed')
      }
    }
    
    checkLayout()
    window.addEventListener('resize', checkLayout)
    return () => window.removeEventListener('resize', checkLayout)
  }, [])
  
  return layout
}
```

### 布局组件

```tsx
// src/features/rag-eval/components/RecommendationPanel/LayoutAdapter.tsx

interface LayoutAdapterProps {
  children: React.ReactNode
  mode: 'fixed' | 'drawer'
}

export const LayoutAdapter: React.FC<LayoutAdapterProps> = ({ children, mode }) => {
  if (mode === 'drawer') {
    return (
      <Drawer
        placement="right"
        width="40%"
        style={{ minWidth: 480 }}
        closable={false}
      >
        {children}
      </Drawer>
    )
  }
  
  return (
    <aside className="fixed-sidebar" style={{ width: 380 }}>
      {children}
    </aside>
  )
}
```

### 用户手动切换

用户可通过面板顶部的 `[固定] [抽屉]` 按钮手动切换布局模式，覆盖自动响应式策略。

```typescript
interface PanelLayoutState {
  autoMode: boolean        // 是否自动响应
  forcedMode: 'fixed' | 'drawer' | null  // 用户手动指定的模式
}

const getEffectiveLayout = (state: PanelLayoutState, screenWidth: number) => {
  if (state.forcedMode) {
    return state.forcedMode
  }
  return screenWidth >= 1440 ? 'fixed' : 'drawer'
}
```

### 验收标准

- [ ] 屏幕宽度 >= 1440px 时使用固定分栏 (380px)
- [ ] 屏幕宽度 < 1440px 时自动切换为 Drawer 抽屉式
- [ ] Drawer 宽度为 40% 屏幕宽度，最小 480px
- [ ] 用户可手动切换布局模式
- [ ] 窗口 resize 时自动适配布局
