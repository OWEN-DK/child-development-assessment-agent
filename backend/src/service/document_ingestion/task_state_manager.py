import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.config import settings
from src.utils.logger import logger


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStateManager:
    def __init__(self, state_expire_days: int = 7):
        self.task_dir = os.path.join(settings.data_dir, "import_tasks")
        self.state_expire_days = state_expire_days
        os.makedirs(self.task_dir, exist_ok=True)
        self._cleanup_expired_tasks()

    def _cleanup_expired_tasks(self) -> None:
        now = datetime.now()
        expire_threshold = now - timedelta(days=self.state_expire_days)
        for filename in os.listdir(self.task_dir):
            if not filename.endswith(".json"):
                continue
            file_path = os.path.join(self.task_dir, filename)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if mtime < expire_threshold:
                    os.remove(file_path)
                    logger.info(f"Cleaned up expired import task state: {filename}")
            except Exception as e:
                logger.warning(f"Failed to cleanup task state {filename}: {e}")

    def save_task_state(self, task_id: str, state: Dict[str, Any]) -> None:
        state_path = os.path.join(self.task_dir, f"{task_id}.json")
        state["updated_at"] = datetime.now().isoformat()
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        state_path = os.path.join(self.task_dir, f"{task_id}.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load task state {task_id}: {e}")
                return None
        return None

    def load_task_by_file_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        for filename in os.listdir(self.task_dir):
            if not filename.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.task_dir, filename), "r", encoding="utf-8") as f:
                    state = json.load(f)
                    if state.get("file_hash") == file_hash and state.get("status") == TaskStatus.COMPLETED:
                        return state
            except Exception:
                continue
        return None

    def delete_task_state(self, task_id: str) -> None:
        state_path = os.path.join(self.task_dir, f"{task_id}.json")
        if os.path.exists(state_path):
            try:
                os.remove(state_path)
            except Exception as e:
                logger.warning(f"Failed to delete task state {task_id}: {e}")


task_state_manager = TaskStateManager()
