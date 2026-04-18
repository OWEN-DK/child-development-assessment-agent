import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from src.config import settings
from src.utils.logger import logger


class ContentAuditService:
    """内容审核服务，在导入和检索环节进行内容安全检测"""
    
    def __init__(self):
        self.config_file = Path(__file__).parent.parent / "data" / "sensitive_words.json"
        self.config = self._load_config()
        self.sensitive_words: Set[str] = self._parse_sensitive_words()
        self.categories = self.config.get("categories", {})
        self.enable_external_audit = settings.rag_config.get("content_audit", {}).get("enable_external", False)
        self.external_audit_api_url = settings.rag_config.get("content_audit", {}).get("external_api_url", "")
        self.external_audit_api_key = settings.rag_config.get("content_audit", {}).get("external_api_key", "")
    
    def _load_config(self) -> Dict[str, Any]:
        """从 JSON 配置文件加载"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"Loaded sensitive words config from {self.config_file}")
                return config
            else:
                logger.warning(f"Config file {self.config_file} not found, using defaults")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load sensitive words config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """默认配置（兜底）"""
        return {
            "version": "1.0.0",
            "categories": {}
        }
    
    def _parse_sensitive_words(self) -> Set[str]:
        """解析敏感词库"""
        words = set()
        for category_data in self.config.get("categories", {}).values():
            words.update(category_data.get("words", []))
        return words
    
    async def audit_content(self, content: str, stage: str = "import") -> Tuple[bool, str]:
        """审核内容，返回是否通过和原因"""
        try:
            if not content:
                return False, "内容为空"
            
            passed, reason = await self._local_audit(content)
            if not passed:
                return False, reason
            
            if self.enable_external_audit and stage == "import":
                passed, reason = await self._external_audit(content)
                if not passed:
                    return False, reason
            
            return True, "内容审核通过"
        except Exception as e:
            logger.error(f"Content audit failed: {e}")
            return False, f"内容审核异常：{str(e)}"
    
    async def _local_audit(self, content: str) -> Tuple[bool, str]:
        """本地敏感词检测"""
        content_lower = content.lower()
        
        for word in self.sensitive_words:
            if word.lower() in content_lower:
                category = self._get_word_category(word)
                return False, f"包含{category}敏感词：{word}"
        
        risk_patterns = [
            r"(暴力 | 恐怖 | 血腥 | 色情)",
            r"(自杀 | 自残 | 虐待 | 欺凌)",
            r"(毒品 | 赌博 | 武器)",
            r"(成人内容 | 限制级 | 不适宜儿童)"
        ]
        
        for pattern in risk_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False, f"检测到风险内容：{pattern}"
        
        return True, "本地审核通过"
    
    def _get_word_category(self, word: str) -> str:
        """获取敏感词所属分类"""
        for category_name, category_data in self.categories.items():
            if word in category_data.get("words", []):
                return category_data.get("name", "未知")
        return "其他"
    
    async def _external_audit(self, content: str) -> Tuple[bool, str]:
        """第三方 API 审核"""
        if not self.enable_external_audit:
            return True, "外部审核未启用"
        
        try:
            import aiohttp
            
            headers = {
                "Authorization": f"Bearer {self.external_audit_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "content": content,
                "scene": "child_content"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.external_audit_api_url,
                    json=payload,
                    headers=headers,
                    timeout=5
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("pass", True):
                            return True, "外部审核通过"
                        else:
                            return False, f"外部审核未通过：{result.get('reason', '未知原因')}"
                    else:
                        logger.warning(f"External audit API returned status {response.status}")
                        return True, "外部审核 API 异常，降级为本地审核"
        except Exception as e:
            logger.warning(f"External content audit failed: {e}")
            return True, "外部审核失败，降级为本地审核"
    
    async def audit_batch(self, contents: List[str], stage: str = "import") -> List[Tuple[bool, str]]:
        """批量审核内容"""
        results = []
        for content in contents:
            result = await self.audit_content(content, stage)
            results.append(result)
        return results
    
    def add_sensitive_word(self, word: str, category: str = "other"):
        """添加敏感词到指定分类"""
        self.sensitive_words.add(word)
        if category in self.categories:
            if word not in self.categories[category]["words"]:
                self.categories[category]["words"].append(word)
        logger.info(f"Added sensitive word '{word}' to category '{category}'")
    
    def remove_sensitive_word(self, word: str):
        """移除敏感词"""
        self.sensitive_words.discard(word)
        for category_data in self.categories.values():
            if word in category_data.get("words", []):
                category_data["words"].remove(word)
        logger.info(f"Removed sensitive word: {word}")
    
    def get_sensitive_words_count(self) -> int:
        """获取敏感词数量"""
        return len(self.sensitive_words)
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息"""
        return {
            "config_file": str(self.config_file),
            "version": self.config.get("version", "unknown"),
            "last_updated": self.config.get("last_updated", "unknown"),
            "total_words": len(self.sensitive_words),
            "categories": list(self.categories.keys())
        }


content_audit_service = ContentAuditService()
