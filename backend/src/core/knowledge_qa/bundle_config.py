"""KnowledgeBundle 模式灰度开关配置

放置位置: backend/src/core/knowledge_qa/bundle_config.py
职责: Feature Flag 控制 Bundle 模式的启停与流量比例，不依赖数据库配置系统。
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeQABundleConfig:
    """Bundle 模式灰度开关。

    全局开关 closed 时走旧版分散搜索逻辑。
    细粒度开关可单独控制 Phase 1/2/3。
    """

    # ── 全局开关 ──
    bundle_mode_enabled: bool = True   # 总开关——关闭时全部走旧版

    # ── 细粒度开关 ──
    bundle_phase1_enabled: bool = True   # Phase 1: 统一检索 (Neo4j + Chroma + LazyGraphRAG)
    bundle_phase2_enabled: bool = True   # Phase 2: Bundle 消费 (Section 节点零搜索)
    bundle_phase3_enabled: bool = True   # Phase 3: 四层引用校验

    # ── 流量比例 (0.0–1.0) ──
    bundle_traffic_ratio: float = 1.0  # 默认全量，可以通过参数调低

    # ── 手动覆盖 ──
    bundle_force_enabled: bool = False  # URL param ?bundle=1 强制开启


# 全局单例
_bundle_config: KnowledgeQABundleConfig | None = None


def get_bundle_config() -> KnowledgeQABundleConfig:
    """获取 Bundle 配置单例。"""
    global _bundle_config
    if _bundle_config is None:
        _bundle_config = KnowledgeQABundleConfig()
    return _bundle_config


def set_bundle_config(config: KnowledgeQABundleConfig) -> None:
    """覆盖全局配置（测试用）。"""
    global _bundle_config
    _bundle_config = config


def _use_bundle() -> bool:
    """判定当前请求是否使用 Bundle 模式。

    判定逻辑（按优先级）:
    1. force_enabled → 强制使用
    2. bundle_mode_enabled=False → 不使用
    3. phase1_enabled=False → 不使用
    4. 流量比例随机判定
    """
    config = get_bundle_config()

    if config.bundle_force_enabled:
        return True

    if not config.bundle_mode_enabled:
        return False

    if not config.bundle_phase1_enabled:
        return False

    if config.bundle_traffic_ratio >= 1.0:
        return True

    if config.bundle_traffic_ratio <= 0.0:
        return False

    return random.random() < config.bundle_traffic_ratio


def use_bundle_phase2() -> bool:
    """Phase 2 (Bundle 消费) 是否启用。"""
    config = get_bundle_config()
    return _use_bundle() and config.bundle_phase2_enabled


def use_bundle_phase3() -> bool:
    """Phase 3 (四层引用校验) 是否启用。"""
    config = get_bundle_config()
    return _use_bundle() and config.bundle_phase3_enabled
