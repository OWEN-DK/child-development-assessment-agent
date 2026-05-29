# 知识问答系统修复方案 V2

**基于**: latest-result.json（2026-05-29 10:08 运行数据）  
**日期**: 2026-05-29  
**修复范围**: 3 个新问题 + 1 个遗留问题

---

## 新数据运行结果对比

| 指标 | 旧数据 (result.json) | 新数据 (latest-result.json) | 目标 |
|------|---------------------|---------------------------|------|
| phase_name | "阶段"（无意义） | "基础激活与情绪释放期（第1-2周）" ✅ | 有意义名称 |
| 阶段数 | 1 | 1 ❌ | 2 |
| 总天数 | 13 | 12 ❌ | 28 |
| 休息日 | 无 | 无 ❌ | 每周 2 天 |
| 多书引用 | 仅《运动改变大脑》 | 3 本书 ✅ | ≥2 本 |
| partial | True | True | False |
| 运动详情 | 降级路径，参数不完整 | 正常路径，参数完整 ✅ | 完整 |

### 新数据改善
- ✅ F1 Phase alias 生效：phase_name 不再是"阶段"
- ✅ 多书引用改善：search_coverage = {'学习之道': 6, '孩子如何思考': 6, '运动改变大脑': 6}
- ✅ 运动参数完整：每个 exercise 有 description、duration_min、intensity、sets 等

### 仍存在的问题

#### 问题 A: 只有 1 个阶段（应为 2 个）

**现象**: LLM 生成的 outline 只有 1 个 phase（PH01），尽管 prompt 已更新为 "固定 2 个阶段"。

**根因**: `qwen3.5-27b` 对 "固定 2 个阶段" 的硬约束服从率不足。LLM 自行决定只生成 1 个阶段。

**修复**:
1. **代码层** (`plan_outline.py`): 新增 `_ensure_min_phases()` 函数，在 outline 生成后自动补全缺失阶段
2. **Prompt 层** (`templates.py`): 强化约束措辞为 "phases 数组必须恰好包含 2 个阶段（PH01 + PH02），不能多也不能少"

#### 问题 B: 运动方案排得太满，没有休息日

**现象**: Week 1 排了 7 天全部训练（爬行+舞动、武术+散步、爬行+自由舞蹈...），没有任何休息日。

**根因**: 
1. expand prompt 中 "每周至少安排 1-2 天休息" 措辞太弱，LLM 选择忽略
2. outline prompt 没有要求每天标记是否为休息日
3. 代码层没有强制校验

**修复**:
1. **Outline prompt**: 新增 "每周安排 5 天训练 + 2 天休息，休息日不安排运动"
2. **Expand prompt**: 强化为 "每周必须恰好安排 2 天休息日，休息日的 main_exercises 数组必须为空 []"
3. **代码层** (`plan_outline.py`): 新增 `_enforce_rest_days()` 函数，强制每周最多 5 天训练

#### 问题 C: 总时长只有 12 天（应为 28 天）

**现象**: plan_summary.total_duration_days = 12，实际 phases 结构只有 1 阶段 2 周 12 天。

**根因**: 问题 A 的级联 — 只有 1 个阶段，自然只有 12 天。

**修复**: 修复问题 A 后自动解决。另外修复了 `_derive_plan_summary` 中优先使用 outline 旧值的 bug，改为始终使用从 phases 结构计算的值。

#### 问题 D: partial=True

**现象**: 结果 partial=True，但无明显数据缺失。

**根因** (确认): S3 的 citations 被 `verify_citations.py` 全部剔除（excerpt < 10 字符），触发 partial=True。

**修复**: 已在 FIX-PLAN V1 中提出（F11），本次未改动，留待后续迭代。

---

## 本次修复清单

| # | 问题 | 文件 | 改动 | 优先级 |
|---|------|------|------|--------|
| F9 | 阶段数不足自动补全 | `nodes/plan_outline.py` | +55 行 | P0 |
| F10 | 休息日强制校验 | `nodes/plan_outline.py` | +20 行 | P0 |
| F11 | outline prompt 强化 | `prompts/templates.py` | +15 行 | P0 |
| F12 | expand prompt 强化休息日 | `prompts/templates.py` | +4 行 | P0 |
| F13 | total_duration_days 计算修复 | `nodes/plan_assemble.py` | +8 行 | P1 |

### F9: `_ensure_min_phases()` — 阶段数自动补全

**位置**: `plan_outline.py` 新增函数 + 集成到 plan_outline_node

**逻辑**: 
- 检查 phases 数量，不足 2 个时自动从已有阶段复制并调整
- 新阶段的 phase_id、name、goal 自动递增
- weeks 的 week_index 自动偏移

**集成点**: line 130-135，在 exercise 完整性校验之前

### F10: `_enforce_rest_days()` — 休息日强制校验

**位置**: `plan_outline.py` 新增函数

**逻辑**:
- 遍历每个 phase 的每个 week
- 如果训练天数 > 5，将多余的天（从后面开始）转为休息日
- 休息日 = main_exercises 清空为空数组

**集成点**: line 137，在 `_ensure_min_phases` 之后

### F11: Outline Prompt 强化

**改动**:
- 任务描述: "严格划分 2 个阶段" + "每周 5 天训练 + 2 天休息"
- 新增硬性数量约束区块: phases=2、每周=7天(5训练+2休息)、总计=4周28天
- 自审核清单: 增加 phases 恰好 2 个、每周恰好 7 天、总 28 天的检查项

### F12: Expand Prompt 强化休息日

**改动**:
- "每周至少安排 1-2 天休息" → "每周必须恰好安排 2 天休息日"
- 新增: "不要把所有 7 天都排满运动，孩子需要恢复时间"

### F13: total_duration_days 计算修复

**改动**: `_derive_plan_summary()` 中 `total_duration_days` 从优先使用 outline 旧值改为始终使用 phases 结构计算值。

---

## 预期修复效果

| 指标 | 修复前 | 修复后（预期） |
|------|--------|---------------|
| 阶段数 | 1 | 2（自动补全） |
| 总天数 | 12 | 28 |
| 休息日 | 0 | 每周 2 天 |
| 训练天/周 | 7（过满） | 5 |
| phase_name | ✅ 有意义 | ✅ 保持 |
| total_duration_days | 12（错误） | 28（正确） |

---

## 验证方案

重新运行同一问题，检查：
1. `phases` 数组是否恰好有 2 个阶段
2. 每个 phase 是否有 2 周
3. 每周是否有 5 天训练 + 2 天休息（main_exercises 为空的天）
4. `plan_summary.total_duration_days` 是否为 28
5. `plan_summary.total_phases` 是否为 2
6. 运动参数是否完整（有 description、duration_min 等）

---

## 已知局限

1. **F5 来源配额局限**: section 级搜索仍可能被单书垄断，需后续实现问题预处理
2. **F11 partial 标记**: verify_citations 的 excerpt 检查过于激进，需后续降级为 warning
3. **LLM 服从率**: `qwen3.5-27b` 对硬约束的服从率不稳定，代码层自动补全是必要保障

---

## 补充修复（V2.1）

### 问题发现

单元测试发现：LLM 生成 Week 2 时只有 5 天（没有补全休息日），导致 `total_duration_days` 计算为 24（而非 28）。

### F14: `_ensure_full_weeks()` — 补全每周 7 天

**位置**: `plan_outline.py` 新增函数

**逻辑**:
- 遍历每个 phase 的每个 week
- 不足 7 天的周：自动补全缺失天（`main_exercises=[]`，标记为休息日）
- 超过 7 天的周：截断到 7 天

**执行顺序**（在 plan_outline_node 中）:
1. `_ensure_min_phases` — 确保 2 个阶段
2. `_ensure_full_weeks` — 确保每周恰好 7 天
3. `_enforce_rest_days` — 确保每周最多 5 天训练

**测试结果**:
```
阶段数: 2
PH01: 基础适应期
  Week1: 7天 (5训练 + 2休息)
  Week2: 7天 (5训练 + 2休息)
PH02: 能力提升期
  Week3: 7天 (5训练 + 2休息)
  Week4: 7天 (5训练 + 2休息)

total_duration_days: 28 ✅
total_training_days: 20 ✅
total_phases: 2 ✅
```
