# 批量执行测试用例 - 设计方案

**创建日期**: 2026-04-10  
**状态**: 待审核  
**作者**: AI Assistant

---

## 一、需求概述

### 1.1 用户故事
作为 RAG 系统测试人员，我希望能够灵活地批量执行测试用例，以便：
- 快速验证特定测试集的质量
- 针对特定领域或年龄范围进行定向测试
- 并发执行提高测试效率
- 实时查看执行进度和结果

### 1.2 功能需求
1. **多种执行模式**：
   - 按测试用例 ID 列表执行（表格多选）
   - 按测试集执行
   - 按条件过滤执行（领域、年龄范围等）

2. **并发执行**：使用 asyncio 并发，可配置并发数（1-10）

3. **实时进度展示**：
   - 进度条显示完成百分比
   - 统计卡片（总计/成功/失败/进行中）
   - 实时结果表格更新

4. **取消机制**：支持取消正在执行的批量测试

5. **错误处理**：单个用例失败不影响其他用例执行

### 1.3 现有问题修复
- 修复前端"运行单个"按钮 bug（目前调用的是 runAllTests 而非 runSingleTest）

---

## 二、架构设计

### 2.1 后端架构

```
新增 API 端点: POST /rag/test/run/batch
     ↓
RagTestController.batch_run_tests()
     ↓
RagTestManager.run_batch_tests()
     ├── 解析执行模式 (case_ids / test_set_id / filters)
     ├── 获取目标测试用例列表
     ├── 创建 BatchTestRun 对象 (status="running")
     ├── asyncio.Semaphore(concurrency_limit) 控制并发
     ├── asyncio.gather() 并发执行每个测试用例
     │    └── 每个用例完成后更新进度
     ├── 计算整体指标
     └── 保存结果到 test_runs/{run_id}.json
```

### 2.2 前端架构

```
RagEvaluationPage
     ├── TestCaseTable (支持多选)
     │    └── rowSelection 勾选框
     ├── 批量执行按钮组
     │    ├── "执行选中" (勾选后显示)
     │    ├── "执行测试集" (下拉选择)
     │    └── "条件执行" (弹窗配置过滤条件)
     ├── BatchExecutionModal (批量执行配置弹窗)
     │    ├── 执行模式选择
     │    ├── 并发数配置 (1-10)
     │    └── 开始执行按钮
     └── ExecutionProgress (实时进度组件)
          ├── 进度条
          ├── 统计信息 (成功/失败/总计)
          └── 实时结果表格
```

---

## 三、数据模型设计

### 3.1 新增请求模型

```python
class BatchRunRequest(BaseModel):
    """批量执行请求"""
    name: str = ""                              # 执行名称
    description: str = ""                       # 执行描述
    mode: Literal["cases", "test_set", "filter"] # 执行模式
    case_ids: Optional[List[str]] = None        # 模式=cases: 用例ID列表
    test_set_id: Optional[str] = None           # 模式=test_set: 测试集ID
    filters: Optional[Dict[str, Any]] = None    # 模式=filter: 过滤条件
    concurrency: int = 5                        # 并发数 (1-10)
    limit: int = 10                             # 每个用例检索数量 (1-50)


class FilterConditions(BaseModel):
    """过滤条件"""
    domain: Optional[str] = None                # 领域过滤
    age_min: Optional[int] = None               # 最小年龄
    age_max: Optional[int] = None               # 最大年龄
    source_document_id: Optional[str] = None    # 源文档
```

### 3.2 扩展 TestRun 模型

```python
class TestRun(BaseModel):
    # ... 现有字段 ...
    mode: str = "all"                           # 新增: 执行模式 (all/cases/test_set/filter)
    concurrency: int = 1                        # 新增: 并发数
    case_ids: Optional[List[str]] = None        # 新增: 实际执行的用例ID
    progress: int = 0                           # 新增: 进度百分比 (0-100)
    started_at: Optional[str] = None            # 新增: 开始时间
    completed_at: Optional[str] = None          # 新增: 完成时间
    errors: List[Dict[str, str]] = []           # 新增: 错误记录
```

---

## 四、API 设计

### 4.1 新增端点

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/rag/test/run/batch` | POST | 批量执行测试 | `BatchRunRequest` | `{status, test_run}` |
| `/rag/test/run/batch/{run_id}/cancel` | POST | 取消执行 | - | `{status, message}` |

> 🔹 **端点复用**：获取执行进度直接复用现有`GET /rag/test/runs/{run_id}`端点，该端点已返回完整的进度信息和测试结果，无需新增独立progress端点，减少API冗余

### 4.2 修改现有端点

| 端点 | 修改内容 |
|------|----------|
| `/rag/test/runs` | 返回数据增加 `mode`, `progress`, `concurrency`, `started_at`, `completed_at` 字段 |
| `/rag/test/runs/{run_id}` | 返回数据增加实时进度信息和错误记录 |
| `/rag/test/runs/{run_id}` (DELETE) | 删除后触发评分同步，返回更新后的聚合评分 |

### 4.3 请求/响应示例

#### 批量执行请求

```json
// 模式 1: 按用例 ID
{
  "mode": "cases",
  "case_ids": ["case_001", "case_002", "case_003"],
  "concurrency": 5,
  "limit": 10,
  "name": "感觉统合测试",
  "description": "测试感觉统合领域的用例"
}

// 模式 2: 按测试集
{
  "mode": "test_set",
  "test_set_id": "set_001",
  "concurrency": 3,
  "limit": 10
}

// 模式 3: 按条件过滤
{
  "mode": "filter",
  "filters": {
    "domain": "感觉统合",
    "age_min": 0,
    "age_max": 3
  },
  "concurrency": 5,
  "limit": 10
}
```

#### 执行进度响应

```json
{
  "id": "run_20260410_001",
  "name": "感觉统合测试",
  "mode": "cases",
  "status": "running",
  "progress": 60,
  "total_test_cases": 10,
  "completed_test_cases": 6,
  "passed_test_cases": 5,
  "concurrency": 5,
  "test_results": [...],
  "errors": [
    {"test_case_id": "case_003", "error": "检索超时"}
  ],
  "started_at": "2026-04-10T10:00:00",
  "completed_at": null
}
```

---

## 五、后端实现设计

### 5.1 RagTestManager 新增方法

```python
class RagTestManager:
    def __init__(self):
        # ... 现有代码 ...
        self._running_tasks: Dict[str, asyncio.Task] = {}  # run_id -> task
        self._cancel_flags: Dict[str, bool] = {}           # run_id -> flag
    
    async def run_batch_tests(
        self,
        mode: str,
        case_ids: Optional[List[str]] = None,
        test_set_id: Optional[str] = None,
        filters: Optional[Dict] = None,
        concurrency: int = 5,
        limit: int = 10,
        name: str = "",
        description: str = "",
    ) -> TestRun:
        """
        批量执行测试
        
        Args:
            mode: 执行模式 (cases/test_set/filter)
            case_ids: 用例 ID 列表
            test_set_id: 测试集 ID
            filters: 过滤条件
            concurrency: 并发数 (1-10)
            limit: 每个用例检索数量
            name: 执行名称
            description: 执行描述
            
        Returns:
            TestRun: 测试运行结果
        """
        # 1. 解析目标测试用例
        target_cases = await self._resolve_test_cases(mode, case_ids, test_set_id, filters)
        
        # 🔹 执行数量限制：单次最多100个用例，避免内存溢出和长时间占用资源
        if len(target_cases) > 100:
            raise ValueError(f"单次批量执行最多支持100个用例，当前选择了{len(target_cases)}个")
            
        # 🔹 并发安全说明：asyncio单线程模型下，所有协程在同一个线程执行，并发修改TestRun属性不会有竞态条件
        # 不需要额外加锁，进度更新是原子操作
        
        if not target_cases:
            raise ValueError("没有找到符合条件的测试用例")
        
        # 2. 创建 TestRun 记录
        test_run = self._create_batch_test_run(
            target_cases, name, description, mode, concurrency
        )
        
        # 3. 初始化取消标志
        self._cancel_flags[test_run.id] = False
        
        # 4. 并发执行
        semaphore = asyncio.Semaphore(concurrency)
        tasks = [
            self._run_single_with_semaphore(test_case, semaphore, limit, test_run)
            for test_case in target_cases
        ]
        
        # 保存任务引用（用于取消）
        batch_task = asyncio.create_task(asyncio.gather(*tasks, return_exceptions=True))
        self._running_tasks[test_run.id] = batch_task
        
        try:
            await batch_task
        except asyncio.CancelledError:
            test_run.status = "cancelled"
            test_run.completed_at = datetime.now().isoformat()
            self._save_test_run(test_run)
            raise
        finally:
            del self._running_tasks[test_run.id]
            del self._cancel_flags[test_run.id]
        
        # 5. 所有用例执行完成后，统一计算整体指标
        # 注意：不在执行过程中实时计算指标，因为：
        # - 批量执行时实时指标数据不完整，没有参考价值
        # - 减少执行过程中的计算开销
        # - 最终指标更准确
        self._calculate_overall_metrics(test_run)
        
        # 6. 保存结果
        test_run.status = "completed"
        test_run.completed_at = datetime.now().isoformat()
        self._save_test_run(test_run)
        
        return test_run
    
    async def _resolve_test_cases(
        self,
        mode: str,
        case_ids: Optional[List[str]] = None,
        test_set_id: Optional[str] = None,
        filters: Optional[Dict] = None,
    ) -> List[TestCase]:
        """解析目标测试用例"""
        if mode == "cases":
            if not case_ids:
                raise ValueError("case_ids 不能为空")
            return [
                self.get_test_case(cid) 
                for cid in case_ids 
                if self.get_test_case(cid)
            ]
        
        elif mode == "test_set":
            if not test_set_id:
                raise ValueError("test_set_id 不能为空")
            test_set = self.get_test_set(test_set_id)
            if not test_set:
                raise ValueError(f"测试集 {test_set_id} 不存在")
            return [
                self.get_test_case(cid) 
                for cid in test_set.test_case_ids 
                if self.get_test_case(cid)
            ]
        
        elif mode == "filter":
            all_cases = self.list_test_cases()
            return self._filter_test_cases(all_cases, filters or {})
        
        else:
            raise ValueError(f"不支持的执行模式: {mode}")
    
    def _filter_test_cases(
        self, cases: List[TestCase], filters: Dict
    ) -> List[TestCase]:
        """根据条件过滤测试用例"""
        result = cases
        
        if filters.get("domain"):
            result = [c for c in result if c.domain == filters["domain"]]
        
        if filters.get("age_min") is not None:
            result = [c for c in result if c.age >= filters["age_min"]]
        
        if filters.get("age_max") is not None:
            result = [c for c in result if c.age <= filters["age_max"]]
        
        if filters.get("source_document_id"):
            result = [
                c for c in result 
                if c.source_document_id == filters["source_document_id"]
            ]
        
        return result
    
    def _create_batch_test_run(
        self,
        cases: List[TestCase],
        name: str,
        description: str,
        mode: str,
        concurrency: int,
    ) -> TestRun:
        """创建批量测试运行记录"""
        from datetime import datetime
        import uuid
        
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        return TestRun(
            id=run_id,
            name=name or f"Batch Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            description=description,
            mode=mode,
            concurrency=concurrency,
            case_ids=[c.id for c in cases],
            total_test_cases=len(cases),
            passed_test_cases=0,
            status="running",
            progress=0,
            test_results=[],
            errors=[],
            started_at=datetime.now().isoformat(),
            config_version_id=self._get_current_config_version(),
            config_snapshot=self._get_config_snapshot(),
        )
    
    async def _run_single_with_semaphore(
        self,
        test_case: TestCase,
        semaphore: asyncio.Semaphore,
        limit: int,
        test_run: TestRun,
    ):
        """带信号量控制的单个测试执行"""
        async with semaphore:
            # 检查取消标志
            if self._cancel_flags.get(test_run.id):
                return
            
            try:
                # 执行测试用例，但不计算整体指标
                result = await self.run_test_case(test_case, limit)
                test_run.test_results.append(result)
                
                # 仅更新进度（完成数量），不计算指标
                completed = len(test_run.test_results)
                test_run.progress = int(
                    completed / test_run.total_test_cases * 100
                )
                    
            except Exception as e:
                # 记录错误但不中断其他测试
                test_run.errors.append({
                    "test_case_id": test_case.id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })
                # 即使失败也要更新进度
                completed = len(test_run.test_results) + len(test_run.errors)
                test_run.progress = int(
                    completed / test_run.total_test_cases * 100
                )
    
    async def cancel_test_run(self, run_id: str) -> bool:
        """
        取消正在执行的测试
        
        Args:
            run_id: 测试运行 ID
            
        Returns:
            bool: 是否成功取消
        """
        if run_id not in self._running_tasks:
            return False
        
        self._cancel_flags[run_id] = True
        self._running_tasks[run_id].cancel()
        return True
```

### 5.2 Controller 层

```python
# backend/src/controller/rag_test_controller.py

class BatchRunRequest(BaseModel):
    name: str = ""
    description: str = ""
    mode: Literal["cases", "test_set", "filter"]
    case_ids: Optional[List[str]] = None
    test_set_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    concurrency: int = Field(5, ge=1, le=10)
    limit: int = Field(10, ge=1, le=50)


@router.post("/run/batch")
async def batch_run_tests(request: BatchRunRequest):
    """批量执行测试"""
    try:
        test_run = await rag_test_manager.run_batch_tests(
            mode=request.mode,
            case_ids=request.case_ids,
            test_set_id=request.test_set_id,
            filters=request.filters,
            concurrency=request.concurrency,
            limit=request.limit,
            name=request.name,
            description=request.description,
        )
        return {
            "status": "success",
            "test_run": test_run.model_dump()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量执行失败: {str(e)}")


@router.post("/run/batch/{run_id}/cancel")
async def cancel_batch_run(run_id: str):
    """取消批量执行"""
    success = await rag_test_manager.cancel_test_run(run_id)
    if success:
        return {"status": "success", "message": "已取消执行"}
    else:
        raise HTTPException(
            status_code=404, 
            detail="测试运行不存在或已完成"
        )
```

---

## 六、前端实现设计

### 6.1 新增组件

#### BatchExecutionModal.tsx

```tsx
// frontend/src/features/rag-evaluation/components/BatchExecutionModal.tsx

import React, { useState } from 'react';
import { Modal, Form, Select, Input, InputNumber, Button, Space } from 'antd';
import { TestSet } from '@/models/rag-test';

interface BatchExecutionModalProps {
  visible: boolean;
  mode: 'cases' | 'test_set' | 'filter';
  selectedCaseIds?: string[];
  testSets: TestSet[];
  onConfirm: (config: BatchRunConfig) => Promise<void>;
  onCancel: () => void;
}

interface BatchRunConfig {
  mode: 'cases' | 'test_set' | 'filter';
  caseIds?: string[];
  testSetId?: string;
  filters?: {
    domain?: string;
    age_min?: number;
    age_max?: number;
    source_document_id?: string;
  };
  concurrency: number;
  limit: number;
  name: string;
  description: string;
}

const BatchExecutionModal: React.FC<BatchExecutionModalProps> = ({
  visible,
  mode,
  selectedCaseIds = [],
  testSets,
  onConfirm,
  onCancel,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleOk = async () => {
    const values = await form.validateFields();
    setLoading(true);
    try {
      const config: BatchRunConfig = {
        mode,
        concurrency: values.concurrency || 5,
        limit: values.limit || 10,
        name: values.name,
        description: values.description,
      };

      if (mode === 'cases') {
        config.caseIds = selectedCaseIds;
      } else if (mode === 'test_set') {
        config.testSetId = values.testSetId;
      } else if (mode === 'filter') {
        config.filters = {
          domain: values.domain,
          age_min: values.ageRange?.[0],
          age_max: values.ageRange?.[1],
          source_document_id: values.sourceDocumentId,
        };
      }

      await onConfirm(config);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="批量执行测试"
      open={visible}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      width={600}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="执行名称">
          <Input placeholder="例如：感觉统合测试" />
        </Form.Item>

        <Form.Item name="description" label="执行描述">
          <Input.TextArea rows={2} placeholder="可选" />
        </Form.Item>

        {mode === 'cases' && (
          <Form.Item label="已选用例">
            <span>已选择 {selectedCaseIds.length} 个测试用例</span>
          </Form.Item>
        )}

        {mode === 'test_set' && (
          <Form.Item
            name="testSetId"
            label="测试集"
            rules={[{ required: true, message: '请选择测试集' }]}
          >
            <Select
              placeholder="选择测试集"
              options={testSets.map((ts) => ({
                label: ts.name,
                value: ts.id,
              }))}
            />
          </Form.Item>
        )}

        {mode === 'filter' && (
          <>
            <Form.Item name="domain" label="领域">
              <Select
                placeholder="选择领域"
                allowClear
                options={[
                  { label: '粗大动作', value: '粗大动作' },
                  { label: '精细动作', value: '精细动作' },
                  { label: '语言发展', value: '语言发展' },
                  { label: '认知能力', value: '认知能力' },
                  { label: '社交情感', value: '社交情感' },
                  { label: '感觉统合', value: '感觉统合' },
                ]}
              />
            </Form.Item>

            <Form.Item name="ageRange" label="年龄范围">
              <InputNumber.Group compact>
                <InputNumber
                  style={{ width: '50%' }}
                  placeholder="最小年龄"
                  min={0}
                  max={12}
                />
                <InputNumber
                  style={{ width: '50%' }}
                  placeholder="最大年龄"
                  min={0}
                  max={12}
                />
              </InputNumber.Group>
            </Form.Item>
          </>
        )}

        <Form.Item
          name="concurrency"
          label="并发数"
          initialValue={5}
          rules={[{ required: true }]}
        >
          <InputNumber min={1} max={10} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          name="limit"
          label="检索数量"
          initialValue={10}
          rules={[{ required: true }]}
        >
          <InputNumber min={1} max={50} style={{ width: '100%' }} />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default BatchExecutionModal;
```

#### ExecutionProgress.tsx

```tsx
// frontend/src/features/rag-evaluation/components/ExecutionProgress.tsx

import React from 'react';
import { Progress, Card, Row, Col, Table, Button, Space, Tag } from 'antd';
import { TestRun } from '@/models/rag-test';

interface ExecutionProgressProps {
  testRun: TestRun | null;
  onCancel: () => void;
}

const ExecutionProgress: React.FC<ExecutionProgressProps> = ({
  testRun,
  onCancel,
}) => {
  if (!testRun) return null;

  const isRunning = testRun.status === 'running';
  const isCompleted = testRun.status === 'completed';
  const isCancelled = testRun.status === 'cancelled';

  const columns = [
    {
      title: '用例 ID',
      dataIndex: 'test_case_id',
      key: 'test_case_id',
      width: 120,
    },
    {
      title: '查询',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
    },
    {
      title: 'F1',
      dataIndex: 'f1_score',
      key: 'f1_score',
      width: 80,
      render: (score: number) => (
        <Tag color={score >= 0.7 ? 'green' : 'red'}>
          {score?.toFixed(2) || '-'}
        </Tag>
      ),
    },
    {
      title: '耗时 (ms)',
      dataIndex: 'execution_time_ms',
      key: 'execution_time_ms',
      width: 100,
      render: (ms: number) => ms?.toFixed(0) || '-',
    },
    {
      title: '状态',
      key: 'status',
      width: 80,
      render: (_: any, record: any) => (
        <Tag color={record.f1_score >= 0.7 ? 'success' : 'error'}>
          {record.f1_score >= 0.7 ? '通过' : '失败'}
        </Tag>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card title="执行进度" style={{ marginBottom: 16 }}>
        <Progress
          percent={testRun.progress || 0}
          status={
            isRunning
              ? 'active'
              : isCompleted
              ? 'success'
              : isCancelled
              ? 'exception'
              : 'normal'
          }
        />

        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col span={6}>
            <Card size="small">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold' }}>
                  {testRun.total_test_cases}
                </div>
                <div>总计</div>
              </div>
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: '#52c41a' }}>
                  {testRun.passed_test_cases || 0}
                </div>
                <div>通过</div>
              </div>
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: '#ff4d4f' }}>
                  {(testRun.test_results?.length || 0) -
                    (testRun.passed_test_cases || 0)}
                </div>
                <div>失败</div>
              </div>
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: '#1890ff' }}>
                  {testRun.test_results?.length || 0}
                </div>
                <div>已完成</div>
              </div>
            </Card>
          </Col>
        </Row>

        {isRunning && (
          <Space style={{ marginTop: 16 }}>
            <Button danger onClick={onCancel}>
              取消执行
            </Button>
          </Space>
        )}
      </Card>

      <Card title="执行结果">
        <Table
          columns={columns}
          dataSource={testRun.test_results || []}
          rowKey="test_case_id"
          pagination={false}
          size="small"
          scroll={{ y: 400 }}
        />
      </Card>
    </div>
  );
};

export default ExecutionProgress;
```

### 6.2 API 层扩展

```typescript
// frontend/src/api/rag-test/index.ts

// 新增批量执行 API
export const runBatchTests = async (data: {
  mode: 'cases' | 'test_set' | 'filter';
  case_ids?: string[];
  test_set_id?: string;
  filters?: Record<string, any>;
  concurrency?: number;
  limit?: number;
  name?: string;
  description?: string;
}) => {
  const response = await apiClient.post('/rag/test/run/batch', data);
  return response.data;
};

// 获取测试运行详情（包含进度）
export const getTestRun = async (runId: string) => {
  const response = await apiClient.get(`/rag/test/runs/${runId}`);
  return response.data;
};

// 取消测试运行
export const cancelTestRun = async (runId: string) => {
  const response = await apiClient.post(`/rag/test/run/batch/${runId}/cancel`);
  return response.data;
};
```

### 6.3 Hook 层扩展

```typescript
// frontend/src/features/rag-evaluation/hooks/useRagEvaluation.ts

// 新增状态
const [batchModalVisible, setBatchModalVisible] = useState(false);
const [executionMode, setExecutionMode] = useState<'cases' | 'test_set' | 'filter'>('cases');
const [currentRun, setCurrentRun] = useState<TestRun | null>(null);
const [progressPolling, setProgressPolling] = useState<NodeJS.Timeout | null>(null);
const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);

// 新增方法
const startBatchExecution = async (config: BatchRunConfig) => {
  try {
    setBatchModalVisible(false);
    const run = await runBatchTests({
      mode: config.mode,
      case_ids: config.caseIds,
      test_set_id: config.testSetId,
      filters: config.filters,
      concurrency: config.concurrency,
      limit: config.limit,
      name: config.name,
      description: config.description,
    });
    
    setCurrentRun(run.test_run);
    startProgressPolling(run.test_run.id);
  } catch (err) {
    message.error('批量执行失败');
  }
};

const startProgressPolling = (runId: string) => {
  // 清除之前的轮询
  if (progressPolling) {
    clearInterval(progressPolling);
  }

  const timer = setInterval(async () => {
    try {
      const runData = await getTestRun(runId);
      setCurrentRun(runData.test_run);

      if (runData.test_run.status === 'completed' || 
          runData.test_run.status === 'cancelled') {
        clearInterval(timer);
        setProgressPolling(null);
        message.success('测试执行完成');
        await loadTestRuns();
      }
    } catch (err) {
      console.error('获取进度失败:', err);
    }
  }, 1500);

  setProgressPolling(timer);
};

const cancelExecution = async (runId: string) => {
  try {
    await cancelTestRun(runId);
    if (progressPolling) {
      clearInterval(progressPolling);
      setProgressPolling(null);
    }
    message.info('已取消执行');
  } catch (err) {
    message.error('取消失败');
  }
};

// 清理轮询（组件卸载时）
useEffect(() => {
  return () => {
    if (progressPolling) {
      clearInterval(progressPolling);
    }
  };
}, [progressPolling]);
```

### 6.4 TestCaseTable 扩展

```tsx
// frontend/src/features/rag-evaluation/components/TestCaseTable.tsx

// 新增 props
interface TestCaseTableProps {
  // ... 现有 props ...
  selectedCaseIds?: string[];
  onSelectionChange?: (ids: string[]) => void;
  onRunBatch?: (mode: 'cases' | 'test_set' | 'filter') => void;
}

// 添加多选支持
const rowSelection = {
  selectedRowKeys: selectedCaseIds,
  onChange: (selectedKeys: React.Key[]) => {
    onSelectionChange?.(selectedKeys as string[]);
  },
};

// 在工具栏添加批量执行按钮
<Space style={{ marginBottom: 16 }}>
  {selectedCaseIds.length > 0 && (
    <Button
      type="primary"
      onClick={() => onRunBatch?.('cases')}
    >
      执行选中 ({selectedCaseIds.length})
    </Button>
  )}
  <Button onClick={() => onRunBatch?.('test_set')}>
    执行测试集
  </Button>
  <Button onClick={() => onRunBatch?.('filter')}>
    条件执行
  </Button>
</Space>

// 修复单个运行按钮
{
  title: '操作',
  render: (_, record) => (
    <Space>
      <Button
        size="small"
        onClick={() => onRunSingle?.(record.id)}
      >
        运行
      </Button>
      {/* ... 其他操作 ... */}
    </Space>
  ),
}
```

---

## 七、错误处理设计

### 7.1 错误场景与处理策略

| 场景 | 处理策略 | 用户提示 |
|------|----------|----------|
| 单个用例执行失败 | 记录错误到 `test_run.errors`，继续执行其他用例 | 结果表格中标记为失败 |
| 并发数超限 | Semaphore 自动排队，不报错 | 无 |
| 用户取消执行 | 设置 cancel 标志，正在执行的用例完成后停止 | "已取消执行" |
| 网络中断 | 前端轮询超时，显示"连接中断"提示 | "连接中断，可重新查询进度" |
| 无效的参数 | 后端校验，返回 400 + 错误信息 | 表单校验错误提示 |
| 测试集不存在 | 后端返回 404 | "测试集不存在" |
| 无符合条件的用例 | 后端返回 400 | "没有找到符合条件的测试用例" |

### 7.2 重试机制

当前设计不支持自动重试，但可以在 ExecutionProgress 组件中添加"重试失败"按钮，手动重新执行失败的用例。

---

## 八、执行流程图

```
用户选择执行方式
     ↓
打开 BatchExecutionModal
     ├── 选择执行模式
     ├── 配置并发数 (默认 5)
     └── 点击"开始执行"
          ↓
前端调用 POST /rag/test/run/batch
     ↓
后端创建 TestRun (status="running")
     ↓
返回 run_id 给前端
     ↓
前端开始轮询 GET /rag/test/runs/{run_id} (每 1.5s)
     ↓
后端并发执行测试用例
     ├── asyncio.Semaphore 控制并发数
     ├── 每完成一个，更新 test_results 和 progress
     └── 全部完成后 status="completed"
          ↓
前端检测到 completed，停止轮询
     ↓
显示完整结果报告
```

---

## 九、文件变更清单

### 9.1 后端 (Python)

| 文件 | 变更类型 | 变更内容 |
|------|----------|----------|
| `backend/src/model/rag_test.py` | 修改 | TestRun 增加 mode, concurrency, case_ids, progress, started_at, completed_at, errors 字段 |
| `backend/src/service/rag_test_manager.py` | 修改 | 新增 run_batch_tests, _resolve_test_cases, _filter_test_cases, _create_batch_test_run, _run_single_with_semaphore, cancel_test_run 方法 |
| `backend/src/controller/rag_test_controller.py` | 修改 | 新增 BatchRunRequest 模型，新增 /run/batch, /run/batch/{run_id}/cancel 端点 |

### 9.2 前端 (TypeScript)

| 文件 | 变更类型 | 变更内容 |
|------|----------|----------|
| `frontend/src/api/rag-test/index.ts` | 修改 | 新增 runBatchTests, getTestRun, cancelTestRun API |
| `frontend/src/features/rag-evaluation/hooks/useRagEvaluation.ts` | 修改 | 新增批量执行状态和方法 |
| `frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx` | 修改 | 新增批量执行入口和状态管理 |
| `frontend/src/features/rag-evaluation/components/BatchExecutionModal.tsx` | 新增 | 批量执行配置弹窗 |
| `frontend/src/features/rag-evaluation/components/ExecutionProgress.tsx` | 新增 | 实时进度组件 |
| `frontend/src/features/rag-evaluation/components/TestCaseTable.tsx` | 修改 | 支持多选 + 修复单个运行 bug |

---

## 十、性能考虑

### 10.1 并发控制
- 使用 `asyncio.Semaphore` 限制并发数，默认 5，最大 10
- 避免同时过多请求 LLM 和向量数据库

### 10.2 内存管理
- 大量测试用例时，test_results 可能很大
- 建议单次执行不超过 50 个用例
- 前端表格使用虚拟滚动（Ant Design Table 默认支持）

### 10.3 轮询优化
- 轮询间隔 1.5 秒，平衡实时性和服务器压力
- 执行完成后立即停止轮询
- 组件卸载时清理轮询定时器

### 10.4 指标计算策略

**核心原则**：批量执行过程中不计算整体指标，等所有用例执行完成后再统一计算。

**原因**：
1. **数据完整性**：执行过程中的指标基于部分数据，没有参考价值
2. **性能优化**：减少执行过程中的重复计算开销
3. **准确性**：最终指标基于完整数据集，更准确

**实现方式**：
```python
# 执行过程中：仅更新进度
async def _run_single_with_semaphore(...):
    result = await self.run_test_case(test_case, limit)
    test_run.test_results.append(result)
    test_run.progress = int(completed / total * 100)  # 仅更新进度
    # 不计算指标！

# 执行完成后：统一计算指标
async def run_batch_tests(...):
    await asyncio.gather(*tasks)  # 等待所有用例执行完成
    self._calculate_overall_metrics(test_run)  # 一次性计算
    test_run.status = "completed"
```

**前端展示**：
- 执行中：显示进度条 + 已完成数量（不显示指标）
- 执行完成：显示完整指标（precision、recall、f1、mrr、ndcg）

---

## 十一、测试策略

### 11.1 后端测试

```python
# backend/tests/test_batch_execution.py

async def test_run_batch_tests_by_case_ids():
    """测试按 ID 列表执行"""
    pass

async def test_run_batch_tests_by_test_set():
    """测试按测试集执行"""
    pass

async def test_run_batch_tests_by_filter():
    """测试按条件过滤执行"""
    pass

async def test_cancel_batch_execution():
    """测试取消执行"""
    pass

async def test_concurrent_execution():
    """测试并发执行"""
    pass

async def test_error_handling():
    """测试错误处理（单个失败不影响其他）"""
    pass
```

### 11.2 前端测试

```typescript
// frontend/src/features/rag-evaluation/__tests__/BatchExecutionModal.test.tsx

test('should submit batch execution config', () => {
  // 测试表单提交
});

test('should show selected case count', () => {
  // 测试显示已选用例数量
});

test('should validate concurrency range', () => {
  // 测试并发数校验
});
```

---

## 十二、后续扩展

### 12.1 可能的未来功能
1. **WebSocket 实时推送**：替代轮询，更低的延迟
2. **任务队列**：引入 Celery/Redis 支持超大批量（100+ 用例）
3. **定时执行**：支持定时/周期性执行测试
4. **结果对比**：对比两次批量执行的结果差异
5. **导出报告**：导出批量执行结果为 PDF/Excel

### 12.2 当前不实现
- 自动重试失败用例（可手动重试）
- 执行暂停/恢复（只支持取消）
- 优先级队列（所有用例平等）

---

## 十三、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM API 限流 | 部分用例执行失败 | Semaphore 控制并发，错误记录不中断 |
| 向量数据库负载过高 | 检索变慢 | 限制并发数，监控数据库性能 |
| 前端轮询过多 | 服务器压力 | 1.5s 间隔，完成后立即停止 |
| 大量结果导致内存问题 | 前端卡顿 | 限制单次执行数量，表格虚拟滚动 |

---

## 十四、书籍导入模块优化

### 14.1 优化目标

全面优化书籍导入模块，解决现有问题并提升用户体验：
1. 使用文档解析服务替代直接读取文件，提升草稿生成质量
2. 支持用户自定义生成参数（领域、年龄范围、数量等）
3. 可选将书籍索引到知识库，关联实际知识块 ID
4. 增加进度反馈、重试机制、文档质量评估
5. 生成多样化的测试用例，考核 RAG 的不同能力

### 14.2 现有问题分析

| 问题 | 严重程度 | 影响 |
|------|----------|------|
| 直接读取 PDF 二进制文件 | 严重 | 草稿生成质量差，LLM 收到乱码 |
| 生成参数硬编码 | 严重 | 用户无法自定义，灵活性差 |
| 书籍与知识库隔离 | 严重 | `expected_knowledge_ids` 始终为空 |
| `content_summary` 为空 | 中等 | 降级逻辑无效 |
| 缺少进度反馈 | 中等 | 用户不知道生成进度 |
| LLM 失败无重试 | 中等 | 网络波动导致整个上传失败 |
| TXT 解析支持不完整 | 中等 | 前端接受但后端无正式支持 |
| 审核即导入不灵活 | 低 | 无法只标记审核稍后批量导入 |
| 缺少文档质量评估 | 低 | 无法提示文档是否适合生成 |
| 草稿无去重机制 | 低 | 可能生成重复草稿 |

### 14.3 优化方案

#### 14.3.1 文档解析集成

**当前问题**：`upload_source_document()` 仅保存文件，未解析内容。

**优化方案**：
```python
# 上传流程改为：
上传文件 → 保存临时文件 → 调用 DocumentIngestionService 解析
  → 获取解析后的文本内容 → 创建 SourceDocument（填充 content_summary）
  → 如果 index_to_knowledge_base=true → 索引到向量库
  → 生成草稿时使用解析后的文本
```

**实现细节**：
```python
async def upload_source_document(
    self,
    file_path: str,
    title: str,
    index_to_knowledge_base: bool = False,  # 新增参数
) -> SourceDocument:
    # 1. 计算哈希、检查去重（现有逻辑）
    
    # 2. 调用文档解析服务
    from src.service.document_ingestion_service import DocumentIngestionService
    ingestion_service = DocumentIngestionService()
    
    # 解析文档获取文本内容
    parsed_content = await ingestion_service.parse_document(file_path)
    content_summary = parsed_content[:500] + "..." if len(parsed_content) > 500 else parsed_content
    
    # 3. 如果选择索引到知识库
        if index_to_knowledge_base:
            task_id = await ingestion_service.ingest_document(file_path, title)
            # 🔹 索引依赖明确：等待索引完成后再生成测试用例，确保可以正确关联expected_knowledge_ids字段
            await ingestion_service.wait_for_task_completed(task_id, timeout=300)  # 最多等待5分钟
        
        # 4. 创建 SourceDocument 记录（填充 content_summary）
        doc = SourceDocument(
            id=doc_id,
            title=title,
            file_type=file_type,
            file_path=dest_path,
            file_hash=file_hash,
            content_summary=content_summary,  # 新增
            status="ready",
        )
    
    return doc
```

#### 14.3.2 生成参数自定义

**前端 UI 扩展**：在 `UploadDocumentModal` 中增加参数配置面板

```tsx
// UploadDocumentModal.tsx 新增表单项
<Form.Item name="targetDomains" label="目标领域" initialValue={["感觉统合"]}>
  <Select
    mode="multiple"
    placeholder="选择领域"
    options={[
      { label: '粗大动作', value: '粗大动作' },
      { label: '精细动作', value: '精细动作' },
      { label: '语言发展', value: '语言发展' },
      { label: '认知能力', value: '认知能力' },
      { label: '社交情感', value: '社交情感' },
      { label: '感觉统合', value: '感觉统合' },
    ]}
  />
</Form.Item>

<Form.Item name="ageRange" label="年龄范围" initialValue={[0, 6]}>
  <InputNumber.Group compact>
    <InputNumber style={{ width: '50%' }} placeholder="最小年龄" min={0} max={12} />
    <InputNumber style={{ width: '50%' }} placeholder="最大年龄" min={0} max={12} />
  </InputNumber.Group>
</Form.Item>

<Form.Item name="count" label="生成数量" initialValue={10}>
  <InputNumber min={1} max={50} style={{ width: '100%' }} />
</Form.Item>

<Form.Item name="difficulty" label="难度分布" initialValue="mixed">
  <Select options={[
    { label: '混合难度（推荐）', value: 'mixed' },
    { label: '简单', value: 'easy' },
    { label: '中等', value: 'medium' },
    { label: '困难', value: 'hard' },
  ]} />
</Form.Item>

<Form.Item name="indexToKnowledgeBase" label="索引到知识库" valuePropName="checked" initialValue={false}>
  <Switch checkedChildren="是" unCheckedChildren="否" />
</Form.Item>
```

**后端 API 扩展**：
```python
class GenerationParams(BaseModel):
    """测试用例生成参数"""
    target_domains: List[str] = Field(default_factory=lambda: ["感觉统合"])
    age_min: int = 0
    age_max: int = 6
    count: int = Field(10, ge=10, le=500)
    difficulty: str = "mixed"

class UploadDocumentRequest(BaseModel):
    title: str = ""
    auto_generate: bool = True
    index_to_knowledge_base: bool = False  # 新增
    generation_params: Optional[GenerationParams] = None  # 新增
```

#### 14.3.3 大规模多样化测试用例生成

**核心需求**：
- 从一本书生成上百个测试用例草稿（100-500 个）
- 每个问题的角度都要不一致，避免重复
- 考核 RAG 系统的不同能力维度

**多样化策略矩阵**：

通过多维度组合实现高度多样化，而非仅依赖 6 种固定类型：

```python
class TestCaseDraftGenerator:
    """大规模多样化测试用例草稿生成器"""
    
    # 1. 考核维度（12 种）
    EVALUATION_DIMENSIONS = [
        {
            "type": "factual_retrieval",
            "name": "事实检索",
            "description": "测试能否检索到具体的发展里程碑数据",
            "weight": 0.15,  # 占比 15%
        },
        {
            "type": "concept_definition",
            "name": "概念定义",
            "description": "测试对专业术语的定义解释能力",
            "weight": 0.10,
        },
        {
            "type": "concept_comparison",
            "name": "概念对比",
            "description": "测试区分相似概念的能力",
            "weight": 0.08,
        },
        {
            "type": "age_milestone",
            "name": "年龄里程碑",
            "description": "测试特定年龄段的发展标准",
            "weight": 0.12,
        },
        {
            "type": "cross_age_comparison",
            "name": "跨年龄对比",
            "description": "测试对比不同年龄段发展差异",
            "weight": 0.08,
        },
        {
            "type": "domain_integration",
            "name": "跨领域整合",
            "description": "测试整合多个发展领域的能力",
            "weight": 0.07,
        },
        {
            "type": "scenario_application",
            "name": "场景应用",
            "description": "测试将理论应用到实际场景",
            "weight": 0.12,
        },
        {
            "type": "problem_diagnosis",
            "name": "问题诊断",
            "description": "测试根据表现识别发展问题",
            "weight": 0.08,
        },
        {
            "type": "intervention_design",
            "name": "干预设计",
            "description": "测试设计训练活动的能力",
            "weight": 0.08,
        },
        {
            "type": "risk_identification",
            "name": "风险识别",
            "description": "测试识别发展风险因素",
            "weight": 0.05,
        },
        {
            "type": "professional_term",
            "name": "专业术语",
            "description": "测试对专业术语的理解和使用",
            "weight": 0.04,
        },
        {
            "type": "comprehensive_analysis",
            "name": "综合分析",
            "description": "测试综合分析多个知识点",
            "weight": 0.03,
        },
    ]
    
    # 2. 问题角度模板（每个维度下有多个角度）
    QUESTION_ANGLES = {
        "factual_retrieval": [
            "{age}岁儿童在{domain}方面应该达到什么标准？",
            "{domain}发展的关键指标有哪些？",
            "请列出{age}岁儿童的{domain}发展清单",
            "{domain}能力在{age}岁时的具体表现是什么？",
            "评估{domain}发展的标准是什么？",
        ],
        "concept_definition": [
            "什么是{concept}？它对儿童发展有什么意义？",
            "请解释{concept}的含义和重要性",
            "{concept}在儿童发展中扮演什么角色？",
            "如何理解{concept}这个概念？",
        ],
        "concept_comparison": [
            "{concept_a}和{concept_b}有什么区别？",
            "如何区分{concept_a}和{concept_b}？",
            "{concept_a}与{concept_b}的关联是什么？",
        ],
        "age_milestone": [
            "{age}岁儿童应该掌握哪些{domain}技能？",
            "{domain}发展在{age}岁的典型表现",
            "如何判断{age}岁儿童的{domain}发展是否正常？",
        ],
        "cross_age_comparison": [
            "{age1}岁和{age2}岁儿童在{domain}上有什么区别？",
            "{domain}能力从{age1}岁到{age2}岁如何发展？",
            "对比{age1}岁和{age2}岁的{domain}发展标准",
        ],
        "domain_integration": [
            "{domain_a}和{domain_b}之间有什么关联？",
            "如何同时促进{domain_a}和{domain_b}的发展？",
            "{domain_a}发展如何影响{domain_b}？",
        ],
        "scenario_application": [
            "一个{age}岁儿童{symptom}，可能是什么问题？",
            "针对{scenario}场景，应该设计什么训练活动？",
            "儿童在{context}下表现{behavior}，如何评估？",
        ],
        "problem_diagnosis": [
            "儿童经常{behavior}，可能反映了什么发展问题？",
            "如何判断{symptom}是否需要专业干预？",
            "{behavior}是正常发展现象还是需要关注？",
        ],
        "intervention_design": [
            "为{age}岁儿童设计{domain}训练活动",
            "如何改善儿童的{domain}能力？",
            "针对{problem}，有哪些有效的干预方法？",
        ],
        "risk_identification": [
            "哪些因素会影响儿童的{domain}发展？",
            "{behavior}可能带来什么发展风险？",
            "如何预防{domain}发展迟缓？",
        ],
        "professional_term": [
            "请解释{term}在儿童发展中的含义",
            "{term}与儿童发展有什么关系？",
            "如何使用{term}评估儿童发展？",
        ],
        "comprehensive_analysis": [
            "综合分析{age}岁儿童{domain}发展的关键要素",
            "请全面评估{scenario}下的儿童发展状况",
            "从多个维度分析{problem}的原因和对策",
        ],
    }
    
    # 3. 内容切片策略（确保覆盖文档不同部分）
    CONTENT_SLICING_STRATEGIES = [
        "chapter_based",      # 按章节切片
        "topic_based",        # 按主题切片
        "random_segment",     # 随机段落切片
        "key_concept",        # 关键概念切片
        "age_group",          # 按年龄分组切片
    ]
    
    def __init__(self):
        # 模型选择配置
        self.MODEL_CONFIG = {
            "qwen-plus": {
                "max_batch_size": 10,
                "cost_per_1k_tokens": 0.012,
                "recommended_max_count": 50
            },
            "qwen3-omni-flash": {
                "max_batch_size": 20,
                "cost_per_1k_tokens": 0.001,  # 便宜12倍
                "recommended_max_count": 500
            }
        }
        
    async def generate_large_scale_diverse_drafts(
        self,
        content: str,
        params: GenerationParams,
    ) -> List[TestCaseDraft]:
        """
        大规模多样化生成测试用例草稿
        
        Args:
            content: 文档内容
            params: 生成参数（count 可达 100-500）
            
        Returns:
            多样化的测试用例草稿列表
        """
        drafts = []
        generated_queries = set()  # 用于去重
        
        # 1. 自动选择模型
        selected_model = self._select_model(params)
        logger.info(f"生成 {params.count} 个测试用例，使用模型: {selected_model}")
        
        # 2. 解析文档结构，提取关键信息
        doc_structure = await self._parse_document_structure(content)
        concepts = doc_structure["concepts"]
        chapters = doc_structure["chapters"]
        age_groups = doc_structure["age_groups"]
        domains = doc_structure["domains"]
        
        # 3. 按权重分配各维度的生成数量
        dimension_counts = self._allocate_dimension_counts(
            params.count, self.EVALUATION_DIMENSIONS
        )
        
        # 4. 为每个维度生成指定数量的用例
        for dimension in self.EVALUATION_DIMENSIONS:
            dim_count = dimension_counts[dimension["type"]]
            
            for i in range(dim_count):
                # 为每个用例选择不同的角度、内容切片、参数组合
                draft = await self._generate_unique_draft(
                    content=content,
                    params=params,
                    dimension=dimension,
                    doc_structure=doc_structure,
                    concepts=concepts,
                    chapters=chapters,
                    age_groups=age_groups,
                    domains=domains,
                    generated_queries=generated_queries,
                    draft_index=len(drafts),
                    model=selected_model
                )
                
                if draft:
                    drafts.append(draft)
        
        # 5. 最终去重检查
        drafts = self._final_deduplication(drafts)
        
        return drafts
    
    def _select_model(self, params: GenerationParams) -> str:
        """选择测试用例生成模型，从系统配置读取"""
        from src.config import settings
        return settings.rag_test.test_case_generation_model  # 默认qwen3-omni-flash，可在配置页面修改
    
    async def _generate_unique_draft(
        self,
        content,
        params,
        dimension,
        doc_structure,
        concepts,
        chapters,
        age_groups,
        domains,
        generated_queries,
        draft_index,
        model: str,  # 新增模型参数
    ) -> Optional[TestCaseDraft]:
        """生成一个独特的测试用例，确保与已有用例不重复"""
        max_attempts = 5
        
        for attempt in range(max_attempts):
            # 1. 随机选择问题角度
            angles = self.QUESTION_ANGLES.get(dimension["type"], [])
            angle_template = random.choice(angles)
            
            # 2. 随机选择内容切片
            content_slice = self._select_content_slice(
                content, doc_structure, draft_index, attempt
            )
            
            # 3. 填充模板参数
            filled_query = self._fill_angle_template(
                angle_template,
                concepts=concepts,
                chapters=chapters,
                age_groups=age_groups,
                domains=domains,
                params=params,
            )
            
            # 4. 检查是否与已有查询重复
            if self._is_unique_query(filled_query, generated_queries):
                # 5. 调用 LLM 生成完整草稿
                draft = await self._create_draft_with_llm(
                    query=filled_query,
                    content_slice=content_slice,
                    dimension=dimension,
                    params=params,
                )
                
                if draft:
                    generated_queries.add(filled_query)
                    return draft
        
        return None
    
    def _select_content_slice(
        self, content, doc_structure, draft_index, attempt
    ) -> str:
        """根据草稿索引和尝试次数选择不同的内容切片"""
        strategy = self.CONTENT_SLICING_STRATEGIES[
            (draft_index + attempt) % len(self.CONTENT_SLICING_STRATEGIES)
        ]
        
        if strategy == "chapter_based":
            chapter_idx = draft_index % len(doc_structure["chapters"])
            return doc_structure["chapters"][chapter_idx]["content"]
        
        elif strategy == "topic_based":
            topic_idx = draft_index % len(doc_structure["topics"])
            return doc_structure["topics"][topic_idx]["content"]
        
        elif strategy == "random_segment":
            # 随机选择一段内容
            segments = self._split_into_segments(content)
            seg_idx = (draft_index + attempt * 7) % len(segments)
            return segments[seg_idx]
        
        # ... 其他策略
    
    def _allocate_dimension_counts(
        self, total_count: int, dimensions: List[Dict]
    ) -> Dict[str, int]:
        """根据权重分配各维度的生成数量"""
        counts = {}
        remaining = total_count
        
        for i, dim in enumerate(dimensions):
            if i == len(dimensions) - 1:
                counts[dim["type"]] = remaining
            else:
                count = int(total_count * dim["weight"])
                counts[dim["type"]] = count
                remaining -= count
        
        return counts
```

**数据模型扩展**：
```python
class TestCaseDraft(BaseModel):
    # ... 现有字段 ...
    evaluation_type: str = "factual_retrieval"  # 新增：考核类型（12 种）
    difficulty_level: str = "medium"            # 新增：难度等级
    content_source: str = ""                    # 新增：内容来源（章节/主题）
    question_angle: str = ""                    # 新增：问题角度模板
```

**生成数量配置**：
```tsx
// 前端调整生成数量上限
<Form.Item name="count" label="生成数量" initialValue={100}>
  <InputNumber 
    min={10} 
    max={500} 
    step={10}
    style={{ width: '100%' }} 
    addonAfter="个"
  />
  <div style={{ fontSize: '12px', color: '#8c8c8c', marginTop: '4px' }}>
    💡 生成500个用例预计成本约0.5元（qwen3-omni-flash模型）
  </div>
</Form.Item>
```

**多样化保证机制**：

| 机制 | 说明 | 效果 |
|------|------|------|
| 12 种考核维度 | 覆盖事实检索、概念理解、场景应用等 | 宏观层面多样化 |
| 50+ 问题角度模板 | 每个维度下有多个角度模板 | 中观层面多样化 |
| 5 种内容切片策略 | 按章节/主题/随机/概念/年龄切片 | 内容来源多样化 |
| 参数随机组合 | 年龄、领域、概念随机组合 | 参数层面多样化 |
| 查询去重检查 | 生成前检查是否与已有查询重复 | 避免重复 |
| 最终去重过滤 | 生成后基于相似度再次去重 | 兜底保证 |

**示例：生成 100 个用例的分布**

| 考核维度 | 权重 | 数量 | 示例问题 |
|----------|------|------|----------|
| 事实检索 | 15% | 15 | "2 岁儿童在粗大动作方面应该达到什么标准？" |
| 概念定义 | 10% | 10 | "什么是前庭觉？它对儿童发展有什么意义？" |
| 概念对比 | 8% | 8 | "前庭觉和本体觉有什么区别？" |
| 年龄里程碑 | 12% | 12 | "3 岁儿童应该掌握哪些精细动作技能？" |
| 跨年龄对比 | 8% | 8 | "1 岁和 3 岁儿童在语言发展上有什么区别？" |
| 跨领域整合 | 7% | 7 | "粗大动作和精细动作之间有什么关联？" |
| 场景应用 | 12% | 12 | "一个 2 岁儿童经常摔倒，应该设计什么训练活动？" |
| 问题诊断 | 8% | 8 | "儿童经常碰撞东西，可能是什么发展问题？" |
| 干预设计 | 8% | 8 | "为 3 岁儿童设计感觉统合训练活动" |
| 风险识别 | 5% | 5 | "哪些因素会影响儿童的语言发展？" |
| 专业术语 | 4% | 4 | "请解释'本体觉失调'在儿童发展中的含义" |
| 综合分析 | 3% | 3 | "综合分析 2-3 岁儿童感觉统合发展的关键要素" |

#### 14.3.4 进度反馈优化

**当前问题**：草稿生成阶段从 40% 直接跳到 100%。

**优化方案**：
```python
async def generate_test_case_drafts(
    self,
    source_document_id: str,
    params: GenerationParams,
    progress_callback: Optional[Callable] = None,  # 新增回调
) -> List[TestCaseDraft]:
    # 1. 读取内容 (进度 0-10%)
    content = await self._read_document_content(source_document_id)
    if progress_callback:
        progress_callback(10, "文档解析完成")
    
    # 2. 分批生成 (进度 10-90%)
    total_batches = (params.count + 2) // 3  # 每批 3 个
    all_drafts = []
    
    for batch_idx in range(total_batches):
        if progress_callback:
            progress = 10 + int((batch_idx / total_batches) * 80)
            progress_callback(progress, f"正在生成第 {batch_idx + 1}/{total_batches} 批")
        
        batch_drafts = await self._generate_batch(content, params, batch_idx)
        all_drafts.extend(batch_drafts)
    
    # 3. 保存草稿 (进度 90-100%)
    if progress_callback:
        progress_callback(95, "正在保存草稿")
    
    await self._save_drafts(all_drafts)
    
    if progress_callback:
        progress_callback(100, f"生成完成，共 {len(all_drafts)} 条草稿")
    
    return all_drafts
```

**前端进度展示**：
```tsx
// UploadDocumentModal.tsx 中的轮询处理
const pollTaskStatus = async (taskId: string) => {
  const task = await getUploadTask(taskId);
  
  setProgress({
    percent: task.progress || 0,
    status: task.status,
    message: task.message || '',
    draftCount: task.draft_count || 0,
  });
  
  if (task.status === 'completed') {
    message.success(`文档处理完成，生成了 ${task.draft_count} 条草稿`);
    onSuccess();
  } else if (task.status === 'failed') {
    message.error(`处理失败：${task.error}`);
  }
};
```

#### 14.3.5 LLM 重试机制

```python
async def _generate_with_retry(
    self,
    prompt: str,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
) -> str:
    """带重试的 LLM 调用"""
    for attempt in range(max_retries):
        try:
            response = await self.llm.invoke(prompt)
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            
            wait_time = backoff_factor ** attempt
            logger.warning(f"LLM 调用失败，{wait_time}s 后重试 (第 {attempt + 1} 次): {e}")
            await asyncio.sleep(wait_time)
```

#### 14.3.6 文档质量评估

```python
class DocumentQualityEvaluator:
    """文档质量评估器"""
    
    async def evaluate(self, file_path: str, file_type: str) -> Dict:
        """评估文档质量"""
        report = {
            "score": 0.0,
            "issues": [],
            "recommendations": [],
        }
        
        # 1. 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size < 10000:  # 小于 10KB
            report["issues"].append("文件内容过少，可能影响生成质量")
            report["score"] -= 20
        
        # 2. 检查文本提取率（PDF）
        if file_type == "pdf":
            text = self._extract_pdf_text(file_path)
            text_ratio = len(text) / file_size if file_size > 0 else 0
            
            if text_ratio < 0.1:
                report["issues"].append("文本提取率低，可能是扫描版 PDF")
                report["recommendations"].append("建议使用 OCR 解析版本")
                report["score"] -= 30
        
        # 3. 检查内容相关性
        content = text[:2000]
        relevance_score = self._check_relevance(content)
        report["score"] += relevance_score
        
        # 4. 总体评级
        if report["score"] >= 80:
            report["level"] = "excellent"
        elif report["score"] >= 60:
            report["level"] = "good"
        elif report["score"] >= 40:
            report["level"] = "fair"
        else:
            report["level"] = "poor"
        
        return report
```

**前端质量提示**：
```tsx
// 上传完成后显示质量报告
{qualityReport && (
  <Alert
    type={qualityReport.level === 'poor' ? 'warning' : 'info'}
    message="文档质量评估"
    description={
      <div>
        <p>质量等级：{qualityReport.level}</p>
        {qualityReport.issues.map((issue, i) => (
          <p key={i}>⚠️ {issue}</p>
        ))}
        {qualityReport.recommendations.map((rec, i) => (
          <p key={i}>💡 {rec}</p>
        ))}
      </div>
    }
  />
)}
```

#### 14.3.7 草稿去重机制

```python
class DraftDeduplicator:
    """草稿去重器"""
    
    def deduplicate(
        self,
        new_drafts: List[TestCaseDraft],
        existing_drafts: List[TestCaseDraft],
        similarity_threshold: float = 0.85,
    ) -> List[TestCaseDraft]:
        """去重新草稿"""
        unique_drafts = []
        
        for new_draft in new_drafts:
            is_duplicate = False
            
            for existing in existing_drafts:
                similarity = self._calculate_similarity(
                    new_draft.query,
                    existing.query,
                )
                
                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_drafts.append(new_draft)
        
        return unique_drafts
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()
```

#### 14.3.8 灵活的审核导入流程

**当前问题**：审核通过即导入，无法分离。

**优化方案**：
```python
# 新增 API 端点
@router.post("/drafts/batch-review")
async def batch_review_drafts(request: BatchReviewRequest):
    """批量审核草稿（不导入）"""
    for draft_id in request.draft_ids:
        await rag_test_manager.review_draft(
            draft_id,
            action=request.action,  # reviewed/rejected
            auto_import=False,      # 新增参数
        )
    return {"status": "success", "count": len(request.draft_ids)}


@router.post("/drafts/batch-import")
async def batch_import_drafts(request: BatchImportRequest):
    """批量导入已审核草稿"""
    imported = await rag_test_manager.import_reviewed_drafts(
        draft_ids=request.draft_ids,
    )
    return {"status": "success", "imported_count": len(imported)}
```

### 14.4 文件变更清单

#### 后端 (Python)

| 文件 | 变更类型 | 变更内容 |
|------|----------|----------|
| `backend/src/model/rag_test.py` | 修改 | TestCaseDraft 增加 evaluation_type, difficulty_level 字段 |
| `backend/src/service/rag_test_manager.py` | 修改 | 重构 upload_source_document, generate_test_case_drafts, 新增重试/去重/质量评估方法 |
| `backend/src/controller/rag_test_controller.py` | 修改 | 扩展上传 API 支持参数，新增批量审核/导入端点 |
| `backend/src/core/prompts.py` | 修改 | 新增多样化测试用例生成提示词 |
| `backend/src/core/rag_test/test_case_generator.py` | 新增 | 多样化测试用例生成器类 |
| `backend/src/core/rag_test/document_quality_evaluator.py` | 新增 | 文档质量评估器类 |
| `backend/src/core/rag_test/draft_deduplicator.py` | 新增 | 草稿去重器类 |
| `backend/src/config/modules/rag/test.py` | 新增 | RAG测试配置模块，默认`test_case_generation_model = "qwen3-omni-flash"`，支持在系统配置页面修改 |

> 🔹 类目录规范：所有RAG测试相关核心类统一放在`backend/src/core/rag_test/`子目录下，保持core目录结构整洁

#### 前端 (TypeScript)

| 文件 | 变更类型 | 变更内容 |
|------|----------|----------|
| `frontend/src/features/rag-evaluation/components/UploadDocumentModal.tsx` | 修改 | 增加参数配置面板、进度展示、质量报告 |
| `frontend/src/api/rag-test/index.ts` | 修改 | 新增批量审核/导入 API |
| `frontend/src/features/rag-evaluation/components/TestCaseReviewTable.tsx` | 修改 | 支持批量选择审核/导入 |

### 14.5 优化前后对比

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| 文档解析 | 直接读取二进制文件 | 使用 DocumentIngestionService 解析 |
| 生成参数 | 硬编码（感觉统合/0-6 岁/10 个） | 用户可自定义 |
| 知识库关联 | 完全隔离 | 可选索引到知识库 |
| 测试用例多样性 | 单一类型 | 12 种考核维度，各不相同 |
| 模型选择 | 固定使用 qwen-plus | 智能选择模型，大规模生成成本降低10倍 |
| 进度反馈 | 40% → 100% 跳跃 | 实时进度更新 |
| LLM 容错 | 失败即抛异常 | 3 次指数退避重试 |
| 文档质量 | 无评估 | 自动评估并提示 |
| 草稿去重 | 无 | 基于相似度去重 |
| 审核流程 | 审核即导入 | 支持分离审核和导入 |

### 14.6 多样化测试用例生成提示词设计

```python
# backend/src/core/prompts.py

TEST_CASE_DIMENSIONS_PROMPT = """
你是一个儿童发展评估专家。请根据提供的文档内容，生成多样化的测试用例来考核 RAG 系统的不同能力。

文档内容：
{content}

生成要求：
- 目标领域：{domains}
- 年龄范围：{age_min}-{age_max} 岁
- 生成数量：{count} 个
- 难度分布：{difficulty}

请确保每个测试用例考核不同的能力维度：

1. **事实检索** (factual_retrieval)
   - 考核：能否检索到具体的发展里程碑数据
   - 示例："2 岁儿童应该能够完成哪些大动作技能？"

2. **概念理解** (concept_understanding)
   - 考核：对专业概念的理解和解释
   - 示例："什么是前庭觉？它对儿童发展有什么影响？"

3. **对比分析** (comparison)
   - 考核：对比不同年龄段/领域的能力
   - 示例："1 岁和 3 岁儿童在精细动作发展上有什么区别？"

4. **应用实践** (application)
   - 考核：将理论知识应用到实际场景
   - 示例："一个 2 岁儿童经常摔倒，平衡感差，应该设计什么样的训练活动？"

5. **综合分析** (synthesis)
   - 考核：综合多个知识点的能力
   - 示例："请综合分析 3-4 岁儿童感觉统合发展的关键要素和训练建议"

6. **关键词匹配** (keyword_matching)
   - 考核：对专业术语的识别能力
   - 示例："解释'本体觉失调'的表现和干预方法"

请以 JSON 格式返回，每个测试用例包含：
- query: 查询问题
- age: 适用年龄
- domain: 领域
- evaluation_type: 考核类型（从上述 6 种中选择）
- difficulty: 难度（easy/medium/hard）
- expected_keywords: 预期关键词列表
- description: 问题描述
- answer_points: 得分要点
- professional_terms: 相关专业术语
- age_requirement: 年龄要求说明
"""
```

---

## 十五、删除报告后评分同步机制

### 15.1 需求说明

删除评估报告（TestRun）后，所有相关的评分统计数据必须同步更新，确保数据一致性。

### 15.2 当前系统分析

**现有架构**：
- 每个 TestRun 以独立 JSON 文件存储在 `{rag_storage_dir}/test_runs/{run_id}.json`
- 聚合评分（历史平均分、配置版本对比等）是**实时计算**的，每次查询时遍历所有 TestRun 文件
- 删除操作仅删除对应的 JSON 文件，**没有触发评分同步**

**存在的问题**：
1. 删除报告后，前端不会自动刷新评分数据
2. 没有明确的反馈告知用户评分已更新
3. 如果将来引入独立的聚合统计存储，当前删除逻辑无法触发重新计算

### 15.3 评分同步方案

#### 15.3.1 后端扩展

**修改删除 API**：
```python
# backend/src/controller/rag_test_controller.py

@router.delete("/runs/{run_id}")
async def delete_test_run(run_id: str):
    """删除测试运行结果并同步更新评分"""
    try:
        # 1. 删除 TestRun 文件
        success = rag_test_manager.delete_test_run(run_id)
        if not success:
            raise HTTPException(status_code=404, detail="Test run not found")
        
        # 2. 重新计算聚合评分
        updated_aggregates = rag_test_manager.recalculate_aggregate_scores()
        
        # 3. 返回删除结果和更新后的评分
        return {
            "status": "success",
            "message": "Test run deleted and scores updated",
            "updated_aggregates": updated_aggregates,  # 新增
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
```

**新增聚合评分计算方法**：
```python
# backend/src/service/rag_test_manager.py

def recalculate_aggregate_scores(self) -> Dict:
    """
    重新计算所有聚合评分
    
    Returns:
        包含各类聚合评分的字典
    """
    all_runs = self.list_test_runs()
    
    if not all_runs:
        return {
            "overall": {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "mrr": 0.0,
                "ndcg": 0.0,
                "total_runs": 0,
            },
            "by_config_version": {},
            "trend": [],
        }
    
    # 1. 全局平均分
    total_runs = len(all_runs)
    overall = {
        "precision": sum(r.overall_precision for r in all_runs) / total_runs,
        "recall": sum(r.overall_recall for r in all_runs) / total_runs,
        "f1": sum(r.overall_f1 for r in all_runs) / total_runs,
        "mrr": sum(r.overall_mrr for r in all_runs) / total_runs,
        "ndcg": sum(r.overall_ndcg for r in all_runs) / total_runs,
        "total_runs": total_runs,
    }
    
    # 2. 按配置版本分组统计
    by_config_version = {}
    version_runs = {}
    for run in all_runs:
        version_id = run.config_version_id or "unknown"
        if version_id not in version_runs:
            version_runs[version_id] = []
        version_runs[version_id].append(run)
    
    for version_id, runs in version_runs.items():
        count = len(runs)
        by_config_version[version_id] = {
            "precision": sum(r.overall_precision for r in runs) / count,
            "recall": sum(r.overall_recall for r in runs) / count,
            "f1": sum(r.overall_f1 for r in runs) / count,
            "mrr": sum(r.overall_mrr for r in runs) / count,
            "ndcg": sum(r.overall_ndcg for r in runs) / count,
            "run_count": count,
        }
    
    # 3. 趋势数据（按时间排序）
    sorted_runs = sorted(all_runs, key=lambda r: r.created_at)
    trend = [
        {
            "run_id": r.id,
            "name": r.name,
            "created_at": r.created_at.isoformat(),
            "precision": r.overall_precision,
            "recall": r.overall_recall,
            "f1": r.overall_f1,
            "mrr": r.overall_mrr,
            "ndcg": r.overall_ndcg,
            "passed": r.passed_test_cases,
            "total": r.total_test_cases,
        }
        for r in sorted_runs
    ]
    
    return {
        "overall": overall,
        "by_config_version": by_config_version,
        "trend": trend,
    }
```

#### 15.3.2 前端同步

**删除报告后立即刷新评分**：
```tsx
// RagEvaluationPage.tsx

const handleDeleteTestRun = async (runId: string) => {
  try {
    const result = await deleteTestRun(runId);
    
    // 1. 提示用户
    message.success('报告已删除，评分已更新');
    
    // 2. 刷新报告列表
    await loadTestRuns();
    
    // 3. 刷新聚合评分（如果有独立的评分展示组件）
    if (loadAggregateScores) {
      await loadAggregateScores();
    }
    
    // 4. 更新本地状态
    setAggregateScores(result.updated_aggregates);
    
  } catch (err) {
    message.error('删除失败');
  }
};
```

**新增聚合评分展示组件**：
```tsx
// AggregateScores.tsx

interface AggregateScoresProps {
  scores: {
    overall: {
      precision: number;
      recall: number;
      f1: number;
      mrr: number;
      ndcg: number;
      total_runs: number;
    };
    by_config_version: Record<string, any>;
    trend: Array<any>;
  };
}

const AggregateScores: React.FC<AggregateScoresProps> = ({ scores }) => {
  return (
    <Card title="聚合评分统计">
      <Row gutter={16}>
        <Col span={4}>
          <Statistic title="平均 Precision" value={scores.overall.precision} precision={3} />
        </Col>
        <Col span={4}>
          <Statistic title="平均 Recall" value={scores.overall.recall} precision={3} />
        </Col>
        <Col span={4}>
          <Statistic title="平均 F1" value={scores.overall.f1} precision={3} />
        </Col>
        <Col span={4}>
          <Statistic title="平均 MRR" value={scores.overall.mrr} precision={3} />
        </Col>
        <Col span={4}>
          <Statistic title="平均 NDCG" value={scores.overall.ndcg} precision={3} />
        </Col>
        <Col span={4}>
          <Statistic title="总运行次数" value={scores.overall.total_runs} />
        </Col>
      </Row>
      
      {/* 趋势图表 */}
      {scores.trend.length > 0 && (
        <LineChart
          data={scores.trend}
          xField="created_at"
          yField="f1"
          title="F1 分数趋势"
        />
      )}
    </Card>
  );
};
```

#### 15.3.3 评分同步流程

```
用户点击删除报告
     ↓
前端调用 DELETE /rag/test/runs/{run_id}
     ↓
后端删除 TestRun JSON 文件
     ↓
后端调用 recalculate_aggregate_scores()
     ├── 遍历所有剩余 TestRun 文件
     ├── 计算全局平均分
     ├── 按配置版本分组统计
     └── 生成趋势数据
     ↓
返回 {status, message, updated_aggregates}
     ↓
前端接收响应
     ├── 提示"报告已删除，评分已更新"
     ├── 刷新报告列表
     └── 更新聚合评分展示
```

### 15.4 未来扩展性

#### 性能优化方案
> 🔹 当前方案：全量遍历计算，适合TestRun数量<1000的场景，简单可靠无一致性问题

> 🔹 未来性能预留（当TestRun数量>1000时）：
> - **缓存机制**：增加1小时级的缓存，聚合评分计算后存入缓存，避免每次请求都全量计算
> - **增量更新**：删除/新增报告时只更新对应分数，不需要重新遍历所有报告，性能提升100倍+

```python
# 增量计算优化方案（未来实现）
def recalculate_aggregate_scores_incremental(self, deleted_run: Optional[TestRun] = None) -> Dict:
    """增量更新聚合评分"""
    # 1. 从缓存读取当前聚合评分
    aggregates = self._get_cached_aggregates()
    
    if not aggregates:
        # 缓存不存在，全量计算一次
        return self.recalculate_aggregate_scores()
    
    if deleted_run:
        # 减去被删除报告的分数
        total = aggregates["overall"]["total_runs"] - 1
        
        if total > 0:
            aggregates["overall"]["precision"] = (aggregates["overall"]["precision"] * (total + 1) - deleted_run.overall_precision) / total
            aggregates["overall"]["recall"] = (aggregates["overall"]["recall"] * (total + 1) - deleted_run.overall_recall) / total
            aggregates["overall"]["f1"] = (aggregates["overall"]["f1"] * (total + 1) - deleted_run.overall_f1) / total
            aggregates["overall"]["mrr"] = (aggregates["overall"]["mrr"] * (total + 1) - deleted_run.overall_mrr) / total
            aggregates["overall"]["ndcg"] = (aggregates["overall"]["ndcg"] * (total + 1) - deleted_run.overall_ndcg) / total
            aggregates["overall"]["total_runs"] = total
        else:
            # 所有报告都被删除，重置分数
            aggregates = self._get_empty_aggregates()
    
    # 2. 保存到缓存
    self._save_aggregates_to_cache(aggregates)
    
    return aggregates
```

### 15.5 评分同步保证

| 机制 | 说明 | 效果 |
|------|------|------|
| 删除时实时计算 | 每次删除后立即重新计算聚合评分 | 数据一致性 |
| 前端立即刷新 | 删除成功后立即更新前端展示 | 用户体验 |
| 明确反馈 | 提示"报告已删除，评分已更新" | 用户感知 |
| 趋势数据更新 | 趋势图表自动移除被删除的点 | 可视化一致性 |
| 配置版本统计更新 | 按版本分组的统计自动更新 | 版本对比准确性 |

---

**文档结束**
