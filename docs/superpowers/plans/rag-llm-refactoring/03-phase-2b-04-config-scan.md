# Phase 2B.4: 配置扫描与盘点

> **状态:** ⏳ 待实现
> **前置任务:** [03-prompt-validation.md](./03-phase-2b-03-prompt-validation.md)

## 目标

全面扫描代码库中所有硬编码的魔法值 (Magic Numbers) 和业务配置，建立完整的配置清单，并映射到 ConfigManager 的目标配置键。

> **⚠️ 路径映射说明**: 配置键 (如 `rag.retrieval.dedup.containment_threshold`) 与 Settings 属性访问路径 (`settings.rag.retrieval.dedup.containment_threshold`) 必须保持一致。若 ConfigManager 使用扁平化存储 (如 MySQL 中的 `config_snapshots` 表)，需在加载时转换为嵌套结构。

## 实施任务

### 1. 扫描范围定义

- [ ] **1.1 定义扫描范围**
  - 检索服务: `src/service/retrieval_service.py`
  - 评分节点: `src/core/nodes/scoring.py`
  - 元数据提取: `src/core/metadata_extractor.py`
  - 分块处理: `src/core/metadata_processor.py`
  - 年龄过滤: `src/core/age_filter.py`
  - 儿童发展引擎: `src/core/child_development_engine.py`
  - 混合检索: `src/core/hybrid_retrieval.py`

- [ ] **1.2 定义魔法值识别规则**
  - 硬编码的数字阈值 (如 `0.8`, `0.9`, `10`, `20`)
  - 硬编码的字符串常量 (如 `"high"`, `"low"`)
  - 硬编码的权重配置 (如 `0.7`, `0.3`)
  - 硬编码的并发/线程数 (如 `20`, `100`)
  - 硬编码的时间参数 (如 `300`, `3600`)

### 2. P0 配置扫描 (LLM 参数)

- [ ] **2.1 扫描各场景的 LLM 参数**

  | 场景 | 当前配置方式 | 来源文件 | 目标配置键 | 影响范围 |
  |------|-------------|----------|-----------|---------|
  | assessment | `temperature=0.5`, `max_tokens=1024` | `src/core/nodes/assessment.py` | `llm.assessment.temperature`, `llm.assessment.max_tokens` | 评估节点 |
  | reporting | `temperature=0.7`, `max_tokens=8000` | `src/core/nodes/reporting.py` | `llm.reporting.temperature`, `llm.reporting.max_tokens` | 报告生成 |
  | validation | `temperature=0.3`, `max_tokens=512` | `src/core/nodes/validation.py` | `llm.validation.temperature`, `llm.validation.max_tokens` | 校验节点 |
  | metadata_extraction | `temperature=0.4`, `max_tokens=1024` | `src/core/metadata_extractor.py` | `llm.metadata_extraction.temperature`, `llm.metadata_extraction.max_tokens` | 元数据提取 |
  | query_rewrite | `temperature=0.6`, `max_tokens=256` | `src/service/retrieval_service.py` | `llm.query_rewrite.temperature`, `llm.query_rewrite.max_tokens` | 查询重写 |
  | synonym_expansion | `temperature=0.8`, `max_tokens=256` | `src/service/retrieval_service.py` | `llm.synonym_expansion.temperature`, `llm.synonym_expansion.max_tokens` | 同义词扩展 |
  | query_classification | `temperature=0.2`, `max_tokens=128` | `src/core/query_router.py` | `llm.query_classification.temperature`, `llm.query_classification.max_tokens` | 查询分类 |
  | layered_content | `temperature=0.4`, `max_tokens=256/1024/4096` | `src/core/layered_content_generator.py` | `llm.layered_content.temperature`, `llm.layered_content.max_tokens_l0/l1/batch` | 分层内容生成 |

- [ ] **2.2 统计影响范围**
  - 涉及 15+ 文件，60+ 处硬编码参数
  - 需统一从 ConfigManager 读取

### 3. P1 配置扫描 (RAG 检索阈值与参数)

> **⚠️ 配置模块路径对齐说明**: 以下配置项归入现有 `src/config/modules/rag/` 模块:
> - 评分相关 → `src/config/modules/rag/core.py`
> - 去重相关 → `src/config/modules/rag/retrieval.py`

- [ ] **3.1 扫描去重相关阈值**

  | 配置项 | 当前值 | 来源文件 | 行号 | 目标配置模块 | 目标配置键 |
  |--------|--------|----------|------|-----------|-----------|
  | 去重包含阈值 | `>0.8` | `retrieval_service.py` | ~566 | `rag/retrieval.py` | `rag.retrieval.dedup.containment_threshold` |
  | 长度差异阈值 | `<0.2` | `retrieval_service.py` | ~574 | `rag/retrieval.py` | `rag.retrieval.dedup.length_diff_threshold` |
  | difflib 相似度阈值 | `>0.9` | `retrieval_service.py` | ~581 | `rag/retrieval.py` | `rag.retrieval.dedup.similarity_threshold` |

- [ ] **3.2 扫描评分相关参数**

  | 配置项 | 当前值 | 来源文件 | 行号 | 目标配置模块 | 目标配置键 |
  |--------|--------|----------|------|-----------|-----------|
  | 显示分数基准 | `0.60` | `retrieval_service.py` | ~725 | `rag/core.py` | `rag.core.scoring.base_display_score` |
  | 显示分数上限 | `0.98` | `retrieval_service.py` | ~725 | `rag/core.py` | `rag.core.scoring.max_display_score` |
  | 关键词匹配加成 | `*0.2` | `retrieval_service.py` | ~713 | `rag/core.py` | `rag.core.scoring.keyword_bonus_multiplier` |
  | 高相关性阈值 | `>0.8` | `scoring.py` | ~278 | `rag/core.py` | `rag.core.scoring.high_relevance_threshold` |

- [ ] **3.3 扫描年龄适配权重**

  | 配置项 | 当前值 | 来源文件 | 行号 | 目标配置模块 | 目标配置键 |
  |--------|--------|----------|------|-----------|-----------|
  | 年龄适配权重 | `0.7/0.3` | `retrieval_service.py` | ~504 | `rag/core.py` | `rag.core.scoring.age_fit_weights` |

### 4. P2 配置扫描 (文档处理与业务规则)

> **⚠️ 配置模块路径对齐说明**:
> - 元数据/分块参数 → 归入已有 `src/config/modules/rag/chunking.py`
> - 业务规则 → 归入 `src/config/modules/rag/rules.py`（通过 ConfigManager 存 MySQL，禁止本地 JSON 文件）

- [ ] **4.1 扫描元数据处理参数**

  | 配置项 | 当前值 | 来源文件 | 行号 | 目标配置模块 | 目标配置键 |
  |--------|--------|----------|------|-----------|-----------|
  | 元数据缓存大小 | `10000` | `metadata_extractor.py` | ~120 | `rag/chunking.py` | `rag.chunking.metadata.cache_max_size` |
  | 最小文本长度 | `10` | `metadata_extractor.py` | ~148 | `rag/chunking.py` | `rag.chunking.metadata.min_text_length` |
  | 文本截断长度 | `2000` | `metadata_extractor.py` | ~157 | `rag/chunking.py` | `rag.chunking.metadata.text_truncation_length` |
  | 最大主题数 | `8` | `metadata_extractor.py` | ~224 | `rag/chunking.py` | `rag.chunking.metadata.max_topics` |
  | 并行线程数 | `20` | `metadata_processor.py` | - | `rag/chunking.py` | `rag.chunking.metadata.max_workers` |

- [ ] **4.2 扫描分块处理参数**

  | 配置项 | 当前值 | 来源文件 | 行号 | 目标配置模块 | 目标配置键 |
  |--------|--------|----------|------|-----------|-----------|
  | 英文检测阈值 | `>0.7` | `metadata_processor.py` | - | `rag/chunking.py` | `rag.chunking.english_threshold` |
  | 分块合并倍率 | `1.2/1.5` | `metadata_processor.py` | - | `rag/chunking.py` | `rag.chunking.merge_ratio` |

- [ ] **4.3 扫描业务规则参数**

  | 配置项 | 当前值 | 来源文件 | 目标位置 |
  |--------|--------|----------|---------|
  | 年龄段划分 (tolerance/strictness/weight) | 硬编码字典 | `age_filter.py` | `ConfigManager` → `rag_rules_age_filter` |
  | 年龄边界和推荐规则 | 硬编码逻辑 | `child_development_engine.py` | `ConfigManager` → `rag_rules_age_boundaries` |

### 5. 配置清单整理

- [ ] **5.1 建立配置映射表**
  - 记录每个魔法值的来源文件、行号、当前值、目标配置键
  - 标注配置类型 (LLM 参数/RAG 阈值/文档处理/业务规则)

- [ ] **5.2 优先级分级依据**
  - **P0 (LLM 参数)**: 涉及 15+ 文件，60+ 处，迁移后实现全量热配置
  - **P1 (RAG 阈值)**: 直接影响检索和评分质量，需通过单元测试验证
  - **P2 (文档处理)**: 后台处理参数，迁移风险低

- [ ] **5.3 业务规则分离策略确认**
  - 仅将可配置参数外部化到 ConfigManager（MySQL 存储）
  - 保留核心算法逻辑在代码中，避免逻辑碎片化

### 6. 输出产物

- [ ] **6.1 魔法值完整清单** (Markdown 表格)
- [ ] **6.2 目标配置键映射表** (魔法值 → ConfigManager 键路径)
- [ ] **6.3 业务规则 Pydantic 模型草案** (`src/config/modules/rag/rules.py`)

---

## 验收标准

- [ ] 所有硬编码魔法值已识别并记录
- [ ] 每个魔法值的目标配置键已明确
- [ ] 业务规则分离策略经过团队确认
- [ ] 无遗漏的魔法值 (通过 grep 扫描验证)

---

**上一任务:** [03-prompt-validation.md](./03-phase-2b-03-prompt-validation.md)  
**下一任务:** [05-config-migration.md](./03-phase-2b-05-config-migration.md)
