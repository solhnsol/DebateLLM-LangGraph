import logging
import sys
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_path() -> str:
    """
    DB_URL 환경 변수에서 SQLite 파일 경로를 추출합니다.
    """
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("ERROR: DB_URL Not Set.")
    
    # sqlite+aiosqlite:///./sqlite_db/debate_history.db 형식에서 경로 추출
    if db_url.startswith("sqlite+aiosqlite:///"):
        path = db_url.replace("sqlite+aiosqlite:///", "")
        # ./ 제거 (상대 경로 정규화)
        if path.startswith("./"):
            path = path[2:]
        return path
    elif db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "")
        if path.startswith("./"):
            path = path[2:]
        return path
    else:
        raise ValueError(f"Unsupported DB_URL format: {db_url}")

def setup_logging():
    """
    로깅 설정을 초기화합니다.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    logger_httpx = logging.getLogger("httpx")
    logger_httpx.setLevel(logging.WARNING)
    logger_gemini = logging.getLogger("google_genai")
    logger_gemini.setLevel(logging.WARNING)
    logger_app = logging.getLogger("app")
    logger_app.setLevel(logging.DEBUG)