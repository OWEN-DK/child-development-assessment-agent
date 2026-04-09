# RAG系统完整落地 - 测试用例指南

> **执行者**: 用户
> **日期**: 2026-04-08
> **说明**: 请按照以下步骤依次执行测试，每步完成后告知结果

---

## 第一阶段：后端测试集与评估脚本测试

### 测试 1.1: 测试集导入脚本

**目的**: 验证测试集导入脚本能正常工作

**步骤**:
```bash
cd backend
python scripts/rag/import_test_set.py src/data/test_sets/rag_evaluation_test_set_v1.json
```

**预期结果**:
- 输出 "成功导入 330 条测试用例"
- 输出评估器统计信息，包含 total_queries、total_relevant_docs 等
- 在 `backend/storage/test_cases.json` 中生成测试用例存储文件

**检查点**:
- [ ] 导入成功，无报错
- [ ] 统计信息输出正常
- [ ] storage/test_cases.json 文件生成

---

### 测试 1.2: 检索评估脚本

**目的**: 验证检索评估脚本能正常运行并输出指标

**步骤**:
```bash
cd backend
python scripts/rag/evaluate_retrieval.py
```

**预期结果**:
- 输出 "使用 XXX 条测试用例进行检索评估"
- 输出检索评估报告，包含 Precision@3、Recall@3、NDCG@3、MRR、MAP
- 生成报告文件 `backend/reports/retrieval_evaluation_report_v1.json`
- 输出达标检查状态（可能未达标，这是正常的，后续会调优）

**检查点**:
- [ ] 脚本运行无报错
- [ ] 评估报告生成
- [ ] 指标数值合理（0-1之间）

---

### 测试 1.3: 生成评估脚本

**目的**: 验证生成评估脚本框架能正常运行

**步骤**:
```bash
cd backend
python scripts/rag/evaluate_generation.py src/data/test_sets/rag_evaluation_test_set_v1.json
```

**预期结果**:
- 输出 "使用 330 条测试用例进行生成评估"
- 生成报告文件 `backend/reports/generation_evaluation_report_v1.json`
- 报告中指标初始值为 0.0（框架阶段正常）

**检查点**:
- [ ] 脚本运行无报错
- [ ] 报告文件生成

---

### 测试 1.4: 文档导入质量评估脚本

**目的**: 验证文档导入质量评估脚本能正常运行

**步骤**:
```bash
cd backend
python scripts/rag/evaluate_ingestion_quality.py
```

**预期结果**:
- 输出知识库中文档数量
- 生成报告文件 `backend/reports/ingestion_quality_report_v1.json`

**检查点**:
- [ ] 脚本运行无报错
- [ ] 报告文件生成

---

## 第二阶段：前端RAG评估页面测试

### 测试 5.1: 前端编译检查

**目的**: 验证前端代码无编译错误

**步骤**:
```bash
cd frontend
npm run dev
```

**预期结果**:
- 开发服务器启动成功
- 无 TypeScript 编译错误
- 无模块导入错误

**检查点**:
- [ ] 开发服务启动成功
- [ ] 控制台无报错

---

### 测试 5.2: 访问RAG评估页面

**目的**: 验证新页面能正常访问和显示

**步骤**:
1. 启动前端开发服务后
2. 浏览器访问 `http://localhost:5173/rag-evaluation`

**预期结果**:
- 页面正常加载
- 显示 "RAG 自动化评估" 标题
- 显示顶部操作按钮（运行所有测试、导入测试用例、导出报告）
- 显示核心指标看板（7个指标卡片）
- 显示4个Tab（评估概览、测试用例管理、评估报告、Bad Case分析）

**检查点**:
- [ ] 页面正常加载，无白屏
- [ ] 标题和按钮显示正常
- [ ] 指标卡片显示正常
- [ ] Tab切换正常

---

### 测试 5.3: 测试用例管理功能

**目的**: 验证测试用例管理功能正常

**步骤**:
1. 在RAG评估页面，切换到"测试用例管理"Tab
2. 检查测试用例列表是否正常显示
3. 尝试使用搜索框搜索查询内容
4. 尝试使用领域和年龄筛选
5. 点击"新建测试用例"按钮

**预期结果**:
- 测试用例列表正常显示（如果后端已导入测试用例）
- 搜索和筛选功能正常
- 新建弹窗正常弹出

**检查点**:
- [ ] 列表显示正常
- [ ] 搜索功能正常
- [ ] 筛选功能正常
- [ ] 新建弹窗正常

---

### 测试 5.4: 旧路由清理验证

**目的**: 验证旧 rag-test 路由已清理

**步骤**:
1. 浏览器访问 `http://localhost:5173/rag-test`

**预期结果**:
- 页面显示404或重定向到新页面
- 旧页面不再可访问

**检查点**:
- [ ] 旧路由不可访问

---

## 第三阶段：监控服务测试

### 测试 6.1: 监控服务验证

**目的**: 验证监控服务能正常记录和查询指标

**步骤**:
```bash
cd backend
python -c "
from src.service.monitoring_service import monitoring_service
monitoring_service.record_metric('test_metric', 1.0, {'env': 'test'})
metrics = monitoring_service.get_metrics('test_metric')
print(f'监控服务正常，记录到 {len(metrics)} 条指标')
"
```

**预期结果**:
- 输出 "监控服务正常，记录到 1 条指标"

**检查点**:
- [ ] 监控服务正常运行
- [ ] 指标记录和查询正常

---

## 第四阶段：性能压测脚本验证

### 测试 7.1: 性能压测脚本语法检查

**目的**: 验证压测脚本无语法错误

**步骤**:
```bash
cd backend
python -c "import ast; ast.parse(open('scripts/performance/rag_load_test.py').read()); print('脚本语法检查通过')"
```

**预期结果**:
- 输出 "脚本语法检查通过"

**检查点**:
- [ ] 脚本无语法错误

---

## 测试报告模板

请按照以下格式反馈测试结果：

```
测试 1.1: [通过/失败]
  - 备注: xxx

测试 1.2: [通过/失败]
  - 备注: xxx
  - 输出指标: Precision@3=xxx, Recall@3=xxx, MRR=xxx, NDCG@3=xxx

测试 5.1: [通过/失败]
  - 备注: xxx

...
```

---

## 常见问题排查

### 问题1: 导入脚本报错 "ModuleNotFoundError"
**解决**: 确保在 `backend` 目录下运行脚本

### 问题2: 前端页面白屏
**解决**: 
1. 检查浏览器控制台是否有报错
2. 确认后端服务是否启动
3. 检查 API 路径是否正确

### 问题3: 测试用例列表为空
**解决**: 先执行测试 1.1 导入测试集
