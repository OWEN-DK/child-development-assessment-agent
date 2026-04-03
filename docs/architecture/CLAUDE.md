# CLAUDE.md - 项目指南

## 项目概览
**儿童发展评估 Agent (Child Development Assessment Agent)** 是一个基于 AI 的系统，根据儿童的发展画像评估其运动计划。该系统使用 **LangGraph** 进行编排，采用 **ReAct** 架构，并集成了 **LangChain** 和 **LlamaIndex**。

- **目标**: 根据用户输入自动生成专业的评估报告。
- **架构**: 多 Agent 系统 (预处理 -> 校验 -> 评估 -> 检索 -> 评分 -> 报告)。
- **前端**: React + TypeScript (已初始化)。
- **后端**: FastAPI + LangGraph (已实现基础架构)。
- **包管理**: uv

## 技术栈
- **语言**: Python 3.13.12, TypeScript 5.9.3
- **编排**: LangGraph 1.1.0
- **LLM 框架**: LangChain 1.2.11
- **RAG**: LlamaIndex 0.14.16
- **API**: FastAPI 0.135.1
- **校验**: Pydantic 2.12.5, Zod 3.x
- **日志**: Loguru 0.7.3
- **前端**: React 19.2.4, Ant Design 6.3.2, ProComponents 2.8.10
- **样式**: SCSS Module (禁止直接写 CSS，必须分离样式文件)
- **状态管理**: Zustand (全局), TanStack Query (服务端)
- **路由**: React Router v6/v7
- **可视化**: Ant Design Charts
- **工具库**: Lodash-es, Day.js, Clsx
- **数据库**: Vector DB (Chroma/Faiss), Graph DB (Neo4j - 计划中)
- **工具**: uv 0.10.9

## 常用命令

### 后端 (Python - 使用 uv)
- **进入目录**: `cd backend`
- **初始化环境**: `uv sync`
- **激活环境**: `source .venv/bin/activate`
- **安装依赖**: `uv sync` (或 `uv add <package>`)
- **运行服务**: `uv run python src/server.py`
- **API 文档**: `http://localhost:8000/docs`
- **运行测试**: `uv run pytest`
- **格式化代码**: `uv run black .`
- **Lint 检查**: `uv run flake8 .`

### 前端 (React)
- **进入目录**: `cd frontend`
- **安装依赖**: `npm install --legacy-peer-deps`
- **开发服务器**: `npm run dev`
- **构建**: `npm run build`
- **Lint 检查**: `npm run lint`

## 项目结构 (当前)
```
/
├── backend/             # 后端项目根目录
│   ├── .venv/           # 虚拟环境
│   ├── src/             # Python 源代码
│   │   ├── config/      # 配置文件
│   │   ├── controller/  # API 控制器
│   │   ├── core/        # Agent 核心逻辑
│   │   ├── model/       # 数据模型
│   │   ├── service/     # 业务服务
│   │   ├── utils/       # 工具类
│   │   └── server.py    # 后端入口
│   ├── logs/            # 后端日志
│   ├── pyproject.toml   # 后端依赖配置
│   ├── uv.lock          # 依赖锁定文件
│   └── opencode.json    # Agent 配置
├── frontend/            # 前端项目根目录
│   ├── src/             # React 源代码
│   ├── public/          # 静态资源
│   ├── package.json     # 前端依赖配置
│   └── vite.config.ts   # 构建配置
├── book/                # 知识库源文件 (PDF/EPUB)
├── README.md            # 项目说明
├── AGENTS.md            # Agent 定义文档
├── CLAUDE.md            # 本文件
└── IMPLEMENTATION_PLAN.md # 详细系统设计方案
```

## 规划结构 (目标)
```
/
├── src/                 # 后端源代码 (FastAPI + LangGraph)
│   ├── api/             # API 路由与控制器 (Routers)
│   ├── core/            # 核心组件 (Security, Middleware, Events)
│   ├── domain/          # 业务领域模型 (Entities, Value Objects)
│   ├── services/        # 业务逻辑服务 (Service Layer)
│   ├── agents/          # LangGraph Agent 逻辑
│   ├── graph/           # 工作流编排 (Workflows)
│   ├── schemas/         # Pydantic 数据传输对象 (DTOs)
│   ├── db/              # 数据库访问 (Repositories, Models)
│   ├── utils/           # 通用工具
│   └── server.py        # 应用入口
├── frontend/            # React 应用 (规划中)
│   ├── public/          # 静态资源
│   └── src/             # 源代码
│       ├── assets/      # 图片、样式等资源
│       ├── components/  # 公共组件 (Atomic Design)
│       ├── config/      # 全局配置 (路由、主题等)
│       ├── hooks/       # 自定义 Hooks
│       ├── layouts/     # 页面布局
│       ├── pages/       # 页面视图
│       ├── services/    # API 请求服务
│       ├── store/       # 状态管理 (Zustand/Redux)
│       ├── types/       # TypeScript 类型定义
│       ├── utils/       # 工具函数
│       ├── App.tsx      # 根组件
│       └── main.tsx     # 入口文件
├── books/               # RAG 数据源
└── tests/               # 测试代码
```

## 代码规范
- **风格**: Python 遵循 PEP 8。
- **日志**: 使用 `src.utils.logger` 而不是 `print`。
- **类型提示**: 所有函数签名必须包含类型提示。
- **文档字符串**: 复杂函数使用 Google 风格的文档字符串。
- **错误处理**: 使用自定义异常。
- **状态**: 保持 `AgentState` 整洁。
- **导入**: 优先使用绝对导入。
- **提示词管理**: 所有LLM相关的提示词必须统一存放在 `src/core/prompts.py` 文件中，禁止在业务代码中硬编码提示词。
- **注释规范**: 所有代码注释必须使用中文，禁止使用英文注释，确保代码可读性和团队协作一致性。

## 核心概念
- **StandardizedInput**: 校验后的标准数据格式。
- **AgentState**: 通过 LangGraph 传递的全局状态对象。
- **MCP Server**: 用于检索结构化知识的模型上下文协议服务器。
- **AHP**: 用于基准评分逻辑的层次分析法 (Analytic Hierarchy Process)。
# Claude/Agent Rules

## Backend Development

- **Dependency Management**: All backend dependencies must be explicitly configured in `backend/pyproject.toml`. Do not rely on implicit dependencies or manual installation without updating the configuration file.
- **Configuration Management**: 
  - 所有可配置参数必须在 `backend/src/config/settings.py` 中定义，并支持通过 `.env.dev` 环境变量覆盖
  - 禁止在业务代码中硬编码任何配置值，必须从 settings 对象读取
  - 新增配置项时必须同时添加到 `.env.dev.example` 作为示例
- **代码规范**:
  - 所有配置相关的修改必须同步更新配置文件，不得直接在代码中写死数值
