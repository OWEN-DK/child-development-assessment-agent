"""RAG 监控服务 - 采集和上报 RAG 系统运行指标"""
import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from src.config import settings
from src.utils.logger import logger

@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)

class MonitoringService:
    """RAG 监控服务"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.metrics: List[MetricPoint] = []
        self.enabled = settings.rag_monitoring_enabled
        self._initialized = True
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """记录指标"""
        if not self.enabled:
            return
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {}
        )
        self.metrics.append(point)
        logger.debug(f"Metric recorded: {name}={value} {tags}")
    
    def get_metrics(self, name: str = None, since: float = None) -> List[MetricPoint]:
        """获取指标"""
        result = self.metrics
        if name:
            result = [m for m in result if m.name == name]
        if since:
            result = [m for m in result if m.timestamp >= since]
        return result
    
    def get_latest(self, name: str) -> Optional[MetricPoint]:
        """获取最新指标值"""
        metrics = [m for m in self.metrics if m.name == name]
        return max(metrics, key=lambda m: m.timestamp) if metrics else None

# 单例实例
monitoring_service = MonitoringService()
