# Phase C: 同义词扩展质量优化 (P1)

> **优先级**: P1 (质量优化)
> **对应需求**: 4.5 (同义词扩展质量优化)
> **对应测试**: 测试 12

## 🎯 目标

解决同义词扩展引入噪声问题：
- LLM 生成的同义词可能包含不相关词汇（如"注意力"扩展出"视力"）
- 质量验证规则不足（仅过滤单字、过长词、非中文字符）
- LLM 失败时无本地兜底机制

## 📋 实施步骤

- [ ] **C-1: 同义词质量验证器**
  - 详见 [03-phase-c-01-synonym-validator.md](./03-phase-c-01-synonym-validator.md)
- [ ] **C-2: LLM 失败本地兜底策略**
  - 详见 [03-phase-c-02-fallback-strategy.md](./03-phase-c-02-fallback-strategy.md)

## ✅ 验收标准

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 同义词扩展质量验证通过率 | 未测量 | ≥95% |
| LLM 失败时本地兜底成功率 | 0% | ≥80% |

## 🔧 回滚策略

配置项 `rag_query_rewrite_method=legacy` 可恢复旧版查询重写。

---

## 🏗️ 架构说明

### 同义词扩展流水线

```
查询输入 (query)
    │
    ▼
┌─────────────────────────────────┐
│  LLM 同义词扩展                  │
│  (通过 PromptManager 获取提示词) │
│  ↓ 成功 → 解析 JSON 获取同义词列表 │
│  ↓ 失败 → 触发本地兜底 (C-2)     │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  SynonymValidator (C-1)         │
│  多维度质量验证：                 │
│  ├── 黑名单过滤                  │
│  ├── 粒度控制 (防太宽泛)         │
│  ├── 白名单优先通过              │
│  ├── 语义重叠检查                │
│  └── 专属规则匹配                │
│  ↓ 通过 → 保留有效词             │
│  ↓ 未通过 → 过滤 + 记录日志      │
└──────────────┬──────────────────┘
               │
               ▼
    验证后有效同义词列表
               │
               ▼
    去重后拼接为扩展查询
    "原词 同义词1 同义词2 ..."
               │
               ▼
    送入后续检索流程 (BM25 + 向量)
```

### 本地兜底策略流程 (C-2)

```
LLM 调用失败 / 验证后无有效词
    │
    ▼
┌─────────────────────────────────┐
│  LocalSynonymExpander (C-2)     │
│  三级匹配策略：                   │
│  ├── 精确匹配 (exact_match)      │
│  ├── 子串匹配 (substring_match)  │
│  └── 分词匹配 (tokenized_match)  │
│  ↓                               │
│  加载 src/data/local_synonyms.json│
│  (优先从数据库 system_configs 加载)│
└──────────────┬──────────────────┘
               │
               ▼
    本地扩展结果
               │
               ▼
┌─────────────────────────────────┐
│  复用 SynonymValidator 过滤      │
│  (确保兜底结果同样经过质量验证)   │
└──────────────┬──────────────────┘
               │
               ▼
    最终扩展查询
```

### 配置管理

| 配置项 | 类型 | 默认值 | 说明 | 存储位置 |
|--------|------|--------|------|----------|
| `rag_query_rewrite_method` | str | `"validated"` | 查询重写模式：`validated` \| `legacy` | `system_configs` 表 |
| `rag_synonym_quality_threshold` | float | `0.8` | 验证通过率阈值（≥此值认为有效） | `system_configs` 表 |
| `rag_synonym_validation_rules` | JSON | 见下方 | 验证规则词典（白名单/黑名单/专属规则） | `system_configs` 表 |
| `rag_local_synonyms_dict` | JSON | 见下方 | 本地同义词词典（兜底用） | `system_configs` 表 |
| `rag_synonym_expansion_timeout` | int | `10` | LLM 同义词扩展超时时间（秒） | `system_configs` 表 |
| `rag_synonym_log_rejected` | bool | `true` | 是否记录被拒绝的同义词（用于优化词典） | `system_configs` 表 |

**`rag_synonym_validation_rules` 结构**:
```json
{
  "domain_terms": {
    "<原词>": {
      "valid": ["有效同义词1", "有效同义词2"],
      "invalid": ["不相关词1", "不相关词2"],
      "too_broad": ["太宽泛词1"]
    }
  },
  "domain_whitelist": ["领域标准术语列表"],
  "domain_blacklist": ["已知不相关词列表"]
}
```

**`rag_local_synonyms_dict` 结构**:
```json
{
  "<领域分类>": {
    "<词条>": ["同义词1", "同义词2", ...]
  }
}
```

### 与其他 Phase 的集成依赖

| 依赖 Phase | 集成点 | 说明 |
|------------|--------|------|
| **Phase A** | 无直接依赖 | Phase C 可独立于 Phase A 执行，但建议 Phase A 完成后再接入（分数语义稳定后，同义词扩展效果更易评估） |
| **Phase B** | 查询类型分析器 | Phase B 的 `QueryAnalyzer` 可识别"专业术语查询"，Phase C 的验证器可复用其领域词库做额外校验 |
| **Phase D** | 边界场景处理 | Phase D 的超长查询意图提取结果，可作为 Phase C 验证器的 `original_query` 输入，避免对提取后的短意图做过度扩展 |

### 数据库配置初始化

Phase C 需要在 `system_configs` 表中新增以下配置记录：

```sql
-- 同义词验证规则词典
INSERT INTO system_configs (config_key, config_value, config_type, description, is_active, created_at, updated_at)
VALUES (
    'rag_synonym_validation_rules',
    '{"domain_terms":{"注意力":{"valid":["专注力","集中力","注意力集中","注意广度"],"invalid":["视力","听力","观察力","记忆力","想象力"],"too_broad":["注意","力"]},"感统":{"valid":["感觉统合","感觉整合","感官统合"],"invalid":["感觉","统合","感官","感觉系统"],"too_broad":["感","统"]},"精细动作":{"valid":["小肌肉","手眼协调","手指灵活","精细运动"],"invalid":["动作","精细","肌肉","运动"],"too_broad":["精细","动作"]}},"domain_whitelist":["前庭觉","本体觉","触觉","大动作","精细动作","语言发展","认知发展","社交技能","注意力","专注力","感统","感觉统合","平衡感","协调性","手眼协调","核心力量","情绪调节"],"domain_blacklist":["视力","听力","嗅觉","味觉","记忆力","想象力","创造力","逻辑思维","数学能力","阅读能力"]}',
    'json',
    '同义词质量验证规则词典（白名单/黑名单/专属规则）',
    1,
    NOW(),
    NOW()
);

-- 本地同义词词典（兜底用）
INSERT INTO system_configs (config_key, config_value, config_type, description, is_active, created_at, updated_at)
VALUES (
    'rag_local_synonyms_dict',
    '{"sensory_integration":{"感统":["感觉统合","感觉整合","感官统合"],"前庭觉":["前庭感","平衡觉","前庭系统"],"本体觉":["本体感","本体感觉"],"触觉":["触觉系统","触觉防御","触觉敏感"]},"motor_development":{"大运动":["粗大动作","大肌肉运动"],"精细动作":["精细运动","小肌肉","手眼协调"],"大动作":["粗大动作","大肌肉运动","全身运动"]},"cognitive_development":{"注意力":["专注力","集中力","注意力集中"],"专注力":["注意力","集中力","专注"]},"language_development":{"语言":["语言能力","语言表达","语言发展"],"表达":["表达能力","语言表达","沟通能力"]},"social_emotional":{"社交":["社交能力","人际交往","社交技能"],"情绪":["情绪管理","情绪调节","情绪控制"]}}',
    'json',
    '本地同义词词典（LLM 失败时兜底用）',
    1,
    NOW(),
    NOW()
);

-- 同义词扩展质量阈值
INSERT INTO system_configs (config_key, config_value, config_type, description, is_active, created_at, updated_at)
VALUES (
    'rag_synonym_quality_threshold',
    '0.8',
    'float',
    '同义词验证通过率阈值（≥此值认为扩展有效）',
    1,
    NOW(),
    NOW()
);
```

### Prompt 更新流程

Phase C 需要优化 `SYNONYM_EXPANSION_PROMPT`，新增领域约束和负面示例。更新必须通过数据库完成：

```sql
-- 更新 synonym_expansion 提示词（通过 system_configs 或 prompt_templates 表）
UPDATE prompt_templates
SET content = '<优化后的完整 Prompt 内容>',
    updated_at = NOW(),
    updated_by = 'rag-search-optimization-phase-c'
WHERE prompt_key = 'synonym_expansion';
```

**Prompt 新增约束内容** (追加到现有 Prompt 的【强制约束】部分):
```
【领域约束】
- 同义词必须属于儿童发展/感统训练/脑科学/教育心理学领域
- 禁止扩展为上位词（如"感统"→"感觉"）、下位词（如"感统"→"前庭觉"）
- 禁止扩展为不相关领域词汇（如"注意力"→"视力"、"记忆力"）

【负面示例】
- ❌ 错误："注意力" → ["视力", "听力", "记忆力"]（不相关领域）
- ❌ 错误："感统" → ["感觉", "统合"]（太宽泛的上位词）
- ❌ 错误："精细动作" → ["动作", "肌肉"]（太宽泛的上位词）
- ✅ 正确："注意力" → ["专注力", "集中力", "注意力集中"]
- ✅ 正确："感统" → ["感觉统合", "感觉整合", "感官统合"]
- ✅ 正确："精细动作" → ["手眼协调", "小肌肉", "精细运动"]
```

### Phase C 专属风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 领域词典覆盖不足，导致常见查询验证通过率低于 95% | 中 | 中 | 初始词典覆盖诊断测试 3 个标注查询 + 30 个常见查询；提供 `rag_synonym_log_rejected` 配置记录被拒词，持续优化词典 |
| 验证规则过严，导致 LLM 生成的有效词被误拒 | 低 | 高 | 白名单优先通过机制；提供 `rag_synonym_quality_threshold` 可调阈值；保留 `rag_query_rewrite_method=legacy` 回滚 |
| 本地兜底词典规模不足，成功率低于 80% | 低 | 中 | 初始词典覆盖 5 大领域约 30 个词条；通过 `rag_local_synonyms_dict` 配置项可动态扩展，无需发版 |
| Prompt 更新后 LLM 输出格式变化导致解析失败 | 低 | 中 | 保留现有 PydanticOutputParser 结构化输出约束；新增约束仅追加不修改原有格式要求；JSON 解析失败时自动回退到本地兜底 |
| 验证器初始化时数据库配置未就绪 | 低 | 低 | 三级降级加载：数据库 → 本地 JSON 文件 → 空词典（仅使用通用规则） |

---

**返回索引：** [00-overview.md](../00-overview.md)
