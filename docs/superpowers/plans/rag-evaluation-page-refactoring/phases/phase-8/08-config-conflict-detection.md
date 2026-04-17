# 08 - 配置冲突检测 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 08 - 配置冲突检测

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **Phase**: 8
> **需求点**: 8
> **需求来源**: spec `08c-config-validation.md`

## 目标

实现 10 条完整的配置冲突检测规则。

## 方案设计

### 冲突检测规则

| # | 规则 | 级别 | 说明 |
|---|------|------|------|
| 1 | BM25 TopK + Vector TopK 比例 | WARNING | BM25 TopK 不应远小于 Vector TopK（比例 < 0.5） |
| 2 | 融合阈值 + 权重匹配 | ERROR | 融合阈值不应大于 BM25 权重 + Vector 权重之和 |
| 3 | 重排序 initial_k >= final_k | ERROR | initial_k 必须大于等于 final_k |
| 4 | 分块大小 + 重叠比例 | WARNING | 重叠不应超过分块大小的 50% |
| 5 | 年龄过滤严格度 + 容忍度 | WARNING | 严格度高时容忍度应低 |
| 6 | LLM 温度 + TopP | WARNING | 温度高时 TopP 应低，避免过度随机 |
| 7 | 缓存 TTL + 更新频率 | WARNING | 缓存 TTL 不应远大于数据更新频率 |
| 8 | 日志级别 + 性能配置 | WARNING | DEBUG 日志级别不应在生产环境使用 |
| 9 | 数据库连接池 + 并发数 | ERROR | 连接池大小不应小于最大并发数 |
| 10 | 配置循环依赖 | ERROR | 检测配置项之间的循环依赖关系 |

### 检测引擎实现

```python
# backend/src/service/config_conflict_detector.py

class ConfigConflictDetector:
    async def detect(self, config_updates: dict, current_config: dict) -> list[Conflict]:
        """检测配置冲突"""
        conflicts = []
        merged_config = {**current_config, **config_updates}
        
        # 规则 1: BM25 TopK + Vector TopK 比例
        conflicts.extend(self._check_bm25_vector_ratio(merged_config))
        
        # 规则 2: 融合阈值 + 权重匹配
        conflicts.extend(self._check_fusion_threshold(merged_config))
        
        # 规则 3: 重排序 initial_k >= final_k
        conflicts.extend(self._check_reranker_k(merged_config))
        
        # 规则 4: 分块大小 + 重叠比例
        conflicts.extend(self._check_chunk_overlap(merged_config))
        
        # 规则 5: 年龄过滤严格度 + 容忍度
        conflicts.extend(self._check_age_filter(merged_config))
        
        # 规则 6: LLM 温度 + TopP
        conflicts.extend(self._check_llm_sampling(merged_config))
        
        # 规则 7: 缓存 TTL + 更新频率
        conflicts.extend(self._check_cache_ttl(merged_config))
        
        # 规则 8: 日志级别 + 性能配置
        conflicts.extend(self._check_log_level(merged_config))
        
        # 规则 9: 数据库连接池 + 并发数
        conflicts.extend(self._check_db_pool(merged_config))
        
        # 规则 10: 配置循环依赖
        conflicts.extend(self._check_circular_dependencies(merged_config))
        
        return conflicts
    
    def _check_bm25_vector_ratio(self, config: dict) -> list[Conflict]:
        """规则 1: BM25 TopK 不应远小于 Vector TopK"""
        bm25_k = config.get("bm25_top_k", 10)
        vector_k = config.get("vector_top_k", 10)
        if vector_k > 0 and bm25_k / vector_k < 0.5:
            return [Conflict(
                level="warning",
                rule="bm25_vector_ratio",
                message=f"BM25 TopK ({bm25_k}) 远小于 Vector TopK ({vector_k})，可能导致检索不平衡"
            )]
        return []
    
    def _check_reranker_k(self, config: dict) -> list[Conflict]:
        """规则 3: initial_k 必须大于等于 final_k"""
        initial_k = config.get("reranker_initial_k", 30)
        final_k = config.get("reranker_final_k", 5)
        if initial_k < final_k:
            return [Conflict(
                level="error",
                rule="reranker_k_order",
                message=f"重排序 initial_k ({initial_k}) 必须大于等于 final_k ({final_k})"
            )]
        return []
```

### 冲突结果格式

```typescript
interface Conflict {
  level: 'error' | 'warning'
  rule: string
  message: string
  affected_configs: string[]
}
```

### 验收标准

- [ ] 10 条冲突检测规则全部实现
- [ ] 正确检测配置冲突
- [ ] 返回冲突级别和详细说明
- [ ] ERROR 级别阻止保存，WARNING 级别允许保存
