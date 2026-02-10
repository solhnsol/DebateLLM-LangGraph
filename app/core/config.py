import logging
import sys

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
    logger_app = logging.getLogger("app")
    logger_app.setLevel(logging.DEBUG)