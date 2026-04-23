# Phase 0 根因修复：书籍导入 + 批量测试

**优先级**: 🟢 核心工作流修复  
**工作量**: 5h  *(原 4h + 1h)*

---

## 零、LLM 工厂调用签名错误（新增阻断性 Bug）

### 0.1 修复 0：LLMServiceFactory.create() 参数错误

**问题**：9 个文件调用 `LLMServiceFactory.create()` 时传入错误参数，导致 `TypeError: got an unexpected keyword argument 'model_name'`

**错误日志**：
```
LLMServiceFactory.create() got an unexpected keyword argument 'model_name'
Batch generation failed: LLMServiceFactory.create() got an unexpected keyword argument 'model_name'
Failed to generate drafts using LLM
```

**根因分析**：
- 代码调用的是**新架构异步实例方法** `LLMServiceFactory.create(scene, framework)`
- 但传入的是**兼容层同步类方法** `LLMServiceFactoryCompat.create(framework, model_name, scenario, temperature)` 的参数
- 两个方法签名完全不同，不能混用

**影响范围**：
| 文件 | 调用次数 | 影响功能 |
|------|----------|----------|
| `backend/src/service/rag_test/draft_service.py` | 1 | 测试用例草稿生成 |
| `backend/src/core/metadata_extractor.py` | 1 | 元数据提取 |
| `backend/src/controller/task_controller.py` | 1 | 流式报告生成 |
| `backend/src/core/pipeline/steps/query_rewrite.py` | 1 | 查询重写 |
| `backend/src/core/pipeline/steps/query_router.py` | 1 | 查询路由 |
| `backend/src/core/pipeline/steps/synonym_expansion.py` | 1 | 同义词扩展 |
| `backend/src/core/query_router.py` | 1 | 查询分类 |
| `backend/src/core/memory_manager.py` | 2 | 记忆提取 |
| `backend/src/core/layered_content_generator.py` | 3 | 分层内容生成 |
| **总计** | **12 处** | **核心 LLM 调用全部失败** |

**修复方案**：

```python
# 修改前（错误：调用新架构方法但传兼容层参数）
from src.core.llm.factory import LLMFramework, LLMServiceFactory

llm = LLMServiceFactory.create(
    framework=LLMFramework.LLAMAINDEX,
    model_name=params.llm_model,
    scenario="test_case_generation",
    temperature=params.temperature,
)

# 修改后（正确：使用兼容层类方法）
from src.core.llm.factory import LLMFramework, LLMServiceFactory, LLMServiceFactoryCompat

llm = LLMServiceFactoryCompat.create(
    framework=LLMFramework.LLAMAINDEX,
    model_name=params.llm_model,
    scenario="test_case_generation",
    temperature=params.temperature,
)
```

**修复步骤**：
1. 在 9 个文件的 import 中添加 `LLMServiceFactoryCompat`
2. 将所有 `LLMServiceFactory.create(...)` 改为 `LLMServiceFactoryCompat.create(...)`
3. 验证异步上下文调用正常（兼容层是同步方法，可直接调用）

**验收**：
- [ ] 9 个文件全部改为 `LLMServiceFactoryCompat.create()`
- [ ] 测试用例草稿生成正常（无 `TypeError`）
- [ ] 元数据提取正常
- [ ] 流式报告生成正常
- [ ] RAG 流水线步骤正常（查询重写/路由/同义词扩展）
- [ ] 记忆提取正常
- [ ] 分层内容生成正常

**影响分析**：
| 影响维度 | 说明 |
|----------|------|
| **破坏性变更** | 无，仅修正方法调用 |
| **性能影响** | 无，兼容层性能一致 |
| **风险等级** | 极低（修复参数错误，不改变业务逻辑） |
| **优先级** | 🔴 P0（阻断性 Bug，核心功能完全不可用） |

---

## 一、书籍导入修复（5 个根因）

### 1.1 修复 1：EventSource 相对路径

**问题**：前端 dev server (5173) 和后端 (8000) 端口不同，SSE 请求 404

**文件**：`frontend/src/utils/api.ts`（新建，提取公共函数至 utils/）

**修复方案**：
```typescript
// frontend/src/utils/api.ts
export const getApiBaseUrl = (): string => {
  if (import.meta.env.DEV) {
    return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  }
  return window.location.origin;
};
```

**使用**：
```typescript
// frontend/src/api/sse.ts
import { getApiBaseUrl } from '@/utils/api';

const eventSource = new EventSource(
  `${getApiBaseUrl()}/api/rag/runs/${runId}/sse`
);
```

**验收**：
- [ ] 开发环境 SSE 连接正常（5173 → 8000）
- [ ] 生产环境 SSE 连接正常（同源）
- [ ] `getApiBaseUrl` 统一在 `utils/api.ts` 中定义，不重复实现

---

### 1.2 修复 2：PDF/EPUB 二进制读取

**问题**：用文本模式读取二进制文件，产生乱码

**文件**：`backend/src/service/document_ingestion/document_parser.py`

**修复方案**：
```python
# 修改前（文本模式）
def parse_pdf(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

# 修改后（专用解析器）
import pypdf2
from ebooklib import epub

def parse_pdf(file_path: str) -> str:
    """使用 PyPDF2 解析 PDF"""
    text = []
    with open(file_path, 'rb') as f:  # 二进制模式
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text.append(page.extract_text())
    return '\n'.join(text)

def parse_epub(file_path: str) -> str:
    """使用 ebooklib 解析 EPUB，清理 HTML 标签"""
    from bs4 import BeautifulSoup
    
    book = epub.read_epub(file_path)
    text = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        html = item.get_content().decode('utf-8')
        # 使用 BeautifulSoup 清理 HTML 标签
        soup = BeautifulSoup(html, 'html.parser')
        text.append(soup.get_text(separator='\n', strip=True))
    return '\n'.join(text)
```

**验收**：
- [ ] PDF 解析无乱码
- [ ] EPUB 解析无乱码
- [ ] 扫描件触发 VL 视觉降级（OCR 回退）

---

### 1.3 修复 3：DASHSCOPE_API_KEY 未配置

**问题**：环境变量缺失，LLM 调用失败

**文件**：`backend/src/core/health_check.py`（新建或修改）

**修复方案**：
```python
"""启动时校验关键环境变量"""

import os
import logging

logger = logging.getLogger(__name__)

async def check_environment_variables():
    """校验关键环境变量（异步函数）"""
    
    missing_vars = []
    
    # 校验 DASHSCOPE_API_KEY
    if not os.getenv('DASHSCOPE_API_KEY'):
        missing_vars.append('DASHSCOPE_API_KEY')
    
    # 校验其他关键变量
    if not os.getenv('DATABASE_URL'):
        missing_vars.append('DATABASE_URL')
    
    if missing_vars:
        logger.warning(
            f"以下环境变量未配置，LLM 相关功能将禁用: {', '.join(missing_vars)}"
        )
        # 使用应用级配置标志，而非修改环境变量（线程安全）
        from src.config.core.manager import config_manager
        await config_manager.set_feature_flag('llm_enabled', False)
    else:
        logger.info("所有关键环境变量已配置")
        from src.config.core.manager import config_manager
        await config_manager.set_feature_flag('llm_enabled', True)

# 在应用启动时调用
# app/lifespan.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    check_environment_variables()
    yield
```

**验收**：
- [ ] 启动时输出环境变量校验日志
- [ ] 缺失时 LLM 功能禁用，但不阻塞系统启动
- [ ] 访问健康检查端点显示 LLM 状态

---

### 1.4 修复 4：Redis 依赖问题

**问题**：SSE 依赖 Redis Pub/Sub，Redis 未启动时消息丢失

**文件**：`backend/src/core/sse/publisher.py`

**修复方案**：
```python
"""SSE 发布器（支持 Redis 和内存队列双模式）"""

import asyncio
from typing import Optional
from abc import ABC, abstractmethod

class SSEPublisher(ABC):
    """SSE 发布器基类"""
    
    @abstractmethod
    async def publish(self, channel: str, data: dict):
        pass

class RedisSSEPublisher(SSEPublisher):
    """基于 Redis 的 SSE 发布器"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def publish(self, channel: str, data: dict):
        await self.redis.publish(channel, json.dumps(data))

class InMemorySSEPublisher(SSEPublisher):
    """基于内存队列的 SSE 发布器（降级模式）"""
    
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
    
    async def publish(self, channel: str, data: dict):
        if channel not in self._queues:
            self._queues[channel] = asyncio.Queue()
        await self._queues[channel].put(data)
    
    async def subscribe(self, channel: str) -> asyncio.Queue:
        if channel not in self._queues:
            self._queues[channel] = asyncio.Queue()
        return self._queues[channel]

# 工厂方法（修正：改为异步函数）
async def create_sse_publisher(redis_client=None) -> SSEPublisher:
    """创建 SSE 发布器（自动降级）"""
    if redis_client:
        try:
            # 测试 Redis 连接（带超时）
            await asyncio.wait_for(redis_client.ping(), timeout=3.0)
            return RedisSSEPublisher(redis_client)
        except Exception as e:
            logger.warning(f"Redis 连接失败，降级到内存队列模式: {e}")
    
    return InMemorySSEPublisher()
```

**验收**：
- [ ] Redis 启动时使用 Redis 模式
- [ ] Redis 未启动时使用内存队列
- [ ] SSE 消息不丢失

---

### 1.5 修复 5：asyncio.create_task 无引用

**问题**：Task 可能被 GC，导致任务静默终止

**文件**：`backend/src/service/async_task_manager.py`

**修复方案**：
```python
"""异步任务管理器（保持强引用）"""

import asyncio
from typing import Set

class AsyncTaskManager:
    """管理异步任务，防止 GC"""
    
    def __init__(self):
        self._active_tasks: Set[asyncio.Task] = set()
    
    def create_task(self, coro) -> asyncio.Task:
        """创建任务并保持强引用"""
        task = asyncio.create_task(coro)
        self._active_tasks.add(task)
        
        # 任务完成时自动移除
        task.add_done_callback(self._active_tasks.discard)
        
        return task
    
    async def cancel_all(self):
        """取消所有活跃任务"""
        for task in self._active_tasks:
            task.cancel()
        
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
```

**验收**：
- [ ] 后台任务不会静默终止
- [ ] 任务完成时自动清理
- [ ] 应用关闭时取消所有任务

---

## 二、批量测试修复（7 个根因）

### 2.1 修复 6：前端无 SSE 监听

**问题**：前端发 POST 后等待 HTTP 响应，但批量测试远超 30 秒超时

**文件**：`frontend/src/features/rag-eval/hooks/useTestProgress.ts`（新建）

**修复方案**：
```typescript
/**
 * 监听批量测试进度（SSE）
 */
export const useTestProgress = (runId: string | null) => {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'running' | 'completed' | 'failed'>();
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (!runId) return;

    const eventSource = new EventSource(
      `${getBaseUrl()}/api/rag/runs/${runId}/sse`
    );

    eventSource.addEventListener('test_progress', (event) => {
      const data = JSON.parse(event.data);
      setProgress(data.progress);
      setResults(prev => [...prev, data.result]);
    });

    eventSource.addEventListener('test_completed', (event) => {
      const data = JSON.parse(event.data);
      setStatus('completed');
      setProgress(100);
    });

    eventSource.addEventListener('test_failed', (event) => {
      setStatus('failed');
    });

    // 心跳保活
    eventSource.addEventListener('heartbeat', () => {
      // 保持连接
    });

    return () => {
      eventSource.close();
    };
  }, [runId]);

  return { progress, status, results };
};
```

**验收**：
- [ ] 前端实时显示测试进度
- [ ] 无 30 秒超时问题
- [ ] 断线重连正常

---

### 2.2 修复 7：runSingleTest 调用 runAllTests

**问题**：代码 Bug：`_caseId` 参数被忽略，实际运行了所有测试

**文件**：`frontend/src/api/rag-test/index.ts`

**修复方案**：
```typescript
// 修改前
export const runSingleTest = async (caseId: string) => {
  return api.post('/rag/test/run', {
    test_case_ids: [caseId],  // 正确传递单个用例 ID
  });
};

// 确保后端也正确处理
// backend/src/service/rag_test/test_run_service.py
async def run_tests(self, request: RunTestsRequest):
    if request.test_case_ids:
        # 仅运行指定的用例
        cases = self.case_repository.get_by_ids(request.test_case_ids)
    elif request.test_set_id:
        # 运行测试集的所有用例
        cases = self.test_set_repository.get_cases(request.test_set_id)
    else:
        raise AppException("必须指定 test_case_ids 或 test_set_id")
```

**验收**：
- [ ] 运行单个用例时仅执行该用例
- [ ] 运行测试集时执行所有关联用例

---

### 2.3 修复 8：RetrievalService 重复初始化

**问题**：每个用例创建新实例，并发时耗尽连接池

**文件**：`backend/src/service/rag_test/test_batch_runner.py`

**修复方案**：
```python
# 修改前（每个用例创建新实例）
async def execute_single_case(self, case: TestCase):
    retrieval_service = RetrievalService()  # 错误！重复初始化
    result = await retrieval_service.retrieve(case.query)

# 修改后（复用单例）
from src.service.retrieval.facade import get_retrieval_facade

class TestBatchRunner:
    def __init__(self):
        # 初始化时创建单例
        self.retrieval_facade = get_retrieval_facade()
    
    async def execute_single_case(self, case: TestCase):
        # 复用同一实例
        result = await self.retrieval_facade.retrieve_knowledge(case.query)
```

**验收**：
- [ ] 批量测试时仅初始化一次 RetrievalService
- [ ] 连接池不耗尽
- [ ] 并发测试正常

---

### 2.4 修复 9：分布式锁对唯一 run_id 无意义

**问题**：增加复杂度，Redis 故障时导致失败

**文件**：`backend/src/service/rag_test/test_run_service.py`

**修复方案**：
```python
# 修改前（使用分布式锁）
async def execute_batch(self, run_id: str):
    lock = DistributedLock(f"run:{run_id}")
    await lock.acquire()
    try:
        # 执行测试
    finally:
        await lock.release()

# 修改后（使用本地并发控制）
import asyncio

async def execute_batch(self, run_id: str):
    # 使用本地锁（run_id 唯一，无需分布式锁）
    async with self._running_locks.setdefault(run_id, asyncio.Lock()):
        try:
            # 执行测试
            pass
        finally:
            # 执行完成后清理锁，防止内存泄漏
            self._running_locks.pop(run_id, None)
```

**验收**：
- [ ] 移除 DistributedLock 依赖
- [ ] 本地锁正常工作
- [ ] Redis 故障不影响批量测试

---

### 2.5 修复 10：complete_test_run 读到不完整数据

**问题**：聚合指标可能不准确

**文件**：`backend/src/service/rag_test/test_run/test_batch_runner.py`

**修复方案**：
```python
async def complete_test_run(self, run_id: str):
    """完成测试运行（等待所有用例聚合）"""
    
    # 等待所有用例执行完成
    await self._wait_for_all_cases_completed(run_id)
    
    # 聚合指标
    results = self._get_all_results(run_id)
    
    # 确保数据完整
    if len(results) != self._expected_case_count(run_id):
        logger.warning(
            f"用例数量不匹配：期望 {self._expected_case_count(run_id)}, "
            f"实际 {len(results)}"
        )
    
    # 计算聚合指标
    aggregate_scores = self.analyzer.recalculate_aggregate_scores(run_id)
    
    # 更新运行状态
    self.run_repository.update_status(run_id, 'completed', aggregate_scores)
```

**验收**：
- [ ] 聚合指标准确
- [ ] 用例数量不匹配时输出警告
- [ ] 运行状态正确更新

---

### 2.6 修复 11：SSE 心跳队列内存泄漏

**问题**：前端断开时队列无限增长

**文件**：`backend/src/core/sse/publisher.py`

**修复方案**：
```python
class InMemorySSEPublisher(SSEPublisher):
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._active_connections: dict[str, int] = {}  # 记录活跃连接数
    
    async def subscribe(self, channel: str) -> asyncio.Queue:
        if channel not in self._queues:
            self._queues[channel] = asyncio.Queue()
        self._active_connections[channel] = self._active_connections.get(channel, 0) + 1
        return self._queues[channel]
    
    async def unsubscribe(self, channel: str):
        """前端断开时清理队列"""
        self._active_connections[channel] = max(0, self._active_connections.get(channel, 0) - 1)
        
        # 无活跃连接时清理
        if self._active_connections[channel] == 0:
            if channel in self._queues:
                # 清空队列
                while not self._queues[channel].empty():
                    try:
                        self._queues[channel].get_nowait()
                    except asyncio.QueueEmpty:
                        break
            del self._active_connections[channel]
            logger.info(f"清理 SSE 队列: {channel}")
```

**验收**：
- [ ] 前端断开时队列清空
- [ ] 内存不泄漏
- [ ] 重新连接时队列正常创建

---

### 2.7 修复 12：前端 API 超时 30 秒

**问题**：批量测试通常远超 30 秒

**文件**：`frontend/src/api/rag-test/index.ts`

**修复方案**：
```typescript
// 修改前（固定 30 秒超时）
export const runBatchTests = async (request: BatchRunRequest) => {
  return api.post('/rag/test/runs/batch', request, {
    timeout: 30000,  // 错误！批量测试通常超过 30 秒
  });
};

// 修改后（设置合理超时 5 分钟，依赖 SSE 进度）
export const runBatchTests = async (request: BatchRunRequest) => {
  return api.post('/rag/test/runs/batch', request, {
    timeout: 300000,  // 5 分钟超时，足够长以等待 SSE 进度
  });
};

// 前端通过 SSE 监听进度
const { progress, status } = useTestProgress(runId);
```

**验收**：
- [ ] 批量测试无超时错误
- [ ] 进度通过 SSE 实时更新
- [ ] 长时间运行测试正常（> 5 分钟）

---

## 三、验收清单

### 3.0 LLM 工厂修复验收

- [ ] 9 个文件全部改为 `LLMServiceFactoryCompat.create()`
- [ ] 测试用例草稿生成正常（无 `TypeError`）
- [ ] 元数据提取正常
- [ ] 流式报告生成正常
- [ ] RAG 流水线步骤正常（查询重写/路由/同义词扩展）
- [ ] 记忆提取正常
- [ ] 分层内容生成正常

### 3.1 书籍导入验收

- [ ] EventSource 使用绝对路径
- [ ] PDF/EPUB 解析无乱码
- [ ] 启动时校验环境变量
- [ ] Redis 未启动时 SSE 使用内存队列
- [ ] asyncio.create_task 保持强引用

### 3.2 批量测试验收

- [ ] 前端通过 SSE 监听进度
- [ ] runSingleTest 仅运行指定用例
- [ ] RetrievalService 复用单例
- [ ] 移除分布式锁，使用本地并发控制
- [ ] complete_test_run 等待所有用例聚合
- [ ] SSE 心跳队列无内存泄漏
- [ ] 前端 API 无 30 秒超时

---

## 四、影响分析

| 影响维度 | 说明 |
|----------|------|
| **破坏性变更** | 所有修复均为直接替换，不保留旧代码 |
| **性能影响** | 复用单例减少连接池压力，性能提升 |
| **风险等级** | 低（修复已知根因，不引入新功能） |


