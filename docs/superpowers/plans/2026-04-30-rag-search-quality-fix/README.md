# RAG 搜索质量修复方案

> 基于对代码库 21 个问题的逐项核实，全部确认存在。
> 本方案按依赖关系拆为 6 个独立文件，每个文件可独立实施和验证。

---

## 文件索引

| 文件 | 阶段 | 问题数 | 改动文件数 | 说明 |
|------|------|--------|-----------|------|
| [01-age-filter-removal.md](01-age-filter-removal.md) | 先行 | — | 24 | 年龄过滤整体移除，为后续修复简化代码 |
| [02-runtime-crashes.md](02-runtime-crashes.md) | P0 | 4 | 5 | 消除 TypeError/AttributeError/NameError |
| [03-score-fusion.md](03-score-fusion.md) | P1 | 5 | 3+ | 重写分数融合为核心修复 |
| [04-query-classification.md](04-query-classification.md) | P2 | 2 | 4 | 统一查询分类器和枚举 |
| [05-silent-failures.md](05-silent-failures.md) | P3 | 4 | 5 | 修复静默功能失效 |
| [06-design-defects.md](06-design-defects.md) | P4 | 6 | 6 | 消除设计缺陷 |
| [07-query-decomposition.md](07-query-decomposition.md) | P5 | 新增 | 2+ | 复杂查询子查询分解，拆为多个简单查询独立检索后归并 |

---

## 执行顺序

```
01 年龄过滤移除（先行简化，为后续减少干扰）
 │
 ├─→ 02 P0 运行时崩溃（消除崩溃，P0-3 暂缓）
 │
 └─→ 03 P1 分数融合（不依赖 PageIndex，可独立测试）
      │
      ├─→ 04 P2 查询分类器
      ├─→ 05 P3 静默失效（P3-1 暂缓）
      └─→ 06 P4 设计缺陷（P4 之间无硬依赖，可并行）
           │
           └─→ 07 P5 查询分解（依赖 03 RRF + 04 分类器统一后才能完整测试）
```

**硬依赖**：
- 01 → 02/03（年龄移除后代码更干净，避免修复冲突）
- 03 + 04 → 07（RRF 融合生效 + 分类器统一后，复杂查询分解的独立检索和归并才能正确工作）

**可并行**：02（不含 P0-3）、04、05（不含 P3-1）、06 之间无依赖。

**暂缓项**（PageIndex 暂时不引入）：
- P0-3（PageIndex 增强步骤修复）
- P3-1（PageIndex score/confidence 字段统一）
- 以上两项待 PageIndex 正式上线后执行

---

## 全局原则

1. **零迁移**：直接删除旧代码，不留兼容层
2. **每阶段验证**：完成一个阶段文件后跑 `pytest` + 手动搜索验证，再进入下一个
3. **先删后改**：01 年龄过滤移除先行，后续修复不再需要考虑年龄参数
4. **阈值重校准**：P1 改完分数体系后，下游阈值（`rag_search_min_similarity_threshold` 等）必须重新调整

---

## 审核修正记录

基于代码核实，对原方案做以下修正：

| 原方案内容 | 核实发现 | 修正 |
|-----------|---------|------|
| 年龄过滤涉及 3+ 文件 | 实际涉及 **24 个文件** | 扩大范围，单独成文件 |
| P0-1 `await` 同步方法会 TypeError | Python 中 `await` 非协程返回值不报错，TypeError 来自参数名错误 | 修正为：去掉 `await`，修正参数名 |
| P1 只改 `merge_results()` | 实际有两条独立路径：`merge_results()` 和 `merge_for_search()` | 两条路径都要改 |
| P1 改完分数即可 | 下游 `result_processor.py` 的分数映射区间 `[threshold, 0.65] → [0.55, 0.98]` 基于旧分数范围 | 需同步重校准 |
| P1-5 只需对齐 YAML `fusion_mode` | YAML 中 `vector_weight` 也是死配置（代码算 `1-bm25_weight`） | 一并清理 |
| 问题 17（三重惩罚）| 代码确认为双重惩罚（0.3 × 0.3），非三重 | 合并到 P1-2 中处理 |
| P0-4 NameError | `layered_config` 已在 L186 定义，L389 可正常访问，无 NameError | 修正为：统一配置读取方式，消除 stale 快照；加 `.get()` 防 KeyError |
| P5-2 reranker 空 query | `rerank(query="", nodes=nodes)` 传空 query 对 bge-reranker 无效，logits 退化为随机值 | 修正为：`rerank(query=original_query, nodes=nodes)`，传入原始查询供相关性判断 |
| PageIndex 相关项（P0-3, P3-1）| PageIndex 暂不引入 | 标注为暂缓，执行顺序解除 P0-3 对 P1 的阻塞 |
