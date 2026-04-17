# Phase 2B.1: 提示词扫描与盘点

> **状态:** ⏳ 待实现
> **前置任务:** [00-overview.md](./03-phase-2b-00-overview.md)

## 目标

全面扫描代码库中所有硬编码的提示词 (System Messages 和 PromptTemplate)，建立完整的提示词清单，并按优先级分级 (P0/P1/P2)。

## 实施任务

### 1. 扫描范围定义

- [ ] **1.1 定义扫描范围**
  - 核心节点目录: `src/core/nodes/`
  - 提示词文件: `src/core/prompts.py`
  - 服务层: `src/service/`
  - 核心模块: `src/core/` (query_router, metadata_extractor, layered_content_generator 等)

- [ ] **1.2 定义提示词识别规则**
  - 多行字符串中的系统指令 (通常包含 "你是一个..."、"请分析..." 等指令性语言)
  - `PromptTemplate` 或类似模板对象
  - LLM 调用中的 `system` 角色消息
  - 包含占位符 (如 `{variable}`) 的模板字符串

- [ ] **1.3 执行 grep 扫描命令**
  ```bash
  # 扫描中文系统指令模式
  grep -rn "你是一个\|请分析\|请根据\|请以" src/ --include="*.py" | grep -v test | grep -v __pycache__

  # 扫描 PromptTemplate 对象
  grep -rn "PromptTemplate\|ChatPromptTemplate\|SystemMessagePromptTemplate" src/ --include="*.py" | grep -v test

  # 扫描 system 角色消息
  grep -rn '"system"\|role.*=.*"system"\|SystemMessage' src/ --include="*.py" | grep -v test

  # 扫描占位符模板
  grep -rn '\{[a-z_]\+\}' src/core/prompts.py src/core/nodes/ --include="*.py"

  # 扫描 prompts.py 中的常量定义
  grep -rn "^[A-Z_]\+.*=\s*['\"]" src/core/prompts.py
  ```

### 2. 全代码扫描执行

- [ ] **2.1 扫描 P0 - 节点级系统提示词 (核心评估流程)**

  | Prompt Key | 来源文件 | 行号 | 说明 | 占位符 [待扫描确认] |
  |------------|----------|------|------|--------|
  | `assessment_system` | `src/core/nodes/assessment.py` | ~67 | 儿童发展评估专家系统消息 | `{child_age}`, `{issues}` [待确认] |
  | `reporting_system` | `src/core/prompts.py` + `src/core/nodes/reporting.py` | 182-297, 226 | 报告生成专家系统消息 | `{child_state}`, `{evaluation_result}`, `{retrieved_docs}` [待确认] |
  | `validation_system` | `src/core/prompts.py` | 102-106 | 数据校验系统消息 | `{proposed_plan}` [待确认] |
  | `intensity_inference` | `src/core/prompts.py` | 108-120 | 活动强度推断 | `{activity_name}`, `{child_age}` [待确认] |
  | `category_inference` | `src/core/prompts.py` | 122-138 | 活动类别推断 | `{activity_name}` [待确认] |

- [ ] **2.2 扫描 P1 - RAG 检索相关提示词**

  | Prompt Key | 来源文件 | 行号 | 说明 | 占位符 [待扫描确认] |
  |------------|----------|------|------|--------|
  | `rag_query_template` | `src/core/prompts.py` | ~6 | 检索节点查询模板 | `{issues}`, `{goals}` [待确认] |
  | `query_rewrite` | `src/core/prompts.py` + `src/service/retrieval_service.py` | 8-19, 830-832 | 查询重写 | `{query}` [待确认] |
  | `synonym_expansion` | `src/core/prompts.py` + `src/service/retrieval_service.py` | 21-46, 949-951 | 同义词扩展 | `{query}`, `{domain}` [待确认] |
  | `query_classification` | `src/core/query_router.py` | 174-194, 208-209 | 查询分类 | `{query}` [待确认] |

- [ ] **2.3 扫描 P2 - 元数据与内容生成提示词**

  | Prompt Key | 来源文件 | 行号 | 说明 | 占位符 [待扫描确认] |
  |------------|----------|------|------|--------|
  | `metadata_extraction` | `src/core/prompts.py` + `src/core/metadata_extractor.py` | 52-73, 187 | 元数据提取 | `{content}` [待确认] |
  | `test_case_draft_generation` | `src/core/prompts.py` | 75-95 | 测试用例草稿生成 | `{chapter_content}`, `{domain}`, `{age}` [待确认] |
  | `layered_content_l0` | `src/core/layered_content_generator.py` | 155-159 | L0 摘要生成 | `{content}` [待确认] |
  | `layered_content_l1` | `src/core/layered_content_generator.py` | 187-191 | L1 概览生成 | `{content}` [待确认] |
  | `layered_content_batch` | `src/core/layered_content_generator.py` | 267-274 | 批量摘要生成 | `{contents}` [待确认] |
  | `layered_content_combined` | `src/core/layered_content_generator.py` | 355-361 | L0+L1 联合生成 | `{content}` [待确认] |

### 3. 提示词清单整理

- [ ] **3.1 建立提示词映射表**
  - 记录每个提示词的 Key、来源文件、行号、内容摘要、占位符列表
  - 标注当前使用方式 (直接硬编码 / 通过 prompts.py 集中管理)

- [ ] **3.2 优先级分级依据**
  - **P0 (核心评估流程)**: 直接影响用户可见的评估报告质量，迁移风险高但收益最大
  - **P1 (RAG 检索)**: 影响检索质量和同义词扩展，迁移风险中等
  - **P2 (元数据与内容生成)**: 后台处理流程，迁移风险低，可批量处理

- [ ] **3.3 占位符一致性检查**
  - 对比同一提示词在不同文件中的占位符是否一致
  - 记录需要统一的占位符命名差异

### 4. 输出产物

- [ ] **4.1 提示词完整清单** (Markdown 表格)
- [ ] **4.2 占位符映射表** (Prompt Key → Variables 列表)
- [ ] **4.3 迁移优先级确认** (P0/P1/P2 分组)

---

## 验收标准

- [ ] 所有硬编码提示词已识别并记录
- [ ] 每个提示词的占位符已完整列出
- [ ] 优先级分级合理且经过团队确认
- [ ] 无遗漏的提示词 (通过 grep 扫描验证)

---

**上一任务:** [00-overview.md](./03-phase-2b-00-overview.md)  
**下一任务:** [02-prompt-migration.md](./03-phase-2b-02-prompt-migration.md)
