# 儿童运动评估系统实现方案

本方案基于 **LangGraph** 进行流程编排，采用 **ReAct** 架构模式，整合 **LangChain** 与 **LlamaIndex** 的优势，实现从用户输入到专业评估报告生成的全自动化流程。

## 1. 系统架构概览

系统采用多 Agent 协作模式，通过 LangGraph 管理全局状态（State），各节点（Node）各司其职，形成一条清晰的数据处理流水线。

### 核心流程图
```mermaid
graph TD
    User[用户/家长] --> UI[React Frontend]
    UI --> |REST API (HTTP POST)| Gateway[FastAPI 网关]
    Gateway --> NodePre[预处理与上下文压缩]
    NodePre --> Node1[数据校验与标准化]
    
    %% 书籍上传与知识库更新
    UI -.-> |Upload File (PDF/EPUB)| Gateway
    Gateway -.-> |Trigger Async ETL| Node3
    
    Node1 --> Node2[儿童发展评估模型]
    Node2 --> Node3[混合检索专家]
    Node3 --> Node4[价值评估 Scoring Agent]
    Node4 --> Node5[报告生成 Agent]
    Node5 --> End[输出评估报告]
    End --> |JSON Response| UI
    
    %% 异步专家反馈机制
    End -.-> Expert[专家异步纠错 (负反馈)]
    Expert -.-> |调整权重/优化模型| Node4
```

## 2. 核心模块详解

### 2.0 模块零：预处理与上下文压缩 (Preprocessing & Context Compression)
- **功能**：解决 Context Window 压力，对大规模历史数据进行摘要和特征提取。
- **策略**：
    - **History Pruning**: 不将完整的 `history_context` (可能包含数百条记录) 放入 Prompt。
    - **Feature Extraction**: 提取关键统计指标存入 `condensed_context`：
        - **时间维度**:
            - `weekly_avg_duration`: 近4周平均每周运动总时长。
            - `frequency_consistency`: 运动频率的方差（衡量坚持性，越低越好）。
            - `last_session_gap`: 距离上次运动的天数（衡量活跃度）。
        - **强度与类型**:
            - `intensity_trend`: 强度变化趋势 (rising/falling/stable)。
            - `diversity_score`: 运动种类丰富度（唯一活动数/总活动数）。
            - `dominant_type`: 占比最高的运动类型（如“有氧-跑跳”）。
        - **生理适应性**:
            - `fatigue_pattern`: 疲劳模式分析（如“连续运动3天后依从性显著下降”）。
            - `injury_risk_flags`: 基于历史不适反馈（如“膝盖疼”、“呼吸困难”）计算的风险标记。
            - `sleep_correlation`: 运动强度与当日睡眠质量的相关系数（需可穿戴设备数据支持）。
        - **长期发展轨迹**:
            - `milestone_progress`: 关键里程碑（如“单脚站立10秒”）的达成速率。
            - `growth_percentile`: 在同龄用户群体中的相对排位（需脱敏大数据支持）。
            - `seasonality_effect`: 季节性影响因子（如“冬季户外活动显著减少”）。
    - **Vector Memory**: 对于非结构化的历史反馈（如“孩子上次做完很累”），存入 Vector DB，仅检索 Top-3 相关反馈。
- **输出**：轻量级的 `condensed_context`，极大降低 Token 消耗。

### 2.1 模块一：数据校验与标准化 (Data Validation & Standardization)
- **功能**：作为子系统的入口，负责接收上游系统传入的 JSON 数据，进行严格的格式校验和必要的默认值填充。
- **定位**：API Gateway / Input Guardrails。
- **输入**：上游系统传入的 JSON 对象。
- **输入示例**：
  ```json
  {
    "child_profile": {
      "name": "小明",
      "age": 5,
      "gender": "male",
      "issues": ["注意力不集中", "感统失调"]
    },
    "proposed_plan": {
      "plan_name": "感统强化周计划",
      "activities": [
        { "name": "跳绳", "duration_minutes": 20, "frequency_weekly": 4, "intensity": "high" },
        { "name": "平衡木训练", "duration_minutes": 15, "frequency_weekly": 3, "intensity": "medium" }
      ],
      "goals": ["提升注意力", "增强平衡感"]
    },
    "history_context": [
      { "date": "2023-10-01", "activities": [{ "name": "跑步", "duration_minutes": 30 }] }
    ]
  }
  ```
- **处理逻辑**：
    1.  **Schema Validation (Pydantic)**:
        - 校验 `child_profile` 是否包含 `age`, `gender`, `issues` 等必填项。
        - 校验 `proposed_plan` 是否包含至少一项活动。
    2.  **Data Standardization (数据标准化)**:
        - **单位统一**：将所有时长统一为“分钟”，频次统一为“每周次”。
        - **默认值填充 (Intelligent Imputation)**：
            - 若上游未传入 `intensity`，则根据 `activity_name` 和 `age` 调用 LLM/规则库推断默认强度（例如：5岁+跳绳 -> "medium"）。
            - 若未传入 `duration`，填充该年龄段的建议时长（如 15分钟）。
- **输出**：标准化后的 `StandardizedInput` 对象，供后续节点使用。
- **异常处理**：若缺少核心字段（如年龄），直接抛出 `400 Bad Request`，不进入后续流程。
- **特征工程 (Plan-Centric Feature Engineering)**：
    - **计划合规性特征 (Compliance Features)**:
        - `age_appropriateness`: 计划中的运动项目是否符合该年龄段的生理发育规律。
        - `intensity_safety`: 运动强度是否在安全范围内（基于年龄和历史背景）。
        - `duration_alignment`: 单次时长是否符合科学建议（如 5 岁儿童不宜进行超长耐力训练）。
    - **科学匹配特征 (Scientific Match Features)**：
        - `issue_targeted_score`: 计划项目（如跳绳）与孩子问题（如注意力）的针对性匹配度。
        - `brain_region_stimulation`: 计划预估能刺激到的核心脑区覆盖率。
        - `sensory_integration_load`: 对前庭、本体、触觉的综合刺激强度预估。
    - **背景参考特征 (Contextual Features)**：
        - `progression_level`: 相比历史记录（history_context），新计划的挑战增量是否合理（避免过于激进或原地踏步）。
        - `diversity_increment`: 新计划是否引入了孩子之前缺失的运动种类。
    - 这些特征将作为随机森林模型的输入，确保评分的专业性。

### 2.2 模块二：儿童发展评估模型 (Child Development Assessment Model)
- **功能**：基于提取的基础信息，构建儿童当前的**发展状态模型 (Current Development State)**，识别其优势与短板。
- **输入**：`child_profile` (含 `issues`), `history_context`。
- **输出**：`child_state` (结构化评估结果)。
- **输出示例**：
  ```json
  {
    "vestibular_system": { "status": "deficit", "level": 2, "description": "前庭敏感，对旋转运动有恐惧" },
    "proprioception": { "status": "normal", "level": 5, "description": "本体感正常" },
    "core_strength": { "status": "weak", "level": 3, "description": "核心力量不足，坐姿维持困难" },
    "emotional_regulation": { "status": "unstable", "level": 2, "description": "易怒，难以自我安抚" }
  }
  ```
- **核心逻辑**：
    - **规则映射 (Rule-Based Mapping)**：将家长描述的自然语言症状（如“怕高”、“转圈晕”）映射到专业的感统维度（如“前庭觉”）。
    - **发展对标 (Developmental Benchmarking)**：对比同龄儿童的标准里程碑（调用 MCP Server 的 `get_age_milestones`），判断其当前所处的发展阶段。
- **作用**：
    - 为后续的评分提供**个性化基准**。例如，对于“前庭敏感”的孩子，高强度的旋转运动虽然科学上能刺激前庭，但对该个体可能是“过度刺激”，应给予低分或警告。

### 2.3 模块三：混合检索专家 (Hybrid Retrieval Expert - MCP Server)
- **功能**：作为独立的 MCP (Model Context Protocol) Server，提供基于**结构化知识库**的高级检索服务。
- **技术架构**：
    - **Protocol**: MCP (Model Context Protocol).
    - **Core**: LlamaIndex + Structred Data Extraction Pipeline.
- **实现细节 (Knowledge Base Implementation)**：
    1.  **结构化预处理 (Structured Pre-processing)**:
        - **ETL 流程**: 
            1. **Extraction**: 读取 `book/` 下的 epub/pdf -> LLM 初步提取。
            2. **Verification (Human-in-the-loop / Multi-Agent)**: 
                - 引入 **Verification Agent**，将提取出的结构化条目与原文片段进行比对，检查幻觉。
                - 对于高风险条目（`risk_level` >= Medium），标记为 `pending_review`，需人工确认。
            3. **Storage**: 存入结构化数据库。
        - **知识点数据模型 (Knowledge Item Schema)**:
            - `content`: 核心知识描述（如“跑跳运动促进前庭发展”）。
            - `source_quote`: **[新增]** 原文引用片段（用于溯源和前端展示）。
            - `target_age_min`: 适用最小年龄 (int).
            - `target_age_max`: 适用最大年龄 (int).
            - `brain_regions`: 影响脑区列表（如 ["小脑", "前庭系统"]）。
            - `benefits`: 预期效果列表（如 ["注意力稳定", "空间感知增强"]）。
            - `risk_level`: 基础风险等级（Low/Medium/High），服务于 AHP 安全评分。
            - `contraindications`: 禁忌症/不适宜人群（如“哮喘慎用”），用于安全硬约束。
            - `recommended_duration`: 适宜时长/频率建议，用于防止过度训练。
            - `milestone_category`: 关联的里程碑类别（如“前庭觉-静态平衡”），用于精准年龄适配。
            - `exercise_types`: 相关运动类型（如 ["跑跳", "有氧运动"]）。
            - `source_book`: 书籍名称。
            - `source_chapter`: 章节信息。
            - `evidence_strength`: 证据强度（如 "RCT研究", "专家建议"）。
        - **索引构建**: 
            - **Vector Store**: 用于语义检索。
            - **Keyword Table / Metadata Filters**: 用于按年龄、运动类型进行精确过滤。

    2.  **MCP Server 工具暴露**:
        - `query_knowledge_base(query: str, age: int, exercise_type: str = None)`: 
            - **逻辑**: 
                1. 先使用 Metadata Filters 过滤掉不适用该年龄段的知识点。
                2. 再在剩余集合中进行语义向量检索。
                3. 返回**结构化对象列表**而非纯文本。
            - **返回示例**: `[{"content": "...", "brain_regions": ["前额叶"], "source": "运动改变大脑"}]`
        - `get_age_milestones(age: int)`: 获取特定年龄段的发展里程碑。
        - `ingest_book(file_path: str)`: **[新增]** 触发后台异步任务，将上传的书籍文件纳入 ETL 流程。

- **调用优势**：
    - 评分 Agent 可以直接获取“影响脑区”等结构化字段作为特征输入，无需二次解析。
    - 严格的年龄过滤防止了错误的建议（如给3岁孩子推荐8岁的训练）。

### 2.4 模块四：价值评估 Scoring Agent
- **功能**：基于检索到的科学证据、拟定计划和历史背景，对运动计划进行多维度打分。
- **技术架构**：采用 **三层混合评分引擎 (Three-Tier Hybrid Scoring Engine)**，兼顾冷启动稳定性与数据驱动的精准度。
- **评分逻辑**：

    #### **Level 1: 基础层 (AHP Baseline)**
    - **定位**：专家规则系统，负责提供保底分数，解决冷启动问题。
    - **实施步骤**:
        1.  **构建层次结构**: 目标层(综合分) -> 准则层(科学/年龄/目标/安全) -> 方案层。
        2.  **权重计算**: 使用特征值法计算权重向量（如：科学40%, 年龄25%...）。
        3.  **安全硬约束**: 若 `risk_level` 为 High 或触犯 `contraindications`，触发非线性惩罚。
        4.  **输出**: $Score_{AHP}$。

    #### **Level 2: 预测层 (ML Prediction) - [Phase 2 特性]**
    - **定位**：数据驱动层，捕捉复杂非线性关系（待积累 >1000 条结构化反馈数据后激活）。
    - **数据闭环设计**:
        - **不依赖主观打分**: 放弃直接让用户打分（Subjective Score）。
        - **采集结构化反馈**: 追踪执行后的客观指标：
            - `compliance_rate`: 计划完成率。
            - `sleep_quality_change`: 睡眠改善（基于穿戴设备或简单问卷）。
            - `emotional_stability`: 情绪平稳度变化。
        - **模型目标**: 预测上述“客观指标”而非“分数”。如果某计划预测出“低依从性”或“情绪恶化”，则降低 $Score_{ML}$。

    #### **Level 3: 融合层 (Dynamic Polynomial Interpolation) - [Phase 2 特性]**
    - **定位**：通过差值多项式动态修正 AHP 的偏差。
    - **核心公式**: 
        $$Score_{Final} = Score_{AHP} + P(\Delta)$$
        其中 $P(\Delta)$ 是拟合残差的多项式函数，$\Delta$ 为特征向量。
    - **工作流**:
        1.  收集用户反馈分数 $Score_{Real}$。
        2.  计算残差 $Residual = Score_{Real} - Score_{AHP}$。
        3.  训练多项式回归模型 $P(x)$ 来预测该残差。
        4.  **动态调整**: 系统定期（如每周）利用新数据重新拟合 $P(x)$ 的系数，实现自我进化。
    - **优势**: 
        - 既保留了 AHP 的可解释性（作为基准）。
        - 又具备了 ML 的精准度（作为修正项）。
        - 能灵活处理“局部非线性”（如：某些特定年龄段对强度的敏感度突增）。

    #### **Level 4: 可解释性 (Explainability)**
    - 利用 **SHAP** 分析 $Score_{ML}$ 和 $P(\Delta)$，结合 AHP 权重，生成最终报告。
    - *示例*: "基准分 80（因科学依据充分），但模型根据历史反馈修正了 -5 分，因为此类高强度运动在 5 岁儿童中普遍依从性较差。"
- **输出**：
    - `score`: 85
    - `reasoning`: "跳绳能有效刺激前庭系统，进而改善注意力..."

### 2.5 模块五：报告生成 (Report Generation)
- **功能**：整合所有信息，生成面向家长的友好报告。
- **实现方式**：LLM 生成。
- **输出内容**：
    - **总评分**：82分
    - **科学原理**：引用《运动改变大脑》等书籍内容，解释运动如何改变大脑结构。
    - **预期改善**：针对孩子具体问题（如注意力）的改善预期。
    - **调整建议**：如果评分较低，给出优化建议（如增加时长、改变运动形式）。

### 2.6 专家负反馈机制 (Expert Negative Feedback Loop - Asynchronous)
- **功能**：专家对系统的历史评分进行**事后审查 (Post-hoc Review)**。
- **触发场景**：
    - 定期抽检（如每周 Top 10 低分/高分案例）。
    - 用户投诉/反馈评分不合理。
- **纠错流程**：
    1.  专家标记某条评估记录为 `Bad Case`。
    2.  专家提供 `Corrected Score` (修正分) 和 `Correction Reason` (修正理由)。
    3.  **系统响应**：
        - **即时**：更新该条记录，（可选）向用户推送修正后的报告。
        - **长效**：
            - 将该案例加入 **Golden Dataset**（作为 Few-shot 样本）。
            - 自动分析误差来源（是 AHP 权重不合理，还是知识库检索错误）。
            - 触发 AHP 权重的微调建议。

### 2.7 模块六：前端展示 (React + TypeScript)
- **功能**：面向最终用户的交互界面，负责数据采集与结果展示。
- **架构**：
    - **SPA (Single Page Application)**：采用 React 18 + TypeScript 构建。
    - **Styling**: Tailwind CSS (快速构建现代 UI)。
    - **State Management**: Zustand / React Query (管理服务端数据缓存)。
- **主要页面**：
    1.  **评估输入页**：
        - 使用 `react-hook-form` + `zod` 进行前端表单校验（与后端 Pydantic 对齐）。
        - 动态表单支持运动计划的增删改查。
    2.  **报告展示页**：
        - **总分仪表盘**：使用 Recharts 或 Ant Design Charts 绘制 Gauge。
        - **雷达图**：展示多维能力模型。
        - **详细报告**：使用 `react-markdown` 渲染后端生成的 Markdown，支持数学公式和代码高亮。
    3.  **知识库管理页 (Admin)**：
        - 文件上传组件（支持拖拽上传）。
        - 实时 WebSocket/轮询 进度条展示 ETL 状态。
- **技术实现**：
    - **Build Tool**: Vite.
    - **HTTP Client**: Axios.
    - **Routing**: React Router v6.

## 3. LangGraph 编排设计

使用 `langgraph` 定义图结构，管理状态流转。

### 3.1 State 定义
```python
from typing import TypedDict, List, Dict, Optional

class AgentState(TypedDict):
    input_text: str
    child_profile: Dict
    child_state: Dict          # 儿童当前发展状态评估结果
    proposed_plan: Dict        # 待评估的拟定计划
    
    # --- Context Optimization Strategy ---
    # 原始 history_context 可能非常大，不直接存入 State。
    # 而是由 Pre-processing Node 提取为 condensed_context (摘要特征)。
    # 原始数据存储在外部数据库或 File System，仅通过 ID 引用。
    condensed_context: Dict    # { "trend": "improving", "avg_intensity": "medium", "last_week_compliance": 0.8 }
    
    # 同样，retrieved_docs 仅保留 Top-K 最相关的片段，或进行 Summarization。
    retrieved_docs: List[Dict] # Top-3 结构化科学依据
    
    evaluation_result: Dict    # 包含分数、SHAP 解释和理由
    final_report: str
    messages: List[str]        # 聊天记录/日志 (需定期执行 trim_messages)
```

### 3.2 节点 (Nodes) 与 边 (Edges)
1.  **`validation_node`**:
    - 接收上游 `input_json`。
    - 执行 Pydantic 校验和默认值填充。
    - 若失败 -> 抛出异常/结束。
    - 若成功 -> 更新 `child_profile`, `proposed_plan` 等。
    - -> `assess_node`
2.  **`assess_node`**:
    - 读取 `child_profile` 和 `history_context`。
    - 调用发展评估模型，识别优势与短板。
    - 更新 `child_state`。
    - -> `retrieve_node`
3.  **`retrieve_node`**:
    - 读取 `proposed_plan` 和 `child_profile` (用于年龄过滤)。
    - 调用 `MCP Tool` 检索科学依据。
    - 更新 `retrieved_docs`。
    - -> `score_node`
4.  **`score_node`**:
    - 读取 `proposed_plan`, `retrieved_docs`, `history_context` 和 `child_state`。
    - 调用 `calculate_ahp_score` 工具执行 AHP 评分逻辑（结合 `child_state` 进行个性化修正）。
    - 更新 `evaluation_result`。
    - -> `report_node`
5.  **`report_node`**:
    - 读取所有信息。
    - 生成 Markdown 报告。
    - 更新 `final_report`。
    - -> `END`

## 4. 技术栈清单
- **Orchestration**: LangGraph
- **LLM Framework**: LangChain (用于 Tool 定义和 Agent 交互)
- **RAG Engine**: LlamaIndex (用于高效的文档索引和检索)
- **Model**: OpenAI GPT-4o / Gemini Pro (或其他高性能 LLM)
- **Backend**: FastAPI (提供 RESTful API 接口)
- **Frontend**: React + TypeScript (Modern SPA, 配合 Tailwind CSS + Shadcn/UI)

## 5.  **后续开发计划**
    1.  **环境搭建**：安装 langgraph, llama-index, langchain 等依赖。
    2.  **RAG 模块实现 (Phase 1)**：编写脚本处理 `book/` 下的书籍，构建本地 Vector Store 索引。
    3.  **Agent 开发**：分别实现提取、评分 (AHP)、报告生成的 Prompt 和逻辑。
    4.  **服务封装**：使用 FastAPI 封装 LangGraph 流程为 REST API。
    5.  **前端实现**：使用 Vite 初始化 React 项目，集成 Shadcn/UI 组件库，开发核心页面。
    6.  **端到端测试**：Cypress / Playwright 进行 E2E 测试。
    7.  **数据闭环与模型迭代 (Phase 2)**:
        - 部署 MVP，收集用户对评分的反馈数据。
        - 训练 XGBoost/RF 模型，激活“三层混合评分引擎”。
    6.  **深度推理升级 (Phase 3)**:
        - 当知识点数量突破 10,000 条或需要支持多跳因果推理（如：前庭失调 -> 阅读困难 -> 解决方案）时，引入 **Neo4j** 实现 GraphRAG。
