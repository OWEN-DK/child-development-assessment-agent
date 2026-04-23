# 需求方案：多维度测试用例草稿全覆盖生成

> **文档版本**: v3.1  
> **创建日期**: 2026-04-19  
> **更新日期**: 2026-04-19  
> **状态**: 已审查通过  

---

## 一、需求背景

### 1.1 当前问题

| 问题 | 代码位置 | 根因 |
|------|----------|------|
| 仅生成 10 个草稿 | `rag_test_controller.py:506` | `count=10` 硬编码 |
| 草稿类型单一 | `draft_service.py:190` | `target_domains` 固定为 `["感觉统合"]` |
| 年龄范围固定 | `rag_test_controller.py:505` | `age_range=(0, 6)` 硬编码 |
| 未使用配置系统 | 同上 | 配置中有完整维度定义但未使用 |

### 1.2 用户目标

- 上传书籍后，自动生成**大量、多维度、全覆盖**的测试用例草稿
- 后台异步执行，用户无需等待
- 覆盖所有发展领域、0-18 岁全年龄段、多种查询类型和难度
- 生成数量越多越好，不固定上限

---

## 二、维度设计

### 2.1 核心维度矩阵

| 维度 | 分类 | 数量 | 说明 |
|------|------|------|------|
| **发展领域** | 粗大动作、精细动作、语言发展、认知能力、社交情感、感觉统合 | 6 | 儿童发展的核心能力维度 |
| **年龄段** | 0-1岁、1-3岁、3-6岁、6-9岁、9-12岁、12-15岁、15-18岁 | 7 | 左闭右开区间，月龄精确表示（行业标准） |
| **查询类型** | 事实性查询、比较性查询、方案性查询、原因分析性查询 | 4 | 模拟家长/专业人士的不同提问方式 |
| **难度级别** | 入门级、中级、高级 | 3 | 测试用例的复杂度和专业深度 |

**年龄段精确定义**（左闭右开，避免边界歧义）：

| 年龄段标签 | 月龄范围 | 说明 |
|-----------|---------|------|
| 0-1岁 | [0, 12) | 婴儿期 |
| 1-3岁 | [12, 36) | 幼儿期 |
| 3-6岁 | [36, 72) | 学龄前期 |
| 6-9岁 | [72, 108) | 学龄初期 |
| 9-12岁 | [108, 144) | 学龄中期 |
| 12-15岁 | [144, 180) | 青春期早期 |
| 15-18岁 | [180, 216) | 青春期中后期 |

### 2.2 分批生成策略

**核心思想**：不一次性生成全部草稿，改为**用户自定义组合**，按需生成。

**术语定义**（重要，全文统一）：

| 术语 | 定义 | 示例 |
|------|------|------|
| **组合** | 1 个领域 × 1 个年龄段 | "感觉统合" × "3-6岁" |
| **草稿** | 单个测试用例草稿 | 1 个 query + answer |
| **任务** | 1 个草稿的生成单元 | 生成 1 个草稿 |
| **执行批次** | 底层优化，多个任务打包一次 LLM 调用（对用户透明） | 每 5 个任务打包一次 |

**组合定义**：
- 1 个组合 = N 个草稿（N 由用户指定，默认 3，范围 1-10）
- 单组合 TOKEN 消耗：约 2,100（输入）+ N × 300（输出）
- 单组合成本：约 ¥0.003-0.01
- 单组合时间：约 5-15 秒
- 执行批次大小：5 个任务/批（底层优化，用户无感知）

### 2.3 系统默认配置

**配置位置**：系统配置页面 `/system-config` → `草稿生成` 模块

**原则**：所有可配置参数必须在系统配置中定义默认值，前端交互面板读取这些默认值进行初始化。

| 配置项 | 配置键 | 默认值 | 说明 |
|--------|--------|--------|------|
| **默认领域** | `draft.default_domains` | `["感觉统合"]` | 上传书籍后默认选中的领域（可多选） |
| **默认年龄段** | `draft.default_age_stages` | `["3-6岁"]` | 上传书籍后默认选中的年龄段（可多选） |
| **默认每个组合草稿数** | `draft.default_drafts_per_combination` | `3` | 范围 1-10 |
| **默认查询类型** | `draft.default_query_types` | `["事实性查询", "比较性查询", "方案性查询"]` | 默认勾选的查询类型 |
| **默认难度级别** | `draft.default_difficulty_levels` | `["入门级", "中级", "高级"]` | 默认勾选的难度 |
| **默认模型** | `draft.default_model` | `qwen-plus` | 必须是在系统配置中已配置成本的模型 |
| **去重阈值** | `draft.deduplication_threshold` | `0.85` | 语义相似度阈值 |
| **执行批次大小** | `draft.batch_size` | `5` | 底层优化，每批任务数打包一次 LLM 调用 |
| **组合间隔秒数** | `draft.combination_interval_seconds` | `1` | 组合间间隔，控制 CPU 和 API 频率 |
| **最大并发任务数** | `draft.max_concurrent_tasks` | `1` | 同一文档同时只允许 1 个生成任务 |
| **TOKEN 消耗上限** | `draft.max_tokens_per_generation` | `500000` | 单次生成任务上限，防止费用失控 |
| **内存上限 MB** | `draft.max_memory_mb` | `500` | 生成任务内存硬上限 |
| **LLM 最大重试次数** | `draft.max_llm_retries` | `2` | 单组合 LLM 调用失败重试次数 |

### 2.4 用户交互设计

**前端页面**：草稿生成配置面板（读取系统默认配置初始化）

```
┌─────────────────────────────────────────────────┐
│  📝 生成测试用例草稿                              │
├─────────────────────────────────────────────────┤
│  1. 选择发展领域（可多选）                         │
│  ☑ 粗大动作  ☑ 精细动作  ☑ 语言发展               │
│  ☑ 认知能力  ☑ 社交情感  ☑ 感觉统合               │
│                                                 │
│  2. 选择年龄段（可多选）                           │
│  ☑ 0-1岁  ☑ 1-3岁  ☑ 3-6岁  ☑ 6-9岁             │
│  ☑ 9-12岁  ☑ 12-15岁  ☑ 15-18岁                 │
│                                                 │
│  3. 每个组合生成数量                               │
│  [  3  ] 个（范围 1-10，每个领域×年龄段组合）      │
│                                                 │
│  ─────────────────────────────────────────────  │
│  📊 预估信息                                      │
│  • 选中领域：6 个                                 │
│  • 选中年龄段：7 个                               │
│  • 组合数量：42 个（6×7）                         │
│  • 每个组合草稿数：3 个                           │
│  • 预计生成：126 个草稿（42×3）                   │
│  • 预计 TOKEN：约 126,000                         │
│  • 预计成本：约 ¥0.13-0.30                        │
│  • 预计时间：约 10-15 分钟                        │
│                                                 │
│  [ 取消 ]                    [ 开始生成 ]          │
│                                                 │
│  ▼ 高级设置（默认折叠，点击展开）                   │
│  ┌─────────────────────────────────────────────┐│
│  │ 模型选择：[qwen-plus ▼]                      ││
│  │   （仅显示已配置成本的模型）                    ││
│  │                                             ││
│  │ 查询类型：☑ 事实性 ☑ 比较性 ☑ 方案性 ☐ 原因   ││
│  │   （自定义，默认从系统配置读取）                ││
│  │                                             ││
│  │ 难度级别：☑ 入门 ☑ 中级 ☑ 高级                ││
│  │   （自定义，默认从系统配置读取）                ││
│  │                                             ││
│  │ 去重阈值：[0.85]（范围 0.7-0.95）             ││
│  │                                             ││
│  │ 组合间隔：[1] 秒（范围 0-5）                  ││
│  │                                             ││
│  │ 生成模式：(•) 追加  ( ) 覆盖                  ││
│  └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

**说明**：
- 主面板的领域、年龄段、每个组合草稿数从系统配置 `draft.default_*` 读取默认值
- 查询类型和难度从系统配置 `draft.default_query_types` 和 `draft.default_difficulty_levels` 读取默认值，高级设置中可自定义
- 模型选择仅显示已配置成本的模型

**计算逻辑**（已修正歧义）：
```
组合数 = 领域数 × 年龄段数
总草稿数 = 组合数 × 每个组合草稿数

# TOKEN 预估（基于分组件计量，实测校准）
# 注意：输入 TOKEN 按组合计算，输出 TOKEN 按草稿计算
单组合输入 TOKEN = 500（系统提示词）+ 1500（书籍内容片段）+ 100（变量）= 2,100
单草稿输出 TOKEN = 300
预计 TOKEN = 组合数 × 单组合输入 TOKEN + 总草稿数 × 单草稿输出 TOKEN

# 示例：6 领域 × 7 年龄段 × 3 草稿 = 126 草稿
# 预计 TOKEN = 42 × 2,100 + 126 × 300 = 88,200 + 37,800 = 126,000

预计成本 = 预计 TOKEN / 1,000,000 × 当前模型单价（从系统配置读取）
预计时间 = 组合数 × 15 秒（每组合串行，约 15 秒/组合）
```

### 2.5 默认组合策略

**上传书籍时自动生成**：
- 解析书籍内容，识别主领域（如"感觉统合"）
- 识别书籍适用的核心年龄段（如 3-6 岁）
- 生成 1 个默认组合：主领域 × 核心年龄段 × 3 草稿（数量从系统配置 `draft.default_drafts_per_combination` 读取）
- 提示用户："已生成 3 个草稿，点击[生成更多]可自定义配置"

### 2.6 模型选择约束

**规则**：模型下拉框仅显示在系统配置中已配置成本的模型。

**实现逻辑**：
```python
async def get_available_models() -> List[ModelOption]:
    """获取可用的草稿生成模型列表"""
    all_models = await get_all_llm_models()
    
    # 过滤：仅返回已配置成本的模型
    available = [
        m for m in all_models
        if m.cost_input_per_million is not None 
        and m.cost_output_per_million is not None
        and m.cost_input_per_million > 0
        and m.cost_output_per_million > 0
    ]
    
    # 降级策略：如果没有模型配置成本，返回空列表并提示
    if not available:
        logger.warning("No models with cost configuration found")
        return []
    
    return [
        ModelOption(
            key=m.model_key,
            label=f"{m.name}（输入¥{m.cost_input_per_million}/百万，输出¥{m.cost_output_per_million}/百万）",
            disabled=False
        )
        for m in available
    ]
```

**前端展示**：
- 未配置成本的模型不显示在下拉框中
- 模型选项显示成本信息，方便用户决策
- 默认选中系统配置 `draft.default_model` 指定的模型
- 如果默认模型未配置成本，自动选择第一个可用模型
- 如果没有任何模型配置成本，下拉框显示"请先在系统配置中设置模型成本"

---

## 三、生成策略

### 3.1 草稿分配规则

**策略**：轮询分配 + 优先覆盖（业内通用最佳实践）

每种核心组合（领域 + 年龄段）的草稿分配采用**轮询策略**，保证每种查询类型和难度均匀分布：

| 草稿序号 | 查询类型 | 难度 | 说明 | 示例 |
|----------|----------|------|------|------|
| 第 1 个 | 事实性查询 | 入门级 | 基础概念认知 | "什么是前庭觉？" |
| 第 2 个 | 比较性查询 | 中级 | 对比分析 | "前庭觉和本体觉的区别？" |
| 第 3 个 | 方案性查询 | 高级 | 解决方案 | "如何改善前庭觉敏感？" |
| 第 4 个 | 原因分析性查询 | 入门级 | 成因分析 | "为什么孩子会前庭觉敏感？" |
| 第 5 个 | 事实性查询 | 中级 | 深度概念 | "前庭觉的神经机制是什么？" |
| 第 6 个 | 比较性查询 | 高级 | 场景对比 | "前庭觉敏感与迟钝的表现差异？" |
| 第 7 个 | 方案性查询 | 入门级 | 简单训练 | "家庭前庭觉训练小游戏" |
| 第 8 个 | 原因分析性查询 | 中级 | 机制分析 | "前庭觉发育迟缓的成因？" |
| 第 9 个 | 事实性查询 | 高级 | 专业理论 | "前庭觉的神经通路解析" |
| 第 10 个 | 比较性查询 | 入门级 | 基础对比 | "前庭觉与触觉的关系" |

**轮询算法**：
```python
QUERY_TYPES = ["事实性查询", "比较性查询", "方案性查询", "原因分析性查询"]
DIFFICULTIES = ["入门级", "中级", "高级"]

def assign_draft_config(draft_index: int):
    """轮询分配查询类型和难度，保证多样性"""
    query_type = QUERY_TYPES[draft_index % len(QUERY_TYPES)]
    difficulty = DIFFICULTIES[draft_index % len(DIFFICULTIES)]
    return query_type, difficulty
```

**优先覆盖策略**（当用户选择多种查询类型和难度时）：
1. 优先保证每种选中的查询类型和难度至少出现一次
2. 剩余草稿按轮询策略随机填充
3. 最终打乱顺序，避免模式化

### 3.2 书籍内容适配策略

**问题**：如果书籍只涉及"感觉统合"，生成"语言发展"的草稿是否合理？

**策略**：

1. **主领域优先**：从书籍内容中提取主题，识别主要涉及的领域
2. **默认生成主领域组合**：上传书籍后，仅生成主领域 × 核心年龄段的 1 个组合（3 个草稿）
3. **用户手动扩展**：用户可在界面选择其他领域/年龄段，手动触发更多组合
4. **内容映射**：生成时注入书籍相关章节内容，确保草稿与书籍有合理关联

**技术方案**：轻量关键词匹配 + LLM 兜底（混合策略）

```python
async def extract_book_metadata(text: str) -> BookMetadata:
    """提取书籍主领域和适用年龄段"""
    
    # Step 1: 关键词快速匹配（覆盖 80% 场景，<1ms）
    domain_keywords = {
        "感觉统合": ["前庭", "本体觉", "触觉", "感觉统合", "感统"],
        "粗大动作": ["跑", "跳", "爬", "平衡", "大肌肉"],
        "精细动作": ["抓握", "捏", "剪纸", "写字", "手眼协调"],
        # ...
    }
    
    scores = {}
    for domain, keywords in domain_keywords.items():
        scores[domain] = sum(text.count(kw) for kw in keywords)
    
    primary_domain = max(scores, key=scores.get)
    
    # Step 2: LLM 辅助确认（关键词置信度低时触发）
    if max(scores.values) < 10:  # 阈值可调
        llm_result = await llm.classify_domain(text[:2000])
        primary_domain = llm_result.domain
    
    # Step 3: 年龄段提取（正则 + LLM）
    age_pattern = r"(\d+)[\-~至](\d+)\s*岁"
    ages = re.findall(age_pattern, text)
    age_range = parse_age_range(ages)
    
    return BookMetadata(domain=primary_domain, age_range=age_range)
```

**优势**：
- 成本极低（单组合 ¥0.003-0.01）
- 用户可控，按需生成
- 草稿质量更高（聚焦书籍核心内容）
- 关键词匹配成本低，LLM 仅兜底模糊场景

---

## 四、技术实现方案

### 4.1 架构设计

```
上传书籍
  ↓
[Step 1] 解析书籍内容
  - 提取全文文本
  - 分析章节结构
  - 识别主领域和核心年龄段（关键词匹配 + LLM 兜底）
  ↓
[Step 2] 生成默认组合（1 个）
  - 主领域 × 核心年龄段 × 3 草稿
  - 约 3 个草稿，15-30 秒完成
  ↓
[Step 3] 用户自定义生成（可选）
  - 前端选择领域、年龄段、每个组合数量
  - 计算预估 TOKEN、成本、时间
  - 用户确认后，后台异步执行
  - SSE 推送进度（支持断线重连）
  ↓
[Step 4] 去重与质量过滤
  - 与历史草稿去重（阈值 0.85）
  - 相关性过滤（与书籍内容的相关度）
  ↓
[Step 5] 幂等入库保存
  - 业务唯一键约束（doc_id + domain + age_stage_label + draft_index）
  - 批量写入数据库，支持覆盖/追加模式
  - 记录生成参数和来源
  ↓
[Step 6] SSE 推送完成通知
```

### 4.2 幂等性设计

**业务唯一键**：同一文档、同领域、同年龄段组合、同草稿索引只保留一份草稿

```python
# 数据库约束（增加 draft_index 支持每个组合多草稿）
class TestCaseDraft(Base):
    __table_args__ = (
        UniqueConstraint(
            'doc_id', 'domain', 'age_stage_label', 'draft_index',
            name='uk_draft_combination_index'
        ),
    )
    
    doc_id = Column(String(36))
    domain = Column(Enum(TestDomain))
    age_stage_label = Column(String(20))  # 如 "3-6岁"
    draft_index = Column(Integer)          # 草稿索引（0, 1, 2...）
    batch_id = Column(String(36))         # 生成批次追踪
    version = Column(Integer, default=1)  # 乐观锁

# 插入逻辑（支持覆盖/追加模式）
async def save_drafts(drafts: List[Draft], mode: str = "append"):
    for draft in drafts:
        try:
            if mode == "overwrite":
                await db.execute(
                    insert(TestCaseDraft)
                    .values(**draft.dict())
                    .on_duplicate_key_update(
                        query=draft.query,
                        description=draft.description,
                        version=TestCaseDraft.version + 1
                    )
                )
            else:  # append
                await db.execute(insert(TestCaseDraft).values(**draft.dict()))
        except IntegrityError:
            logger.info(f"Draft exists, skipped: {draft.doc_id}/{draft.domain}/{draft.age_stage_label}/{draft.draft_index}")
```

**去重与幂等性协调**：
1. 去重在幂等性判断**之前**执行
2. 去重后的草稿重新编号 `draft_index`（从 0 开始连续）
3. 去重仅过滤"与历史草稿"的重复，不过滤"当前组合内"的重复（组合内由 LLM 保证多样性）

**前端交互**：
- 重复触发时提示：「该组合已存在 N 个草稿，是否覆盖？」
- 提供"追加模式"和"覆盖模式"选择

### 4.3 并发控制

**同一文档同时只允许 1 个生成任务**：

```python
import redis

async def acquire_generation_lock(doc_id: str, ttl: int = 3600) -> bool:
    """获取分布式锁，防止同一文档并发生成"""
    lock_key = f"draft_gen:{doc_id}"
    return redis_client.set(lock_key, "1", nx=True, ex=ttl)

async def release_generation_lock(doc_id: str):
    """释放分布式锁"""
    redis_client.delete(f"draft_gen:{doc_id}")
```

### 4.4 关键修改点

| 文件 | 修改内容 | 说明 |
|------|----------|------|
| `config/modules/rag/testing.py` | 扩展年龄段为 0-18 岁（7 个阶段，月龄精确表示），新增 13 项配置键 | 配置层 |
| `controller/rag_test_controller.py` | 上传接口改为读取配置，动态计算数量，增加并发控制 | 接口层 |
| `service/rag_test/draft_service.py` | 重构 `generate_test_case_drafts`，支持矩阵生成、去重、轮询分配 | 核心逻辑 |
| `core/prompts_fallback.py` | Prompt 增加查询类型、难度变量，增加 JSON 格式约束 | 提示词 |
| `schemas/test_case.py` | `GenerationParams` 增加可选的维度组合参数，增加幂等性字段（draft_index） | 数据模型 |
| `service/rag_test/deduplication_service.py` | 新增：去重服务（与历史草稿比对，阈值从系统配置读取） | 新增服务 |
| `service/rag_test/book_metadata_service.py` | 新增：书籍内容解析服务（关键词匹配 + LLM 兜底） | 新增服务 |

### 4.5 异步执行设计

```python
# 完整异步执行流程（含错误处理、去重、SSE 推送）
async def generate_drafts_matrix(
    doc_id: str,
    params: GenerationParams,
    mode: str = "append"
):
    import time
    start_time = time.time()
    
    # 0. 并发控制
    if not await acquire_generation_lock(doc_id):
        raise AppException("该文档正在生成草稿，请稍后重试")
    
    try:
        config = await get_config()
        deduplicator = DraftDeduplicator(threshold=config.draft_deduplication_threshold)
        batch_size = config.draft_batch_size  # 从系统配置读取，默认 5
        
        # 1. 生成任务矩阵（轮询分配查询类型和难度）
        tasks = []
        for domain in params.domains:
            for age_stage in params.age_stages:
                draft_configs = generate_draft_configs(
                    count=params.drafts_per_combination,
                    query_types=params.query_types,
                    difficulties=params.difficulties
                )
                for idx, config_item in enumerate(draft_configs):
                    tasks.append({
                        "domain": domain,
                        "age_stage": age_stage,
                        "draft_index": idx,
                        **config_item,
                    })
        
        # 2. 按组合分组执行（前端展示"组合进度"）
        total_combinations = len(params.domains) * len(params.age_stages)
        completed_combinations = 0
        total_generated = 0
        
        await sse_publish("draft_generation_started", {
            "total_combinations": total_combinations,
            "total_drafts": len(tasks),
            "mode": mode,
        })
        
        # 按组合分组
        for domain in params.domains:
            for age_stage in params.age_stages:
                combination_tasks = [
                    t for t in tasks
                    if t["domain"] == domain and t["age_stage"] == age_stage
                ]
                
                # 2.1 执行批次（底层优化，每 batch_size 个任务打包一次 LLM 调用）
                for i in range(0, len(combination_tasks), batch_size):
                    batch = combination_tasks[i:i+batch_size]
                    new_drafts = await generate_batch(doc_id, batch)
                    
                    # 2.2 与历史草稿去重（不过滤组合内重复）
                    final_drafts = [
                        d for d in new_drafts
                        if deduplicator.deduplicate_final(d)
                    ]
                    
                    # 2.3 重新编号 draft_index
                    for idx, draft in enumerate(final_drafts):
                        draft.draft_index = idx
                    
                    # 2.4 幂等入库
                    await save_drafts(final_drafts, mode=mode)
                    total_generated += len(final_drafts)
                
                completed_combinations += 1
                
                # 2.5 SSE 推送组合进度
                await sse_publish("draft_combination_progress", {
                    "current_combination": completed_combinations,
                    "total_combinations": total_combinations,
                    "domain": domain,
                    "age_stage": age_stage,
                    "generated": total_generated,
                })
                
                # 2.6 组合间间隔，控制 CPU 和 API 调用频率
                await asyncio.sleep(config.draft_combination_interval_seconds)
        
        await sse_publish("draft_generation_completed", {
            "total": total_generated,
            "duration": calculate_duration(start_time),
        })
        
    except Exception as e:
        await sse_publish("draft_generation_failed", {"error": str(e)})
        raise
    finally:
        await release_generation_lock(doc_id)
```

**错误处理策略**：
- LLM 调用失败：最多重试 2 次（从系统配置 `draft.max_llm_retries` 读取），使用 `json-repair` 库修复 JSON
- 格式错误：标记 `status=failed`，供人工处理
- 单组合失败：跳过当前组合，记录日志，继续下一组合

---

## 五、Prompt 设计

### 5.1 增强版 Prompt 模板

```
你是儿童发展、感觉统合、教育心理学领域的专业测试用例设计师。
请根据提供的文档内容，生成 RAG（检索增强生成）测试用例草稿。

文档内容:
{text}

生成约束：
- 目标领域：{domain}（必须围绕此领域生成）
- 适用年龄段：{age_min}-{age_max}岁（查询和答案必须符合此年龄段特征）
- 查询类型：{query_type}（{query_type_desc}）
- 难度级别：{difficulty}（{difficulty_desc}）

查询类型说明：
- 事实性查询：是什么/有什么/定义类问题
- 比较性查询：区别/对比/优劣类问题
- 方案性查询：怎么做/如何改善/训练方法类问题
- 原因分析性查询：为什么/成因/机制类问题

难度说明：
- 入门级：基础概念认知，适合家长日常提问
- 中级：场景应用和对比分析，适合有一定知识的家长
- 高级：专业深度和机制分析，适合专业人士

返回 JSON 结构：
{"drafts": [{"age": 月龄, "query": "问题", "description": "意图说明", ...}]}
```

### 5.2 差异化保障

| 策略 | 说明 |
|------|------|
| **Prompt 注入差异化** | 每个组合注入不同的领域、年龄段、查询类型、难度 |
| **温度参数调整** | temperature 设为 0.8-0.9，增加多样性 |
| **JSON 格式约束** | Prompt 明确 JSON Schema，使用 `json-repair` 库兜底解析失败 |
| **去重** | 与历史草稿去重（阈值 0.85），组合内由 LLM 保证多样性 |
| **轮询分配** | 查询类型和难度按轮询策略分配，保证多样性 |

### 5.3 LLM 输出解析与容错

```python
from json_repair import repair_json

async def parse_llm_response(llm_output: str, max_retries: int = 2) -> List[Draft]:
    """解析 LLM 输出，支持 JSON 修复和重试"""
    
    for attempt in range(max_retries + 1):
        try:
            # 1. 尝试直接解析
            data = json.loads(llm_output)
            return validate_and_convert_drafts(data["drafts"])
            
        except (json.JSONDecodeError, KeyError, ValidationError) as e:
            if attempt < max_retries:
                # 2. 使用 json-repair 修复
                repaired = repair_json(llm_output)
                data = json.loads(repaired)
                return validate_and_convert_drafts(data["drafts"])
            else:
                # 3. 重试耗尽，标记为失败
                logger.error(f"LLM output parse failed: {e}")
                return []  # 返回空列表，上层标记 status=failed
```

---

## 六、执行流程与进度展示

### 6.1 SSE 事件设计

| 事件类型 | 数据 | 说明 |
|----------|------|------|
| `draft_generation_started` | `{total_combinations: 42, total_drafts: 126, mode: "append"}` | 任务开始 |
| `draft_combination_progress` | `{current_combination: 5, total_combinations: 42, domain: "感觉统合", age_stage: "3-6岁", generated: 15}` | 组合进度（前端展示） |
| `draft_generated` | `{draft_id: "xxx", domain: "感觉统合", age_stage: "3-6岁", draft_index: 0, query_type: "事实性查询"}` | 单个草稿完成 |
| `draft_deduplication` | `{removed: 12, threshold: 0.85, reason: "语义相似度超限"}` | 去重结果 |
| `draft_generation_completed` | `{total: 114, deduplicated: 12, duration: "12m30s"}` | 任务完成 |
| `draft_generation_failed` | `{error: "LLM API 超时", combination: "感觉统合×3-6岁", retry_count: 2}` | 组合失败 |
| `draft_generation_cancelled` | `{total: 45, reason: "用户取消"}` | 任务取消 |

**说明**：
- 前端展示"组合进度"，不暴露底层"执行批次"优化
- `draft_combination_progress` 是前端进度条的主要数据源

**SSE 断线重连机制**：
- 前端实现指数退避重连（1s → 2s → 4s → 8s → 16s）
- 后端支持 `?resume_from=batch_id` 参数，断点续传
- 任务状态持久化到 Redis，重连后恢复进度

### 6.2 前端展示

```
草稿生成中...
进度：████████░░░░░░░░ 45% (19/42 组合)
当前：正在生成 [感觉统合] [6-9岁] 组合
已生成：57 个草稿
预计剩余时间：约 8 分钟
```

---

## 七、验收标准

| 验收项 | 标准 |
|--------|------|
| **单组合草稿数** | 每个组合生成 N 个草稿（N 由用户指定，范围 1-10，默认值从系统配置读取） |
| **默认组合** | 上传书籍后自动生成 1 个组合（主领域 × 核心年龄段 × 系统配置的默认草稿数） |
| **领域选择** | 用户可选择 6 个领域中的任意组合（支持全选/反选，默认值从系统配置读取） |
| **年龄选择** | 用户可选择 7 个年龄段中的任意组合（支持全选/反选，默认值从系统配置读取） |
| **数量配置** | 用户可设置每个领域×年龄段组合生成的草稿数量（1-10 个） |
| **查询类型覆盖** | 每个组合覆盖用户选择的查询类型，优先保证每种类型至少出现一次 |
| **难度覆盖** | 每个组合覆盖用户选择的难度级别，优先保证每种难度至少出现一次 |
| **预估信息** | 前端实时显示预计草稿数、TOKEN、成本、时间（基于分组件计量公式，成本从系统配置读取） |
| **去重效果** | 与历史草稿去重：阈值 0.85（可从系统配置调整），组合内由 LLM 保证多样性 |
| **异步执行** | 生成接口立即返回，后台执行，SSE 推送组合进度 |
| **失败处理** | 单组合失败不影响其他组合，LLM 调用最多重试 2 次（可从系统配置调整） |
| **成本控制** | 单组合 TOKEN 消耗 < 5,000，成本 < ¥0.01 |
| **幂等性** | 同一组合重复触发不产生重复草稿，支持覆盖/追加模式，唯一键 `(doc_id, domain, age_stage_label, draft_index)` |
| **并发控制** | 同一文档同时只允许 1 个生成任务（Redis 分布式锁） |
| **取消机制** | 提供取消接口，已完成草稿保留，标记任务为 `cancelled` |
| **断线重连** | SSE 断线后支持指数退避重连，断点续传进度 |
| **系统配置** | 所有默认参数必须在系统配置页面可配置（13 项配置键） |
| **高级设置** | 上传书籍时的高级设置面板默认折叠，点击展开后显示查询类型/难度自定义 |
| **模型选择约束** | 高级设置中模型下拉框仅显示已配置成本的模型，未配置成本的不显示 |
| **成本计算** | 预估成本必须使用系统配置中当前选中模型的实际单价计算 |
| **前端进度展示** | 前端展示"组合进度"，不暴露底层"执行批次"优化 |

---

## 八、风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| **LLM 调用成本高** | 费用增加 | 使用 qwen-plus 等低成本模型，批量生成，文档内容截断至 4000 字 |
| **生成时间过长** | 用户体验差 | 后台异步 + SSE 进度推送，用户可离开页面，支持断线重连 |
| **草稿质量参差** | 测试集质量下降 | 去重 + 质量过滤 + 人工审核环节 |
| **书籍内容不足** | 某些领域草稿不相关 | 允许生成"弱相关"草稿，测试系统边界，关键词匹配确保主领域优先 |
| **并发限制** | LLM API 限流 | 组合串行，控制并发数，组合间间隔 1-2 秒 |
| **LLM 输出格式不稳定** | 解析失败 | 使用 `json-repair` 库 + 最多 2 次重试（系统配置可调）+ 失败草稿标记为 `status=failed` |
| **SSE 连接断开** | 进度丢失 | 前端指数退避重连 + 后端断点续传 + 任务状态持久化到 Redis |
| **并发冲突** | 同一文档多任务竞态 | Redis 分布式锁，同一文档同时只允许 1 个生成任务 |

---

## 九、实施计划

| 阶段 | 工作内容 | 预计工时 |
|------|----------|----------|
| **Phase 1** | 系统配置模块（13 项草稿生成配置键定义、MySQL 表结构） | 0.5h |
| **Phase 2** | 配置调整（年龄段扩展为月龄精确表示、数量计算公式修正） | 0.5h |
| **Phase 3** | Prompt 增强（查询类型、难度变量、JSON Schema 约束） | 0.5h |
| **Phase 4** | 草稿生成服务重构（矩阵生成逻辑、轮询分配策略、按组合执行） | 2h |
| **Phase 5** | 控制器适配（读取配置、动态参数、并发控制） | 0.5h |
| **Phase 6** | SSE 进度事件增强（组合进度、断线重连、断点续传支持） | 0.5h |
| **Phase 7** | 去重服务实现（与历史草稿比对，阈值 0.85，重新编号 draft_index） | 1h |
| **Phase 8** | 书籍内容解析服务（关键词匹配 + LLM 兜底） | 0.5h |
| **Phase 9** | 幂等性设计（业务唯一键 `doc_id+domain+age_stage_label+draft_index`、乐观锁、覆盖/追加模式） | 0.5h |
| **Phase 10** | LLM 输出解析容错（json-repair、重试机制） | 0.5h |
| **Phase 11** | 前端系统配置页面（草稿生成模块 13 项配置表单） | 1h |
| **Phase 12** | 前端草稿生成面板（默认配置加载 + 高级设置折叠面板、查询类型/难度自定义） | 1h |
| **Phase 13** | 模型选择约束（过滤未配置成本的模型、降级策略） | 0.5h |
| **Phase 14** | 测试与验证（单元测试、集成测试、TOKEN 基准校准） | 1.5h |

**总计**：约 11 小时

---

## 十、资源控制策略

### 10.1 CPU 占用控制

| 策略 | 说明 | 预期效果 |
|------|------|----------|
| **组合串行执行** | 每个组合串行调用 LLM，组合间间隔 1-2 秒 | CPU 峰值 < 30% |
| **文本分块加载** | 书籍内容按 4000 字分块，按需加载到内存 | 避免全文加载导致 CPU 飙升 |
| **异步 IO 优先** | 所有数据库操作使用 async/await，不阻塞事件循环 | 避免 CPU 空转等待 |
| **执行批次优化** | 底层每 5 个任务打包一次 LLM 调用（从系统配置读取） | 提升 TOKEN 利用率 |

### 10.2 内存占用控制

| 策略 | 说明 | 预期效果 |
|------|------|----------|
| **流式写入数据库** | 每个组合完成后立即入库，不累积在内存 | 内存占用 < 100MB |
| **及时释放引用** | 组合完成后清空草稿列表，触发 GC | 避免内存泄漏 |
| **文档内容按需加载** | 不缓存全文，每次只加载当前组合需要的片段 | 减少内存占用 60%+ |

### 10.3 TOKEN 消耗控制

**分组件计量基准**（实测校准）：

```python
TOKEN_BUDGET = {
    "prompt_base": 500,        # 系统提示词
    "prompt_context": 1500,    # 书籍内容片段（截断后）
    "prompt_variables": 100,   # 领域/年龄段等变量
    "output_per_draft": 300,   # 单个草稿输出
}

def estimate_tokens(combinations: int, drafts_per_combination: int, model: str = "qwen-plus") -> dict:
    """
    预估 TOKEN 消耗
    
    注意：输入 TOKEN 按组合计算，输出 TOKEN 按草稿计算
    """
    total_drafts = combinations * drafts_per_combination
    input_tokens = combinations * (
        TOKEN_BUDGET["prompt_base"] 
        + TOKEN_BUDGET["prompt_context"] 
        + TOKEN_BUDGET["prompt_variables"]
    )
    output_tokens = total_drafts * TOKEN_BUDGET["output_per_draft"]
    
    return {
        "input": input_tokens,
        "output": output_tokens,
        "total": input_tokens + output_tokens,
        "cost": calculate_cost(input_tokens, output_tokens, model=model)
    }

# 示例：6 领域 × 7 年龄段 × 3 草稿 = 42 组合, 126 草稿
# 预计 TOKEN = 42 × 2,100 + 126 × 300 = 88,200 + 37,800 = 126,000
```

| 策略 | 说明 | 预期效果 |
|------|------|----------|
| **文档内容截断** | 每次 LLM 调用只传入 4000 字（约 2000 TOKEN） | 单组合节省 50% TOKEN |
| **Prompt 精简** | 去除冗余说明，保留核心约束（约 500 TOKEN） | 单次调用节省 15% TOKEN |
| **批量生成** | 单次 LLM 调用生成 3-5 个草稿（而非 1 个） | TOKEN 利用率提升 3-5 倍 |
| **模型选择** | 使用低成本模型（草稿生成逻辑简单），用户可切换 | 成本降低 60-90% |
| **缓存复用** | 相同领域+年龄段的 Prompt 模板缓存 | 减少重复 TOKEN 消耗 |

**模型选择说明**：

草稿生成任务属于**结构化文本生成**，不需要强推理能力。根据阿里云百炼平台官网数据，推荐以下模型：

| 模型 | 定位 | 输入价格 | 输出价格 | 适用场景 |
|------|------|----------|----------|----------|
| **qwen-plus**（推荐默认） | 能力均衡，非思考模式最便宜 | ¥0.8/百万 | ¥2/百万 | 草稿生成、简单问答、校验 |
| **qwen3.5-plus** | 性价比之王，效果媲美 Max | ¥0.8/百万 | ¥4.8/百万 | 报告生成、评估分析 |
| **qwen3.6-plus** | 效果、速度、成本均衡 | ¥2/百万 | ¥12/百万 | 复杂分析、多步骤任务 |
| **qwen3.6-flash** | 简单任务，速度快 | ¥1.2/百万 | ¥7.2/百万 | 简单文本处理 |
| **qwen3-max** | 能力最强，适合复杂任务 | ¥2.5/百万 | ¥10/百万 | 深度推理、专业评估 |

**推荐策略**：
- **默认模型**：`qwen-plus`（非思考模式最便宜，输入¥0.8+输出¥2/百万，足够胜任草稿生成）
- **用户可切换**：在配置页面提供模型选择下拉框
- **复杂任务**：评估报告、LLM 诊断等使用 `qwen3.5-plus`（性价比之王，效果媲美 Max）

### 10.4 资源消耗预估

**场景 A**：上传书籍，生成默认 1 个组合（3 个草稿）

| 资源 | 预估消耗 | 说明 |
|------|----------|------|
| **TOKEN 总量** | 约 3,000 TOKEN | 输入 2,100 + 输出 900（基于分组件计量） |
| **TOKEN 成本** | 约 ¥0.003-0.005 | 使用 qwen-plus（输入¥0.8+输出¥2/百万） |
| **生成时间** | 约 10-15 秒 | 单次 LLM 调用 |
| **CPU 峰值** | < 10% | 单次调用，低负载 |
| **内存峰值** | < 50MB | 少量草稿缓存 |
| **数据库写入** | 1 次 | 3 个草稿批量插入 |

**场景 B**：用户手动触发 10 个组合（累计 30 个草稿）

| 资源 | 预估消耗 | 说明 |
|------|----------|------|
| **TOKEN 总量** | 约 30,000 TOKEN | 10 组合累计（10 × 3,000） |
| **TOKEN 成本** | 约 ¥0.03-0.05 | 10 组合累计 |
| **生成时间** | 约 2-3 分钟 | 10 组合串行 |
| **CPU 峰值** | < 15% | 组合串行 |
| **内存峰值** | < 80MB | 流式写入 |
| **数据库写入** | 10 次 | 每组合 1 次 |

**场景 C**：用户手动触发 42 个组合（全覆盖，126 个草稿）

| 资源 | 预估消耗 | 说明 |
|------|----------|------|
| **TOKEN 总量** | 约 126,000 TOKEN | 42 组合累计（42 × 3,000） |
| **TOKEN 成本** | 约 ¥0.13-0.20 | 42 组合累计 |
| **生成时间** | 约 10-15 分钟 | 42 组合串行 |
| **CPU 峰值** | < 20% | 组合串行 |
| **内存峰值** | < 100MB | 流式写入 |
| **数据库写入** | 42 次 | 每组合 1 次 |

### 10.5 熔断与降级机制

| 触发条件 | 动作 | 说明 |
|----------|------|------|
| **内存 > 500MB** | 暂停生成，等待 GC | 防止 OOM |
| **LLM 连续失败** | 跳过当前组合，记录日志（重试次数从系统配置 `draft.max_llm_retries` 读取，默认 2） | 避免死循环 |
| **TOKEN 消耗 > 阈值** | 停止生成，推送告警 | 防止费用失控 |
| **生成时间 > 60 分钟** | 保存已生成草稿，标记为部分完成 | 避免无限等待 |

---

## 十一、已确定事项

以下事项已在审查中确认，采用业内最佳方案：

| 序号 | 事项 | 决策 |
|------|------|------|
| 1 | **年龄段边界** | 采用左闭右开区间，月龄精确表示（行业标准） |
| 2 | **草稿分配策略** | 轮询分配 + 优先覆盖，支持 1-10 个草稿 |
| 3 | **去重策略** | 与历史草稿去重（阈值 0.85），组合内由 LLM 保证多样性 |
| 4 | **书籍内容适配** | 关键词匹配 + LLM 兜底（混合策略） |
| 5 | **计算逻辑** | 明确"每个领域×年龄段组合"为粒度 |
| 6 | **TOKEN 预估** | 输入按组合计算，输出按草稿计算，公式已修正 |
| 7 | **查询类型和难度覆盖** | 优先保证每种类型至少出现一次，剩余随机填充，高级设置可自定义 |
| 8 | **幂等性设计** | 唯一键 `(doc_id, domain, age_stage_label, draft_index)`，支持覆盖/追加模式 |
| 9 | **LLM 输出格式** | json-repair 库 + 最多 2 次重试 + 失败标记 |
| 10 | **SSE 断线重连** | 指数退避 + 断点续传 + Redis 状态持久化 |
| 11 | **取消机制** | 提供取消接口，已完成草稿保留 |
| 12 | **并发控制** | Redis 分布式锁，同一文档同时只允许 1 个任务 |
| 13 | **系统配置** | 所有默认参数必须在系统配置页面可配置（13 项配置键） |
| 14 | **高级设置** | 上传书籍时的高级设置面板默认折叠，点击展开后显示查询类型/难度自定义 |
| 15 | **模型选择约束** | 仅显示已配置成本的模型，未配置成本的不显示，提供降级策略 |
| 16 | **成本计算** | 预估成本必须使用系统配置中当前选中模型的实际单价 |
| 17 | **术语统一** | 前端展示"组合进度"，不暴露底层"执行批次"优化 |
| 18 | **去重与幂等协调** | 去重在幂等之前执行，去重后重新编号 draft_index |

---

## 十二、待讨论事项

以下事项需根据实际情况确认：

1. **草稿质量评估**：如何判断生成的草稿"可用"？是否需要人工审核环节？

2. **默认组合触发时机**：上传书籍后立即生成，还是用户手动触发？
