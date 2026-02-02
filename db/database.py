from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os

# 환경 변수에서 DB URL을 가져오거나 기본값으로 로컬 SQLite 사용
# Async SQLite URL 형식: sqlite+aiosqlite:///...
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./debate.db")

# SQLite 사용 시 스레드 체크 옵션 해제 필요 (비동기에서도 SQLite 특성상 주의 필요)
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_async_engine(
    DATABASE_URL, 
    connect_args=connect_args,
    # echo=True  # 쿼리 로그 보고 싶으면 주석 해제
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
