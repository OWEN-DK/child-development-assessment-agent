# 06 - Layer 4b: 分块质量评分 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 06 - Layer 4b: 分块质量评分

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer4b_chunk_quality.py`
- Test: `backend/tests/test_placeholder.py`

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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.4.2 校验 4b: 分块质量评分` 节
> **所属 Phase**: Phase 4

## 需求定义

检查文档分块的信息密度、可读性、切分合理性。综合质量分 = 信息密度 40% + 结构化程度 30% + 切分合理性 30%。

## 验收标准

- [ ] 信息密度计算正确（停用词占比）
- [ ] 结构化程度计算正确
- [ ] 切分合理性计算正确
- [ ] 低质量比例 > 10% 时警告
- [ ] 平均质量分 < 0.6 时严重警告

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer4b_chunk_quality.py` | 新增 | Layer 4b 实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer4b_chunk_quality.py
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

CHINESE_STOP_WORDS = set(
    "的了是在有和或但而与之及对关于通过根据按照由于因此虽然然而如果那么是否什么哪里怎么"
    "可以需要应该必须能够可能已经正在将要继续开始结束进行完成提供包含包括使用应用"
    "方法过程步骤结果原因目的意义价值作用效果影响关系条件环境背景情况分析研究调查"
    "报告数据显示图表说明解释描述定义概念原理理论基础实践操作经验技巧建议提示注意"
    "问题答案回复反馈意见建议评价标准规范要求指南手册教程示例样本模板格式结构内容"
)

PROFESSIONAL_TERMS = {
    "感统训练", "精细动作", "粗大动作", "前庭觉", "本体觉", "触觉", "视觉", "听觉",
    "语言发育", "认知发展", "社交能力", "情绪管理", "注意力", "记忆力", "思维力",
    "Piaget", "Vygotsky", "蒙台梭利", "感觉统合", "运动协调", "手眼协调",
}

class Layer4bChunkQuality:
    """Layer 4b: 分块质量评分"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行分块质量评分"""
        chunks = self.test_run.chunks or []
        
        if not chunks:
            return {"status": "skipped", "data": {"reason": "缺少分块数据"}}
        
        quality_scores = []
        low_quality_count = 0
        
        for chunk in chunks:
            content = chunk.get("content", "")
            if not content:
                continue
            
            info_density = self._calc_info_density(content)
            structure_level = self._calc_structure_level(content)
            split_rationality = self._calc_split_rationality(chunk)
            
            composite = info_density * 0.4 + structure_level * 0.3 + split_rationality * 0.3
            quality_scores.append(composite)
            
            if composite < 0.3:
                low_quality_count += 1
        
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        low_quality_ratio = low_quality_count / len(quality_scores) if quality_scores else 0
        
        warnings = []
        if low_quality_ratio > 0.10:
            warnings.append({"level": "warning", "message": f"低质量分块过多 ({low_quality_ratio:.1%} > 10%)"})
        if avg_quality < 0.6:
            warnings.append({"level": "critical", "message": f"平均质量过低 ({avg_quality:.2f} < 0.6)"})
        
        return {
            "status": "completed",
            "data": {
                "avg_quality": avg_quality,
                "low_quality_ratio": low_quality_ratio,
                "low_quality_examples": self._get_low_quality_examples(chunks, quality_scores)[:3],
                "warnings": warnings,
            },
        }
    
    def _calc_info_density(self, content: str) -> float:
        """信息密度 = 1 - (停用词数 / 总字符数)（按字符统计）"""
        chars = [c for c in content if c.strip()]
        if not chars:
            return 0
        stop_word_count = sum(1 for c in chars if c in CHINESE_STOP_WORDS)
        return 1 - (stop_word_count / len(chars))
    
    def _calc_structure_level(self, content: str) -> float:
        """结构化程度 = (标题数 × 2 + 列表项数) / 段落数"""
        lines = content.split("\n")
        paragraphs = [l for l in lines if l.strip()]
        if not paragraphs:
            return 0
        
        title_count = sum(1 for l in lines if re.match(r"^#{1,6}\s", l) or re.match(r"^[一二三四五六七八九十]+[、.]", l))
        list_item_count = sum(1 for l in lines if re.match(r"^[\s]*[-*•]\s", l) or re.match(r"^\d+[.、]", l))
        
        return min(1.0, (title_count * 2 + list_item_count) / len(paragraphs))
    
    def _calc_split_rationality(self, chunk: dict) -> float:
        """切分合理性 = 以完整句子/段落结束的分块占比"""
        content = chunk.get("content", "").strip()
        if not content:
            return 0
        
        ends_with_sentence = bool(re.search(r"[。！？\n]\s*$", content))
        return 1.0 if ends_with_sentence else 0.5
    
    def _get_low_quality_examples(self, chunks: list, scores: list) -> list:
        """获取低质量示例"""
        examples = []
        for chunk, score in zip(chunks, scores):
            if score < 0.3:
                examples.append({
                    "chunk_id": chunk.get("id"),
                    "quality_score": score,
                    "content_preview": chunk.get("content", "")[:100],
                })
        return examples
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_info_density_calculation():
    """信息密度计算正确"""
    ...

@pytest.mark.asyncio
async def test_composite_score():
    """综合质量分加权平均正确"""
    ...
```

## 注意事项

- 专业术语密度作为辅助指标，不纳入综合分
- 停用词使用中文通用列表
