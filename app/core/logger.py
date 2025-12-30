import sys
from loguru import logger
import logging

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def setup_logging():
    # Remove all existing handlers
    logging.getLogger().handlers = [InterceptHandler()]
    
    # Configure Loguru
    logger.remove() # Remove default handler
    
    # Add console handler
    logger.add(
        sys.stdout, 
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file handler for errors
    logger.add(
        "logs/errors.log",
        level="ERROR",
        rotation="10 MB",
        retention="1 month",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )
    
    # Intercept standard logging messages (from libraries like Uvicorn)
    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    
    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)

# Export singleton logger
__all__ = ["logger", "setup_logging"]
