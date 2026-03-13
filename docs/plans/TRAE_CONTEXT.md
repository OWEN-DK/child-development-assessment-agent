# TRAE_CONTEXT.md - Trae AI 上下文指南

> **重要提示**: 本文档必须与 `CLAUDE.md` 保持同步。如果 `CLAUDE.md` 中的技术栈、架构或规范发生变更，**必须**同步更新本文档，以确保 Trae AI 获取最新的项目上下文。

本文档专为 Trae AI 助手设计，旨在提供项目核心上下文、技术约束和开发规范，以提高代码生成和问题解答的准确性。

## 1. 项目概览
**儿童发展评估 Agent (Child Development Assessment Agent)** 是一个基于 AI 的垂直领域专家系统。
- **核心功能**: 接收儿童画像（年龄、性别、问题）和拟定运动计划，生成专业的评估报告（包含评分、科学依据、调整建议）。
- **架构模式**: Browser-Use (前端) + LangGraph (后端编排) + RAG (LlamaIndex)。

## 2. 技术栈 (严格遵守)

### 前端 (Frontend)
- **框架**: React 19.2.4 + TypeScript 5.9.3 + Vite
- **UI 组件库**: Ant Design 6.3.2 + ProComponents 2.8.10
- **样式方案**: **SCSS Modules** (`*.module.scss`)。**禁止**使用 Tailwind CSS 或内联样式（除动态值外）。
- **状态管理**:
  - **全局 UI/业务状态**: Zustand
  - **服务端数据/缓存**: TanStack Query (React Query) v5
- **路由**: React Router v6
- **可视化**: Ant Design Charts (@ant-design/plots)
- **工具库**: Lodash-es, Day.js, Clsx, Axios
- **包管理**: npm (需使用 `--legacy-peer-deps` 安装依赖)

### 后端 (Backend)
- **语言**: Python 3.13.12
- **Web 框架**: FastAPI 0.135.1
- **Agent 编排**: LangGraph 1.1.0
- **LLM 框架**: LangChain 1.2.11
- **RAG 引擎**: LlamaIndex 0.14.16
- **数据校验**: Pydantic 2.12.5
- **包管理**: uv (`uv sync`, `uv add`, `uv run`)

## 3. 核心目录结构
```
/
├── src/                    # 后端核心代码
│   ├── core/               # LangGraph 节点与 Agent 逻辑
│   ├── model/              # Pydantic 数据模型 (Schemas)
│   ├── service/            # 业务服务 (RagService)
│   └── server.py           # FastAPI 入口
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/     # UI 组件 (AssessForm, ReportViewer)
│   │   │   └── *.module.scss # 组件样式
│   │   ├── hooks/          # 业务逻辑 Hooks (useAssessment)
│   │   ├── pages/          # 页面视图 (HomePage)
│   │   ├── store/          # Zustand Store
│   │   ├── lib/            # 工具配置 (queryClient)
│   │   └── router/         # 路由配置
│   └── package.json
├── book/                   # RAG 知识库源文件
└── CLAUDE.md               # 项目主指南
```

## 4. 开发规范与约束

### 前端规范
1.  **样式分离**: 所有组件样式必须写在对应的 `*.module.scss` 文件中，通过 `import styles from './Component.module.scss'` 引入。
2.  **逻辑分离**: 复杂的业务逻辑（表单处理、API 调用）必须抽离到 `src/hooks/` 目录下的自定义 Hook 中。
3.  **类型安全**: 所有 Props 和 API 响应必须定义 TypeScript 接口（在 `src/types/` 中）。
4.  **组件库使用**: 优先使用 Ant Design ProComponents (`ProForm`, `ProLayout`, `PageContainer`) 以提升开发效率。

### 后端规范
1.  **类型提示**: 所有 Python 函数必须包含 Type Hints。
2.  **模块化**: Agent 逻辑应拆分为独立的 Node 函数（在 `src/core/nodes/`）。
3.  **环境管理**: 必须使用 `uv` 进行依赖管理和运行 (`uv run python ...`)。

## 5. 常用命令速查

| 任务 | 命令 | 备注 |
| :--- | :--- | :--- |
| **启动后端** | `uv run python src/server.py` | 端口 8000 |
| **后端测试** | `uv run pytest` | |
| **安装前端依赖** | `cd frontend && npm install --legacy-peer-deps` | 必须加 legacy-peer-deps |
| **启动前端** | `cd frontend && npm run dev` | 端口 5173 |
| **前端 Lint** | `cd frontend && npm run lint` | |

## 6. 关键业务流程 (Context)
1.  **用户输入**: 前端 `AssessmentForm` 收集 `child_profile` 和 `proposed_plan`。
2.  **提交**: 调用 `POST /assess`。
3.  **后端处理**:
    - `NodePre`: 历史数据压缩。
    - `Node1`: Pydantic 校验与标准化。
    - `Node2`: 评估儿童当前状态 (Child State)。
    - `Node3`: RAG 检索科学依据 (LlamaIndex)。
    - `Node4`: AHP 评分 (Scoring)。
    - `Node5`: 生成 Markdown 报告。
4.  **结果展示**: 前端 `ReportViewer` 渲染 Markdown，并使用 Ant Design Charts 展示雷达图。

---
**注意**: 在生成代码时，请务必检查 `package.json` 和 `pyproject.toml` 确认具体的依赖版本。
