# Phase 4.4: 后端 API 扩展

> **优先级:** P1
> **预估工作量:** 4-6 小时

---

## 🎯 目标

扩展后端 API，支持：
1. `/api/v1/config/reset` - 恢复出厂设置（P0 Bug 修复）
2. `/api/v1/config/validate` - 配置实时校验
3. `/api/v1/config/export` - 导出配置为 JSON
4. `/api/v1/config/import` - 从 JSON 导入配置
5. `/api/v1/config/health` - LLM 健康度诊断

---

## 🔧 API 实现

### 1. 恢复出厂设置

**文件:** `backend/src/controller/config_controller.py`

```python
@router.post("/reset")
async def reset_to_factory(
    request: ResetConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """
    恢复出厂设置
    
    - 二次确认校验
    - 加载出厂默认配置
    - 保存为新版本
    - 记录审计日志
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="需要二次确认"
        )
    
    try:
        # 获取出厂配置
        factory_config = await config_manager.get_factory_config()
        
        # 保存为新版本
        version = await config_manager.save_config(
            config_snapshot=factory_config,
            description=f"恢复出厂设置: {request.reason or '无'}",
            created_by=current_user.id,
            is_factory_reset=True
        )
        
        # 记录审计日志
        from src.repository.config_repository import ConfigAuditLogRepository
        from src.models.config import ConfigAction
        
        audit_repo = ConfigAuditLogRepository()
        current_version_id = config_manager.current_version_id
        
        await audit_repo.create({
            "action": ConfigAction.RESET,
            "from_version": current_version_id,
            "to_version": version.id,
            "user": current_user.username
        })
        
        return {
            "success": True,
            "version_id": version.id,
            "message": "已恢复出厂设置"
        }
    except Exception as e:
        logger.error(f"恢复出厂设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 2. 配置实时校验

**文件:** `backend/src/controller/config_controller.py`

```python
@router.post("/validate")
async def validate_config(request: ValidateConfigRequest):
    """
    配置实时校验
    
    - 复用 LLMConfigValidator
    - 返回校验错误列表
    """
    validator = LLMConfigValidator()
    errors = validator.validate(request.config)
    
    return {
        "valid": len(errors) == 0,
        "errors": [
            {
                "field": e.field,
                "message": e.message,
                "severity": e.severity
            }
            for e in errors
        ]
    }
```

**Schema:**

```python
class ValidateConfigRequest(BaseModel):
    config: dict = Field(..., description="待校验的配置")

class ValidationError(BaseModel):
    field: str
    message: str
    severity: str  # error/warning/info

class ValidateConfigResponse(BaseModel):
    valid: bool
    errors: list[ValidationError]
```

### 3. 导出配置

**文件:** `backend/src/controller/config_controller.py`

```python
@router.get("/export")
async def export_config(
    version_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    导出配置为 JSON
    
    - 支持指定版本
    - 默认导出当前版本
    """
    if version_id:
        config = await config_manager.get_version(version_id)
    else:
        config = await config_manager.get_current_config()
    
    return {
        "version_id": config.id,
        "exported_at": datetime.now().isoformat(),
        "exported_by": current_user.id,
        "config": config.config_snapshot
    }
```

### 4. 导入配置

**文件:** `backend/src/controller/config_controller.py`

```python
@router.post("/import")
async def import_config(
    request: ImportConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """
    从 JSON 导入配置
    
    - 校验配置格式
    - 保存为新版本
    - 记录审计日志
    """
    # 校验配置
    validator = LLMConfigValidator()
    errors = validator.validate(request.config)
    
    if errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "配置校验失败",
                "errors": [e.dict() for e in errors]
            }
        )
    
    # 保存为新版本
    version = await config_manager.save_config(
        config_snapshot=request.config,
        description=f"导入配置: {request.description or '无'}",
        created_by=current_user.id
    )
    
    return {
        "success": True,
        "version_id": version.id,
        "message": "配置导入成功"
    }
```

**Schema:**

```python
class ImportConfigRequest(BaseModel):
    config: dict = Field(..., description="导入的配置")
    description: Optional[str] = Field(None, description="导入说明")
```

### 5. LLM 健康度诊断

**文件:** `backend/src/controller/config_health_controller.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from src.config import config_manager

router = APIRouter(prefix="/api/v1/config", tags=["config-health"])

@router.post("/health")
async def run_health_diagnostic(request: HealthDiagnosticRequest):
    """
    LLM 健康度诊断
    
    - 调用 LLM 分析配置
    - 返回评分与建议
    - 缓存 5 分钟（使用 Redis）
    """
    # 计算配置哈希（用于缓存）
    config_hash = hash_config(request.config)
    
    # 检查 Redis 缓存
    from src.infrastructure.redis import get_redis_client
    redis = get_redis_client()
    cached = redis.get(f"health_diagnostic:{config_hash}")
    if cached:
        import json
        return json.loads(cached)
    
    try:
        # 调用健康诊断服务
        service = ConfigHealthService()
        result = await service.diagnose(request.config)
        
        # 缓存结果到 Redis（5 分钟）
        import json
        redis.setex(
            f"health_diagnostic:{config_hash}",
            300,  # 5 分钟
            json.dumps(result)
        )
        
        return result
    except Exception as e:
        # 降级到本地规则评分
        service = ConfigHealthService()
        return service.local_score(request.config)
```

**Schema:**

```python
class HealthDiagnosticRequest(BaseModel):
    config: dict = Field(..., description="当前配置")

class DiagnosticSuggestion(BaseModel):
    priority: str  # high/medium/low
    issue: str
    suggestion: str
    config_path: str
    current_value: str
    recommended_value: str

class HealthDiagnosticResponse(BaseModel):
    score: int = Field(..., ge=0, le=100)
    score_basis: str
    suggestions: list[DiagnosticSuggestion]
```

---

## 🧠 健康诊断服务

**文件:** `backend/src/service/config_health_service.py`

```python
import hashlib
import json
from typing import Any

class ConfigHealthService:
    """配置健康诊断服务"""
    
    async def diagnose(self, config: dict) -> dict:
        """
        使用 LLM 进行健康诊断
        
        1. 构建 Prompt
        2. 调用 LLM (qwen-turbo)
        3. 解析结果
        4. 返回诊断报告
        """
        # 从 PromptManager 获取诊断 Prompt
        prompt = await prompt_manager.get_prompt(
            "config_health_diagnosis",
            variables={
                "config_json": json.dumps(config, indent=2, ensure_ascii=False),
                "current_issues": self._detect_known_issues(config),
                "usage_context": "儿童发展评估系统"
            }
        )
        
        # 调用 LLM
        llm = await llm_factory.create(provider="dashscope", model="qwen-turbo")
        response = await llm.ainvoke(prompt)
        
        # 解析结果（使用 json-repair 容错）
        try:
            import json_repair
            result = json_repair.loads(response.content)
            return HealthDiagnosticResponse(**result).dict()
        except Exception:
            # 解析失败，降级到本地规则
            return self.local_score(config)
    
    def local_score(self, config: dict) -> dict:
        """
        本地规则评分（降级备用）
        
        权重：
        - LLM 凭证: 30%
        - 核心场景模型: 25%
        - RAG 配置: 20%
        - 业务规则: 15%
        - 系统设置: 10%
        """
        score = 0
        
        # LLM 凭证 (30%)
        llm_providers = config.get("llm_providers", {})
        if len(llm_providers) > 0:
            score += 30
        
        # 核心场景模型 (25%)
        scene_configs = config.get("llm_scene_configs", {})
        recommended_models = {"qwen-max", "qwen-plus"}
        if any(sc.get("model") in recommended_models for sc in scene_configs.values()):
            score += 25
        
        # RAG 配置 (20%)
        rag_retrieval = config.get("rag_retrieval", {})
        if rag_retrieval.get("strategy") and rag_retrieval.get("chunk_size"):
            score += 20
        
        # 业务规则 (15%)
        rules = config.get("rules", {})
        if len(rules) > 0:
            score += 15
        
        # 系统设置 (10%)
        system = config.get("system", {})
        if system.get("logging") and system.get("paths"):
            score += 10
        
        return {
            "score": score,
            "score_basis": "基于本地规则评分（降级模式）",
            "suggestions": []
        }
    
    def _detect_known_issues(self, config: dict) -> str:
        """检测已知问题"""
        issues = []
        
        # 检查 RAG 检索阈值
        rag_threshold = config.get("rag_retrieval", {}).get("score_threshold", 0)
        if rag_threshold < 0.25:
            issues.append(f"RAG 检索阈值偏低 ({rag_threshold})，建议 ≥0.25")
        
        # 检查未配置的提供商
        llm_providers = config.get("llm_providers", {})
        if not llm_providers:
            issues.append("未配置任何 LLM 提供商")
        
        return "\n".join(issues)

def hash_config(config: dict) -> str:
    """计算配置哈希（用于缓存）"""
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()
```

---

## 📊 ConfigManager 扩展

**文件:** `backend/src/config/core/manager.py`

```python
class ConfigManager:
    # ... 现有代码
    
    async def get_factory_config(self) -> dict:
        """
        获取出厂默认配置
        
        从 .env.dev 或硬编码默认值加载
        """
        # 加载默认配置
        factory_config = {
            "llm_providers": {
                "dashscope": {
                    "api_key": os.getenv("DASHSCOPE_API_KEY", "")
                }
            },
            "llm_scene_configs": {
                "assessment": {
                    "provider": "dashscope",
                    "model": "qwen-plus",
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                # ... 其他场景
            },
            # ... 其他默认配置
        }
        
        return factory_config
    
    async def reset_to_factory(self, user_id: str) -> ConfigVersion:
        """
        恢复到出厂设置
        
        1. 获取出厂配置
        2. 保存为新版本
        3. 记录审计日志
        """
        factory_config = await self.get_factory_config()
        
        version = await self.save_config(
            config_snapshot=factory_config,
            description="恢复出厂设置",
            created_by=user_id,
            is_factory_reset=True
        )
        
        return version
```

---

## ✅ 验收清单

- [ ] **恢复出厂设置**
  - [ ] `/reset` 路由实现
  - [ ] 二次确认校验
  - [ ] 审计日志记录
  - [ ] 测试通过

- [ ] **配置校验**
  - [ ] `/validate` 路由实现
  - [ ] 复用 LLMConfigValidator
  - [ ] 返回错误列表
  - [ ] 测试通过

- [ ] **导入导出**
  - [ ] `/export` 路由实现
  - [ ] `/import` 路由实现
  - [ ] 配置校验
  - [ ] 测试通过

- [ ] **健康诊断**
  - [ ] `/health` 路由实现
  - [ ] LLM 诊断服务
  - [ ] 缓存策略（5 分钟）
  - [ ] 降级策略（本地规则）
  - [ ] 测试通过

---

## 📝 实施步骤

1. **Step 1:** 实现 /reset 路由
   - ResetConfigRequest Schema
   - ConfigManager.get_factory_config()
   - 审计日志记录
   - 测试

2. **Step 2:** 实现 /validate 路由
   - ValidateConfigRequest Schema
   - 复用 LLMConfigValidator
   - 测试

3. **Step 3:** 实现 /export 和 /import 路由
   - ImportConfigRequest Schema
   - 配置校验
   - 测试

4. **Step 4:** 实现 /health 路由
   - ConfigHealthService
   - LLM 诊断
   - 缓存策略
   - 降级策略
   - 测试

---

**返回总览：** [06-phase-4-00-overview.md](./06-phase-4-00-overview.md)
