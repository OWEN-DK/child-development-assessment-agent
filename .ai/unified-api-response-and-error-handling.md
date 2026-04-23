# 统一响应与异常处理规范（核心规则）
> 本规范为系统强制要求，所有开发必须严格遵守

## 1. 实体类集中管理规范
### 1.1 禁止规则
❌ 绝对禁止在 `service/`、`controller/`、`core/` 中定义 `class xxx(BaseModel)`
### 1.2 强制要求
✅ 所有 Pydantic 实体类必须统一放置在 `backend/src/schemas/` 目录下，按业务模块组织：
- `schemas/common.py` - 通用模型（API响应、分页、基础异常等）
- `schemas/assessment.py` - 评估模块所有模型
- `schemas/rag.py` - RAG模块所有模型
- `schemas/test_case.py` - 测试模块所有模型
- `schemas/config.py` - 配置模块所有模型
- `schemas/prompt.py` - 提示词模块所有模型
- `schemas/monitoring.py` - 监控模块所有模型
- `schemas/events.py` - SSE事件模型
### 1.3 导入规则
所有实体类通过统一入口导入：`from src.schemas import xxx` 或 `from src.schemas.xxx import xxx`

## 2. 类职责拆分规范
### 2.1 禁止规则
❌ 单类不得超过 **500行**（含空行和注释），违反必须拆分
### 2.2 强制要求
✅ 采用门面模式对外提供统一API，内部协调子服务
✅ 每个类仅负责单一明确的业务职责
✅ 子服务通过依赖注入获取，而非直接实例化

## 3. 冗余代码消除规范
### 3.1 禁止规则
❌ 禁止重复定义相同功能的函数，必须提取至 `utils/` 目录对应工具模块
### 3.2 高频重复模式提取方案
| 重复模式 | 出现次数 | 提取位置 | 提供函数 |
|---------|---------|---------|---------|
| 数据库Session获取 | 26处 | `utils/db.py` | `get_db_session()`、`execute_with_session()` |
| 错误处理模板 | 100+处 | `utils/response.py` | `handle_api_error()`、`not_found()`、`server_error()` |
| 模型序列化 | 30+处 | `utils/serializers.py` | `safe_isoformat()`、`safe_enum_value()`、`model_to_dict()` |
| 文件操作 | 70+处 | `utils/file_ops.py` | `ensure_dir()`、`safe_remove()`、`read_json()`、`write_json()` |
| 时间处理 | 50+处 | `utils/time_utils.py` | `utc_now()`、`time_range()`、`safe_timestamp()` |
| 内容哈希 | 7处 | `utils/crypto.py` | `hash_content()` |
| ID生成 | 15处 | `utils/id_generator.py` | `generate_id()` |
### 3.3 强制要求
✅ 所有重复代码必须替换为统一工具函数，禁止自行实现相同功能

## 4. 统一响应与异常处理规范
### 4.1 响应格式要求
#### 成功响应（HTTP 200）
```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```
- `code`: 固定为0表示成功
- `message`: 提示信息
- `data`: 业务数据（可为null、对象、数组）

#### 错误响应（HTTP 4xx/5xx）
```json
{
  "code": 10001,
  "message": "请求参数校验失败",
  "error_code": "INVALID_PARAMS",
  "details": {},
  "trace_id": "xxx"
}
```
- `code`: 数字业务错误码，用于机器判断
- `message`: 用户可读中文错误信息，直接展示
- `error_code`: 大写英文错误码标识，用于前端逻辑判断和国际化
- `details`: 可选，错误额外上下文信息
- `trace_id`: 可选，请求追踪ID
### 4.2 异常处理规则
❌ 禁止直接使用 `HTTPException`
✅ 所有业务异常必须继承 `AppException`，通过全局异常处理器统一格式化
✅ 成功响应必须使用 `APIResponse.success(data)` 包装，禁止直接返回字典
### 4.3 错误码分段规范
| 错误码范围 | 模块 |
|------------|------|
| `0` | 成功 |
| `10000-10999` | 通用错误（参数校验、权限、系统异常等） |
| `11000-11999` | 评估模块 |
| `12000-12999` | RAG知识库模块 |
| `13000-13999` | RAG测试模块 |
| `14000-14999` | 配置管理模块 |
| `15000-15999` | 提示词管理模块 |
| `16000-16999` | 监控模块 |

## 5. 代码引用规范
### 5.1 禁止规则
❌ 禁止 `model/` 与 `models/` 命名混淆（原`src/model/`已重命名为`src/schemas/`）
❌ 禁止无分组排序的import语句
❌ 禁止不必要的函数内import
❌ 禁止跨feature导入（前端）
❌ 禁止从pages导入（前端）
### 5.2 强制要求
✅ 跨模块统一使用 `from src.xxx` 绝对导入
✅ import按 `标准库 → 第三方库 → 本地应用` 分组，组内按字母排序
✅ 每个包必须有 `__init__.py`，明确导出公共API
✅ 前端采用FSD Lite架构，严格遵循分层依赖规则：`pages → widgets → features → entities → shared`
