# 系统改进实施计划 (System Improvement Implementation Plan)

本计划旨在解决代码库中存在的硬编码、逻辑缺陷和错误处理不足等问题，提升系统的健壮性和可维护性。

## 1. 配置重构与规则解耦 (Configuration Refactoring)

目标：将散落在代码中的硬编码规则提取到独立的配置文件中。

- [x] **创建规则配置**: 在 `backend/src/config/` 下创建 `rules.py`，定义 `RuleSettings` 类。
- [x] **迁移校验规则**: 将 `validation.py` 中的 `simple_rules` 活动映射表移入 `rules.py`。
- [x] **迁移里程碑数据**: 将 `assessment.py` 中的 `_get_age_milestones` 数据移入 `rules.py`。
- [x] **迁移评分参数**: 将 `scoring.py` 中的 AHP 权重、时间阈值（300min, 30min）和扣分标准移入 `rules.py`。
- [x] **集成配置**: 在 `settings.py` 中集成 `RuleSettings`，确保可以通过环境变量覆盖。

## 2. 核心逻辑优化 (Core Logic Optimization)

目标：增强评分和校验逻辑的准确性与鲁棒性。

- [x] **优化科学性匹配 (Scoring)**:
    - 在 `scoring.py` 中改进 `_calculate_ahp_score`。
    - 引入关键词标准化或简单的语义扩展匹配（替代单纯的子串匹配）。
    - 增加对 `KnowledgeItem` 中 `brain_regions` 和 `topics` 的利用。
- [x] **完善活动校验 (Validation)**:
    - 在 `ValidationNode` 中增加对 `ActivityType` (如：前庭类、本体类) 的推断逻辑（基于规则或 LLM）。
    - 确保 `intensity` 推断逻辑使用配置中的规则。

## 3. 错误处理与兜底优化 (Error Handling & Fallback)

目标：提升系统在异常情况下的用户体验和安全性。

- [x] **重写报告兜底 (Reporting)**:
    - 修改 `reporting.py` 的 `_generate_fallback_report` 方法。
    - 设计一个静态的、用户友好的 Markdown 模板，仅展示已知数据（分数、雷达图），严禁泄露 Prompt。
- [x] **增强评估健壮性 (Assessment)**:
    - 在 `assessment.py` 中，当 JSON 解析完全失败时，返回更明确的错误状态描述，而不是误导性的 "normal"。

## 4. 预处理逻辑对齐 (Preprocessing Alignment)

目标：消除代码与文档之间的差异。

- [x] **更新文档或代码**:
    - 检查 `preprocessing.py` 中的 `intensity_trend` 算法。
    - 决定是升级算法以匹配 `AGENTS.md` 的描述，还是更新文档以反映当前实现。
    - *建议*: 先更新文档以反映现状，后续再优化算法。

## 5. 验证与测试 (Verification)

- [x] **单元测试**: 为提取出的 `rules.py` 编写简单的加载测试。
- [x] **集成验证**: 运行一次完整的评估流程，确保配置读取正常，且兜底机制有效。
