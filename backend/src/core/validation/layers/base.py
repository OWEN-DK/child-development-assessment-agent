from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_eval.test_run import RagEvalTestRun

SessionFactory = Callable[[], AsyncSession]


class Layer1RuleEngine:
    def __init__(self, session_factory: SessionFactory, test_run: RagEvalTestRun):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        return {"data": {}}


class Layer2HistoryComparison:
    def __init__(self, session_factory: SessionFactory, test_run: RagEvalTestRun):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        return {"data": {}}


class Layer3LLMDiagnosis:
    def __init__(self, session_factory: SessionFactory, test_run: RagEvalTestRun):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        return {"data": {}}


class Layer4aGoldenCoverage:
    def __init__(self, session_factory: SessionFactory, test_run: RagEvalTestRun):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        return {"data": {}}


class Layer4bChunkQuality:
    def __init__(self, session_factory: SessionFactory, test_run: RagEvalTestRun):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        return {"data": {}}


class Layer4cDocumentStaleness:
    def __init__(self, session_factory: SessionFactory, test_run: RagEvalTestRun):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        return {"data": {}}


class Layer5aEmbeddingQuality:
    def __init__(self, session_factory: SessionFactory, test_run: RagEvalTestRun):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        return {"data": {}}


class Layer5bIntentAccuracy:
    def __init__(self, session_factory: SessionFactory, test_run: RagEvalTestRun):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        return {"data": {}}


class Layer5cErrorPatterns:
    def __init__(self, session_factory: SessionFactory, test_run: RagEvalTestRun):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        return {"data": {}}
