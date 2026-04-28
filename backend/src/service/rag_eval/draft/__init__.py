"""草稿引擎模块

从源文档自动生成测试用例草稿，经过忠实度验证和语义去重后保存。
协调 BookMetadataAnalyzer、DraftGenerator、FaithfulnessChecker、DraftDeduplicator。
"""

from src.service.rag_eval.draft.book_analyzer import BookMetadataAnalyzer
from src.service.rag_eval.draft.deduplicator import DraftDeduplicator
from src.service.rag_eval.draft.facade import DraftEngineFacade
from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
from src.service.rag_eval.draft.generator import DraftGenerator

__all__ = [
    "BookMetadataAnalyzer",
    "DraftGenerator",
    "FaithfulnessChecker",
    "DraftDeduplicator",
    "DraftEngineFacade",
]
