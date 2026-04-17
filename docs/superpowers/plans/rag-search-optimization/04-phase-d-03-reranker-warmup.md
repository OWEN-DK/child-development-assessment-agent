# D-3: Cross-Encoder 模型预热

> **所属 Phase**: Phase D (P2)
> **任务类型**: 单一任务 — 服务启动时后台异步加载 Cross-Encoder 模型，消除懒加载延迟
> **对应问题**: 测试 7 主要问题（首次请求延迟 2000-5000ms）

## 🎯 目标

在服务启动时后台异步加载 `BAAI/bge-reranker-v2-m3` 模型，消除首次请求的懒加载延迟，确保冷启动首次请求延迟 ≤1500ms。

## 📋 实施步骤

- [ ] **Step 1: 分析现有懒加载逻辑**
  - [ ] 阅读 `src/core/reranker.py` 的 `_load_model` 方法
  - [ ] 确认模型加载耗时瓶颈（模型下载 vs 内存加载）
  - [ ] 确认当前懒加载触发时机

- [ ] **Step 2: 实现模型预热器**
  - [ ] 新增 `src/core/rag/model_warmer.py` 模块
  - [ ] 实现 `warmup_reranker()` 异步方法，后台加载 Cross-Encoder 模型
  - [ ] 在服务启动时（FastAPI lifespan 或 startup event）触发预热
  - [ ] 预热不阻塞服务启动，后台完成后标记模型就绪

- [ ] **Step 3: 修改 reranker 加载逻辑**
  - [ ] 将 `_load_model` 改为检查预热状态，若已预热则直接使用
  - [ ] 保留懒加载作为预热失败的降级策略
  - [ ] 添加预热状态健康检查端点

- [ ] **Step 4: 编写测试**
  - [ ] 测试预热成功后首次请求延迟 ≤1500ms
  - [ ] 测试预热失败时降级到懒加载
  - [ ] 测试预热不阻塞服务启动

- [ ] **Step 5: 性能验证**
  - [ ] 手动测试：服务重启后首次请求延迟 ≤1500ms
  - [ ] 后续请求延迟 ≤300ms

## ✅ 验收标准

- 冷启动首次请求延迟 ≤1500ms
- 后续请求延迟 ≤300ms
- 预热不阻塞服务启动
- 预热失败有降级策略

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/rag/model_warmer.py` | 新增 | 模型预热器实现 |
| `src/core/reranker.py` | 修改 | 集成预热状态检查 |
| `src/server.py` | 修改 | 启动时触发预热 |
| `tests/test_model_warmer.py` | 新增 | 单元测试 |

---

**返回索引：** [04-phase-d-00-overview.md](./04-phase-d-00-overview.md)
