"""BM25 独立索引管理器

为 Chroma/Milvus 后端维护独立 BM25 关键词索引。
ES 后端使用 ES 内置 BM25，不需要此模块。

索引结构：storage/bm25/{tenant_id}/{kb_id}/
├── index.json       # BM25Okapi 序列化索引
├── id_map.json      # 内部 ID → chunk_id 映射
└── metadata.json    # 创建时间、文档数、k1=1.5, b=0.75
"""
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional

from src.utils.logger import logger


class BM25IndexManager:
    """BM25 独立索引管理器"""

    # 固定参数
    K1 = 1.5
    B = 0.75

    def __init__(self, storage_dir: str = "./app_data/storage/bm25"):
        self._storage_dir = storage_dir
        self._locks: dict[str, asyncio.Lock] = {}  # kb_id → Lock

    def _get_lock(self, kb_id: str) -> asyncio.Lock:
        """获取知识库级别的写锁"""
        if kb_id not in self._locks:
            self._locks[kb_id] = asyncio.Lock()
        return self._locks[kb_id]

    def _index_dir(self, kb_id: str, tenant_id: str) -> Path:
        """获取索引目录"""
        return Path(self._storage_dir) / tenant_id / kb_id

    async def add_chunks(
        self, kb_id: str, tenant_id: str, chunks: list[dict[str, Any]]
    ) -> None:
        """增量添加分块到 BM25 索引

        Args:
            kb_id: 知识库 ID
            tenant_id: 租户 ID
            chunks: [{"chunk_id": str, "content": str}, ...]
        """
        async with self._get_lock(kb_id):
            index_dir = self._index_dir(kb_id, tenant_id)
            index_dir.mkdir(parents=True, exist_ok=True)

            # 加载现有索引
            index_data, id_map = self._load_index(index_dir)

            # 添加新分块
            for chunk in chunks:
                chunk_id = chunk["chunk_id"]
                content = chunk["content"]
                tokens = self._tokenize(content)
                internal_id = len(id_map)
                id_map[str(internal_id)] = chunk_id
                index_data.append(tokens)

            # 保存索引
            self._save_index(index_dir, index_data, id_map)
            logger.info(f"BM25 索引增量添加 {len(chunks)} 个分块: {kb_id}")

    async def remove_chunks(
        self, kb_id: str, tenant_id: str, chunk_ids: list[str]
    ) -> None:
        """按 chunk_ids 删除分块"""
        async with self._get_lock(kb_id):
            index_dir = self._index_dir(kb_id, tenant_id)
            if not index_dir.exists():
                return

            index_data, id_map = self._load_index(index_dir)

            # 找到需要删除的内部 ID
            to_remove = set()
            for internal_id, chunk_id in id_map.items():
                if chunk_id in chunk_ids:
                    to_remove.add(int(internal_id))

            if not to_remove:
                return

            # 重建索引（排除删除的）
            new_index_data = []
            new_id_map = {}
            new_internal_id = 0
            for i, tokens in enumerate(index_data):
                if i not in to_remove:
                    new_index_data.append(tokens)
                    new_id_map[str(new_internal_id)] = id_map[str(i)]
                    new_internal_id += 1

            self._save_index(index_dir, new_index_data, new_id_map)
            logger.info(f"BM25 索引删除 {len(to_remove)} 个分块: {kb_id}")

    async def search(
        self, kb_id: str, tenant_id: str, query: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """BM25 搜索

        Args:
            query: 查询文本

        Returns:
            [{"chunk_id": str, "score": float}, ...]
        """
        index_dir = self._index_dir(kb_id, tenant_id)
        if not index_dir.exists():
            return []

        index_data, id_map = self._load_index(index_dir)
        if not index_data:
            return []

        # 计算 BM25 分数
        query_tokens = self._tokenize(query)
        scores = self._bm25_scores(query_tokens, index_data)

        # 排序取 top_k
        scored = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for idx, score in scored:
            chunk_id = id_map.get(str(idx), "")
            if chunk_id and score > 0:
                results.append({"chunk_id": chunk_id, "score": score})

        return results

    async def rebuild(
        self, kb_id: str, tenant_id: str, chunks: list[dict[str, Any]]
    ) -> None:
        """全量重建索引"""
        async with self._get_lock(kb_id):
            index_dir = self._index_dir(kb_id, tenant_id)
            index_dir.mkdir(parents=True, exist_ok=True)

            index_data = []
            id_map = {}

            for i, chunk in enumerate(chunks):
                tokens = self._tokenize(chunk["content"])
                index_data.append(tokens)
                id_map[str(i)] = chunk["chunk_id"]

            self._save_index(index_dir, index_data, id_map)
            logger.info(f"BM25 索引全量重建 {len(chunks)} 个分块: {kb_id}")

    async def delete_index(self, kb_id: str, tenant_id: str) -> None:
        """删除整个索引目录"""
        import shutil

        index_dir = self._index_dir(kb_id, tenant_id)
        if index_dir.exists():
            shutil.rmtree(index_dir)
            logger.info(f"BM25 索引目录删除: {kb_id}")

    async def get_info(self, kb_id: str, tenant_id: str) -> dict[str, Any]:
        """获取索引信息"""
        index_dir = self._index_dir(kb_id, tenant_id)
        if not index_dir.exists():
            return {"exists": False, "chunk_count": 0}

        metadata_path = index_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            return {"exists": True, **metadata}

        return {"exists": True, "chunk_count": 0}

    def _tokenize(self, text: str) -> list[str]:
        """中文分词"""
        import jieba
        return list(jieba.cut(text))

    def _bm25_scores(
        self, query_tokens: list[str], corpus: list[list[str]]
    ) -> list[float]:
        """计算 BM25 分数"""
        import math

        n_docs = len(corpus)
        if n_docs == 0:
            return []

        # 计算平均文档长度
        avg_dl = sum(len(doc) for doc in corpus) / n_docs

        # 计算 IDF
        df = {}
        for doc in corpus:
            unique_tokens = set(doc)
            for token in unique_tokens:
                df[token] = df.get(token, 0) + 1

        idf = {}
        for token, freq in df.items():
            idf[token] = math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1)

        # 计算每个文档的 BM25 分数
        scores = []
        for doc in corpus:
            score = 0.0
            dl = len(doc)
            tf = {}
            for token in doc:
                tf[token] = tf.get(token, 0) + 1

            for token in query_tokens:
                if token not in tf:
                    continue
                token_tf = tf[token]
                token_idf = idf.get(token, 0)
                numerator = token_tf * (self.K1 + 1)
                denominator = token_tf + self.K1 * (1 - self.B + self.B * dl / avg_dl)
                score += token_idf * numerator / denominator

            scores.append(score)

        return scores

    def _load_index(self, index_dir: Path) -> tuple[list, dict]:
        """加载索引文件"""
        index_path = index_dir / "index.json"
        id_map_path = index_dir / "id_map.json"

        if index_path.exists() and id_map_path.exists():
            with open(index_path, "r") as f:
                index_data = json.load(f)
            with open(id_map_path, "r") as f:
                id_map = json.load(f)
            return index_data, id_map

        return [], {}

    def _save_index(
        self, index_dir: Path, index_data: list, id_map: dict
    ) -> None:
        """保存索引文件"""
        from datetime import datetime

        with open(index_dir / "index.json", "w") as f:
            json.dump(index_data, f, ensure_ascii=False)

        with open(index_dir / "id_map.json", "w") as f:
            json.dump(id_map, f, ensure_ascii=False)

        metadata = {
            "chunk_count": len(index_data),
            "k1": self.K1,
            "b": self.B,
            "updated_at": datetime.utcnow().isoformat(),
        }
        with open(index_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, ensure_ascii=False)
