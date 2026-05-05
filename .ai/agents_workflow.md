# Agent 系统架构

本文档定义了儿童发展评估系统的 Agent 架构。系统基于 **LangGraph** 进行编排，并适时采用 **ReAct** 模式。

## 1. 核心工作流
`网关 (Gateway)` -> `预处理 (Preprocessing)` -> `校验 (Validation)` -> `评估 (Assessment)` -> `检索 (Retrieval)` -> `评分 (Scoring)` -> `报告生成 (Report Generation)`

## 2. 状态管理 (LangGraph State)

`AgentState` 是在节点间传递的共享内存结构。

```python
class AgentState(BaseModel):
    """LangGraph 状态定义"""
    input_text: Optional[str] = None
    child_profile: ChildProfile
    proposed_plan: ProposedPlan
    child_state: Optional[ChildState] = None
    condensed_context: Optional[CondensedContext] = None
    history_context: Optional[List[HistoryRecord]] = Field(default_factory=list)
    retrieved_docs: List[KnowledgeItem] = Field(default_factory=list)
    evaluation_result: Optional[EvaluationResult] = None
    final_report: Optional[FinalReport] = None
    messages: List[Dict[str, str]] = Field(default_factory=list)
    report_prompts: Optional[List[str]] = Field(None)
    is_streaming: bool = Field(False)
```

## 3. Agent 节点定义

### 3.0 NodePre: 预处理与上下文压缩
- **角色**: 上下文窗口优化器
- **职责**: 将大规模历史数据压缩为统计特征，以降低 Token 消耗。
- **输入**: 原始 `history_context` (JSON 列表)。
- **输出**: `condensed_context` (JSON 对象)。

### 3.1 Node1: 数据校验与标准化 Agent
- **角色**: 把关人 / 输入守卫
- **职责**: 校验输入 Schema 并标准化数据格式（单位、默认值），智能填补活动强度。
- **输入**: 原始 `proposed_plan`, `child_profile`。
- **输出**: 更新后的 `proposed_plan`。

### 3.2 Node2: 儿童发展评估模型
- **角色**: 画像师
- **职责**: 将用户描述的问题映射到专业的感统维度，并对标年龄里程碑。
- **输入**: `child_profile`, `condensed_context`。
- **输出**: `child_state` (前庭觉、本体觉等维度的状态评估)。

### 3.3 Node3: 混合检索专家
- **角色**: 知识专家
- **职责**: 检索与计划和儿童画像相关的科学依据及知识库条目。
- **输入**: `child_profile`, `proposed_plan`。
- **输出**: `retrieved_docs` (结构化知识条目列表)。
- *注意：详细检索流程与RAG双流水线架构请参阅 `.ai/rag_pipeline.md` 和 `.ai/architecture.md`*

### 3.4 Node4: 评分 Agent
- **角色**: 裁判 / 评估员
- **职责**: 对拟定计划进行多维度分层打分（AHP 基准评分 + ML 模型融合）。
- **输入**: `proposed_plan`, `retrieved_docs`, `child_state`, `child_profile`。
- **输出**: `evaluation_result` (分数, 理由, SHAP 值, 维度分析, 建议)。

### 3.5 Node5: 报告生成 Agent
- **角色**: 撰稿人 / 沟通者
- **职责**: 将所有数据综合成家长友好的 Markdown 报告。
- **输入**: 所有前序状态 (`child_profile`, `proposed_plan`, `child_state`, `evaluation_result`, `retrieved_docs`, `is_streaming`)。
- **输出**: `final_report` (Markdown + 结构化数据)。支持流式输出时会额外返回 `report_prompts`。

## 4. 专家反馈循环 (未实现 - 规划中)
- **状态**: 尚未实现，当前图为纯线性 DAG，无反馈边。
- **规划职责**: 人在回路审核员，事后审查分数以微调系统。
- **规划动作**: 标记 Bad Case，提供修正分，更新金标准数据集。
