"""Phase 4.4: 配置健康诊断服务测试

测试 ConfigHealthService 类的本地规则评分和已知问题检测
"""

import pytest
from src.service.config_health_service import ConfigHealthService, hash_config


class TestConfigHealthService:
    """测试配置健康诊断服务"""

    def setup_method(self):
        """每个测试方法前创建服务实例"""
        self.service = ConfigHealthService()

    def test_local_score_perfect_config(self):
        """测试完美配置的本地评分"""
        config = {
            "llm_providers": {"dashscope": {"api_key": "sk-test"}},
            "llm_scene_configs": {
                "assessment": {"model": "qwen-plus", "provider": "dashscope"}
            },
            "rag_retrieval": {
                "strategy": "hybrid",
                "chunk_size": 512,
                "score_threshold": 0.3,
            },
            "rules": {"validation": {}, "scoring": {}},
            "system": {"logging": {"level": "INFO"}, "paths": {"data": "/data"}},
        }

        result = self.service.local_score(config)

        assert result["score"] == 100
        # 阈值 >= 0.25 时不应该有建议
        assert len(result["suggestions"]) == 0

    def test_local_score_empty_config(self):
        """测试空配置的本地评分"""
        config = {}

        result = self.service.local_score(config)

        assert result["score"] == 0
        assert len(result["suggestions"]) == 5  # 所有配置都缺失

    def test_local_score_llm_providers_only(self):
        """测试仅配置 LLM 提供商的评分"""
        config = {
            "llm_providers": {"dashscope": {"api_key": "sk-test"}},
        }

        result = self.service.local_score(config)

        assert result["score"] == 30
        assert any("LLM 提供商" in s["issue"] for s in result["suggestions"]) is False
        assert any("未使用推荐模型" in s["issue"] for s in result["suggestions"])

    def test_local_score_rag_threshold_too_low(self):
        """测试 RAG 检索阈值过低的检测"""
        config = {
            "llm_providers": {"dashscope": {"api_key": "sk-test"}},
            "llm_scene_configs": {
                "assessment": {"model": "qwen-plus", "provider": "dashscope"}
            },
            "rag_retrieval": {
                "strategy": "hybrid",
                "chunk_size": 512,
                "score_threshold": 0.1,
            },
            "rules": {"validation": {}},
            "system": {"logging": {"level": "INFO"}, "paths": {"data": "/data"}},
        }

        result = self.service.local_score(config)

        assert result["score"] == 100  # 仍然满分，因为阈值低只是建议
        assert any("阈值偏低" in s["issue"] for s in result["suggestions"])

    def test_detect_known_issues_empty_config(self):
        """测试检测已知问题 - 空配置"""
        config = {}

        issues = self.service._detect_known_issues(config)

        assert "未配置任何 LLM 提供商" in issues

    def test_detect_known_issues_low_rag_threshold(self):
        """测试检测已知问题 - RAG 阈值过低"""
        config = {
            "rag_retrieval": {"score_threshold": 0.1},
            "llm_providers": {"dashscope": {"api_key": "sk-test"}},
        }

        issues = self.service._detect_known_issues(config)

        assert "RAG 检索阈值偏低" in issues

    def test_detect_known_issues_empty_api_key(self):
        """测试检测已知问题 - 空 API Key"""
        config = {
            "llm_providers": {
                "dashscope": {"api_key": ""},
                "openai": {"api_key": "sk-..."},
            }
        }

        issues = self.service._detect_known_issues(config)

        assert "dashscope API Key 未配置" in issues
        assert "openai API Key 未配置" in issues

    def test_detect_known_issues_no_issues(self):
        """测试检测已知问题 - 无问题"""
        config = {
            "llm_providers": {"dashscope": {"api_key": "sk-valid-key"}},
            "rag_retrieval": {"score_threshold": 0.3},
        }

        issues = self.service._detect_known_issues(config)

        assert "无明显问题" in issues

    def test_get_score_level(self):
        """测试评分等级"""
        assert self.service._get_score_level(95) == "优秀"
        assert self.service._get_score_level(80) == "良好"
        assert self.service._get_score_level(65) == "一般"
        assert self.service._get_score_level(50) == "需优化"
        assert self.service._get_score_level(20) == "较差"

    def test_hash_config_consistency(self):
        """测试配置哈希一致性"""
        config = {"llm_providers": {"dashscope": {"api_key": "sk-test"}}}

        hash1 = hash_config(config)
        hash2 = hash_config(config)

        assert hash1 == hash2

    def test_hash_config_order_independent(self):
        """测试配置哈希与键顺序无关"""
        config1 = {"a": 1, "b": 2}
        config2 = {"b": 2, "a": 1}

        hash1 = hash_config(config1)
        hash2 = hash_config(config2)

        assert hash1 == hash2

    def test_hash_config_different_values(self):
        """测试不同值的配置哈希不同"""
        config1 = {"llm_providers": {"dashscope": {"api_key": "sk-test1"}}}
        config2 = {"llm_providers": {"dashscope": {"api_key": "sk-test2"}}}

        hash1 = hash_config(config1)
        hash2 = hash_config(config2)

        assert hash1 != hash2
