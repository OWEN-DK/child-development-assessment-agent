# 提示词配置管理系统设计文档

## 1. 需求概述
### 1.1 背景
当前项目中提示词采用"集中式硬编码 + 零散硬编码"混合存储方式，无法实现动态配置，修改提示词需要重新部署代码，效率低下。

### 1.2 目标
实现完整的提示词配置管理系统，支持所有提示词在页面中可视化配置，不需要硬编码，支持版本管理、热重载、回滚等高级功能。

### 1.3 范围
覆盖项目中所有提示词：
- `prompts.py`中所有集中管理的提示词（9个）
- 所有分散在各组件、工具类、脚本中的硬编码提示词（11处）
- 总计约20个提示词

### 1.4 约束
- 项目未上线，不考虑任何迁移和灰度方案
- 复用现有JSON文件存储架构，不引入关系型数据库
- 独立一级菜单页面，不复用系统配置页

## 2. 系统架构设计
### 2.1 整体架构
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  前端管理页面   │────▶│  PromptController│────▶│  PromptManager  │
│  (独立一级菜单) │     │  (API路由)       │     │  (业务逻辑)     │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │PromptRepository │
                                                 │(JSON文件存储)   │
                                                 └────────┬────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │  JSON文件存储   │
                                                 │backend/data/    │
                                                 │  prompts/       │
                                                 └─────────────────┘

业务代码调用:
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Agent节点/服务  │────▶│  PromptLoader   │────▶│  PromptManager  │
│  (消费方)       │     │  (统一加载接口)  │     │  (缓存+降级)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 2.2 核心模块
| 模块 | 文件路径 | 职责 |
|------|----------|------|
| **PromptManager** | `backend/src/config/prompt_manager.py` | 提示词业务逻辑：CRUD、版本管理、热重载、缓存 |
| **PromptRepository** | `backend/src/config/prompt_repository.py` | JSON文件持久化存储 |
| **PromptLoader** | `backend/src/core/prompt_loader.py` | 业务代码统一加载接口，支持变量渲染和降级 |
| **PromptController** | `backend/src/controller/prompt_controller.py` | RESTful API路由 |
| **前端页面** | `frontend/src/pages/PromptManagementPage.tsx` | 独立提示词管理页面 |
| **前端组件** | `frontend/src/features/prompt-management/` | 列表、编辑器、预览、版本历史组件 |

### 2.3 与现有架构的关系
- **存储架构**：复用ConfigManager的JSON文件存储模式，但使用独立目录
- **事件总线**：复用EventBus发布提示词变更事件
- **降级机制**：保留`prompts.py`作为降级默认值来源
- **API路由**：独立路由前缀`/api/v1/prompts`，不与配置API混用

## 3. 数据结构设计
### 3.1 单个提示词JSON结构
每个提示词独立存储为一个JSON文件，路径：`backend/data/prompts/{key}.json`

```json
{
  "key": "ASSESSMENT_SYSTEM_PROMPT",
  "name": "评估系统提示词",
  "category": "assessment",
  "content": "你是一个专业的儿童发展评估专家...",
  "variables": ["child_profile", "assessment_data"],
  "description": "用于Node2评估节点的系统提示词",
  "status": "active",
  "current_version": "v1.0.0",
  "created_at": "2026-04-09T10:00:00Z",
  "updated_at": "2026-04-09T10:00:00Z",
  "versions": {
    "v1.0.0": {
      "content": "你是一个专业的儿童发展评估专家...",
      "change_log": "初始版本，从prompts.py迁移",
      "created_at": "2026-04-09T10:00:00Z",
      "created_by": "system"
    }
  }
}
```

### 3.2 字段说明
| 字段名 | 类型 | 说明 |
|--------|------|------|
| key | string | 提示词唯一标识（如`ASSESSMENT_SYSTEM_PROMPT`） |
| name | string | 提示词名称（中文） |
| category | string | 分类：assessment/scoring/reporting/retrieval/metadata/validation |
| content | string | 提示词内容模板 |
| variables | string[] | 变量列表（如`["child_profile", "assessment_data"]`） |
| description | string | 提示词描述、使用说明 |
| status | string | 状态：active/inactive |
| current_version | string | 当前版本号 |
| created_at | string | 创建时间（ISO 8601） |
| updated_at | string | 更新时间（ISO 8601） |
| versions | object | 版本历史字典，key为版本号 |

### 3.3 版本对象结构
| 字段名 | 类型 | 说明 |
|--------|------|------|
| content | string | 该版本的提示词内容 |
| change_log | string | 变更说明 |
| created_at | string | 创建时间 |
| created_by | string | 创建人 |

### 3.4 存储目录结构
```
backend/data/prompts/
├── versions/                    # 版本历史归档（可选，用于清理旧版本）
│   └── {key}/
│       └── {version}.json
├── ASSESSMENT_SYSTEM_PROMPT.json
├── REPORTING_SYSTEM_PROMPT.json
├── QUERY_REWRITE_PROMPT.json
└── ...
```

## 4. 后端核心类设计
### 4.1 PromptManager
```python
class PromptManager:
    """提示词管理器 - 单例模式，类似ConfigManager"""
    
    # 核心方法
    get_prompt(key: str) -> dict              # 获取提示词完整数据
    get_content(key: str) -> str              # 仅获取提示词内容
    update_prompt(key: str, content: str, change_log: str) -> dict  # 更新提示词
    create_prompt(data: dict) -> dict         # 创建新提示词
    delete_prompt(key: str) -> bool           # 删除提示词
    list_prompts(category: str = None, status: str = None) -> list  # 列表查询
    get_versions(key: str) -> list            # 获取版本列表
    get_version(key: str, version: str) -> dict  # 获取指定版本
    rollback(key: str, version: str) -> dict  # 回滚到指定版本
    diff_versions(key: str, v1: str, v2: str) -> dict  # 版本对比
    refresh()                                 # 热重载缓存
```

### 4.2 PromptRepository
```python
class PromptRepository:
    """JSON文件持久化存储仓库"""
    
    # 核心方法
    async def load_prompt(key: str) -> dict | None
    async def save_prompt(key: str, data: dict) -> None
    async def delete_prompt(key: str) -> None
    async def list_all_prompts() -> list[str]  # 返回所有key
```

### 4.3 PromptLoader
```python
class PromptLoader:
    """业务代码统一加载接口"""
    
    # 核心方法
    load(key: str, **variables) -> str        # 加载并渲染变量
    load_raw(key: str) -> str                 # 加载原始模板（不渲染）
    batch_load(keys: list[str]) -> dict       # 批量加载
    
    # 降级机制
    # 如果PromptManager不可用或提示词不存在，
    # 自动fallback到prompts.py中的硬编码值
```

### 4.4 变量渲染规则
- 变量占位符格式：`{{variable_name}}`
- 使用Python的`string.Template`或自定义渲染器
- 未提供的变量保持原样不替换
- 支持嵌套变量：`{{child_profile.name}}`

## 5. 后端接口设计
### 5.1 基础CRUD接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/prompts` | 获取提示词列表（支持category、status过滤） |
| GET | `/api/v1/prompts/{key}` | 获取单个提示词详情 |
| POST | `/api/v1/prompts` | 创建新提示词 |
| PUT | `/api/v1/prompts/{key}` | 更新提示词（自动创建新版本） |
| DELETE | `/api/v1/prompts/{key}` | 删除提示词 |

### 5.2 版本管理接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/prompts/{key}/versions` | 获取提示词的所有版本列表 |
| GET | `/api/v1/prompts/{key}/versions/{version}` | 获取指定版本详情 |
| POST | `/api/v1/prompts/{key}/rollback` | 回滚到指定版本 |
| GET | `/api/v1/prompts/{key}/diff` | 对比两个版本的差异（query参数：v1, v2） |

### 5.3 业务加载接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/prompts/load/{key}` | 加载指定key的提示词（query参数：variables JSON） |
| POST | `/api/v1/prompts/batch-load` | 批量加载多个key的提示词 |
| POST | `/api/v1/prompts/refresh` | 刷新提示词缓存（热重载） |

## 6. 前端页面设计
### 6.1 路由配置
- 路径：`/prompts`
- 菜单：独立一级菜单「提示词管理」
- 组件：`PromptManagementPage`

### 6.2 页面结构
**左侧：提示词列表**
- 搜索框：按key/name搜索
- 分类筛选：下拉选择（全部/评估/评分/报告/检索/元数据/校验）
- 状态筛选：全部/启用/停用
- 列表项：名称、标识、分类、状态、更新时间
- 操作按钮：编辑、版本历史、启用/停用、删除

**右侧：编辑/详情区域**
- Tab 1：基础信息编辑
  - 名称、标识（只读）、分类、描述
  - 变量列表（动态增删）
  - 状态切换
  
- Tab 2：提示词编辑器
  - 代码编辑器（支持语法高亮）
  - 变量高亮提示（`{{variable}}`格式）
  - 实时变量校验（检查未定义的变量）
  - 保存按钮（触发版本创建）
  
- Tab 3：实时预览
  - 变量值输入表单
  - 预览渲染后的完整提示词
  - Token计数
  
- Tab 4：版本历史
  - 版本列表（版本号、时间、变更日志、创建人）
  - 版本对比（选择两个版本，高亮差异）
  - 回滚按钮

### 6.3 组件设计
| 组件 | 路径 | 职责 |
|------|------|------|
| PromptList | `features/prompt-management/components/PromptList.tsx` | 提示词列表和筛选 |
| PromptEditor | `features/prompt-management/components/PromptEditor.tsx` | 代码编辑器，支持变量高亮 |
| PromptPreview | `features/prompt-management/components/PromptPreview.tsx` | 实时预览组件 |
| VersionHistory | `features/prompt-management/components/VersionHistory.tsx` | 版本列表和对比 |
| VariableValidator | `features/prompt-management/components/VariableValidator.tsx` | 变量校验组件 |

### 6.4 状态管理
```typescript
// store/promptStore.ts
interface PromptState {
  prompts: PromptItem[];
  currentPrompt: PromptItem | null;
  versions: VersionItem[];
  loading: boolean;
  error: string | null;
  
  // Actions
  fetchPrompts: () => void;
  fetchPrompt: (key: string) => void;
  updatePrompt: (key: string, data: UpdatePromptDto) => void;
  createPrompt: (data: CreatePromptDto) => void;
  deletePrompt: (key: string) => void;
  fetchVersions: (key: string) => void;
  rollbackVersion: (key: string, version: string) => void;
  refreshCache: () => void;
}
```

## 7. 提示词分类和清单
### 7.1 分类定义
| 分类 | 说明 | 提示词 |
|------|------|--------|
| **assessment** | 评估节点 | ASSESSMENT_SYSTEM_PROMPT |
| **scoring** | 评分节点 | SCORING_SYSTEM_PROMPT, qwen_scorer prompts |
| **reporting** | 报告生成 | REPORTING_SYSTEM_PROMPT, fallback report template |
| **retrieval** | 检索相关 | RAG_QUERY_TEMPLATE, QUERY_REWRITE_PROMPT, SYNONYM_EXPANSION_PROMPT, query_router prompt |
| **metadata** | 元数据提取 | METADATA_EXTRACTION_PROMPT, layered content generator prompts |
| **validation** | 校验节点 | VALIDATION_SYSTEM_PROMPT, INTENSITY_INFERENCE_PROMPT, CATEGORY_INFERENCE_PROMPT |
| **memory** | 记忆管理 | memory manager prompts (偏好提取、经验提取) |
| **security** | 安全防护 | prompt injection guard template |

### 7.2 初始迁移清单
从`prompts.py`迁移（9个）：
1. RAG_QUERY_TEMPLATE → retrieval
2. QUERY_REWRITE_PROMPT → retrieval
3. SYNONYM_EXPANSION_PROMPT → retrieval
4. METADATA_EXTRACTION_PROMPT → metadata
5. VALIDATION_SYSTEM_PROMPT → validation
6. INTENSITY_INFERENCE_PROMPT → validation
7. CATEGORY_INFERENCE_PROMPT → validation
8. ASSESSMENT_SYSTEM_PROMPT → assessment
9. SCORING_SYSTEM_PROMPT → scoring
10. REPORTING_SYSTEM_PROMPT → reporting

从业务代码迁移（11个）：
11. layered_content_generator L0 prompt → metadata
12. layered_content_generator L1 prompt → metadata
13. layered_content_generator batch prompt → metadata
14. layered_content_generator merge prompt → metadata
15. qwen_scorer system prompt → scoring
16. qwen_scorer user prompt → scoring
17. query_router prompt → retrieval
18. memory_manager preference prompt → memory
19. memory_manager experience prompt → memory
20. prompt_injection_guard template → security
21. reporting fallback report template → reporting

## 8. 功能特性
### 8.1 核心功能
1. **热重载**：提示词修改后立即更新内存缓存，通过EventBus通知相关组件
2. **版本管理**：每次更新自动创建新版本，支持语义化版本号
3. **版本对比**：使用diff算法高亮显示两个版本之间的差异
4. **回滚功能**：一键回滚到任意历史版本
5. **变量校验**：自动检测`{{variable}}`模式的变量，与variables列表对比
6. **实时预览**：输入变量值即可预览渲染后的完整提示词
7. **降级机制**：PromptManager不可用时，fallback到prompts.py硬编码值

### 8.2 扩展功能（后续迭代）
- A/B测试支持：同时激活多个版本
- 使用统计：记录调用次数、成功率
- 批量导入/导出
- 提示词模板库

## 9. 业务代码替换方案
### 9.1 替换原则
- 所有业务代码中的提示词引用改为通过`PromptLoader.load()`获取
- 保留`prompts.py`作为降级默认值，不删除
- 替换过程不涉及任何迁移逻辑（项目未上线）

### 9.2 替换示例
**替换前**：
```python
from src.core.prompts import ASSESSMENT_SYSTEM_PROMPT

response = llm.invoke([
    {"role": "system", "content": ASSESSMENT_SYSTEM_PROMPT},
    {"role": "user", "content": user_input}
])
```

**替换后**：
```python
from src.core.prompt_loader import prompt_loader

system_prompt = prompt_loader.load("ASSESSMENT_SYSTEM_PROMPT")
response = llm.invoke([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_input}
])
```

### 9.3 需要替换的文件
| 文件 | 替换内容 |
|------|----------|
| `nodes/retrieval.py` | RAG_QUERY_TEMPLATE |
| `service/retrieval_service.py` | QUERY_REWRITE_PROMPT, SYNONYM_EXPANSION_PROMPT |
| `core/metadata_extractor.py` | METADATA_EXTRACTION_PROMPT |
| `nodes/validation.py` | INTENSITY_INFERENCE_PROMPT, CATEGORY_INFERENCE_PROMPT |
| `nodes/assessment.py` | ASSESSMENT_SYSTEM_PROMPT |
| `nodes/reporting.py` | REPORTING_SYSTEM_PROMPT, fallback report template |
| `core/layered_content_generator.py` | 4个内联提示词 |
| `core/ml/qwen_scorer.py` | 2个内联提示词 |
| `core/query_router.py` | 1个内联提示词 |
| `core/memory_manager.py` | 2个内联提示词 |
| `core/prompt_injection_guard.py` | 1个内联模板 |

## 10. 实施计划
### 阶段1：后端核心（2天）
- [ ] 创建`PromptRepository`（JSON文件存储）
- [ ] 创建`PromptManager`（业务逻辑、版本管理、缓存）
- [ ] 创建`PromptLoader`（统一加载接口、变量渲染、降级）
- [ ] 创建`PromptController`（API路由）
- [ ] 注册到FastAPI应用和DI容器
- [ ] 编写单元测试

### 阶段2：前端页面（2天）
- [ ] 创建`PromptManagementPage`和路由
- [ ] 实现`PromptList`组件（列表、筛选、搜索）
- [ ] 实现`PromptEditor`组件（代码编辑器、变量高亮）
- [ ] 实现`PromptPreview`组件（实时预览）
- [ ] 实现`VersionHistory`组件（版本列表、对比、回滚）
- [ ] 实现`promptStore`状态管理
- [ ] 实现API调用层

### 阶段3：数据初始化和业务替换（1天）
- [ ] 编写初始化脚本：将现有提示词导入JSON存储
- [ ] 替换所有业务代码中的硬编码引用
- [ ] 验证所有功能正常
- [ ] 删除孤立提示词（VALIDATION_SYSTEM_PROMPT、SCORING_SYSTEM_PROMPT如果未被引用）

### 阶段4：测试和优化（1天）
- [ ] 端到端测试：创建、编辑、版本管理、回滚
- [ ] 热重载测试：修改后立即生效
- [ ] 降级测试：删除JSON文件后fallback到prompts.py
- [ ] 性能测试：批量加载响应时间<100ms
- [ ] 代码审查和优化

## 11. 测试方案
### 11.1 单元测试
- PromptRepository：JSON读写、文件不存在处理
- PromptManager：CRUD、版本管理、缓存、热重载
- PromptLoader：变量渲染、降级机制、批量加载

### 11.2 集成测试
- API端点测试：所有CRUD、版本管理接口
- 前端组件测试：编辑器、预览、版本对比

### 11.3 端到端测试
- 完整工作流：创建提示词 → 编辑 → 版本对比 → 回滚
- 业务代码调用：通过PromptLoader加载提示词并用于LLM调用

## 12. 风险和注意事项
### 12.1 风险
- **JSON并发写入**：多用户同时编辑同一提示词可能导致冲突，需要加锁
- **变量渲染冲突**：提示词中包含`{{}}`但不是变量的情况，需要转义机制
- **性能问题**：大量提示词同时加载可能影响启动速度，需要懒加载

### 12.2 注意事项
- 版本号格式：使用`v{major}.{minor}.{patch}`语义化版本
- 文件编码：所有JSON文件使用UTF-8编码
- 备份机制：每次更新前自动备份当前版本
- 审计日志：记录所有提示词变更操作
