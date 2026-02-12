from sqlalchemy import MetaData, delete, select
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv
import os
load_dotenv()

DB_URL = os.environ.get("DB_URL")

if not DB_URL:
    raise RuntimeError("ERROR: DB_URL Not Set.")

class DBManager:
    def __init__(self):
        self.engine = create_async_engine(DB_URL)
        self.metadata = MetaData()
        self.checkpoints = None
        self.writes = None
    
    async def init_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(self._reflect_metadata)
    
    def _reflect_metadata(self, conn):
        self.metadata.reflect(bind=conn)

        if "checkpoints" in self.metadata.tables:
            self.checkpoints = self.metadata.tables["checkpoints"]
        if "writes" in self.metadata.tables:
            self.writes = self.metadata.tables["writes"]
        
        if self.checkpoints is None or self.writes is None:
            raise RuntimeError("ERROR: Required tables not found in the database.")

    async def delete_session(self, session_id: str):
        if self.checkpoints is None or self.writes is None:
            raise RuntimeError("ERROR: Tables not initialized.")
        async with self.engine.begin() as conn:
            await conn.execute(
                delete(self.checkpoints).where(self.checkpoints.c.thread_id == session_id)
            )
            await conn.execute(
                delete(self.writes).where(self.writes.c.thread_id == session_id)
            )

    async def get_all_sessions(self) -> list[str]:
        if self.checkpoints is None or self.writes is None:
            raise RuntimeError("ERROR: Tables not initialized.")
        async with self.engine.connect() as conn:
            stmt = select(self.checkpoints.c.thread_id).distinct()
            
            result = await conn.execute(stmt)
            
            return result.scalars().all()

db_manager = DBManager()