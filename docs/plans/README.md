# Child Development Assessment Agent

这是一个基于 **LangGraph** 和 **FastAPI** 构建的儿童发展评估系统。它通过多 Agent 协作流程，对家长提供的儿童画像和拟定计划进行科学评估，并生成专业的改进建议。

## 核心功能

- **预处理与压缩**: 自动提取历史数据的关键特征。
- **数据校验**: 确保输入的完整性和合规性。
- **发展评估**: 基于年龄里程碑识别儿童的发展强弱项。
- **混合检索 (RAG)**: 结合向量数据库检索相关的科学育儿知识。
- **多维评分**: 使用 AHP (层次分析法) 对计划进行打分。
- **报告生成**: 生成家长友好的 Markdown 格式评估报告。

## 快速开始

### 1. 环境准备

- Python 3.12+
- 推荐使用 `uv` 进行依赖管理，或者使用标准的 `venv`。

### 2. 安装依赖

```bash
cd backend
# 如果使用 uv (推荐)
uv sync
```

### 3. 配置环境

主要配置项在 `backend/src/config/settings.py` 中定义。

### 4. 启动服务

```bash
# 在 backend 目录下
uv run python src/server.py
```

服务将启动在 `http://0.0.0.0:8000`。

### 5. 前端启动

```bash
cd frontend
npm install
npm run dev
```

### 6. API 文档

启动后端服务后，访问 `http://localhost:8000/docs` 查看交互式 API 文档。

## 项目结构

- `backend/`: 后端服务
  - `src/config`: 配置文件
  - `src/controller`: API 路由控制器
  - `src/core`: Agent 核心逻辑 (LangGraph 节点与图定义)
  - `src/model`: Pydantic 数据模型
  - `src/service`: 业务服务 (如 RAG 服务)
- `frontend/`: 前端应用 (React)
- `book/`: 知识库源文件 (PDF/EPUB)

## 开发指南

- **添加新依赖**: 修改 `pyproject.toml` 并运行 `uv sync`。
- **修改 Agent 流程**: 编辑 `src/core/graph.py` 和 `src/core/nodes.py`。
