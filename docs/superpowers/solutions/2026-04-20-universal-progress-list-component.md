# 通用异步任务进度列表组件技术方案

> **文档版本**: v1.0  
> **创建日期**: 2026-04-20  
> **状态**: 方案评审中  
> **适用场景**: 文档上传进度、草稿生成进度、模型训练进度等所有异步任务场景  

---

## 一、需求背景

### 1.1 当前问题

| 问题 | 代码位置 | 根因 | 影响 |
|------|----------|------|------|
| 草稿生成使用 Modal 弹窗 | `DraftManagementPage.tsx:537-574` | 阻塞用户操作，无法并行处理其他任务 | 用户体验差 |
| 缺少阶段信息展示 | 同上 | 仅显示"正在生成 [粗大动作] [1-3岁]" | 用户无法感知处理阶段 |
| 无取消/中断功能 | 同上 | 后端未暴露取消 API | 用户无法主动终止长任务 |
| 知识库上传取消后数据不清除 | `useDocumentManagement.ts:58` | cancelled 状态保留 30 秒 | 列表显示已取消任务，造成困惑 |
| 进度组件重复开发 | `TaskProgressList.tsx` + `DraftManagementPage.tsx` | 缺乏抽象，每个场景独立实现 | 维护成本高，样式不一致 |

### 1.2 用户目标

- 异步任务进度统一展示为**内嵌列表**，不阻塞用户操作
- 支持**多任务并行**展示（如同时上传多个文档、同时生成多批草稿）
- 显示**阶段信息**、**加载图标**、**百分比进度**
- 提供**取消/中断**按钮，取消后立即从列表移除
- 组件可复用，适配不同业务场景（文档上传、草稿生成、模型训练等）

---

## 二、业内通用方案调研

### 2.1 主流产品进度展示模式

| 产品 | 展示方式 | 核心特性 | 可借鉴点 |
|------|----------|----------|----------|
| **GitHub Actions** | 内嵌列表 + 状态图标 | 阶段拆分、日志折叠、实时刷新 | 阶段可视化、状态映射 |
| **Vercel Deployments** | 卡片列表 + 进度条 | 步骤拆解、耗时统计、一键取消 | 步骤进度、取消交互 |
| **GitLab CI/CD** | 流水线视图 | 阶段依赖、并行任务、重试机制 | 任务编排可视化 |
| **Ant Design Pro** | Table + Progress | 批量操作、状态筛选、操作列 | 批量管理、状态过滤 |
| **Material-UI** | List + LinearProgress | 简洁列表、状态颜色映射 | 组件组合模式 |

### 2.2 核心设计模式提取

**模式 1: 任务卡片列表 (Task Card List)**
```
┌─────────────────────────────────────────────────────────┐
│ 🔵 正在处理的文档                                        │
├─────────────────────────────────────────────────────────┤
│ ⏳ 文档 A.pdf                              处理中  45%   │
│ ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│ 阶段：正在分块 (3/5)                                     │
│                                    [中断]                │
├─────────────────────────────────────────────────────────┤
│ ⏳ 文档 B.epub                             处理中  12%   │
│ ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│ 阶段：正在解析                                           │
│                                    [中断]                │
└─────────────────────────────────────────────────────────┘
```

**模式 2: 步骤进度条 (Stepped Progress)**
```
解析 ████████░░ 分块 ░░░░░░░░ 嵌入 ░░░░░░░░ 索引 ░░░░░░░░
```

**模式 3: 状态徽章 + 操作列 (Status Badge + Actions)**
```
文件名          状态      进度    操作
文档 A.pdf     🟡 处理中   45%    [中断]
文档 B.pdf     🟢 已完成   100%   [查看]
文档 C.pdf     🔴 失败     67%    [重试] [删除]
```

### 2.3 方案选择

**采用模式 1 + 模式 3 组合**：
- 列表形式展示多任务
- 每个任务卡片包含：标题、状态图标、进度条、阶段信息、操作按钮
- 参考 Ant Design `List` + `Progress` + `Space` 组件组合

---

## 三、架构设计

### 3.1 组件分层架构

```
frontend/src/components/progress/
├── ProgressList.tsx              # 通用进度列表组件（展示层）
├── ProgressListItem.tsx          # 单个任务卡片组件（展示层）
├── types.ts                      # 类型定义（接口层）
├── hooks/
│   └── useProgressPolling.ts     # 轮询逻辑抽象（逻辑层）
└── configs/
    ├── documentUpload.ts         # 文档上传配置（适配层）
    └── draftGeneration.ts        # 草稿生成配置（适配层）
```

### 3.2 数据流设计

```
业务页面 (DraftManagementPage / KnowledgeBasePage)
    ↓
useProgressPolling Hook (轮询 + SSE 监听)
    ↓
ProgressList 组件 (渲染列表)
    ↓
ProgressListItem 组件 (渲染单个任务)
    ↓
Ant Design 组件 (Progress, List, Button, Typography)
```

### 3.3 类型系统设计

```typescript
// 1. 基础任务状态（所有场景通用）
interface BaseProgressTask {
  taskId: string;
  status: TaskStatus;
  progress: number;           // 0-100
  message: string;            // 当前阶段描述
  createdAt: number;          // 创建时间戳
  error?: string;             // 错误信息
}

// 2. 任务状态枚举
type TaskStatus = 
  | 'pending'      // 等待中
  | 'processing'   // 处理中
  | 'success'      // 成功
  | 'failed'       // 失败
  | 'cancelled';   // 已取消

// 3. 场景扩展类型（通过泛型支持）
interface DocumentUploadTask extends BaseProgressTask {
  filename: string;
  stage?: 'parsing' | 'chunking' | 'embedding' | 'indexing';
}

interface DraftGenerationTask extends BaseProgressTask {
  domain: string;
  ageStage: string;
  generated?: number;
  deduplicated?: number;
}

// 4. 组件配置接口
interface ProgressListConfig<T extends BaseProgressTask> {
  title: string;                              // 列表标题
  emptyText?: string;                         // 空状态文案
  getItemKey: (task: T) => string;            // 唯一键提取
  getItemTitle: (task: T) => ReactNode;       // 标题渲染
  getItemSubtitle?: (task: T) => ReactNode;   // 副标题（可选）
  getStageText?: (task: T) => ReactNode;      // 阶段信息（可选）
  showProgress: boolean;                      // 是否显示进度条
  showStage: boolean;                         // 是否显示阶段
  onCancel?: (task: T) => void;               // 取消回调
  onDelete?: (task: T) => void;               // 删除回调
  onRetry?: (task: T) => void;                // 重试回调（可选）
  autoRemoveOnSuccess?: boolean;              // 成功后自动移除
  autoRemoveOnCancel?: boolean;               // 取消后自动移除
  successKeepSeconds?: number;                // 成功后保留秒数
  cancelKeepSeconds?: number;                 // 取消后保留秒数
  failedKeepSeconds?: number;                 // 失败后保留秒数
}
```

---

## 四、核心组件设计

### 4.1 ProgressList 组件

**职责**：渲染任务列表容器，处理空状态、加载状态

```typescript
interface ProgressListProps<T extends BaseProgressTask> {
  config: ProgressListConfig<T>;
  tasks: T[];
  loading?: boolean;
}

// 使用示例
<ProgressList
  config={documentUploadConfig}
  tasks={processingTasks}
  loading={loading}
/>
```

**关键设计决策**：
- 使用泛型 `T extends BaseProgressTask` 保证类型安全
- 配置对象模式避免 Props 爆炸
- 支持自定义渲染函数（标题、副标题、阶段信息）

### 4.2 ProgressListItem 组件

**职责**：渲染单个任务卡片，包含进度条、状态图标、操作按钮

```typescript
interface ProgressListItemProps<T extends BaseProgressTask> {
  task: T;
  config: ProgressListConfig<T>;
}

// 内部结构
┌─────────────────────────────────────────────────────────┐
│ [状态图标]  [标题]  [状态文本]                    [操作按钮] │
│ ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│ [阶段信息]                                               │
└─────────────────────────────────────────────────────────┘
```

**状态映射规则**：

| 状态 | 图标 | 颜色 | 进度条 status |
|------|------|------|---------------|
| pending | `ClockCircleOutlined` | 灰色 | `normal` |
| processing | `LoadingOutlined` (spin) | 蓝色 | `active` |
| success | `CheckCircleOutlined` | 绿色 | `success` |
| failed | `CloseCircleOutlined` | 红色 | `exception` |
| cancelled | `StopOutlined` | 橙色 | `exception` |

### 4.3 useProgressPolling Hook

**职责**：抽象轮询逻辑，支持 SSE + 定时轮询双模式

```typescript
interface UseProgressPollingOptions {
  fetchTasks: () => Promise<Task[]>;        // 获取任务列表
  cancelTask: (taskId: string) => Promise<void>;  // 取消任务
  pollingInterval?: number;                 // 轮询间隔（默认 2000ms）
  sseUrl?: string;                          // SSE 地址（可选）
  onTaskComplete?: (task: Task) => void;    // 任务完成回调
  onTaskFailed?: (task: Task) => void;      // 任务失败回调
}

// 使用示例
const { 
  tasks, 
  loading, 
  cancelTask, 
  refreshTasks 
} = useProgressPolling({
  fetchTasks: fetchDraftTasks,
  cancelTask: cancelDraftTask,
  pollingInterval: 2000,
  sseUrl: `/api/drafts/generate/${taskId}/stream`,
});
```

**关键设计决策**：
- 轮询与 SSE 解耦，SSE 仅用于实时推送，轮询用于状态同步
- 自动清理已完成/取消的任务（根据配置保留时间）
- 支持断线重连（SSE 模式）

---

## 五、业务场景适配

### 5.1 文档上传场景配置

```typescript
// configs/documentUpload.ts
export const documentUploadConfig: ProgressListConfig<DocumentUploadTask> = {
  title: '正在处理的文档',
  emptyText: '暂无正在处理的任务',
  getItemKey: (task) => task.taskId,
  getItemTitle: (task) => task.filename,
  getItemSubtitle: (task) => formatFileSize(task.fileSize),
  getStageText: (task) => {
    const stageMap = {
      parsing: '正在解析',
      chunking: '正在分块',
      embedding: '正在嵌入',
      indexing: '正在索引',
    };
    return task.stage ? stageMap[task.stage] : null;
  },
  showProgress: true,
  showStage: true,
  onCancel: (task) => cancelUploadTask(task.taskId),
  onDelete: (task) => deleteFailedTask(task.taskId),
  autoRemoveOnSuccess: true,
  autoRemoveOnCancel: true,
  successKeepSeconds: 3,    // 成功后保留 3 秒
  cancelKeepSeconds: 2,     // 取消后保留 2 秒
  failedKeepSeconds: 3600,  // 失败后保留 1 小时
};
```

### 5.2 草稿生成场景配置

```typescript
// configs/draftGeneration.ts
export const draftGenerationConfig: ProgressListConfig<DraftGenerationTask> = {
  title: '草稿生成任务',
  emptyText: '暂无草稿生成任务',
  getItemKey: (task) => task.taskId,
  getItemTitle: (task) => `生成草稿：${task.domain}`,
  getItemSubtitle: (task) => `年龄段：${task.ageStage}`,
  getStageText: (task) => {
    if (task.status === 'processing') {
      return `正在生成 [${task.domain}] [${task.ageStage}]`;
    }
    return null;
  },
  showProgress: true,
  showStage: true,
  onCancel: (task) => cancelDraftGeneration(task.taskId),
  autoRemoveOnSuccess: true,
  autoRemoveOnCancel: true,
  successKeepSeconds: 5,    // 成功后保留 5 秒（用户需要看到完成提示）
  cancelKeepSeconds: 2,     // 取消后保留 2 秒
  failedKeepSeconds: 3600,  // 失败后保留 1 小时
};
```

---

## 六、后端 API 设计

### 6.1 草稿生成取消接口

**端点**：`POST /rag/test/drafts/generate/{task_id}/cancel`

**请求**：
```json
{
  "task_id": "uuid-string"
}
```

**响应**：
```json
{
  "code": 0,
  "message": "取消请求已发送",
  "data": {
    "task_id": "uuid-string",
    "status": "cancelling"
  }
}
```

**实现逻辑**：
```python
@router.post("/drafts/generate/{task_id}/cancel")
async def cancel_draft_generation(task_id: str):
    """取消草稿生成任务"""
    success = await async_task_manager.cancel_task(task_id)
    
    if success:
        # 推送取消事件到 SSE
        await SSEPublisher.publish(
            f"draft_generation:{task_id}",
            {
                "type": "cancelled",
                "message": "任务已取消",
                "task_id": task_id
            }
        )
        return APIResponse.success(
            data={"task_id": task_id, "status": "cancelled"},
            message="取消请求已发送"
        )
    else:
        raise TaskNotFoundException(task_id=task_id)
```

### 6.2 任务状态查询接口

**端点**：`GET /rag/test/drafts/generate/tasks`

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "tasks": [
      {
        "task_id": "uuid-1",
        "status": "processing",
        "progress": 45,
        "message": "正在生成 [感觉统合] [3-6岁]",
        "domain": "感觉统合",
        "age_stage": "3-6岁",
        "generated": 15,
        "created_at": 1713600000
      },
      {
        "task_id": "uuid-2",
        "status": "success",
        "progress": 100,
        "message": "生成完成",
        "domain": "粗大动作",
        "age_stage": "1-3岁",
        "generated": 30,
        "created_at": 1713599000
      }
    ]
  }
}
```

---

## 七、取消后数据清除修复

### 7.1 问题根因

**当前逻辑** (`useDocumentManagement.ts:55-61`)：
```typescript
const activeTasks = res.tasks.filter(t =>
  t.status === 'pending' ||
  t.status === 'processing' ||
  (t.status === 'cancelled' && (Date.now() / 1000 - t.created_at < 30)) ||  // ❌ 保留 30 秒
  (t.status === 'failed' && (Date.now() / 1000 - t.created_at < 3600)) ||
  (t.status === 'success' && (Date.now() / 1000 - t.created_at < 5))
);
```

**问题**：
- cancelled 状态保留 30 秒过长，用户看到已取消任务仍显示在列表中
- 取消后立即刷新列表，但后端仍返回 cancelled 状态，导致前端重新显示

### 7.2 修复方案

**方案 A：前端立即移除（推荐）**
```typescript
// 取消操作后立即从本地状态移除
const handleCancel = useCallback(async (taskId: string) => {
  try {
    await cancelUploadTask(taskId);
    // 立即从本地状态移除，不等轮询
    setProcessingTasks(prev => prev.filter(t => t.task_id !== taskId));
    notification.info('已请求取消任务...');
  } catch (e: any) {
    const apiError = extractApiError(e);
    notification.error(`取消失败: ${apiError.message}`);
  }
}, []);
```

**方案 B：缩短保留时间**
```typescript
const activeTasks = res.tasks.filter(t =>
  t.status === 'pending' ||
  t.status === 'processing' ||
  (t.status === 'cancelled' && (Date.now() / 1000 - t.created_at < 3)) ||  // ✅ 缩短到 3 秒
  (t.status === 'failed' && (Date.now() / 1000 - t.created_at < 3600)) ||
  (t.status === 'success' && (Date.now() / 1000 - t.created_at < 3))
);
```

**推荐方案 A**：用户体验更好，取消后立即消失，符合用户预期。

---

## 八、SSE 事件增强

### 8.1 草稿生成 SSE 事件扩展

| 事件类型 | 数据 | 说明 | 前端处理 |
|----------|------|------|----------|
| `draft_generation_started` | `{task_id, total_combinations, total_drafts}` | 任务开始 | 添加到任务列表 |
| `draft_combination_progress` | `{current_combination, total_combinations, domain, age_stage, generated}` | 组合进度 | 更新进度条和阶段信息 |
| `draft_generation_completed` | `{task_id, total, duration}` | 任务完成 | 标记为 success，N 秒后移除 |
| `draft_generation_failed` | `{task_id, error, combination}` | 组合失败 | 标记为 failed，显示错误 |
| `draft_generation_cancelled` | `{task_id, total, reason}` | 任务取消 | 标记为 cancelled，立即移除 |

### 8.2 SSE 断线重连机制

```typescript
// useProgressPolling.ts 内部实现
const connectSSE = (taskId: string) => {
  const es = new EventSource(`${API_BASE_URL}/drafts/generate/${taskId}/stream`);
  
  es.addEventListener('error', () => {
    es.close();
    // 指数退避重连
    if (retryCount < MAX_RETRIES) {
      const delay = Math.min(1000 * Math.pow(2, retryCount), 16000);
      retryCount++;
      setTimeout(() => connectSSE(taskId), delay);
    }
  });
  
  return es;
};
```

---

## 九、验证指标与方法

### 9.1 功能验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| **内嵌列表展示** | 草稿生成进度嵌入页面，不弹窗 | 手动测试 |
| **多任务并行** | 同时显示多个任务卡片 | 手动测试 |
| **阶段信息** | 显示当前处理阶段（如"正在分块"） | 手动测试 |
| **加载图标** | 处理中任务显示旋转图标 | 手动测试 |
| **百分比进度** | 进度条显示百分比或"当前/总数" | 手动测试 |
| **取消功能** | 点击取消按钮后任务立即消失 | 手动测试 |
| **取消后清除** | 取消后列表不显示已取消任务 | 手动测试 |
| **成功后清除** | 成功后 N 秒自动移除 | 手动测试 |
| **失败后保留** | 失败后保留 1 小时，显示错误信息 | 手动测试 |
| **SSE 实时推送** | 进度更新延迟 < 1 秒 | 网络抓包 |
| **断线重连** | SSE 断开后自动重连，进度不丢失 | 断开网络测试 |

### 9.2 性能验收标准

| 指标 | 目标值 | 验证方法 |
|------|--------|----------|
| **列表渲染延迟** | < 100ms（10 个任务） | React DevTools Profiler |
| **轮询间隔** | 2 秒（可配置） | 网络请求监控 |
| **SSE 消息处理** | < 50ms/条 | 性能监控 |
| **内存占用** | < 50MB（100 个任务历史） | Chrome DevTools Memory |

---

## 十、风险评估与兜底策略

### 10.1 技术风险

| 风险项 | 风险等级 | 触发条件 | 规避措施 | 应急方案 |
|--------|----------|----------|----------|----------|
| **SSE 连接不稳定** | 中 | 网络波动、代理超时 | 指数退避重连 + 轮询兜底 | 纯轮询模式 |
| **任务状态不一致** | 低 | 后端更新延迟 | 轮询同步 + 乐观更新 | 手动刷新按钮 |
| **取消接口失败** | 低 | 后端未实现 | 前端禁用取消按钮 | 降级为不可取消 |
| **组件泛型类型复杂** | 低 | TypeScript 编译错误 | 提供默认类型参数 | 降级为 any 类型 |

### 10.2 用户体验风险

| 风险项 | 风险等级 | 触发条件 | 规避措施 | 应急方案 |
|--------|----------|----------|----------|----------|
| **取消后立即消失，用户困惑** | 低 | 取消反馈不明显 | 取消前二次确认 + Toast 提示 | 保留 3 秒再移除 |
| **多任务列表过长** | 中 | 同时运行 10+ 任务 | 列表滚动 + 分页 | 折叠已完成任务 |
| **进度条跳动** | 低 | SSE 消息乱序 | 进度只增不减逻辑 | 后端保证顺序 |

---

## 十一、实施计划

### 11.1 阶段划分

| 阶段 | 工作内容 | 预计工时 | 依赖项 |
|------|----------|----------|--------|
| **Phase 1** | 类型定义与接口设计（types.ts） | 0.5h | 无 |
| **Phase 2** | ProgressListItem 组件实现 | 1h | Phase 1 |
| **Phase 3** | ProgressList 组件实现 | 0.5h | Phase 2 |
| **Phase 4** | useProgressPolling Hook 实现 | 1h | Phase 1 |
| **Phase 5** | 文档上传场景适配（迁移现有逻辑） | 1h | Phase 2-4 |
| **Phase 6** | 草稿生成场景适配（新建配置） | 0.5h | Phase 2-4 |
| **Phase 7** | 后端取消接口实现 | 0.5h | 无 |
| **Phase 8** | 后端任务状态查询接口 | 0.5h | Phase 7 |
| **Phase 9** | 取消后数据清除修复 | 0.5h | Phase 5 |
| **Phase 10** | 测试与验证 | 1h | Phase 1-9 |

**总计**：约 7 小时

### 11.2 关键里程碑

- **M1（Phase 1-4）**：通用组件与 Hook 完成，可独立运行
- **M2（Phase 5-6）**：两个业务场景适配完成，替换现有实现
- **M3（Phase 7-9）**：后端 API 完成，端到端联调通过
- **M4（Phase 10）**：测试通过，验收达标

---

## 十二、已确定事项

| 序号 | 事项 | 决策 |
|------|------|------|
| 1 | **组件抽象方式** | 泛型 + 配置对象模式，避免 Props 爆炸 |
| 2 | **展示方式** | 内嵌列表，不弹窗，支持多任务并行 |
| 3 | **状态映射** | 5 种状态（pending/processing/success/failed/cancelled） |
| 4 | **取消后清除** | 前端立即移除，不等轮询（方案 A） |
| 5 | **成功后保留** | 3-5 秒（根据场景配置） |
| 6 | **失败后保留** | 1 小时，显示错误信息 |
| 7 | **轮询间隔** | 2 秒（可配置） |
| 8 | **SSE 重连** | 指数退避（1s → 2s → 4s → 8s → 16s），最多 5 次 |
| 9 | **进度条样式** | Ant Design Progress 组件，active 状态 |
| 10 | **阶段信息** | 根据业务场景自定义渲染函数 |

---

## 十三、待讨论事项

1. **任务历史记录**：是否需要保留已完成任务的历史记录？保留多久？
2. **批量操作**：是否需要支持批量取消多个任务？
3. **进度持久化**：刷新页面后是否恢复进度显示？（需后端支持任务状态持久化）
4. **通知推送**：任务完成/失败时是否需要桌面通知？
5. **移动端适配**：是否需要针对移动端优化展示方式？

---

## 十四、参考资源

### 14.1 Ant Design 组件文档

- [Progress 进度条](https://ant.design/components/progress-cn)
- [List 列表](https://ant.design/components/list-cn)（注：v6 将废弃，但当前项目使用 v5）
- [Space 间距](https://ant.design/components/space-cn)
- [Typography 排版](https://ant.design/components/typography-cn)

### 14.2 业内产品参考

- [GitHub Actions Workflow Run](https://github.com/features/actions)
- [Vercel Deployments](https://vercel.com/docs/deployments)
- [GitLab CI/CD Pipelines](https://docs.gitlab.com/ee/ci/pipelines/)

### 14.3 技术文章

- [React Hooks 最佳实践](https://react.dev/reference/react)
- [SSE vs WebSocket vs Polling](https://ably.com/blog/websockets-vs-sse-vs-polling)
- [TypeScript 泛型设计模式](https://www.typescriptlang.org/docs/handbook/2/generics.html)
