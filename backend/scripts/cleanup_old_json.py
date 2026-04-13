# backend/scripts/cleanup_old_json.py
"""
清理旧 JSON 文件（MySQL 迁移后执行）

⚠️ 重要：执行前请确认所有数据已成功迁移到 MySQL
"""

import os
import shutil
import sys
from pathlib import Path
from src.utils.logger import logger

# 可安全删除的旧文件/目录
FILES_TO_DELETE = [
    "app_data/data/configs/",  # 配置版本和审计日志
    "app_data/storage/test_cases.json",  # 测试用例
    "app_data/storage/test_sets/",  # 测试集
    "app_data/storage/test_case_drafts/",  # 测试用例草稿
    "app_data/storage/test_runs/",  # 测试运行结果
    "app_data/storage/source_documents/",  # 源文档元数据
    "app_data/storage/document_store.json",  # 文档记录
    "app_data/storage/ab_test_metrics.json",
    "app_data/storage/memory_store.json",
    "app_data/storage/prompt_versions/",  # 提示词版本
    "app_data/cache/",  # 磁盘缓存
]

# 保留的文件
FILES_TO_KEEP = [
    "backend/src/config/rules/rules.json",  # 业务规则
    "backend/src/data/",  # 静态数据
]


def cleanup(dry_run: bool = True):
    """执行清理（默认 dry_run 模式）"""
    base_dir = Path(__file__).parent.parent.parent

    for rel_path in FILES_TO_DELETE:
        full_path = base_dir / rel_path

        if not full_path.exists():
            logger.info(f"[跳过] 不存在: {rel_path}")
            continue

        if dry_run:
            if full_path.is_dir():
                size = sum(
                    f.stat().st_size for f in full_path.rglob("*") if f.is_file()
                )
            else:
                size = full_path.stat().st_size
            logger.info(f"[预览] 将删除: {rel_path} ({size / 1024:.1f} KB)")
        else:
            if full_path.is_dir():
                shutil.rmtree(full_path)
            else:
                full_path.unlink()
            logger.info(f"[已删除] {rel_path}")

    if dry_run:
        logger.info("\n=== 预览模式，未实际删除 ===")
        logger.info(
            "确认无误后，运行: uv run python scripts/cleanup_old_json.py --execute"
        )
    else:
        logger.info("\n=== 清理完成 ===")


if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    cleanup(dry_run=dry_run)
