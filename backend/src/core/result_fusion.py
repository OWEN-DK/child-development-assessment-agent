"""
结果融合器 - 合并混合检索和 PageIndex 的结果
"""
import hashlib
import re
from typing import Any, Dict, List

from src.config import settings


class ResultFusion:
    """
    结果融合器
    
    融合策略:
    1. 简单查询：仅使用混合检索结果
    2. 复杂查询：融合两种结果，PageIndex 结果加分
    3. 默认查询：混合检索为主，PageIndex 补充
    """
    
    def __init__(self):
        self.score_boost = settings.fusion_score_boost_for_pageindex
        self.hybrid_supplement_limit = settings.fusion_hybrid_supplement_limit
        self.dedup_normalize = settings.fusion_dedup_normalize
    
    def fuse(
        self,
        hybrid_results: List[Dict[str, Any]],
        pageindex_results: List[Dict[str, Any]],
        query_type: str
    ) -> List[Dict[str, Any]]:
        """
        融合两种检索结果
        
        Args:
            hybrid_results: 混合检索结果
            pageindex_results: PageIndex 结果
            query_type: 查询类型 (simple/complex/default)
            
        Returns:
            List[Dict]: 融合后的结果
        """
        if query_type == "simple":
            # 简单查询：仅使用混合检索
            return hybrid_results
        
        elif query_type == "complex":
            # 复杂查询：融合两种结果
            return self._fuse_complex(hybrid_results, pageindex_results)
        
        else:  # default
            # 默认查询：混合检索为主，PageIndex 补充
            return self._fuse_default(hybrid_results, pageindex_results)
    
    def _fuse_complex(
        self, 
        hybrid_results: List[Dict], 
        pageindex_results: List[Dict]
    ) -> List[Dict]:
        """复杂查询的融合逻辑"""
        # 1. 去重（基于内容哈希）
        all_results = hybrid_results + pageindex_results
        deduped_results = self._deduplicate(all_results)
        
        # 2. PageIndex 结果加分
        for result in deduped_results:
            if result.get("_source") == "pageindex":
                result["score"] = result.get("score", 0.5) * self.score_boost
        
        # 3. 统一排序
        deduped_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return deduped_results
    
    def _fuse_default(
        self, 
        hybrid_results: List[Dict], 
        pageindex_results: List[Dict]
    ) -> List[Dict]:
        """默认查询的融合逻辑"""
        # 混合检索取前 N 个，PageIndex 补充 M 个
        limit = len(hybrid_results) or 10
        
        fused = hybrid_results[:limit]
        
        # 补充 PageIndex 结果（去重）
        existing_hashes = {
            self._content_hash(r.get("content", "")) 
            for r in fused
        }
        
        supplement_count = 0
        for result in pageindex_results:
            if supplement_count >= self.hybrid_supplement_limit:
                break
            
            content = result.get("content", "")
            if self.dedup_normalize:
                content = self._normalize_text(content)
            content_hash = self._content_hash(content)
            
            if content_hash not in existing_hashes:
                fused.append(result)
                existing_hashes.add(content_hash)
                supplement_count += 1
        
        return fused
    
    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        """基于内容哈希去重（增强：文本归一化）"""
        seen_hashes = set()
        deduped = []
        
        for result in results:
            content = result.get("content", "")
            # 文本归一化后再计算哈希
            if self.dedup_normalize:
                normalized_content = self._normalize_text(content)
                content_hash = self._content_hash(normalized_content)
            else:
                content_hash = self._content_hash(content)
            
            if content_hash not in seen_hashes:
                # 标记来源
                result["_source"] = (
                    "pageindex" if "reasoning_path" in result 
                    else "hybrid"
                )
                # 确保 score 字段存在（防 KeyError）
                if "score" not in result:
                    result["score"] = 0.5  # 默认分数
                
                deduped.append(result)
                seen_hashes.add(content_hash)
        
        return deduped
    
    def _normalize_text(self, text: str) -> str:
        """文本归一化（去标点、去空格、统一大小写）"""
        # 1. 转小写
        text = text.lower()
        
        # 2. 去除所有空白字符（空格、换行、制表符）
        text = re.sub(r'\s+', '', text)
        
        # 3. 去除标点符号（保留中英文）
        text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
        
        return text
    
    def _content_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
