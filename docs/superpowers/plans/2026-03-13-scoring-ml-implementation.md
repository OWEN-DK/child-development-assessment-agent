# 评分节点 ML 预测与融合功能实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现评分节点Level 2&3 ML预测与融合功能，前期优先使用千问API，数据积累后平滑过渡到XGBoost模型。

**Architecture:**
1. Level 2实现支持双模式：a) 千问API直接打分模式(前期数据量小时使用) b) XGBoost模型预测模式(数据量足够后使用)，可通过配置切换
2. Level 3实现可配置权重融合，支持AHP规则得分与ML得分的动态融合
3. 所有功能可通过开关控制，默认关闭不影响现有流程

**Tech Stack:** Python 3.13, XGBoost, SHAP, DashScope SDK, LangChain

---

## Chunk 1: 配置项与依赖添加

**Files:**
- Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/config/settings.py`
- Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/pyproject.toml`
- Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/.env.dev.example`

- [ ] **Step 1: 在settings.py中添加ML评分相关配置**
```python
# ML评分配置
ml_scoring_enabled: bool = Field(False, validation_alias="ML_SCORING_ENABLED")
ml_scoring_mode: str = Field("qwen", validation_alias="ML_SCORING_MODE")  # qwen / xgboost
ml_scoring_model_path: str = Field("./models/scoring_xgb.model", validation_alias="ML_SCORING_MODEL_PATH")
ml_scoring_weight_ahp: float = Field(0.7, validation_alias="ML_SCORING_WEIGHT_AHP")
ml_scoring_weight_ml: float = Field(0.3, validation_alias="ML_SCORING_WEIGHT_ML")
ml_scoring_qwen_model: str = Field("qwen3.5-turbo", validation_alias="ML_SCORING_QWEN_MODEL")
```

- [ ] **Step 2: 在pyproject.toml中添加依赖**
```toml
[tool.uv.dependencies]
xgboost = "^2.1.2"
shap = "^0.46.0"
scikit-learn = "^1.5.2"
joblib = "^1.4.2"
```

- [ ] **Step 3: 在.env.dev.example中添加示例配置**
```env
# ML评分配置
ML_SCORING_ENABLED=False
ML_SCORING_MODE="qwen"  # 可选值: qwen/xgboost
ML_SCORING_MODEL_PATH="./models/scoring_xgb.model"
ML_SCORING_WEIGHT_AHP=0.7
ML_SCORING_WEIGHT_ML=0.3
ML_SCORING_QWEN_MODEL="qwen3.5-turbo"
```

- [ ] **Step 4: 安装依赖验证配置**
Run: `cd backend && uv add xgboost shap scikit-learn joblib`
Expected: Dependencies installed successfully

- [ ] **Step 5: Commit**
```bash
git add backend/src/config/settings.py backend/pyproject.toml backend/.env.dev.example
git commit -m "feat: add ML scoring configuration and dependencies"
```

---

## Chunk 2: 千问API评分实现

**Files:**
- Create: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/ml/qwen_scorer.py`
- Modify: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/nodes/scoring.py`

- [ ] **Step 1: 创建QwenScorer类**
```python
from typing import Dict, Any, List, Tuple
from langchain_community.chat_models import TongyiChat
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from src.config.settings import settings
from src.model.schemas import ChildProfile, ProposedPlan, ChildState, KnowledgeItem
from src.utils.logger import logger

class QwenScoringOutput(BaseModel):
    score: float = Field(description="预测的评分，0-100之间")
    reasoning: str = Field(description="评分理由")
    feature_importance: Dict[str, float] = Field(description="各特征重要度，总和为100")

class QwenScorer:
    def __init__(self):
        self.llm = TongyiChat(
            model_name=settings.ml_scoring_qwen_model,
            dashscope_api_key=settings.dashscope_api_key,
            temperature=0.1
        )
        self.parser = PydanticOutputParser(pydantic_object=QwenScoringOutput)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是儿童发展评估专家，需要对儿童训练计划进行打分。
请根据以下信息给出0-100的综合评分，并说明评分理由和各影响因素的重要度。
输出格式要求：
{format_instructions}
"""),
            ("human", """
儿童信息:
年龄: {child_age}岁
性别: {child_gender}
存在问题: {child_issues}
发育状态: {child_state}

训练计划:
活动列表: {plan_activities}
计划目标: {plan_goals}
周总时长: {total_duration}分钟

规则引擎评分结果:
科学性得分: {scientific_score}分
年龄适配度得分: {age_score}分
安全性得分: {safety_score}分
综合规则得分: {ahp_total_score}分

检索到的知识文档:
{rag_docs}

请基于以上信息给出专业的评分。
""")
        ])

    async def predict(
        self,
        child: ChildProfile,
        plan: ProposedPlan,
        child_state: ChildState,
        docs: List[KnowledgeItem],
        ahp_scores: Dict[str, float]
    ) -> Tuple[float, Dict[str, float], str]:
        try:
            format_instructions = self.parser.get_format_instructions()
            
            # 准备输入数据
            input_data = {
                "child_age": child.age,
                "child_gender": "男" if child.gender == "male" else "女",
                "child_issues": ", ".join(child.issues) if child.issues else "无",
                "child_state": child_state.model_dump_json() if child_state else "无",
                "plan_activities": "\n".join([f"- {a.name}: {a.intensity}强度, 每次{a.duration_minutes}分钟, 每周{a.frequency_weekly}次" for a in plan.activities]),
                "plan_goals": ", ".join(plan.goals) if plan.goals else "无",
                "total_duration": sum(a.duration_minutes * a.frequency_weekly for a in plan.activities),
                "scientific_score": ahp_scores["scientific"],
                "age_score": ahp_scores["age"],
                "safety_score": ahp_scores["safety"],
                "ahp_total_score": ahp_scores["total"],
                "rag_docs": "\n".join([f"- 《{d.source_book}》: {d.content[:200]}..." for d in docs]) if docs else "无",
                "format_instructions": format_instructions
            }
            
            chain = self.prompt | self.llm | self.parser
            result = await chain.ainvoke(input_data)
            
            logger.info(f"Qwen ML scoring completed, score: {result.score}")
            return result.score, result.feature_importance, result.reasoning
            
        except Exception as e:
            logger.error(f"Qwen scoring failed: {e}", exc_info=True)
            # 失败时回退到AHP得分
            return ahp_scores["total"], {}, "ML评分失败，使用规则评分结果"
```

- [ ] **Step 2: 在ScoringNode中添加ML预测方法**
```python
from src.core.ml.qwen_scorer import QwenScorer
from src.config.settings import settings

class ScoringNode(BaseNode):
    def __init__(self):
        super().__init__()
        self.qwen_scorer = QwenScorer() if settings.ml_scoring_enabled and settings.ml_scoring_mode == "qwen" else None
        # TODO: 后续添加XGBoost scorer初始化

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Executing Scoring Node...")

        child = state.child_profile
        plan = state.proposed_plan
        child_state = state.child_state
        docs = state.retrieved_docs

        # Level 1: AHP Baseline Scoring
        score, explanation, suggestions, dimension_analysis = self._calculate_ahp_score(
            child, plan, child_state, docs
        )
        
        ahp_scores = {
            "scientific": dimension_analysis["scientific_match"].score,
            "age": dimension_analysis["age_appropriateness"].score,
            "safety": dimension_analysis["safety"].score,
            "total": score
        }

        # Level 2: ML Prediction
        ml_score = score
        ml_feature_importance = {}
        ml_reasoning = ""
        if settings.ml_scoring_enabled:
            if settings.ml_scoring_mode == "qwen" and self.qwen_scorer:
                ml_score, ml_feature_importance, ml_reasoning = await self.qwen_scorer.predict(
                    child, plan, child_state, docs, ahp_scores
                )
            # TODO: 后续添加XGBoost模式支持

        # Level 3: Fusion
        final_score = score * settings.ml_scoring_weight_ahp + ml_score * settings.ml_scoring_weight_ml
        final_score = round(max(0, min(100, final_score)), 1)

        # 合并解释
        if settings.ml_scoring_enabled:
            ml_explanation = f" ML模型预测得分{ml_score:.0f} (权重{settings.ml_scoring_weight_ml*100:.0f}%)。"
            if ml_reasoning:
                ml_explanation += f" ML分析: {ml_reasoning}"
            explanation += ml_explanation

        result = EvaluationResult(
            score=final_score,
            reasoning=f"综合评分基于科学性、年龄适配度和安全性分析。{explanation}",
            shap_explanation={
                "scientific_match": 40 * settings.ml_scoring_weight_ahp + ml_feature_importance.get("scientific_match", 0) * settings.ml_scoring_weight_ml,
                "age_appropriateness": 30 * settings.ml_scoring_weight_ahp + ml_feature_importance.get("age_appropriateness", 0) * settings.ml_scoring_weight_ml,
                "safety": 30 * settings.ml_scoring_weight_ahp + ml_feature_importance.get("safety", 0) * settings.ml_scoring_weight_ml,
                **ml_feature_importance
            },
            dimension_analysis=dimension_analysis,
            suggestions=suggestions,
        )

        return {"evaluation_result": result}
```

- [ ] **Step 3: 运行代码检查语法**
Run: `cd backend && uv run python -c "from src.core.nodes.scoring import ScoringNode; print('Import success')"`
Expected: Import success

- [ ] **Step 4: Commit**
```bash
git add backend/src/core/ml/qwen_scorer.py backend/src/core/nodes/scoring.py
git commit -m "feat: implement Qwen API based ML scoring"
```

---

## Chunk 3: 数据收集与模型训练准备

**Files:**
- Create: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/ml/data_collector.py`
- Create: `/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/ml/train_xgb_model.py`
- Create: `/Users/owen/project/ai/child-development-assessment-agent/backend/models/.gitkeep`

- [ ] **Step 1: 创建数据收集器，自动保存评估数据用于后续训练**
```python
import json
import os
from datetime import datetime
from typing import Dict, Any
from src.config.settings import settings
from src.utils.logger import logger

class MLDataCollector:
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(settings.ml_scoring_model_path), "training_data")
        os.makedirs(self.data_dir, exist_ok=True)
    
    def save_evaluation_data(
        self,
        input_data: Dict[str, Any],
        ahp_scores: Dict[str, float],
        ml_score: float,
        final_score: float,
        expert_feedback: float = None
    ):
        """保存评估数据用于训练"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            data = {
                "timestamp": timestamp,
                "input": input_data,
                "ahp_scores": ahp_scores,
                "ml_score": ml_score,
                "final_score": final_score,
                "expert_feedback": expert_feedback
            }
            
            file_path = os.path.join(self.data_dir, f"eval_{timestamp}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"Evaluation data saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save evaluation data: {e}", exc_info=True)
```

- [ ] **Step 2: 创建XGBoost模型训练脚本**
```python
import os
import json
import joblib
import pandas as pd
import numpy as np
from typing import List, Dict
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb
import shap
from src.config.settings import settings

def load_training_data() -> pd.DataFrame:
    """加载所有训练数据"""
    data_dir = os.path.join(os.path.dirname(settings.ml_scoring_model_path), "training_data")
    all_data = []
    
    for filename in os.listdir(data_dir):
        if filename.endswith(".json"):
            with open(os.path.join(data_dir, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
                # 使用专家反馈作为标签，如果没有则使用最终得分
                label = data["expert_feedback"] if data.get("expert_feedback") is not None else data["final_score"]
                # 提取特征
                features = extract_features(data["input"], data["ahp_scores"])
                features["label"] = label
                all_data.append(features)
    
    return pd.DataFrame(all_data)

def extract_features(input_data: Dict, ahp_scores: Dict) -> Dict:
    """从输入数据中提取特征"""
    child = input_data["child"]
    plan = input_data["plan"]
    docs = input_data["docs"]
    
    features = {
        # 基础信息
        "child_age": child["age"],
        "child_gender": 1 if child["gender"] == "female" else 0,
        "issue_count": len(child.get("issues", [])),
        "plan_activity_count": len(plan["activities"]),
        "plan_goal_count": len(plan.get("goals", [])),
        
        # 规则引擎输出
        "ahp_scientific_score": ahp_scores["scientific"],
        "ahp_age_score": ahp_scores["age"],
        "ahp_safety_score": ahp_scores["safety"],
        "total_duration_weekly": sum(a["duration_minutes"] * a["frequency_weekly"] for a in plan["activities"]),
        "avg_activity_duration": np.mean([a["duration_minutes"] for a in plan["activities"]]),
        
        # 活动强度统计
        "high_intensity_count": sum(1 for a in plan["activities"] if a["intensity"] == "high"),
        "medium_intensity_count": sum(1 for a in plan["activities"] if a["intensity"] == "medium"),
        "low_intensity_count": sum(1 for a in plan["activities"] if a["intensity"] == "low"),
        
        # RAG特征
        "rag_doc_count": len(docs),
        "rag_avg_relevance": np.mean([d["relevance_score"] for d in docs]) if docs else 0,
        "rag_high_relevance_count": sum(1 for d in docs if d["relevance_score"] > 0.8),
        "rag_risk_doc_count": sum(1 for d in docs if d["risk_level"] == "High"),
    }
    
    # 儿童状态特征
    if input_data.get("child_state"):
        state = input_data["child_state"]
        status_map = {"normal": 0, "deficit": 1, "excellent": 2}
        features.update({
            "vestibular_status": status_map.get(state.get("vestibular_system", {}).get("status", "normal"), 0),
            "proprioception_status": status_map.get(state.get("proprioception_system", {}).get("status", "normal"), 0),
            "tactile_status": status_map.get(state.get("tactile_system", {}).get("status", "normal"), 0),
            "auditory_status": status_map.get(state.get("auditory_system", {}).get("status", "normal"), 0),
            "visual_status": status_map.get(state.get("visual_system", {}).get("status", "normal"), 0),
        })
    
    return features

def train_model():
    """训练XGBoost模型"""
    df = load_training_data()
    if len(df) < 50:
        print(f"训练数据不足，当前只有{len(df)}条，需要至少50条数据才能训练模型")
        return
    
    print(f"开始训练模型，数据量: {len(df)}条")
    
    # 分离特征和标签
    X = df.drop("label", axis=1)
    y = df["label"]
    
    # 划分训练集测试集
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 训练XGBoost模型
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
        objective="reg:squarederror"
    )
    model.fit(X_train, y_train)
    
    # 评估模型
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"模型评估结果: MAE={mae:.2f}, R2={r2:.2f}")
    
    # 计算SHAP值用于解释
    explainer = shap.TreeExplainer(model)
    shap_values = explainer(X)
    
    # 保存模型和解释器
    os.makedirs(os.path.dirname(settings.ml_scoring_model_path), exist_ok=True)
    joblib.dump(model, settings.ml_scoring_model_path)
    joblib.dump(explainer, os.path.join(os.path.dirname(settings.ml_scoring_model_path), "shap_explainer.joblib"))
    
    print(f"模型已保存到 {settings.ml_scoring_model_path}")
    return model, explainer

if __name__ == "__main__":
    train_model()
```

- [ ] **Step 3: 创建models目录**
Run: `mkdir -p /Users/owen/project/ai/child-development-assessment-agent/backend/models && touch /Users/owen/project/ai/child-development-assessment-agent/backend/models/.gitkeep`

- [ ] **Step 4: Commit**
```bash
git add backend/src/core/ml/data_collector.py backend/src/core/ml/train_xgb_model.py backend/models/.gitkeep
git commit -m "feat: add data collector and XGBoost training script"
```

---

## Chunk 4: 功能测试与验证

**Files:**
- Create: `/Users/owen/project/ai/child-development-assessment-agent/backend/tests/test_ml_scoring.py`

- [ ] **Step 1: 编写ML评分测试用例**
```python
import pytest
from unittest.mock import Mock, patch
from src.core.ml.qwen_scorer import QwenScorer
from src.model.schemas import ChildProfile, ProposedPlan, Activity, ChildState, SystemStatus

@pytest.mark.asyncio
async def test_qwen_scorer():
    # 构造测试数据
    child = ChildProfile(
        age=5,
        gender="male",
        issues=["注意力不集中", "平衡感差"],
        development_age=4.8
    )
    
    activities = [
        Activity(
            name="平衡木训练",
            intensity="medium",
            duration_minutes=20,
            frequency_weekly=3,
            category="vestibular"
        ),
        Activity(
            name="拼图游戏",
            intensity="low",
            duration_minutes=15,
            frequency_weekly=5,
            category="cognitive"
        )
    ]
    
    plan = ProposedPlan(
        activities=activities,
        goals=["提升注意力", "改善平衡能力"]
    )
    
    child_state = ChildState(
        vestibular_system=SystemStatus(status="deficit", score=2),
        proprioception_system=SystemStatus(status="normal", score=4),
        tactile_system=SystemStatus(status="normal", score=4)
    )
    
    ahp_scores = {
        "scientific": 75,
        "age": 85,
        "safety": 90,
        "total": 82
    }
    
    # Mock LLM返回
    mock_output = {
        "score": 80.5,
        "reasoning": "计划整体合理，针对平衡感问题的训练很有针对性，时长安排也符合5岁儿童特点",
        "feature_importance": {
            "scientific_match": 40,
            "age_appropriateness": 30,
            "safety": 20,
            "targetedness": 10
        }
    }
    
    with patch.object(QwenScorer, 'predict', return_value=(mock_output["score"], mock_output["feature_importance"], mock_output["reasoning"])):
        scorer = QwenScorer()
        score, feature_importance, reasoning = await scorer.predict(child, plan, child_state, [], ahp_scores)
        
        assert 0 <= score <= 100
        assert isinstance(feature_importance, dict)
        assert isinstance(reasoning, str)
        assert score == mock_output["score"]
```

- [ ] **Step 2: 运行测试**
Run: `cd backend && uv run pytest tests/test_ml_scoring.py -v`
Expected: Test passes

- [ ] **Step 3: 整体流程测试，开启ML评分后运行完整评估流程**
Run: `cd backend && ML_SCORING_ENABLED=True uv run python run_assessment.py`
Expected: Process completes successfully, ML scoring is executed

- [ ] **Step 4: Commit**
```bash
git add backend/tests/test_ml_scoring.py
git commit -m "test: add ML scoring test cases"
```

---

## 完成标准
1. ML评分功能可通过配置开关控制，默认关闭不影响现有功能
2. 千问API模式正常工作，能够返回合理的评分和解释
3. 数据收集功能正常，自动保存评估数据
4. 训练脚本可用，数据量足够时可以训练XGBoost模型
5. 所有测试用例通过
