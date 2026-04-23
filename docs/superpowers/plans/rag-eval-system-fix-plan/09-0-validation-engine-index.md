# 6层校验引擎文件索引
**总工作量**：140h
**模块拆分**：
| 序号 | 文件名称 | 功能描述 | 工作量 | 状态 |
|------|----------|----------|--------|------|
| 1 | 09-0-validation-engine-index.md | 校验引擎整体说明与文件索引 | 0.5h | ✅ 已完成 |
| 2 | 09-1-layer1-rules.md | Layer1 规则引擎详细实现 | 8h | ✅ 已完成 |
| 3 | 09-2-layer2-history.md | Layer2 历史对比校验详细实现 | 10h | ✅ 已完成 |
| 4 | 09-3-layer3-llm.md | Layer3 LLM诊断校验详细实现 | 25h | ✅ 已完成 |
| 5 | 09-4-layer4-data.md | Layer4 数据质量校验详细实现 | 15h | ✅ 已完成 |
| 6 | 09-5-layer5-retrieval.md | Layer5 检索链路校验详细实现 | 20h | ✅ 已完成 |
| 7 | 09-6-layer6-verification.md | Layer6 验证保障校验详细实现 | 15h | ✅ 已完成 |
| 8 | 09-7-engine-integration.md | 校验引擎调度、结果合并、报告生成集成 | 12h | ✅ 已完成 |
| 9 | 09-8-validation-test.md | 校验引擎单元测试、集成测试用例 | 5h | ✅ 已完成 |
---
## 一、整体架构
```
校验引擎入口（engine.py）
├── 统一调度所有层校验器
├── 合并各层校验结果
├── 去重调优建议
├── 生成最终报告
└── 集成到测试运行完成流程
```
---
## 二、统一输出规范（所有层必须遵循）
每个校验器的`validate`方法必须返回以下结构：
```python
{
    "layer": str,  # 层标识：layer1/layer2/layer3/layer4/layer5/layer6
    "name": str,   # 层名称
    "score": float, # 层得分 0-100
    "issues": List[Dict], # 问题列表，每个问题包含：type, metric, current, threshold, description
    "suggestions": List[TuningSuggestionCreate], # 调优建议列表，符合统一Schema
    "details": Dict, # 详细校验数据，用于前端展示
    "cost_time": float, # 校验耗时ms
}
```
---
## 三、集成要求
1. ✅ 所有层继承统一基类`BaseValidator`，接口一致
2. ✅ 所有数据库操作通过Service层，不直接操作ORM
3. ✅ 所有调优建议符合统一的`TuningSuggestionCreate`结构
4. ✅ 监控日志记录到文件，不依赖Prometheus（符合用户需求）
5. ✅ 零迁移，不修改现有测试运行逻辑，仅在完成后追加校验流程
6. ✅ 异步执行，不阻塞测试完成回调，校验过程后台运行
---
## 四、依赖组件
| 组件名称 | 用途 | 现有组件复用 |
|----------|------|--------------|
| TestResultService | 获取测试运行指标数据 | ✅ 已有，直接复用 |
| ConfigService | 获取当前配置、历史配置版本 | ✅ 已有，直接复用 |
| LLMFactory | 调用大模型进行诊断分析 | ✅ 已有，直接复用 |
| PromptManager | 获取诊断提示词模板 | ✅ 已有，直接复用 |
| DocumentService | 获取文档数据进行质量校验 | ✅ 已有，直接复用 |
| AnnotationService | 获取意图标注数据校验检索效果 | ✅ 新增，已实现 |
| ReportService | 保存最终校验报告 | ✅ 新增，已实现 |
| SuggestionService | 保存调优建议 | ✅ 新增，已实现 |
---
**注意**：所有组件均已存在或已在数据模型模块实现，无需重复开发。
