import hashlib
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import aiofiles

from src.config import settings
from src.core.llm.factory import LLMFramework, LLMServiceFactory, LLMServiceFactoryCompat
from src.schemas import LLMMessage, LLMRequest
from src.utils.logger import logger


class MemoryManager:
    """长期记忆管理系统，管理用户记忆和智能体记忆"""

    def __init__(self):
        self.llm_available = bool(settings.dashscope_api_key)

        # 内存存储
        self.user_memory: Dict[str, List[Dict]] = {}  # user_id -> 记忆列表
        self.agent_memory: List[Dict] = []  # 智能体全局记忆
        self.enable_memory = settings.rag_config.get("memory", {}).get("enabled", True)

        # 持久化存储路径
        self.storage_dir = settings.rag_storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.memory_file = os.path.join(self.storage_dir, "memory_store.json")
        self._load_memory()

    def _load_memory(self):
        """从本地 JSON 文件加载记忆"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.user_memory = data.get("user_memory", {})
                    self.agent_memory = data.get("agent_memory", [])
                logger.info("Successfully loaded memory from local storage.")
            except Exception as e:
                logger.error(f"Failed to load memory from {self.memory_file}: {e}")

    async def _save_memory_async(self):
        """异步保存记忆到本地 JSON 文件"""
        try:
            data = {"user_memory": self.user_memory, "agent_memory": self.agent_memory}
            async with aiofiles.open(self.memory_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Failed to save memory to {self.memory_file}: {e}")

    async def extract_memory_from_session(self, session_id: str, user_id: str = None):
        """从会话中提取长期记忆"""
        if not self.enable_memory:
            return

        try:
            session_history = await self._get_session_history(session_id)
            if not session_history:
                return

            # 提取用户偏好
            user_preferences = await self._extract_user_preferences(
                session_history, user_id
            )
            # 提取任务经验
            task_experiences = await self._extract_task_experiences(session_history)

            # 保存到记忆库
            if user_id and user_preferences:
                await self._save_user_memory(user_id, user_preferences)

            if task_experiences:
                await self._save_agent_memory(task_experiences)

            # 持久化
            await self._save_memory_async()

            logger.info(
                f"Extracted {len(user_preferences)} user preferences and {len(task_experiences)} task experiences from session {session_id}"
            )

        except Exception as e:
            logger.warning(f"Memory extraction failed: {e}")

    async def get_relevant_memory(
        self, query: str, user_id: str = None, limit: int = 3
    ) -> List[str]:
        """获取相关记忆补充到检索上下文"""
        if not self.enable_memory:
            return []

        memories = []

        if user_id and user_id in self.user_memory:
            user_memories = await self._search_user_memory(user_id, query, limit)
            memories.extend(user_memories)

        agent_memories = await self._search_agent_memory(
            query, max(0, limit - len(memories))
        )
        memories.extend(agent_memories)

        logger.debug(f"Retrieved {len(memories)} relevant memories for query: {query}")
        return memories

    async def add_user_memory(
        self,
        user_id: str,
        memory: str,
        memory_type: str = "preference",
        tags: List[str] = None,
    ):
        """添加用户记忆"""
        if not self.enable_memory:
            return

        if user_id not in self.user_memory:
            self.user_memory[user_id] = []

        memory_entry = {
            "id": hashlib.md5(
                f"{user_id}_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:8],
            "content": memory,
            "type": memory_type,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "last_accessed_at": datetime.now().isoformat(),
            "access_count": 0,
        }

        self.user_memory[user_id].append(memory_entry)
        await self._save_memory_async()
        logger.debug(f"Added user memory for {user_id}: {memory[:50]}...")

    async def add_agent_memory(
        self, memory: str, memory_type: str = "experience", tags: List[str] = None
    ):
        """添加智能体记忆"""
        if not self.enable_memory:
            return

        memory_entry = {
            "id": hashlib.md5(
                f"agent_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:8],
            "content": memory,
            "type": memory_type,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "last_accessed_at": datetime.now().isoformat(),
            "access_count": 0,
        }

        self.agent_memory.append(memory_entry)
        await self._save_memory_async()
        logger.debug(f"Added agent memory: {memory[:50]}...")

    async def _get_session_history(self, session_id: str) -> List[Dict]:
        """获取会话历史，通过读取本地的会话存储文件获取历史记录"""
        # 这里模拟一个从本地持久化会话文件获取历史记录的逻辑
        # 实际生产环境中应通过依赖注入引入 SessionService 获取
        session_file = os.path.join(self.storage_dir, f"session_{session_id}.json")
        if os.path.exists(session_file):
            try:
                async with aiofiles.open(session_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)
                    return data.get("history", [])
            except Exception as e:
                logger.error(f"Failed to read session history for {session_id}: {e}")
        return []

    async def _extract_user_preferences(
        self, session_history: List[Dict], user_id: str = None
    ) -> List[str]:
        """从会话历史中提取用户偏好"""
        if not self.llm_available:
            return []

        try:
            # 构建会话历史文本
            history_text = "\n".join(
                [
                    f"{msg.get('role', '')}: {msg.get('content', '')}"
                    for msg in session_history[-10:]
                ]
            )

            prompt = f"""
            请从以下儿童发展咨询会话历史中提取用户（家长的偏好和常见需求，每条简洁明了，不超过10条：
            会话历史：
            {history_text}
            
            输出格式：每行一条偏好，不要其他说明。
            """

            # 使用工厂创建 LLM 实例
            llm = LLMServiceFactoryCompat.create(
                framework=LLMFramework.LLAMAINDEX,
                model_name=settings.llm_models.get("memory_extraction", "qwen-turbo"),
                scenario="memory_extraction",
                temperature=0.3,
            )

            messages = [
                LLMMessage(
                    role="system",
                    content="你是一个用户偏好分析专家，擅长从对话中提取用户的需求和偏好。",
                ),
                LLMMessage(role="user", content=prompt),
            ]

            response = await llm.chat(
                LLMRequest(
                    messages=messages,
                    model_name=settings.llm_models.get(
                        "memory_extraction", "qwen-turbo"
                    ),
                    temperature=0.3,
                    max_tokens=1024,
                    scenario="memory_extraction",
                    prompt_key="user_preference_extraction",
                )
            )
            preferences = [
                p.strip() for p in response.content.strip().split("\n") if p.strip()
            ]
            return preferences[:10]

        except Exception as e:
            logger.warning(f"User preference extraction failed: {e}")
            return []

    async def _extract_task_experiences(self, session_history: List[Dict]) -> List[str]:
        """从会话历史中提取任务执行经验"""
        if not self.llm_available:
            return []

        try:
            # 构建会话历史文本
            history_text = "\n".join(
                [
                    f"{msg.get('role', '')}: {msg.get('content', '')}"
                    for msg in session_history
                ]
            )

            prompt = f"""
            请从以下儿童发展咨询会话历史中提取可以复用的经验和最佳实践，每条简洁明了，不超过5条：
            会话历史：
            {history_text}
            
            输出格式：每行一条经验，不要其他说明。
            """

            # 使用工厂创建 LLM 实例
            llm = LLMServiceFactoryCompat.create(
                framework=LLMFramework.LLAMAINDEX,
                model_name=settings.llm_models.get("memory_extraction", "qwen-turbo"),
                scenario="memory_extraction",
                temperature=0.3,
            )

            messages = [
                LLMMessage(
                    role="system",
                    content="你是一个任务经验总结专家，擅长从对话中提取可复用的最佳实践。",
                ),
                LLMMessage(role="user", content=prompt),
            ]

            response = await llm.chat(
                LLMRequest(
                    messages=messages,
                    model_name=settings.llm_models.get(
                        "memory_extraction", "qwen-turbo"
                    ),
                    temperature=0.3,
                    max_tokens=1024,
                    scenario="memory_extraction",
                    prompt_key="task_experience_extraction",
                )
            )
            experiences = [
                e.strip() for e in response.content.strip().split("\n") if e.strip()
            ]
            return experiences[:5]

        except Exception as e:
            logger.warning(f"Task experience extraction failed: {e}")
            return []

    async def _save_user_memory(self, user_id: str, preferences: List[str]):
        """保存用户记忆"""
        for pref in preferences:
            # 避免重复记忆
            existing = [
                m for m in self.user_memory.get(user_id, []) if m["content"] == pref
            ]
            if not existing:
                await self.add_user_memory(user_id, pref, memory_type="preference")

    async def _save_agent_memory(self, experiences: List[str]):
        """保存智能体记忆"""
        for exp in experiences:
            # 避免重复记忆
            existing = [m for m in self.agent_memory if m["content"] == exp]
            if not existing:
                await self.add_agent_memory(exp, memory_type="experience")

    async def _search_user_memory(
        self, user_id: str, query: str, limit: int = 3
    ) -> List[str]:
        """搜索用户相关记忆"""
        if user_id not in self.user_memory:
            return []

        memories = self.user_memory[user_id]
        # 简单的关键词匹配，TODO: 后续改用向量检索
        query_lower = query.lower()
        relevant = []

        for mem in memories:
            # 简单相关性计算：包含关键词的优先
            score = 0
            content_lower = mem["content"].lower()
            if query_lower in content_lower:
                score += 2
            for tag in mem["tags"]:
                if tag.lower() in query_lower:
                    score += 1

            if score > 0:
                relevant.append((mem, score))

        # 按相关性和访问时间排序
        relevant.sort(key=lambda x: (x[1], x[0]["last_accessed_at"]), reverse=True)

        # 更新访问时间和计数
        result = []
        for mem, _ in relevant[:limit]:
            mem["last_accessed_at"] = datetime.now().isoformat()
            mem["access_count"] += 1
            result.append(mem["content"])

        return result

    async def _search_agent_memory(self, query: str, limit: int = 2) -> List[str]:
        """搜索智能体相关记忆"""
        if not self.agent_memory:
            return []

        # 简单的关键词匹配，TODO: 后续改用向量检索
        query_lower = query.lower()
        relevant = []

        for mem in self.agent_memory:
            score = 0
            content_lower = mem["content"].lower()
            if query_lower in content_lower:
                score += 2
            for tag in mem["tags"]:
                if tag.lower() in query_lower:
                    score += 1

            if score > 0:
                relevant.append((mem, score))

        # 按相关性和访问时间排序
        relevant.sort(key=lambda x: (x[1], x[0]["last_accessed_at"]), reverse=True)

        # 更新访问时间和计数
        result = []
        for mem, _ in relevant[:limit]:
            mem["last_accessed_at"] = datetime.now().isoformat()
            mem["access_count"] += 1
            result.append(mem["content"])

        return result

    def get_user_memory_stats(self, user_id: str) -> List[Dict]:
        """获取用户所有记忆"""
        return self.user_memory.get(user_id, [])

    def get_agent_memory_stats(self) -> List[Dict]:
        """获取智能体所有记忆"""
        return self.agent_memory.copy()

    async def clear_user_memory(self, user_id: str):
        """清空用户记忆"""
        if user_id in self.user_memory:
            del self.user_memory[user_id]
            await self._save_memory_async()
            logger.info(f"Cleared all memory for user {user_id}")

    async def clear_agent_memory(self):
        """清空智能体记忆"""
        self.agent_memory.clear()
        await self._save_memory_async()
        logger.info("Cleared all agent memory")


# 全局实例
memory_manager = MemoryManager()
