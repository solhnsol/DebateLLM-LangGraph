from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import aiosqlite
import os

from app.models.schemas import DebateInitiateRequest
from app.core.config import setup_logging, get_db_path
from app.db.db_manager import db_manager
from app.graph.workflow import workflow

from dotenv import load_dotenv
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    print("🔄 Connecting to DB and Compiling Graph...")
    db_path = get_db_path()
    
    # DB 파일이 위치할 디렉토리 생성
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print(f"📁 Created database directory: {db_dir}")
    
    async with aiosqlite.connect(db_path) as db_conn:
        await workflow.compile(db_conn)
        await db_manager.init_tables()
        yield
        await db_manager.engine.dispose()
        print("🛑 DB Connection Closed")

app = FastAPI(lifespan=lifespan)
# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]
)
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
    session_id = await workflow.generate_debate(
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
    if not await workflow.is_session_valid(session_id):
        print(f"❌ Invalid Session ID access attempt: {session_id}")
        await websocket.send_json({
            "type": "error", 
            "content": "유효하지 않거나 만료된 세션입니다. 세션을 먼저 생성해주세요."
        })
        await websocket.close(code=1008) # 1008: Policy Violation
        return
    
    config = {"configurable": {"thread_id": session_id}}
    while True:
        debate_gen = workflow.run_debate(session_id)
        try:
            async for event in debate_gen:
                await websocket.send_json(event)
            
            state = await workflow.app.aget_state(config)
            
            if state.next and "human" in state.next:
                await websocket.send_json({
                    "type": "input_request",
                    "node": "human",
                    "step": workflow.current_step[session_id] + 1
                })
                
                # 사용자 입력 대기
                user_msg = await websocket.receive_text()
                
                await workflow.user_input(session_id, user_msg)
                continue 
            else:
                await websocket.send_json({"type": "status", "content": "END"})
                await websocket.close()
                break

        except WebSocketDisconnect:
            break
        except Exception as e:
            raise e