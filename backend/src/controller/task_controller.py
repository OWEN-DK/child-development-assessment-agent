import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.config import settings
from src.core.graph import agent_app
from src.core.llm.factory import LLMFramework, LLMServiceFactory
from src.core.tracing.context import trace_context
from src.schemas import AgentState, UserInput
from src.schemas.common import APIResponse
from src.utils.exceptions import AssessmentFailedException, InternalServerErrorException
from src.utils.logger import logger

router = APIRouter()


@router.get("/health")
async def health_check():
    return APIResponse.success(data={"status": "ok"})


@router.post("/assess")
async def assess_development(user_input: UserInput):
    """
    接收儿童画像和拟定计划，返回评估报告。
    支持流式输出 (is_streaming=True)
    """
    try:
        # 创建 Trace 上下文
        async with trace_context(
            name="assessment_run",
            metadata={
                "child_profile_id": user_input.child_profile.get("id", "unknown")
                if isinstance(user_input.child_profile, dict)
                else "unknown",
            },
        ) as tid:
            logger.info(f"Trace created: {tid} for assessment run")

            # 初始化 State
            initial_state = AgentState(
                child_profile=user_input.child_profile,
                proposed_plan=user_input.proposed_plan,
                messages=[],
                is_streaming=user_input.is_streaming,
            )

            # 调用 LangGraph
            result = await agent_app.ainvoke(initial_state)

            # 检查是否为流式模式
            if user_input.is_streaming and result.get("report_prompts"):
                return StreamingResponse(
                    stream_report_generation(result), media_type="text/event-stream"
                )

            # 非流式模式直接返回结果
            if "final_report" in result:
                return APIResponse.success(data=result["final_report"])
            else:
                raise AssessmentFailedException(message="Failed to generate report")

    except Exception as e:
        raise InternalServerErrorException(message=str(e))


async def stream_report_generation(result: dict):
    """
    流式生成报告内容
    格式: Server-Sent Events (SSE)
    - event: data (结构化数据)
    - event: message (Markdown 内容片段)
    - event: done (完成)
    """
    final_report = result["final_report"]
    prompts = result["report_prompts"]

    # 1. 发送结构化数据 (Metadata)
    metadata = {
        "score": final_report.structured_data.get("score", 0),
        "radar_chart": final_report.structured_data.get("radar_chart", {}),
        "key_suggestions": final_report.structured_data.get("key_suggestions", []),
    }
    yield f"event: data\ndata: {json.dumps(metadata, ensure_ascii=False)}\n\n"

    # 2. 流式生成 Markdown 内容
    logger.info(
        f"Starting streaming report generation, prompts count: {len(prompts)}, prompt length: {len(prompts[0]) if prompts else 0}"
    )
    if settings.dashscope_api_key and prompts:
        # 顺序生成所有部分以保证流的顺序
        for i, prompt in enumerate(prompts):
            try:
                # 使用工厂创建 LLM 实例
                llm = LLMServiceFactory.create(
                    framework=LLMFramework.LLAMAINDEX,
                    model_name=settings.llm_models["report_generation"],
                    scenario="report_generation_streaming",
                    temperature=0.7,
                )

                # 构建提示词
                from src.schemas import LLMMessage, LLMRequest

                messages = [
                    LLMMessage(
                        role="system",
                        content="你是一个专业的儿童发展评估报告撰写专家，根据提供的评估数据生成清晰、专业、易于家长理解的Markdown格式报告。",
                    ),
                    LLMMessage(role="user", content=prompt),
                ]

                # 使用流式聊天接口
                logger.info(f"Starting LLM stream for prompt {i + 1}/{len(prompts)}")
                chunk_count = 0
                async for delta in llm.chat_stream(
                    LLMRequest(
                        messages=messages,
                        model_name=settings.llm_models["report_generation"],
                        temperature=0.7,
                        max_tokens=8000,
                        scenario="report_generation_streaming",
                        prompt_key="report_generation",
                    )
                ):
                    chunk_count += 1
                    if chunk_count % 10 == 0:
                        logger.debug(
                            f"Received chunk {chunk_count}, delta length: {len(delta)}"
                        )
                    safe_delta = json.dumps(delta, ensure_ascii=False)
                    yield f"event: message\ndata: {safe_delta}\n\n"
                logger.info(
                    f"Completed LLM stream for prompt {i + 1}, total chunks: {chunk_count}"
                )

                # 多部分之间添加分隔符
                if i < len(prompts) - 1:
                    sep = "\n\n"
                    yield f"event: message\ndata: {json.dumps(sep, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"Error during prompt {i + 1} generation: {e}")
                error_msg = f"\n[Generation Error: {str(e)}]\n"
                yield f"event: message\ndata: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
    else:
        # Fallback if no API key
        fallback_msg = "AI Service Unavailable. Showing fallback data.\n\n"
        yield f"event: message\ndata: {json.dumps(fallback_msg)}\n\n"

    # 3. 发送完成信号
    logger.info("Streaming report generation completed successfully")
    yield "event: done\ndata: [DONE]\n\n"
