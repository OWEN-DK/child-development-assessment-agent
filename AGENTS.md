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
  - **特征提取**:
    - `weekly_avg_duration`: 计算周平均时长。
    - `frequency_consistency`: 基于变异系数 (CV) 计算频率一致性。
    - `intensity_trend`: 对比前后半段数据判断强度趋势 (rising/falling/stable)。
    - `diversity_score`: 计算活动种类的多样性占比。
  - **关键反馈提取**: 提取最近 3 条记录的反馈和备注。
  - *注意*: 当前版本暂未包含向量记忆功能，仅做统计压缩。

### 2.1 Node1: 数据校验与标准化 Agent (Data Validation & Standardization)
- **角色**: 把关人 / 输入守卫
- **职责**: 校验输入 Schema 并标准化数据格式（单位、默认值）。
- **输入**: 原始 `proposed_plan` (拟定计划), `child_profile` (儿童画像)。
- **输出**: 更新后的 `proposed_plan`。
- **工具/库**: Pydantic (基础类型校验), LLM (qwen-plus, 用于智能填补)。
- **逻辑**:
  - **智能填补 (Intensity Imputation)**:
    1.  优先匹配本地规则库 (如 "drawing" -> "low", "running" -> "high")。
    2.  若未命中，调用 LLM 根据活动名称和儿童年龄推断强度。
  - *注意*: 年龄适配度和脑区刺激分析已移至评分节点或后续流程处理。

### 2.2 Node2: 儿童发展评估模型 (Child Development Assessment Model)
- **角色**: 画像师
- **职责**: 将用户描述的问题映射到专业的感统维度，并对标年龄里程碑。
- **输入**: `child_profile`, `condensed_context`。
- **输出**: `child_state` (包含前庭觉、本体觉等维度的状态评估)。
- **工具/库**: LLM (qwen-plus)。
- **逻辑**:
  - **里程碑对比**: 使用内置的年龄里程碑数据 (`_get_age_milestones`) 作为评估参照。
  - **综合评估**: 结合儿童画像和历史运动特征（如有），生成包含各感统维度（等级 1-5）和综合评价的结构化数据。
  - **异常处理**: 若 JSON 解析失败，具备自动修复机制；若 LLM 不可用，返回默认兜底评估。

### 2.3 Node3: 混合检索专家 (Hybrid Retrieval Expert)
- **角色**: 知识专家
- **职责**: 检索与计划和儿童画像相关的科学依据及知识库条目。
- **输入**: `child_profile` (Issues), `proposed_plan` (Goals)。
- **输出**: `retrieved_docs` (结构化知识条目列表)。
- **核心架构**: 采用 **BM25关键词检索 + 向量语义检索** 混合架构。
- **文档导入流程**:
  1. **去重校验**: 基于文件MD5哈希自动去重。
  2. **智能解析**: 支持 PDF/EPUB，自动识别扫描版 PDF 并调用 OCR。
  3. **语义分块**: 1024 字符分块，20 字符重叠。
  4. **元数据提取**: LLM 自动提取脑区、主题、益处、年龄范围等。
- **检索逻辑**:
  - 根据 `issues` 和 `goals` 构造查询。
  - 调用 `rag_service` 执行混合检索 (BM25 + Vector)。
  - 返回 Top K 相关文档。

### 2.4 Node4: 评分 Agent (Value Assessment)
- **角色**: 裁判 / 评估员
- **职责**: 对拟定计划进行多维度打分。
- **输入**: `proposed_plan`, `retrieved_docs`, `child_state`, `child_profile`。
- **输出**: `evaluation_result` (分数, 理由, SHAP 值, 维度分析, 建议)。
- **逻辑**: **分层评分引擎**
  1.  **Level 1 (AHP 基准评分 - 已实现)**:
      - **科学性 (40%)**: 基于 RAG 文档的相关性和对家长主诉问题的覆盖率。
      - **年龄适配度 (30%)**: 检查周总时长、单次时长是否符合年龄建议。
      - **安全性 (30%)**: 检查高风险活动与年龄的匹配度，以及 RAG 检索到的风险提示；结合 `child_state` (如前庭觉缺陷) 进行个性化扣分。
  2.  **Level 2 & 3 (ML 预测与融合 - 规划中)**: 暂未实现，目前直接输出 AHP 分数。
  3.  **输出**: 生成详细的维度分析 (`DimensionAnalysis`) 和改进建议 (`suggestions`)。

### 2.5 Node5: 报告生成 Agent (Report Generation)
- **角色**: 撰稿人 / 沟通者
- **职责**: 将所有数据综合成家长友好的 Markdown 报告。
- **输入**: 所有前序状态 (`child_profile`, `child_state`, `evaluation_result`, `retrieved_docs`)。
- **输出**: `final_report` (Markdown + 结构化数据)。
- **逻辑**:
  - **数据准备**: 整理雷达图数据、科学依据列表、算法分析详情。
  - **流式支持**: 若 `is_streaming` 为 True，返回 Prompts 供上层流式调用。
  - **报告生成**: 调用 LLM (qwen-plus) 生成 Markdown 报告。
  - **兜底机制**: 若 LLM 调用失败，生成基础的降级报告。

### 2.6 专家反馈循环 (异步 - 规划中)
- **角色**: 人在回路审核员
- **职责**: 事后审查分数以微调系统。
- **动作**: 标记 Bad Case，提供修正分，更新金标准数据集。

## 3. 状态管理 (LangGraph)

`AgentState` 是在节点间传递的共享内存结构。

```python
class AgentState(BaseModel):
    """LangGraph 状态定义"""

    input_text: Optional[str] = None
    child_profile: ChildProfile
    proposed_plan: ProposedPlan
    child_state: Optional[ChildState] = None
    condensed_context: Optional[CondensedContext] = None
    history_context: Optional[List[HistoryRecord]] = Field(
        default_factory=list, description="原始历史记录"
    )
    retrieved_docs: List[KnowledgeItem] = Field(default_factory=list)
    evaluation_result: Optional[EvaluationResult] = None
    final_report: Optional[FinalReport] = None
    messages: List[Dict[str, str]] = Field(default_factory=list, description="对话历史")
    report_prompts: Optional[List[str]] = Field(None, description="用于流式生成的 Prompt 列表")
    is_streaming: bool = Field(False, description="是否启用流式输出")
```

## 4. 交互模型

- **用户**: 提交画像 (`child_profile`) + 计划 (`proposed_plan`) + 可选历史 (`history_context`)。
- **系统**: 返回包含 `final_report` (Markdown) 和结构化数据 (雷达图、分数) 的 JSON 响应。
