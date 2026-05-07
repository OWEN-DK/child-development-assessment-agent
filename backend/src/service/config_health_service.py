"""
配置健康诊断服务

提供 LLM 健康度诊断和本地规则评分功能
"""

import hashlib
import json
from typing import Any

from src.utils.logger import logger


class ConfigHealthService:
    """配置健康诊断服务"""

    async def diagnose(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        使用 LLM 进行健康诊断

        1. 构建 Prompt
        2. 调用 LLM (qwen-turbo)
        3. 解析结果
        4. 返回诊断报告
        """
        try:
            from src.core.llm.factory import LLMFramework, LLMServiceFactoryCompat
            from src.core.prompt_impl.facade import prompt_manager

            # 从 PromptManager 获取诊断 Prompt
            prompt = await prompt_manager.get_prompt(
                "config_health_diagnosis",
                variables={
                    "config_json": json.dumps(config, indent=2, ensure_ascii=False),
                    "current_issues": self._detect_known_issues(config),
                    "usage_context": "儿童发展评估系统",
                },
            )

            # 调用 LLM（使用兼容层）
            from src.schemas import LLMMessage, LLMRequest

            llm = LLMServiceFactoryCompat.create(
                framework=LLMFramework.LANGCHAIN,
                model_name="qwen-turbo",
                scenario="config_health_diagnosis",
                temperature=0.7,
            )
            request = LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                scenario="config_health_diagnosis",
            )
            response = await llm.chat(request)

            # 解析结果（使用 json-repair 容错）
            import json_repair

            result = json_repair.loads(response.content)

            return {
                "score": result.get("score", 0),
                "score_basis": result.get("score_basis", ""),
                "suggestions": result.get("suggestions", []),
            }
        except Exception as e:
            logger.warning(f"LLM 健康诊断失败，降级到本地规则评分: {e}")
            # 降级到本地规则评分
            return self.local_score(config)

    def local_score(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        本地规则评分（降级备用）

        权重：
        - LLM 凭证: 30%
        - 核心场景模型: 25%
        - RAG 配置: 20%
        - 业务规则: 15%
        - 系统设置: 10%
        """
        score = 0
        suggestions = []

        # LLM 凭证 (30%)
        llm_providers = config.get("llm_providers", {})
        if len(llm_providers) > 0:
            score += 30
        else:
            suggestions.append(
                {
                    "priority": "high",
                    "issue": "未配置任何 LLM 提供商",
                    "suggestion": "至少配置一个 LLM 提供商（如 DashScope）",
                    "config_path": "llm_providers",
                    "current_value": "未配置",
                    "recommended_value": "配置 DashScope API Key",
                }
            )

        # 核心场景模型 (25%)
        scene_configs = config.get("llm_scene_configs", {})
        recommended_models = {"qwen-max", "qwen-plus"}
        has_recommended = any(
            sc.get("model") in recommended_models
            for sc in scene_configs.values()
            if isinstance(sc, dict)
        )
        if has_recommended:
            score += 25
        else:
            suggestions.append(
                {
                    "priority": "medium",
                    "issue": "未使用推荐模型",
                    "suggestion": "使用 qwen-plus 或 qwen-max 获得最佳效果",
                    "config_path": "llm_scene_configs",
                    "current_value": "未知模型",
                    "recommended_value": "qwen-plus",
                }
            )

        # RAG 配置 (20%)
        rag_retrieval = config.get("rag_retrieval", {})
        if rag_retrieval.get("strategy") and rag_retrieval.get("chunk_size"):
            score += 20
            # 检查检索阈值
            threshold = rag_retrieval.get("score_threshold", 0)
            if threshold < 0.25:
                suggestions.append(
                    {
                        "priority": "medium",
                        "issue": f"RAG 检索阈值偏低 ({threshold})",
                        "suggestion": "建议设置为 ≥0.25 以提高检索质量",
                        "config_path": "rag_retrieval.score_threshold",
                        "current_value": str(threshold),
                        "recommended_value": "0.25",
                    }
                )
        else:
            suggestions.append(
                {
                    "priority": "medium",
                    "issue": "RAG 检索配置不完整",
                    "suggestion": "配置检索策略和分块大小",
                    "config_path": "rag_retrieval",
                    "current_value": "不完整",
                    "recommended_value": "strategy: hybrid, chunk_size: 512",
                }
            )

        # 业务规则 (15%)
        rules = config.get("rules", {})
        if len(rules) > 0:
            score += 15
        else:
            suggestions.append(
                {
                    "priority": "low",
                    "issue": "未配置业务规则",
                    "suggestion": "配置校验规则、评分规则等",
                    "config_path": "rules",
                    "current_value": "未配置",
                    "recommended_value": "启用默认规则",
                }
            )

        # 系统设置 (10%)
        system = config.get("system", {})
        if system.get("logging") and system.get("paths"):
            score += 10
        else:
            suggestions.append(
                {
                    "priority": "low",
                    "issue": "系统设置不完整",
                    "suggestion": "配置日志和路径设置",
                    "config_path": "system",
                    "current_value": "不完整",
                    "recommended_value": "配置 logging 和 paths",
                }
            )

        return {
            "score": score,
            "score_basis": f"基于本地规则评分（{self._get_score_level(score)}）",
            "suggestions": suggestions,
        }

    def _detect_known_issues(self, config: dict[str, Any]) -> str:
        """检测已知问题"""
        issues = []

        # 检查 RAG 检索阈值
        rag_threshold = config.get("rag_retrieval", {}).get("score_threshold", 0)
        if rag_threshold < 0.25:
            issues.append(f"RAG 检索阈值偏低 ({rag_threshold})，建议 ≥0.25")

        # 检查未配置的提供商
        llm_providers = config.get("llm_providers", {})
        if not llm_providers:
            issues.append("未配置任何 LLM 提供商")

        # 检查空 API Key
        for provider, provider_config in llm_providers.items():
            if isinstance(provider_config, dict):
                api_key = provider_config.get("api_key", "")
                if not api_key or api_key == "sk-...":
                    issues.append(f"{provider} API Key 未配置")

        return "\n".join(issues) if issues else "无明显问题"

    def _get_score_level(self, score: int) -> str:
        """获取评分等级"""
        if score >= 90:
            return "优秀"
        elif score >= 75:
            return "良好"
        elif score >= 60:
            return "一般"
        elif score >= 40:
            return "需优化"
        else:
            return "较差"


def hash_config(config: dict[str, Any]) -> str:
    """计算配置哈希（用于缓存）"""
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()
