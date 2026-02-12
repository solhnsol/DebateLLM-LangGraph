from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Literal
from contextlib import asynccontextmanager
import aiosqlite
import os

from app.graph.workflow import DebateWorkflow
from app.core.config import setup_logging
from app.db.db_manager import DBManager

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
db_manager = DBManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    print("🔄 Connecting to DB and Compiling Graph...")
    async with aiosqlite.connect("sqlite_db/debate_history.db") as db_conn:
        await workflow_manager.compile(db_conn)
        await db_manager.init_tables()
        yield
        await db_manager.engine.dispose()
        print("🛑 DB Connection Closed")

app = FastAPI(lifespan=lifespan)

# 정적 파일 제공
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    """테스트 페이지 보기"""
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/sessions")
async def get_sessions():
    """현재 존재하는 세션 목록 가져오기"""
    sessions = await db_manager.get_all_sessions()
    return {"status": "success", "sessions": sessions}

@app.post("/sessions")
async def create_session(request: DebateInitiateRequest):
    """세션 생성하기"""
    session_id = await workflow_manager.generate_debate(
        session_id=request.session_id,
        topic=request.topic,
        user_side=request.user_side
    )
    return {"status": "success", "session_id": session_id}

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """세션 삭제하기"""
    try:
        await db_manager.delete_session(session_id)
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.websocket("/ws/{session_id}")
async def debate_ws(websocket: WebSocket, session_id: str):
    """WebSocket 연결해서 토론 진행하기"""
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
        try:
            async for event in debate_gen:
                await websocket.send_json(event)
            
            state = await workflow_manager.app.aget_state(config)
            
            if state.next and "human" in state.next:
                await websocket.send_json({
                    "type": "input_request",
                    "node": "human",
                    "step": workflow_manager.current_step + 1
                })
                
                # 사용자 입력 대기
                user_msg = await websocket.receive_text()
                
                await workflow_manager.user_input(session_id, user_msg)
                continue 
            else:
                await websocket.send_json({"type": "status", "content": "END"})
                await websocket.close()
                break

        except WebSocketDisconnect:
            break
        except Exception as e:
            raise e