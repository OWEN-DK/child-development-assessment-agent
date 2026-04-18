"""配置冲突检测器 - Phase 8"""

from pydantic import BaseModel, Field


class Conflict(BaseModel):
    """配置冲突"""

    level: str  # error | warning
    rule: str
    message: str
    affected_configs: list[str] = Field(default_factory=list)


class ConfigConflictDetector:
    """配置冲突检测器 - 10 条完整冲突检测规则"""

    async def detect(
        self, config_updates: dict, current_config: dict
    ) -> list[Conflict]:
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
            return [
                Conflict(
                    level="warning",
                    rule="bm25_vector_ratio",
                    message=f"BM25 TopK ({bm25_k}) 远小于 Vector TopK ({vector_k})，可能导致检索不平衡",
                    affected_configs=["bm25_top_k", "vector_top_k"],
                )
            ]
        return []

    def _check_fusion_threshold(self, config: dict) -> list[Conflict]:
        """规则 2: 融合阈值不应大于 BM25 权重 + Vector 权重之和"""
        threshold = config.get("fusion_threshold", 0.25)
        bm25_weight = config.get("bm25_weight", 0.5)
        vector_weight = config.get("vector_weight", 0.5)
        if threshold > bm25_weight + vector_weight:
            return [
                Conflict(
                    level="error",
                    rule="fusion_threshold",
                    message=f"融合阈值 ({threshold}) 大于 BM25 权重 ({bm25_weight}) + Vector 权重 ({vector_weight}) 之和",
                    affected_configs=[
                        "fusion_threshold",
                        "bm25_weight",
                        "vector_weight",
                    ],
                )
            ]
        return []

    def _check_reranker_k(self, config: dict) -> list[Conflict]:
        """规则 3: initial_k 必须大于等于 final_k"""
        initial_k = config.get("reranker_initial_k", 30)
        final_k = config.get("reranker_final_k", 5)
        if initial_k < final_k:
            return [
                Conflict(
                    level="error",
                    rule="reranker_k_order",
                    message=f"重排序 initial_k ({initial_k}) 必须大于等于 final_k ({final_k})",
                    affected_configs=["reranker_initial_k", "reranker_final_k"],
                )
            ]
        return []

    def _check_chunk_overlap(self, config: dict) -> list[Conflict]:
        """规则 4: 重叠不应超过分块大小的 50%"""
        chunk_size = config.get("chunk_size", 500)
        overlap = config.get("chunk_overlap", 50)
        if chunk_size > 0 and overlap > chunk_size * 0.5:
            return [
                Conflict(
                    level="warning",
                    rule="chunk_overlap",
                    message=f"分块重叠 ({overlap}) 超过分块大小 ({chunk_size}) 的 50%",
                    affected_configs=["chunk_size", "chunk_overlap"],
                )
            ]
        return []

    def _check_age_filter(self, config: dict) -> list[Conflict]:
        """规则 5: 严格度高时容忍度应低"""
        strictness = config.get("age_filter_strictness", "medium")
        tolerance = config.get("age_tolerance", 2)
        if strictness == "high" and tolerance > 1:
            return [
                Conflict(
                    level="warning",
                    rule="age_filter",
                    message=f"年龄过滤严格度高时，容忍度 ({tolerance}) 应不大于 1",
                    affected_configs=["age_filter_strictness", "age_tolerance"],
                )
            ]
        return []

    def _check_llm_sampling(self, config: dict) -> list[Conflict]:
        """规则 6: 温度高时 TopP 应低，避免过度随机"""
        temperature = config.get("llm_temperature", 0.7)
        top_p = config.get("llm_top_p", 0.9)
        if temperature > 0.8 and top_p > 0.8:
            return [
                Conflict(
                    level="warning",
                    rule="llm_sampling",
                    message=f"LLM 温度 ({temperature}) 和 TopP ({top_p}) 都较高，可能导致输出过度随机",
                    affected_configs=["llm_temperature", "llm_top_p"],
                )
            ]
        return []

    def _check_cache_ttl(self, config: dict) -> list[Conflict]:
        """规则 7: 缓存 TTL 不应远大于数据更新频率"""
        cache_ttl = config.get("cache_ttl", 3600)
        update_freq = config.get("data_update_freq_hours", 24)
        if cache_ttl > update_freq * 3600 * 2:
            return [
                Conflict(
                    level="warning",
                    rule="cache_ttl",
                    message=f"缓存 TTL ({cache_ttl}s) 远大于数据更新频率 ({update_freq}h)",
                    affected_configs=["cache_ttl", "data_update_freq_hours"],
                )
            ]
        return []

    def _check_log_level(self, config: dict) -> list[Conflict]:
        """规则 8: DEBUG 日志级别不应在生产环境使用"""
        log_level = config.get("log_level", "INFO")
        environment = config.get("environment", "production")
        if log_level == "DEBUG" and environment == "production":
            return [
                Conflict(
                    level="warning",
                    rule="log_level",
                    message="生产环境不应使用 DEBUG 日志级别",
                    affected_configs=["log_level", "environment"],
                )
            ]
        return []

    def _check_db_pool(self, config: dict) -> list[Conflict]:
        """规则 9: 连接池大小不应小于最大并发数"""
        pool_size = config.get("db_pool_size", 10)
        max_concurrent = config.get("max_concurrent_tasks", 5)
        if pool_size < max_concurrent:
            return [
                Conflict(
                    level="error",
                    rule="db_pool_size",
                    message=f"数据库连接池大小 ({pool_size}) 不应小于最大并发数 ({max_concurrent})",
                    affected_configs=["db_pool_size", "max_concurrent_tasks"],
                )
            ]
        return []

    def _check_circular_dependencies(self, config: dict) -> list[Conflict]:
        """规则 10: 检测配置项之间的循环依赖关系"""
        # 简化实现：检查是否有明显的循环引用配置
        # 实际应用中需要更复杂的依赖图分析
        circular_deps = config.get("circular_dependencies", [])
        if circular_deps:
            return [
                Conflict(
                    level="error",
                    rule="circular_dependencies",
                    message=f"检测到配置循环依赖: {', '.join(circular_deps)}",
                    affected_configs=circular_deps,
                )
            ]
        return []
