"""自定义知识管理 API 控制器

放置位置: backend/src/controller/custom_knowledge_controller.py
端点:
  POST   /api/v1/custom-knowledge/upload    上传 .md 文件（最多 5 份）
  GET    /api/v1/custom-knowledge           列表查询
  GET    /api/v1/custom-knowledge/{rule_id} 获取详情
  PUT    /api/v1/custom-knowledge/{rule_id} 更新
  DELETE /api/v1/custom-knowledge/{rule_id} 删除
  POST   /api/v1/custom-knowledge/match     匹配测试（调试用）
"""

from __future__ import annotations
import logging
from typing import List, Optional
from fastapi import APIRouter, Path, Query, UploadFile, File
from pydantic import BaseModel, Field
from src.schemas.common import APIResponse

logger = logging.getLogger(__name__)


class MatchRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)


class UpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None


class CustomKnowledgeController:
    def __init__(self, service):
        self._svc = service

    def register(self, router: APIRouter) -> None:
        router.add_api_route("/confirm", self.confirm_save,
                              methods=["POST"], summary="确认入库（双写 Neo4j + MySQL）")
        router.add_api_route("/upload", self.upload,
                              methods=["POST"], summary="上传 .md 文件（最多 5 份）")
        router.add_api_route("/", self.list_items,
                              methods=["GET"], summary="列表查询")
        router.add_api_route("/match", self.match_test,
                              methods=["POST"], summary="匹配测试")
        router.add_api_route("/{rule_id}", self.get_item,
                              methods=["GET"], summary="获取详情")
        router.add_api_route("/{rule_id}", self.update_item,
                              methods=["PUT"], summary="更新")
        router.add_api_route("/{rule_id}", self.delete_item,
                              methods=["DELETE"], summary="删除")

    async def upload(self, files: List[UploadFile] = File(...)):
        """上传 .md 文件 → AI 解析 → 返回规则列表（待用户审核确认）"""
        if len(files) > 5:
            return APIResponse.error(400, "too_many_files", "单次最多上传 5 份文件")
        parsed = []
        for f in files:
            if not f.filename.endswith(".md"):
                return APIResponse.error(400, "invalid_format", f"仅支持 .md 文件: {f.filename}")
            content = (await f.read()).decode("utf-8")
            if len(content) > 50 * 1024:
                return APIResponse.error(400, "file_too_large", f"文件过大: {f.filename}")
            parsed.append({"filename": f.filename, "content": content})

        rules = await self._svc.upload_and_parse(parsed)
        if not rules:
            return APIResponse.error(400, "no_rules", "未从文件中提取到规则")
        enriched = await self._svc.generate_keywords_and_patterns(rules)
        return APIResponse.success({"rules": enriched, "total": len(enriched)})

    async def list_items(
        self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    ):
        items = await self._svc._repo.get_all_enabled(limit=page_size)
        return APIResponse.success({
            "items": [
                {"rule_id": i.rule_id, "priority": i.priority, "enabled": i.enabled}
                for i in items
            ],
            "total": len(items),
        })

    async def get_item(self, rule_id: str = Path(...)):
        rule = await self._svc._repo.get_custom_rule(rule_id)
        if not rule:
            return APIResponse.error(404, "not_found", "条目不存在")
        rels = await self._svc._repo.get_custom_rule_relations(rule_id)
        return APIResponse.success({**rule, "relations": rels})

    async def update_item(self, request: UpdateRequest, rule_id: str = Path(...)):
        data = {k: v for k, v in request.model_dump().items() if v is not None}
        if not data:
            return APIResponse.error(400, "empty_update", "无更新字段")
        await self._svc._repo.upsert_index(rule_id, data)
        return APIResponse.success({"updated": True})

    async def delete_item(self, rule_id: str = Path(...)):
        await self._svc._repo.delete_custom_rule(rule_id)
        await self._svc._repo.delete_index(rule_id)
        return APIResponse.success({"deleted": True})

    async def confirm_save(self, request: dict):
        """确认入库: 双写 Neo4j CustomRule + MySQL 索引"""
        rules = request.get("rules", [])
        if not rules:
            return APIResponse.error(400, "no_rules", "无规则数据")
        result = await self._svc.confirm_and_save(rules)
        return APIResponse.success(result)

    async def match_test(self, request: MatchRequest):
        result = await self._svc.match(request.question)
        return APIResponse.success({
            "hit": result.hit,
            "match_channel": result.match_channel,
            "latency_ms": result.latency_ms,
            "matched_count": len(result.matched_items),
            "matched_items": [
                {"rule_id": i.get("rule_id"), "title": i.get("title")}
                for i in result.matched_items
            ],
        })