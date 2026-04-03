import hashlib
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from src.config.settings import settings
from src.utils.logger import logger


@dataclass
class ABTestVariant:
    """A/B 测试变体"""
    name: str
    weight: float = 1.0
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ABTestConfig:
    """A/B 测试配置"""
    name: str
    description: str
    variants: List[ABTestVariant]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    traffic_ratio: float = 1.0
    enabled: bool = True


class ABTestFramework:
    """轻量级 A/B 测试框架"""
    
    def __init__(self):
        self.tests: Dict[str, ABTestConfig] = {}
        self.metrics: Dict[str, Dict[str, List[float]]] = {}
        self.storage_dir = settings.rag_storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.metrics_file = os.path.join(self.storage_dir, "ab_test_metrics.json")
        self._load_tests()
        self._load_metrics()
    
    def _load_tests(self):
        """从配置文件加载 A/B 测试"""
        ab_tests_config = settings.rag_config.get("ab_tests", [])
        for test_config in ab_tests_config:
            self.register_test(
                name=test_config["name"],
                description=test_config.get("description", ""),
                variants=test_config["variants"],
                traffic_ratio=test_config.get("traffic_ratio", 1.0)
            )
    
    def _load_metrics(self):
        """从本地文件加载指标数据"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    self.metrics = json.load(f)
                logger.info(f"Loaded A/B test metrics from {self.metrics_file}")
            except Exception as e:
                logger.warning(f"Failed to load A/B test metrics: {e}")
    
    def _save_metrics(self):
        """保存指标数据到本地文件"""
        try:
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save A/B test metrics: {e}")
    
    def register_test(
        self,
        name: str,
        description: str,
        variants: List[Dict[str, Any]],
        traffic_ratio: float = 1.0
    ):
        """注册 A/B 测试"""
        variant_objects = [
            ABTestVariant(
                name=v["name"],
                weight=v.get("weight", 1.0),
                config=v.get("config", {})
            )
            for v in variants
        ]
        
        self.tests[name] = ABTestConfig(
            name=name,
            description=description,
            variants=variant_objects,
            traffic_ratio=traffic_ratio,
            enabled=True
        )
        
        if name not in self.metrics:
            self.metrics[name] = {v.name: [] for v in variant_objects}
        
        logger.info(f"Registered A/B test: {name} with {len(variants)} variants")
    
    def get_variant(self, user_id: str, test_name: str) -> str:
        """根据用户 ID 分配测试变体"""
        if test_name not in self.tests:
            logger.warning(f"A/B test {test_name} not found, returning control")
            return "control"
        
        test_config = self.tests[test_name]
        
        if not test_config.enabled:
            return "control"
        
        if test_config.start_time and datetime.now() < test_config.start_time:
            logger.info(f"A/B test {test_name} has not started yet")
            return "control"
        
        if test_config.end_time and datetime.now() > test_config.end_time:
            logger.info(f"A/B test {test_name} has ended")
            return "control"
        
        hash_val = int(
            hashlib.md5(f"{user_id}_{test_name}".encode()).hexdigest(), 
            16
        )
        
        if hash_val % 100 >= test_config.traffic_ratio * 100:
            return "control"
        
        total_weight = sum(v.weight for v in test_config.variants)
        normalized_hash = hash_val % total_weight
        
        cumulative_weight = 0
        for variant in test_config.variants:
            cumulative_weight += variant.weight
            if normalized_hash < cumulative_weight:
                logger.debug(f"User {user_id} assigned to variant {variant.name}")
                return variant.name
        
        return test_config.variants[-1].name
    
    def get_variant_config(self, test_name: str, variant_name: str) -> Dict[str, Any]:
        """获取变体配置"""
        if test_name not in self.tests:
            return {}
        
        test_config = self.tests[test_name]
        for variant in test_config.variants:
            if variant.name == variant_name:
                return variant.config
        
        return {}
    
    def track_metric(
        self, 
        test_name: str, 
        variant: str, 
        metric_name: str, 
        value: float
    ):
        """记录测试指标"""
        if test_name not in self.metrics:
            self.metrics[test_name] = {}
        
        if variant not in self.metrics[test_name]:
            self.metrics[test_name][variant] = []
        
        self.metrics[test_name][variant].append(value)
        
        logger.debug(
            f"A/B Test: {test_name} variant={variant} metric={metric_name} value={value}"
        )
        
        self._save_metrics()
    
    def get_metric_stats(
        self, 
        test_name: str, 
        variant: str, 
        metric_name: str = None
    ) -> Dict[str, float]:
        """获取指标统计信息"""
        if test_name not in self.metrics:
            return {}
        
        if variant not in self.metrics[test_name]:
            return {}
        
        values = self.metrics[test_name][variant]
        if not values:
            return {}
        
        return {
            "count": len(values),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "sum": sum(values)
        }
    
    def get_test_results(self, test_name: str) -> Dict[str, Any]:
        """获取 A/B 测试结果"""
        if test_name not in self.tests:
            return {"error": "Test not found"}
        
        test_config = self.tests[test_name]
        results = {
            "test_name": test_name,
            "description": test_config.description,
            "variants": {}
        }
        
        for variant in test_config.variants:
            variant_data = self.metrics.get(test_name, {}).get(variant.name, [])
            results["variants"][variant.name] = {
                "sample_size": len(variant_data),
                "mean": sum(variant_data) / len(variant_data) if variant_data else 0,
                "config": variant.config
            }
        
        results["winner"] = self._calculate_winner(results["variants"])
        
        return results
    
    def _calculate_winner(self, variants: Dict[str, Any]) -> str:
        """计算获胜变体（基于均值）"""
        if not variants:
            return "control"
        
        best_variant = None
        best_mean = -float('inf')
        
        for name, data in variants.items():
            if data["mean"] > best_mean:
                best_mean = data["mean"]
                best_variant = name
        
        return best_variant or "control"
    
    def enable_test(self, test_name: str):
        """启用 A/B 测试"""
        if test_name in self.tests:
            self.tests[test_name].enabled = True
            logger.info(f"Enabled A/B test: {test_name}")
    
    def disable_test(self, test_name: str):
        """禁用 A/B 测试"""
        if test_name in self.tests:
            self.tests[test_name].enabled = False
            logger.info(f"Disabled A/B test: {test_name}")
    
    def clear_metrics(self, test_name: str = None):
        """清空指标数据"""
        if test_name:
            if test_name in self.metrics:
                self.metrics[test_name] = {}
                logger.info(f"Cleared metrics for A/B test: {test_name}")
        else:
            self.metrics = {}
            logger.info("Cleared all A/B test metrics")
        
        self._save_metrics()


ab_test_framework = ABTestFramework()
