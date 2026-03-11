# Agent 系统架构

本文档定义了儿童发展评估系统的 Agent 架构。系统基于 **LangGraph** 进行编排，并适时采用 **ReAct** 模式。

## 1. 系统概览

本系统是一个由专用 Agent/节点组成的有向循环图 (DAG)，负责处理用户输入并生成全面的儿童发展评估报告。

### 核心工作流
`网关 (Gateway)` -> `预处理 (Preprocessing)` -> `校验 (Validation)` -> `评估 (Assessment)` -> `检索 (Retrieval)` -> `评分 (Scoring)` -> `报告生成 (Report Generation)`

## 2. Agent 定义

### 2.0 NodePre: 预处理与上下文压缩 (Preprocessing & Context Compression)
- **角色**: 上下文窗口优化器
- **职责**: 将大规模历史数据压缩为统计特征，以降低 Token 消耗。
- **输入**: 原始 `history_context` (JSON 列表)。
- **输出**: `condensed_context` (JSON 对象)。
- **核心逻辑**:
  - **剪枝 (Pruning)**: 移除 X 个月前的详细日志。
  - **特征提取**: 计算 `weekly_avg_duration` (周平均时长), `frequency_consistency` (频率一致性), `intensity_trend` (强度趋势), `diversity_score` (多样性得分) 等。
  - **向量记忆**: 使用向量嵌入存储/检索非结构化反馈。

### 2.1 Node1: 数据校验与标准化 Agent (Data Validation & Standardization)
- **角色**: 把关人 / 输入守卫
- **职责**: 校验输入 Schema 并标准化数据格式（单位、默认值）。
- **输入**: 原始用户 JSON (`child_profile`, `proposed_plan`)。
- **输出**: `StandardizedInput` 对象或错误信息。
- **工具/库**: Pydantic, LLM (用于智能填补)。
- **逻辑**:
  - 校验必填字段（年龄、性别、问题）。
  - 统一单位（分钟、每周频次）。
  - **智能填补 (Imputation)**: 若缺失 `intensity` (强度)，根据 `activity_name` (活动名称) + `age` (年龄) 进行推断。
  - **特征工程**: 计算 `age_appropriateness` (年龄适配度), `brain_region_stimulation` (脑区刺激) 等。

### 2.2 Node2: 儿童发展评估模型 (Child Development Assessment Model)
- **角色**: 画像师
- **职责**: 将用户描述的问题映射到专业的感统维度，并对标年龄里程碑。
- **输入**: `child_profile`, `history_context`。
- **输出**: `child_state` (JSON)。
- **逻辑**:
  - **映射**: "怕高" -> `vestibular_system: deficit` (前庭觉缺陷)。
  - **对标**: 对比标准里程碑 (通过 MCP `get_age_milestones`)。
  - **结果**: 识别当前发展状态（弱项/强项/正常）。

### 2.3 Node3: 混合检索专家 (Hybrid Retrieval Expert - MCP Client)
- **角色**: 知识专家
- **职责**: 检索与计划和儿童画像相关的科学依据及知识库条目。
- **输入**: `proposed_plan`, `child_profile` (用于年龄过滤)。
- **输出**: `retrieved_docs` (结构化知识条目列表)。
- **工具**: LlamaIndex, Vector DB。
- **逻辑**:
  - **过滤**: 排除不适用于 `child_profile.age` 的知识。
  - **搜索**: 对 `activity.name` + `goals` 进行语义搜索。
  - **结构化**: 返回结构化数据（脑区、益处、风险），而非纯文本块。

### 2.4 Node4: 评分 Agent (Value Assessment)
- **角色**: 裁判 / 评估员
- **职责**: 对拟定计划进行多维度打分。
- **输入**: `proposed_plan`, `retrieved_docs`, `child_state`, `history_context`。
- **输出**: `evaluation_result` (分数, 理由, SHAP 值)。
- **逻辑**: **三层混合评分引擎**
  1.  **Level 1 (AHP)**: 基于专家规则的层次分析法 (科学性, 年龄, 安全性)。
      - *硬约束*: 若 `risk_level` 为 High -> 惩罚。
  2.  **Level 2 (ML 预测)**: (二期) 预测依从性和结果概率。
  3.  **Level 3 (融合)**: `Score = Score_AHP + P(Residual)`。
  4.  **可解释性**: 生成分数的 SHAP 类解释。

### 2.5 Node5: 报告生成 Agent (Report Generation)
- **角色**: 撰稿人 / 沟通者
- **职责**: 将所有数据综合成家长友好的 Markdown 报告。
- **输入**: 所有前序状态 (`child_profile`, `child_state`, `evaluation_result`, `retrieved_docs`)。
- **输出**: `final_report` (Markdown)。
- **Prompt 策略**:
  - 人设: 同理心强的儿童发展专家。
  - 结构: 总分 -> 科学依据 -> 预期改善 -> 调整建议。
  - 格式: 使用表格、要点和粗体以提高可读性。

### 2.6 专家反馈循环 (异步)
- **角色**: 人在回路审核员
- **职责**: 事后审查分数以微调系统。
- **动作**:
  - 标记 `Bad Case` (不良案例)。
  - 提供 `Corrected Score` (修正分)。
  - 系统更新 `Golden Dataset` (金标准数据集) 并调整 AHP 权重。

## 3. 状态管理 (LangGraph)

`AgentState` 是在节点间传递的共享内存结构。

```python
class AgentState(TypedDict):
    input_text: str
    child_profile: Dict
    child_state: Dict          # Node2 的输出
    proposed_plan: Dict        # 标准化后的计划
    condensed_context: Dict    # NodePre 的输出
    retrieved_docs: List[Dict] # Node3 的输出
    evaluation_result: Dict    # Node4 的输出
    final_report: str          # Node5 的输出
    messages: List[str]        # 对话历史
```

## 4. 交互模型

- **用户**: 提交画像 + 计划。
- **系统**: 返回包含 `final_report` 和结构化数据的 JSON 响应。
- **专家**: 异步交互以进行模型调优。
