import re
import json
from typing import Tuple, List, Dict, Any
from pathlib import Path
from src.config import settings
from src.utils.logger import logger


class ChildDevelopmentRuleEngine:
    """儿童发展领域规则引擎，基于《3-6 岁儿童学习与发展指南》"""
    
    def __init__(self):
        self.config_file = Path(__file__).parent.parent / "data" / "child_development_milestones.json"
        self.config = self._load_config()
        self.milestones = self._parse_milestones()
        self.difficulty_rules = self.config.get("difficulty_rules", {})
        self.age_patterns = self.config.get("age_detection_patterns", [])
        self.age_appropriateness_cache: Dict[str, float] = {}
    
    def _load_config(self) -> Dict[str, Any]:
        """从 JSON 配置文件加载"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"Loaded child development config from {self.config_file}")
                return config
            else:
                logger.warning(f"Config file {self.config_file} not found, using defaults")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load child development config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """默认配置（兜底）"""
        return {
            "milestones": {},
            "difficulty_rules": {},
            "age_detection_patterns": []
        }
    
    def _parse_milestones(self) -> Dict[int, Dict[str, List[str]]]:
        """解析里程碑配置"""
        milestones = {}
        for age_str, age_data in self.config.get("milestones", {}).items():
            age = int(age_str)
            domains = {}
            for domain_name, domain_data in age_data.get("domains", {}).items():
                domains[domain_name] = domain_data.get("indicators", [])
            milestones[age] = domains
        return milestones
    
    def calculate_age_appropriateness(self, content: str, age: int) -> float:
        """计算内容的年龄适配度，0-1 分"""
        cache_key = f"{hash(content)}_{age}"
        if cache_key in self.age_appropriateness_cache:
            return self.age_appropriateness_cache[cache_key]
        
        try:
            content_age_min, content_age_max = self._extract_age_range(content)
            
            if content_age_min <= age <= content_age_max:
                score = 1.0
            elif abs(age - content_age_min) <= 1 or abs(age - content_age_max) <= 1:
                score = 0.7
            else:
                score = 0.3
            
            self.age_appropriateness_cache[cache_key] = score
            return score
        except Exception as e:
            logger.warning(f"Failed to calculate age appropriateness: {e}")
            return 0.5
    
    def _extract_age_range(self, content: str) -> Tuple[int, int]:
        """从内容中提取年龄范围"""
        for pattern in self.age_patterns:
            match = re.search(pattern, content)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return int(groups[0]), int(groups[1])
                else:
                    age = int(groups[0])
                    return age, age
        
        milestone_keywords = {}
        for age_str, age_data in self.config.get("milestones", {}).items():
            age = int(age_str)
            keywords = []
            for domain_data in age_data.get("domains", {}).values():
                keywords.extend(domain_data.get("indicators", [])[:2])
            milestone_keywords[age] = keywords
        
        for age in range(6, 2, -1):
            for keyword in milestone_keywords.get(age, []):
                if keyword in content:
                    return age, age
        
        return 3, 6
    
    def filter_unsuitable_content(self, content: str, age: int) -> Tuple[bool, str]:
        """过滤不适宜特定年龄的内容"""
        unsuitable_patterns = [
            r"(危险 | 不安全 | 禁止 | 不适合 | 请勿) 给.*(儿童 | 宝宝)",
            r"(吞咽 | 窒息 | 受伤 | 中毒)",
            r"(暴力 | 恐怖 | 血腥 | 色情)",
            r"(成人 | 限制级 | 不适宜儿童)"
        ]
        
        for pattern in unsuitable_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False, "内容包含不适宜儿童的风险提示或不适宜内容"
        
        appropriateness = self.calculate_age_appropriateness(content, age)
        if appropriateness < 0.5:
            return False, f"内容不适用于{age}岁儿童（适配度：{appropriateness:.2f}）"
        
        return True, "内容适合"
    
    def get_age_appropriate_content(self, content: str, age: int) -> Dict[str, Any]:
        """获取适合特定年龄的内容建议"""
        appropriateness = self.calculate_age_appropriateness(content, age)
        milestones = self.milestones.get(age, {})
        
        return {
            "age": age,
            "appropriateness_score": appropriateness,
            "developmental_milestones": milestones,
            "recommendations": self._generate_recommendations(content, age, milestones)
        }
    
    def _generate_recommendations(self, content: str, age: int, milestones: Dict) -> List[str]:
        """基于内容生成年龄适配建议"""
        recommendations = []
        
        if age == 3:
            recommendations.append("建议使用简单语言和具体示例")
            recommendations.append("配合图片和实物演示")
        elif age == 4:
            recommendations.append("可以引入简单故事和情境")
            recommendations.append("鼓励提问和探索")
        elif age == 5:
            recommendations.append("可以增加互动和讨论环节")
            recommendations.append("引导逻辑思考")
        elif age == 6:
            recommendations.append("可以引入抽象概念")
            recommendations.append("鼓励独立解决问题")
        
        return recommendations
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息"""
        return {
            "config_file": str(self.config_file),
            "version": self.config.get("version", "unknown"),
            "source": self.config.get("source", "unknown"),
            "last_updated": self.config.get("last_updated", "unknown"),
            "age_count": len(self.milestones)
        }


child_development_engine = ChildDevelopmentRuleEngine()
