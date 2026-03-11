from fastapi import APIRouter, HTTPException
from src.model.schemas import UserInput, AgentState
from src.core.graph import agent_app

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.post("/assess")
async def assess_development(user_input: UserInput):
    """
    接收儿童画像和拟定计划，返回评估报告。
    """
    try:
        # 初始化 State
        initial_state = AgentState(
            child_profile=user_input.child_profile,
            proposed_plan=user_input.proposed_plan,
            messages=[]
        )
        
        # 调用 LangGraph
        result = await agent_app.ainvoke(initial_state)
        
        # 返回结果
        if "final_report" in result:
            return result["final_report"]
        else:
            raise HTTPException(status_code=500, detail="Failed to generate report")
            
    except Exception as e:
        # TODO: 更好的错误处理
        raise HTTPException(status_code=500, detail=str(e))
