# Phase 2-7: PromptManager 拆分

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `3.4 P2` 节
> **所属 Phase**: Phase 2

## 需求定义

将 `PromptManager`（444 行）按单一职责拆分，消除混合的版本管理、A/B 测试、缓存失效、影响分析等职责。

## 验收标准

- [ ] 单类不超过 200 行
- [ ] 门面类对外 API 保持兼容
- [ ] 子服务通过依赖注入获取
- [ ] 现有测试全部通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/prompt/manager.py` | 删除 | 原 444 行文件 |
| `backend/src/core/prompt/version_manager.py` | 新增 | PromptVersionManager（版本管理，~200 行） |
| `backend/src/core/prompt/ab_tester.py` | 新增 | PromptABTester（A/B 测试，~150 行） |
| `backend/src/core/prompt/cache_invalidator.py` | 新增 | PromptCacheInvalidator（缓存失效，~80 行） |
| `backend/src/core/prompt/impact_analyzer.py` | 新增 | PromptImpactAnalyzer（影响分析，~150 行） |
| `backend/src/core/prompt/facade.py` | 新增 | PromptFacade（门面，~100 行） |

## 拆分方案

### 职责划分

| 子服务 | 职责 | 原 PromptManager 方法 |
|--------|------|---------------------|
| `PromptVersionManager` | 版本创建、回滚、列表、对比 | `create_version`, `rollback`, `list_versions`, `compare_versions` |
| `PromptABTester` | A/B 测试创建、切换、结果分析 | `create_ab_test`, `toggle_ab_test`, `get_ab_results` |
| `PromptCacheInvalidator` | 缓存失效、通知 | `invalidate_cache`, `_notify_subscribers` |
| `PromptImpactAnalyzer` | 影响分析、代码引用扫描 | `analyze_impact`, `_scan_code_references` |

### 门面类实现

```python
"""
提示词管理门面类

协调各提示词子服务，对外提供统一管理 API。
"""

from typing import Optional

from src.core.prompt.version_manager import PromptVersionManager
from src.core.prompt.ab_tester import PromptABTester
from src.core.prompt.cache_invalidator import PromptCacheInvalidator
from src.core.prompt.impact_analyzer import PromptImpactAnalyzer


class PromptFacade:
    """提示词管理门面类"""

    def __init__(
        self,
        version_mgr: PromptVersionManager,
        ab_tester: PromptABTester,
        cache_inv: PromptCacheInvalidator,
        impact_analyzer: PromptImpactAnalyzer,
    ):
        self._version_mgr = version_mgr
        self._ab_tester = ab_tester
        self._cache_inv = cache_inv
        self._impact_analyzer = impact_analyzer

    async def create_version(self, prompt_id: str, content: str) -> dict:
        version = await self._version_mgr.create_version(prompt_id, content)
        await self._cache_inv.invalidate(prompt_id)
        return version

    async def rollback(self, prompt_id: str, version_id: str) -> dict:
        result = await self._version_mgr.rollback(prompt_id, version_id)
        await self._cache_inv.invalidate(prompt_id)
        return result

    async def create_ab_test(self, prompt_id: str, variants: list) -> dict:
        return await self._ab_tester.create_ab_test(prompt_id, variants)

    async def analyze_impact(self, prompt_id: str, new_content: str) -> dict:
        return await self._impact_analyzer.analyze(prompt_id, new_content)


# 单例
prompt_facade: Optional[PromptFacade] = None


def get_prompt_facade() -> PromptFacade:
    global prompt_facade
    if prompt_facade is None:
        prompt_facade = PromptFacade(
            version_mgr=PromptVersionManager(),
            ab_tester=PromptABTester(),
            cache_inv=PromptCacheInvalidator(),
            impact_analyzer=PromptImpactAnalyzer(),
        )
    return prompt_facade
```

## 测试方案

1. 版本创建/回滚正确
2. A/B 测试切换正常
3. 缓存失效通知正确
4. 影响分析结果准确

## 注意事项

- 版本创建后需立即使缓存失效
- A/B 测试需记录流量分配比例
- 影响分析需扫描代码中的 prompt 引用
