# RAG 评估页面设计方案

**文档版本**: v1.0  
**创建日期**: 2026-04-02  
**适用对象**: 前端开发、后端开发、测试工程师  
**参考文档**: 
- [`docs/rag 评估方法.md`](/Users/owen/project/ai/child-development-assessment-agent/docs/rag 评估方法.md)
- [`docs/superpowers/specs/2026-04-02-rag-evaluation-system-design.md`](/Users/owen/project/ai/child-development-assessment-agent/docs/superpowers/specs/2026-04-02-rag-evaluation-system-design.md)

---

## 📑 目录

1. [需求概述](#1-需求概述)
2. [技术选型](#2-技术选型)
3. [系统架构](#3-系统架构)
4. [后端 API 设计](#4-后端 api 设计)
5. [前端页面设计](#5-前端页面设计)
6. [数据模型设计](#6-数据模型设计)
7. [核心流程](#7-核心流程)
8. [实施步骤](#8-实施步骤)

---

## 1. 需求概述

### 1.1 核心需求

创建一个**RAG 能力评估页面**，用于全面评估 RAG 系统的检索和生成能力，包含：

**评估维度**:
- ✅ **检索能力评估**: Recall@k、MRR、NDCG 等检索质量指标
- ✅ **生成能力评估**: 忠实度、相关性、完整性等 LLM 生成质量
- ✅ **端到端评估**: 综合检索 + 生成的整体效果评分
- ✅ **对比实验**: 不同版本/配置之间的效果对比

**数据来源**: 手动标注测试集（人工标注 query + 标准答案 + 相关文档）

**展示形式**: Dashboard 仪表盘 + 详细报告列表（总览 + 详情钻取）

### 1.2 用户场景

**场景 1: 版本迭代评估**
```
开发优化了检索策略 → 运行评估 → 对比优化前后指标 → 决定是否上线
```

**场景 2: 问题诊断**
```
用户反馈检索不准 → 运行评估 → 查看失败案例 → 定位是检索问题还是生成问题
```

**场景 3: 质量监控**
```
每周定期评估 → 查看 Dashboard 趋势 → 发现指标下降 → 触发告警
```

---

## 2. 技术选型

### 2.1 后端技术栈

**核心库**:
- **RAGAS** (v0.1.0+): 业界标准 RAG 评估框架，提供 Faithfulness、Answer Relevance 等指标
- **LangChain** (v0.1.0+): LLM 调用和 Prompt 管理
- **DashScope** (阿里云): Qwen 模型，用于 LLM-as-Judge 评估

**为什么选择 RAGAS?**
- ✅ 业界标准，已被广泛采用
- ✅ 支持所有核心指标（Faithfulness、Answer Relevance、Context Recall 等）
- ✅ 开箱即用，无需重复造轮子
- ✅ 支持自定义指标扩展

### 2.2 前端技术栈

**核心库**:
- **Ant Design Charts** (v2.0+): 图表库（柱状图、折线图、雷达图）
- **Recharts** (v2.0+): 轻量级图表备选方案
- **Ant Design**: 现有 UI 组件库

**为什么选择 Ant Design Charts?**
- ✅ 与现有 Ant Design 风格一致
- ✅ 支持中文文档
- ✅ 图表类型丰富，满足 Dashboard 需求

---

## 3. 系统架构

### 3.1 整体架构图

```
┌──────────────────────────────────────────────────────────────┐
│                      RAG 评估页面                              │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 测试集管理  │  │ 评估执行    │  │ Dashboard   │          │
│  │             │  │             │  │             │          │
│  │ • 创建标注  │  │ • 选择版本  │  │ • 指标总览  │          │
│  │ • 导入导出  │  │ • 运行评估  │  │ • 趋势图表  │          │
│  │ • 版本标注  │  │ • 查看进度  │  │ • 失败案例  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                      后端 API 层                               │
├──────────────────────────────────────────────────────────────┤
│  /api/rag/evaluation/datasets      # 数据集管理              │
│  /api/rag/evaluation/run           # 执行评估                │
│  /api/rag/evaluation/results       # 获取结果                │
│  /api/rag/evaluation/compare       # 对比实验                │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                    评估引擎层                                  │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ RAGAS       │  │ 自定义评估  │  │ 指标聚合    │          │
│  │ Evaluator   │  │ Evaluator   │  │ & 报告生成  │          │
│  │             │  │             │  │             │          │
│  │ • Faithful │  │ • Context   │  │ • 综合得分  │          │
│  │ • Relevant │  │  Relevance  │  │ • 版本对比  │          │
│  │ • Recall   │  │ • Business  │  │ • 失败归因  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 模块依赖关系

```
RAGEvaluationPage (前端)
├── EvaluationDashboard (Dashboard 组件)
├── DatasetManager (数据集管理组件)
├── EvaluationRunner (评估执行组件)
├── ResultDetail (结果详情组件)
└── ComparisonView (对比视图)

RAGEvaluationController (后端)
├── RAGEvaluationService
│   ├── RAGASEvaluator (RAGAS 评估器)
│   ├── CustomEvaluator (自定义评估器)
│   └── ReportGenerator (报告生成器)
├── DatasetManager (数据集管理)
└── MetricAggregator (指标聚合器)
```

---

## 4. 后端 API 设计

### 4.1 数据集管理 API

#### 4.1.1 创建评估数据集

**接口**: `POST /api/rag/evaluation/datasets`

**请求体**:
```typescript
interface CreateEvaluationDatasetRequest {
  name: string;                    // 数据集名称
  description?: string;            // 描述
  test_cases: EvaluationTestCase[]; // 测试用例列表
}

interface EvaluationTestCase {
  query: string;                   // 用户查询
  age: number;                     // 儿童年龄
  ground_truth: string;            // 标准答案
  relevant_docs: RelevantDoc[];    // 相关文档标注
  query_type: '事实查询' | '多条件查询' | '摘要类' | '对比类' | '边缘问题';
  keywords?: string[];             // 关键词
}

interface RelevantDoc {
  doc_id: string;                  // 文档 ID
  chunk_id?: string;               // 片段 ID（可选，精确到 chunk）
  relevance_score: 0 | 1 | 2 | 3;  // 相关性评分：0-无关，1-边缘，2-弱相关，3-强相关
  reason?: string;                 // 标注理由
}
```

**响应**:
```typescript
interface EvaluationDataset {
  id: string;
  name: string;
  description: string;
  test_cases: EvaluationTestCase[];
  created_at: string;
  updated_at: string;
  created_by: string;
}
```

**实现代码位置**: `backend/src/controller/rag_evaluation_controller.py`

#### 4.1.2 获取数据集列表

**接口**: `GET /api/rag/evaluation/datasets`

**响应**:
```typescript
interface EvaluationDatasetList {
  datasets: Array<{
    id: string;
    name: string;
    description: string;
    test_case_count: number;
    created_at: string;
  }>;
}
```

**实现代码**:
```python
# backend/src/controller/rag_evaluation_controller.py
@router.get("/datasets", response_model=EvaluationDatasetList)
async def list_evaluation_datasets():
    """获取所有评估数据集"""
    datasets = rag_evaluation_service.list_datasets()
    return {
        "datasets": [
            {
                "id": ds.id,
                "name": ds.name,
                "description": ds.description,
                "test_case_count": len(ds.test_cases),
                "created_at": ds.created_at.isoformat()
            }
            for ds in datasets
        ]
    }
```

#### 4.1.3 获取单个数据集

**接口**: `GET /api/rag/evaluation/datasets/{dataset_id}`

**响应**: 返回完整的 `EvaluationDataset` 对象，包含所有测试用例

#### 4.1.4 更新数据集

**接口**: `PUT /api/rag/evaluation/datasets/{dataset_id}`

**请求体**: `UpdateEvaluationDatasetRequest` (部分字段可选)

#### 4.1.5 删除数据集

**接口**: `DELETE /api/rag/evaluation/datasets/{dataset_id}`

### 4.2 评估执行 API

#### 4.2.1 执行评估

**接口**: `POST /api/rag/evaluation/run`

**请求体**:
```typescript
interface RunEvaluationRequest {
  dataset_id: string;              // 数据集 ID
  evaluation_name?: string;        // 评估运行名称
  version_tag?: string;            // 版本标签（用于对比）
  config?: EvaluationConfig;       // 评估配置
}

interface EvaluationConfig {
  retrieval_metrics: string[];     // 检索指标：['recall@3', 'mrr', 'ndcg@5']
  generation_metrics: string[];    // 生成指标：['faithfulness', 'relevance', 'completeness']
  enable_ragas: boolean;           // 是否启用 RAGAS
  enable_custom: boolean;          // 是否启用自定义评估
  llm_model?: string;              // LLM 模型（用于 LLM-as-Judge）
}
```

**响应**:
```typescript
interface RunEvaluationResponse {
  status: 'pending' | 'running' | 'completed' | 'failed';
  run_id: string;
  message: string;
  estimated_time_seconds?: number;
}
```

**实现代码**:
```python
# backend/src/controller/rag_evaluation_controller.py
@router.post("/run", response_model=RunEvaluationResponse)
async def run_evaluation(request: RunEvaluationRequest):
    """执行 RAG 评估"""
    try:
        run_id = await rag_evaluation_service.run_evaluation(
            dataset_id=request.dataset_id,
            evaluation_name=request.evaluation_name,
            version_tag=request.version_tag,
            config=request.config
        )
        return {
            "status": "running",
            "run_id": run_id,
            "message": "评估已启动",
            "estimated_time_seconds": 60  # 根据测试集规模估算
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"评估失败：{str(e)}")
```

#### 4.2.2 获取评估进度

**接口**: `GET /api/rag/evaluation/run/{run_id}/progress`

**响应**:
```typescript
interface EvaluationProgress {
  run_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  total_cases: number;
  processed_cases: number;
  progress_percentage: number;
  current_stage?: 'retrieval' | 'generation' | 'aggregation';
  error?: string;
}
```

**实现代码**:
```python
# backend/src/service/rag_evaluation_service.py
class RAGEvaluationService:
    def get_evaluation_progress(self, run_id: str) -> EvaluationProgress:
        """获取评估进度"""
        run = self._get_run_by_id(run_id)
        if not run:
            raise ValueError(f"评估运行 {run_id} 不存在")
        
        return EvaluationProgress(
            run_id=run_id,
            status=run.status,
            total_cases=len(run.test_cases),
            processed_cases=run.processed_count,
            progress_percentage=(run.processed_count / len(run.test_cases) * 100),
            current_stage=run.current_stage,
            error=run.error_message
        )
```

### 4.3 评估结果 API

#### 4.3.1 获取评估结果

**接口**: `GET /api/rag/evaluation/run/{run_id}/results`

**响应**:
```typescript
interface EvaluationResults {
  run_id: string;
  dataset_id: string;
  version_tag: string;
  completed_at: string;
  
  // 总体指标
  overall_metrics: {
    // 检索指标
    retrieval: {
      recall_at_1: number;
      recall_at_3: number;
      recall_at_5: number;
      mrr: number;
      ndcg_at_5: number;
      context_relevance: number;  // LLM 打分，1-5 分
    };
    
    // 生成指标
    generation: {
      faithfulness: number;       // LLM 打分，1-5 分
      answer_relevance: number;   // LLM 打分，1-5 分
      completeness: number;       // LLM 打分，1-5 分
      readability: number;        // LLM 打分，1-5 分
    };
    
    // 综合得分
    composite: {
      retrieval_score: number;    // 0-100
      generation_score: number;   // 0-100
      overall_score: number;      // 0-100
    };
  };
  
  // 详细结果（每个测试用例）
  case_results: EvaluationCaseResult[];
  
  // 失败案例 Top 10
  failure_cases: Array<{
    query: string;
    failure_type: 'retrieval' | 'generation' | 'both';
    reason: string;
    score: number;
  }>;
}
```

**实现代码**:
```python
# backend/src/service/rag_evaluation_service.py
class RAGEvaluationService:
    def get_evaluation_results(self, run_id: str) -> EvaluationResults:
        """获取评估结果"""
        run = self._get_run_by_id(run_id)
        if not run or run.status != 'completed':
            raise ValueError(f"评估运行 {run_id} 未完成")
        
        # 聚合指标
        overall_metrics = self._aggregate_metrics(run.case_results)
        
        # 提取失败案例
        failure_cases = self._extract_failure_cases(run.case_results, top_k=10)
        
        return EvaluationResults(
            run_id=run_id,
            dataset_id=run.dataset_id,
            version_tag=run.version_tag,
            completed_at=run.completed_at.isoformat(),
            overall_metrics=overall_metrics,
            case_results=run.case_results,
            failure_cases=failure_cases
        )
```

#### 4.3.2 获取 Dashboard 数据

**接口**: `GET /api/rag/evaluation/dashboard`

**响应**:
```typescript
interface EvaluationDashboard {
  // 关键指标卡片
  key_metrics: {
    overall_score: number;
    retrieval_score: number;
    generation_score: number;
    total_test_cases: number;
    pass_rate: number;  // F1 > 0.7 的比例
  };
  
  // 指标趋势（最近 10 次评估）
  trends: {
    labels: string[];  // 评估时间或版本标签
    overall_scores: number[];
    retrieval_scores: number[];
    generation_scores: number[];
  };
  
  // 指标分布（直方图数据）
  distributions: {
    recall_distribution: Array<{ range: string; count: number }>;
    faithfulness_distribution: Array<{ range: string; count: number }>;
  };
  
  // 问题归因（饼图数据）
  failure_attribution: Array<{
    type: 'leak_recall' | 'low_rank' | 'hallucination' | 'irrelevant' | 'incomplete';
    count: number;
    percentage: number;
  }>;
}
```

**实现代码**:
```python
# backend/src/controller/rag_evaluation_controller.py
@router.get("/dashboard", response_model=EvaluationDashboard)
async def get_evaluation_dashboard():
    """获取评估 Dashboard 数据"""
    # 获取最近 10 次评估
    recent_runs = rag_evaluation_service.get_recent_runs(limit=10)
    
    # 计算趋势
    trends = {
        "labels": [run.version_tag or run.created_at.strftime('%m-%d') for run in recent_runs],
        "overall_scores": [run.overall_score for run in recent_runs],
        "retrieval_scores": [run.retrieval_score for run in recent_runs],
        "generation_scores": [run.generation_score for run in recent_runs],
    }
    
    # 聚合最新一次评估的 Dashboard 数据
    latest_run = recent_runs[0] if recent_runs else None
    if not latest_run:
        raise HTTPException(status_code=404, detail="暂无评估数据")
    
    dashboard_data = rag_evaluation_service.build_dashboard(latest_run)
    dashboard_data["trends"] = trends
    
    return dashboard_data
```

### 4.4 对比实验 API

#### 4.4.1 对比两次评估

**接口**: `GET /api/rag/evaluation/compare`

**查询参数**:
- `run_id1`: 第一次评估运行 ID
- `run_id2`: 第二次评估运行 ID

**响应**:
```typescript
interface EvaluationComparison {
  run1: {
    id: string;
    version_tag: string;
    overall_score: number;
    retrieval_score: number;
    generation_score: number;
  };
  run2: {
    id: string;
    version_tag: string;
    overall_score: number;
    retrieval_score: number;
    generation_score: number;
  };
  
  // 指标变化
  differences: {
    overall_score_change: number;
    retrieval_score_change: number;
    generation_score_change: number;
    recall_at_3_change: number;
    mrr_change: number;
    faithfulness_change: number;
  };
  
  // 改进/退化的测试用例
  improved_cases: Array<{
    query: string;
    score_change: number;
    improvement_reason: string;
  }>;
  
  degraded_cases: Array<{
    query: string;
    score_change: number;
    degradation_reason: string;
  }>;
}
```

**实现代码**:
```python
# backend/src/service/rag_evaluation_service.py
class RAGEvaluationService:
    def compare_evaluations(self, run_id1: str, run_id2: str) -> EvaluationComparison:
        """对比两次评估"""
        run1 = self._get_run_by_id(run_id1)
        run2 = self._get_run_by_id(run_id2)
        
        if not run1 or not run2:
            raise ValueError("评估运行不存在")
        
        # 计算指标变化
        differences = {
            "overall_score_change": run2.overall_score - run1.overall_score,
            "retrieval_score_change": run2.retrieval_score - run1.retrieval_score,
            "generation_score_change": run2.generation_score - run1.generation_score,
            "recall_at_3_change": run2.recall_at_3 - run1.recall_at_3,
            "mrr_change": run2.mrr - run1.mrr,
            "faithfulness_change": run2.faithfulness - run1.faithfulness,
        }
        
        # 找出改进和退化的案例
        improved_cases = []
        degraded_cases = []
        
        for case1, case2 in zip(run1.case_results, run2.case_results):
            score_change = case2.total_score - case1.total_score
            if score_change > 0.1:  # 阈值
                improved_cases.append({
                    "query": case1.query,
                    "score_change": score_change,
                    "improvement_reason": self._analyze_improvement(case1, case2)
                })
            elif score_change < -0.1:
                degraded_cases.append({
                    "query": case1.query,
                    "score_change": score_change,
                    "degradation_reason": self._analyze_degradation(case1, case2)
                })
        
        return EvaluationComparison(
            run1={...},
            run2={...},
            differences=differences,
            improved_cases=improved_cases[:10],  # Top 10
            degraded_cases=degraded_cases[:10]
        )
```

---

## 5. 前端页面设计

### 5.1 页面结构

**文件路径**: `frontend/src/pages/RAGEvaluationPage.tsx`

**页面布局**:
```
┌─────────────────────────────────────────────────────────────┐
│  RAG 能力评估                                    [新建评估]   │
├─────────────────────────────────────────────────────────────┤
│  [概览] [数据集管理] [评估历史] [对比实验]                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ● 概览 Tab: Dashboard 仪表盘                                │
│    - 关键指标卡片（整体得分、检索得分、生成得分）             │
│    - 趋势图表（折线图）                                      │
│    - 指标分布（直方图）                                      │
│    - 失败案例 Top 10（表格）                                 │
│                                                             │
│  ● 数据集管理 Tab: 测试集列表 + 创建/编辑                     │
│    - 数据集列表（表格）                                      │
│    - 创建数据集（表单）                                      │
│    - 导入/导出（按钮）                                       │
│                                                             │
│  ● 评估历史 Tab: 历次评估结果                                │
│    - 评估运行列表（表格）                                    │
│    - 结果详情（弹窗/抽屉）                                   │
│                                                             │
│  ● 对比实验 Tab: 选择两次评估进行对比                        │
│    - 选择 run1 和 run2（下拉框）                              │
│    - 对比结果（对比表格 + 差异高亮）                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 核心组件设计

#### 5.2.1 Dashboard 组件

**文件路径**: `frontend/src/components/evaluation/EvaluationDashboard.tsx`

**组件结构**:
```typescript
interface EvaluationDashboardProps {
  datasetId?: string;  // 可选，筛选特定数据集
}

const EvaluationDashboard: React.FC<EvaluationDashboardProps> = ({ datasetId }) => {
  const { data, loading } = useEvaluationDashboard(datasetId);
  
  return (
    <div>
      {/* 关键指标卡片 */}
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic 
              title="整体得分" 
              value={data.key_metrics.overall_score} 
              suffix="分"
              precision={2}
              valueStyle={{ color: getColorByScore(data.key_metrics.overall_score) }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="检索得分" 
              value={data.key_metrics.retrieval_score} 
              suffix="分"
              precision={2}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="生成得分" 
              value={data.key_metrics.generation_score} 
              suffix="分"
              precision={2}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="通过率" 
              value={data.key_metrics.pass_rate * 100} 
              suffix="%"
              precision={1}
            />
          </Card>
        </Col>
      </Row>
      
      {/* 趋势图表 */}
      <Card title="指标趋势" style={{ marginTop: 24 }}>
        <LineChart data={data.trends} />
      </Card>
      
      {/* 指标分布 */}
      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={12}>
          <Card title="Recall@3 分布">
            <Histogram data={data.distributions.recall_distribution} />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="忠实度分布">
            <Histogram data={data.distributions.faithfulness_distribution} />
          </Card>
        </Col>
      </Row>
      
      {/* 问题归因 */}
      <Card title="失败原因分析" style={{ marginTop: 24 }}>
        <PieChart data={data.failure_attribution} />
      </Card>
      
      {/* 失败案例 Top 10 */}
      <Card title="失败案例 Top 10" style={{ marginTop: 24 }}>
        <Table 
          dataSource={data.failure_cases}
          columns={[
            { title: '查询', dataIndex: 'query', key: 'query' },
            { title: '失败类型', dataIndex: 'failure_type', key: 'failure_type' },
            { title: '得分', dataIndex: 'score', key: 'score' },
            { title: '原因', dataIndex: 'reason', key: 'reason' },
          ]}
        />
      </Card>
    </div>
  );
};
```

#### 5.2.2 数据集管理组件

**文件路径**: `frontend/src/components/evaluation/DatasetManager.tsx`

**核心功能**:
- 数据集列表展示
- 创建/编辑数据集（表单）
- 导入/导出数据集（JSON 文件）

**创建数据集表单**:
```typescript
interface CreateDatasetForm {
  name: string;
  description?: string;
  test_cases: Array<{
    query: string;
    age: number;
    ground_truth: string;
    relevant_docs: Array<{
      doc_id: string;
      relevance_score: number;
      reason?: string;
    }>;
    query_type: string;
    keywords?: string[];
  }>;
}

const CreateDatasetModal: React.FC<{ visible: boolean; onClose: () => void }> = ({ visible, onClose }) => {
  const [form] = Form.useForm();
  
  return (
    <Modal
      title="创建评估数据集"
      open={visible}
      onCancel={onClose}
      width={1000}
      footer={[
        <Button onClick={onClose}>取消</Button>,
        <Button type="primary" onClick={() => form.submit()}>创建</Button>
      ]}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="数据集名称" rules={[{ required: true }]}>
          <Input placeholder="例如：儿童发展评估测试集 v1.0" />
        </Form.Item>
        
        <Form.Item name="description" label="描述">
          <TextArea rows={2} placeholder="数据集的说明信息" />
        </Form.Item>
        
        <Form.List name="test_cases">
          {(fields, { add, remove }) => (
            <div>
              <div style={{ marginBottom: 16 }}>
                <Button type="dashed" onClick={() => add()} block>
                  + 添加测试用例
                </Button>
              </div>
              
              {fields.map(field => (
                <Card 
                  key={field.key} 
                  size="small" 
                  title={`测试用例 ${field.name + 1}`}
                  style={{ marginBottom: 16 }}
                  extra={<Button type="link" danger onClick={() => remove(field.name)}>删除</Button>}
                >
                  <Form.Item label="查询内容" required>
                    <Input.TextArea rows={2} placeholder="用户可能提出的问题" />
                  </Form.Item>
                  
                  <Form.Item label="儿童年龄" required>
                    <InputNumber min={0} max={18} />
                  </Form.Item>
                  
                  <Form.Item label="标准答案" required>
                    <Input.TextArea rows={3} placeholder="期望的标准答案" />
                  </Form.Item>
                  
                  <Form.Item label="相关文档标注" required>
                    {/* 文档选择器，支持搜索和选择 */}
                    <DocSelector multiple />
                  </Form.Item>
                  
                  <Form.Item label="问题类型" required>
                    <Select>
                      <Select.Option value="事实查询">事实查询</Select.Option>
                      <Select.Option value="多条件查询">多条件查询</Select.Option>
                      {/* ...其他类型 */}
                    </Select>
                  </Form.Item>
                </Card>
              ))}
            </div>
          )}
        </Form.List>
      </Form>
    </Modal>
  );
};
```

#### 5.2.3 评估执行组件

**文件路径**: `frontend/src/components/evaluation/EvaluationRunner.tsx`

**核心功能**:
- 选择数据集
- 配置评估参数
- 启动评估
- 实时进度展示

**组件结构**:
```typescript
const EvaluationRunner: React.FC = () => {
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<EvaluationProgress | null>(null);
  
  const handleRunEvaluation = async (config: RunEvaluationRequest) => {
    setRunning(true);
    const { run_id } = await runEvaluation(config);
    
    // 轮询进度
    const interval = setInterval(async () => {
      const progressData = await getEvaluationProgress(run_id);
      setProgress(progressData);
      
      if (progressData.status === 'completed' || progressData.status === 'failed') {
        clearInterval(interval);
        setRunning(false);
        message.success('评估完成');
      }
    }, 2000);
  };
  
  return (
    <Card title="执行评估">
      <Form layout="vertical">
        <Form.Item label="选择数据集" required>
          <Select placeholder="请选择评估数据集" />
        </Form.Item>
        
        <Form.Item label="版本标签" required>
          <Input placeholder="例如：v1.2.0-optimization" />
        </Form.Item>
        
        <Form.Item label="评估指标" required>
          <Checkbox.Group>
            <Checkbox value="recall@3">Recall@3</Checkbox>
            <Checkbox value="mrr">MRR</Checkbox>
            <Checkbox value="ndcg@5">NDCG@5</Checkbox>
            <Checkbox value="faithfulness">忠实度</Checkbox>
            <Checkbox value="relevance">相关性</Checkbox>
            <Checkbox value="completeness">完整性</Checkbox>
          </Checkbox.Group>
        </Form.Item>
        
        <Form.Item>
          <Button 
            type="primary" 
            onClick={handleRunEvaluation}
            loading={running}
          >
            开始评估
          </Button>
        </Form.Item>
      </Form>
      
      {/* 进度展示 */}
      {progress && (
        <div style={{ marginTop: 24 }}>
          <Progress 
            percent={progress.progress_percentage} 
            status={progress.status === 'failed' ? 'exception' : 'active'}
          />
          <Text>
            当前阶段：{progress.current_stage} | 
            进度：{progress.processed_cases}/{progress.total_cases}
          </Text>
        </div>
      )}
    </Card>
  );
};
```

#### 5.2.4 结果详情组件

**文件路径**: `frontend/src/components/evaluation/ResultDetail.tsx`

**展示内容**:
- 总体指标卡片
- 每个测试用例的详细得分
- 检索结果和生成结果的对比
- LLM 评估理由

### 5.3 路由配置

**文件路径**: `frontend/src/router/index.tsx`

**新增路由**:
```typescript
const routes: RouteObject[] = [
  // ...现有路由
  {
    path: '/evaluation',
    element: <RAGEvaluationPage />,
    children: [
      { index: true, element: <EvaluationDashboard /> },
      { path: 'datasets', element: <DatasetManager /> },
      { path: 'history', element: <EvaluationHistory /> },
      { path: 'compare', element: <ComparisonView /> },
    ]
  }
];
```

---

## 6. 数据模型设计

### 6.1 后端数据模型

**文件路径**: `backend/src/model/rag_evaluation.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum

class RelevanceScore(int, Enum):
    """相关性评分"""
    IRRELEVANT = 0  # 无关
    MARGINAL = 1    # 边缘
    WEAK = 2        # 弱相关
    STRONG = 3      # 强相关

class QueryType(str, Enum):
    """问题类型"""
    FACTUAL = "事实查询"
    MULTI_CONDITION = "多条件查询"
    SUMMARY = "摘要类"
    COMPARISON = "对比类"
    EDGE_CASE = "边缘问题"

class RelevantDoc(BaseModel):
    """相关文档标注"""
    doc_id: str
    chunk_id: Optional[str] = None
    relevance_score: RelevanceScore
    reason: Optional[str] = None

class EvaluationTestCase(BaseModel):
    """评估测试用例"""
    query: str
    age: int
    ground_truth: str
    relevant_docs: List[RelevantDoc]
    query_type: QueryType
    keywords: List[str] = Field(default_factory=list)

class EvaluationDataset(BaseModel):
    """评估数据集"""
    id: str = Field(default_factory=lambda: f"eval_ds_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    name: str
    description: str = ""
    test_cases: List[EvaluationTestCase]
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = ""

class EvaluationRunStatus(str, Enum):
    """评估运行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class EvaluationStage(str, Enum):
    """评估阶段"""
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    AGGREGATION = "aggregation"

class EvaluationCaseResult(BaseModel):
    """单个测试用例的评估结果"""
    test_case_id: str
    query: str
    
    # 检索指标
    recall_at_3: float
    mrr: float
    ndcg_at_5: float
    context_relevance: float  # LLM 打分，1-5 分
    
    # 生成指标
    faithfulness: float       # LLM 打分，1-5 分
    answer_relevance: float   # LLM 打分，1-5 分
    completeness: float       # LLM 打分，1-5 分
    readability: float        # LLM 打分，1-5 分
    
    # 综合得分
    retrieval_score: float    # 0-100
    generation_score: float   # 0-100
    total_score: float        # 0-100
    
    # 失败分析
    failure_type: Optional[str] = None  # 'leak_recall', 'low_rank', 'hallucination', etc.
    failure_reason: Optional[str] = None

class EvaluationRun(BaseModel):
    """评估运行记录"""
    id: str = Field(default_factory=lambda: f"eval_run_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    dataset_id: str
    version_tag: str = ""
    evaluation_name: str = ""
    
    status: EvaluationRunStatus = EvaluationRunStatus.PENDING
    current_stage: Optional[EvaluationStage] = None
    
    total_cases: int = 0
    processed_count: int = 0
    
    case_results: List[EvaluationCaseResult] = Field(default_factory=list)
    
    # 总体指标
    overall_score: float = 0.0
    retrieval_score: float = 0.0
    generation_score: float = 0.0
    
    recall_at_3: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    faithfulness: float = 0.0
    
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
```

### 6.2 前端 TypeScript 类型

**文件路径**: `frontend/src/models/evaluation.ts`

```typescript
export interface EvaluationTestCase {
  query: string;
  age: number;
  ground_truth: string;
  relevant_docs: Array<{
    doc_id: string;
    chunk_id?: string;
    relevance_score: 0 | 1 | 2 | 3;
    reason?: string;
  }>;
  query_type: '事实查询' | '多条件查询' | '摘要类' | '对比类' | '边缘问题';
  keywords?: string[];
}

export interface EvaluationDataset {
  id: string;
  name: string;
  description: string;
  test_cases: EvaluationTestCase[];
  created_at: string;
  updated_at: string;
  created_by: string;
}

export interface EvaluationCaseResult {
  test_case_id: string;
  query: string;
  
  // 检索指标
  recall_at_3: number;
  mrr: number;
  ndcg_at_5: number;
  context_relevance: number;
  
  // 生成指标
  faithfulness: number;
  answer_relevance: number;
  completeness: number;
  readability: number;
  
  // 综合得分
  retrieval_score: number;
  generation_score: number;
  total_score: number;
  
  // 失败分析
  failure_type?: string;
  failure_reason?: string;
}

export interface EvaluationResults {
  run_id: string;
  dataset_id: string;
  version_tag: string;
  completed_at: string;
  
  overall_metrics: {
    retrieval: {
      recall_at_1: number;
      recall_at_3: number;
      recall_at_5: number;
      mrr: number;
      ndcg_at_5: number;
      context_relevance: number;
    };
    generation: {
      faithfulness: number;
      answer_relevance: number;
      completeness: number;
      readability: number;
    };
    composite: {
      retrieval_score: number;
      generation_score: number;
      overall_score: number;
    };
  };
  
  case_results: EvaluationCaseResult[];
  failure_cases: Array<{
    query: string;
    failure_type: 'retrieval' | 'generation' | 'both';
    reason: string;
    score: number;
  }>;
}
```

---

## 7. 核心流程

### 7.1 评估执行流程

```
1. 用户在前端选择数据集和配置
   ↓
2. 前端调用 POST /api/rag/evaluation/run
   ↓
3. 后端创建 EvaluationRun 记录，状态设为 'running'
   ↓
4. 评估引擎异步执行：
   4.1 对每个测试用例执行检索
   4.2 计算检索指标（Recall@k, MRR, NDCG）
   4.3 执行 LLM 生成（可选，如果需要评估生成）
   4.4 使用 RAGAS 计算生成指标（Faithfulness, Relevance 等）
   4.5 聚合指标，计算综合得分
   4.6 更新 EvaluationRun 记录
   ↓
5. 前端轮询进度接口
   ↓
6. 评估完成，前端展示结果
```

**后端实现代码**:
```python
# backend/src/service/rag_evaluation_service.py
class RAGEvaluationService:
    async def run_evaluation(
        self,
        dataset_id: str,
        evaluation_name: str = "",
        version_tag: str = "",
        config: Optional[EvaluationConfig] = None
    ) -> str:
        """执行评估"""
        # 1. 加载数据集
        dataset = self._get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"数据集 {dataset_id} 不存在")
        
        # 2. 创建评估运行记录
        run = EvaluationRun(
            dataset_id=dataset_id,
            evaluation_name=evaluation_name,
            version_tag=version_tag,
            total_cases=len(dataset.test_cases)
        )
        self._save_run(run)
        
        # 3. 异步执行评估
        asyncio.create_task(self._execute_evaluation(run, dataset, config))
        
        return run.id
    
    async def _execute_evaluation(
        self,
        run: EvaluationRun,
        dataset: EvaluationDataset,
        config: Optional[EvaluationConfig]
    ):
        """执行评估（后台任务）"""
        try:
            run.status = EvaluationRunStatus.RUNNING
            run.current_stage = EvaluationStage.RETRIEVAL
            
            case_results = []
            
            for i, test_case in enumerate(dataset.test_cases):
                # 4.1 执行检索
                retrieval_results = await self._retrieve(
                    query=test_case.query,
                    age=test_case.age,
                    limit=10
                )
                
                # 4.2 计算检索指标
                retrieval_metrics = self._calculate_retrieval_metrics(
                    retrieved_docs=[r.id for r in retrieval_results],
                    relevant_docs=[d.doc_id for d in test_case.relevant_docs]
                )
                
                # 4.3 执行 LLM 生成（如果需要）
                if config and config.enable_generation:
                    generated_answer = await self._generate_answer(
                        query=test_case.query,
                        context=[r.content for r in retrieval_results]
                    )
                    
                    # 4.4 使用 RAGAS 计算生成指标
                    if config.enable_ragas:
                        generation_metrics = await self._ragas_evaluate(
                            query=test_case.query,
                            context=[r.content for r in retrieval_results],
                            answer=generated_answer,
                            ground_truth=test_case.ground_truth
                        )
                    else:
                        generation_metrics = await self._custom_evaluate(
                            query=test_case.query,
                            context=[r.content for r in retrieval_results],
                            answer=generated_answer
                        )
                else:
                    generation_metrics = {}
                
                # 4.5 聚合指标
                case_result = self._aggregate_case_result(
                    retrieval_metrics=retrieval_metrics,
                    generation_metrics=generation_metrics
                )
                
                case_results.append(case_result)
                run.processed_count = i + 1
                
                # 定期持久化
                if (i + 1) % 10 == 0:
                    self._save_run(run)
            
            # 5. 更新运行记录
            run.case_results = case_results
            run.status = EvaluationRunStatus.COMPLETED
            run.completed_at = datetime.now()
            
            # 计算总体指标
            self._calculate_overall_metrics(run)
            
            self._save_run(run)
            
        except Exception as e:
            run.status = EvaluationRunStatus.FAILED
            run.error_message = str(e)
            self._save_run(run)
```

### 7.2 RAGAS 集成代码

**文件路径**: `backend/src/core/ragas_evaluator.py`

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevance,
    context_recall,
    context_precision,
    context_relevancy,
)
from datasets import Dataset

class RAGASEvaluator:
    """RAGAS 评估器"""
    
    def __init__(self, llm_model: str = "qwen-turbo", api_key: str = ""):
        """
        初始化 RAGAS 评估器
        
        Args:
            llm_model: LLM 模型名称
            api_key: API 密钥
        """
        from llama_index.llms.dashscope import DashScope
        
        self.llm = DashScope(model=llm_model, api_key=api_key)
    
    async def evaluate(
        self,
        query: str,
        context: List[str],
        answer: str,
        ground_truth: str
    ) -> Dict[str, float]:
        """
        使用 RAGAS 评估单个测试用例
        
        Returns:
            各项指标得分
        """
        # 构建 RAGAS 数据集
        dataset = Dataset.from_list([
            {
                "question": query,
                "contexts": [context],  # RAGAS 期望 contexts 是列表
                "answer": answer,
                "ground_truth": ground_truth
            }
        ])
        
        # 执行评估
        result = evaluate(
            dataset,
            metrics=[
                faithfulness,
                answer_relevance,
                context_recall,
                context_precision,
            ],
            llm=self.llm
        )
        
        # 提取分数
        scores = result.to_pandas().iloc[0]
        
        return {
            "faithfulness": scores["faithfulness"],
            "answer_relevance": scores["answer_relevance"],
            "context_recall": scores["context_recall"],
            "context_precision": scores["context_precision"],
        }
    
    async def evaluate_batch(
        self,
        test_cases: List[Dict]
    ) -> Dict[str, float]:
        """
        批量评估
        
        Args:
            test_cases: 测试用例列表，每个包含 query, context, answer, ground_truth
        
        Returns:
            平均指标得分
        """
        dataset = Dataset.from_list([
            {
                "question": case["query"],
                "contexts": [case["context"]],
                "answer": case["answer"],
                "ground_truth": case["ground_truth"]
            }
            for case in test_cases
        ])
        
        result = evaluate(
            dataset,
            metrics=[
                faithfulness,
                answer_relevance,
                context_recall,
                context_precision,
            ],
            llm=self.llm
        )
        
        # 计算平均分数
        df = result.to_pandas()
        
        return {
            "faithfulness": df["faithfulness"].mean(),
            "answer_relevance": df["answer_relevance"].mean(),
            "context_recall": df["context_recall"].mean(),
            "context_precision": df["context_precision"].mean(),
        }
```

### 7.3 自定义评估器代码

**文件路径**: `backend/src/core/custom_evaluator.py`

```python
class CustomRAGEvaluator:
    """自定义 RAG 评估器（LLM-as-Judge）"""
    
    def __init__(self, llm_model: str = "qwen-turbo", api_key: str = ""):
        from llama_index.llms.dashscope import DashScope
        self.llm = DashScope(model=llm_model, api_key=api_key)
    
    async def evaluate_faithfulness(
        self,
        context: str,
        answer: str
    ) -> float:
        """
        评估忠实度（是否基于上下文，无幻觉）
        
        Returns:
            1-5 分
        """
        prompt = f"""
你是 RAG 系统专业评估员，请评估以下回答的忠实度：

【检索上下文】
{context}

【模型回答】
{answer}

请打分（1-5 分）：
5 分：完全基于上下文，无任何编造
4 分：基本基于上下文，轻微表述差异
3 分：部分内容基于上下文，部分编造
2 分：大部分内容编造
1 分：完全编造，与上下文无关

仅输出分数（1-5 之间的数字），不要其他内容。
"""
        
        response = await self.llm.acomplete(prompt)
        score = int(response.text.strip())
        return min(5, max(1, score))
    
    async def evaluate_relevance(
        self,
        query: str,
        answer: str
    ) -> float:
        """
        评估回答相关性
        
        Returns:
            1-5 分
        """
        prompt = f"""
你是 RAG 系统专业评估员，请评估以下回答的相关性：

【用户问题】
{query}

【模型回答】
{answer}

请打分（1-5 分）：
5 分：直接精准回答问题
4 分：基本回答问题，略有冗余
3 分：部分相关，部分跑题
2 分：大部分跑题
1 分：完全答非所问

仅输出分数（1-5 之间的数字），不要其他内容。
"""
        
        response = await self.llm.acomplete(prompt)
        score = int(response.text.strip())
        return min(5, max(1, score))
    
    async def evaluate_completeness(
        self,
        query: str,
        answer: str,
        ground_truth: str
    ) -> float:
        """
        评估回答完整性
        
        Returns:
            1-5 分
        """
        prompt = f"""
你是 RAG 系统专业评估员，请评估以下回答的完整性：

【用户问题】
{query}

【标准答案】
{ground_truth}

【模型回答】
{answer}

请打分（1-5 分）：
5 分：覆盖标准答案所有关键信息点
4 分：覆盖大部分关键信息点
3 分：覆盖部分关键信息点
2 分：仅覆盖少量关键信息点
1 分：未覆盖任何关键信息点

仅输出分数（1-5 之间的数字），不要其他内容。
"""
        
        response = await self.llm.acomplete(prompt)
        score = int(response.text.strip())
        return min(5, max(1, score))
```

---

## 8. 实施步骤

### 8.1 第一阶段：后端基础（2-3 天）

**Day 1: 数据模型和服务层**
- [ ] 创建 `backend/src/model/rag_evaluation.py` - 数据模型定义
- [ ] 创建 `backend/src/service/rag_evaluation_service.py` - 评估服务
- [ ] 创建 `backend/src/core/ragas_evaluator.py` - RAGAS 评估器
- [ ] 创建 `backend/src/core/custom_evaluator.py` - 自定义评估器

**Day 2: API 控制器**
- [ ] 创建 `backend/src/controller/rag_evaluation_controller.py` - API 路由
- [ ] 实现数据集管理 API（CRUD）
- [ ] 实现评估执行 API
- [ ] 实现评估结果 API

**Day 3: 测试和调试**
- [ ] 编写单元测试
- [ ] 手动测试 API
- [ ] 修复 bug

### 8.2 第二阶段：前端页面（2-3 天）

**Day 1: 基础组件**
- [ ] 创建 `frontend/src/pages/RAGEvaluationPage.tsx` - 主页面
- [ ] 创建 `frontend/src/components/evaluation/EvaluationDashboard.tsx` - Dashboard
- [ ] 创建 `frontend/src/components/evaluation/DatasetManager.tsx` - 数据集管理
- [ ] 添加路由配置

**Day 2: 功能组件**
- [ ] 创建 `frontend/src/components/evaluation/EvaluationRunner.tsx` - 评估执行
- [ ] 创建 `frontend/src/components/evaluation/ResultDetail.tsx` - 结果详情
- [ ] 创建 `frontend/src/components/evaluation/ComparisonView.tsx` - 对比视图
- [ ] 集成 Ant Design Charts

**Day 3: API 集成和测试**
- [ ] 创建 `frontend/src/api/evaluation.ts` - API 客户端
- [ ] 集成后端 API
- [ ] 测试和调试

### 8.3 第三阶段：优化和文档（1-2 天）

**Day 1: 性能优化**
- [ ] 评估任务异步化
- [ ] 进度轮询优化
- [ ] 大数据集分页加载

**Day 2: 文档和培训**
- [ ] 编写 API 文档
- [ ] 编写用户使用指南
- [ ] 团队培训

---

## 附录

### A. 依赖安装

**后端**:
```bash
cd backend
poetry add ragas langchain llama-index-dashscope
```

**前端**:
```bash
cd frontend
npm install @ant-design/charts
```

### B. 环境变量配置

```bash
# .env 文件
DASHSCOPE_API_KEY=your_api_key
RAG_EVALUATION_ENABLED=true
RAG_EVALUATION_DEFAULT_MODEL=qwen-turbo
```

### C. 相关文件索引

- 后端模型：`backend/src/model/rag_evaluation.py`
- 后端服务：`backend/src/service/rag_evaluation_service.py`
- 后端控制器：`backend/src/controller/rag_evaluation_controller.py`
- RAGAS 评估器：`backend/src/core/ragas_evaluator.py`
- 自定义评估器：`backend/src/core/custom_evaluator.py`
- 前端页面：`frontend/src/pages/RAGEvaluationPage.tsx`
- 前端 API: `frontend/src/api/evaluation.ts`

---

## 总结

本方案设计了一个**完整的 RAG 能力评估页面**，采用业界通用的 RAGAS 框架，避免重复造轮子，包含：

✅ **检索能力评估**: Recall@k、MRR、NDCG 等标准指标  
✅ **生成能力评估**: Faithfulness、Relevance、Completeness（RAGAS + 自定义）  
✅ **端到端评估**: 综合得分 + 失败归因  
✅ **对比实验**: 版本间效果对比  
✅ **Dashboard**: 可视化指标展示  
✅ **数据集管理**: 手动标注测试集管理  

**下一步**: 等待方案确认后，创建详细的实施计划文档。
