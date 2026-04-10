# RAG 测试集导入功能设计文档

**日期**: 2026-04-09  
**状态**: 已审核（V1.2）
**版本**: 1.2
**更新记录**:
- 2026-04-09: 初始版本
- 2026-04-09: V1.1 增加优化点：统一ID生成、并发控制、LLM校验、异步处理、版本控制  
- 2026-04-09: V1.2 修复审查问题：完善ID生成策略、事务性写入、版本控制、LLM Prompt约束、API设计
**作者**: AI Assistant

---

## 1. 需求背景

当前 RAG 评估测试页面的"导入测试用例"功能仅为占位实现，无法实际导入测试数据。用户需要：
1. 从 JSON 文件批量导入测试用例
2. 从书籍文件生成测试用例

**核心问题**：直接导入书籍生成测试用例会因书籍质量问题导致测试集不可靠。

**解决方案**：采用"分阶段质量控制"策略，将"导入"与"生成测试用例"解耦，增加人工审核环节。

### 1.1 优化点说明
本方案在原有设计基础上增加了以下优化：
- 统一ID生成策略，提高可读性和唯一性
- 增强并发控制机制，保证数据一致性
- 完善LLM生成结果校验，提高系统稳定性
- 增加大文件异步处理机制，提升用户体验
- 考虑测试数据版本控制，便于回溯和对比

---

## 2. 系统架构

### 2.1 数据模型扩展

#### 2.1.1 原始文档（SourceDocument）

```python
class ChapterInfo(BaseModel):
    title: str                   # 章节标题
    page_start: int              # 起始页
    page_end: int                # 结束页
    level: int                   # 层级（1=一级章节，2=二级...）

class QualityReport(BaseModel):
    content_completeness: float  # 内容完整性 0-1
    text_extractability: float   # 文本可提取性 0-1
    chapter_clarity: float       # 章节清晰度 0-1
    suggested_domains: list[str] # 建议领域
    warnings: list[str]          # 警告信息
    raw_text_length: int         # 原始文本长度（字符数）

class SourceDocument(BaseModel):
    id: str                      # 文档唯一标识（格式：doc_{nanoid_10}）
    title: str                   # 文档标题
    file_type: str               # PDF/TXT/EPUB
    file_path: str               # 存储路径（相对路径）
    file_hash: str               # 文件 SHA256 哈希（用于去重）
    content_summary: str         # 内容摘要（前500字符）
    page_count: int              # 页数（如适用）
    chapter_structure: list[ChapterInfo]  # 章节结构
    quality_report: QualityReport         # 质量报告
    status: str                  # uploaded/parsing/ready/archived
    created_at: datetime
    updated_at: datetime
```

**ID 生成策略**：
```python
from nanoid import generate

def generate_doc_id() -> str:
    return f"doc_{generate(size=10)}"  # 例：doc_Ax7kP9mQ2w
```

#### 2.1.2 测试用例草稿（TestCaseDraft）

```python
class GenerationParams(BaseModel):
    target_domains: list[str]      # 目标领域列表
    age_range: tuple[int, int]     # 年龄段范围 [min, max]
    count: int                     # 生成数量
    difficulty: str                # easy/medium/hard
    llm_model: str                 # 使用的模型名称
    temperature: float             # 温度参数 0-1

class TestCaseDraft(BaseModel):
    id: str                        # 草稿唯一标识（格式：draft_{nanoid_10}）
    source_document_id: str        # 来源文档ID
    query: str                     # 测试查询
    age: int                       # 年龄段（0-18）
    domain: str                    # 领域
    expected_knowledge_ids: list[str]
    expected_keywords: list[str]
    description: str
    answer_points: list[str]       # 答题要点
    professional_terms: list[str]  # 专业术语
    age_requirement: str           # 年龄要求
    generation_params: GenerationParams  # 生成参数（仅草稿阶段使用，导入时丢弃）
    status: str                    # draft/reviewed/rejected/imported（导入时丢弃）
    created_at: datetime
    updated_at: datetime
```

**ID 生成策略**：
```python
def generate_draft_id() -> str:
    return f"draft_{generate(size=10)}"  # 例：draft_Bx8mN3pR5t
```

#### 2.1.3 测试集（TestSet）

```python
class TestSet(BaseModel):
    id: str                        # 测试集唯一标识（格式：set_{nanoid_10}）
    name: str                      # 测试集名称
    description: str               # 描述
    source_type: str               # json_import/book_generated/manual/mixed
    test_case_ids: list[str]       # 包含的测试用例ID
    # 注意：source_document_ids 已移除，来源文档信息通过 TestCase.source_document_id 关联
    created_at: datetime
    updated_at: datetime
```

**ID 生成策略**：
```python
def generate_set_id() -> str:
    return f"set_{generate(size=10)}"  # 例：set_Cy9nQ4rS6v
```

**source_type 说明**：
- `json_import`: 全部从 JSON 导入
- `book_generated`: 全部从书籍生成
- `manual`: 手动创建
- `mixed`: 混合来源

### 2.2 现有 TestCase 模型扩展

在现有 `TestCase` 模型中增加字段：

```python
class TestCase(BaseModel):
    # 现有字段
    id: str = Field(default_factory=lambda: f"tc_{generate(size=10)}")  # 统一格式：tc_{nanoid_10}
    query: str
    age: int                       # 年龄段（0-18）
    expected_knowledge_ids: list[str]
    expected_keywords: list[str]
    description: str
    
    # 新增字段（均为可选，向后兼容）
    domain: str = ""               # 领域（粗大动作、精细动作等）
    answer_points: list[str] = []  # 答题要点
    professional_terms: list[str] = []  # 专业术语
    age_requirement: str = ""      # 年龄要求
    relevance_scores: dict = {}    # 相关性评分
    source_document_id: str = ""   # 来源文档ID（可选，空表示手动创建或JSON导入）
    test_set_id: str = ""          # 所属测试集ID（可选）
    version: int = 1               # 测试用例版本号，用于版本控制
    created_at: datetime
    updated_at: datetime
```

**ID 生成策略说明**：
- 使用 `nanoid` 库生成唯一标识，格式为 `tc_{nanoid_10}`（例：`tc_Dz0pR5sT7x`）
- nanoid 保证高并发下的唯一性，比时间戳更可靠
- 需在 `requirements.txt` 中添加 `nanoid` 依赖

**字段处理说明**：
- 草稿转正式用例时：`generation_params` 和 `status` 字段不映射到 TestCase
- `relevance_scores` 在草稿阶段为空，导入后可由测试运行填充
- `test_set_id` 在批量导入时由用户指定或自动创建测试集后赋值

---

## 3. 功能设计

### 3.1 JSON 导入流程

```
用户选择JSON文件 
  → 前端上传到后端
  → 后端校验并返回预览（有效/无效/重复标记）
  → 前端显示统计信息和预览表格
  → 用户选择要导入的条目
  → 确认导入
  → 后端批量存储
  → 返回导入结果
```

**职责划分**：
- **前端**：文件选择、UI 展示、用户交互
- **后端**：格式校验、重复检测、数据存储

#### 3.1.1 JSON 格式规范

导入的 JSON 文件应为数组格式，每个元素为一个测试用例对象：

```json
[
  {
    "query": "0岁儿童走路的发展情况如何",
    "age": 0,
    "domain": "粗大动作",
    "expected_knowledge_ids": [],
    "expected_keywords": ["走路", "发展", "里程碑"],
    "description": "测试婴儿粗大动作领域关于走路的检索能力",
    "answer_points": ["发展里程碑", "正常范围", "训练方法"],
    "professional_terms": ["大运动发展", "运动里程碑"],
    "age_requirement": "0岁婴儿适用"
  }
]
```

**字段要求**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 测试查询，不能为空 |
| age | int | 是 | 年龄段，0-18 |
| domain | string | 否 | 领域，见领域枚举 |
| expected_knowledge_ids | list[str] | 否 | 期望的知识ID列表 |
| expected_keywords | list[str] | 否 | 期望的关键词列表 |
| description | string | 否 | 描述 |
| answer_points | list[str] | 否 | 答题要点 |
| professional_terms | list[str] | 否 | 专业术语 |
| age_requirement | string | 否 | 年龄要求 |

**领域枚举**：粗大动作、精细动作、语言发展、认知能力、社交情感、感觉统合

**领域常量定义**：
```python
# backend/src/constants/test_case.py
TEST_CASE_DOMAINS = [
    "粗大动作",
    "精细动作",
    "语言发展",
    "认知能力",
    "社交情感",
    "感觉统合"
]

# 前端常量
# frontend/src/constants/test-case.ts
export const TEST_CASE_DOMAINS = [
  "粗大动作",
  "精细动作",
  "语言发展",
  "认知能力",
  "社交情感",
  "感觉统合"
] as const;
```

**重复检测规则**：基于 `query + age + domain` 组合判断，完全相同视为重复。

#### 3.1.2 前端组件

**ImportJsonModal**
- 文件选择器（支持 .json）
- 上传进度条
- 预览表格（分页显示，默认每页10条）
- 统计面板：
  - 总条目数
  - 有效条目数
  - 无效条目数（格式错误，显示原因）
  - 重复条目数（已存在，显示已有ID）
- 批量选择/取消选择
- 导入按钮（带进度条）
- 可选：导入到指定测试集

#### 3.1.3 后端 API

**POST /rag/test/cases/import/preview**
- 接收：JSON 文件内容（multipart/form-data 或 raw JSON）
- 处理：
  1. 格式校验（必填字段、类型检查）
  2. 重复检测（基于 query + age + domain）
  3. 返回预览数据（含有效/无效/重复标记）
- 返回：
```json
{
  "valid_cases": [...],
  "invalid_cases": [{"index": 0, "data": {...}, "error": "query 字段缺失"}],
  "duplicates": [{"index": 2, "data": {...}, "existing_id": "tc_xxx"}]
}
```

**POST /rag/test/cases/batch**
- 接收：用户确认导入的测试用例列表
```json
{
  "cases": [...],
  "test_set_id": "set_xxx"  // 可选
}
```
- 处理：
  1. **预校验阶段**（全部验证，任一失败则终止）：
     - 格式校验（必填字段、类型检查）
     - 重复检测（基于 query + age + domain）
     - 业务规则校验（age 范围 0-18、domain 枚举值）
  2. **原子写入阶段**（全部验证通过后执行）：
     - 获取文件锁（filelock）
     - 批量创建测试用例到内存
     - 写入临时文件（test_cases.json.tmp）
     - 原子替换（os.replace）原文件
     - 如指定 test_set_id，更新测试集
     - 释放文件锁
  3. 返回导入结果
- 返回：
```json
{
  "imported_count": 50,
  "failed_count": 0,
  "test_case_ids": ["tc_xxx", ...],
  "errors": []
}
```

**事务性写入实现**：
```python
def batch_import_cases(self, cases: List[TestCase], test_set_id: Optional[str] = None):
    # 阶段 1：预校验所有数据
    for i, case in enumerate(cases):
        self._validate_test_case(case)  # 失败则抛出异常
        if self._is_duplicate(case):
            raise DuplicateError(f"Case {i} is duplicate")
    
    # 阶段 2：原子写入
    with FileLock(self.test_case_store_path + ".lock"):
        # 加载当前数据
        self._load_test_cases()
        
        # 批量添加到内存
        for case in cases:
            self.test_case_store.test_cases[case.id] = case
        
        # 如指定测试集，更新关联
        if test_set_id:
            test_set = self._load_test_set(test_set_id)
            test_set.test_case_ids.extend([c.id for c in cases])
            self._save_test_set(test_set)
        
        # 原子写入：先写临时文件，再替换
        tmp_path = self.test_case_store_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(self.test_case_store.model_dump_json(indent=2))
        os.replace(tmp_path, self.test_case_store_path)  # 原子操作
    
    return {"imported_count": len(cases), "test_case_ids": [c.id for c in cases]}
```

---

### 3.2 书籍导入流程（分阶段）

#### 阶段1：文档上传与解析

```
用户上传书籍文件
  → 后端解析文档
  → 生成质量报告
  → 存储为原始文档
  → 返回文档信息
```

**前端组件：UploadDocumentModal**
- 文件上传（支持 PDF/TXT/EPUB）
- 上传进度条
- 解析状态显示
- 质量报告展示：
  - 文档标题
  - 页数/字数
  - 章节结构
  - 内容完整性评估
  - 适用领域建议

**后端 API：POST /rag/test/documents/upload**
- 接收：文件上传
- 处理：
  1. 文件类型验证
  2. 文本提取（PDF/EPUB 解析）
  3. 生成内容摘要
  4. 提取章节结构
  5. 生成质量报告
- 返回：{ document_id, title, quality_report }

---

#### 阶段2：测试用例生成工作台

```
用户选择原始文档
  → 配置生成参数
  → LLM 生成测试用例草稿
  → 自动进入审核流程
```

**前端组件：TestCaseGenerationWorkbench**
- 文档选择器（从原始文档库选择）
- 生成参数配置面板：
  - 目标领域（多选）
  - 年龄段范围（滑块，0-18）
  - 生成数量（输入框，1-100）
  - 难度级别（简单/中等/困难）
- 生成按钮（带进度指示）
- 生成完成后自动切换到审核表格

**后端 API：POST /rag/test/drafts/generate**
- 接收：
```json
{
  "source_document_id": "doc_xxx",
  "generation_params": {
    "target_domains": ["粗大动作", "精细动作"],
    "age_range": [3, 6],
    "count": 20,
    "difficulty": "medium"
  }
}
```
- 处理：
  1. 加载文档内容
  2. 如文档过大，分块处理（每块 4000 字符）
  3. 构建 LLM Prompt
  4. 调用 LLM 生成测试用例
  5. 保存为草稿
  6. 返回草稿列表
- 返回：
```json
{
  "draft_ids": ["draft_xxx", ...],
  "count": 20,
  "estimated_time_seconds": 30
}
```

**LLM Prompt 设计草案**：

```
你是一个儿童发展评估专家。请基于以下文档内容，生成测试用例用于评估 RAG 系统的检索能力。

文档内容：
{document_content}

生成要求：
- 领域：{target_domains}
- 年龄段：{age_range[0]}-{age_range[1]}岁
- 数量：{count}
- 难度：{difficulty}

每个测试用例应包含：
1. query: 家长可能提出的问题
2. age: 适用的年龄段（整数）
3. domain: 领域（从{target_domains}中选择）
4. expected_keywords: 3-5个期望检索的关键词
5. description: 测试目的描述
6. answer_points: 2-4个答题要点
7. professional_terms: 2-3个相关专业术语

请严格按照以下 JSON Schema 返回，不要包含任何其他文本：

{
  "type": "array",
  "items": {
    "type": "object",
    "required": ["query", "age", "domain"],
    "properties": {
      "query": {"type": "string", "minLength": 5},
      "age": {"type": "integer", "minimum": 0, "maximum": 18},
      "domain": {"type": "string", "enum": ["粗大动作", "精细动作", "语言发展", "认知能力", "社交情感", "感觉统合"]},
      "expected_keywords": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
      "description": {"type": "string"},
      "answer_points": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
      "professional_terms": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3}
    },
    "additionalProperties": false
  }
}
```

**LLM 响应解析与校验**：

```python
import json
import re
from jsonschema import validate, ValidationError

TEST_CASE_DRAFT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["query", "age", "domain"],
        "properties": {
            "query": {"type": "string", "minLength": 5},
            "age": {"type": "integer", "minimum": 0, "maximum": 18},
            "domain": {"type": "string", "enum": ["粗大动作", "精细动作", "语言发展", "认知能力", "社交情感", "感觉统合"]},
            "expected_keywords": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
            "description": {"type": "string"},
            "answer_points": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
            "professional_terms": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3}
        },
        "additionalProperties": False
    }
}

def parse_llm_response(response: str) -> List[dict]:
    """解析并校验 LLM 返回的测试用例数据
    
    处理流程：
    1. 提取 JSON（处理 markdown 代码块包裹）
    2. 解析 JSON
    3. Schema 校验
    4. 返回校验后的数据
    """
    # 1. 提取 JSON（处理 ```json ... ``` 格式）
    json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 尝试直接解析
        json_str = response.strip()
    
    # 2. 解析 JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise LLMGenerationError(f"LLM 返回非 JSON 格式: {e}")
    
    # 3. Schema 校验
    try:
        validate(instance=data, schema=TEST_CASE_DRAFT_SCHEMA)
    except ValidationError as e:
        raise LLMGenerationError(f"LLM 返回数据格式错误: {e.message}")
    
    # 4. 业务规则校验
    for i, item in enumerate(data):
        if not item.get("query") or len(item["query"].strip()) < 5:
            raise LLMGenerationError(f"第 {i+1} 条测试用例 query 过短")
        if item["age"] < 0 or item["age"] > 18:
            raise LLMGenerationError(f"第 {i+1} 条测试用例 age 超出范围")
    
    return data
```

---

#### 阶段3：人工审核与导入

```
用户审核草稿列表
  → 逐条编辑/删除/标记
  → 批量操作
  → 确认导入
  → 生成正式测试用例
```

**前端组件：TestCaseReviewTable**
- 草稿表格（可编辑，分页显示）
- 状态标记（通过/拒绝/待修改）
- 批量操作工具栏（批量通过、批量拒绝）
- 导入确认对话框（显示导入统计）
- 导入进度显示
- 可选：添加到指定测试集

**后端 API**

**GET /rag/test/drafts**
- 接收：query params
  - source_document_id（可选）
  - status（可选）：draft/reviewed/rejected/imported
  - page（默认1）
  - page_size（默认20，最大100）
  - sort_by（默认 created_at）：created_at/age/domain/status
  - order（默认 desc）：asc/desc
- 返回：
```json
{
  "drafts": [...],
  "total": 150,
  "page": 1,
  "page_size": 20
}
```

**PUT /rag/test/drafts/{draft_id}**
- 接收：更新后的草稿数据
- 处理：更新草稿
- 返回：更新后的草稿

**DELETE /rag/test/drafts/batch**
- 接收：`{ "draft_ids": ["draft_xxx", ...] }`
- 处理：批量删除草稿
- 返回：`{ "deleted_count": 10 }`

**POST /rag/test/drafts/batch-import**
- 接收：
```json
{
  "draft_ids": ["draft_xxx", ...],
  "test_set_id": "set_xxx"  // 可选
}
```
- 处理：
  1. 加载草稿数据
  2. **草稿转正式测试用例**（调用转换函数，见下方）
  3. 预校验所有转换后的测试用例
  4. 原子写入测试用例库
  5. 更新草稿状态为 imported
  6. 如指定 test_set_id，自动添加到测试集
- 返回：
```json
{
  "imported_count": 15,
  "test_case_ids": ["tc_xxx", ...]
}
```

**草稿转正式用例转换函数**：
```python
def draft_to_test_case(draft: TestCaseDraft) -> TestCase:
    """将草稿转换为正式测试用例
    
    转换规则：
    - 生成新的 TestCase ID（tc_{nanoid_10}）
    - 映射所有业务字段
    - 丢弃 generation_params 和 status 字段
    - 保留 source_document_id 用于溯源
    - 初始化 version=1
    """
    return TestCase(
        id=f"tc_{generate(size=10)}",  # 生成新 ID
        query=draft.query,
        age=draft.age,
        domain=draft.domain,
        expected_knowledge_ids=draft.expected_knowledge_ids,
        expected_keywords=draft.expected_keywords,
        description=draft.description,
        answer_points=draft.answer_points,
        professional_terms=draft.professional_terms,
        age_requirement=draft.age_requirement,
        source_document_id=draft.source_document_id,
        test_set_id="",  # 由调用方指定
        version=1,
        relevance_scores={},
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
```

---

### 3.3 测试集管理

**前端组件：TestSetManager**
- 测试集列表
- 创建测试集
- 添加/移除测试用例
- 导出测试集为 JSON
- 测试集统计信息

**后端 API**

**POST /rag/test/sets**
- 创建测试集

**GET /rag/test/sets**
- 获取测试集列表

**GET /rag/test/sets/{set_id}**
- 获取测试集详情

**PUT /rag/test/sets/{set_id}**
- 更新测试集

**DELETE /rag/test/sets/{set_id}**
- 删除测试集

**GET /rag/test/sets/{set_id}/export**
- 导出测试集为 JSON（推荐，符合 RESTful 规范）
- 响应头：`Content-Disposition: attachment; filename="test_set_{set_id}.json"`

**GET /rag/test/sets/{set_id}/cases**
- 获取测试集的所有测试用例
- 返回：`{ "test_cases": [...], "total": 50 }`

**POST /rag/test/sets/{set_id}/cases**
- 添加测试用例到测试集
- 接收：`{ "case_ids": ["tc_xxx", ...] }`
- 处理：将测试用例 ID 添加到 test_case_ids 列表
- 返回：`{ "added_count": 5, "test_set_id": "set_xxx" }`

**DELETE /rag/test/sets/{set_id}/cases/{case_id}**
- 从测试集移除测试用例
- 返回：`{ "status": "success", "message": "Case removed from test set" }`

---

### 3.4 错误响应格式

所有 API 错误响应统一格式：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "字段 query 不能为空",
    "details": { "field": "query", "reason": "required" }
  }
}
```

**常见错误码**：
- `VALIDATION_ERROR`: 参数校验失败
- `DUPLICATE_ERROR`: 重复数据
- `NOT_FOUND`: 资源不存在
- `INTERNAL_ERROR`: 内部错误
- `LLM_GENERATION_ERROR`: LLM 生成失败
- `FILE_PARSE_ERROR`: 文件解析失败

---

## 4. 前端页面结构

### 4.1 页面布局调整

在 `RagEvaluationPage` 中：

```
导入测试用例按钮 → 下拉菜单
  ├── 从 JSON 文件导入
  └── 从书籍生成

新增 Tab：测试集管理
  ├── 测试集列表
  ├── 原始文档库
  └── 测试用例草稿审核
```

### 4.2 新增组件

```
frontend/src/features/rag-evaluation/components/
├── ImportJsonModal.tsx           # JSON 导入弹窗
├── UploadDocumentModal.tsx       # 文档上传弹窗
├── TestCaseGenerationWorkbench.tsx  # 生成工作台
├── TestCaseReviewTable.tsx       # 草稿审核表格
├── TestSetManager.tsx            # 测试集管理
└── DocumentQualityReport.tsx     # 文档质量报告
```

### 4.3 新增 Hooks

```
frontend/src/features/rag-evaluation/hooks/
├── useDocumentUpload.ts          # 文档上传逻辑
├── useTestCaseGeneration.ts      # 测试用例生成逻辑
└── useTestSetManagement.ts       # 测试集管理逻辑
```

---

## 5. 后端 API 路由

### 5.1 文档管理

```
POST   /rag/test/documents/upload      # 上传文档
GET    /rag/test/documents             # 获取文档列表（支持分页）
GET    /rag/test/documents/{doc_id}    # 获取文档详情
DELETE /rag/test/documents/{doc_id}    # 删除文档
DELETE /rag/test/documents/batch       # 批量删除文档
```

### 5.2 测试用例草稿

```
POST   /rag/test/drafts/generate       # 生成草稿
GET    /rag/test/drafts                # 获取草稿列表（支持分页和过滤）
GET    /rag/test/drafts/{draft_id}     # 获取草稿详情
PUT    /rag/test/drafts/{draft_id}     # 更新草稿
DELETE /rag/test/drafts/{draft_id}     # 删除草稿
DELETE /rag/test/drafts/batch          # 批量删除草稿
POST   /rag/test/drafts/batch-import   # 批量导入
```

### 5.3 测试集管理

```
POST   /rag/test/sets                  # 创建测试集
GET    /rag/test/sets                  # 获取测试集列表
GET    /rag/test/sets/{set_id}         # 获取测试集详情
PUT    /rag/test/sets/{set_id}         # 更新测试集
DELETE /rag/test/sets/{set_id}         # 删除测试集
GET    /rag/test/sets/{set_id}/export  # 导出测试集（推荐）
POST   /rag/test/sets/{set_id}/export  # 导出测试集（兼容旧版）
GET    /rag/test/sets/{set_id}/cases   # 获取测试集的所有测试用例
POST   /rag/test/sets/{set_id}/cases   # 添加测试用例到测试集
DELETE /rag/test/sets/{set_id}/cases/{case_id}  # 从测试集移除测试用例
```

### 5.4 现有 API 扩展

```
POST   /rag/test/cases/import/preview  # JSON 导入预览
POST   /rag/test/cases/batch           # 批量导入
```

---

## 6. 数据流图

### 6.1 JSON 导入

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  JSON 文件   │ ──→ │ 前端解析预览  │ ──→ │ 用户选择确认  │
└─────────────┘     └──────────────┘     └──────────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │ 后端批量导入  │
                                         └──────────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │ 测试用例库    │
                                         └──────────────┘
```

### 6.2 书籍导入

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  书籍文件    │ ──→ │ 文档解析存储  │ ──→ │ 原始文档库    │
└─────────────┘     └──────────────┘     └──────────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │ 配置生成参数  │
                                         └──────────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │ LLM 生成草稿  │
                                         └──────────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │ 人工审核编辑  │
                                         └──────────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │ 正式测试用例  │
                                         └──────────────┘
```

---

## 7. 错误处理

### 7.1 JSON 导入

| 错误类型 | 处理方式 |
|---------|---------|
| 文件格式错误 | 前端拦截，提示用户 |
| JSON 解析失败 | 显示具体错误行号 |
| 字段缺失 | 标记为无效，显示原因 |
| 重复数据 | 标记为重复，可选跳过或覆盖 |

### 7.2 书籍导入

| 错误类型 | 处理方式 |
|---------|---------|
| 不支持的文件类型 | 前端拦截 |
| 文件过大 | 限制大小，提示用户 |
| 解析失败 | 显示错误详情，允许重试 |
| LLM 生成失败 | 保留文档，允许重新生成 |
| 草稿审核超时 | 自动保存草稿状态 |

---

## 8. 测试策略

### 8.1 单元测试

- JSON 解析和校验逻辑（包括格式校验、重复检测）
- 文档解析逻辑（不同文件类型、大文件异步处理）
- 测试用例生成 Prompt 构建和结果校验
- 数据转换逻辑（草稿转正式用例、版本升级）
- 并发控制逻辑（文件锁、事务性写入）
- 版本控制逻辑（版本号递增、历史版本管理）

### 8.2 集成测试

- JSON 导入完整流程
- 文档上传到测试用例生成完整流程
- 草稿审核和导入流程

### 8.3 用户验收测试

- 导入 100 条 JSON 测试用例
- 上传 PDF 书籍并生成测试用例
- 审核并导入生成的测试用例

---

## 9. 实施优先级

### Phase 1（MVP - JSON 导入）
1. JSON 导入预览 API（POST /rag/test/cases/import/preview）
2. 批量导入 API（POST /rag/test/cases/batch）
3. ImportJsonModal 前端组件
4. 更新 TestCase 模型（新增可选字段）
5. 更新前端 TypeScript 类型定义

**交付标准**：用户可以从 JSON 文件批量导入测试用例，支持预览和校验

### Phase 2（书籍导入 + 审核流程）
6. 文档上传和解析 API
7. UploadDocumentModal 前端组件
8. DocumentQualityReport 组件
9. 测试用例草稿生成 API
10. TestCaseGenerationWorkbench 组件
11. 草稿审核表格组件
12. 草稿批量导入 API

**交付标准**：用户可以上传书籍，生成测试用例草稿，审核后导入

### Phase 3（测试集管理）
13. 测试集 CRUD API
14. TestSetManager 组件
15. 测试集导出 API
16. 导入时关联测试集功能

**交付标准**：用户可以创建和管理测试集，导出为 JSON

---

## 10. 技术选型

### 10.1 文档解析

| 文件类型 | 库 | 说明 |
|---------|-----|------|
| PDF | PyMuPDF (fitz) | 已存在于项目依赖，支持异步解析 |
| TXT | 内置 open() | 无需额外依赖 |
| EPUB | ebooklib | 需添加依赖，支持EPUB2/EPUB3格式 |

**异步处理机制**：
- 大于10MB的文件自动采用异步解析
- 前端轮询查询解析状态，支持取消解析
- 解析失败自动重试2次，保留原始文件

**异步任务管理 API**：
```
POST   /rag/test/documents/upload                    # 上传文档，返回 task_id
GET    /rag/test/documents/upload/{task_id}/status   # 查询解析状态
DELETE /rag/test/documents/upload/{task_id}          # 取消解析
```

**异步任务状态**：
```python
class ParseTaskStatus(BaseModel):
    task_id: str
    status: str              # pending/parsing/completed/failed/cancelled
    progress: float          # 0-100
    document_id: str = ""    # 解析完成后填充
    error_message: str = ""  # 失败时填充
    created_at: datetime
    completed_at: Optional[datetime] = None
```

### 10.2 LLM 生成

使用现有 RAG 系统的 LLM 服务，构建专用 Prompt 模板。

### 10.3 前端组件库

继续使用 Ant Design，新增组件基于现有组件封装。

---

## 11. 数据迁移

### 11.1 现有测试用例

现有测试用例无需迁移，新增字段为可选（有默认值）。

### 11.2 需要修改的现有文件

**后端**：
- `backend/src/model/rag_test.py` - 扩展 TestCase 模型
- `backend/src/service/rag_test_manager.py` - 新增导入/草稿/文档管理方法

**前端**：
- `frontend/src/api/rag-test/types.ts` - 扩展 TestCase 接口
- `frontend/src/features/rag-evaluation/components/TestCaseTable.tsx` - 新增列显示
- `frontend/src/features/rag-evaluation/components/TestCaseModal.tsx` - 新增表单字段

### 11.3 存储结构

```
./storage/
├── test_cases.json              # 现有测试用例（扩展字段）
├── test_runs/                   # 现有测试运行
├── snapshots/                   # 现有快照
├── source_documents/            # 新增：原始文档
│   ├── {doc_id}.pdf             # 原始文件
│   └── {doc_id}.meta.json       # 元数据
├── test_case_drafts/            # 新增：测试用例草稿
│   └── {draft_id}.json
└── test_sets/                   # 新增：测试集
    └── {set_id}.json
```

### 11.4 初始化脚本

首次运行时自动创建目录：
```python
import os
from pathlib import Path

STORAGE_DIRS = [
    "./storage/source_documents",
    "./storage/test_case_drafts",
    "./storage/test_sets",
    "./storage/test_cases_history",  # 版本控制历史
]

for dir_path in STORAGE_DIRS:
    Path(dir_path).mkdir(parents=True, exist_ok=True)
```

### 11.5 数据迁移脚本

现有测试用例新增字段需要初始化默认值：

```python
# backend/scripts/migrate_test_cases.py
from pathlib import Path
import json
from datetime import datetime

def migrate_test_cases():
    """迁移现有测试用例，为新增字段设置默认值"""
    store_path = Path("./storage/test_cases.json")
    
    if not store_path.exists():
        print("No test cases to migrate")
        return
    
    with open(store_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    migrated_count = 0
    
    for case_id, case in data.get("test_cases", {}).items():
        needs_save = False
        
        # 为新增字段设置默认值
        if "domain" not in case or case["domain"] == "":
            case["domain"] = "未知"
            needs_save = True
        
        if "answer_points" not in case:
            case["answer_points"] = []
            needs_save = True
        
        if "professional_terms" not in case:
            case["professional_terms"] = []
            needs_save = True
        
        if "age_requirement" not in case or case["age_requirement"] == "":
            case["age_requirement"] = ""
            needs_save = True
        
        if "relevance_scores" not in case:
            case["relevance_scores"] = {}
            needs_save = True
        
        if "source_document_id" not in case:
            case["source_document_id"] = ""
            needs_save = True
        
        if "test_set_id" not in case:
            case["test_set_id"] = ""
            needs_save = True
        
        if "version" not in case:
            case["version"] = 1
            needs_save = True
        
        if needs_save:
            migrated_count += 1
    
    if migrated_count > 0:
        # 备份原文件
        backup_path = store_path.with_suffix(f".backup.{datetime.now().strftime('%Y%m%d%H%M%S')}")
        store_path.rename(backup_path)
        
        # 写入新数据
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Migrated {migrated_count} test cases")
        print(f"Backup saved to {backup_path}")
    else:
        print("No test cases need migration")

if __name__ == "__main__":
    migrate_test_cases()
```

---

## 12. 安全考虑

1. **文件上传限制**：
   - 最大文件大小：50MB
   - 允许的文件类型：.json, .pdf, .txt, .epub
   - 文件哈希校验（防止重复上传）

2. **LLM 调用限制**：
   - 单次生成数量上限：100 条
   - 频率限制：每分钟 5 次
   - 超时时间：60 秒

3. **数据校验**：
   - 所有导入数据必须经过格式校验
   - 事务性批量操作（全部成功或全部回滚）

4. **并发安全**：
   - 使用文件锁（filelock 库）保护所有 JSON 文件读写操作，比 threading.Lock 支持跨进程并发
   - 批量操作采用事务性写入：先写入临时文件，成功后再替换原文件
   - 对于高频操作（草稿生成、批量导入），实现乐观锁机制，避免版本冲突

---

## 13. 性能优化

1. **JSON 导入**：
   - 前端分页预览，避免一次性渲染大量数据
   - 后端批量写入，减少 I/O 操作
   - 性能目标：100 条导入 < 5 秒

2. **文档解析**：
   - 异步处理大文件
   - 缓存解析结果
   - 文档内容分块存储（每块 4000 字符）

3. **LLM 生成**：
   - 流式返回草稿，提升用户体验
   - 后台任务队列处理大批量生成
   - 生成结果增加JSON格式校验和字段完整性检查
   - 生成失败自动重试3次，返回详细错误信息
   - 性能目标：20 条生成 < 30 秒

---

## 14. 回滚与撤销机制

### 14.1 批量导入回滚

- 批量导入采用事务性操作
- 如任何一条失败，全部回滚
- 返回详细错误信息

### 14.2 草稿删除恢复

- 草稿删除后保留 24 小时
- 提供"回收站"功能可恢复

### 14.3 测试用例删除

- 删除测试用例时检查是否关联测试集
- 如关联，提示用户确认
- 删除后保留版本历史，可查看历史版本和恢复

### 14.4 版本控制

**版本存储策略**：
- 测试用例修改时自动递增版本号
- 历史版本存储到独立文件：`./storage/test_cases_history/{tc_id}/v{version}.json`
- 测试集关联特定版本的测试用例，保证测试结果可复现

**版本管理实现**：
```python
class TestCaseVersion(BaseModel):
    version: int                     # 版本号
    data: TestCase                   # 该版本的完整数据
    changed_at: datetime             # 变更时间
    changed_by: str = "system"       # 变更人（system/user_id）
    change_reason: str = ""          # 变更原因

def save_test_case_version(self, test_case: TestCase, changed_by: str = "system", reason: str = ""):
    """保存测试用例历史版本"""
    history_dir = Path(f"./storage/test_cases_history/{test_case.id}")
    history_dir.mkdir(parents=True, exist_ok=True)
    
    version_file = history_dir / f"v{test_case.version}.json"
    version_record = TestCaseVersion(
        version=test_case.version,
        data=test_case,
        changed_at=datetime.now(),
        changed_by=changed_by,
        change_reason=reason
    )
    version_file.write_text(version_record.model_dump_json(indent=2))

def get_test_case_versions(self, test_case_id: str) -> List[TestCaseVersion]:
    """获取测试用例所有历史版本"""
    history_dir = Path(f"./storage/test_cases_history/{test_case_id}")
    if not history_dir.exists():
        return []
    
    versions = []
    for version_file in sorted(history_dir.glob("v*.json")):
        versions.append(TestCaseVersion.model_validate_json(version_file.read_text()))
    return versions

def rollback_test_case_version(self, test_case_id: str, target_version: int) -> TestCase:
    """回滚到指定版本"""
    history_dir = Path(f"./storage/test_cases_history/{test_case_id}")
    version_file = history_dir / f"v{target_version}.json"
    
    if not version_file.exists():
        raise NotFoundError(f"Version {target_version} not found")
    
    version_record = TestCaseVersion.model_validate_json(version_file.read_text())
    old_data = version_record.data
    
    # 创建新版本（复制旧版本数据）
    current_case = self.get_test_case(test_case_id)
    current_case.version += 1
    current_case.query = old_data.query
    current_case.age = old_data.age
    current_case.expected_knowledge_ids = old_data.expected_knowledge_ids
    current_case.expected_keywords = old_data.expected_keywords
    current_case.description = old_data.description
    current_case.domain = old_data.domain
    current_case.answer_points = old_data.answer_points
    current_case.professional_terms = old_data.professional_terms
    current_case.age_requirement = old_data.age_requirement
    current_case.updated_at = datetime.now()
    
    # 保存当前版本为新版本
    self.save_test_case_version(current_case, changed_by="rollback", reason=f"Rollback to v{target_version}")
    self.update_test_case(test_case_id, current_case)
    
    return current_case

def compare_test_case_versions(self, test_case_id: str, version1: int, version2: int) -> Dict:
    """对比两个版本的差异"""
    history_dir = Path(f"./storage/test_cases_history/{test_case_id}")
    
    v1_file = history_dir / f"v{version1}.json"
    v2_file = history_dir / f"v{version2}.json"
    
    if not v1_file.exists() or not v2_file.exists():
        raise NotFoundError("Version not found")
    
    v1_data = TestCaseVersion.model_validate_json(v1_file.read_text()).data
    v2_data = TestCaseVersion.model_validate_json(v2_file.read_text()).data
    
    # 对比字段差异
    diff_fields = []
    for field in ["query", "age", "domain", "expected_keywords", "answer_points", "professional_terms"]:
        if getattr(v1_data, field) != getattr(v2_data, field):
            diff_fields.append({
                "field": field,
                "old_value": getattr(v1_data, field),
                "new_value": getattr(v2_data, field)
            })
    
    return {
        "version1": version1,
        "version2": version2,
        "diff_fields": diff_fields
    }
```

**版本目录结构**：
```
./storage/test_cases_history/
├── tc_Dz0pR5sT7x/
│   ├── v1.json          # 初始版本
│   ├── v2.json          # 第一次修改
│   └── v3.json          # 第二次修改
└── tc_Ea1qS6tU8y/
    └── v1.json
```
