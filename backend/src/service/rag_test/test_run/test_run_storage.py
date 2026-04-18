import json
import os
from typing import List, Optional

from src.utils.logger import logger


class TestRunStorage:
    """测试运行存储器，负责测试运行的文件持久化"""

    def __init__(self):
        self.test_runs_dir = f"{__import__('src.config', fromlist=['settings']).settings.rag_storage_dir}/test_runs"
        os.makedirs(self.test_runs_dir, exist_ok=True)

    def save_test_run(self, test_run) -> None:
        """
        保存测试运行到文件
        
        Args:
            test_run: 测试运行对象
        """
        try:
            file_path = os.path.join(self.test_runs_dir, f"{test_run.id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(test_run.model_dump_json(indent=2))
            logger.info(f"Test run saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save test run: {e}")

    def list_test_runs(self) -> List:
        """
        列出所有测试运行
        
        Returns:
            测试运行列表，按创建时间倒序
        """
        from src.models.test_case import TestRun

        test_runs = []
        try:
            for filename in os.listdir(self.test_runs_dir):
                if filename.endswith(".json"):
                    file_path = os.path.join(self.test_runs_dir, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        test_runs.append(TestRun(**data))
            test_runs.sort(key=lambda x: x.created_at, reverse=True)
        except Exception as e:
            logger.error(f"Failed to list test runs: {e}")
        return test_runs

    def get_test_run(self, run_id: str) -> Optional:
        """
        获取指定测试运行
        
        Args:
            run_id: 测试运行ID
            
        Returns:
            测试运行对象，如果不存在则返回None
        """
        from src.models.test_case import TestRun

        try:
            file_path = os.path.join(self.test_runs_dir, f"{run_id}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return TestRun(**data)
        except Exception as e:
            logger.error(f"Failed to get test run {run_id}: {e}")
        return None

    def get_last_test_run(self) -> Optional:
        """
        获取最后一个测试运行
        
        Returns:
            最后一个测试运行对象，如果不存在则返回None
        """
        runs = self.list_test_runs()
        if runs:
            return runs[0]
        return None
