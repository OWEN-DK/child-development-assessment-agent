"""搜索服务（门面类）

同步搜索 + SSE 流式搜索的统一入口。
集成 PipelineCompiler 执行管道，处理白名单过滤、响应截断、top_k 控制。
"""
import json
import uuid
from typing import Any, Optional

from src.api.sse import SSEPublisher
from src.core.pipeline.compiler import PipelineCompiler
from src.core.pipeline.node_context import AuthContext
from src.schemas.search.response import (
    DegradationEvent,
    DomainResult,
    SearchResponse,
    TopChunk,
)
from src.schemas.search.request import SearchParams
from src.utils.logger import logger

# 响应大小限制（2MB）
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024

# 白名单允许的参数名
ALLOWED_PARAM_NAMES = {"top_k", "temperature", "filters", "max_domains", "response_top_k"}


class SearchService:
    """搜索服务"""

    def __init__(self, compiler: PipelineCompiler):
        self._compiler = compiler

    async def sync_search(
        self,
        pipeline_config: dict[str, Any],
        query: str,
        params: dict[str, Any],
        auth: AuthContext,
        allowed_param_whitelist: Optional[list[str]] = None,
    ) -> SearchResponse:
        """同步搜索

        Args:
            pipeline_config: 管道配置 JSON
            query: 查询文本
            params: 搜索参数
            auth: 认证上下文
            allowed_param_whitelist: 参数白名单（None=全部生效，非 None=仅白名单内生效）

        Returns:
            SearchResponse 搜索结果
        """
        run_id = str(uuid.uuid4()).replace("-", "")[:16]

        # 白名单过滤
        effective_params = self._filter_params(params, allowed_param_whitelist)

        try:
            # 编译 + 执行
            compiled = self._compiler.compile(pipeline_config)
            result = await self._compiler.execute(compiled, query, effective_params, auth)

            # 构建响应
            response = self._build_response(run_id, result)

            # 响应大小控制
            response = self._apply_response_top_k(
                response, effective_params.get("response_top_k")
            )
            response = self._enforce_response_size_limit(response)

            return response

        except Exception as e:
            logger.error(f"搜索执行失败: {e}")
            return SearchResponse(
                run_id=run_id,
                answer=f"搜索执行失败: {e}",
                degradation_events=[
                    DegradationEvent(
                        node_id="pipeline",
                        strategy="abort",
                        reason=str(e),
                    )
                ],
            )

    async def stream_search(
        self,
        pipeline_config: dict[str, Any],
        query: str,
        params: dict[str, Any],
        auth: AuthContext,
        publish_channel: str,
    ) -> None:
        """SSE 流式搜索

        通过 SSEPublisher 逐事件推送搜索进度和结果。

        Args:
            pipeline_config: 管道配置
            query: 查询文本
            params: 搜索参数
            auth: 认证上下文
            publish_channel: SSE 频道名
        """
        run_id = publish_channel.split(":")[-1] if ":" in publish_channel else str(uuid.uuid4()).replace("-", "")[:16]

        try:
            # 推送 run_started
            await SSEPublisher.publish(publish_channel, {
                "type": "run_started",
                "run_id": run_id,
            })

            # 编译 + 执行
            compiled = self._compiler.compile(pipeline_config)
            result = await self._compiler.execute(compiled, query, params, auth)

            # 推送融合完成
            await SSEPublisher.publish(publish_channel, {
                "type": "fusion_complete",
                "merged_count": len(result.get("sources", [])),
            })

            # 推送答案
            answer = result.get("answer", "")
            if answer:
                await SSEPublisher.publish(publish_channel, {
                    "type": "answer_streaming",
                    "delta_text": answer,
                    "sequence": 0,
                })

            # 推送引用
            for source in result.get("sources", [])[:5]:
                await SSEPublisher.publish(publish_channel, {
                    "type": "citation",
                    "chunk_id": source.get("chunk_id", ""),
                    "doc_name": source.get("doc_name", ""),
                    "score": source.get("rrf_score", source.get("score", 0)),
                })

            # 推送 run_completed
            await SSEPublisher.publish(publish_channel, {
                "type": "run_completed",
                "run_id": run_id,
                "total_latency_ms": result.get("execution_time_ms", 0),
                "answer_length": len(answer),
            })

            # 推送降级事件
            for event in result.get("degradation_events", []):
                await SSEPublisher.publish(publish_channel, {
                    "type": "degradation_event",
                    **event,
                })

        except Exception as e:
            logger.error(f"SSE 搜索失败: {e}")
            await SSEPublisher.publish(publish_channel, {
                "type": "run_failed",
                "run_id": run_id,
                "error_message": str(e),
            })

        finally:
            # 关闭连接
            await SSEPublisher.publish(publish_channel, {
                "type": "close",
                "code": 1000,
                "reason": "completed",
            })

    def _filter_params(
        self, params: dict[str, Any], whitelist: Optional[list[str]]
    ) -> dict[str, Any]:
        """白名单过滤参数

        Args:
            params: 原始参数
            whitelist: 白名单（None=全部生效）

        Returns:
            过滤后的参数
        """
        if whitelist is None:
            return params

        allowed = set(whitelist) & ALLOWED_PARAM_NAMES
        return {k: v for k, v in params.items() if k in allowed}

    def _build_response(self, run_id: str, result: dict[str, Any]) -> SearchResponse:
        """从管道执行结果构建搜索响应"""
        domain_results = []
        for dr in result.get("domain_results", []):
            candidates = dr.get("candidates", [])
            top_chunks = []
            for c in candidates[:10]:
                top_chunks.append(TopChunk(
                    chunk_id=c.get("chunk_id", ""),
                    doc_name=c.get("metadata", {}).get("doc_name", c.get("doc_name", "")),
                    text=c.get("content", c.get("text", "")),
                    score=c.get("rrf_score", c.get("score", 0)),
                ))
            domain_results.append(DomainResult(
                domain_id=dr.get("domain_id", ""),
                domain_name=dr.get("domain_name", ""),
                candidates=candidates,
                top_chunks=top_chunks,
                contributed_to_answer=dr.get("contributed_to_answer", False),
                error=dr.get("error"),
            ))

        degradation_events = [
            DegradationEvent(
                node_id=e.get("node_id", ""),
                node_type=e.get("node_type", ""),
                domain_id=e.get("domain_id", ""),
                strategy=e.get("strategy", "skip"),
                reason=e.get("error", e.get("reason", "")),
            )
            for e in result.get("degradation_events", [])
        ]

        return SearchResponse(
            run_id=run_id,
            answer=result.get("answer", ""),
            shortcut_activated=result.get("shortcut_activated", False),
            domain_results=domain_results,
            degradation_events=degradation_events,
        )

    def _apply_response_top_k(
        self, response: SearchResponse, top_k: Optional[int]
    ) -> SearchResponse:
        """限制每个域的 top_chunks 数量"""
        if top_k is None:
            return response

        for dr in response.domain_results:
            dr.top_chunks = dr.top_chunks[:top_k]
        return response

    def _enforce_response_size_limit(self, response: SearchResponse) -> SearchResponse:
        """检查响应大小，超过 2MB 则截断"""
        serialized = json.dumps(response.model_dump(), ensure_ascii=False)
        if len(serialized.encode("utf-8")) <= _MAX_RESPONSE_BYTES:
            return response

        # 截断每个域的 text 到 100 字
        for dr in response.domain_results:
            for chunk in dr.top_chunks:
                if len(chunk.text) > 100:
                    chunk.text = chunk.text[:100] + "..."

        response.truncated = True
        logger.warning("搜索响应超过 2MB，已截断 top_chunks.text")
        return response
