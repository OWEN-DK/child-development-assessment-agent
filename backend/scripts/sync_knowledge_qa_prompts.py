"""一次性脚本：将 templates.py 中的 Knowledge QA Prompt 同步到 MySQL。

用法：cd backend && uv run python scripts/sync_knowledge_qa_prompts.py
原理：调用 PromptStorage.create_prompt_version，content hash 不变时跳过（幂等）。
"""

import asyncio
import sys

from src.core.knowledge_qa.prompts.templates import PROMPT_TEMPLATES
from src.core.prompt_impl.facade import prompt_manager


async def main():
    total = len(PROMPT_TEMPLATES) * 2  # system + user per key
    synced = 0
    skipped = 0
    failed = 0

    for prompt_key, templates in PROMPT_TEMPLATES.items():
        for suffix, content in [
            ("system", templates["system"]),
            ("user", templates["user_template"]),
        ]:
            db_key = f"knowledge_qa_{prompt_key}_{suffix}"
            try:
                version_label = await prompt_manager.create_prompt_version(
                    prompt_key=db_key,
                    content=content,
                    description=f"从 templates.py 自动同步 ({prompt_key}.{suffix})",
                    created_by="sync_script",
                )
                if version_label.startswith("v"):
                    print(f"  SYNC  {db_key} → {version_label} ({len(content)} 字符)")
                    synced += 1
                else:
                    print(f"  SKIP  {db_key} (内容未变)")
                    skipped += 1
            except Exception as e:
                print(f"  FAIL  {db_key}: {e}")
                failed += 1

    print(f"\n完成: {synced} 条已同步, {skipped} 条跳过, {failed} 条失败 (共 {total} 条)")


if __name__ == "__main__":
    asyncio.run(main())
