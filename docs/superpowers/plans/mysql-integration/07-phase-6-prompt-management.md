# Phase 6: 提示词管理系统实现

> 本文档是 MySQL + Redis 集成重构实施方案的一部分
> 
> **返回索引：** [README.md](./README.md) | [项目概览](./00-overview.md)

---

## Phase 6: 提示词管理系统实现（周期：2 天）

### 目标
实现提示词版本控制和 MySQL 存储，开发前端提示词管理页面，支持在线编辑和预览，实现 A/B 测试流量分发功能。

### 架构设计

```
┌─────────────────────────────────────────────────┐
│           前端提示词管理页面                       │
│    - 提示词列表                                  │
│    - 在线编辑器                                  │
│    - 版本对比                                    │
│    - A/B 测试配置                                 │
└─────────────────────────────────────────────────┘
                      ↓ API
┌─────────────────────────────────────────────────┐
│      提示词管理器 (PromptManager)                │
│    - 版本控制                                    │
│    - MySQL 存储 + Redis 缓存                       │
│    - A/B 测试分流                                 │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         MySQL 数据库                             │
│    - prompt_versions                             │
│    - prompt_ab_tests                             │
└─────────────────────────────────────────────────┘
```

---

### Task 6.1: 创建提示词管理器

**Files:**
- Create: `backend/src/core/prompt/manager.py`

- [ ] **Step 1: 创建提示词管理器**

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import hashlib
from typing import Optional
from src.core.database import db_session_factory
from src.service.cache_service import cache_service
from src.utils.logger import logger

class PromptManager:
    """提示词管理器（MySQL 存储 + Redis 缓存）"""
    
    def __init__(self):
        self.db_session_factory = db_session_factory
        self.cache = cache_service
    
    async def get_prompt(
        self,
        prompt_key: str,
        version: str = None,
        ab_test_id: str = None,
    ) -> str:
        """获取提示词"""
        # 构建缓存键
        cache_key = f"prompt:{prompt_key}:{version or 'latest'}:{ab_test_id or 'default'}"
        
        # 查缓存
        cached = await self.cache.get(cache_key)
        if cached:
            logger.debug(f"提示词缓存命中：{cache_key}")
            return cached
        
        # 查数据库
        async with self.db_session_factory() as session:
            from src.models.prompt import PromptVersion
            
            if version:
                # 指定版本
                stmt = select(PromptVersion).where(
                    PromptVersion.prompt_key == prompt_key,
                    PromptVersion.version == version,
                )
            else:
                # 最新版本
                stmt = select(PromptVersion).where(
                    PromptVersion.prompt_key == prompt_key
                ).order_by(
                    PromptVersion.created_at.desc()
                ).limit(1)
            
            result = await session.execute(stmt)
            prompt_version = result.scalar_one_or_none()
            
            if not prompt_version:
                logger.warning(f"提示词未找到：{prompt_key}")
                return self._get_fallback_prompt(prompt_key)
            
            # A/B 测试分流
            if ab_test_id:
                prompt_content = await self._apply_ab_test(
                    session,
                    prompt_version,
                    ab_test_id,
                )
            else:
                prompt_content = prompt_version.content
            
            # 写入缓存
            await self.cache.set_with_jitter(
                cache_key,
                prompt_content,
                base_ttl=3600,
                tags=["prompt", prompt_key],
            )
            
            return prompt_content
    
    async def create_prompt_version(
        self,
        prompt_key: str,
        content: str,
        description: str = None,
        created_by: str = None,
    ) -> str:
        """创建新版本"""
        async with self.db_session_factory() as session:
            from src.models.prompt import PromptVersion
            
            # 计算内容哈希
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            # 检查是否重复
            stmt = select(PromptVersion).where(
                PromptVersion.prompt_key == prompt_key,
                PromptVersion.content_hash == content_hash,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"提示词内容未变化，返回现有版本：{existing.version}")
                return existing.version
            
            # 获取最新版本号
            stmt = select(PromptVersion).where(
                PromptVersion.prompt_key == prompt_key
            ).order_by(
                PromptVersion.created_at.desc()
            ).limit(1)
            
            result = await session.execute(stmt)
            latest = result.scalar_one_or_none()
            
            # 生成新版本号
            if latest:
                version_parts = latest.version.split('.')
                version_parts[-1] = str(int(version_parts[-1]) + 1)
                new_version = '.'.join(version_parts)
            else:
                new_version = "1.0.0"
            
            # 创建新版本
            prompt_version = PromptVersion(
                prompt_key=prompt_key,
                version=new_version,
                content=content,
                content_hash=content_hash,
                description=description,
                created_by=created_by,
            )
            
            session.add(prompt_version)
            await session.commit()
            
            # 清除缓存
            await self.cache.invalidate_tag(f"prompt:{prompt_key}")
            
            logger.info(f"提示词新版本已创建：{prompt_key} v{new_version}")
            return new_version
    
    async def list_versions(self, prompt_key: str) -> list[dict]:
        """列出所有版本"""
        async with self.db_session_factory() as session:
            from src.models.prompt import PromptVersion
            
            stmt = select(
                PromptVersion.version,
                PromptVersion.description,
                PromptVersion.created_by,
                PromptVersion.created_at,
            ).where(
                PromptVersion.prompt_key == prompt_key
            ).order_by(
                PromptVersion.created_at.desc()
            )
            
            result = await session.execute(stmt)
            return [
                {
                    "version": row[0],
                    "description": row[1],
                    "created_by": row[2],
                    "created_at": row[3],
                }
                for row in result.all()
            ]
    
    async def compare_versions(
        self,
        prompt_key: str,
        version_1: str,
        version_2: str,
    ) -> dict:
        """对比两个版本"""
        async with self.db_session_factory() as session:
            from src.models.prompt import PromptVersion
            
            stmt = select(PromptVersion).where(
                PromptVersion.prompt_key == prompt_key,
                PromptVersion.version.in_([version_1, version_2]),
            )
            
            result = await session.execute(stmt)
            versions = {v.version: v for v in result.scalars().all()}
            
            if len(versions) != 2:
                raise ValueError("版本未找到")
            
            v1 = versions[version_1]
            v2 = versions[version_2]
            
            # 简单对比
            lines_1 = v1.content.split('\n')
            lines_2 = v2.content.split('\n')
            
            added_lines = set(lines_2) - set(lines_1)
            removed_lines = set(lines_1) - set(lines_2)
            
            return {
                "version_1": {
                    "version": version_1,
                    "content": v1.content,
                    "created_at": v1.created_at,
                },
                "version_2": {
                    "version": version_2,
                    "content": v2.content,
                    "created_at": v2.created_at,
                },
                "diff": {
                    "added": list(added_lines),
                    "removed": list(removed_lines),
                    "added_count": len(added_lines),
                    "removed_count": len(removed_lines),
                }
            }
    
    def _get_fallback_prompt(self, prompt_key: str) -> str:
        """获取兜底提示词"""
        fallbacks = {
            "rag_query_rewrite": "请优化以下查询，使其更适合检索：{query}",
            "child_assessment": "请评估以下儿童的发展状态：{child_profile}",
            "report_generation": "请生成一份儿童发展评估报告：{data}",
        }
        return fallbacks.get(prompt_key, "You are a helpful assistant.")
    
    async def _apply_ab_test(
        self,
        session: AsyncSession,
        prompt_version,
        ab_test_id: str,
    ) -> str:
        """应用 A/B 测试分流"""
        from src.models.prompt import PromptABTest
        
        stmt = select(PromptABTest).where(
            PromptABTest.id == ab_test_id,
            PromptABTest.prompt_key == prompt_version.prompt_key,
        )
        
        result = await session.execute(stmt)
        ab_test = result.scalar_one_or_none()
        
        if not ab_test or not ab_test.is_active:
            return prompt_version.content
        
        # 根据流量分组返回不同内容
        # 这里简化处理，实际应使用用户 ID 哈希
        import random
        if random.random() < ab_test.variant_a_ratio:
            return ab_test.variant_a_content
        else:
            return ab_test.variant_b_content
```

---

### Task 6.2: 创建提示词 API

**Files:**
- Modify: `backend/src/controller/prompt_controller.py`

- [ ] **Step 1: 创建提示词控制器**

```python
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from src.core.prompt.manager import PromptManager

router = APIRouter()

@router.get("/prompts/{prompt_key}")
async def get_prompt(
    prompt_key: str,
    version: Optional[str] = None,
    ab_test_id: Optional[str] = None,
):
    """获取提示词"""
    manager = PromptManager()
    
    try:
        content = await manager.get_prompt(
            prompt_key=prompt_key,
            version=version,
            ab_test_id=ab_test_id,
        )
        return {"prompt_key": prompt_key, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/prompts/{prompt_key}/versions")
async def create_version(
    prompt_key: str,
    content: str,
    description: str = None,
    created_by: str = None,
):
    """创建新版本"""
    manager = PromptManager()
    
    version = await manager.create_prompt_version(
        prompt_key=prompt_key,
        content=content,
        description=description,
        created_by=created_by,
    )
    
    return {"version": version, "message": "版本已创建"}

@router.get("/prompts/{prompt_key}/versions")
async def list_versions(prompt_key: str):
    """列出所有版本"""
    manager = PromptManager()
    versions = await manager.list_versions(prompt_key)
    return {"versions": versions}

@router.get("/prompts/{prompt_key}/compare")
async def compare_versions(
    prompt_key: str,
    version_1: str,
    version_2: str,
):
    """对比版本"""
    manager = PromptManager()
    
    try:
        diff = await manager.compare_versions(
            prompt_key=prompt_key,
            version_1=version_1,
            version_2=version_2,
        )
        return diff
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

### Phase 6 完成验证

- [ ] 运行单元测试，验证提示词管理功能正常
- [ ] 测试版本控制和对比功能
- [ ] 验证 A/B 测试分流
- [ ] 检查缓存失效机制
- [ ] 验证前端管理页面

---

**返回索引：** [README.md](./README.md)
