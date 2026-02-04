from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Literal
from contextlib import asynccontextmanager
import aiosqlite
import os

from app.graph.workflow import DebateWorkflow

from dotenv import load_dotenv
load_dotenv()

class DebateInitiateRequest(BaseModel):
    topic: str
    "해당 세션에서 토론할 주제입니다."
    user_side: Literal["positive", "negative"]
    "사용자가 맡을 토론자 역할입니다."
    session_id: Optional[str] = None
    "생성한 세션의 id입니다. 지정하지 않으면 새로 생성됩니다."

# 전역 인스턴스
workflow_manager = DebateWorkflow()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔄 Connecting to DB and Compiling Graph...")
    async with aiosqlite.connect("debate_history.db") as db_conn:
        await workflow_manager.compile(db_conn)
        yield
        print("🛑 DB Connection Closed")

app = FastAPI(lifespan=lifespan)

# 정적 파일 제공
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    """정적 테스트 페이지 제공"""
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.post("/debate/create")
async def initiate_debate(request: DebateInitiateRequest):
    session_id = await workflow_manager.generate_debate(
        session_id=request.session_id,
        topic=request.topic,
        user_side=request.user_side
    )
    return {"session_id": session_id}
    

@app.websocket("/ws/debate/{session_id}")
async def debate_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    if not await workflow_manager.is_session_valid(session_id):
        print(f"❌ Invalid Session ID access attempt: {session_id}")
        await websocket.send_json({
            "type": "error", 
            "content": "유효하지 않거나 만료된 세션입니다. 세션을 먼저 생성해주세요."
        })
        await websocket.close(code=1008) # 1008: Policy Violation
        return
    
    config = {"configurable": {"thread_id": session_id}}
    while True:
        debate_gen = workflow_manager.run_debate(session_id)
        should_continue = False
        try:
            async for event in debate_gen:
                if event.get("type") == "message":
                    await websocket.send_json(event)
            
            state = await workflow_manager.app.aget_state(config)
            if state.next and "human" in state.next:
                await websocket.send_json({
                    "type": "input_request",
                    "node": "human",
                })
                
                # 사용자 입력 대기
                user_msg = await websocket.receive_text()
                
                await workflow_manager.user_input(session_id, user_msg)
                continue 
            else:
                await websocket.send_json({"type": "status", "content": "토론이 종료되었습니다."})
                await websocket.close()
                break

        except WebSocketDisconnect:
            break
        except Exception as e:
            print(f"Error: {e}")
            break