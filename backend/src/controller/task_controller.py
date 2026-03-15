from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.model.schemas import UserInput, AgentState
from src.core.graph import agent_app
from llama_index.llms.dashscope import DashScope
from src.config.settings import settings
from src.utils.logger import logger
import json
import asyncio

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/assess")
async def assess_development(user_input: UserInput):
    """
    接收儿童画像和拟定计划，返回评估报告。
    支持流式输出 (is_streaming=True)
    """
    try:
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
            return result["final_report"]
        else:
            raise HTTPException(status_code=500, detail="Failed to generate report")

    except Exception as e:
        # TODO: 更好的错误处理
        raise HTTPException(status_code=500, detail=str(e))


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
    logger.info(f"Starting streaming report generation, prompts count: {len(prompts)}, prompt length: {len(prompts[0]) if prompts else 0}")
    if settings.dashscope_api_key and prompts:
        try:
            llm = DashScope(
                model=settings.llm_models["report_generation"],
                api_key=settings.dashscope_api_key,
                max_tokens=8000,
                temperature=0.7,
                top_p=0.8,
            )
            logger.info("LLM initialized successfully for streaming")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            error_msg = f"\n[LLM Initialization Error: {str(e)}]\n"
            yield f"event: message\ndata: {json.dumps(error_msg, ensure_ascii=False)}\n\n"

        # 顺序生成所有部分以保证流的顺序
        for i, prompt in enumerate(prompts):
            try:
                # 使用 stream_complete 方法进行流式生成
                # Note: LlamaIndex stream_complete returns a generator
                logger.info(f"Starting LLM stream for prompt {i+1}/{len(prompts)}")
                response_gen = await llm.astream_complete(prompt)
                chunk_count = 0
                async for chunk in response_gen:
                    # 获取当前 delta 内容
                    delta = chunk.delta
                    if delta:
                        chunk_count += 1
                        if chunk_count % 10 == 0:  # 每10个chunk打一次日志
                            logger.debug(f"Received chunk {chunk_count}, delta length: {len(delta)}")
                        # 替换换行符以适应 SSE 格式
                        # SSE format requires "data: <content>\n\n"
                        # We send JSON string to preserve newlines
                        safe_delta = json.dumps(delta, ensure_ascii=False)
                        yield f"event: message\ndata: {safe_delta}\n\n"
                logger.info(f"Completed LLM stream for prompt {i+1}, total chunks: {chunk_count}")

                # 多部分之间添加分隔符
                if i < len(prompts) - 1:
                    sep = "\n\n"
                    yield f"event: message\ndata: {json.dumps(sep, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"Error during prompt {i+1} generation: {e}")
                error_msg = f"\n[Generation Error: {str(e)}]\n"
                yield f"event: message\ndata: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
    else:
        # Fallback if no API key
        fallback_msg = "AI Service Unavailable. Showing fallback data.\n\n"
        yield f"event: message\ndata: {json.dumps(fallback_msg)}\n\n"

    # 3. 发送完成信号
    logger.info("Streaming report generation completed successfully")
    yield "event: done\ndata: [DONE]\n\n"
