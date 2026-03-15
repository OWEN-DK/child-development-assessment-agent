# 评分节点 ML 预测与融合功能设计文档
## 版本信息
- 版本: v1.0
- 日期: 2026-03-13
- 作者: Trae AI
- 状态: 设计中

## 1. 概述
本文档描述评分节点 Level 2 & 3 (ML 预测与融合) 功能的设计方案，基于轻量树模型实现，快速落地 ML 评分能力。

## 2. 功能目标
1. 补充现有 AHP 规则评分的不足，提升评分准确性
2. 提供特征重要度解释，增强评分可解释性
3. 支持模型持续迭代优化，随着数据积累自动提升效果

## 3. 整体架构
```
+-------------------+     +-------------------+     +-------------------+
|   Level 1: AHP    |     |  Level 2: ML      |     |  Level 3: Fusion  |
|   规则评分        |---->|  预测得分         |---->|  加权融合输出     |
|   (已实现)        |     |  (树模型)         |     |  最终得分         |
+-------------------+     +-------------------+     +-------------------+
         |                         |                          |
         v                         v                          v
+-------------------+     +-------------------+     +-------------------+
| 维度分析结果      |     | SHAP 特征重要度   |     | 综合解释生成      |
+-------------------+     +-------------------+     +-------------------+
```

## 4. 详细设计

### 4.1 Level 2: ML 预测模块
#### 4.1.1 模型选型
- 模型: XGBoost Regressor (回归任务，预测0-100分)
- 优势: 可解释性强、训练速度快、对结构化数据效果好、输出SHAP值支持特征重要度分析

#### 4.1.2 输入特征 (共26维)
| 特征分类 | 特征名称 | 类型 | 说明 |
|---------|---------|------|------|
| 基础信息 | child_age | float | 儿童年龄 |
| | child_gender | int | 性别 (0=男, 1=女) |
| | issue_count | int | 儿童问题数量 |
| | plan_activity_count | int | 计划活动数量 |
| | plan_goal_count | int | 计划目标数量 |
| 规则引擎输出 | ahp_scientific_score | float | AHP科学性得分 |
| | ahp_age_score | float | AHP年龄适配度得分 |
| | ahp_safety_score | float | AHP安全性得分 |
| | issue_coverage_rate | float | 问题覆盖率 |
| | total_duration_weekly | int | 周总时长 |
| | avg_activity_duration | float | 平均活动时长 |
| | high_intensity_count | int | 高强度活动数量 |
| | medium_intensity_count | int | 中等强度活动数量 |
| | low_intensity_count | int | 低强度活动数量 |
| RAG特征 | rag_doc_count | int | 检索到的文档数量 |
| | rag_avg_relevance | float | 文档平均相关度 |
| | rag_high_relevance_count | int | 高相关度文档数量(>0.8) |
| | rag_risk_doc_count | int | 高风险文档数量 |
| 儿童状态特征 | vestibular_status | int | 前庭觉状态 (0=normal, 1=deficit, 2=excellent) |
| | proprioception_status | int | 本体觉状态 |
| | tactile_status | int | 触觉状态 |
| | auditory_status | int | 听觉状态 |
| | visual_status | int | 视觉状态 |
| 文本语义特征 (千问API生成) | plan_semantic_similarity | float | 计划目标与儿童问题的语义相似度 |
| | activity_age_appropriateness | float | 活动与年龄的语义适配度 (千问打分0-1) |
| | plan_risk_semantic_score | float | 计划语义风险得分 (千问打分0-1) |

#### 4.1.3 输出
- `ml_predicted_score`: float [0, 100]，ML预测的最终得分
- `ml_shap_values`: Dict[str, float]，各输入特征的SHAP重要度值，用于解释

### 4.2 Level 3: 结果融合模块
#### 4.2.1 融合策略
- 初始权重: AHP规则得分占70%，ML预测得分占30%
- 权重可配置，通过settings参数动态调整
- 融合公式: `final_score = ahp_score * weight_ahp + ml_score * weight_ml`

#### 4.2.2 可配置参数 (settings.py新增)
```python
# ML评分配置
ml_scoring_enabled: bool = Field(False, validation_alias="ML_SCORING_ENABLED")
ml_scoring_model_path: str = Field("./models/scoring_xgb.model", validation_alias="ML_SCORING_MODEL_PATH")
ml_scoring_weight_ahp: float = Field(0.7, validation_alias="ML_SCORING_WEIGHT_AHP")
ml_scoring_weight_ml: float = Field(0.3, validation_alias="ML_SCORING_WEIGHT_ML")
ml_scoring_semantic_feature_enabled: bool = Field(True, validation_alias="ML_SCORING_SEMANTIC_FEATURE_ENABLED")
```

### 4.3 模型训练与部署
1. 训练数据: 历史评估数据+专家标注得分，至少50条数据即可训练初版模型
2. 模型文件: 保存为二进制文件，随代码库发布
3. 推理: 加载预训练模型，实时推理，单次预测耗时<10ms
4. 版本管理: 模型文件带版本号，支持平滑升级

### 4.4 集成到现有流程
在ScoringNode的`__call__`方法中，Level1之后添加:
```python
# Level 2: ML Prediction
if settings.ml_scoring_enabled:
    ml_score, shap_values = self._predict_ml_score(child, plan, child_state, docs, ahp_scores)
else:
    ml_score = score
    shap_values = {}

# Level 3: Fusion
final_score = score * settings.ml_scoring_weight_ahp + ml_score * settings.ml_scoring_weight_ml
```

## 5. 非功能需求
- 推理速度: 单次请求<50ms，不影响整体接口响应
- 兼容性: 开关可配置，默认关闭，不影响现有功能
- 可解释性: 输出ML特征贡献度，和规则引擎结果共同构成完整解释

## 6. 后续迭代计划
1. v1.0: 实现基础ML预测与融合功能，静态权重
2. v1.1: 加入千问API生成的语义特征，提升预测效果
3. v1.2: 实现动态权重调整，根据场景自动适配融合比例
4. v2.0: 数据积累到500条以上时升级到深度模型方案
