# backend/scripts/migrate_json_to_mysql.py
import json
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.models.test_case import TestCase
from src.models.test_set import TestSet
from src.models.test_case_draft import TestCaseDraft
from src.models.source_document import SourceDocument
from src.models.config import ConfigVersion, ConfigAuditLog
from src.models.prompt import PromptVersion, PromptABTest


async def migrate_all_data():
    """迁移所有JSON数据到MySQL"""
    base_dir = Path(__file__).parent.parent.parent
    engine = create_async_engine(settings.database.dsn)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. 迁移测试用例
        test_cases_path = base_dir / "app_data" / "storage" / "test_cases.json"
        if test_cases_path.exists():
            with open(test_cases_path, "r", encoding="utf-8") as f:
                test_cases_data = json.load(f)

            test_cases = (
                test_cases_data.get("test_cases", {}).values()
                if isinstance(test_cases_data, dict)
                else test_cases_data
            )

            for tc_data in test_cases:
                tc = TestCase(**tc_data)
                session.add(tc)

            print(f"准备迁移 {len(test_cases)} 个测试用例")

        # 2. 迁移测试集
        test_sets_path = base_dir / "app_data" / "storage" / "test_sets"
        if test_sets_path.exists() and test_sets_path.is_dir():
            for ts_file in test_sets_path.glob("*.json"):
                with open(ts_file, "r", encoding="utf-8") as f:
                    ts_data = json.load(f)
                ts = TestSet(**ts_data)
                session.add(ts)
            print(f"准备迁移测试集")

        # 3. 迁移测试用例草稿
        drafts_path = base_dir / "app_data" / "storage" / "test_case_drafts"
        if drafts_path.exists() and drafts_path.is_dir():
            for draft_file in drafts_path.glob("*.json"):
                with open(draft_file, "r", encoding="utf-8") as f:
                    draft_data = json.load(f)
                draft = TestCaseDraft(**draft_data)
                session.add(draft)
            print(f"准备迁移测试用例草稿")

        # 4. 迁移源文档
        docs_path = base_dir / "app_data" / "storage" / "source_documents"
        if docs_path.exists() and docs_path.is_dir():
            for doc_file in docs_path.glob("*.json"):
                with open(doc_file, "r", encoding="utf-8") as f:
                    doc_data = json.load(f)
                doc = SourceDocument(**doc_data)
                session.add(doc)
            print(f"准备迁移源文档")

        # 5. 迁移配置版本
        configs_path = base_dir / "app_data" / "data" / "configs"
        if configs_path.exists() and configs_path.is_dir():
            for config_file in configs_path.glob("version_*.json"):
                with open(config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                config = ConfigVersion(**config_data)
                session.add(config)
            print(f"准备迁移配置版本")

        # 6. 迁移提示词版本
        prompts_path = base_dir / "app_data" / "storage" / "prompt_versions"
        if prompts_path.exists() and prompts_path.is_dir():
            for prompt_file in prompts_path.glob("*.json"):
                with open(prompt_file, "r", encoding="utf-8") as f:
                    prompt_data = json.load(f)
                prompt = PromptVersion(**prompt_data)
                session.add(prompt)
            print(f"准备迁移提示词版本")

        await session.commit()

    print("所有数据迁移完成")


if __name__ == "__main__":
    asyncio.run(migrate_all_data())
