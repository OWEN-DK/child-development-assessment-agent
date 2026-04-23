# 任务状态管理系统 - 实施方案

> **基于需求文档**: `requirements.md`  
> **创建日期**: 2026-04-20  
> **实施策略**: 分 5 个阶段，零迁移原则（直接替换，不保留兼容层）

---

## 一、文件结构规划

```
backend/src/
├── schemas/
│   ├── task.py                          # [新建] 统一任务状态模型
│   └── events.py                        # [修改] 补充统一 SSE 事件格式
├── service/
│   ├── task_state_service.py            # [新建] 核心服务（Redis Hash + Lua）
│   ├── task_sse_publisher.py            # [新建] 统一 SSE 发布器
│   ├── test_run_task_adapter.py         # [新建] TestRun 双写适配器（阶段 4）
│   ├── task_status_service.py           # [删除] 旧服务（阶段 2）
│   └── document_ingestion/
│       └── task_state_manager.py        # [删除] 旧 JSON 文件服务（阶段 2）
├── controller/
│   ├── task_controller.py               # [新建] 统一任务 API
│   └── rag_controller.py                # [修改] 替换为新服务（阶段 2）
├── core/
│   ├── async_task.py                    # [修改] 接入新 SSE + 取消信号（阶段 3）
│   ├── di_container.py                  # [修改] 注册新服务
│   └── layered_content_generator.py     # [修改] 接入新服务（阶段 3）
├── api/
│   └── sse.py                           # [修改] 删除专用方法（阶段 4）
└── models/
    └── test_case.py                     # [修改] TestRunStatus 增加 pending（阶段 4）

frontend/src/
├── hooks/
│   └── useTaskProgress.ts               # [新建] 统一任务进度 Hook
└── features/documents/hooks/
    └── useDocumentManagement.ts         # [修改] 替换为新 API（阶段 2）

scripts/
└── cleanup_old_redis_keys.py            # [新建] 旧 Key 清理脚本（阶段 5）
```

---

## 二、分阶段实施计划

### 阶段 1：基础设施搭建（核心服务）

**目标**: 创建新服务，不替换旧代码，验证基础功能

**文件清单**:
1. `schemas/task.py` - 统一任务状态模型
2. `service/task_state_service.py` - 核心服务（Lua 脚本原子更新）
3. `service/task_sse_publisher.py` - 统一 SSE 发布器
4. `controller/task_controller.py` - 统一任务 API
5. `schemas/events.py` - 补充统一 SSE 事件格式
6. `core/di_container.py` - 注册新服务

**关键实现要点**:
- Lua 脚本保证：终态校验 + HSET + EXPIRE 原子执行
- 活跃任务索引 Set：`task:active:{task_type}`
- 强制 TTL 策略：所有 Key 必须设置过期时间
- 内存兜底：单实例部署时降级到本地内存
- 取消信号管理：`asyncio.Event` 字典

**验收标准**:
- [ ] 单元测试覆盖率 > 80%
- [ ] Lua 脚本终态保护验证通过
- [ ] TTL 自动续期验证通过
- [ ] API 端点可正常调用

---

### 阶段 2：迁移文档上传任务

**目标**: 替换 RAG 文档上传/索引任务的状态管理

**修改文件**:
1. `controller/rag_controller.py` - 直接替换为 `TaskStateService`
2. `frontend/src/features/documents/hooks/useDocumentManagement.ts` - 替换 API 调用

**删除文件**:
- `service/task_status_service.py`
- `service/document_ingestion/task_state_manager.py`

**关键变更**:
- 状态值统一：`success` → `completed`，`processing` → `running`
- Redis Key 统一：`upload:{task_id}` → `task:upload:{task_id}`
- 进度回调改为同步 `await`，消除竞态条件
- 前端使用统一 `useTaskProgress` Hook

**验收标准**:
- [ ] 上传任务状态更新无竞态
- [ ] 终态保护生效（完成后无法更新为 running）
- [ ] 前端 3 秒内显示成功状态
- [ ] 旧代码完全删除

---

### 阶段 3：迁移草稿生成 + 导出任务

**目标**: 替换内存存储为 Redis，统一 SSE 推送

**修改文件**:
1. `core/async_task.py` - 接入 `TaskSsePublisher` + 取消信号
2. `service/export_service.py` - 替换为 `TaskStateService`
3. `core/layered_content_generator.py` - 替换为 `TaskStateService`

**关键变更**:
- 草稿生成：从内存存储迁移到 Redis Hash
- 导出任务：删除全局可变状态，使用 DI 注入
- 分层内容生成：从内存字典迁移到 Redis
- 统一 SSE 事件格式：所有任务使用 `TaskSsePublisher.publish()`

**验收标准**:
- [ ] 草稿生成任务可持久化查询
- [ ] 导出任务支持取消
- [ ] 分层内容生成支持多实例部署
- [ ] 旧 SSE 专用方法标记删除

---

### 阶段 4：迁移 RAG 评估任务

**目标**: TestRun 类型实现 Redis + MySQL 双写

**修改文件**:
1. `models/test_case.py` - `TestRunStatus` 增加 `pending`
2. `service/test_run_task_adapter.py` - 新建双写适配器

**关键实现**:
- Redis 作为主存储（快速查询 + SSE 推送）
- MySQL TestRun.status 作为持久化兜底
- 中间状态定期同步（stage 变化或进度每增加 10%）
- 终态必须同步到 MySQL

**验收标准**:
- [ ] Redis 失败时可从 MySQL 恢复
- [ ] 进度同步频率合理（不过度写入 MySQL）
- [ ] 终态转换时 MySQL 数据一致

---

### 阶段 5：清理旧代码

**目标**: 删除所有旧服务引用，清理 Redis 旧 Key

**删除/修改文件**:
1. `api/sse.py` - 删除 `publish_progress/publish_complete` 专用方法
2. `scripts/cleanup_old_redis_keys.py` - 新建清理脚本

**清理清单**:
- 旧 Redis Key 模式：`upload:*`、`rag_eval:export:*`
- 前端旧状态兼容逻辑（如有）
- 所有旧服务导入语句

**验收标准**:
- [ ] 代码搜索无旧服务引用
- [ ] 旧 Redis Key 全部清理
- [ ] 前端无 `normalizeStatus` 函数

---

## 三、核心实现细节

### 3.1 Lua 脚本（原子更新）

```lua
-- 文件：service/task_state_service.py 内嵌
-- 功能：终态校验 + HSET + EXPIRE + 活跃任务索引维护
```

**关键点**:
1. 终态保护：已完成任务不可逆转为非终态
2. 自动填充时间戳：`started_at`、`completed_at`
3. TTL 自动续期：根据状态自动设置（running 不续期）
4. 活跃任务索引：创建时 SADD，终态时 SREM

### 3.2 内存兜底机制

**触发条件**: Redis 连接失败
**限制**: 仅单实例部署时启用（`multi_instance=False`）
**清理**: 定时任务每 1 分钟清理过期内存缓存（TTL 5 分钟）
**恢复**: Redis 恢复后自动同步内存数据

### 3.3 取消信号管理

```python
# TaskStateService 内部管理
_cancellation_signals: dict[str, asyncio.Event]

# 业务代码使用
if await task_state_service.check_cancellation(task_id):
    return  # 优雅退出
```

### 3.4 TestRun 双写适配器

**同步策略**:
- 终态转换：立即同步
- stage 变化：立即同步
- 进度增加：每 10% 同步一次

**降级策略**:
- Redis 优先：查询时先读 Redis
- MySQL 兜底：Redis 失败时读 TestRun 表

---

## 四、测试策略

### 4.1 单元测试

| 测试文件 | 测试内容 |
|---------|---------|
| `tests/service/test_task_state_service.py` | Lua 脚本原子性、终态保护、TTL 策略 |
| `tests/service/test_task_sse_publisher.py` | 事件格式统一、频道命名 |
| `tests/service/test_test_run_adapter.py` | 双写一致性、降级恢复 |
| `tests/controller/test_task_controller.py` | API 契约、错误处理 |

### 4.2 集成测试

| 测试场景 | 验证内容 |
|---------|---------|
| 并发更新 | 无竞态条件，字段不丢失 |
| Redis 宕机 | 降级到内存，恢复后同步 |
| 后端重启 | 运行中任务标记为 failed |
| 看门狗检测 | 超时任务自动标记失败 |

### 4.3 前端测试

| 测试文件 | 测试内容 |
|---------|---------|
| `src/hooks/__tests__/useTaskProgress.test.tsx` | SSE 连接、降级轮询、离线恢复 |

---

## 五、风险与应对

| 风险 | 应对措施 |
|------|---------|
| Lua 脚本加载失败 | 启动时预加载，失败则服务启动失败 |
| Redis 内存溢出 | 强制 TTL + 内存监控告警 |
| 多实例部署时钟不同步 | 使用 NTP 同步 |
| 迁移过程中断 | git revert 回滚 |

---

## 六、实施顺序

```
阶段 1（基础设施）
    ↓
阶段 2（文档上传）← 验证核心功能
    ↓
阶段 3（草稿 + 导出）← 验证多任务类型
    ↓
阶段 4（RAG 评估）← 验证双写适配器
    ↓
阶段 5（清理旧代码）← 最终验收
```

每个阶段完成后：
1. 运行测试验证
2. 删除旧代码（零迁移原则）
3. 更新本文档进度

---

## 七、进度追踪

| 阶段 | 状态 | 完成日期 | 备注 |
|------|------|---------|------|
| 阶段 1 | ✅ 已完成 | 2026-04-20 | 核心服务、API、DI 注册完成 |
| 阶段 2 | ✅ 已完成 | 2026-04-20 | 文档上传任务迁移完成，竞态条件已消除，状态值统一 |
| 阶段 3 | ✅ 已完成 | 2026-04-20 | 草稿生成 + 导出任务 + 分层内容生成迁移完成 |
| 阶段 4 | ✅ 已完成 | 2026-04-20 | RAG 评估任务迁移完成，Redis + MySQL 双写适配器实现 |
| 阶段 5 | ✅ 已完成 | 2026-04-20 | 旧代码清理完成，旧 SSE 方法删除，旧 Redis Key 清理脚本创建 |

---

## 八、阶段 2 完成详情

### 8.1 已完成变更

#### 后端（3 个文件）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `controller/rag_controller.py` | 重写 | 替换为新任务状态服务，消除竞态条件 |
| `service/task_status_service.py` | 删除 | 旧 Redis String 服务 |
| `core/di_container.py` | 修复 | 移除前向引用，解决 DI 初始化问题 |

#### 前端（8 个文件）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `api/documents/types.ts` | 修改 | `processing` → `running`，`success` → `completed` |
| `shared/lib/constants.ts` | 修改 | 更新 TASK_STATUS 常量 |
| `components/documents/TaskProgressList.tsx` | 修改 | 状态值替换 |
| `features/documents/hooks/useDocumentManagement.ts` | 修改 | 状态过滤逻辑更新 |
| `features/documents/pages/KnowledgeBasePage.tsx` | 修改 | 状态值替换 |
| `components/progress/types.ts` | 修改 | TaskStatus 类型定义更新 |
| `components/progress/hooks/useProgressPolling.ts` | 修改 | 状态值替换 |
| `components/progress/ProgressListItem.tsx` | 修改 | STATUS_CONFIG 更新 |

### 8.2 关键改进

1. **消除竞态条件**：进度回调改为同步 `await`，不再使用 `call_soon_threadsafe`
2. **统一状态语义**：`success` → `completed`，`processing` → `running`
3. **Redis Key 统一**：`upload:{task_id}` → `task:upload:{task_id}`
4. **SSE 推送**：新增统一 SSE 事件发布
5. **取消信号**：支持任务取消和优雅退出

### 8.3 遗留问题

| 问题 | 影响 | 解决阶段 |
|------|------|---------|
| `task_state_manager.py` 未删除 | 还被 BookIngestor 使用 | 阶段 3/5 |
| 草稿生成类型错误 (5 个) | 不影响文档上传功能 | 阶段 3 |

### 8.4 代码质量

- **后端语法**: ✅ 全部通过
- **前端类型**: ⚠️ 5 个错误（草稿生成相关，阶段 3 修复）
- **零迁移原则**: ✅ 直接替换，无兼容层

---

## 九、阶段 3 完成详情

### 9.1 已完成变更

#### 后端（4 个文件）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `core/async_task.py` | 重写 | 接入 TaskStateService + TaskSsePublisher + 取消信号 |
| `service/export_service.py` | 重写 | 替换为 TaskStateService，删除旧 Redis String 操作 |
| `core/layered_content_generator.py` | 重写 | 替换内存字典为 TaskStateService |
| `service/document_ingestion/task_state_manager.py` | 删除 | 旧本地 JSON 文件服务 |

#### 前端（1 个文件）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `components/progress/configs/draftGeneration.ts` | 修改 | 状态值替换 + onCancel 签名修复 |

### 9.2 关键改进

1. **统一任务管理器**：AsyncTaskManager 现在使用 TaskStateService 管理所有任务状态
2. **导出任务持久化**：从内存存储迁移到 Redis Hash，支持多实例部署
3. **分层内容生成持久化**：从内存字典迁移到 Redis Hash
4. **取消信号集成**：所有任务类型支持优雅取消

---

## 十、阶段 4 完成详情

### 10.1 已完成变更

#### 后端（4 个文件）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `models/test_case.py` | 修改 | TestRunStatus 增加 pending 状态 |
| `schemas/test_case.py` | 修改 | TestRunStatus 增加 pending 状态 |
| `service/test_run_task_adapter.py` | 新建 | Redis + MySQL 双写适配器 |
| `service/rag_test/test_run/test_run_creator.py` | 修改 | 集成 TaskStateService 创建任务状态 |
| `service/rag_test/test_run/test_batch_runner.py` | 修改 | 集成 TaskStateService 更新进度 |
| `controller/rag_test_controller.py` | 修改 | 使用统一 TaskSsePublisher |

### 10.2 关键改进

1. **双写适配器**：TestRunTaskStateAdapter 实现 Redis 主写 + MySQL 按需同步
2. **智能同步策略**：终态必同步、stage 变化同步、进度每 10% 同步
3. **降级恢复**：Redis 失败时可从 MySQL TestRun 表恢复状态
4. **状态枚举统一**：TestRunStatus 增加 pending，与统一状态机对齐

---

## 十一、阶段 5 完成详情

### 11.1 已完成变更

#### 后端（8 个文件）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `api/sse.py` | 修改 | 删除 publish_progress/publish_complete 专用方法 |
| `service/document_ingestion/__init__.py` | 修改 | 移除旧导入 |
| `service/document_ingestion/facade.py` | 修改 | 移除 task_state_manager 参数 |
| `service/document_ingestion/book_ingestor.py` | 重写 | 使用 TaskStateService |
| `service/document_ingestion/chunking_indexing.py` | 重写 | 使用 TaskStateService |
| `service/document_ingestion/document_parser.py` | 修改 | 移除无用 TaskStatus 导入 |
| `service/document_ingestion_service.py` | 修改 | 移除旧导入 |
| `core/di_container.py` | 修改 | 添加返回类型注解 |

#### 脚本（1 个文件）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/cleanup_old_redis_keys.py` | 新建 | 旧 Redis Key 清理脚本 |

### 11.2 清理清单

- ✅ 旧 Redis Key 模式：`upload:*`、`rag_eval:export:*`（清理脚本已创建）
- ✅ 前端旧状态兼容逻辑：无 normalizeStatus 函数
- ✅ 所有旧服务导入语句：task_state_manager、TaskStateManager、task_status_service 零引用

### 11.3 代码质量

- **后端语法**: ✅ 全部通过
- **前端类型**: ✅ 0 个错误
- **单元测试**: ✅ 12/12 通过
- **零迁移原则**: ✅ 直接替换，无兼容层
