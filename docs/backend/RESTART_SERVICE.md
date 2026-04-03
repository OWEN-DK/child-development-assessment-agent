# 🔄 重启服务以应用新配置

## ✅ 已完成的修改

### 1. 代码修改
- ✅ `backend/src/config/settings.py` - 配置默认值
- ✅ `backend/src/core/hybrid_retrieval.py` - 分数校准和归一化逻辑
- ✅ `backend/src/service/retrieval_service.py` - 详细日志记录

### 2. 环境变量修改
- ✅ `backend/.env.dev` - **这是关键！服务从这里读取配置**

## 📝 修改的配置项

### .env.dev 文件中的关键配置

```bash
# BM25 校准因子
BM25_SCALE_FACTOR=5                             # 从 10 降低到 5

# RAG 搜索权重
RAG_SEARCH_BM25_WEIGHT=0.5                      # 从 0.7 降低到 0.5
RAG_SEARCH_VECTOR_WEIGHT=0.5                    # 从 0.3 提高到 0.5
RAG_SEARCH_NO_MATCH_VECTOR_PENALTY=0.5          # 从 0.3 提高到 0.5

# RAG 搜索阈值
RAG_SEARCH_SCORE_THRESHOLD_HYBRID=0.35          # 从 0.1 提高到 0.35
RAG_SEARCH_SCORE_THRESHOLD_VECTOR=0.35          # 从 0.5 降低到 0.35
RAG_SEARCH_RELATIVE_CUTOFF_RATIO=0.5            # 从 0.3 提高到 0.5
RAG_SEARCH_MIN_SIMILARITY_THRESHOLD=0.3         # 从 0.5 降低到 0.3
```

## 🚀 重启服务

### 方法 1：直接重启（推荐）
```bash
cd /Users/owen/project/ai/child-development-assessment-agent/backend
# 停止当前服务（如果正在运行）
lsof -ti:8000 | xargs kill -9 2>/dev/null

# 重新启动服务
uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

### 方法 2：使用现有的启动脚本
```bash
cd /Users/owen/project/ai/child-development-assessment-agent
# 根据你的启动方式
python backend/src/main.py
# 或者
cd backend && python src/main.py
```

## ✅ 验证配置生效

重启后，搜索"孩子"或"老师"，查看日志：

### 期望看到的日志
```
INFO - _process_search_results: 向量检索模式，阈值=0.35  ✅ 阈值应该是 0.35
INFO - _process_search_results: 最高分=0.55, 阈值=0.35, 相对截断比例=0.5  ✅ 应该高于阈值
INFO - _process_search_results: 处理完成，返回 15 个结果  ✅ 应该有结果返回
```

### 不应该看到的日志
```
INFO - _process_search_results: 向量检索模式，阈值=0.5  ❌ 这是旧配置
WARNING - _process_search_results: 最高分 0.3175 低于阈值 0.5, 返回空结果  ❌ 不应该再出现
```

## 🔍 如果配置仍未生效

### 检查方法 1：查看进程
```bash
ps aux | grep "uvicorn\|main.py"
# 确认没有旧的进程在运行
```

### 检查方法 2：查看配置加载
启动服务时，注意看是否有配置相关的日志输出。

### 检查方法 3：Python 缓存
如果修改后仍未生效，清除 Python 缓存：
```bash
cd /Users/owen/project/ai/child-development-assessment-agent/backend
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete
```

## 📊 预期效果对比

| 查询 | 重启前 | 重启后 |
|-----|-------|-------|
| 孩子 | 0 结果 ❌ | 10-20 个 ✅ |
| 老师 | 0 结果 ❌ | 10-20 个 ✅ |
| 感觉统合 | 0-5 个 | 5-15 个 |
| 足球 | 可能返回噪声 | 0 结果（正确） |

## 🎯 下一步

重启服务后：
1. 搜索测试查询（孩子、老师、感觉统合等）
2. 查看详细日志，确认分数分布
3. 如果有问题，检查日志中的阈值和分数

---

**修改时间**: 2026-04-03 00:05  
**需要操作**: 重启服务
